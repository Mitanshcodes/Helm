# OWNER: P2
"""Serial thread, breath level and sip/puff events (docs/SPEC.md 6.10)."""
import logging
import math
import statistics
import threading
import time
from collections import deque

from helm import config
from helm.contracts import SipPuffEvent

_log = logging.getLogger(__name__)


def parse_line(line: str) -> float | None:
    """`P,<millis>,<sensor millivolts>` -> millivolts, or None for noise.

    Both Arduino sketches print this format, so the laptop does not care which board is attached.
    A classic Uno resets when the port opens and emits garbage first, so unparseable lines are
    normal and must simply be skipped.
    """
    parts = line.strip().split(",")
    if len(parts) != 3 or parts[0] != "P":
        return None
    try:
        mv = float(parts[2])
    except ValueError:
        return None
    return mv if math.isfinite(mv) else None


class BreathDetector:
    """Pure pressure event detector; the serial owner supplies baseline and calibration.

    Times must be monotonic host milliseconds, not raw ESP32 millis(). Maxima are
    positive displacements from baseline. feed() emits at most one event on release.
    """

    def __init__(self, baseline_mv: float, max_puff_mv: float, max_sip_mv: float):
        if not all(math.isfinite(value) for value in (baseline_mv, max_puff_mv, max_sip_mv)):
            raise ValueError("pressure calibration must be finite")
        if max_puff_mv <= 0 or max_sip_mv <= 0:
            raise ValueError("pressure maxima must be positive baseline-relative displacements")
        self.baseline_mv = baseline_mv
        self.max_puff_mv = max_puff_mv
        self.max_sip_mv = max_sip_mv
        self.level = 0.0
        self._direction = 0
        self._started_ms = 0.0
        self._peak = 0.0
        self._qualified = False
        self._last_ms = float("-inf")

    @property
    def active(self) -> bool:
        """True during a candidate or qualified press; freeze baseline updates then."""
        return self._direction != 0

    def feed(self, t_ms: float, mv: float) -> SipPuffEvent | None:
        if not math.isfinite(t_ms) or not math.isfinite(mv):
            raise ValueError("pressure samples and timestamps must be finite")
        if t_ms < self._last_ms:
            raise ValueError("pressure timestamps must not move backwards")
        self._last_ms = t_ms
        displacement = mv - self.baseline_mv
        maximum = self.max_puff_mv if displacement >= 0 else self.max_sip_mv
        self.level = max(-1.0, min(1.0, displacement / maximum))
        magnitude = abs(self.level)
        direction = (1 if self.level > 0 else -1) if magnitude > config.BREATH_SOFT else 0
        event = None
        if self._direction and direction != self._direction:
            if self._qualified:
                strength = "hard" if self._peak >= config.BREATH_HARD else "soft"
                action = "puff" if self._direction > 0 else "sip"
                event = SipPuffEvent(t_ns=round(t_ms * 1_000_000), kind=f"{strength}_{action}")
            self._direction = 0
            self._qualified = False
            self._peak = 0.0
        if direction:
            if not self._direction:
                self._direction = direction
                self._started_ms = t_ms
            self._peak = max(self._peak, magnitude)
            if t_ms - self._started_ms >= config.BREATH_MIN_PRESS_MS:
                self._qualified = True
        return event


class SipPuff:
    """Owns the serial port on its own daemon thread. Everything the pipeline thread touches
    (`level`, `poll`, `connected`) reads a latest-value slot under a lock and never blocks.
    """

    def __init__(self, port: str | None = "auto"):   # None or "off": no device
        self.port = None if port in (None, "off") else port
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._detector: BreathDetector | None = None
        self._level = 0.0
        self._events: list[SipPuffEvent] = []
        self._last_sample_s = 0.0
        self._open_port: str | None = None
        self._max_puff_mv = config.BREATH_MAX_PUFF_MV
        self._max_sip_mv = config.BREATH_MAX_SIP_MV
        self._warned = False

    # ---- called from the pipeline thread; never blocks on I/O --------------------------------

    @property
    def connected(self) -> bool:
        with self._lock:
            return (self._open_port is not None
                    and time.monotonic() - self._last_sample_s < config.SERIAL_STALE_S)

    @property
    def level(self) -> float:
        """[-1, 1], + puff, - sip, 0 at rest."""
        with self._lock:
            return self._level

    def poll(self) -> list[SipPuffEvent]:
        """Events since the last call."""
        with self._lock:
            events, self._events = self._events, []
            return events

    def calibrate(self, max_puff_mv: float, max_sip_mv: float) -> None:
        """Set the player's own maxima, as positive displacements from baseline."""
        with self._lock:
            self._max_puff_mv = max(1.0, abs(float(max_puff_mv)))
            self._max_sip_mv = max(1.0, abs(float(max_sip_mv)))
            if self._detector is not None:
                self._detector.max_puff_mv = self._max_puff_mv
                self._detector.max_sip_mv = self._max_sip_mv

    # ---- lifecycle ---------------------------------------------------------------------------

    def start(self) -> None:
        if self.port is None or self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="sipnpuff", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2.0)

    # ---- serial thread -----------------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            port = self._connect()
            if port is None:
                self._stop.wait(config.SERIAL_RECONNECT_S)
                continue
            try:
                self._read_until_lost(port)
            except Exception:                       # a yanked cable must never take Helm down
                if not self._warned:
                    _log.warning("breath sensor read failed; will keep retrying", exc_info=True)
                    self._warned = True
            finally:
                try:
                    port.close()
                except Exception:
                    pass
                self._go_idle()

    def _connect(self):
        """Open the configured port, or try every port and keep the one that speaks `P,`."""
        try:
            import serial                            # lazy: no pyserial needed without a device
            from serial.tools import list_ports
        except Exception:
            if not self._warned:
                _log.warning("pyserial is not available; running without a breath sensor")
                self._warned = True
            self._stop.wait(config.SERIAL_RECONNECT_S)
            return None

        names = [self.port] if self.port != "auto" else [p.device for p in list_ports.comports()]
        for name in names:
            if self._stop.is_set():
                return None
            port = self._probe(serial, name)
            if port is not None:
                _log.info("breath sensor on %s", name)
                with self._lock:
                    self._open_port = name
                    self._warned = False
                return port
        return None

    def _probe(self, serial_module, name: str):
        """Keep a port only once it has actually sent a parseable `P,` line."""
        try:
            port = serial_module.Serial(name, config.SERIAL_BAUD,
                                        timeout=config.SERIAL_READ_TIMEOUT_S)
        except Exception:
            return None
        deadline = time.monotonic() + config.SERIAL_PROBE_S
        while time.monotonic() < deadline and not self._stop.is_set():
            if parse_line(_read_line(port)) is not None:
                return port
        try:
            port.close()
        except Exception:
            pass
        return None

    def _read_until_lost(self, port) -> None:
        samples: list[float] = []
        baseline_deadline = time.monotonic() + config.BREATH_BASELINE_S
        window: deque[float] = deque(maxlen=int(config.BREATH_BASELINE_WINDOW_S * 100))
        detector: BreathDetector | None = None

        while not self._stop.is_set():
            mv = parse_line(_read_line(port))
            if mv is None:
                continue
            now = time.monotonic()
            # Host monotonic milliseconds, never the board's millis(): it resets on reconnect and
            # BreathDetector rejects a backwards timestamp.
            t_ms = now * 1000.0

            if detector is None:
                # Baseline starts at the first valid line, not at open: a classic Uno spends its
                # first ~1.5 s resetting, and that noise must not land in the median.
                samples.append(mv)
                if now < baseline_deadline:
                    continue
                with self._lock:
                    detector = BreathDetector(statistics.median(samples),
                                              self._max_puff_mv, self._max_sip_mv)
                    self._detector = detector
                continue

            event = detector.feed(t_ms, mv)
            if not detector.active:
                window.append(mv)                   # drift only while nothing is being blown
                if len(window) >= 10:
                    detector.baseline_mv = statistics.median(window)
            else:
                window.clear()

            with self._lock:
                self._level = detector.level
                self._last_sample_s = now
                if event is not None:
                    self._events.append(event)

    def _go_idle(self) -> None:
        with self._lock:
            self._open_port = None
            self._detector = None
            self._level = 0.0


def _read_line(port) -> str:
    try:
        return port.readline().decode("ascii", "ignore")
    except Exception:
        return ""
