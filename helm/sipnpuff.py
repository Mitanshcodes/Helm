# OWNER: P2
"""Serial thread, breath level and sip/puff events (docs/SPEC.md 6.10). Bootstrap stub: no device."""
import math

from helm import config
from helm.contracts import SipPuffEvent


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
    def __init__(self, port: str | None = "auto"):   # None or "off": no device
        self.port = None if port in (None, "off") else port

    def start(self) -> None:
        # TODO(P2): import serial here; auto-detect the port that sends lines starting with "P,",
        # read at 100 Hz in a daemon thread, track baseline and level, detect events with a pure
        # class fed (t_ms, mv) pairs. A missing or unplugged device must never crash Helm.
        pass

    def stop(self) -> None:
        pass

    @property
    def connected(self) -> bool:
        return False

    @property
    def level(self) -> float:
        """[-1, 1], + puff, - sip, 0 at rest."""
        return 0.0

    def poll(self) -> list[SipPuffEvent]:
        """Events since the last call."""
        return []

    def calibrate(self, max_puff_mv: float, max_sip_mv: float) -> None:
        pass
