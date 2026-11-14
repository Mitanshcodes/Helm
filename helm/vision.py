# OWNER: P1
"""MediaPipe Face Landmarker wrapper -> FrameFeatures (docs/SPEC.md 6.2). Bootstrap stub: never finds a face."""
import time

import numpy as np

from helm import config
from helm.contracts import FrameFeatures


class FaceTracker:
    def __init__(self, model_path: str = config.MODEL_PATH):
        # TODO(P1): import mediapipe here; create FaceLandmarker in VIDEO mode, num_faces=1, with
        # blendshapes and transformation matrices. Compare the model's category names with
        # contracts.BLENDSHAPE_NAMES on the first real inference.
        self.model_path = model_path

    def process(self, bgr: np.ndarray, t_capture_ns: int, seq: int) -> FrameFeatures:
        # TODO(P1): BGR -> RGB (never mirror), detect_for_video with strictly increasing ms timestamps,
        # head pose from the rotation block, blend filled by category name.
        return FrameFeatures(seq=seq, t_capture_ns=t_capture_ns, t_infer_ns=time.perf_counter_ns(), face=False)

    def close(self) -> None:
        pass


if __name__ == "__main__":
    # TODO(P1): live print test of yaw, pitch, roll and jawOpen to check signs.
    raise SystemExit("python -m helm.vision: print test not implemented yet")
