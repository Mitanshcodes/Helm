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
              "breath", "activations", "thresholds", "control", "fired", "progress", "gestures", "notices", "mapping", "expressions", "catalog", "dev", "breath_marks", "ranges", "identity", "multiplayer"}


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
    mapping = default_mapping("SuperTuxKart")                    # brow, smile, nose scrunch, jaw: all "weak"
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
    assert set(rt._competitors) == {"brow_raise", "smile", "jaw_open"}
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


class _FakeBreath:
    """A connected sensor whose level the test sets; events are queued for one poll."""

    def __init__(self, *_):
        self.level, self.connected, self.events = 0.0, True, []
        self.scales = (config.BREATH_MAX_PUFF_MV, config.BREATH_MAX_SIP_MV)

    def start(self): pass
    def stop(self): pass

    def calibrate(self, puff, sip):
        self.scales = (puff, sip)

    def poll(self):
        events, self.events = self.events, []
        return events


def test_live_breath_presses_while_blowing_and_drives_analog_triggers(monkeypatch):
    import helm.main as main_mod
    from helm import coach
    from helm.contracts import FrameFeatures
    monkeypatch.setattr(main_mod, "SipPuff", _FakeBreath)
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server"]))
    mapping = default_mapping("SuperTuxKart")
    mapping["gestures"]["breath_puff"] = coach.breath_level_gesture()
    mapping["gestures"]["breath_sip"] = coach.breath_level_gesture()
    mapping["buttons"].append({"gesture": "breath_puff", "target": "RB", "mode": "hold"})
    mapping["triggers"] = [{"source": "breath_sip", "target": "lt", "lo": 0.15, "hi": 0.85}]
    assert rt.set_mapping(mapping) == []
    rt._handle_requests()
    names = {g["name"] for g in rt._gesture_catalog()["gestures"] if g["group"] == "breath"}
    assert {"breath_puff", "breath_sip", "hard_puff"} <= names

    def step(i, breath):
        rt._sip.level = breath
        ns = int(i * 1e9 / 30)
        rt._step(FrameFeatures(seq=i, t_capture_ns=ns, t_infer_ns=ns, face=True))
        return rt.snapshot()

    for i in range(10):
        snap = step(i, 0.02)                                    # rest noise: nothing
    assert "RB" not in snap["control"]["buttons"] and snap["control"]["lt"] == 0.0
    for i in range(10, 20):
        snap = step(i, 0.6)                                     # blowing: RB held down while it lasts
    assert "RB" in snap["control"]["buttons"] and snap["activations"]["breath_puff"] == pytest.approx(0.6)
    snap = step(20, 0.05)
    assert "RB" not in snap["control"]["buttons"]               # released as soon as the breath stops
    snap = step(21, -0.5)                                       # sipping half: brake in proportion
    assert snap["control"]["lt"] == pytest.approx((0.5 - 0.15) / 0.7) and snap["activations"]["breath_sip"] == 0.5
    assert snap["breath_marks"] == {"soft": config.BREATH_SOFT, "hard": config.BREATH_HARD}


def test_coach_never_holds_a_breath_event():
    from helm import coach
    from helm.calibration import default_calibration
    calib = default_calibration("sam", mode="full")              # only the eyes: breath is all there is
    m = coach.offline_mapping("SuperTuxKart", calib, [], True)
    kinds = {b["target"]: (m["gestures"][b["gesture"]]["kind"], b["mode"]) for b in m["buttons"]}
    assert all(not (kind == "breath" and mode == "hold") for kind, mode in kinds.values())
    assert coach.check(m, calib, [], True) == []


def test_hand_edited_breath_range_is_applied(monkeypatch, tmp_path):
    import helm.main as main_mod
    monkeypatch.setattr(main_mod, "SipPuff", _FakeBreath)
    monkeypatch.setattr(profiles, "_ROOT", tmp_path)
    profiles.save_breath("sam", 900.0, 1500.0)
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server", "--player", "sam"]))
    assert rt._sip.scales == (900.0, 1500.0)                     # loaded at startup
    seen: dict = {}
    rt._check_profile_files(seen)
    path = tmp_path / "sam" / "breath.json"
    path.write_text(json.dumps({"max_puff_mv": 600.0, "max_sip_mv": 1200.0}))
    seen[path] -= 1
    rt._check_profile_files(seen)
    assert rt._sip.scales == (600.0, 1200.0)
    assert [e["data"]["what"] for e in rt.pop_events()] == ["breath"]


def test_steering_sensitivity_comes_from_the_mapping_and_is_published():
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server"]))
    base = rt.snapshot()["ranges"]["yaw"]
    mapping = default_mapping("SuperTuxKart")
    mapping["axes"][0]["gain"] = 2.0
    assert rt.set_mapping(mapping) == []
    rt._handle_requests()
    from helm.contracts import ControlState
    rt._snapshot = rt._build_snapshot(None, None, {}, ControlState(), None)
    assert rt.snapshot()["ranges"]["yaw"] == [pytest.approx(base[0] / 2, abs=0.1), pytest.approx(base[1] / 2, abs=0.1)]


def test_calibration_nods_train_the_learned_move_and_land_on_x(monkeypatch, tmp_path):
    from helm.calibration import default_calibration
    from helm.contracts import FrameFeatures
    monkeypatch.setattr(profiles, "_ROOT", tmp_path)
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server", "--player", "sam"]))
    calib = default_calibration("sam", mode="full")
    rng = np.random.default_rng(0)

    def frames(n, pitch=0.0, yaw=0.0):
        return [FrameFeatures(seq=i, t_capture_ns=i * 33_000_000, t_infer_ns=i * 33_000_000, face=True,
                              pitch=pitch + rng.normal(0, 0.3), yaw=yaw + rng.normal(0, 0.3)) for i in range(n)]

    takes = [frames(12, pitch=15.0) for _ in range(3)]
    not_nod = [frames(30), frames(30, yaw=-15.0), frames(30, yaw=15.0)]
    rt._prepare_nod(calib, {}, takes, not_nod)                     # normally on a worker
    rt._handle_requests()
    assert "nod_up" in rt._learned()
    assert {"gesture": "nod_up", "target": "X", "mode": "tap"} in rt._mapping["buttons"]
    assert rt._mapping["gestures"]["nod_up"]["kind"] == "learned"
    deadline = time.monotonic() + 3.0                            # fit and save happen on a worker
    while not (tmp_path / "sam" / "SuperTuxKart.json").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert json.loads((tmp_path / "sam" / "SuperTuxKart.json").read_text())["gestures"]["nod_up"]["kind"] == "learned"


def test_face_id_learns_during_head_movement_steps_and_protects_the_profile(monkeypatch, tmp_path):
    import helm.identity as identity
    import helm.main as main_mod
    from types import SimpleNamespace
    monkeypatch.setattr(profiles, "_ROOT", tmp_path / "profiles")
    weights = tmp_path / "sface.onnx"
    weights.write_bytes(b"x")
    monkeypatch.setattr(identity, "MODEL_PATH", weights)
    monkeypatch.setattr(config, "FACE_ID_INTERVAL_S", 0.0)
    me = np.random.default_rng(1).normal(size=128)
    embedded: list[int] = []

    class Camera:
        seq = 0
        def wait_latest(self, last, timeout=0.2):
            time.sleep(0.001)
            Camera.seq += 1
            return np.zeros((480, 640, 3), np.uint8), Camera.seq * 1_000_000, Camera.seq

    class Encoder:
        def embed(self, image, face):
            embedded.append(Camera.seq)
            return identity.unit(me + np.random.default_rng(Camera.seq).normal(scale=0.05, size=128))

    class Tracker:
        def __init__(self, num_faces=1): pass
        def process_all(self, image, t, seq): return [SimpleNamespace()]
        def close(self): pass

    monkeypatch.setattr(identity, "SFace", Encoder)
    monkeypatch.setattr(main_mod, "FaceTracker", Tracker)
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server", "--player", "sam"]))
    rt._camera = Camera()                                      # a camera, so Face ID can run
    rt._do_calibrate("full")
    assert rt._calibrator is not None and rt._face_id is not None   # no step of its own: calibration starts now
    time.sleep(0.1)
    assert embedded == []                                      # not sampling until a head-movement step
    rt._face_id.active = True                                  # what the pipeline sets during neutral / range steps
    deadline = time.monotonic() + 3.0
    while rt._face_id.samples < config.FACE_ID_SAMPLES and time.monotonic() < deadline:
        time.sleep(0.01)
    rt._face_id.active = False                                 # expression steps: no samples
    count = len(embedded)
    time.sleep(0.1)
    assert count == config.FACE_ID_SAMPLES and len(embedded) == count
    rt._face_id.finish()                                       # the calibration ended
    rt._calibrator = None
    while not rt._face_id.done and time.monotonic() < deadline:
        time.sleep(0.01)
    rt._face_id_ended()
    assert [e["data"] for e in rt.pop_events() if e["name"] == "face_id_done"] == [
        {"saved": True, "reason": "", "samples": config.FACE_ID_SAMPLES}]
    assert identity.identity_required("sam") and rt._identity_required and rt._face_id is None


def test_shared_profiles_and_no_camera_skip_face_id():
    rt = Runtime(parse_args(["--mock", "--output", "null", "--no-server"]))   # guest, mock: no camera
    rt._do_calibrate("full")
    assert rt._face_id is None and rt._calibrator is not None
