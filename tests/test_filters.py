# OWNER: P1
"""filters.py: shape_axis edge values, One Euro on a constant, range scaling, quick auto-range, drift, face lost."""
import math

import numpy as np
import pytest

from helm import config
from helm.calibration import default_calibration
from helm.contracts import AXES, BLENDSHAPE_NAMES, FEATURE_DIM, N_BLEND, Calibration, FrameFeatures
from helm.filters import Normalizer, OneEuro, shape_axis

DT_NS = 33_333_333


def frame(i: int, face: bool = True, **kw) -> FrameFeatures:
    return FrameFeatures(seq=i, t_capture_ns=i * DT_NS, t_infer_ns=i * DT_NS + 1, face=face, **kw)


def calib(**kw) -> Calibration:
    c = default_calibration("t", mode=kw.pop("mode", "full"))
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_one_euro_passes_a_constant():
    f = OneEuro()
    assert all(f(2.5, t * 0.033) == pytest.approx(2.5) for t in range(30))


def test_one_euro_smooths_and_converges():
    f = OneEuro()
    outs = [f(0.0 if i < 10 else 1.0, i / 30) for i in range(60)]
    assert 0.0 < outs[10] < 1.0                     # a step is not passed through instantly
    assert outs[-1] == pytest.approx(1.0, abs=1e-3)
    f.reset()
    assert f(5.0, 100.0) == 5.0                     # after reset the first sample passes through


def test_shape_axis_edges():
    assert shape_axis(0.0) == 0.0
    assert shape_axis(0.079, deadzone=0.08) == 0.0 and shape_axis(-0.079, deadzone=0.08) == 0.0
    assert shape_axis(0.08, deadzone=0.08) == 0.0
    assert shape_axis(1.0) == 1.0 and shape_axis(-1.0) == -1.0
    assert shape_axis(5.0) == 1.0 and shape_axis(-5.0) == -1.0
    assert shape_axis(1.0, invert=True) == -1.0
    mid = shape_axis(0.54, deadzone=0.08, gamma=1.5)
    assert mid == pytest.approx(0.5 ** 1.5)
    assert shape_axis(-0.54, deadzone=0.08, gamma=1.5) == pytest.approx(-mid)
    assert shape_axis(0.5, deadzone=0.0, gamma=1.0) == pytest.approx(0.5)


def test_ten_degree_range_maps_ten_degrees_to_one():
    n = Normalizer(calib(range={"yaw": (10.0, 10.0), "pitch": (10.0, 10.0), "roll": (10.0, 10.0)}))
    for i in range(5):
        s = n.update(frame(i, yaw=10.0, pitch=-5.0))
    assert s.axes["yaw"] == pytest.approx(1.0) and s.axes["pitch"] == pytest.approx(-0.5)


def test_neutral_and_per_direction_range():
    n = Normalizer(calib(neutral={"yaw": 5.0, "pitch": 0.0, "roll": 0.0},
                         range={"yaw": (10.0, 20.0), "pitch": (15.0, 15.0), "roll": (15.0, 15.0)}))
    assert n.update(frame(0, yaw=15.0)).axes["yaw"] == pytest.approx(0.5)      # +10 of a 20 degree right range
    n2 = Normalizer(n._calib)
    assert n2.update(frame(0, yaw=0.0)).axes["yaw"] == pytest.approx(-0.5)     # -5 of a 10 degree left range
    assert n2.update(frame(1, yaw=90.0)).axes["yaw"] <= 1.0                    # clamped


def test_uncalibrated_defaults():
    n = Normalizer()
    s = n.update(frame(1, yaw=config.DEFAULT_RANGE_DEG), breath=0.5)
    assert set(s.axes) == set(AXES) and s.axes["yaw"] == pytest.approx(1.0)
    assert s.expr.shape == (N_BLEND,) and s.delta.shape == (FEATURE_DIM,)
    assert s.breath == 0.5 and s.delta[-1] == pytest.approx(0.5)


def test_expression_scale_and_delta():
    k = BLENDSHAPE_NAMES.index("browInnerUp")
    j = BLENDSHAPE_NAMES.index("jawOpen")
    bn = [0.0] * N_BLEND
    bn[k] = 0.1
    n = Normalizer(calib(blend_neutral=bn, blend_peak={"browInnerUp": 0.5}))
    blend = np.zeros(N_BLEND, np.float32)
    blend[k], blend[j] = 0.3, 0.25
    s = n.update(frame(0, blend=blend))
    assert s.expr[k] == pytest.approx(0.5)                    # (0.3 - 0.1) / (0.5 - 0.1)
    assert s.expr[j] == pytest.approx(0.5)                    # no peak measured: neutral + 0.5
    assert s.delta[k] == pytest.approx(0.2)
    blend[k] = 0.0
    assert n.update(frame(1, blend=blend)).expr[k] == 0.0     # clamped at 0


def test_face_lost_returns_zeros_and_resets_filters():
    n = Normalizer()
    for i in range(10):
        n.update(frame(i, yaw=7.5))
    lost = n.update(frame(10, face=False), breath=-0.3)
    assert not lost.face and all(v == 0.0 for v in lost.axes.values()) and not lost.expr.any()
    assert lost.delta.shape == (FEATURE_DIM,) and lost.delta[-1] == pytest.approx(-0.3)
    back = n.update(frame(11, yaw=-config.DEFAULT_RANGE_DEG))
    assert back.axes["yaw"] == pytest.approx(-1.0)            # no smoothing carried over from before the loss


def test_quick_mode_widens_but_never_shrinks():
    n = Normalizer(calib(mode="quick"))
    for i in range(60):
        n.update(frame(i, yaw=24.0 + (i % 3)))
    widened = n.range["yaw"][1]
    assert 24.0 <= widened <= 26.0
    assert n.range["yaw"][0] == config.DEFAULT_RANGE_DEG     # the other direction is untouched
    for i in range(60, 120):
        n.update(frame(i, yaw=16.0))
    assert n.range["yaw"][1] == widened


def test_full_mode_does_not_auto_widen():
    n = Normalizer(calib(mode="full"))
    for i in range(60):
        n.update(frame(i, yaw=30.0))
    assert n.range["yaw"][1] == config.DEFAULT_RANGE_DEG


def test_drift_follows_pose_only_while_idle():
    n = Normalizer(calib())
    for i in range(300):                                      # 10 s at 2 degrees, not idle
        n.update(frame(i, yaw=2.0), idle=False)
    assert n.neutral["yaw"] == 0.0
    for i in range(300, 600):                                 # 10 s idle: about 1 - e^(-10/30) of the way
        n.update(frame(i, yaw=2.0), idle=True)
    expected = 2.0 * (1 - math.exp(-10 / config.DRIFT_TIME_CONSTANT_S))
    assert n.neutral["yaw"] == pytest.approx(expected, rel=0.05)


def test_drift_is_bounded():
    n = Normalizer(calib())
    for i in range(30 * 600):                                 # ten idle minutes far off neutral
        n.update(frame(i, yaw=40.0), idle=True)
    assert n.neutral["yaw"] == pytest.approx(config.DRIFT_MAX_FRACTION * config.DEFAULT_RANGE_DEG)


def test_steering_gain_scales_the_calibrated_range():
    from helm.calibration import default_calibration
    from helm.contracts import FrameFeatures
    c = default_calibration("sam", mode="full")
    c.range = {"yaw": (20.0, 20.0), "pitch": (10.0, 10.0), "roll": (10.0, 10.0)}
    n = Normalizer(c)
    n.set_gains({"yaw": 2.0})
    assert n.effective_range()["yaw"] == (10.0, 10.0) and n.effective_range()["pitch"] == (10.0, 10.0)
    for i in range(30):                                          # hold 5 degrees right: half the calibrated range
        s = n.update(FrameFeatures(seq=i, t_capture_ns=i * 33_000_000, t_infer_ns=i * 33_000_000, face=True, yaw=5.0))
    assert s.axes["yaw"] == pytest.approx(0.5, abs=0.02)         # gain 2: half lock, not a quarter
    n.set_gains({"yaw": 99.0})
    assert n.gain["yaw"] == config.STEER_GAIN_MAX
    n.set_gains({})
    assert n.gain["yaw"] == 1.0
