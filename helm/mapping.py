# OWNER: P2
"""Trigger state machine and Mapper -> ControlState (docs/SPEC.md 6.8). Bootstrap stubs: always neutral."""
import time

from helm import config
from helm.contracts import ControlState, Signals, SipPuffEvent


class Trigger:
    def __init__(self, on: float = config.TRIGGER_ON, off: float = config.TRIGGER_OFF,
                 min_hold_ms: int = config.TRIGGER_MIN_HOLD_MS, refractory_ms: int = config.TRIGGER_REFRACTORY_MS,
                 mode: str = "tap"):   # "tap" | "hold" | "toggle"
        self.on = on
        self.off = off
        self.min_hold_ms = min_hold_ms
        self.refractory_ms = refractory_ms
        self.mode = mode

    def update(self, level: float, t_ms: float, scale: float = 1.0) -> tuple[bool, bool]:
        """Return (pressed, fired). scale multiplies on/off (fatigue). fired is True on the tick it activates."""
        # TODO(P2): hysteresis, minimum hold, refractory, tap / hold / toggle.
        return False, False


class Mapper:
    def __init__(self, mapping: dict):
        self._mapping = mapping
        self._paused = False

    def set_mapping(self, mapping: dict) -> None:
        self._mapping = mapping

    def set_paused(self, on: bool) -> None:
        self._paused = on

    def update(self, s: Signals, act: dict[str, float], events: list[SipPuffEvent],
               scales: dict[str, float]) -> ControlState:
        # TODO(P2): axes through filters.shape_axis, analog triggers, buttons through Trigger, breath
        # events, auto outputs, the pause gesture, and the list of gestures that fired on this tick.
        return ControlState(t_output_ns=time.perf_counter_ns(), paused=self._paused)

    @property
    def idle(self) -> bool:
        """No gesture pressed and all mapped axes inside their dead zones."""
        return True
