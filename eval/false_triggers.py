# OWNER: P3
"""Replays recorded sessions through the fixed-threshold baseline and full Helm (docs/SPEC.md 12, eval 2).

Each participant was recorded with `python -m helm --player NAME --record eval/results/rec_NAME.npz` for three
minutes while NOT trying to play: one minute reading aloud, one chatting, one watching a gameplay video. Every
fire in that file is therefore a false trigger. Two conditions score the same frames:

  (a) baseline: no calibration, no hysteresis, no hold. For each face gesture the mapping uses, its raw
      blendshape score (combined the same way, min or max) crossing 0.5 upward is one fire.
  (b) Helm: the participant's calibration, mapping and learned model, through the real Normalizer,
      GestureEngine, FatigueTracker and Mapper, with the runtime's face-lost and pause rules. A fire is a
      button or trigger press, or a pause toggle.

Writes eval/results/false_triggers.csv (one row per participant, segment and condition) and prints a summary.

    python eval/false_triggers.py eval/results/rec_*.npz [--game SuperTuxKart] [--player NAME]
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helm import config, profiles  # noqa: E402
from helm.adapt import FatigueTracker  # noqa: E402
from helm.calibration import default_calibration  # noqa: E402
from helm.contracts import BLENDSHAPE_NAMES  # noqa: E402
from helm.filters import Normalizer  # noqa: E402
from helm.gestures import GestureEngine, GestureModel  # noqa: E402
from helm.mapping import Mapper  # noqa: E402
from helm.mock import ReplaySource  # noqa: E402

SEGMENTS = ("reading", "chatting", "video")    # one minute each, in this order
SEGMENT_S = 60.0
BASELINE_THRESHOLD = 0.5
RESULTS = ROOT / "eval" / "results"
_INDEX = {name: i for i, name in enumerate(BLENDSHAPE_NAMES)}


def player_from_path(path: Path) -> str:
    stem = path.stem
    return stem[4:] if stem.startswith("rec_") else stem


def segment_of(t_s: float) -> str:
    return SEGMENTS[min(int(t_s // SEGMENT_S), len(SEGMENTS) - 1)]


def baseline_gestures(mapping: dict) -> dict[str, tuple[list[int], str]]:
    """The face gestures the mapping drives (buttons, triggers, pause), as raw blendshape indices + combine."""
    used = {b.get("gesture") for b in mapping.get("buttons", [])}
    used |= {t.get("source") for t in mapping.get("triggers", [])}
    used.add((mapping.get("pause") or {}).get("gesture"))
    out = {}
    for name, g in (mapping.get("gestures") or {}).items():
        if name in used and isinstance(g, dict) and g.get("kind") == "blendshape":
            idx = [_INDEX[s] for s in g.get("sources", []) if s in _INDEX]
            if idx:
                out[name] = (idx, g.get("combine", "max"))
    return out


def score(path: Path, player: str, game: str) -> tuple[dict[str, Counter], dict[str, Counter], dict[str, float], list[str]]:
    """Returns (baseline fires, helm fires, minutes) per segment, plus warnings. Fires are Counters by gesture."""
    warnings: list[str] = []
    calib = profiles.load_calibration(player)
    if calib is None:
        warnings.append(f"{player}: no saved calibration, full Helm runs on defaults (calibrate with a named player)")
        calib = default_calibration(player)
    elif calib.mode != "full":
        warnings.append(f"{player}: calibration is {calib.mode!r}, not full")
    mapping = profiles.load_mapping(player, game)
    model_path = Path(profiles.gesture_model_path(player))
    model = GestureModel.load(str(model_path)) if model_path.exists() else None
    if model is None:
        warnings.append(f"{player}: no learned gestures or negatives on file")

    norm = Normalizer(calib)
    engine = GestureEngine(calib, mapping.get("gestures", {}), model)
    fatigue = FatigueTracker()
    mapper = Mapper(mapping)
    watch = baseline_gestures(mapping)
    armed = {name: True for name in watch}

    base = {s: Counter() for s in SEGMENTS}
    helm = {s: Counter() for s in SEGMENTS}
    source = ReplaySource(str(path), realtime=False)
    t0 = last_face = None
    idle, was_paused = True, False
    prev_ns = None
    seconds = {s: 0.0 for s in SEGMENTS}
    while (f := source.next()) is not None:
        t0 = f.t_capture_ns if t0 is None else t0
        seg = segment_of((f.t_capture_ns - t0) / 1e9)
        if prev_ns is not None:
            seconds[seg] += min(max((f.t_capture_ns - prev_ns) / 1e9, 0.0), 0.5)
        prev_ns = f.t_capture_ns

        # (a) baseline: raw scores, fixed threshold, every upward crossing fires
        for name, (idx, combine) in watch.items():
            values = [float(f.blend[i]) for i in idx]
            level = (min(values) if combine == "min" else max(values)) if f.face else 0.0
            if armed[name] and level >= BASELINE_THRESHOLD:
                base[seg][name] += 1
                armed[name] = False
            elif level < BASELINE_THRESHOLD:
                armed[name] = True

        # (b) full Helm, the same stages and safety rules as Runtime._step
        s = norm.update(f, breath=0.0, idle=idle)
        act = engine.update(s)
        scales = fatigue.update(act, f.t_capture_ns / 1e9)
        state = mapper.update(s, act, [], scales)
        idle = mapper.idle
        if f.face:
            last_face = f.t_infer_ns
        face_lost = last_face is None or f.t_infer_ns - last_face > config.FACE_LOST_MS * 1_000_000
        if state.paused != was_paused:
            helm[seg]["pause"] += 1
            was_paused = state.paused
        if face_lost or state.paused:
            continue
        for name in state.fired:
            helm[seg][name] += 1
    minutes = {s: seconds[s] / 60.0 for s in SEGMENTS}
    if t0 is None:
        warnings.append(f"{player}: {path.name} has no frames")
    return base, helm, minutes, warnings


def write_rows(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["participant", "segment", "minutes", "condition", "fires", "per_min",
                                           "by_gesture"])
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> list[dict]:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("recordings", nargs="+", type=Path, help="rec_<player>.npz files from `python -m helm --record`")
    p.add_argument("--game", default="SuperTuxKart")
    p.add_argument("--player", help="profile to score with (default: from the file name, rec_<player>.npz)")
    p.add_argument("--out", type=Path, default=RESULTS / "false_triggers.csv")
    args = p.parse_args(argv)

    rows: list[dict] = []
    for path in args.recordings:
        player = args.player or player_from_path(path)
        base, helm, minutes, warnings = score(path, player, args.game)
        for w in warnings:
            print("warning:", w, file=sys.stderr)
        for seg in SEGMENTS:
            if minutes[seg] <= 0:
                continue
            for condition, fires in (("baseline", base[seg]), ("helm", helm[seg])):
                total = sum(fires.values())
                rows.append({"participant": player, "segment": seg, "minutes": round(minutes[seg], 3),
                             "condition": condition, "fires": total, "per_min": round(total / minutes[seg], 2),
                             "by_gesture": ";".join(f"{k}:{v}" for k, v in sorted(fires.items()))})
    write_rows(rows, args.out)

    print(f"wrote {len(rows)} rows to {args.out}")
    for condition in ("baseline", "helm"):
        per_player = {}
        for r in rows:
            if r["condition"] == condition:
                f, m = per_player.get(r["participant"], (0, 0.0))
                per_player[r["participant"]] = (f + r["fires"], m + r["minutes"])
        rates = [f / m for f, m in per_player.values() if m > 0]
        if rates:
            print(f"  {condition:8s} median {statistics.median(rates):.2f} false triggers/min "
                  f"(n={len(rates)}: " + ", ".join(f"{k} {f / m:.2f}" for k, (f, m) in per_player.items() if m) + ")")
    return rows


if __name__ == "__main__":
    main()
