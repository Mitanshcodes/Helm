"""Explicit per-profile face enrollment and conservative single-player identity admission.

SFace inference is independent of gesture features. Runtime uses IdentityWorker; offline
studies may continue to use the default, ungated FaceTracker.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import urllib.request

import numpy as np

from helm.contracts import FrameFeatures

MODEL_SHA256 = '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79'
MODEL_URL = ('https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/'
             'face_recognition_sface/face_recognition_sface_2021dec.onnx')
MODEL_PATH = Path(__file__).resolve().parents[1] / 'artifacts/identity-models/face_recognition_sface_2021dec.onnx'
PREPROCESSING = 'mediapipe_eye_centers_nose1_mouth61_291_opencv_sface_align112_v1'
THRESHOLD = .55                  # conservative initial policy; must be validated on fresh recordings
MARGIN = .08
CONFIRM_S = .20
MAX_AGE_S = .25
MAX_GAP_S = .30
MIN_FACE_PX = 80


def unit(vector):
    x = np.asarray(vector, np.float32)
    if x.shape != (128,) or not np.isfinite(x).all() or np.linalg.norm(x) < 1e-6:
        raise ValueError('Expected a finite, nonzero 128-dimensional SFace embedding')
    return x / np.linalg.norm(x)


def identity_path(player, root=None):
    from helm import profiles
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', player) or player.startswith('_'):
        raise ValueError('Invalid profile name')
    return Path(root if root is not None else profiles._ROOT) / player / 'identity.json'


def identity_required(player, root=None):
    path = identity_path(player, root)
    return path.exists() or path.is_symlink() or path.with_name('identity_required.json').exists()


@dataclass(frozen=True)
class Template:
    player: str
    vectors: np.ndarray
    threshold: float = THRESHOLD
    margin: float = MARGIN

    def score(self, vector):
        return float(np.max(self.vectors @ unit(vector)))


def load_template(path, player):
    """Missing/corrupt templates raise: callers must not downgrade enrolled profiles to unprotected."""
    d = json.loads(Path(path).read_text())
    if (d.get('schema') != 1 or d.get('player') != player or d.get('model_sha256') != MODEL_SHA256
            or d.get('preprocessing') != PREPROCESSING):
        raise ValueError('Identity template has an incompatible profile, model or preprocessing version')
    v = np.asarray(d['embeddings'], np.float32)
    if v.ndim != 2 or v.shape[1] != 128 or not 5 <= len(v) <= 64:
        raise ValueError('Identity enrollment needs 5–64 reference embeddings')
    threshold, margin = float(d['threshold']), float(d['margin'])
    if not .4 <= threshold <= .95 or not .02 <= margin <= .4:
        raise ValueError('Invalid identity thresholds')
    return Template(player, np.stack([unit(row) for row in v]), threshold, margin)


def save_template(player, vectors, root=None, provenance=None):
    from helm import profiles
    if player in profiles.SHARED_PLAYERS:
        raise ValueError('Use a named personal profile, not guest/judge, for face enrollment')
    v = np.stack([unit(row) for row in vectors])
    if not 5 <= len(v) <= 64:
        raise ValueError('Identity enrollment needs 5–64 reference embeddings')
    # Reject an obviously mixed/unstable enrollment, without treating consistency as proof of identity.
    center = v.mean(axis=0)
    if np.linalg.norm(center) < 1e-6 or np.min(v @ center / np.linalg.norm(center)) < .65:
        raise ValueError('Enrollment is inconsistent; record one person with a clear, well-lit face')
    path = identity_path(player, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Retain the protection requirement even if the biometric file is lost or damaged later.
    marker = path.with_name('identity_required.json')
    marker_tmp = marker.with_suffix('.json.tmp')
    marker_tmp.write_text(json.dumps(dict(schema=1, player=player, required=True))+'\n')
    marker_tmp.replace(marker)
    payload = dict(schema=1, player=player, model_sha256=MODEL_SHA256, preprocessing=PREPROCESSING,
                   threshold=THRESHOLD, margin=MARGIN, embeddings=v.tolist(),
                   created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), provenance=provenance or {})
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, indent=2, allow_nan=False)+'\n')
    tmp.chmod(0o600)
    tmp.replace(path)
    return path


def download_model(path=MODEL_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.onnx.download')
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=30) as source, tmp.open('wb') as out:
            while chunk := source.read(1024 * 1024):
                out.write(chunk)
        if hashlib.sha256(tmp.read_bytes()).hexdigest() != MODEL_SHA256:
            raise ValueError('SFace model SHA-256 mismatch')
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def rotate_image(image, clockwise):
    import cv2
    if not clockwise:
        return image
    return cv2.rotate(image, {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180,
                              270: cv2.ROTATE_90_COUNTERCLOCKWISE}[clockwise])


class SFace:
    def __init__(self, path=MODEL_PATH):
        import cv2
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError('Identity weights missing. Run: python -m helm.identity download')
        if hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256:
            raise ValueError('Identity weights do not match the pinned OpenCV SFace SHA-256')
        cv2.setNumThreads(1)                       # avoid nested OpenCV thread oversubscription in the camera worker
        self.recognizer = cv2.FaceRecognizerSF.create(str(path), '')

    def embed(self, bgr, frame):
        """Five-point alignment adapts MediaPipe observations; pixels are never mirrored."""
        p = np.asarray(frame.landmarks, np.float32)
        if p.shape != (478, 2) or not np.isfinite(p).all():
            raise ValueError('Identity requires 478 finite MediaPipe preview landmarks')
        h, w = bgr.shape[:2]
        p = p * [w, h]
        lo, hi = p.min(axis=0), p.max(axis=0)
        if min(hi-lo) < MIN_FACE_PX:
            raise ValueError('Face is too small for identity recognition')
        eyes = sorted([(p[33]+p[133])/2, (p[362]+p[263])/2], key=lambda a: a[0])
        mouth = sorted([p[61], p[291]], key=lambda a: a[0])
        if np.linalg.norm(eyes[1]-eyes[0]) < 20:
            raise ValueError('Face alignment is too small or turned away')
        row = np.concatenate([lo, hi-lo, *eyes, p[1], *mouth, [1]]).astype(np.float32)[None, :]
        aligned = self.recognizer.alignCrop(bgr, row)
        return unit(self.recognizer.feature(aligned).reshape(-1))


class IdentityGate:
    """Per-frame open-set selection; no index/position identity assumptions or cached acceptance."""
    def __init__(self, target, others=()):
        self.target, self.others = target, tuple(others)
        self.reset()

    def reset(self):
        self.since = self.last = None
        self.frames = 0

    def choose(self, embeddings, t_s):
        if self.last is not None and (t_s <= self.last or t_s-self.last > MAX_GAP_S):
            self.reset()
        self.last = t_s
        scores = [self.target.score(e) if e is not None else -1.0 for e in embeddings]
        status = dict(protected=True, allowed=False, state='rejected', reason='Selected person not recognized',
                      player=self.target.player, face_count=len(scores), selected_index=None,
                      face_landmarker_num_faces=4,
                      score=max(scores, default=None), threshold=self.target.threshold)
        if not scores or max(scores) < self.target.threshold:
            self.since, self.frames = None, 0
            return None, status
        ranking = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        i = ranking[0]
        alternative = max((p.score(embeddings[i]) for p in self.others), default=-1.0)
        second_face = scores[ranking[1]] if len(ranking) > 1 else -1.0
        if scores[i]-max(alternative, second_face) < self.target.margin:
            self.since, self.frames = None, 0
            status.update(state='ambiguous', reason='Identity match is ambiguous')
            return None, status
        self.since = t_s if self.since is None else self.since
        self.frames += 1
        if t_s-self.since < CONFIRM_S-1e-9 or self.frames < 3:
            status.update(state='confirming', reason='Confirming selected person')
            return None, status
        status.update(allowed=True, state='recognized', reason='Selected person recognized', selected_index=i)
        return i, status


@dataclass
class IdentityResult:
    frame: FrameFeatures
    image: np.ndarray
    status: dict
    generation: int


def unprotected_status(player):
    return dict(protected=False, allowed=True, state='unprotected', player=player,
                face_landmarker_num_faces=1,
                reason='No face enrollment: this profile accepts any face')


class IdentityWorker:
    """Latest-result worker; camera pixels, identity and gesture observations stay frame-aligned."""
    def __init__(self, camera, model_path=MODEL_PATH):
        self.camera, self.model_path = camera, model_path
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._generation = 0
        self._player = None
        self._latest = None
        self._status = {}
        self._thread = None

    def configure(self, player):
        with self._cond:
            self._generation += 1
            self._player = player
            self._latest = None
            self._status = dict(protected=player is not None, allowed=False, player=player,
                                face_landmarker_num_faces=4 if player is not None else 1,
                                state='loading', reason='Loading face enrollment')
            self._cond.notify_all()
            return self._generation

    def start(self):
        self._thread = threading.Thread(target=self._run, name='face-identity', daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread:
            self._thread.join(timeout=2)

    def wait_latest(self, seq, timeout=.05):
        with self._cond:
            if self._latest is not None:
                remaining = MAX_AGE_S-(time.perf_counter_ns()-self._latest.frame.t_capture_ns)/1e9
                timeout = min(timeout, max(0, remaining))
            self._cond.wait_for(lambda: self._stop.is_set() or
                                (self._latest is not None and self._latest.frame.seq > seq), timeout)
            result = self._latest
            status = dict(self._status)
            if result is not None and result.frame.seq > seq:
                age = (time.perf_counter_ns()-result.frame.t_capture_ns)/1e9
                if age <= MAX_AGE_S:
                    return result, status
                status.update(allowed=False, state='stale', reason='Identity inference is too old; controls neutral')
            elif result is not None and status.get('allowed'):
                age = (time.perf_counter_ns()-result.frame.t_capture_ns)/1e9
                if age > MAX_AGE_S:
                    status.update(allowed=False, state='stale', reason='Identity inference is too old; controls neutral')
                else:
                    status['age_ms'] = age * 1000
            elif status.get('state') not in ('error', 'loading'):
                status.update(allowed=False, state='waiting', reason='Waiting for a fresh identity observation')
            return None, status

    def _publish(self, generation, result=None, status=None):
        with self._cond:
            if generation != self._generation:
                return
            self._latest = result
            self._status = status or result.status
            self._cond.notify_all()

    def _run(self):
        from helm import profiles
        from helm.vision import FaceTracker
        tracker = encoder = gate = None
        generation = -1
        last_seq = -1
        try:
            while not self._stop.is_set():
                with self._cond:
                    self._cond.wait_for(lambda: self._stop.is_set() or self._player is not None, .1)
                    player, current = self._player, self._generation
                if self._stop.is_set():
                    break
                if player is None:
                    continue
                if current != generation:
                    generation = current
                    try:
                        target = load_template(identity_path(player), player)
                        others = []
                        for path in sorted(profiles._ROOT.glob('*/identity.json')):
                            if path.parent.name != player:
                                # An unusable competing profile must not be ignored silently.
                                others.append(load_template(path, path.parent.name))
                        gate = IdentityGate(target, others)
                        encoder = encoder or SFace(self.model_path)
                        tracker = tracker or FaceTracker(num_faces=4)
                    except Exception as e:
                        self._publish(generation, status=dict(protected=True, allowed=False, state='error',
                                      face_landmarker_num_faces=4,
                                      player=player, reason=f'{type(e).__name__}: {e}'))
                        gate = None
                if gate is None:
                    self._stop.wait(.1)
                    continue
                got = self.camera.wait_latest(last_seq, timeout=.1)
                if got is None:
                    continue
                image, capture_ns, last_seq = got
                started = time.perf_counter_ns()
                try:
                    faces = tracker.process_all(image, capture_ns, last_seq)
                    embeddings = []
                    for face in faces:
                        try:
                            embeddings.append(encoder.embed(image, face))
                        except ValueError:
                            embeddings.append(None)
                    i, status = gate.choose(embeddings, capture_ns/1e9)
                    frame = faces[i] if i is not None else FrameFeatures(last_seq, capture_ns, time.perf_counter_ns(), False)
                    frame.t_infer_ns = time.perf_counter_ns()
                    status['inference_ms'] = (time.perf_counter_ns()-started)/1e6
                    status['frame_seq'] = last_seq
                    self._publish(generation, IdentityResult(frame, image, status, generation))
                except Exception as e:
                    gate.reset()
                    self._publish(generation, status=dict(protected=True, allowed=False, state='error', player=player,
                                  face_landmarker_num_faces=4,
                                  reason=f'{type(e).__name__}: {e}'))
        finally:
            if tracker:
                tracker.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('download', help='Fetch and hash-verify official SFace weights')
    enroll = sub.add_parser('enroll', help='Explicitly enroll one person from a video or camera')
    enroll.add_argument('--player', required=True)
    source = enroll.add_mutually_exclusive_group(required=True)
    source.add_argument('--video', type=Path)
    source.add_argument('--camera', type=int)
    enroll.add_argument('--seconds', type=float, default=8)
    enroll.add_argument('--start-seconds', type=float, default=0)
    enroll.add_argument('--rotation', type=int, choices=(0, 90, 180, 270), default=0,
                        help='Explicit clockwise correction for sideways prerecorded video')
    enroll.add_argument('--crop', type=float, nargs=4, metavar=('X0', 'Y0', 'X1', 'Y1'),
                        help='Explicit normalized single-person enrollment crop after rotation')
    enroll.add_argument('--output-root', type=Path, help='Optional separate profile root for experiments')
    args = parser.parse_args()
    if args.command == 'download':
        print(download_model())
        return
    import cv2
    from helm.vision import FaceTracker
    if not 2 <= args.seconds <= 60 or args.start_seconds < 0:
        parser.error('--seconds must be between 2 and 60')
    if args.crop and not (0 <= args.crop[0] < args.crop[2] <= 1 and 0 <= args.crop[1] < args.crop[3] <= 1):
        parser.error('--crop needs 0 <= X0 < X1 <= 1 and 0 <= Y0 < Y1 <= 1')
    encoder, tracker = SFace(), FaceTracker(num_faces=4)
    cap = cv2.VideoCapture(str(args.video) if args.video else args.camera)
    if not cap.isOpened():
        raise RuntimeError('Could not open enrollment source')
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    samples, examined, next_sample = [], 0, 0.0
    started = time.monotonic()
    try:
        while len(samples) < 24:
            ok, image = cap.read()
            if not ok:
                break
            t_s = examined/fps if args.video else time.monotonic()-started
            examined += 1
            if t_s < args.start_seconds:
                continue
            if t_s >= args.start_seconds+args.seconds:
                break
            if t_s < next_sample:
                continue
            next_sample = t_s + .25
            image = rotate_image(image, args.rotation)
            if args.crop:
                h, w = image.shape[:2]
                x0, y0, x1, y1 = args.crop
                image = image[round(y0*h):round(y1*h), round(x0*w):round(x1*w)]
            faces = tracker.process_all(image, round(t_s*1e9), examined)
            if len(faces) != 1:
                raise ValueError('Enrollment requires exactly one visible person throughout sampled frames')
            samples.append(encoder.embed(image, faces[0]))
        if len(samples) < 8:
            raise ValueError('Too few clear enrollment frames; record at least 3 seconds with one visible face')
        path = save_template(args.player, samples, args.output_root,
                             dict(source='video' if args.video else 'camera', frames=len(samples),
                                  duration_s=args.seconds, start_s=args.start_seconds, rotation=args.rotation,
                                  crop=args.crop, policy='explicit_enrollment'))
        print(f'Saved {len(samples)} face references to {path}. Reload this profile in Helm.')
    finally:
        cap.release()
        tracker.close()


if __name__ == '__main__':
    main()
