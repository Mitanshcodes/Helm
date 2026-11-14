# OWNER: P1
"""Bootstrap checks for filters.py. TODO(P1): shape_axis edge values, One Euro on a constant, 10 degree range."""
from helm.contracts import AXES, FEATURE_DIM, N_BLEND, FrameFeatures
from helm.filters import Normalizer, OneEuro, shape_axis


def test_one_euro_passes_a_constant():
    f = OneEuro()
    assert all(f(2.5, t * 0.033) == 2.5 for t in range(10))


def test_shape_axis_stays_in_range():
    assert shape_axis(0.0) == 0.0
    assert shape_axis(5.0) == 1.0 and shape_axis(-5.0) == -1.0
    assert shape_axis(1.0, invert=True) == -1.0


def test_normalizer_shapes():
    n = Normalizer()
    s = n.update(FrameFeatures(seq=1, t_capture_ns=1, t_infer_ns=2, face=True, yaw=15.0), breath=0.5)
    assert set(s.axes) == set(AXES) and s.axes["yaw"] == 1.0
    assert s.expr.shape == (N_BLEND,) and s.delta.shape == (FEATURE_DIM,)
    assert s.breath == 0.5

    lost = n.update(FrameFeatures(seq=2, t_capture_ns=3, t_infer_ns=4, face=False))
    assert not lost.face and all(v == 0.0 for v in lost.axes.values()) and not lost.expr.any()
