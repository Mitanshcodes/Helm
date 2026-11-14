# OWNER: P3
"""Bootstrap checks for adapt.py. TODO(P3): a weakening gesture lowers its scale, never below 0.5."""
from helm.adapt import FatigueTracker


def test_scales_stay_in_range():
    tracker = FatigueTracker()
    scales = tracker.update({"brow_raise": 0.7, "smile": 0.0}, t_s=1.0)
    assert set(scales) == {"brow_raise", "smile"}
    assert all(0.5 <= v <= 1.0 for v in scales.values())
    assert isinstance(tracker.notices(), list)
