# OWNER: P1
"""The mock pipeline runs end to end and publishes the section 8 state message."""
import json
import time

import numpy as np
import pytest

from helm import config, profiles
from helm.gestures import GestureModel
from helm.main import Runtime, parse_args
from helm.profiles import default_mapping

STATE_KEYS = {"type", "fps", "latency_ms", "face", "paused", "breath_connected", "profile", "raw", "axes",
              "breath", "activations", "thresholds", "control", "fired", "progress", "gestures", "notices", "mapping", "expressions", "catalog"}


def _run(runtime: Runtime, until, timeout: float = 3.0) -> None:
    runtime.start()
    try:
        deadline = time.monotonic() + timeout
        while not until() and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        runtime.stop()


def test_mock_runtime_publishes_state():
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server"]))
    assert set(rt.snapshot()) == STATE_KEYS                      # valid before the first frame
    _run(rt, lambda: rt.snapshot()["fps"] > 0)
    snap = rt.snapshot()
    assert set(snap) == STATE_KEYS and snap["type"] == "state"
    assert snap["fps"] > 0 and snap["face"] is True
    assert snap["profile"] == {"player": "guest", "game": "SuperTuxKart", "calibrated": None}
    assert snap["mapping"]["game"] == "SuperTuxKart"             # the active mapping, before any is applied
    json.dumps(snap)                                             # must be plain JSON
    assert rt.preview() is None                                  # --no-server: no cartoon frame is drawn


def test_mock_preview_frame_for_the_dashboard():
    pytest.importorskip("cv2")
    rt = Runtime(parse_args(["--mock", "--output", "null"]))     # server on (not started here)
    _run(rt, lambda: rt.preview() is not None)
    bgr, landmarks = rt.preview()
    assert bgr.shape == (*reversed(config.PREVIEW_SIZE), 3) and bgr.dtype == np.uint8 and landmarks is None


def test_fired_is_held_long_enough_for_the_dashboard():
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server"]))
    ms = 1_000_000
    assert rt._hold_fired(("brow_raise",), 0) == ["brow_raise"]
    assert rt._hold_fired((), 100 * ms) == ["brow_raise"]                       # still there 100 ms later
    assert set(rt._hold_fired(("soft_puff",), 140 * ms)) == {"brow_raise", "soft_puff"}
    assert rt._hold_fired((), (config.FIRED_HOLD_MS + 1) * ms) == ["soft_puff"]   # brow_raise expired
    assert rt._hold_fired((), 400 * ms) == []


def test_commands_do_not_break_the_loop(monkeypatch, tmp_path):
    monkeypatch.setattr(profiles, "_ROOT", tmp_path)              # saves land in a temp dir, not profiles/
    for name in ("TAKE_READY_S", "TAKE_HOLD_S", "TAKE_RELAX_S", "TAKE_GO_TIMEOUT_S"):   # 5 takes in ~2 s
        monkeypatch.setattr(config, name, 0.1)
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server"]))
    rt.set_paused(False)
    assert rt.set_mapping(default_mapping("SuperTuxKart")) == []
    rt.start_calibration("quick")
    seen: list[str] = []

    def done() -> bool:
        new = [e["name"] for e in rt.pop_events()]
        seen.extend(new)
        if "calibration_done" in new:                            # a new command replaces the active one,
            rt.record_gesture("left_smirk")                      # so record only after calibration ends
        return "calibration_done" in seen and "gesture_trained" in seen

    _run(rt, done, timeout=8.0)                                  # quick calibration takes 2 s of face time
    assert "calibration_done" in seen and "gesture_trained" in seen and "error" not in seen
    assert rt.snapshot()["profile"]["calibrated"] == "quick"
    assert rt.snapshot()["gestures"]["learned"] == ["left_smirk"]
    deadline = time.monotonic() + 2.0                            # the model is saved on a worker thread
    while not (tmp_path / "guest" / "gestures.npz").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert GestureModel.load(str(tmp_path / "guest" / "gestures.npz")).names == ["left_smirk"]


def test_hand_made_mapping_may_use_a_weak_expression():
    from helm.calibration import default_calibration
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server"]))
    rt._calib = default_calibration("guest", mode="full")       # full calibration: only the eyes passed
    mapping = default_mapping("SuperTuxKart")                    # brow, smile, pucker, jaw: all "weak"
    assert profiles.validate_mapping(mapping, rt._calib, [], False)   # the strict check would refuse it
    assert rt.set_mapping(mapping) == []                         # but the player chose it by hand


def _ui(tmp_path):
    ui = tmp_path / "ui"
    (ui / "src").mkdir(parents=True)
    (ui / "src" / "App.tsx").write_text("x")
    (ui / "package-lock.json").write_text("{}")
    return ui


def test_dashboard_is_rebuilt_when_its_source_changed(tmp_path, monkeypatch):
    import os
    import subprocess
    from helm import main as helm_main
    ui = _ui(tmp_path)
    ran = []

    def fake_run(cmd, cwd, **kwargs):
        ran.append(cmd[1:])
        if cmd[1:3] == ["run", "build"]:
            (ui / "dist").mkdir(exist_ok=True)
            (ui / "dist" / "index.html").write_text("built")
        if cmd[1] == "install":
            (ui / "node_modules").mkdir(exist_ok=True)
            (ui / "node_modules" / ".package-lock.json").write_text("{}")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(helm_main.shutil, "which", lambda name: "/usr/bin/npm")
    monkeypatch.setattr(helm_main.subprocess, "run", fake_run)
    assert helm_main.ensure_dashboard(ui) and ran == [["install", "--no-audit", "--no-fund"], ["run", "build"]]
    ran.clear()
    assert helm_main.ensure_dashboard(ui) and ran == []                     # up to date: nothing runs
    later = (ui / "dist" / "index.html").stat().st_mtime + 10
    os.utime(ui / "src" / "App.tsx", (later, later))                        # a pull changed the source
    assert helm_main.ensure_dashboard(ui) and ran == [["run", "build"]]     # dependencies unchanged: build only


def test_dashboard_without_npm_warns_and_carries_on(tmp_path, monkeypatch):
    from helm import main as helm_main
    monkeypatch.setattr(helm_main.shutil, "which", lambda name: None)
    assert helm_main.ensure_dashboard(_ui(tmp_path)) is False
