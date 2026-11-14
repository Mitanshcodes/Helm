# OWNER: P1
"""Camera thread with a latest-frame slot (docs/SPEC.md 6.1). Bootstrap stub: delivers no frames."""
import logging
import time

import numpy as np

from helm import config

log = logging.getLogger("helm.capture")


class Camera:
    def __init__(self, index: int = 0, width: int = config.CAMERA_WIDTH, height: int = config.CAMERA_HEIGHT,
                 fps: int = config.CAMERA_FPS):
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps

    def start(self) -> None:
        # TODO(P1): import cv2 here; open the camera (CAP_DSHOW on Windows, MJPG, buffer size 1), start a
        # daemon thread that overwrites one slot under a lock and stamps t_capture_ns right after read().
        log.warning("Camera is a bootstrap stub and delivers no frames. Run with --mock.")

    def stop(self) -> None:
        pass

    def wait_latest(self, last_seq: int, timeout: float = 0.5) -> tuple[np.ndarray, int, int] | None:
        """Block until a frame newer than last_seq exists; return (bgr, t_capture_ns, seq)."""
        # TODO(P1): wait on a threading.Condition instead of sleeping.
        time.sleep(timeout)
        return None
