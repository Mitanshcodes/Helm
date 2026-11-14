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


# ------------------------------------------------- SipPuff serial thread, with a fake serial port
# pyserial is imported lazily inside SipPuff, so a fake module in sys.modules exercises the whole
# thread -- auto-detect, baseline, level, events, unplugging -- with no board attached.
import sys
import threading
import time
import types

import pytest

from helm import config, sipnpuff
from helm.sipnpuff import SipPuff, parse_line


def wait_for(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


class FakePort:
    """Emits scripted lines, one per readline(), pacing them so press durations are real."""

    def __init__(self, lines, per_line_s=0.001, raise_after=None):
        self._lines = list(lines)
        self._per_line_s = per_line_s
        self._raise_after = raise_after
        self._served = 0
        self.calls = 0
        self.closed = False

    def readline(self):
        self.calls += 1
        if self._raise_after is not None and self._served >= self._raise_after:
            raise OSError("device disconnected")
        time.sleep(self._per_line_s)
        self._served += 1
        if self._lines:
            return self._lines.pop(0).encode()
        return b""                      # a real port returns empty on timeout

    def close(self):
        self.closed = True


def install_fake_serial(monkeypatch, ports: dict):
    """ports maps device name -> FakePort."""
    serial_mod = types.ModuleType("serial")
    tools = types.ModuleType("serial.tools")
    list_ports = types.ModuleType("serial.tools.list_ports")
    list_ports.comports = lambda: [types.SimpleNamespace(device=n) for n in ports]
    tools.list_ports = list_ports
    serial_mod.tools = tools

    def Serial(name, baud, timeout=None):
        if name not in ports:
            raise OSError(f"no such port {name}")
        return ports[name]

    serial_mod.Serial = Serial
    for name, mod in (("serial", serial_mod), ("serial.tools", tools),
                      ("serial.tools.list_ports", list_ports)):
        monkeypatch.setitem(sys.modules, name, mod)
    return serial_mod


@pytest.fixture
def fast_breath(monkeypatch):
    """Shrink the timings so the suite stays well under its 10 s budget."""
    monkeypatch.setattr(config, "BREATH_BASELINE_S", 0.02)
    # Production keeps this at 3 s for the classic Uno's reset. In tests it is pure dead time:
    # a rejected port is only rejected once the probe window expires.
    monkeypatch.setattr(config, "SERIAL_PROBE_S", 0.1)
    monkeypatch.setattr(config, "SERIAL_RECONNECT_S", 0.02)
    # The real 80 ms press debounce would force long paced line streams here. BreathDetector's own
    # tests cover that rule with synthetic time; these tests are about the serial plumbing.
    monkeypatch.setattr(config, "BREATH_MIN_PRESS_MS", 10)
    # FakePort serves lines faster than any real board, which the backlog drain would read as a
    # stale queue. Draining has its own test below; everywhere else it is switched off.
    monkeypatch.setattr(config, "SERIAL_DRAIN_MAX_S", 0.0)


def rest(n, mv=2500):
    return [f"P,{i * 10},{mv}" for i in range(n)]


def press(n, mv, start=1000):
    return [f"P,{start + i * 10},{mv}" for i in range(n)]


@pytest.mark.parametrize("line,expected", [
    ("P,1234,2500", 2500.0),
    ("P,0,2500.5\r\n", 2500.5),
    ("", None), ("garbage", None), ("P,1234", None), ("P,1,2,3", None),
    ("X,1234,2500", None), ("P,1234,abc", None), ("P,1234,nan", None),
])
def test_parse_line(line, expected):
    assert parse_line(line) == expected


def test_no_device_stays_silent_and_costs_nothing():
    for port in (None, "off"):
        pad = SipPuff(port)
        pad.start()                      # must be a no-op, not a crash
        assert pad.connected is False and pad.level == 0.0 and pad.poll() == []
        pad.stop()


def test_auto_detect_keeps_the_port_that_speaks_P(monkeypatch, fast_breath):
    install_fake_serial(monkeypatch, {
        "/dev/noise": FakePort(["boot garbage", "not a reading"] * 50),
        "/dev/real": FakePort(rest(120)),
    })
    pad = SipPuff("auto")
    pad.start()
    try:
        assert wait_for(lambda: pad.connected), "never settled on the port sending P, lines"
        assert pad._open_port == "/dev/real"
    finally:
        pad.stop()


def test_baseline_then_puff_and_sip_produce_signed_level(monkeypatch, fast_breath):
    install_fake_serial(monkeypatch, {"/dev/real": FakePort(rest(20) + press(30, 2800))})
    pad = SipPuff("/dev/real")
    pad.start()
    try:
        assert wait_for(lambda: pad.level > 0.5), f"puff never raised level (got {pad.level})"
    finally:
        pad.stop()

    install_fake_serial(monkeypatch, {"/dev/real": FakePort(rest(20) + press(30, 2200))})
    pad = SipPuff("/dev/real")
    pad.start()
    try:
        assert wait_for(lambda: pad.level < -0.5), f"sip never lowered level (got {pad.level})"
    finally:
        pad.stop()


def test_a_held_puff_emits_one_event_on_release(monkeypatch, fast_breath):
    lines = rest(30) + press(40, 2900) + rest(40)       # ~160 ms held, then back to rest
    install_fake_serial(monkeypatch, {"/dev/real": FakePort(lines)})
    pad = SipPuff("/dev/real")
    pad.start()
    try:
        events = []
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and not events:
            events = pad.poll()
            time.sleep(0.01)
        assert len(events) == 1, f"expected exactly one event, got {events}"
        assert events[0].kind.endswith("puff")
        assert pad.poll() == []                          # poll drains
    finally:
        pad.stop()


def test_unplugged_cable_does_not_crash_and_drops_connected(monkeypatch, fast_breath):
    """docs/SPEC.md 6.10: pulling the USB cable mid-run must not take Helm down."""
    port = FakePort(rest(200), raise_after=40)
    install_fake_serial(monkeypatch, {"/dev/real": port})
    pad = SipPuff("/dev/real")
    pad.start()
    try:
        assert wait_for(lambda: pad.connected), "never connected in the first place"
        assert wait_for(lambda: not pad.connected, 4.0), "stayed connected after the cable died"
        assert pad.level == 0.0                          # neutral once the device is gone
        assert pad._thread is not None and pad._thread.is_alive()   # still retrying, not dead
    finally:
        pad.stop()


def test_calibrate_rescales_the_live_level(monkeypatch, fast_breath):
    install_fake_serial(monkeypatch, {"/dev/real": FakePort(rest(20) + press(30, 2700))})
    pad = SipPuff("/dev/real")
    pad.calibrate(max_puff_mv=800, max_sip_mv=800)       # 200 mV of 800 -> about 0.25
    pad.start()
    try:
        assert wait_for(lambda: pad.level > 0.1)
        assert pad.level < 0.5, f"800 mV full scale should keep 200 mV low, got {pad.level}"
    finally:
        pad.stop()


def test_stop_joins_the_thread(monkeypatch, fast_breath):
    install_fake_serial(monkeypatch, {"/dev/real": FakePort(rest(300))})
    pad = SipPuff("/dev/real")
    pad.start()
    assert wait_for(lambda: pad.connected)
    thread = pad._thread
    pad.stop()
    assert not thread.is_alive() and pad._thread is None


def test_missing_pyserial_is_survivable(monkeypatch, fast_breath):
    monkeypatch.setitem(sys.modules, "serial", None)     # None makes `import serial` raise
    pad = SipPuff("auto")
    pad.start()
    try:
        time.sleep(0.1)
        assert pad.connected is False and pad.level == 0.0
        assert pad._thread.is_alive()
    finally:
        pad.stop()


class TimedPort(FakePort):
    """Each line carries its own delay: 0 for a buffered backlog, a few ms for live samples."""

    def __init__(self, timed_lines):
        super().__init__([line for line, _ in timed_lines])
        self._delays = [delay for _, delay in timed_lines]

    def readline(self):
        self.calls += 1
        if self._lines:
            time.sleep(self._delays.pop(0))
            return self._lines.pop(0).encode()
        time.sleep(0.004)
        return b""


def test_uno_q_backlog_is_drained_before_the_baseline(monkeypatch, fast_breath):
    # The UNO Q queues lines while the port is closed and dumps them all on open. Here the stale
    # queue is a long puff. Without draining, the baseline would be learned from that puff and
    # the real resting pressure afterwards would read as a hard sip.
    monkeypatch.setattr(config, "SERIAL_DRAIN_MAX_S", 2.0)
    monkeypatch.setattr(config, "SERIAL_LIVE_GAP_MS", 3.0)
    monkeypatch.setattr(config, "SERIAL_LIVE_STREAK", 5)
    backlog = [(line, 0.0) for line in press(200, 2900, start=0)]
    live = ([(line, 0.004) for line in rest(40)]
            + [(line, 0.004) for line in press(20, 2900, start=5000)]
            + [(line, 0.004) for line in rest(20)])
    install_fake_serial(monkeypatch, {"/dev/unoq": TimedPort(backlog + live)})
    sip = SipPuff("auto")
    sip.start()
    try:
        deadline = time.monotonic() + 3.0
        events = []
        while time.monotonic() < deadline and not events:
            events += sip.poll()
            time.sleep(0.01)
        time.sleep(0.15)
        events += sip.poll()
        assert [e.kind for e in events] == ["hard_puff"]
        assert abs(sip.level) < 0.1
    finally:
        sip.stop()


def test_dead_port_does_not_spin_the_cpu(monkeypatch, fast_breath):
    # A read error must close the port and back off, not retry in a tight loop: a spinning serial
    # thread holds the GIL and makes the whole pipeline lag.
    port = FakePort(rest(30), raise_after=30)
    install_fake_serial(monkeypatch, {"/dev/real": port})
    sip = SipPuff("/dev/real")
    sip.start()
    try:
        time.sleep(0.2)
        before = port.calls
        time.sleep(0.5)
        assert port.calls - before < 200
        assert not sip.connected
        assert sip.level == 0.0
    finally:
        sip.stop()


def test_ports_are_ordered_arduino_first_and_bluetooth_skipped():
    from types import SimpleNamespace as P
    ports = [P(device="/dev/cu.Bluetooth-Incoming-Port", description="n/a", vid=None),
             P(device="COM3", description="Intel Serial", vid=0x8086),
             P(device="/dev/cu.usbmodem3994", description="UNO Q", vid=0x2341)]
    assert sipnpuff._candidate_ports(ports) == ["/dev/cu.usbmodem3994", "COM3"]
