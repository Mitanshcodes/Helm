# OWNER: P1
"""Calibrator state machine, full and quick (docs/SPEC.md 6.5). Steps advance on timers; no clicks."""
import numpy as np

from helm import config
from helm.contracts import AXES, BLENDSHAPE_NAMES, N_BLEND, Calibration, FrameFeatures, Progress

# step name, seconds, prompt, what it measures: ("neutral",) | ("range", axis, sign) | ("expr", blendshape, ...)
# An "expr" step with several blendshapes is one gesture read as their max (a smile is either side).
_NEUTRAL = ("neutral", config.CALIB_NEUTRAL_S, "Look at the screen and relax your face", ("neutral",))
_FULL_STEPS = (
    _NEUTRAL,
    ("yaw_left", config.CALIB_RANGE_S, "Turn your head left as far as is comfortable, and hold", ("range", "yaw", -1)),
    ("yaw_right", config.CALIB_RANGE_S, "Turn your head right as far as is comfortable, and hold", ("range", "yaw", 1)),
    ("pitch_up", config.CALIB_RANGE_S, "Tilt your chin up as far as is comfortable, and hold", ("range", "pitch", 1)),
    ("pitch_down", config.CALIB_RANGE_S, "Tilt your chin down as far as is comfortable, and hold",
     ("range", "pitch", -1)),
    ("brow_raise", config.CALIB_EXPRESSION_S, "Raise your eyebrows, three times", ("expr", "browInnerUp")),
    ("jaw_open", config.CALIB_EXPRESSION_S, "Open your mouth wide, three times", ("expr", "jawOpen")),
    ("smile", config.CALIB_EXPRESSION_S, "Smile wide, three times", ("expr", "mouthSmileLeft", "mouthSmileRight")),
    ("pucker", config.CALIB_EXPRESSION_S, "Pucker your lips like a kiss, three times", ("expr", "mouthPucker")),
)
_QUICK_STEPS = (("neutral", config.CALIB_NEUTRAL_QUICK_S, _NEUTRAL[2], ("neutral",)),)
_DIRECTION_WORD = {("yaw", -1): "left", ("yaw", 1): "right", ("pitch", 1): "up", ("pitch", -1): "down"}
_NO_FACE_PROMPT = "I can't see your face. Look at the screen"


def _indices(measure: tuple) -> list[int]:
    return [BLENDSHAPE_NAMES.index(n) for n in measure[1:]]


def default_calibration(player: str, mode: str = "default") -> Calibration:
    """Neutral 0, 15 degrees each way, no measured expressions."""
    r = config.DEFAULT_RANGE_DEG
    reliable = list(config.ASSUMED_RELIABLE)
    if mode == "quick":
        reliable += list(config.QUICK_ASSUMED_RELIABLE)
    return Calibration(player=player, mode=mode, neutral={a: 0.0 for a in AXES}, range={a: (r, r) for a in AXES},
                       blend_neutral=[0.0] * N_BLEND, blend_peak={}, reliable=reliable)


def top_peaks(values: np.ndarray, times: np.ndarray, n: int = 3,
              separation_s: float = config.CALIB_PEAK_SEPARATION_S) -> list[float]:
    """The n highest local maxima that are at least separation_s apart, highest first. Fewer if the signal has fewer."""
    v = np.asarray(values, np.float64)
    t = np.asarray(times, np.float64)
    if len(v) == 0:
        return []
    padded = np.concatenate([[-np.inf], v, [-np.inf]])
    is_peak = (padded[1:-1] >= padded[:-2]) & (padded[1:-1] > padded[2:])
    chosen: list[int] = []
    for i in sorted(np.flatnonzero(is_peak), key=lambda i: -v[i]):
        if all(abs(t[i] - t[j]) >= separation_s for j in chosen):
            chosen.append(i)
            if len(chosen) == n:
                break
    return [float(v[i]) for i in chosen]


class Calibrator:
    def __init__(self, player: str, mode: str = "full"):   # "full" | "quick"
        if mode not in ("full", "quick"):
            raise ValueError(f"calibration mode must be full or quick, not {mode!r}")
        self.player = player
        self.mode = mode
        self.notes: list[str] = []                 # e.g. small ranges that were raised to the minimum
        self._steps = _QUICK_STEPS if mode == "quick" else _FULL_STEPS
        self._total_s = sum(s[1] for s in self._steps)
        self._i = 0
        self._elapsed = 0.0                        # face-visible seconds in the current step
        self._held = 0.0                           # range steps: seconds spent turned past CALIB_RANGE_MOVED_DEG
        self._reps: list[float] = []               # expression steps: peak (above neutral) of each repetition
        self._in_rep = False
        self._rep_peak = 0.0
        self._done_s = 0.0                         # seconds of completed steps
        self._last_t: float | None = None
        self._samples: list[tuple[float, FrameFeatures]] = []
        self._neutral = {a: 0.0 for a in AXES}
        self._range = {a: [config.DEFAULT_RANGE_DEG, config.DEFAULT_RANGE_DEG] for a in AXES}
        self._blend_neutral = np.zeros(N_BLEND, np.float32)
        self._blend_peak: dict[str, float] = {}
        self._reliable: list[str] = []
        self._prompt_note = ""
        self._done = False

    def feed(self, f: FrameFeatures, t_s: float) -> Progress:
        if self._done:
            return self._progress()
        dt = 0.0 if self._last_t is None else min(max(t_s - self._last_t, 0.0), config.CALIB_MAX_DT_S)
        self._last_t = t_s
        if not f.face:                             # the timer pauses while the face is lost
            return self._progress(prompt=_NO_FACE_PROMPT)

        self._samples.append((t_s, f))
        self._elapsed += dt
        name, duration, _, measure = self._steps[self._i]
        if measure[0] == "range":                  # wait for the turn itself, not just the clock
            _, axis, sign = measure
            if sign * (getattr(f, axis) - self._neutral[axis]) >= config.CALIB_RANGE_MOVED_DEG:
                self._held += dt
            finished = ((self._elapsed >= duration and self._held >= config.CALIB_RANGE_HOLD_S)
                        or self._elapsed >= config.CALIB_RANGE_TIMEOUT_S)
        elif measure[0] == "expr":                 # count repetitions live; end at three, or give up
            level = max(float(f.blend[k] - self._blend_neutral[k]) for k in _indices(measure))
            if not self._in_rep and level >= config.CALIB_REP_LEVEL:
                self._in_rep, self._rep_peak = True, level
            elif self._in_rep:
                self._rep_peak = max(self._rep_peak, level)
                if level < 0.5 * config.CALIB_REP_LEVEL:
                    self._in_rep = False
                    self._reps.append(self._rep_peak)
            finished = len(self._reps) >= 3 or self._elapsed >= config.CALIB_EXPRESSION_MAX_S
        else:
            finished = self._elapsed >= duration
        if finished:
            self._finish_step()
            self._done_s += duration
            self._i += 1
            self._elapsed = 0.0
            self._held = 0.0
            self._reps, self._in_rep, self._rep_peak = [], False, 0.0
            self._samples = []
            if self._i == len(self._steps):
                self._done = True
        return self._progress()

    def result(self) -> Calibration:
        """Valid once Progress.done is True."""
        reliable = list(config.ASSUMED_RELIABLE)
        if self.mode == "quick":
            reliable += list(config.QUICK_ASSUMED_RELIABLE)
        reliable += [n for n in self._reliable if n not in reliable]
        return Calibration(
            player=self.player,
            mode=self.mode,
            neutral={a: float(v) for a, v in self._neutral.items()},
            range={a: (float(lo), float(hi)) for a, (lo, hi) in self._range.items()},
            blend_neutral=[float(v) for v in self._blend_neutral],
            blend_peak=dict(self._blend_peak),
            reliable=reliable,
        )

    # ------------------------------------------------------------------ internals

    def _progress(self, prompt: str | None = None) -> Progress:
        if self._done:
            text = "Calibration complete"
            if self.notes:
                text += ". " + " ".join(self.notes)
            return Progress(active=False, step="done", prompt=text, progress=1.0, overall=1.0, done=True)
        name, duration, step_prompt, measure = self._steps[self._i]
        step_progress = min(self._elapsed / duration, 1.0)
        if measure[0] == "expr":                   # the bar fills with each repetition
            step_progress = len(self._reps) / 3
            if prompt is None and self._reps:
                prompt = f"{step_prompt} ({len(self._reps)} of 3)"
            elif prompt is None and self._elapsed >= 4.0:
                prompt = f"A bit bigger: {step_prompt[0].lower()}{step_prompt[1:]}"
        if measure[0] == "range":                  # the bar fills only while the head is held turned
            step_progress = min(step_progress, self._held / config.CALIB_RANGE_HOLD_S)
            if prompt is None and self._elapsed >= duration:
                prompt = f"Turn a little further {_DIRECTION_WORD[measure[1:]]}, and hold"
        if prompt is None:
            prompt = step_prompt if not self._prompt_note else f"{self._prompt_note} {step_prompt}"
        return Progress(active=True, step=name, prompt=prompt, progress=step_progress,
                        overall=min((self._done_s + min(self._elapsed, duration)) / self._total_s, 0.99))

    def _finish_step(self) -> None:
        name, _, _, measure = self._steps[self._i]
        frames = [f for _, f in self._samples]
        self._prompt_note = ""
        if not frames:
            return
        if measure[0] == "neutral":
            for a in AXES:
                self._neutral[a] = float(np.median([getattr(f, a) for f in frames]))
            self._blend_neutral = np.median(np.stack([f.blend for f in frames]), axis=0).astype(np.float32)
        elif measure[0] == "range":
            _, axis, sign = measure
            displacement = np.array([sign * (getattr(f, axis) - self._neutral[axis]) for f in frames])
            limit = float(np.percentile(np.maximum(displacement, 0.0), 95))
            if limit < config.MIN_RANGE_DEG:
                limit = config.MIN_RANGE_DEG
                word = _DIRECTION_WORD[(axis, sign)]
                self.notes.append(f"Turning {word} was small, so it uses a minimum range.")
                self._prompt_note = f"That was a small {word} movement; that's fine."
            self._range[axis][1 if sign > 0 else 0] = limit
        elif measure[0] == "expr":
            names = list(measure[1:])
            times = np.array([t for t, _ in self._samples])
            for name, k in zip(names, _indices(measure)):   # each source's own peak scales its expression level
                own = top_peaks(np.array([f.blend[k] for f in frames]), times)
                if own:
                    self._blend_peak[name] = float(np.median(own))
            # Reliable: at least two clear repetitions, of similar strength, well above the relaxed face.
            reps = sorted(self._reps, reverse=True)[:3]
            if len(reps) >= config.RELIABLE_MIN_REPS:
                median_peak = float(np.median(reps))
                if (median_peak >= config.RELIABLE_MIN_PEAK_ABOVE_NEUTRAL
                        and min(reps) >= config.RELIABLE_MIN_PEAK_RATIO * median_peak):
                    self._reliable.extend(names)
                    return
            word = self._steps[self._i][0].replace("_", " ")
            self.notes.append(f"{word.capitalize()} was hard to read; it can still be mapped by hand.")
