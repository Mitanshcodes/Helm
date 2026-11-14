# OWNER: P3
"""FatigueTracker: lowers a gesture's thresholds as it weakens (docs/SPEC.md 6.12). Bootstrap stub: scale 1.0."""


class FatigueTracker:
    def update(self, act: dict[str, float], t_s: float) -> dict[str, float]:
        """Gesture -> threshold scale in [0.5, 1.0]."""
        # TODO(P3): rolling 2 minutes of per-activation peaks; scale when the recent median drops below
        # 75% of the first minute's, never below 0.5.
        return {name: 1.0 for name in act}

    def notices(self) -> list[str]:
        """For example "brow_raise is weakening; threshold lowered"."""
        return []
