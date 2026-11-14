# OWNER: P1
"""Calibrator state machine, full and quick (docs/SPEC.md 6.5). Steps advance on timers; no clicks."""
import numpy as np

from helm import config
from helm.contracts import AXES, BLENDSHAPE_NAMES, N_BLEND, Calibration, FrameFeatures, Progress

# step name, seconds, prompt, what it measures: ("neutral",) | ("range", axis, sign) | ("expr", blendshape)
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
    ("smile_left", config.CALIB_EXPRESSION_S, "Smile with the left side of your mouth, three times",
     ("expr", "mouthSmileLeft")),
    ("smile_right", config.CALIB_EXPRESSION_S, "Smile with the right side of your mouth, three times",
     ("expr", "mouthSmileRight")),
    ("pucker", config.CALIB_EXPRESSION_S, "Pucker your lips like a kiss, three times", ("expr", "mouthPucker")),
)
_QUICK_STEPS = (("neutral", config.CALIB_NEUTRAL_QUICK_S, _NEUTRAL[2], ("neutral",)),)
_DIRECTION_WORD = {("yaw", -1): "left", ("yaw", 1): "right", ("pitch", 1): "up", ("pitch", -1): "down"}
_NO_FACE_PROMPT = "I can't see your face. Look at the screen"


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
        name, duration, _, _ = self._steps[self._i]
        if self._elapsed >= duration:
            self._finish_step()
            self._done_s += duration
            self._i += 1
            self._elapsed = 0.0
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
        name, duration, step_prompt, _ = self._steps[self._i]
        if prompt is None:
            prompt = step_prompt if not self._prompt_note else f"{self._prompt_note} {step_prompt}"
        return Progress(active=True, step=name, prompt=prompt, progress=min(self._elapsed / duration, 1.0),
                        overall=min((self._done_s + self._elapsed) / self._total_s, 1.0))

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
            blend_name = measure[1]
            k = BLENDSHAPE_NAMES.index(blend_name)
            peaks = top_peaks(np.array([f.blend[k] for f in frames]), np.array([t for t, _ in self._samples]))
            if not peaks:
                return
            median_peak = float(np.median(peaks))
            self._blend_peak[blend_name] = median_peak
            neutral = float(self._blend_neutral[k])
            if (len(peaks) == 3 and min(peaks) >= config.RELIABLE_MIN_PEAK_RATIO * median_peak
                    and median_peak - neutral >= config.RELIABLE_MIN_PEAK_ABOVE_NEUTRAL):
                self._reliable.append(blend_name)
