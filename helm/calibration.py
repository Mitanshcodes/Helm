# OWNER: P1
"""Calibrator state machine, full and quick (docs/SPEC.md 6.5). Bootstrap stub: finishes on the first frame."""
from helm import config
from helm.contracts import AXES, N_BLEND, Calibration, FrameFeatures, Progress


def default_calibration(player: str, mode: str = "default") -> Calibration:
    """Neutral 0, 15 degrees each way, no measured expressions."""
    r = config.DEFAULT_RANGE_DEG
    return Calibration(player=player, mode=mode, neutral={a: 0.0 for a in AXES}, range={a: (r, r) for a in AXES},
                       blend_neutral=[0.0] * N_BLEND, blend_peak={}, reliable=[])


class Calibrator:
    def __init__(self, player: str, mode: str = "full"):   # "full" | "quick"
        self.player = player
        self.mode = mode

    def feed(self, f: FrameFeatures, t_s: float) -> Progress:
        # TODO(P1): timed, auto-advancing steps: neutral, yaw_left/right, pitch_up/down, then the five
        # expression checks. Frames with face=False pause the timer. Quick mode stops after neutral.
        return Progress(active=False, step="done", prompt="Calibration complete", progress=1.0, overall=1.0, done=True)

    def result(self) -> Calibration:
        """Valid once Progress.done is True."""
        return default_calibration(self.player, self.mode)
