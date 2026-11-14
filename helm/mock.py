# OWNER: P1
"""Mock source, recorder and replay, so every lane can work without a camera (docs/SPEC.md 6.3)."""
import math
import time

import numpy as np

from helm import config
from helm.contracts import BLENDSHAPE_NAMES, N_BLEND, FrameFeatures

_BROW = BLENDSHAPE_NAMES.index("browInnerUp")
_JAW = BLENDSHAPE_NAMES.index("jawOpen")
_FIELDS = ("seq", "t_capture_ns", "t_infer_ns", "face", "yaw", "pitch", "roll")


class MockSource:
    """Synthetic FrameFeatures paced at 30 Hz. realtime=False returns immediately (for tests)."""

    def __init__(self, hz: float = config.MOCK_HZ, realtime: bool = True):
        self._dt = 1.0 / hz
        self._realtime = realtime
        self._seq = 0
        self._next_t: float | None = None

    def next(self) -> FrameFeatures:
        if self._realtime:
            now = time.perf_counter()
            if self._next_t is None or now - self._next_t > 1.0:
                self._next_t = now
            if self._next_t > now:
                time.sleep(self._next_t - now)
            self._next_t += self._dt

        seq = self._seq
        self._seq += 1
        t = seq * self._dt
        t_capture_ns = time.perf_counter_ns()
        face = (t % 20.0) < 19.5                              # drops out for 0.5 s every 20 s
        if not face:
            return FrameFeatures(seq=seq, t_capture_ns=t_capture_ns, t_infer_ns=time.perf_counter_ns(), face=False)

        blend = np.zeros(N_BLEND, np.float32)
        blend[_BROW] = 0.8 if (t % 3.0) < 0.4 else 0.0        # pulses every 3 s
        blend[_JAW] = 0.7 * (1.0 - abs((t % 4.0) / 2.0 - 1.0))  # ramps up and down
        yaw = 15.0 * math.sin(2.0 * math.pi * t / 8.0)        # slow sine, +-15 degrees
        return FrameFeatures(seq=seq, t_capture_ns=t_capture_ns, t_infer_ns=time.perf_counter_ns(), face=True,
                             yaw=yaw, blend=blend)


_BLINK_L = BLENDSHAPE_NAMES.index("eyeBlinkLeft")
_BLINK_R = BLENDSHAPE_NAMES.index("eyeBlinkRight")
_SMILE_L = BLENDSHAPE_NAMES.index("mouthSmileLeft")
_SMILE_R = BLENDSHAPE_NAMES.index("mouthSmileRight")


def render_preview(f: FrameFeatures, size: tuple[int, int] = config.PREVIEW_SIZE) -> np.ndarray:
    """A cartoon face drawn from the features, standing in for the camera frame under --mock and --replay.

    Drawn as the camera sees the subject (unmirrored); the server mirrors it like a real frame.
    """
    import cv2

    w, h = size
    img = np.full((h, w, 3), (40, 34, 30), np.uint8)
    r = h * 0.32
    if not f.face:                                         # an empty outline (text would come out mirrored)
        cv2.circle(img, (w // 2, h // 2), int(r), (90, 90, 90), 2, cv2.LINE_AA)
        return img
    b = f.blend
    # +yaw (turn to their own right) and +roll move toward the image's left: the subject's right, unmirrored.
    cx = w / 2 - r * math.sin(math.radians(max(-60.0, min(60.0, f.yaw))))
    cy = h / 2 - r * math.sin(math.radians(max(-60.0, min(60.0, f.pitch))))
    roll = math.radians(f.roll)

    def pt(x: float, y: float) -> tuple[int, int]:      # face-space offset (in radii) -> rotated pixel
        dx, dy = x * r, y * r
        return (int(cx + dx * math.cos(roll) + dy * math.sin(roll)),
                int(cy - dx * math.sin(roll) + dy * math.cos(roll)))

    skin, line = (150, 180, 215), (40, 40, 60)
    cv2.circle(img, pt(0, 0), int(r), skin, -1, cv2.LINE_AA)
    brow = 0.15 * float(b[_BROW])
    # Image-left is the subject's right side.
    for side, blink in ((-1, b[_BLINK_R]), (1, b[_BLINK_L])):
        ex = 0.38 * side
        cv2.line(img, pt(ex - 0.18, -0.42 - brow), pt(ex + 0.18, -0.42 - brow), line, 3, cv2.LINE_AA)
        open_px = max(1, int(r * 0.1 * (1.0 - float(blink))))
        cv2.ellipse(img, pt(ex, -0.2), (int(r * 0.12), open_px), -math.degrees(roll), 0, 360, line, -1, cv2.LINE_AA)
    jaw = float(b[_JAW])
    smile_r, smile_l = float(b[_SMILE_R]), float(b[_SMILE_L])
    low = 0.46 + 0.3 * jaw
    mouth = [pt(-0.35, 0.42 - 0.12 * smile_r), pt(-0.15, 0.40), pt(0.15, 0.40), pt(0.35, 0.42 - 0.12 * smile_l),
             pt(0.15, low), pt(-0.15, low)]
    cv2.fillPoly(img, [np.array(mouth, np.int32)], line, cv2.LINE_AA)
    return img


class Recorder:
    """Buffers FrameFeatures in memory and writes one .npz on close. No images are stored."""

    def __init__(self, path: str):
        self._path = path
        self._rows: dict[str, list] = {name: [] for name in _FIELDS}
        self._blend: list[np.ndarray] = []

    def write(self, f: FrameFeatures) -> None:
        for name in _FIELDS:
            self._rows[name].append(getattr(f, name))
        self._blend.append(np.array(f.blend, np.float32))

    def close(self) -> None:
        np.savez(
            self._path,
            seq=np.array(self._rows["seq"], np.int64),
            t_capture_ns=np.array(self._rows["t_capture_ns"], np.int64),
            t_infer_ns=np.array(self._rows["t_infer_ns"], np.int64),
            face=np.array(self._rows["face"], bool),
            yaw=np.array(self._rows["yaw"], np.float32),
            pitch=np.array(self._rows["pitch"], np.float32),
            roll=np.array(self._rows["roll"], np.float32),
            blend=np.array(self._blend, np.float32).reshape(-1, N_BLEND),
        )


class ReplaySource:
    """Plays a Recorder file back. Timestamps are re-stamped to now; the recorded vision delay is kept."""

    def __init__(self, path: str, realtime: bool = True):
        with np.load(path) as data:
            self._d = {name: data[name] for name in (*_FIELDS, "blend")}
        self._realtime = realtime
        self._i = 0
        self._t0: float | None = None

    def next(self) -> FrameFeatures | None:
        d, i = self._d, self._i
        if i >= len(d["seq"]):
            return None
        self._i += 1
        if self._realtime:
            if self._t0 is None:
                self._t0 = time.perf_counter()
            due = self._t0 + (int(d["t_capture_ns"][i]) - int(d["t_capture_ns"][0])) / 1e9
            wait = due - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
        now = time.perf_counter_ns()
        vision_ns = int(d["t_infer_ns"][i]) - int(d["t_capture_ns"][i])
        return FrameFeatures(seq=int(d["seq"][i]), t_capture_ns=now - vision_ns, t_infer_ns=now,
                             face=bool(d["face"][i]), yaw=float(d["yaw"][i]), pitch=float(d["pitch"][i]),
                             roll=float(d["roll"][i]), blend=d["blend"][i].astype(np.float32))
