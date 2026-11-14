# OWNER: P3
"""TakeRecorder, GestureModel (k-NN) and GestureEngine (docs/SPEC.md 6.11). Bootstrap stubs: nothing fires."""
import numpy as np

from helm import config
from helm.contracts import Calibration, Progress, Signals


class GestureModel:
    def __init__(self) -> None:
        self._takes: dict[str, list[np.ndarray]] = {}
        self._negatives: list[np.ndarray] = []

    def add_take(self, name: str, frames: np.ndarray) -> None:
        """frames: (n, 56) deltas from one take."""
        self._takes.setdefault(name, []).append(np.asarray(frames, np.float32))

    def add_negative(self, frames: np.ndarray) -> None:
        """Frames for the "none" class."""
        self._negatives.append(np.asarray(frames, np.float32))

    def remove(self, name: str) -> None:
        self._takes.pop(name, None)

    def fit(self) -> dict[str, float]:
        """Gesture name -> leave-one-take-out accuracy."""
        # TODO(P3): StandardScaler + KNeighborsClassifier(n_neighbors=7, weights="distance").
        return {}

    def predict(self, delta: np.ndarray) -> dict[str, float]:
        """Class probabilities, including "none"."""
        # TODO(P3): the stub says "none" every time.
        probs = {name: 0.0 for name in self._takes}
        probs["none"] = 1.0
        return probs

    @property
    def names(self) -> list[str]:
        return sorted(self._takes)

    def save(self, path: str) -> None:
        # TODO(P3): one .npz with the raw takes and negatives, so the model refits on load.
        pass

    @classmethod
    def load(cls, path: str) -> "GestureModel":
        # TODO(P3): read the .npz and refit.
        return cls()


class TakeRecorder:
    def __init__(self, name: str | None, takes: int = config.TAKES):   # name None = record negatives only (15 s)
        self.name = name
        self.takes = takes

    def feed(self, s: Signals, t_s: float) -> Progress:
        # TODO(P3): per take "get ready" 1 s, "do it now and hold" 1 s, "relax" 1 s; or 15 s of negatives.
        return Progress(active=False, step="done", prompt="Recording complete", progress=1.0, overall=1.0, done=True)

    def result(self) -> list[np.ndarray]:
        return []


class GestureEngine:
    def __init__(self, calib: Calibration | None, gesture_defs: dict, model: GestureModel | None):
        self._calib = calib
        self._defs = gesture_defs
        self._model = model

    def update(self, s: Signals) -> dict[str, float]:
        """Activation in [0, 1] for every defined gesture except breath ones (the Mapper handles those)."""
        # TODO(P3): blendshape gestures from s.expr (min or max over sources); learned gestures from the
        # model, averaged over 4 frames and forced to 0 when P("none") >= 0.3.
        return {name: 0.0 for name, g in self._defs.items() if g.get("kind") != "breath"}
