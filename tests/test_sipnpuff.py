# OWNER: P2
"""Bootstrap checks for sipnpuff.py: with no device nothing changes. TODO(P2): event detector on (t_ms, mv) pairs."""
import pytest

from helm import config
from helm.sipnpuff import BreathDetector, SipPuff


@pytest.mark.parametrize("pressure,kind", [
    (400, "soft_puff"), (650, "hard_puff"),
    (-200, "soft_sip"), (-325, "hard_sip"),
])
def test_pressure_trace_emits_once_on_release(pressure, kind):
    detector = BreathDetector(1250, 1000, 500)
    for timestamp in range(0, 201, 10):
        assert detector.feed(timestamp, 1250 + pressure) is None
    event = detector.feed(210, 1250)
    assert event.kind == kind
    assert event.t_ns == 210_000_000
    assert detector.level == 0
    assert not detector.active
    assert detector.feed(220, 1250) is None


@pytest.mark.parametrize("duration,expected", [(79, False), (80, True)])
def test_minimum_press_boundary(duration, expected):
    detector = BreathDetector(1000, 1000, 1000)
    assert detector.feed(0, 1400) is None
    assert detector.feed(duration, 1400) is None
    assert (detector.feed(duration + 1, 1000) is not None) is expected


def test_release_does_not_qualify_a_short_sampled_press():
    detector = BreathDetector(1000, 1000, 1000)
    detector.feed(0, 1400)
    assert detector.feed(1000, 1000) is None


def test_subthreshold_drift_and_exact_soft_boundary_are_silent():
    detector = BreathDetector(1000, 1000, 1000)
    for timestamp, pressure in enumerate([1000, 1010, 990, 1100, 1250, 750, 1000]):
        assert detector.feed(timestamp * 100, pressure) is None
        assert not detector.active


def test_brief_drop_resets_minimum_press_window():
    detector = BreathDetector(1000, 1000, 1000)
    for timestamp, pressure in [(0, 1400), (70, 1400), (75, 1000), (80, 1400), (150, 1400)]:
        assert detector.feed(timestamp, pressure) is None
    assert detector.feed(155, 1000) is None


def test_peak_determines_strength_even_if_press_weakens():
    detector = BreathDetector(1000, 1000, 1000)
    for timestamp, pressure in [(0, 1700), (80, 1400), (200, 1300)]:
        assert detector.feed(timestamp, pressure) is None
    assert detector.feed(210, 1000).kind == "hard_puff"


def test_sign_reversal_releases_old_press_and_starts_new_one():
    detector = BreathDetector(1000, 1000, 1000)
    detector.feed(0, 1400)
    detector.feed(80, 1400)
    assert detector.feed(90, 600).kind == "soft_puff"
    assert detector.feed(170, 600) is None
    assert detector.feed(180, 1000).kind == "soft_sip"


@pytest.mark.parametrize("pressure,expected", [(5000, 1.0), (-5000, -1.0)])
def test_pressure_level_is_clamped(pressure, expected):
    detector = BreathDetector(1000, 1000, 500)
    detector.feed(0, pressure)
    assert detector.level == expected


def test_detector_uses_config_thresholds(monkeypatch):
    monkeypatch.setattr(config, "BREATH_SOFT", 0.1)
    monkeypatch.setattr(config, "BREATH_HARD", 0.2)
    monkeypatch.setattr(config, "BREATH_MIN_PRESS_MS", 10)
    detector = BreathDetector(1000, 1000, 1000)
    detector.feed(0, 1200)
    detector.feed(10, 1200)
    assert detector.feed(11, 1000).kind == "hard_puff"


@pytest.mark.parametrize("max_puff,max_sip", [(0, 500), (-1, 500), (500, 0), (float("nan"), 500)])
def test_invalid_pressure_calibration(max_puff, max_sip):
    with pytest.raises(ValueError):
        BreathDetector(1000, max_puff, max_sip)


def test_invalid_sample_does_not_advance_detector():
    detector = BreathDetector(1000, 1000, 1000)
    detector.feed(10, 1000)
    for timestamp, pressure in [(9, 1000), (20, float("nan")), (float("inf"), 1000)]:
        with pytest.raises(ValueError):
            detector.feed(timestamp, pressure)
    assert detector.feed(11, 1000) is None


def test_no_device_is_silent():
    for port in (None, "off", "auto"):
        sip = SipPuff(port)
        sip.start()
        assert sip.connected is False and sip.level == 0.0 and sip.poll() == []
        sip.stop()
