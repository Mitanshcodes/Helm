# OWNER: P3
"""Replay all-negative normalized features through the learned engine and actual Mapper.

No camera, gamepad or training on the evaluated clip. Input NPZ: X (n,56), timestamp_s (n,), face (n,).
The profile loads/refits its saved enrollment data only. See eval/LEARNED_GESTURES.md.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helm.contracts import FEATURE_DIM, N_BLEND, Signals
from helm.gestures import GestureEngine, GestureModel
from helm.mapping import Mapper


def evaluate(model: GestureModel, x: np.ndarray, timestamps: np.ndarray, face: np.ndarray,
             mapping: dict | None = None) -> dict:
    """Every emitted event is false only when the caller's all-negative intent label is correct."""
    if (x.ndim != 2 or x.shape[1] != FEATURE_DIM or not len(x) or
            timestamps.shape != (len(x),) or face.shape != (len(x),) or
            not np.isfinite(x).all() or not np.isfinite(timestamps).all() or
            np.any(np.diff(timestamps) <= 0)):
        raise ValueError("Expected finite X (n,56), strictly increasing timestamp_s and matching face flags")
    if model._fitted is None or model._fitted.clf is None:
        raise ValueError("The saved model needs positive enrollment and none examples before evaluation")
    if mapping is None:
        mapping = {"gestures": {name: {"kind": "learned"} for name in model.names},
                   "buttons": [{"gesture": name, "target": "A", "mode": "hold"} for name in model.names]}
    engine, mapper = GestureEngine(None, mapping.get("gestures", {}), model), Mapper(mapping)
    events = []
    for i, (row, t_s, found) in enumerate(zip(x, timestamps, face)):
        t_ns = round(float(t_s) * 1e9)
        s = Signals(seq=i, t_capture_ns=t_ns, t_infer_ns=t_ns, face=bool(found),
                    axes=dict(zip(("yaw", "pitch", "roll"), row[N_BLEND:N_BLEND+3].tolist())),
                    expr=np.zeros(N_BLEND, np.float32), delta=row, breath=float(row[-1]))
        state = mapper.update(s, engine.update(s), [], {})
        for name in state.fired:
            events.append({"time_s": float(t_s - timestamps[0]), "gesture": name})
    dt = float(np.median(np.diff(timestamps))) if len(x) > 1 else 0.0
    duration = float(timestamps[-1] - timestamps[0] + dt)
    return {"frames": len(x), "face_frames": int(np.sum(face)), "duration_s": duration,
            "false_events": len(events), "false_per_minute": 60 * len(events) / duration if duration else None,
            "events": events, "assumption": "Entire input recording contains no intended commands"}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True, help="Player's gestures.npz, containing saved enrollment")
    p.add_argument("--features", required=True, help="Normalized feature NPZ: X, timestamp_s, face")
    p.add_argument("--mapping", help="Optional game mapping JSON; otherwise evaluate every learned gesture")
    p.add_argument("--output", help="Write result JSON; no file is written without this option")
    args = p.parse_args()
    model = GestureModel.load(args.model)
    mapping = json.loads(Path(args.mapping).read_text()) if args.mapping else None
    with np.load(args.features, allow_pickle=False) as data:
        result = evaluate(model, data["X"], data["timestamp_s"], data["face"], mapping)
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
