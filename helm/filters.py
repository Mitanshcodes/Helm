# OWNER: P1
"""One Euro filter, axis shaping and the Normalizer with quick-mode auto-range and drift (docs/SPEC.md 6.4)."""
import math
from collections import deque

import numpy as np

from helm import config
from helm.contracts import AXES, BLENDSHAPE_NAMES, N_BLEND, Calibration, FrameFeatures, Signals


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


class OneEuro:
    """Casiez et al. 2012: a low-pass filter whose cutoff rises with speed (less jitter at rest, less lag in motion)."""

    def __init__(self, min_cutoff: float = config.ONE_EURO_MIN_CUTOFF, beta: float = config.ONE_EURO_BETA,
                 d_cutoff: float = config.ONE_EURO_D_CUTOFF):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x: float, t_s: float) -> float:
        if self._t is None:
            self._t, self._x, self._dx = t_s, x, 0.0
            return x
        dt = t_s - self._t
        if dt <= 0.0:                                  # same or older timestamp: nothing new to filter
            return self._x
        dx = (x - self._x) / dt
        self._dx += self._alpha(self.d_cutoff, dt) * (dx - self._dx)
        cutoff = self.min_cutoff + self.beta * abs(self._dx)
        self._x += self._alpha(cutoff, dt) * (x - self._x)
        self._t = t_s
        return self._x

    def reset(self) -> None:
        self._t: float | None = None
        self._x = 0.0
        self._dx = 0.0


def shape_axis(u: float, deadzone: float = config.AXIS_DEADZONE, gamma: float = config.AXIS_GAMMA,
               invert: bool = False) -> float:
    """Dead zone, rescale, response curve, clamp to [-1, 1]. Used by P2's Mapper."""
    u = _clamp(float(u))
    a = abs(u)
    if a < deadzone or deadzone >= 1.0:
        return 0.0
    v = math.copysign(((a - deadzone) / (1.0 - deadzone)) ** gamma, u)
    v = _clamp(v)
    return -v if invert else v


class Normalizer:
    """Raw FrameFeatures -> Signals: neutral removed, scaled to the player's range, One Euro filtered."""

    def __init__(self, calib: Calibration | None = None):
        self._filters = {a: OneEuro() for a in AXES}
        self._excursions = {(a, side): deque(maxlen=config.AUTO_RANGE_SAMPLES) for a in AXES for side in (0, 1)}
        self._last_t: float | None = None
        self._calib: Calibration | None = None
        self.gain = {a: 1.0 for a in AXES}             # steering sensitivity per head axis, from the mapping
        self.set_calibration(calib)

    def set_gains(self, gains: dict[str, float]) -> None:
        """Sensitivity per head axis: the calibrated range is divided by it, so 2.0 reaches full lock at half the
        turn and 0.5 needs twice the turn. Clamped to STEER_GAIN_MIN..MAX; axes not named go back to 1.0."""
        self.gain = {a: min(max(float(gains.get(a, 1.0)), config.STEER_GAIN_MIN), config.STEER_GAIN_MAX) for a in AXES}

    def effective_range(self) -> dict[str, tuple[float, float]]:
        """Degrees of head movement that give full lock each way, sensitivity included."""
        return {a: (self.range[a][0] / self.gain[a], self.range[a][1] / self.gain[a]) for a in AXES}

    def set_calibration(self, calib: Calibration | None) -> None:
        r = config.DEFAULT_RANGE_DEG
        self._calib = calib
        self._calib_neutral = {a: float(calib.neutral.get(a, 0.0)) if calib else 0.0 for a in AXES}
        self.neutral = dict(self._calib_neutral)       # moves with drift; the calibration itself is not touched
        self.range = {a: [float(v) for v in calib.range.get(a, (r, r))] if calib else [r, r] for a in AXES}
        self._auto_range = bool(calib) and calib.mode == "quick"
        bn = np.asarray(calib.blend_neutral if calib else np.zeros(N_BLEND), np.float32)
        if bn.shape != (N_BLEND,):
            bn = np.zeros(N_BLEND, np.float32)
        peak = bn + config.DEFAULT_PEAK_ABOVE_NEUTRAL
        for name, value in (calib.blend_peak.items() if calib else ()):
            if name in BLENDSHAPE_NAMES:
                peak[BLENDSHAPE_NAMES.index(name)] = value
        self._blend_neutral = bn
        self._blend_span = np.maximum(peak - bn, config.MIN_EXPRESSION_SPAN).astype(np.float32)
        for q in self._excursions.values():
            q.clear()
        for f in self._filters.values():
            f.reset()

    def update(self, f: FrameFeatures, breath: float = 0.0, idle: bool = False) -> Signals:
        breath = _clamp(float(breath))
        t_s = f.t_capture_ns / 1e9
        dt = 0.0 if self._last_t is None else min(max(t_s - self._last_t, 0.0), 0.1)
        self._last_t = t_s

        if not f.face:
            for flt in self._filters.values():
                flt.reset()
            axes = {a: 0.0 for a in AXES}
            delta = np.zeros(len(self._blend_neutral) + len(AXES) + 1, np.float32)
            delta[-1] = breath
            return Signals(seq=f.seq, t_capture_ns=f.t_capture_ns, t_infer_ns=f.t_infer_ns, face=False, axes=axes,
                           expr=np.zeros(N_BLEND, np.float32), delta=delta, breath=breath)

        raw = {"yaw": float(f.yaw), "pitch": float(f.pitch), "roll": float(f.roll)}
        axes: dict[str, float] = {}
        for a in AXES:
            d = raw[a] - self.neutral[a]
            side = 1 if d >= 0.0 else 0
            if self._auto_range:
                self._widen(a, side, abs(d))
            u = d * self.gain[a] / self.range[a][side]
            axes[a] = _clamp(self._filters[a](u, t_s))
            if idle and dt > 0.0:
                self._drift(a, raw[a], dt)

        blend = np.asarray(f.blend, np.float32)
        blend_delta = blend - self._blend_neutral
        expr = np.clip(blend_delta / self._blend_span, 0.0, 1.0).astype(np.float32)
        delta = np.concatenate([blend_delta, [axes[a] for a in AXES], [breath]]).astype(np.float32)
        return Signals(seq=f.seq, t_capture_ns=f.t_capture_ns, t_infer_ns=f.t_infer_ns, face=True,
                       axes=axes, expr=expr, delta=delta, breath=breath)

    def _widen(self, a: str, side: int, d: float) -> None:
        """Quick mode: past a limit, widen it to the 95th percentile of large excursions. Never shrink."""
        limit = self.range[a][side]
        q = self._excursions[(a, side)]
        if d > 0.5 * limit:                            # only real turns count, not time spent near neutral
            q.append(d)
        if d > limit and len(q) >= config.AUTO_RANGE_MIN_SAMPLES:
            self.range[a][side] = max(limit, float(np.percentile(q, 95)))

    def _drift(self, a: str, x: float, dt: float) -> None:
        """While idle, neutral follows the raw pose slowly, within a bounded distance of the calibrated neutral."""
        n = self.neutral[a] + (x - self.neutral[a]) * (dt / config.DRIFT_TIME_CONSTANT_S)
        lo = self._calib_neutral[a] - config.DRIFT_MAX_FRACTION * self.range[a][0]
        hi = self._calib_neutral[a] + config.DRIFT_MAX_FRACTION * self.range[a][1]
        self.neutral[a] = min(max(n, lo), hi)
