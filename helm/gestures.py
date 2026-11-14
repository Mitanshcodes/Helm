# OWNER: P3
"""Personal logistic-regression gestures, enrollment and causal activation/release."""
import json
import os

import numpy as np

from helm import config
from helm.contracts import BLENDSHAPE_NAMES, FEATURE_DIM, N_BLEND, Calibration, Progress, Signals

NONE = "none"

def _settings() -> dict:
    """Persist training settings with raw takes so profiles refit consistently."""
    return {"C": config.LEARNED_C, "top": config.LEARNED_FEATURES_PER_CLASS,
            "floor": config.LEARNED_SCALE_FLOOR, "noise_floor": config.LEARNED_NOISE_FLOOR,
            "frames_per_take": config.LEARNED_FRAMES_PER_TAKE, "negative_ratio": config.LEARNED_NEGATIVE_RATIO,
            "radius_percentile": config.LEARNED_RADIUS_PERCENTILE,
            "radius_expansion": config.LEARNED_RADIUS_EXPANSION, "radius_min": config.LEARNED_RADIUS_MIN,
            "radius_separation": config.LEARNED_RADIUS_SEPARATION, "reject": config.LEARNED_REJECT_FACTOR,
            "max_iter": config.LEARNED_MAX_ITER}


class GestureModel:
    """Selected facial deltas, regularized logistic regression, and rejection to "none".

    Refit from the raw takes whenever data changes (well under a second at this size, but still off the
    pipeline thread). fit() swaps in the new classifier in one assignment, so predict() may run meanwhile on
    another thread. Do not add or remove data on a model another thread is fitting: copy() it first.
    """

    def __init__(self) -> None:
        self._takes: dict[str, list[np.ndarray]] = {}
        self._negatives: list[np.ndarray] = []
        self._fitted: _Fitted | None = None
        self._settings = _settings()

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
        other._settings = dict(self._settings)
        return other

    def fit(self) -> dict[str, float]:
        """Classify each held-out take using its median scores; fit preprocessing inside each fold.

        Negative recordings remain separate groups. This is enrollment validation, not a claim about
        command-event recall or false activations during a new session. Publish the fitted snapshot last.
        """
        groups = self._groups()
        fitted = _Fitted(groups, self._settings)
        if fitted.clf is None:
            self._fitted = fitted
            return {}
        accuracy: dict[str, float] = {}
        for name in {label for label, _ in groups}:
            held_out = [i for i, (label, _) in enumerate(groups) if label == name]
            if len(held_out) < 2:                  # nothing left to train this class on if its only take is out
                continue
            hits = 0
            for i in held_out:
                part = _Fitted([g for j, g in enumerate(groups) if j != i], self._settings)
                hits += int(part.classify_take(groups[i][1]) == name)
            accuracy[name] = hits / len(held_out)
        self._fitted = fitted
        return accuracy

    def predict(self, delta: np.ndarray) -> dict[str, float]:
        """Class probabilities, including "none"."""
        probs = {name: 0.0 for name in self._takes}
        probs[NONE] = 1.0
        fitted = self._fitted                      # read once: fit() may replace it from another thread
        if fitted is None or fitted.clf is None:
            return probs
        x = np.asarray(delta, np.float32)
        if x.shape != (FEATURE_DIM,) or not np.isfinite(x).all():
            return probs
        scores = fitted.probabilities(x[None, :])[0]
        if fitted.classes[int(np.argmax(scores))] not in probs:
            return probs
        probs[NONE] = 0.0
        for name, p in zip(fitted.classes, scores):
            # A copied model may still use its old snapshot while a worker fits a deletion.
            probs[name if name in probs else NONE] += float(p)
        return probs

    @property
    def names(self) -> list[str]:
        return sorted(self._takes)

    def save(self, path: str) -> None:
        """One .npz with the raw takes and negatives (the model refits on load). Written atomically."""
        groups = self._groups()
        frames = np.concatenate([g for _, g in groups]) if groups else np.zeros((0, FEATURE_DIM), np.float32)
        labels = np.array([label for label, g in groups for _ in range(len(g))], dtype=str)
        group_ids = np.concatenate([np.full(len(g), i, np.int32) for i, (_, g) in enumerate(groups)]) \
            if groups else np.zeros(0, np.int32)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            np.savez(fh, frames=frames, labels=labels, groups=group_ids, model_version=np.array(2),
                     settings_json=np.array(json.dumps(self._settings)))
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str) -> "GestureModel":
        model = cls()
        with np.load(path, allow_pickle=False) as data:
            if "model_version" in data and int(data["model_version"]) != 2:
                raise ValueError("Unsupported learned-gesture model version")
            if "settings_json" in data:
                settings = json.loads(str(data["settings_json"]))
                if set(settings) != set(model._settings) or any(
                        not isinstance(v, (int, float)) or not np.isfinite(v) or v <= 0
                        for v in settings.values()):
                    raise ValueError("Invalid learned-gesture training settings")
                model._settings = settings
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

    def _groups(self) -> list[tuple[str, np.ndarray]]:
        """Preserve each take and negative recording as a validation group."""
        groups = [(name, take) for name in sorted(self._takes) for take in self._takes[name]]
        if self._negatives:
            groups += [(NONE, neg) for neg in self._negatives]
        return groups


class _Fitted:
    """Immutable-on-publication training snapshot. Only indices 1..51 are classifier candidates."""

    def __init__(self, groups: list[tuple[str, np.ndarray]], settings: dict):
        self.clf = None
        self.classes: list[str] = []
        labels = sorted({label for label, _ in groups})
        if len(labels) < 2 or NONE not in labels:
            return
        positive = [(label, _sample(g, int(settings["frames_per_take"]))) for label, g in groups if label != NONE]
        count = max(sum(len(g) for label, g in positive if label == name) for name in labels if name != NONE)
        negative = _sample(np.concatenate([g for label, g in groups if label == NONE]),
                           int(count * settings["negative_ratio"]))
        sampled = positive + [(NONE, negative)]
        x = np.concatenate([g for _, g in sampled])
        y = np.array([label for label, g in sampled for _ in range(len(g))])
        null = x[y == NONE]
        noise = np.maximum(np.std(null, axis=0), settings["noise_floor"])
        selected = []
        candidates = np.arange(1, N_BLEND)
        for label in labels:
            if label == NONE:
                continue
            pos = x[y == label]
            effect = np.abs(np.median(pos, axis=0) - np.median(null, axis=0)) / (noise + np.std(pos, axis=0))
            selected.extend(candidates[np.argsort(effect[candidates])[-int(settings["top"]):]])
        self.indices = np.unique(selected)
        self.mean = x[:, self.indices].mean(axis=0)
        self.scale = np.maximum(x[:, self.indices].std(axis=0), settings["floor"])
        z = (x[:, self.indices] - self.mean) / self.scale
        from sklearn.linear_model import LogisticRegression

        self.clf = LogisticRegression(C=settings["C"], class_weight="balanced",
                                      max_iter=int(settings["max_iter"]), solver="lbfgs").fit(z, y)
        self.classes = [str(c) for c in self.clf.classes_]
        self.none_index = self.classes.index(NONE)
        self.centers = np.array([z[y == label].mean(axis=0) for label in self.classes])
        self.radii = np.array([
            max(np.percentile(np.linalg.norm(z[y == label] - self.centers[i], axis=1),
                              settings["radius_percentile"]) * settings["radius_expansion"],
                settings["radius_min"],
                np.linalg.norm(self.centers[i] - self.centers[self.none_index]) * settings["radius_separation"])
            for i, label in enumerate(self.classes)])
        self.reject = settings["reject"]

    def probabilities(self, frames: np.ndarray) -> np.ndarray:
        z = (frames[:, self.indices] - self.mean) / self.scale
        p = self.clf.predict_proba(z)
        winner = np.argmax(p, axis=1)
        distance = np.linalg.norm(z - self.centers[winner], axis=1)
        rejected = (winner != self.none_index) & (distance > self.radii[winner] * self.reject)
        p[rejected] = 0.0
        p[rejected, self.none_index] = 1.0
        return p

    def classify_take(self, frames: np.ndarray) -> str | None:
        if self.clf is None:
            return None
        return self.classes[int(np.argmax(np.median(self.probabilities(frames), axis=0)))]


def _sample(frames: np.ndarray, count: int) -> np.ndarray:
    indices = np.unique(np.linspace(0, len(frames) - 1, min(len(frames), count)).round().astype(int))
    return frames[indices]


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
        self._definitions = {name: dict(gesture_defs[name]) for name in self._learned}
        self._gate = _LearnedGate(self._definitions)
        self._snapshot = getattr(model, "_fitted", None)

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
            self._gate.reset()
            return {name: 0.0 for name in self._learned}
        snapshot = getattr(self._model, "_fitted", None)
        if snapshot is not self._snapshot:
            self._gate.reset()
            self._snapshot = snapshot
        return self._gate.update(self._model.predict(s.delta), s.t_infer_ns / 1e9)


class _LearnedGate:
    """Qualified hold levels for the Mapper. One winner; sustained release before switching.

    The Mapper consumes these binary levels without a second debounce. Keeping the level high until
    release preserves tap/hold/toggle mappings; this layer does not send controller events itself.
    """

    def __init__(self, definitions: dict):
        self.definitions = definitions
        self.reset()

    def reset(self) -> None:
        self.active: str | None = None
        self.candidate: str | None = None
        self.since: float | None = None
        self.release_since: float | None = None
        self.last_t: float | None = None

    def update(self, scores: dict[str, float], t_s: float) -> dict[str, float]:
        levels = {name: 0.0 for name in self.definitions}
        if not scores or not all(np.isfinite(p) for p in scores.values()):
            self.reset()
            return levels
        if self.last_t is not None and (t_s <= self.last_t or t_s - self.last_t > config.LEARNED_MAX_GAP_S):
            self.reset()
        self.last_t = t_s
        if self.active is not None:
            definition = self.definitions[self.active]
            off = definition.get("off", config.LEARNED_OFF)
            if scores.get(self.active, 0.0) < off:
                if self.release_since is None:
                    self.release_since = t_s
                if t_s - self.release_since >= config.LEARNED_RELEASE_S - 1e-9:
                    self.active = self.candidate = None
                    self.since = self.release_since = None
                    return levels
            else:
                self.release_since = None
            levels[self.active] = 1.0
            return levels
        winner = max(scores, key=lambda name: (scores[name], name == NONE))
        on = max(config.LEARNED_ON, self.definitions.get(winner, {}).get("on", config.LEARNED_ON))
        if winner not in levels or scores[winner] < on:
            self.candidate = None
            self.since = None
            return levels
        if winner != self.candidate:
            self.candidate, self.since = winner, t_s
        hold_s = max(config.LEARNED_CONFIRM_S, self.definitions[winner].get("min_hold_ms", 0) / 1000)
        if t_s - self.since >= hold_s - 1e-9:
            self.active = winner
            levels[winner] = 1.0
        return levels
