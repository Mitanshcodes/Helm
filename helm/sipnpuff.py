# OWNER: P2
"""Serial thread, breath level and sip/puff events (docs/SPEC.md 6.10)."""
import logging
import math
import statistics
import threading
import time
from collections import deque

from helm import config
from helm.contracts import Progress, SipPuffEvent

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
        # Largest displacement either way since reset_peaks(), in millivolts, both positive.
        # Raw displacement, not level: the point of measuring is that the level scale is wrong.
        self._peak_puff_mv = 0.0
        self._peak_sip_mv = 0.0
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

    @property
    def peaks(self) -> tuple[float, float]:
        """(puff, sip) largest displacement since reset_peaks(), millivolts, both positive."""
        with self._lock:
            return self._peak_puff_mv, self._peak_sip_mv

    @property
    def scales(self) -> tuple[float, float]:
        """(max_puff_mv, max_sip_mv) currently in force: config defaults, or a calibrated player."""
        with self._lock:
            return self._max_puff_mv, self._max_sip_mv

    def reset_peaks(self) -> None:
        with self._lock:
            self._peak_puff_mv = 0.0
            self._peak_sip_mv = 0.0

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

        names = [self.port] if self.port != "auto" else _candidate_ports(list_ports.comports())
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
            try:
                line = port.readline().decode("ascii", "ignore")
            except Exception:                       # dead port: give up now, don't spin on it
                break
            if parse_line(line) is not None:
                return port
        try:
            port.close()
        except Exception:
            pass
        return None

    def _read_until_lost(self, port) -> None:
        """Read until the cable goes or the port falls silent; any exception means reconnect."""
        self._drain_backlog(port)
        samples: list[float] = []
        baseline_deadline: float | None = None
        window: deque[float] = deque(maxlen=int(config.BREATH_BASELINE_WINDOW_S * 100))
        detector: BreathDetector | None = None
        last_valid = time.monotonic()

        while not self._stop.is_set():
            # No try/except here on purpose: a yanked cable raises, and _run closes the port and
            # reconnects. Swallowing the error would spin this thread at full CPU on a dead port.
            mv = parse_line(port.readline().decode("ascii", "ignore"))
            now = time.monotonic()
            if mv is None:
                if now - last_valid > config.SERIAL_LOST_S:
                    raise OSError("breath sensor stopped sending")
                continue
            last_valid = now
            # Host monotonic milliseconds, never the board's millis(): it resets on reconnect and
            # BreathDetector rejects a backwards timestamp.
            t_ms = now * 1000.0

            if detector is None:
                # The baseline clock starts at the first live line, after the backlog is gone.
                if baseline_deadline is None:
                    baseline_deadline = now + config.BREATH_BASELINE_S
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

            displacement = mv - detector.baseline_mv
            with self._lock:
                self._level = detector.level
                self._last_sample_s = now
                self._peak_puff_mv = max(self._peak_puff_mv, displacement)
                self._peak_sip_mv = max(self._peak_sip_mv, -displacement)
                if event is not None:
                    self._events.append(event)

    def _drain_backlog(self, port) -> None:
        """Throw away lines the board buffered while nobody was listening.

        The UNO Q's Linux side keeps queueing lines while the port is closed and delivers the whole
        queue on open: over a minute of stale pressure arriving at ~1500 lines/s. Buffered lines come
        back from readline() instantly; live ones make it wait for the next sample (10 to 15 ms). So
        the backlog is gone once several reads in a row had to wait. A classic Uno has no backlog
        and passes this in a few lines.
        """
        deadline = time.monotonic() + config.SERIAL_DRAIN_MAX_S
        streak = 0
        while streak < config.SERIAL_LIVE_STREAK and time.monotonic() < deadline:
            if self._stop.is_set():
                return
            t0 = time.monotonic()
            port.readline()                         # errors propagate: unplugged mid-drain
            waited_ms = (time.monotonic() - t0) * 1000.0
            streak = streak + 1 if waited_ms >= config.SERIAL_LIVE_GAP_MS else 0

    def _go_idle(self) -> None:
        with self._lock:
            self._open_port = None
            self._detector = None
            self._level = 0.0


class BreathCalibrator:
    """Measures one player's sip and puff range, as a timed prompted flow (docs/SPEC.md 6.5, 6.10).

    Deliberately shaped like `calibration.Calibrator` -- `feed()` returns a `Progress` and sets
    `done` -- so the runtime drives it with the same three lines it already uses for the face
    wizard, and the dashboard renders its prompts with no UI change at all.

    It is not part of `Calibration`: that contract is frozen and has no breath fields, and breath
    range is a property of the sensor and the player's lungs rather than of their face. It persists
    separately through `profiles.save_breath`.

    Pure timing plus latest-value reads from `SipPuff`. No I/O, so it is safe on the pipeline
    thread; persisting the result is the caller's job and belongs off that thread.
    """

    # step name, seconds, prompt, which peak it reads ("" settles the baseline and reads nothing)
    _STEPS = (
        ("breath_rest", config.CALIB_BREATH_REST_S, "Hands off the tube, breathe normally", ""),
        ("breath_sip", config.CALIB_BREATH_STEP_S, "Sip hard on the tube, like a thick straw, and hold", "sip"),
        ("breath_puff", config.CALIB_BREATH_STEP_S, "Now puff hard into the tube, and hold", "puff"),
    )

    def __init__(self, sip: "SipPuff"):
        self._sip = sip
        self._i = 0
        self._started_s: float | None = None
        self._done_s = 0.0
        self._total_s = sum(s[1] for s in self._STEPS)
        self._measured: dict[str, float] = {}
        self.done = False
        self.notes: list[str] = []

    def feed(self, t_s: float) -> Progress:
        """Advance on the frame's own timestamp. Returns the prompt to show the player."""
        if self.done:
            return Progress(active=False, step="done", prompt="Breath range set", progress=1.0,
                            overall=1.0, done=True)
        name, duration, prompt, measures = self._STEPS[self._i]
        if self._started_s is None:
            self._started_s = t_s
            self._sip.reset_peaks()
        elapsed = max(0.0, t_s - self._started_s)

        if elapsed >= duration:
            if measures:
                puff, sip = self._sip.peaks
                self._measured[measures] = puff if measures == "puff" else sip
            self._done_s += duration
            self._i += 1
            self._started_s = None
            if self._i == len(self._STEPS):
                self.done = True
                return self.feed(t_s)
            name, duration, prompt, measures = self._STEPS[self._i]
            elapsed = 0.0

        return Progress(active=True, step=name, prompt=prompt,
                        progress=min(elapsed / duration, 1.0),
                        overall=min((self._done_s + elapsed) / self._total_s, 1.0))

    def result(self) -> tuple[float, float]:
        """(max_puff_mv, max_sip_mv) to hand to `SipPuff.calibrate`.

        A direction that measured too little to be a real breath keeps the current scale and is
        reported in `notes`. Without that floor a player who ignored the step would set full scale
        to a few millivolts of rest noise, and the sensor would then drive the pad on its own.
        """
        current_puff, current_sip = self._sip.scales
        self.notes = []                 # idempotent: a second call must not double the notes
        out = []
        for direction, current in (("puff", current_puff), ("sip", current_sip)):
            peak = self._measured.get(direction, 0.0)
            if peak < config.CALIB_BREATH_MIN_MV:
                self.notes.append(
                    f"{direction.capitalize()} measured only {peak:.0f} mV, too little to trust; "
                    f"keeping the previous range. Check the tube is on the sensor port.")
                out.append(current)
                continue
            scaled = min(peak * config.CALIB_BREATH_FRACTION, config.CALIB_BREATH_MAX_MV)
            out.append(max(scaled, 1.0))
        return out[0], out[1]


def _candidate_ports(ports) -> list[str]:
    """Arduino-looking ports first; Bluetooth ports skipped (on Windows they can hang on open)."""
    arduino_vids = {0x2341, 0x2A03, 0x1A86}          # Arduino, Arduino.org, CH340 clones
    likely, other = [], []
    for p in ports:
        label = f"{p.device} {getattr(p, 'description', '') or ''}".lower()
        if "bluetooth" in label:
            continue
        if getattr(p, "vid", None) in arduino_vids or "arduino" in label or "usbmodem" in label:
            likely.append(p.device)
        else:
            other.append(p.device)
    return likely + other


def _read_line(port) -> str:
    try:
        return port.readline().decode("ascii", "ignore")
    except Exception:
        return ""
