# OWNER: P3
"""adapt.py: a weakening gesture lowers its threshold scale, never below 0.5, and recovers."""
import pytest

from helm import config
from helm.adapt import FatigueTracker


def press(tracker: FatigueTracker, t: float, peak: float, name: str = "brow_raise") -> dict[str, float]:
    """One attempt: rise to `peak` and relax, 0.5 s in all, at 30 Hz."""
    scales = {}
    for i in range(15):
        level = peak if i < 8 else 0.0
        scales = tracker.update({name: level, "smile": 0.0}, t + i / 30)
    return scales


def test_scales_stay_in_range():
    tracker = FatigueTracker()
    scales = tracker.update({"brow_raise": 0.7, "smile": 0.0}, t_s=1.0)
    assert set(scales) == {"brow_raise", "smile"}
    assert all(0.5 <= v <= 1.0 for v in scales.values())
    assert tracker.notices() == []


def test_weakening_gesture_lowers_its_threshold():
    tracker = FatigueTracker()
    t = 0.0
    for _ in range(6):                                  # first minute: strong presses
        press(tracker, t, 0.9)
        t += 10.0
    for _ in range(4):                                  # later: peaks fall to 2/3 of the baseline
        scales = press(tracker, t, 0.6)
        t += 10.0
    assert scales["brow_raise"] == pytest.approx(0.6 / 0.9)
    assert scales["smile"] == 1.0
    assert tracker.notices() == ["brow_raise is weakening; threshold lowered to 67%"]

    for _ in range(4):                                  # much weaker: clamped to the minimum
        scales = press(tracker, t, 0.3)
        t += 10.0
    assert scales["brow_raise"] == config.FATIGUE_MIN_SCALE

    for _ in range(12):                                 # rested: back to full strength, scale recovers
        scales = press(tracker, t, 0.9)
        t += 10.0
    assert scales["brow_raise"] == 1.0 and tracker.notices() == []


def test_small_drop_or_too_few_peaks_change_nothing():
    tracker = FatigueTracker()
    t = 0.0
    for _ in range(6):
        press(tracker, t, 0.9)
        t += 10.0
    scales = press(tracker, t, 0.4)                    # one weak press is not a trend
    assert scales["brow_raise"] == 1.0
    for _ in range(4):
        scales = press(tracker, t, 0.8)                # 89% of the baseline: within normal variation
        t += 10.0
    assert scales["brow_raise"] == 1.0
