"""Offline selected-profile identity replay. Never emits gamepad inputs or enrolls from test footage."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helm.identity import IdentityGate, MAX_AGE_S, MODEL_SHA256, PREPROCESSING, SFace, identity_path, load_template, rotate_image
from helm.vision import FaceTracker


def overlap(a, b):
    """IoU for normalized [x0,y0,x1,y1] boxes; zero when no selected face exists."""
    if a is None or b is None:
        return 0.0
    a, b = np.asarray(a), np.asarray(b)
    intersection = np.maximum(np.minimum(a[2:], b[2:])-np.maximum(a[:2], b[:2]), 0).prod()
    union = np.maximum(a[2:]-a[:2], 0).prod()+np.maximum(b[2:]-b[:2], 0).prod()-intersection
    return float(intersection/union) if union else 0.0


def summarize(rows):
    result = dict(frames=len(rows), admitted_frames=sum(r['allowed'] for r in rows),
                  rejected_frames=sum(not r['allowed'] for r in rows),
                  identity_inference_ms={k: float(np.percentile([r['inference_ms'] for r in rows], p))
                                         for k, p in [('median', 50), ('p95', 95)]} if rows else {},
                  over_budget_frames=sum(r['over_budget'] for r in rows))
    labeled = [r for r in rows if r.get('target_present') is not None]
    if labeled:
        result['presence_labels'] = dict(frames=len(labeled),
            admitted_when_target_absent=sum(r['allowed'] and not r['target_present'] for r in labeled),
            rejected_when_target_present=sum(not r['allowed'] and r['target_present'] for r in labeled))
    boxes = [r for r in rows if r.get('target_box') is not None]
    if boxes:
        result['ownership_labels'] = dict(frames=len(boxes), admitted_frames=sum(r['allowed'] for r in boxes),
            admitted_low_target_box_overlap_frames=sum(r['allowed'] and overlap(r['selected_box'], r['target_box']) < .2 for r in boxes))
    result['limitations'] = ('Presence labels alone cannot establish which person was selected when several are visible. '
                            'Use independently annotated per-frame target boxes for ownership scoring. Rejected target-present '
                            'frames include confirmation, occlusion, low quality, and conservative rejection. Offline timing '
                            'is inference wall time, not measured camera-to-game latency. No accuracy claim without labels.')
    return result


def evaluate(video, player, output, profile_root=None, labels=None, signals=None, width=640, max_seconds=None, rotation=0, start_seconds=0):
    import cv2
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    root = identity_path(player, profile_root).parent.parent
    target_path = identity_path(player, root)
    target = load_template(target_path, player)
    others = [load_template(path, path.parent.name) for path in sorted(root.glob('*/identity.json'))
              if path.parent.name != player]
    gate, encoder, tracker = IdentityGate(target, others), SFace(), FaceTracker(num_faces=4)
    annotations = json.loads(Path(labels).read_text()) if labels else {}
    intervals = annotations.get('intervals', [])
    for item in intervals:
        if not isinstance(item.get('target_present'), bool) or item['end_s'] <= item['start_s']:
            raise ValueError('Intervals need start_s < end_s and boolean target_present')
    boxes = {int(item['frame_index']): item['target_box'] for item in annotations.get('frames', [])}
    times = None
    if signals:
        records = [json.loads(line) for line in Path(signals).read_text().splitlines()]
        if [r['frame_index'] for r in records] != list(range(len(records))):
            raise ValueError('Signal rows must map consecutively to video frame indices')
        times = np.array([r['time_s'] for r in records], np.float64)
        if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
            raise ValueError('Signal capture times must be finite and strictly increasing')
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f'Could not decode {video}')
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    rows = []
    try:
        with (output/'identity.jsonl').open('w') as stream:
            i, last_t = 0, -1.0
            while True:
                ok, image = cap.read()
                if not ok:
                    break
                if times is not None:
                    if i >= len(times):
                        raise ValueError('Video contains more frames than the paired signal stream')
                    t_s = float(times[i])
                else:
                    t_s = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
                    if t_s <= last_t:
                        t_s = i/fps
                if max_seconds is not None and t_s >= max_seconds:
                    break
                if t_s <= last_t:
                    raise ValueError('Video timing is nonmonotonic; provide capture signals')
                last_t = t_s
                if t_s < start_seconds:
                    i += 1
                    continue
                image = rotate_image(image, rotation)
                if width and image.shape[1] > width:
                    image = cv2.resize(image, (width, round(image.shape[0]*width/image.shape[1])))
                started = time.perf_counter_ns()
                faces = tracker.process_all(image, round(t_s*1e9), i)
                vectors, errors = [], []
                for face in faces:
                    try:
                        vectors.append(encoder.embed(image, face))
                        errors.append(None)
                    except ValueError as e:
                        vectors.append(None)
                        errors.append(str(e))
                selected, status = gate.choose(vectors, t_s)
                inference_ms = (time.perf_counter_ns()-started)/1e6
                selected_box = None
                if selected is not None:
                    p = faces[selected].landmarks
                    selected_box = [*p.min(axis=0).tolist(), *p.max(axis=0).tolist()]
                row = dict(frame_index=i, time_s=t_s, **status, inference_ms=inference_ms,
                           face_scores=[target.score(v) if v is not None else None for v in vectors],
                           alignment_errors=errors, selected_box=selected_box,
                           over_budget=inference_ms > MAX_AGE_S*1000)
                if row['over_budget']:
                    row.update(allowed=False, state='stale', reason='Inference exceeded live capture-age budget')
                    gate.reset()
                matching = [item for item in intervals if item['start_s'] <= t_s < item['end_s']]
                if len(matching) > 1:
                    raise ValueError('Ground-truth intervals overlap')
                row['target_present'] = matching[0]['target_present'] if matching else None
                row['target_box'] = boxes.get(i)
                stream.write(json.dumps(row, allow_nan=False)+'\n')
                rows.append(row)
                i += 1
        if times is not None and max_seconds is None and i != len(times):
            raise ValueError('Video/signal frame counts differ')
    finally:
        cap.release()
        tracker.close()
    summary = summarize(rows)
    summary.update(player=player, video=str(Path(video).resolve()), profile_sha256=hashlib.sha256(target_path.read_bytes()).hexdigest(),
                   model_sha256=MODEL_SHA256, preprocessing=PREPROCESSING, evaluation_width=width,
                   rotation_clockwise=rotation,
                   start_seconds=start_seconds,
                   labels=str(labels) if labels else None, signals=str(signals) if signals else None)
    (output/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--player', required=True)
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--profile-root', type=Path)
    p.add_argument('--labels', type=Path)
    p.add_argument('--signals', type=Path, help='Paired dev signals.jsonl; capture timing overrides nominal AVI fps')
    p.add_argument('--width', type=int, default=640)
    p.add_argument('--max-seconds', type=float)
    p.add_argument('--rotation', type=int, choices=(0, 90, 180, 270), default=0)
    p.add_argument('--start-seconds', type=float, default=0, help='Skip enrollment frames and begin a fresh admission gate')
    args = p.parse_args()
    print(json.dumps(evaluate(args.video, args.player, args.output, args.profile_root, args.labels,
                             args.signals, args.width, args.max_seconds, args.rotation, args.start_seconds), indent=2))


if __name__ == '__main__':
    main()
