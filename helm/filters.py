# OWNER: P1
"""One Euro filter, axis shaping and the Normalizer (docs/SPEC.md 6.4). Bootstrap stubs: pass-through."""
import numpy as np

from helm import config
from helm.contracts import AXES, N_BLEND, Calibration, FrameFeatures, Signals


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


class OneEuro:
    def __init__(self, min_cutoff: float = config.ONE_EURO_MIN_CUTOFF, beta: float = config.ONE_EURO_BETA,
                 d_cutoff: float = config.ONE_EURO_D_CUTOFF):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff

    def __call__(self, x: float, t_s: float) -> float:
        # TODO(P1): One Euro filter. The stub passes the value through.
        return x

    def reset(self) -> None:
        pass


def shape_axis(u: float, deadzone: float = config.AXIS_DEADZONE, gamma: float = config.AXIS_GAMMA,
               invert: bool = False) -> float:
    """Dead zone, rescale, response curve, clamp to [-1, 1]. Used by P2's Mapper."""
    # TODO(P1): 0 if |u| < d, else sign(u) * ((|u| - d) / (1 - d)) ** gamma. The stub only clamps.
    u = _clamp(u)
    return -u if invert else u


class Normalizer:
    def __init__(self, calib: Calibration | None = None):
        self._calib = calib

    def set_calibration(self, calib: Calibration) -> None:
        self._calib = calib

    def update(self, f: FrameFeatures, breath: float = 0.0, idle: bool = False) -> Signals:
        # TODO(P1): use the calibration (neutral, per-direction range, blend neutral and peak), One Euro per
        # axis, quick-mode auto-range, drift while idle. The stub uses the uncalibrated defaults only.
        if f.face:
            raw = {"yaw": f.yaw, "pitch": f.pitch, "roll": f.roll}
            axes = {a: _clamp(float(raw[a]) / config.DEFAULT_RANGE_DEG) for a in AXES}
            blend_delta = np.asarray(f.blend, np.float32)
        else:
            axes = {a: 0.0 for a in AXES}
            blend_delta = np.zeros(N_BLEND, np.float32)
        expr = np.clip(blend_delta, 0.0, 1.0)
        delta = np.concatenate([blend_delta, [axes[a] for a in AXES], [breath]]).astype(np.float32)
        return Signals(seq=f.seq, t_capture_ns=f.t_capture_ns, t_infer_ns=f.t_infer_ns, face=f.face,
                       axes=axes, expr=expr, delta=delta, breath=float(breath))
