# OWNER: P1
"""Camera thread with a latest-frame slot (docs/SPEC.md 6.1)."""
import logging
import sys
import threading
import time

import numpy as np

from helm import config

log = logging.getLogger("helm.capture")


class Camera:
    """A daemon thread reads frames as fast as the camera delivers them and keeps only the newest."""

    def __init__(self, index: int = 0, width: int = config.CAMERA_WIDTH, height: int = config.CAMERA_HEIGHT,
                 fps: int = config.CAMERA_FPS):
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self._cap = None
        self._cond = threading.Condition()
        self._frame: np.ndarray | None = None
        self._t_capture_ns = 0
        self._seq = -1
        self._running = False
        self._thread: threading.Thread | None = None
        self.measured_fps = 0.0

    def start(self) -> None:
        import cv2

        if sys.platform == "win32":
            cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(self.index)
        if not cap.isOpened():
            raise RuntimeError(f"camera {self.index} did not open")
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        log.info("camera %d opened: %dx%d, driver reports %.0f fps", self.index,
                 int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                 cap.get(cv2.CAP_PROP_FPS))
        self._cap = cap
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, name="capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        with self._cond:
            self._cond.notify_all()

    def wait_latest(self, last_seq: int, timeout: float = 0.5) -> tuple[np.ndarray, int, int] | None:
        """Block until a frame newer than last_seq exists; return (bgr, t_capture_ns, seq)."""
        with self._cond:
            if not self._cond.wait_for(lambda: self._seq > last_seq or not self._running, timeout=timeout):
                return None
            if self._seq <= last_seq:
                return None
            return self._frame, self._t_capture_ns, self._seq

    def _read_loop(self) -> None:
        fails = 0
        count = 0
        t_window = time.perf_counter()
        logged_fps = False
        while self._running:
            ok, frame = self._cap.read()
            t_capture_ns = time.perf_counter_ns()
            if not ok or frame is None:
                fails += 1
                if fails == 30:
                    log.warning("camera %d returns no frames", self.index)
                time.sleep(0.01)                   # capture thread only; never the pipeline thread
                continue
            fails = 0
            with self._cond:
                self._frame = frame                # each read() returns a new array, so no copy is needed
                self._t_capture_ns = t_capture_ns
                self._seq += 1
                self._cond.notify_all()
            count += 1
            elapsed = time.perf_counter() - t_window
            if elapsed >= 2.0:
                self.measured_fps = count / elapsed
                if not logged_fps:
                    log.info("camera %d delivers %.1f fps", self.index, self.measured_fps)
                    logged_fps = True
                count, t_window = 0, time.perf_counter()


if __name__ == "__main__":
    # python -m helm.capture: show the measured fps for a few seconds.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    cam = Camera(index=int(sys.argv[1]) if len(sys.argv) > 1 else 0)
    cam.start()
    last, n, t0 = -1, 0, time.perf_counter()
    while time.perf_counter() - t0 < 5.0:
        got = cam.wait_latest(last)
        if got:
            last, n = got[2], n + 1
    cam.stop()
    print(f"pipeline saw {n / 5.0:.1f} fps")
