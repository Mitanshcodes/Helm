# OWNER: P3
"""eval/: throughput formula, the false-trigger replay (baseline vs full Helm), and the analysis report."""
import csv
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

from helm import profiles
from helm.calibration import default_calibration
from helm.contracts import BLENDSHAPE_NAMES, N_BLEND, FrameFeatures
from helm.mock import Recorder

ROOT = Path(__file__).resolve().parent.parent
B = {name: i for i, name in enumerate(BLENDSHAPE_NAMES)}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"eval_{name}", ROOT / "eval" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


false_triggers = _load("false_triggers")
analysis = _load("analysis")


def test_block_throughput_matches_the_formula():
    """Two moves of 300 px, selections 10 px either side of centre along the axis, 1 s each."""
    trials = [
        {"from_x": 0, "from_y": 0, "to_x": 300, "to_y": 0, "sel_x": 310, "sel_y": 5, "mt_ms": 1000},
        {"from_x": 300, "from_y": 0, "to_x": 0, "to_y": 0, "sel_x": 10, "sel_y": 0, "mt_ms": 1000},
    ]
    dx = [10.0, -10.0]                          # second move goes leftwards: +10 px in x is short of target
    we = 4.133 * np.std(dx, ddof=1)
    expected = math.log2(300.0 / we + 1) / 1.0  # mean Ae = 300
    assert analysis.block_throughput(trials) == pytest.approx(expected)


@pytest.fixture
def sam(tmp_path, monkeypatch):
    """A named participant with a full calibration and the default SuperTuxKart mapping, in a temp profiles/."""
    mapping = profiles.load_mapping("sam", "SuperTuxKart")          # read the repo defaults before redirecting
    monkeypatch.setattr(profiles, "_ROOT", tmp_path / "profiles")
    calib = default_calibration("sam", mode="full")
    neutral = [0.0] * N_BLEND
    for name in ("browInnerUp", "eyeBlinkLeft", "eyeBlinkRight"):
        neutral[B[name]] = 0.1
    calib.blend_neutral = neutral
    calib.blend_peak = {"browInnerUp": 0.9}
    calib.reliable = list(calib.reliable) + ["browInnerUp", "jawOpen", "mouthSmileLeft", "mouthSmileRight", "mouthPucker"]
    profiles.save_calibration(calib)
    profiles.save_mapping("sam", "SuperTuxKart", mapping)
    return tmp_path


def _record(path: Path, seconds: float = 180.0, hz: float = 30.0) -> None:
    """Talking-style twitches and blinks that cross a raw 0.5 but are not deliberate, plus one deliberate raise
    in each minute (a real 1.2 s brow raise both conditions should fire on)."""
    rec = Recorder(str(path))
    for i in range(int(seconds * hz)):
        t = i / hz
        blend = np.zeros(N_BLEND, np.float32)
        blend[B["browInnerUp"]] = blend[B["eyeBlinkLeft"]] = blend[B["eyeBlinkRight"]] = 0.1
        if t % 4.0 < 0.1:                       # twitch: 0.55 raw = only 56% of this player's range
            blend[B["browInnerUp"]] = 0.55
        if 2.0 <= t % 5.0 < 2.15:               # blink: crosses 0.5 for 150 ms
            blend[B["eyeBlinkLeft"]] = blend[B["eyeBlinkRight"]] = 0.9
        if 30.0 <= t % 60.0 < 31.2:             # one deliberate raise per minute
            blend[B["browInnerUp"]] = 0.95
        ns = int(t * 1e9)
        rec.write(FrameFeatures(seq=i, t_capture_ns=ns, t_infer_ns=ns + 9_000_000, face=True, blend=blend))
    rec.close()


def test_false_triggers_baseline_vs_helm(sam):
    results = sam / "results"
    rec = results / "rec_sam.npz"
    results.mkdir()
    _record(rec)
    rows = false_triggers.main([str(rec), "--out", str(results / "false_triggers.csv")])
    assert {r["segment"] for r in rows} == {"reading", "chatting", "video"}
    by = {(r["segment"], r["condition"]): r for r in rows}
    for seg in ("reading", "chatting", "video"):
        helm, base = by[(seg, "helm")], by[(seg, "baseline")]
        assert helm["by_gesture"] == "brow_raise:1"                 # only the deliberate raise
        assert base["fires"] >= 15 + 12                             # every twitch and every blink
        assert helm["minutes"] == pytest.approx(1.0, abs=0.01)
    with (results / "false_triggers.csv").open() as fh:
        assert len(list(csv.DictReader(fh))) == 6


def test_analysis_writes_charts_and_the_slide_numbers(sam, capsys):
    pytest.importorskip("matplotlib")
    res = sam / "results"
    res.mkdir()
    (res / "latency.csv").write_text("participant,condition,trial,frames,fps\n" + "".join(
        f"p{p},{c},{t},{f + t % 3},240\n" for p in (1, 2) for c, f in (("helm", 30), ("controller", 12)) for t in range(10)))
    (res / "false_triggers.csv").write_text(
        "participant,segment,minutes,condition,fires,per_min,by_gesture\n"
        "p1,reading,1,baseline,20,20,\np1,reading,1,helm,1,1,\np2,reading,1,baseline,10,10,\np2,reading,1,helm,0,0,\n")
    rng = np.random.default_rng(1)
    for cond, spread, mt in (("helm", 8, 900), ("fixed", 8, 1800)):
        with (res / f"target_p1_{cond}.csv").open("w") as fh:
            fh.write("participant,condition,block,trial,mt_ms,sel_x,sel_y,from_x,from_y,to_x,to_y,hit\n")
            for p in ("p1", "p2"):
                for block in (1, 2):
                    for k in range(9):
                        fh.write(f"{p},{cond},{block},{k + 1},{mt},{400 + rng.normal(0, spread):.1f},0,0,0,400,0,1\n")
    head = analysis.main(["--results", str(res)])
    out = capsys.readouterr().out
    assert head["latency"]["helm"]["median_ms"] == pytest.approx(31 * 1000 / 240)
    assert head["false_triggers"]["helm"]["median_per_min"] == pytest.approx(0.5)
    assert head["throughput"]["helm"]["median_bits_per_s"] > 1.8 * head["throughput"]["fixed"]["median_bits_per_s"]
    for chart in ("latency.png", "false_triggers.png", "throughput.png"):
        assert (res / chart).stat().st_size > 10_000
    assert json.loads((res / "headline.json").read_text())["latency"]["helm"]["participants"] == 2
    assert "falseTriggers: { helm: 0.5, baseline: 15, participants: 2 }" in out


def test_analysis_with_nothing_measured_says_so(tmp_path, capsys):
    analysis.main(["--results", str(tmp_path)])
    out = capsys.readouterr().out
    assert out.count("not measured") == 3 and "latency: { helm: null" in out
