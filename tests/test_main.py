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
              "breath", "activations", "thresholds", "control", "fired", "progress", "gestures", "notices", "mapping", "expressions", "catalog", "dev"}


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


def test_crosstalk_is_held_back_but_two_real_moves_pass():
    from helm.main import hold_back_crosstalk
    comp = {"smile": (0.6, frozenset({"mouthSmileLeft", "mouthSmileRight"})), "jaw_open": (0.7, frozenset({"jawOpen"})),
            "brow_raise": (0.6, frozenset({"browInnerUp"})), "big_brow": (0.9, frozenset({"browInnerUp"}))}
    act = {"smile": 1.0, "jaw_open": 0.75, "brow_raise": 0.0, "big_brow": 0.0, "eyes_closed": 0.9}
    out = hold_back_crosstalk(act, comp)
    assert out["smile"] == 1.0 and out["jaw_open"] == 0.0           # jaw is past `on`, but only as a side effect
    assert out["eyes_closed"] == 0.9 and act["jaw_open"] == 0.75     # not a competitor; the input is not changed
    both = hold_back_crosstalk({"smile": 0.95, "brow_raise": 0.9}, comp)
    assert both == {"smile": 0.95, "brow_raise": 0.9}                # made on purpose together
    same = hold_back_crosstalk({"brow_raise": 1.0, "big_brow": 0.6}, comp)
    assert same["big_brow"] == 0.6                                   # same blendshape: layered on purpose
    quiet = {"smile": 0.1, "jaw_open": 0.0}
    assert hold_back_crosstalk(quiet, comp) is quiet                 # nothing to hold back: no copy


def test_runtime_competitors_are_the_mapped_gestures_except_pause():
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server"]))
    assert set(rt._competitors) == {"brow_raise", "smile", "pucker", "jaw_open"}
    assert rt._competitors["jaw_open"] == (0.7, frozenset({"jawOpen"}))


def test_hand_edits_to_profile_files_are_applied(monkeypatch, tmp_path):
    from dataclasses import asdict, replace
    from helm.calibration import default_calibration
    mapping = default_mapping("SuperTuxKart")                    # read the repo defaults before redirecting
    monkeypatch.setattr(profiles, "_ROOT", tmp_path)
    calib = default_calibration("sam", mode="full")
    profiles.save_calibration(calib)
    profiles.save_mapping("sam", "SuperTuxKart", mapping)
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server", "--player", "sam"]))
    seen: dict = {}
    rt._check_profile_files(seen)                                # first look: baseline only
    assert rt._requests == [] and rt.pop_events() == []

    def touch(path, text):
        path.write_text(text)
        seen[path] -= 1                                          # a change even if the clock did not tick

    folder = tmp_path / "sam"
    edited = json.loads(json.dumps(mapping))
    edited["gestures"]["brow_raise"]["on"] = 0.8
    touch(folder / "SuperTuxKart.json", json.dumps(edited))
    calib_edit = replace(calib, blend_peak={"browInnerUp": 0.9})
    touch(folder / "calibration.json", json.dumps(asdict(calib_edit)))
    rt._check_profile_files(seen)
    assert sorted(k for k, _ in rt._requests) == ["set_calibration", "set_mapping"]
    assert [e["name"] for e in rt.pop_events()] == ["profile_reloaded", "profile_reloaded"]
    rt._handle_requests()
    assert rt._mapping["gestures"]["brow_raise"]["on"] == 0.8 and rt._calib.blend_peak == {"browInnerUp": 0.9}

    touch(folder / "SuperTuxKart.json", json.dumps(edited))       # Helm's own save: same content, nothing to do
    touch(folder / "calibration.json", "{ half typed")
    rt._check_profile_files(seen)
    events = rt.pop_events()
    assert rt._requests == [] and [e["name"] for e in events] == ["error"]
    assert "calibration.json was not applied" in events[0]["data"]["message"]
    edited["gestures"]["brow_raise"]["off"] = 0.95                 # off above on: refused, current mapping kept
    touch(folder / "SuperTuxKart.json", json.dumps(edited))
    rt._check_profile_files(seen)
    assert rt._requests == [] and "thresholds must satisfy" in rt.pop_events()[0]["data"]["message"]
