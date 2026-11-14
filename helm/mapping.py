# OWNER: P2
"""Trigger state machine and Mapper -> ControlState (docs/SPEC.md 6.8)."""
import time

from helm import config
from helm.contracts import PAD_AXES, PAD_BUTTONS, PAD_TRIGGERS, ControlState, Signals, SipPuffEvent
from helm.filters import shape_axis


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


class Trigger:
    def __init__(self, on: float = config.TRIGGER_ON, off: float = config.TRIGGER_OFF,
                 min_hold_ms: int = config.TRIGGER_MIN_HOLD_MS, refractory_ms: int = config.TRIGGER_REFRACTORY_MS,
                 mode: str = "tap"):   # "tap" | "hold" | "toggle"
        self.on = on
        self.off = off
        self.min_hold_ms = min_hold_ms
        self.refractory_ms = refractory_ms
        self.mode = mode
        if not 0 <= off < on <= 1:
            raise ValueError("thresholds must satisfy 0 <= off < on <= 1")
        if min_hold_ms < 0 or refractory_ms < 0:
            raise ValueError("trigger durations must be nonnegative")
        if mode not in ("tap", "hold", "toggle"):
            raise ValueError("mode must be tap, hold or toggle")
        self._candidate_since: float | None = None
        self._active = False
        self._released_at = float("-inf")
        self._tap_until = float("-inf")
        self._latched = False

    def update(self, level: float, t_ms: float, scale: float = 1.0) -> tuple[bool, bool]:
        """Return (pressed, fired). scale multiplies on/off (fatigue). fired is True on the tick it activates."""
        on_eff = self.on * scale
        off_eff = self.off * scale
        fired = False
        if self._active:
            # Hysteresis applies only after activation.
            if level <= off_eff:
                self._active = False
                self._released_at = t_ms
        elif t_ms - self._released_at < self.refractory_ms:
            # A new hold window cannot accumulate during refractory.
            self._candidate_since = None
        elif level >= on_eff:
            if self._candidate_since is None:
                self._candidate_since = t_ms
            if t_ms - self._candidate_since >= self.min_hold_ms:
                self._active = True
                self._candidate_since = None
                self._tap_until = t_ms + config.TAP_MS
                self._latched = not self._latched
                fired = True
        else:
            # Any dip below on resets an unconfirmed gesture.
            self._candidate_since = None
        # Pulse/latch output is independent of the gesture's active state.
        if self.mode == "tap":
            return t_ms < self._tap_until, fired
        if self.mode == "toggle":
            return self._latched, fired
        return self._active, fired


class Mapper:
    def __init__(self, mapping: dict):
        self._paused = False
        self._pause_since: float | None = None
        self._pause_armed = True
        self._idle = True
        self.set_mapping(mapping)

    def set_mapping(self, mapping: dict) -> None:
        """Rebuild the Trigger set. Called off the pipeline thread (profile load, coach result)."""
        self._mapping = mapping
        self._gestures = mapping.get("gestures", {}) or {}
        self._axis_defs = mapping.get("axes", []) or []
        self._trigger_defs = mapping.get("triggers", []) or []
        self._auto = mapping.get("auto", {}) or {}
        # Breath gestures are named after the event kind they listen for (docs/SPEC.md 7).
        self._breath_gestures = {n for n, d in self._gestures.items() if d.get("kind") == "breath"}

        self._buttons: list[tuple[str, str, Trigger]] = []
        for entry in mapping.get("buttons", []) or []:
            name = entry.get("gesture")
            target = entry.get("target")
            if not name or not target:
                continue
            defn = self._gestures.get(name, {})
            # A breath event is level 1.0 for exactly one tick, so the usual minimum hold would
            # mean it never activates at all. Discrete events need no debounce: the detector in
            # sipnpuff.py already qualified the press over 80 ms before emitting.
            min_hold = 0 if defn.get("kind") == "breath" else config.TRIGGER_MIN_HOLD_MS
            self._buttons.append((name, target, Trigger(
                on=defn.get("on", config.TRIGGER_ON),
                off=defn.get("off", config.TRIGGER_OFF),
                min_hold_ms=defn.get("min_hold_ms", min_hold),
                mode=entry.get("mode", "tap"),
            )))

        pause = mapping.get("pause") or {}
        self._pause_gesture = pause.get("gesture")
        self._pause_hold_ms = pause.get("hold_ms", config.PAUSE_HOLD_MS)
        # A mapping swap must not strand a half-finished pause hold, but it must not unpause either.
        self._pause_since = None
        self._pause_armed = True

    def set_paused(self, on: bool) -> None:
        self._paused = on
        self._pause_since = None
        self._pause_armed = True

    def update(self, s: Signals, act: dict[str, float], events: list[SipPuffEvent],
               scales: dict[str, float]) -> ControlState:
        # Drive every timer from the frame's own timestamp, not a fresh clock read, so a replayed
        # session reproduces exactly. perf_counter_ns is only for stamping the output.
        t_ms = s.t_infer_ns / 1_000_000.0
        levels = dict(act)
        for name in self._breath_gestures:
            levels[name] = 0.0
        for event in events:
            if event.kind in self._breath_gestures:
                levels[event.kind] = 1.0      # level 1.0 on the tick the event arrives

        if self._update_pause(levels, t_ms):
            self._idle = True
            return ControlState(t_output_ns=time.perf_counter_ns(), paused=True)

        state = ControlState(t_output_ns=time.perf_counter_ns())
        buttons: set[str] = set()

        for target, value in self._auto.items():          # constant outputs, e.g. auto-accelerate
            if target in PAD_AXES:
                setattr(state, target, float(value))
            elif target in PAD_TRIGGERS:
                setattr(state, target, _clamp01(float(value)))
            elif target in PAD_BUTTONS and value:
                buttons.add(target)

        for axis in self._axis_defs:
            source, target = axis.get("source"), axis.get("target")
            if target not in PAD_AXES or source not in s.axes:
                continue
            setattr(state, target, shape_axis(
                s.axes[source],
                axis.get("deadzone", config.AXIS_DEADZONE),
                axis.get("curve", config.AXIS_GAMMA),
                axis.get("invert", False),
            ))

        for trig in self._trigger_defs:
            target = trig.get("target")
            if target not in PAD_TRIGGERS:
                continue
            lo, hi = trig.get("lo", 0.0), trig.get("hi", 1.0)
            if hi <= lo:
                continue
            level = self._analog_level(trig.get("source"), s, levels)
            setattr(state, target, _clamp01((level - lo) / (hi - lo)))

        fired: list[str] = []
        any_pressed = False
        for name, target, trigger in self._buttons:
            pressed, did_fire = trigger.update(levels.get(name, 0.0), t_ms, scales.get(name, 1.0))
            if did_fire:
                fired.append(name)
            if pressed:
                any_pressed = True
                if target in PAD_TRIGGERS:
                    setattr(state, target, 1.0)
                elif target in PAD_BUTTONS:
                    buttons.add(target)

        state.buttons = frozenset(buttons)
        state.fired = tuple(fired)
        self._idle = not any_pressed and all(
            getattr(state, a["target"]) == 0.0
            for a in self._axis_defs if a.get("target") in PAD_AXES
        )
        return state

    def _analog_level(self, source: str | None, s: Signals, levels: dict[str, float]) -> float:
        if source == "breath_puff":
            return max(0.0, s.breath)
        if source == "breath_sip":
            return max(0.0, -s.breath)
        return levels.get(source, 0.0) if source else 0.0

    def _update_pause(self, levels: dict[str, float], t_ms: float) -> bool:
        """Hold the pause gesture above `on` for hold_ms, without a break, to toggle. Any dip below `on`
        restarts the hold, so blinks and squints never add up to a pause. Re-toggling needs a release
        below `off` first, or holding your eyes shut would flip pause every hold_ms."""
        name = self._pause_gesture
        if not name:
            return self._paused
        defn = self._gestures.get(name, {})
        level = levels.get(name, 0.0)
        if level >= defn.get("on", config.TRIGGER_ON):
            if self._pause_armed:
                if self._pause_since is None:
                    self._pause_since = t_ms
                if t_ms - self._pause_since >= self._pause_hold_ms:
                    self._paused = not self._paused
                    self._pause_armed = False
                    self._pause_since = None
        else:
            self._pause_since = None
            if level <= defn.get("off", config.TRIGGER_OFF):
                self._pause_armed = True
        return self._paused

    @property
    def idle(self) -> bool:
        """No gesture pressed and all mapped axes inside their dead zones."""
        return self._idle
