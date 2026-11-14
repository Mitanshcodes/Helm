# OWNER: shared (development dataset capture)
"""Bounded asynchronous video + signal capture, enabled explicitly by the developer."""
import dataclasses
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import threading
import uuid

import numpy as np


def jsonable(value):
    if dataclasses.is_dataclass(value):
        return {f.name: jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in value]
    return value


class DevRecording:
    def __init__(self, root, kind, player, game, calibration, model, mapping, fps=30.0,
                 source='camera', label=None):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        self.path = Path(root).expanduser().resolve() / f'{stamp}-{kind}-{uuid.uuid4().hex[:8]}'
        self.kind, self.error, self.frames = kind, None, 0
        self.finished = threading.Event()
        self.ready = threading.Event()
        self._stop = threading.Event()
        self._queue = queue.Queue(maxsize=64)
        self._artifacts = threading.RLock()
        self._pending_models = 0
        self._model_version = 0
        self._video_done = False
        self._fps = fps
        self._context = dict(schema=1, kind=kind, player=player, game=game, started_utc=stamp,
                             video='video.avi', signals='signals.jsonl', video_fps=fps,
                             video_mirrored=False, timing='signals timestamps are authoritative; frame_index maps to video index',
                             source=source, label=label)
        self._thread = threading.Thread(target=self._run, args=(calibration, model, mapping), daemon=False)
        self._thread.start()

    def submit(self, bgr, frame, signals, activations, scores, control, progress):
        if self._stop.is_set():
            return False
        return self._put(('frame', bgr.copy(), frame, signals, dict(activations), dict(scores), control, progress))

    def calibration(self, value):
        return self._put(('calibration', value))

    def _put(self, item):
        try:
            self._queue.put_nowait(item)
            return True
        except queue.Full:
            self.error = 'Recording stopped: video writer could not keep up; dataset is incomplete'
            self._stop.set()
            return False

    def save_model(self, model, version=None):
        """Only called on a worker; may complete after video capture stopped."""
        self.ready.wait()
        try:
            with self._artifacts:
                if self.path.exists() and (version is None or version == self._model_version):
                    model.save(str(self.path / 'gestures.npz'))
        except Exception as e:
            self.error = f'Model save failed: {type(e).__name__}: {e}'
            self._stop.set()
            if self.path.exists():
                self._json('metadata.json', self._context | dict(complete=False, frames=self.frames, error=self.error))
            raise

    def model_update_started(self):
        with self._artifacts:
            self._pending_models += 1
            self._model_version += 1
            return self._model_version

    def model_update_finished(self, error=None):
        with self._artifacts:
            if error:
                self.error = f'Model update failed: {type(error).__name__}: {error}'
                self._stop.set()
            self._pending_models -= 1
            if self._video_done and self.path.exists():
                self._write_metadata()

    def finish(self, reason='stopped'):
        self._context['stop_reason'] = reason
        self._stop.set()

    def wait(self):
        self._thread.join()

    def status(self):
        return dict(path=str(self.path), kind=self.kind, frames=self.frames,
                    saving=not self.finished.is_set() or self._pending_models > 0, error=self.error)

    def _write_metadata(self):
        with self._artifacts:
            self._json('metadata.json', self._context | dict(frames=self.frames,
                       complete=self.error is None and self.frames > 0 and self._pending_models == 0,
                       model_updates_pending=self._pending_models, error=self.error))

    def _json(self, name, value):
        with self._artifacts:
            tmp = self.path / (name + '.tmp')
            tmp.write_text(json.dumps(jsonable(value), indent=2, allow_nan=False))
            tmp.replace(self.path / name)

    def _run(self, calibration, model, mapping):
        writer = None
        try:
            import cv2
            self.path.mkdir(parents=True, exist_ok=False)
            self._json('mapping.json', mapping)
            if calibration is not None:
                self._json('calibration_before.json', calibration)
                self._json('calibration.json', calibration)
            if model is not None:
                with self._artifacts:
                    model.save(str(self.path / 'gestures_before.npz'))
                    model.save(str(self.path / 'gestures.npz'))
            self._json('metadata.json', self._context | dict(complete=False))
            self.ready.set()
            first_capture = None
            with (self.path / 'signals.jsonl').open('w') as stream:
                while not self._stop.is_set() or not self._queue.empty():
                    try:
                        item = self._queue.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if item[0] == 'calibration':
                        self._json('calibration.json', item[1])
                        continue
                    _, bgr, frame, signals, activations, scores, control, progress = item
                    h, w = bgr.shape[:2]
                    if writer is None:
                        writer = cv2.VideoWriter(str(self.path / 'video.avi'), cv2.VideoWriter_fourcc(*'MJPG'), self._fps, (w,h))
                        if not writer.isOpened():
                            raise RuntimeError('Could not open MJPG video encoder')
                        self._context.update(width=w, height=h)
                    elif (w,h) != (self._context['width'], self._context['height']):
                        raise RuntimeError('Camera resolution changed during capture')
                    first_capture = frame.t_capture_ns if first_capture is None else first_capture
                    row = dict(frame_index=self.frames, time_s=(frame.t_capture_ns-first_capture)/1e9,
                               frame=frame, signals=signals, activations=activations, scores=scores,
                               control=control, progress=progress)
                    writer.write(bgr)
                    stream.write(json.dumps(jsonable(row), allow_nan=False)+'\n')
                    self.frames += 1
        except Exception as e:
            self.error = f'{type(e).__name__}: {e}'
            self._stop.set()
        finally:
            self.ready.set()
            if writer is not None:
                writer.release()
            try:
                if self.path.exists():
                    with self._artifacts:
                        if not self.frames and self.error is None:
                            self.error = 'No video frames were recorded'
                        self._video_done = True
                        self._write_metadata()
            finally:
                self.finished.set()
