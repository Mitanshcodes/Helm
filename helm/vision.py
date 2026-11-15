# OWNER: P1
"""MediaPipe Face Landmarker wrapper -> FrameFeatures (docs/SPEC.md 6.2).

Print test: `python -m helm.vision [camera]` shows yaw, pitch, roll and jawOpen live, with a mirrored
preview window. Turn to your own right: yaw goes positive. Chin up: pitch positive. Tilt toward your
right shoulder: roll positive. If a sign is wrong, flip it in config (YAW_SIGN, PITCH_SIGN, ROLL_SIGN).
"""
import logging
import time

import numpy as np
from scipy.spatial.transform import Rotation

from helm import config
from helm.contracts import BLENDSHAPE_NAMES, N_BLEND, FrameFeatures

log = logging.getLogger("helm.vision")

_BLEND_INDEX = {name: i for i, name in enumerate(BLENDSHAPE_NAMES)}


def pose_from_matrix(m: np.ndarray) -> tuple[float, float, float]:
    """Yaw, pitch, roll in degrees from MediaPipe's 4x4 facial transformation matrix, signs as in FrameFeatures."""
    r = np.asarray(m, np.float64)[:3, :3]
    u, _, vt = np.linalg.svd(r)                    # re-orthonormalize: the block carries scale and noise
    r = u @ vt
    if np.linalg.det(r) < 0:
        u[:, -1] *= -1
        r = u @ vt
    yaw, pitch, roll = Rotation.from_matrix(r).as_euler("yxz", degrees=True)
    return (config.YAW_SIGN * float(yaw), config.PITCH_SIGN * float(pitch), config.ROLL_SIGN * float(roll))


def blend_from_categories(categories) -> np.ndarray:
    """(52,) scores in BLENDSHAPE_NAMES order, filled by category name, never by index."""
    out = np.zeros(N_BLEND, np.float32)
    for c in categories:
        i = _BLEND_INDEX.get(c.category_name)
        if i is not None:
            out[i] = c.score
    return out


class FaceTracker:
    def __init__(self, model_path: str = config.MODEL_PATH):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python import vision as mp_vision

        self._mp = mp
        options = mp_vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)
        self._last_ts_ms = -1
        self._names_checked = False

    def process(self, bgr: np.ndarray, t_capture_ns: int, seq: int) -> FrameFeatures:
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])   # BGR -> RGB. Never mirror before inference.
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        ts_ms = t_capture_ns // 1_000_000
        if ts_ms <= self._last_ts_ms:                 # detect_for_video needs strictly increasing ints
            ts_ms = self._last_ts_ms + 1
        self._last_ts_ms = ts_ms
        result = self._landmarker.detect_for_video(image, ts_ms)
        t_infer_ns = time.perf_counter_ns()

        if not result.face_landmarks or not result.face_blendshapes or not result.facial_transformation_matrixes:
            return FrameFeatures(seq=seq, t_capture_ns=t_capture_ns, t_infer_ns=t_infer_ns, face=False)

        categories = result.face_blendshapes[0]
        if not self._names_checked:
            self._check_names(categories)
        yaw, pitch, roll = pose_from_matrix(result.facial_transformation_matrixes[0])
        landmarks3d = np.array([(p.x, p.y, p.z) for p in result.face_landmarks[0]], np.float32)
        landmarks = landmarks3d[:, :2].copy()
        return FrameFeatures(seq=seq, t_capture_ns=t_capture_ns, t_infer_ns=t_infer_ns, face=True,
                             yaw=yaw, pitch=pitch, roll=roll, blend=blend_from_categories(categories),
                             landmarks=landmarks, landmarks3d=landmarks3d)

    def close(self) -> None:
        self._landmarker.close()

    def _check_names(self, categories) -> None:
        """Compare the model's own category names with contracts.BLENDSHAPE_NAMES, once."""
        self._names_checked = True
        names = tuple(c.category_name for c in categories)
        if names == BLENDSHAPE_NAMES:
            log.info("blendshape names match contracts.BLENDSHAPE_NAMES (%d)", len(names))
            return
        missing = sorted(set(BLENDSHAPE_NAMES) - set(names))
        extra = sorted(set(names) - set(BLENDSHAPE_NAMES))
        log.warning("blendshape names differ from contracts: missing %s, extra %s, same order: %s",
                    missing, extra, not missing and not extra and names == BLENDSHAPE_NAMES)


def _print_test(camera_index: int = 0) -> None:
    import cv2

    from helm.capture import Camera

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    cam = Camera(index=camera_index)
    tracker = FaceTracker()
    cam.start()
    jaw = BLENDSHAPE_NAMES.index("jawOpen")
    print("Turn right: yaw +. Chin up: pitch +. Tilt to right shoulder: roll +. Press q or Esc to quit.")
    last, t_print = -1, 0.0
    try:
        while True:
            got = cam.wait_latest(last)
            if got is None:
                continue
            bgr, t_capture_ns, last = got
            f = tracker.process(bgr, t_capture_ns, last)
            infer_ms = (f.t_infer_ns - f.t_capture_ns) / 1e6
            if f.face:
                line = (f"yaw {f.yaw:+6.1f}  pitch {f.pitch:+6.1f}  roll {f.roll:+6.1f}  "
                        f"jawOpen {f.blend[jaw]:.2f}  vision {infer_ms:5.1f} ms")
            else:
                line = f"no face  vision {infer_ms:5.1f} ms"
            now = time.perf_counter()
            if now - t_print > 0.1:
                print(line)
                t_print = now
            view = cv2.flip(bgr, 1)                   # mirror the preview only
            if f.landmarks is not None:
                h, w = view.shape[:2]
                for x, y in f.landmarks[::4]:
                    cv2.circle(view, (int((1.0 - x) * w), int(y * h)), 1, (0, 255, 0), -1)
            cv2.putText(view, line, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow("helm.vision", view)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cam.stop()
        tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    import sys

    _print_test(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
