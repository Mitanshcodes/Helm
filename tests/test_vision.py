# OWNER: P1
"""Bootstrap check for vision.py: the module imports without MediaPipe."""
from helm.contracts import FrameFeatures
from helm.vision import FaceTracker


def test_tracker_interface():
    tracker = FaceTracker()
    f = tracker.process(None, t_capture_ns=10, seq=3)
    assert isinstance(f, FrameFeatures) and f.seq == 3 and f.t_infer_ns >= 10
    tracker.close()
