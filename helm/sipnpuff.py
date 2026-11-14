# OWNER: P2
"""Serial thread, breath level and sip/puff events (docs/SPEC.md 6.10). Bootstrap stub: no device."""
from helm.contracts import SipPuffEvent


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
