# OWNER: P1
"""vision.py: head-pose math and blendshape fill by name, without a camera. The tracker test needs MediaPipe."""
import os
import time
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from helm import config
from helm.contracts import BLENDSHAPE_NAMES, N_BLEND
from helm.vision import blend_from_categories, pose_from_matrix


def matrix(yaw=0.0, pitch=0.0, roll=0.0, scale=1.0) -> np.ndarray:
    m = np.eye(4)
    m[:3, :3] = Rotation.from_euler("yxz", [yaw, pitch, roll], degrees=True).as_matrix() * scale
    m[:3, 3] = [1.0, -2.0, -40.0]
    return m


def test_pose_from_matrix_signs_and_values():
    yaw, pitch, roll = pose_from_matrix(matrix(20.0, -10.0, 5.0))
    assert yaw == pytest.approx(config.YAW_SIGN * 20.0, abs=1e-6)
    assert pitch == pytest.approx(config.PITCH_SIGN * -10.0, abs=1e-6)
    assert roll == pytest.approx(config.ROLL_SIGN * 5.0, abs=1e-6)


def test_pose_from_matrix_removes_scale_and_noise():
    m = matrix(15.0, 5.0, -3.0, scale=1.3)
    m[:3, :3] += np.random.default_rng(0).normal(0, 1e-3, (3, 3))
    yaw, pitch, roll = pose_from_matrix(m)
    assert abs(yaw) == pytest.approx(15.0, abs=0.2) and abs(pitch) == pytest.approx(5.0, abs=0.2)


def test_blend_filled_by_name_not_index():
    cats = [SimpleNamespace(category_name="jawOpen", score=0.7),
            SimpleNamespace(category_name="_neutral", score=0.1),
            SimpleNamespace(category_name="somethingNew", score=0.9)]
    b = blend_from_categories(cats)
    assert b.shape == (N_BLEND,) and b.dtype == np.float32
    assert b[BLENDSHAPE_NAMES.index("jawOpen")] == pytest.approx(0.7)
    assert b[0] == pytest.approx(0.1) and b.sum() == pytest.approx(0.8)


@pytest.mark.skipif(not os.path.exists(config.MODEL_PATH), reason="model file not present")
def test_tracker_on_a_blank_frame():
    pytest.importorskip("mediapipe")
    from helm.vision import FaceTracker

    tracker = FaceTracker()
    try:
        now = time.perf_counter_ns()
        a = tracker.process(np.zeros((240, 320, 3), np.uint8), now, 1)
        b = tracker.process(np.zeros((240, 320, 3), np.uint8), now, 2)   # same timestamp must not raise
        assert not a.face and not b.face and b.seq == 2 and b.t_infer_ns >= now
    finally:
        tracker.close()
