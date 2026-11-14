# OWNER: P3
"""TakeRecorder, GestureModel (k-NN) and GestureEngine (docs/SPEC.md 6.11)."""
import os
from collections import deque

import numpy as np

from helm import config
from helm.contracts import AXES, BLENDSHAPE_NAMES, FEATURE_DIM, N_BLEND, Calibration, Progress, Signals

NONE = "none"
_POSE = slice(N_BLEND, N_BLEND + len(AXES))       # yaw, pitch, roll inside the 56-value delta


class GestureModel:
    """Learned gestures from a few takes each. Weighted deltas, distance-weighted k-NN, "none" as a class.

    Refit from the raw takes whenever data changes (well under a second at this size, but still off the
    pipeline thread). fit() swaps in the new classifier in one assignment, so predict() may run meanwhile on
    another thread. Do not add or remove data on a model another thread is fitting: copy() it first.
    """

    def __init__(self) -> None:
        self._takes: dict[str, list[np.ndarray]] = {}
        self._negatives: list[np.ndarray] = []
        self._fitted: _Fitted | None = None

    def add_take(self, name: str, frames: np.ndarray) -> None:
        """frames: (n, 56) deltas from one take."""
        frames = _as_frames(frames)
        if len(frames) and name != NONE:
            self._takes.setdefault(name, []).append(frames)

    def add_negative(self, frames: np.ndarray) -> None:
        """Frames for the "none" class."""
        frames = _as_frames(frames)
        if len(frames):
            self._negatives.append(frames)

    def remove(self, name: str) -> None:
        self._takes.pop(name, None)

    def copy(self) -> "GestureModel":
        """Same data and current classifier; adding to the copy leaves this model untouched."""
        other = GestureModel()
        other._takes = {name: list(takes) for name, takes in self._takes.items()}
        other._negatives = list(self._negatives)
        other._fitted = self._fitted
        return other

    def fit(self) -> dict[str, float]:
        """Fit on everything, then score each class leave-one-take-out. Gesture name (and "none") -> accuracy."""
        groups = self._groups()
        self._fitted = _Fitted(groups)
        accuracy: dict[str, float] = {}
        for name in {label for label, _ in groups}:
            held_out = [i for i, (label, _) in enumerate(groups) if label == name]
            if len(held_out) < 2:                  # nothing left to train this class on if its only take is out
                continue
            hits = total = 0
            for i in held_out:
                part = _Fitted([g for j, g in enumerate(groups) if j != i])
                hits += part.hits(groups[i][1], name)
                total += len(groups[i][1])
            accuracy[name] = hits / total if total else 0.0
        return accuracy

    def predict(self, delta: np.ndarray) -> dict[str, float]:
        """Class probabilities, including "none"."""
        probs = {name: 0.0 for name in self._takes}
        probs[NONE] = 1.0
        fitted = self._fitted                      # read once: fit() may replace it from another thread
        if fitted is None or fitted.clf is None:
            return probs
        x = np.asarray(delta, np.float32).reshape(1, -1) / fitted.scale
        for name, p in zip(fitted.classes, fitted.clf.predict_proba(x)[0]):
            probs[name] = float(p)
        if NONE not in fitted.classes:
            probs[NONE] = 0.0
        return probs

    @property
    def names(self) -> list[str]:
        return sorted(self._takes)

    def save(self, path: str) -> None:
        """One .npz with the raw takes and negatives (the model refits on load). Written atomically."""
        groups = self._groups(chunk_negatives=False)
        frames = np.concatenate([g for _, g in groups]) if groups else np.zeros((0, FEATURE_DIM), np.float32)
        labels = np.array([label for label, g in groups for _ in range(len(g))], dtype=str)
        group_ids = np.concatenate([np.full(len(g), i, np.int32) for i, (_, g) in enumerate(groups)]) \
            if groups else np.zeros(0, np.int32)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            np.savez(fh, frames=frames, labels=labels, groups=group_ids)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str) -> "GestureModel":
        model = cls()
        with np.load(path) as data:
            frames, labels, group_ids = data["frames"], data["labels"], data["groups"]
        for g in np.unique(group_ids):
            rows = group_ids == g
            label = str(labels[rows][0])
            if label == NONE:
                model.add_negative(frames[rows])
            else:
                model.add_take(label, frames[rows])
        model.fit()
        return model

    # ------------------------------------------------------------------ internals

    def _groups(self, chunk_negatives: bool = True) -> list[tuple[str, np.ndarray]]:
        """(label, frames) per take. Negatives are pooled and cut into NEGATIVE_CHUNKS for leave-one-out."""
        groups = [(name, take) for name in sorted(self._takes) for take in self._takes[name]]
        if self._negatives:
            if chunk_negatives:
                pooled = np.concatenate(self._negatives)
                n = min(config.NEGATIVE_CHUNKS, len(pooled))
                groups += [(NONE, chunk) for chunk in np.array_split(pooled, n)]
            else:
                groups += [(NONE, neg) for neg in self._negatives]
        return groups


class _Fitted:
    """Feature weights plus classifier fitted on some groups. clf is None with fewer than two classes."""

    def __init__(self, groups: list[tuple[str, np.ndarray]]):
        self.scale = np.ones(FEATURE_DIM, np.float32)
        self.clf = None
        self.classes: list[str] = []
        labels = sorted({label for label, _ in groups})
        if len(labels) < 2:
            self.only = labels[0] if labels else NONE
            return
        x = np.concatenate([g for _, g in groups])
        y = np.array([label for label, g in groups for _ in range(len(g))])
        # Fixed weights, not per-feature standardization: every feature is already on a 0..1 (pose -1..1) scale,
        # and dividing the ~45 blendshapes a gesture does not use by their tiny spread blew their tracking noise
        # up past the gesture itself (54% leave-one-take-out on synthetic data). Head pose counts for less,
        # so steering while making a gesture still recognizes it.
        self.scale[_POSE] = 1.0 / config.KNN_POSE_WEIGHT
        from sklearn.neighbors import KNeighborsClassifier

        self.clf = KNeighborsClassifier(n_neighbors=min(config.KNN_NEIGHBORS, len(x)), weights="distance")
        self.clf.fit(x / self.scale, y)
        self.classes = [str(c) for c in self.clf.classes_]

    def hits(self, frames: np.ndarray, label: str) -> int:
        if self.clf is None:
            return len(frames) if self.only == label else 0
        return int(np.sum(self.clf.predict(frames / self.scale) == label))


def _as_frames(frames: np.ndarray) -> np.ndarray:
    a = np.asarray(frames, np.float32)
    if a.ndim != 2 or a.shape[1] != FEATURE_DIM:
        raise ValueError(f"frames must be (n, {FEATURE_DIM}), got {a.shape}")
    return a[np.isfinite(a).all(axis=1)]


_BLINKS = [BLENDSHAPE_NAMES.index(n) for n in ("eyeBlinkLeft", "eyeBlinkRight")]
_MOVE_MASK = np.ones(FEATURE_DIM, bool)
_MOVE_MASK[_BLINKS] = False                       # a blink is not the move
_MOVE_MASK[-1] = False                            # nor is breath


class TakeRecorder:
    """Guides the player through takes of one move (or 15 s of everyday face) and keeps the frames.

    Each take works like a calibration step: "get ready" (the relaxed face it is measured against), then
    "now, and hold", which waits until the face has actually moved and records TAKE_HOLD_S of the move held
    (nudging after TAKE_NUDGE_S, giving up after TAKE_GO_TIMEOUT_S), then "relax". The second half of each relax
    window is neutral rest for the "none" class (`rest`). Every timer pauses while the face is lost.
    Steps: take_N_ready, take_N_go, take_N_relax; read_aloud for the everyday face.
    """

    def __init__(self, name: str | None, takes: int = config.TAKES):   # name None = record negatives only (15 s)
        self.name = name
        self.takes = takes
        self.rest: list[np.ndarray] = []           # neutral frames from the relax windows, for "none"
        self._label = (name or "").replace("_", " ")
        if name is None:
            self._phases = [("read_aloud", config.NEGATIVE_S, "Read the text aloud, look around, and laugh", "negative")]
        else:
            self._phases = []
            for k in range(1, takes + 1):
                lead = f"Try {k} of {takes}:"
                self._phases += [(f"take_{k}_ready", config.TAKE_READY_S, f"{lead} relax, then get ready to {self._label}", "ready"),
                                 (f"take_{k}_go", config.TAKE_HOLD_S, f"{self._label.capitalize()} now, and hold", "go"),
                                 (f"take_{k}_relax", config.TAKE_RELAX_S, "And relax", "relax")]
        self._total_s = sum(p[1] for p in self._phases)
        self._i = 0
        self._elapsed = 0.0                        # seconds in this phase (face visible)
        self._held = 0.0                           # go phase: seconds spent past TAKE_MOVED
        self._done_s = 0.0
        self._last_t: float | None = None
        self._frames: list[np.ndarray] = []        # current phase
        self._moved: list[np.ndarray] = []         # go phase: frames past TAKE_MOVED
        self._baseline = np.zeros(FEATURE_DIM, np.float32)
        self._result: list[np.ndarray] = []
        self._done = False

    def feed(self, s: Signals, t_s: float) -> Progress:
        if self._done:
            return self._progress()
        dt = 0.0 if self._last_t is None else min(max(t_s - self._last_t, 0.0), config.CALIB_MAX_DT_S)
        self._last_t = t_s
        if not s.face:
            return self._progress(prompt="I can't see your face. Look at the screen")
        delta = np.asarray(s.delta, np.float32)
        self._frames.append(delta)
        self._elapsed += dt
        step, duration, _, kind = self._phases[self._i]
        if kind == "go":
            if self._distance(delta) >= config.TAKE_MOVED:
                self._held += dt
                self._moved.append(delta)
            finished = self._held >= config.TAKE_HOLD_S or self._elapsed >= config.TAKE_GO_TIMEOUT_S
        else:
            finished = self._elapsed >= duration
        if finished:
            self._finish_phase()
            self._done_s += duration
            self._i += 1
            self._elapsed = 0.0
            self._held = 0.0
            self._frames, self._moved = [], []
            self._done = self._i == len(self._phases)
        return self._progress()

    def result(self) -> list[np.ndarray]:
        """One (n, 56) array per take, or a single array of negatives. Valid once Progress.done is True."""
        return list(self._result)

    def _distance(self, delta: np.ndarray) -> float:
        return float(np.linalg.norm((delta - self._baseline)[_MOVE_MASK]))

    def _finish_phase(self) -> None:
        kind = self._phases[self._i][3]
        if not self._frames:
            return
        frames = np.stack(self._frames)
        if kind == "negative":
            self._result.append(frames)
        elif kind == "ready":                      # the relaxed face just before the move
            self._baseline = np.median(frames[len(frames) // 2:], axis=0).astype(np.float32)
        elif kind == "go":
            if self._moved:
                self._result.append(np.stack(self._moved))
            else:                                  # timed out: keep the frames furthest from the ready face
                distance = np.array([self._distance(f) for f in frames])
                keep = max(1, int(round(config.TAKE_TOP_FRACTION * len(frames))))
                self._result.append(frames[np.sort(np.argsort(-distance)[:keep])])
        elif kind == "relax":
            self.rest.append(frames[len(frames) // 2:])

    def _progress(self, prompt: str | None = None) -> Progress:
        if self._done:
            return Progress(active=False, step="done", prompt="Recording complete", progress=1.0, overall=1.0,
                            done=True)
        step, duration, phase_prompt, kind = self._phases[self._i]
        progress = min(self._elapsed / duration, 1.0)
        if kind == "go":                           # the ring fills only while the move is held
            progress = min(self._held / config.TAKE_HOLD_S, 1.0)
            if prompt is None and self._held == 0.0 and self._elapsed >= config.TAKE_NUDGE_S:
                prompt = f"A little bigger: {self._label}, and hold"
        return Progress(active=True, step=step, prompt=prompt or phase_prompt, progress=progress,
                        overall=min((self._done_s + min(self._elapsed, duration)) / self._total_s, 0.99))


class GestureEngine:
    """Signals -> activation in [0, 1] for every defined gesture except breath ones (the Mapper handles those)."""

    def __init__(self, calib: Calibration | None, gesture_defs: dict, model: GestureModel | None):
        self._calib = calib
        self._model = model
        self._blend: dict[str, tuple[list[int], str]] = {}
        self._learned: list[str] = []
        for name, g in gesture_defs.items():
            kind = g.get("kind")
            if kind == "blendshape":
                idx = [BLENDSHAPE_NAMES.index(src) for src in g.get("sources", []) if src in BLENDSHAPE_NAMES]
                self._blend[name] = (idx, g.get("combine", "max"))
            elif kind == "learned":
                self._learned.append(name)
        self._history: deque[dict[str, float]] = deque(maxlen=config.LEARNED_SMOOTH_FRAMES)

    def update(self, s: Signals) -> dict[str, float]:
        act: dict[str, float] = {}
        for name, (idx, combine) in self._blend.items():
            if not s.face or not idx:
                act[name] = 0.0
                continue
            values = [float(s.expr[i]) for i in idx]
            act[name] = min(values) if combine == "min" else max(values)
        if self._learned:
            act.update(self._learned_levels(s))
        return act

    def _learned_levels(self, s: Signals) -> dict[str, float]:
        if not s.face or self._model is None:
            self._history.clear()
            return {name: 0.0 for name in self._learned}
        self._history.append(self._model.predict(s.delta))
        n = len(self._history)
        none = sum(p.get(NONE, 1.0) for p in self._history) / n
        if none >= config.NONE_SUPPRESS:
            return {name: 0.0 for name in self._learned}
        return {name: min(1.0, sum(p.get(name, 0.0) for p in self._history) / n) for name in self._learned}
