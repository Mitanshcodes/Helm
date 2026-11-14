# OWNER: P1
"""capture.py: the latest-frame slot and wait_latest, without OpenCV or a camera."""
import threading
import time

import numpy as np

from helm.capture import Camera


def test_camera_constructs_without_hardware():
    cam = Camera(index=0)
    assert (cam.width, cam.height) == (640, 480)


def _publish(cam: Camera, n: int) -> None:
    """Stand-in for the read loop: overwrite the slot as the capture thread does."""
    with cam._cond:
        cam._frame = np.full((2, 2, 3), n, np.uint8)
        cam._t_capture_ns = time.perf_counter_ns()
        cam._seq = n
        cam._cond.notify_all()


def test_wait_latest_returns_only_newer_frames():
    cam = Camera()
    cam._running = True
    assert cam.wait_latest(-1, timeout=0.01) is None              # nothing yet
    _publish(cam, 0)
    _publish(cam, 1)
    _publish(cam, 2)                                              # a slow consumer skips stale frames
    frame, t_ns, seq = cam.wait_latest(0, timeout=0.01)
    assert seq == 2 and frame[0, 0, 0] == 2 and t_ns > 0
    assert cam.wait_latest(2, timeout=0.01) is None


def test_wait_latest_wakes_on_a_new_frame():
    cam = Camera()
    cam._running = True
    threading.Timer(0.05, _publish, (cam, 7)).start()
    t0 = time.perf_counter()
    got = cam.wait_latest(-1, timeout=1.0)
    assert got is not None and got[2] == 7 and time.perf_counter() - t0 < 0.5
