# OWNER: P3
"""FatigueTracker: lowers a gesture's thresholds as it weakens (docs/SPEC.md 6.12)."""
import statistics

from helm import config


class _Gesture:
    def __init__(self) -> None:
        self.first_t: float | None = None          # time of the first attempt: the baseline minute starts here
        self.baseline: list[float] = []            # attempt peaks in the first minute
        self.recent: list[tuple[float, float]] = []   # (t, peak) after the first minute, last FATIGUE_WINDOW_S
        self.open = False
        self.peak = 0.0
        self.scale = 1.0


class FatigueTracker:
    """Per gesture, the peak of each attempt (level rising past FATIGUE_ATTEMPT_LEVEL until it falls back below
    half of that). When the median recent peak drops below FATIGUE_DROP_RATIO of the first minute's median,
    the gesture's thresholds are scaled by that ratio, never below FATIGUE_MIN_SCALE. Recovers on its own."""

    def __init__(self) -> None:
        self._g: dict[str, _Gesture] = {}

    def update(self, act: dict[str, float], t_s: float) -> dict[str, float]:
        """Gesture -> threshold scale in [0.5, 1.0]."""
        scales: dict[str, float] = {}
        for name, level in act.items():
            g = self._g.get(name)
            if g is None:
                g = self._g[name] = _Gesture()
            if not g.open and level >= config.FATIGUE_ATTEMPT_LEVEL:
                g.open, g.peak = True, level
            elif g.open:
                g.peak = max(g.peak, level)
                if level < 0.5 * config.FATIGUE_ATTEMPT_LEVEL:
                    g.open = False
                    self._close(g, t_s)
            scales[name] = g.scale
        return scales

    def notices(self) -> list[str]:
        """For example "brow_raise is weakening; threshold lowered"."""
        return [f"{name} is weakening; threshold lowered to {round(g.scale * 100)}%"
                for name, g in sorted(self._g.copy().items()) if g.scale < 1.0]   # copy: read off-thread too

    def _close(self, g: _Gesture, t_s: float) -> None:
        if g.first_t is None:
            g.first_t = t_s
        if t_s - g.first_t < config.FATIGUE_BASELINE_S:
            g.baseline.append(g.peak)
            return
        g.recent.append((t_s, g.peak))
        g.recent = [(t, p) for t, p in g.recent if t > t_s - config.FATIGUE_WINDOW_S]
        if len(g.baseline) < config.FATIGUE_MIN_PEAKS or len(g.recent) < config.FATIGUE_MIN_PEAKS:
            return
        ratio = statistics.median(p for _, p in g.recent) / statistics.median(g.baseline)
        g.scale = max(config.FATIGUE_MIN_SCALE, ratio) if ratio < config.FATIGUE_DROP_RATIO else 1.0
