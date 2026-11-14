# OWNER: P1
"""The mock pipeline runs end to end and publishes the section 8 state message."""
import json
import time

from helm.main import Runtime, parse_args
from helm.profiles import default_mapping

STATE_KEYS = {"type", "fps", "latency_ms", "face", "paused", "breath_connected", "profile", "raw", "axes",
              "breath", "activations", "thresholds", "control", "fired", "progress", "gestures", "notices"}


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
    json.dumps(snap)                                             # must be plain JSON


def test_commands_do_not_break_the_loop():
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

    _run(rt, done)
    assert "calibration_done" in seen and "gesture_trained" in seen and "error" not in seen
    assert rt.snapshot()["profile"]["calibrated"] == "quick"
