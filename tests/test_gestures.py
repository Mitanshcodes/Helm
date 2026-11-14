# OWNER: P3
"""Bootstrap checks for gestures.py. TODO(P3): synthetic clusters separate, "none" suppresses, save/load round trip."""
import numpy as np

from helm.contracts import FEATURE_DIM, FrameFeatures, Progress
from helm.filters import Normalizer
from helm.gestures import GestureEngine, GestureModel, TakeRecorder
from helm.profiles import default_mapping


def _signals():
    return Normalizer().update(FrameFeatures(seq=0, t_capture_ns=0, t_infer_ns=0, face=True))


def test_model_interface():
    model = GestureModel()
    model.add_take("left_smirk", np.zeros((10, FEATURE_DIM), np.float32))
    model.add_negative(np.zeros((10, FEATURE_DIM), np.float32))
    assert model.names == ["left_smirk"]
    assert isinstance(model.fit(), dict)
    assert "none" in model.predict(np.zeros(FEATURE_DIM, np.float32))
    model.remove("left_smirk")
    assert model.names == []


def test_take_recorder_interface():
    rec = TakeRecorder("left_smirk")
    assert isinstance(rec.feed(_signals(), 0.0), Progress)
    assert isinstance(rec.result(), list)


def test_engine_reports_every_non_breath_gesture():
    defs = dict(default_mapping("SuperTuxKart")["gestures"], hard_puff={"kind": "breath"})
    act = GestureEngine(None, defs, None).update(_signals())
    assert set(act) == set(defs) - {"hard_puff"}
    assert all(0.0 <= v <= 1.0 for v in act.values())
