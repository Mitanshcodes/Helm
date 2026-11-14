# OWNER: P1
"""Bootstrap checks for calibration.py. TODO(P1): step timing, face-lost pause, range floor, reliable flag."""
from helm.calibration import Calibrator, default_calibration
from helm.contracts import AXES, N_BLEND, Calibration, FrameFeatures, Progress


def test_default_calibration():
    c = default_calibration("guest")
    assert c.mode == "default" and set(c.neutral) == set(AXES) and len(c.blend_neutral) == N_BLEND
    assert all(lo > 0 and hi > 0 for lo, hi in c.range.values())


def test_calibrator_interface():
    cal = Calibrator("guest", mode="quick")
    p = cal.feed(FrameFeatures(seq=0, t_capture_ns=0, t_infer_ns=0, face=True), 0.0)
    assert isinstance(p, Progress)
    assert isinstance(cal.result(), Calibration) and cal.result().mode == "quick"
