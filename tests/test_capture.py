# OWNER: P1
"""Bootstrap check for capture.py: the class builds without OpenCV or a camera."""
from helm.capture import Camera


def test_camera_constructs_without_hardware():
    cam = Camera(index=0)
    assert (cam.width, cam.height) == (640, 480)
