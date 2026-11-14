# OWNER: P2
"""Synthetic-time Trigger and Mapper tests. No camera, gamepad or serial port."""
import pytest

from helm import config, mapping
from helm.contracts import ControlState, FrameFeatures, SipPuffEvent
from helm.filters import Normalizer
from helm.mapping import Mapper, Trigger
from helm.profiles import default_mapping
from helm import filters, mapping as mapping_module


def mapper_signals(yaw=0.0, breath=0.0):
    return Normalizer().update(
        FrameFeatures(seq=1, t_capture_ns=0, t_infer_ns=0, face=True, yaw=yaw), breath=breath
    )


def mapper_tick(mapper, milliseconds, activations=None, events=None, scales=None):
    signals = mapper_signals()
    signals.t_infer_ns = round(milliseconds * 1_000_000)
    return mapper.update(signals, activations or {}, events or [], scales or {})


def test_mapper_auto_throttle_and_manual_pause():
    definition = default_mapping("SuperTuxKart")
    definition["auto"] = {"rt": 1.0}
    mapper = Mapper(definition)
    assert mapper_tick(mapper, 0).rt == 1.0
    mapper.set_paused(True)
    paused = mapper_tick(mapper, 10)
    assert paused.paused and paused.rt == 0 and not paused.buttons
    mapper.set_paused(False)
    assert mapper_tick(mapper, 20).rt == 1.0


@pytest.mark.parametrize("target", ["A", "rt"])
def test_mapper_hold_button_uses_frame_time_and_fatigue_scale(monkeypatch, target):
    monkeypatch.setattr(mapping.time, "perf_counter_ns", lambda: 9_000_000_000)
    definition = default_mapping("SuperTuxKart")
    definition["gestures"]["brow"] = {"kind": "blendshape", "sources": ["browInnerUp"]}
    definition["buttons"] = [{"gesture": "brow", "target": target, "mode": "hold"}]
    mapper = Mapper(definition)
    first = mapper_tick(mapper, 0, {"brow": 0.3}, scales={"brow": 0.5})
    assert not first.fired
    active = mapper_tick(mapper, config.TRIGGER_MIN_HOLD_MS, {"brow": 0.3}, scales={"brow": 0.5})
    assert active.fired == ("brow",)
    assert active.t_output_ns == 9_000_000_000
    assert (target in active.buttons) if target == "A" else active.rt == 1.0
    assert not mapper.idle
    released = mapper_tick(mapper, 100, {"brow": 0.0})
    assert not released.buttons and released.rt == 0 and mapper.idle


@pytest.mark.parametrize("source,breath", [("breath_sip", 0.8), ("breath_puff", -0.8)])
def test_mapper_opposite_breath_direction_does_not_drive_trigger(source, breath):
    definition = default_mapping("SuperTuxKart")
    definition["triggers"] = [{"source": source, "target": "rt", "lo": 0.2, "hi": 0.8}]
    state = Mapper(definition).update(mapper_signals(breath=breath), {}, [], {})
    assert state.rt == 0.0


def test_mapper_pause_ignores_gameplay_activations():
    definition = default_mapping("SuperTuxKart")
    definition["gestures"]["brow"] = {"kind": "blendshape", "sources": ["browInnerUp"]}
    definition["buttons"] = [{"gesture": "brow", "target": "A", "mode": "toggle"}]
    mapper = Mapper(definition)
    mapper.set_paused(True)
    for milliseconds in (0, 100, 200):
        state = mapper_tick(mapper, milliseconds, {"brow": 1.0})
        assert state.paused and not state.buttons and not state.fired
    mapper.set_paused(False)
    assert not mapper_tick(mapper, 300).buttons


def test_mapper_mapping_swap_clears_latched_outputs():
    definition = default_mapping("SuperTuxKart")
    definition["gestures"]["brow"] = {"kind": "blendshape", "sources": ["browInnerUp"]}
    definition["buttons"] = [{"gesture": "brow", "target": "A", "mode": "toggle"}]
    mapper = Mapper(definition)
    mapper_tick(mapper, 0, {"brow": 1.0})
    assert mapper_tick(mapper, 100, {"brow": 1.0}).buttons == frozenset({"A"})
    mapper.set_mapping(default_mapping("SuperTuxKart"))
    assert not mapper_tick(mapper, 200).buttons


@pytest.mark.parametrize("mode", ["tap", "toggle"])
def test_mapper_single_tick_breath_event_activates(mode):
    definition = default_mapping("SuperTuxKart")
    definition["gestures"]["hard_puff"] = {"kind": "breath"}
    definition["buttons"] = [{"gesture": "hard_puff", "target": "rt", "mode": mode}]
    mapper = Mapper(definition)
    event = SipPuffEvent(t_ns=1_000_000, kind="hard_puff")
    activated = mapper_tick(mapper, 1, events=[event])
    assert activated.rt == 1.0 and activated.fired == ("hard_puff",)
    assert mapper_tick(mapper, 34).rt == 1.0
    later = mapper_tick(mapper, 1 + config.TAP_MS)
    assert later.rt == (1.0 if mode == "toggle" else 0.0)


@pytest.mark.parametrize("source,target", [("yaw", "lx"), ("pitch", "ry"), ("roll", "rx")])
def test_mapper_delegates_axis_shaping(monkeypatch, source, target):
    calls = []

    def shape_axis(value, deadzone, gamma, invert):
        calls.append((value, deadzone, gamma, invert))
        return -0.37

    monkeypatch.setattr(filters, "shape_axis", shape_axis)
    monkeypatch.setattr(mapping_module, "shape_axis", shape_axis, raising=False)
    definition = default_mapping("SuperTuxKart")
    definition["axes"] = [{"source": source, "target": target, "deadzone": 0.12,
                           "curve": 1.7, "invert": True}]
    signals = mapper_signals()
    signals.axes[source] = 0.6
    state = Mapper(definition).update(signals, {}, [], {})
    assert calls == [(0.6, 0.12, 1.7, True)]
    assert getattr(state, target) == -0.37


@pytest.mark.parametrize("source,breath,activation", [
    ("jaw_open", 0.0, 0.5), ("breath_puff", 0.5, 0.0), ("breath_sip", -0.5, 0.0),
])
@pytest.mark.parametrize("target", ["lt", "rt"])
def test_mapper_analog_sources_scale_to_trigger(source, breath, activation, target):
    definition = default_mapping("SuperTuxKart")
    definition["triggers"] = [{"source": source, "target": target, "lo": 0.2, "hi": 0.8}]
    state = Mapper(definition).update(mapper_signals(breath=breath), {"jaw_open": activation}, [], {})
    assert getattr(state, target) == pytest.approx(0.5)


@pytest.mark.parametrize("level", [1.0, 2.0])
def test_mapper_analog_trigger_clamps_above_high(level):
    definition = default_mapping("SuperTuxKart")
    definition["triggers"] = [{"source": "jaw_open", "target": "rt", "lo": 0.2, "hi": 0.8}]
    state = Mapper(definition).update(mapper_signals(), {"jaw_open": level}, [], {})
    assert state.rt == 1.0


@pytest.mark.parametrize("level", [-1.0, 0.0, 0.2])
def test_mapper_analog_trigger_is_neutral_below_low(level):
    definition = default_mapping("SuperTuxKart")
    definition["triggers"] = [{"source": "jaw_open", "target": "rt", "lo": 0.2, "hi": 0.8}]
    state = Mapper(definition).update(mapper_signals(), {"jaw_open": level}, [], {})
    assert state.rt == 0.0


def test_mapper_pause_gesture_toggles_once_per_closure(monkeypatch):
    clock = [0]
    monkeypatch.setattr(mapping_module.time, "perf_counter_ns", lambda: clock[0])
    definition = default_mapping("SuperTuxKart")
    definition["auto"] = {"rt": 1.0}
    mapper = Mapper(definition)

    def tick(milliseconds, closed):
        clock[0] = milliseconds * 1_000_000
        signals = mapper_signals()
        signals.t_capture_ns = clock[0]
        signals.t_infer_ns = clock[0]
        return mapper.update(signals, {"eyes_closed": float(closed)}, [], {})

    assert not tick(0, True).paused
    assert not tick(config.PAUSE_HOLD_MS - 1, True).paused
    paused = tick(config.PAUSE_HOLD_MS, True)
    assert paused.paused and paused.rt == 0.0 and not paused.buttons
    assert tick(config.PAUSE_HOLD_MS * 3, True).paused
    assert tick(config.PAUSE_HOLD_MS * 3 + 1, False).paused
    assert tick(config.PAUSE_HOLD_MS * 4, True).paused
    resumed = tick(config.PAUSE_HOLD_MS * 5, True)
    assert not resumed.paused and resumed.rt == 1.0


def test_minimum_hold_and_hysteresis_at_exact_thresholds():
    trigger = Trigger(mode="hold")
    start = 1234.25
    activation = start + config.TRIGGER_MIN_HOLD_MS
    middle = (config.TRIGGER_ON + config.TRIGGER_OFF) / 2
    assert trigger.update(config.TRIGGER_ON, start) == (False, False)
    assert trigger.update(config.TRIGGER_ON, activation - 0.25) == (False, False)
    assert trigger.update(config.TRIGGER_ON, activation) == (True, True)
    for t_ms in (activation, activation + 16, activation + 49):
        assert trigger.update(middle, t_ms) == (True, False)
    assert trigger.update(config.TRIGGER_ON, activation + 65) == (True, False)
    assert trigger.update(config.TRIGGER_OFF, activation + 98) == (False, False)


def test_single_spike_does_not_activate():
    trigger = Trigger(mode="hold")
    assert trigger.update(config.TRIGGER_ON, 0.0) == (False, False)
    assert trigger.update(0.0, config.TRIGGER_MIN_HOLD_MS / 2) == (False, False)
    assert trigger.update(0.0, config.TRIGGER_MIN_HOLD_MS * 2) == (False, False)


def test_dip_into_hysteresis_band_resets_hold_timer():
    trigger = Trigger(mode="hold")
    hold = config.TRIGGER_MIN_HOLD_MS
    middle = (config.TRIGGER_ON + config.TRIGGER_OFF) / 2
    assert trigger.update(config.TRIGGER_ON, 0.0) == (False, False)
    assert trigger.update(middle, hold - 0.25) == (False, False)
    assert trigger.update(config.TRIGGER_ON, hold) == (False, False)
    assert trigger.update(config.TRIGGER_ON, 2 * hold - 0.25) == (False, False)
    assert trigger.update(config.TRIGGER_ON, 2 * hold) == (True, True)


@pytest.mark.parametrize("mode", ["tap", "hold", "toggle"])
@pytest.mark.parametrize("step_ms", [33, 16])
def test_frame_steps_fire_once_and_preserve_mode_output(mode, step_ms):
    trigger = Trigger(mode=mode)
    start = 0.25
    hold = config.TRIGGER_MIN_HOLD_MS
    activation_tick = (hold + step_ms - 1) // step_ms
    activation = start + activation_tick * step_ms
    end_tick = activation_tick + config.TAP_MS // step_ms + 3
    for tick in range(end_tick + 1):
        t_ms = start + tick * step_ms
        pressed, fired = trigger.update(config.TRIGGER_ON, t_ms)
        expected_pressed = t_ms >= activation
        if mode == "tap":
            expected_pressed = expected_pressed and t_ms < activation + config.TAP_MS
        assert (pressed, fired) == (expected_pressed, tick == activation_tick)


@pytest.mark.parametrize("mode", ["tap", "hold", "toggle"])
def test_refractory_starts_on_release_and_requires_a_fresh_hold(mode):
    trigger = Trigger(mode=mode)
    hold = config.TRIGGER_MIN_HOLD_MS
    trigger.update(config.TRIGGER_ON, 0.0)
    assert trigger.update(config.TRIGGER_ON, hold) == (True, True)
    # Keep the gesture active well beyond any activation-based refractory.
    release = hold + config.TRIGGER_REFRACTORY_MS + config.TAP_MS
    assert trigger.update(config.TRIGGER_OFF, release) == (mode == "toggle", False)
    ready = release + config.TRIGGER_REFRACTORY_MS
    for t_ms in (release, release + 0.25, ready - 0.25, ready, ready + hold - 0.25):
        assert trigger.update(config.TRIGGER_ON, t_ms) == (mode == "toggle", False)
    assert trigger.update(config.TRIGGER_ON, ready + hold) == (mode != "toggle", True)
    assert trigger.update(config.TRIGGER_ON, ready + hold) == (mode != "toggle", False)


def test_tap_expires_even_when_gesture_stays_high():
    trigger = Trigger()
    activation = config.TRIGGER_MIN_HOLD_MS
    trigger.update(config.TRIGGER_ON, 0.0)
    assert trigger.update(config.TRIGGER_ON, activation) == (True, True)
    assert trigger.update(config.TRIGGER_ON, activation + config.TAP_MS - 0.25) == (True, False)
    assert trigger.update(config.TRIGGER_ON, activation + config.TAP_MS) == (False, False)


def test_tap_keeps_its_duration_after_early_release():
    trigger = Trigger()
    activation = config.TRIGGER_MIN_HOLD_MS
    trigger.update(config.TRIGGER_ON, 0.0)
    assert trigger.update(config.TRIGGER_ON, activation) == (True, True)
    assert trigger.update(config.TRIGGER_OFF, activation + 0.25) == (True, False)
    assert trigger.update(0.0, activation + config.TAP_MS - 0.25) == (True, False)
    assert trigger.update(0.0, activation + config.TAP_MS) == (False, False)


def test_toggle_persists_on_release_and_flips_on_next_activation():
    trigger = Trigger(mode="toggle")
    t_ms = 0.25
    for latched in (True, False, True):
        assert trigger.update(config.TRIGGER_ON, t_ms) == (not latched, False)
        t_ms += config.TRIGGER_MIN_HOLD_MS
        assert trigger.update(config.TRIGGER_ON, t_ms) == (latched, True)
        t_ms += 16
        assert trigger.update(config.TRIGGER_OFF, t_ms) == (latched, False)
        t_ms += config.TRIGGER_REFRACTORY_MS
        assert trigger.update(0.0, t_ms) == (latched, False)


@pytest.mark.parametrize("scale", [0.5, 1.0, 1.5])
def test_scale_multiplies_both_thresholds(scale):
    trigger = Trigger(mode="hold")
    on = config.TRIGGER_ON * scale
    off = config.TRIGGER_OFF * scale
    hold = config.TRIGGER_MIN_HOLD_MS
    assert trigger.update(on, 0.0, scale) == (False, False)
    assert trigger.update(on, hold, scale) == (True, True)
    assert trigger.update((on + off) / 2, hold + 16, scale) == (True, False)
    assert trigger.update(off, hold + 33, scale) == (False, False)


def test_runtime_scale_change_starts_and_resets_pending_hold():
    trigger = Trigger(mode="hold")
    level = config.TRIGGER_ON * 0.5
    hold = config.TRIGGER_MIN_HOLD_MS
    assert trigger.update(level, 0.0) == (False, False)
    assert trigger.update(level, hold, scale=0.5) == (False, False)
    assert trigger.update(level, 2 * hold - 0.25, scale=1.0) == (False, False)
    assert trigger.update(level, 2 * hold, scale=0.5) == (False, False)
    assert trigger.update(level, 3 * hold - 0.25, scale=0.5) == (False, False)
    assert trigger.update(level, 3 * hold, scale=0.5) == (True, True)


def test_runtime_scale_change_preserves_a_still_qualifying_hold():
    trigger = Trigger(mode="hold")
    hold = config.TRIGGER_MIN_HOLD_MS
    assert trigger.update(config.TRIGGER_ON, 0.0) == (False, False)
    assert trigger.update(config.TRIGGER_ON, hold / 2, scale=0.5) == (False, False)
    assert trigger.update(config.TRIGGER_ON, hold, scale=0.5) == (True, True)


def test_runtime_scale_change_moves_release_threshold():
    trigger = Trigger(mode="hold")
    hold = config.TRIGGER_MIN_HOLD_MS
    trigger.update(config.TRIGGER_ON, 0.0)
    assert trigger.update(config.TRIGGER_ON, hold) == (True, True)
    assert trigger.update(config.TRIGGER_OFF, hold + 16, scale=0.5) == (True, False)
    assert trigger.update(config.TRIGGER_OFF, hold + 33, scale=1.0) == (False, False)


def test_zero_durations_allow_immediate_activation_and_rearm():
    trigger = Trigger(min_hold_ms=0, refractory_ms=0, mode="hold")
    assert trigger.update(1, 0) == (True, True)
    assert trigger.update(0, 1) == (False, False)
    assert trigger.update(1, 2) == (True, True)


@pytest.mark.parametrize("kwargs", [
    {"on": config.TRIGGER_OFF, "off": config.TRIGGER_OFF}, {"off": -0.1}, {"on": 1.1},
    {"min_hold_ms": -1}, {"refractory_ms": -1}, {"mode": "repeat"},
])
def test_invalid_trigger_configuration(kwargs):
    with pytest.raises(ValueError):
        Trigger(**kwargs)


@pytest.mark.parametrize("mode", ["tap", "hold", "toggle"])
def test_trigger_never_reads_the_module_clock(monkeypatch, mode):
    class ForbiddenClock:
        def __getattr__(self, name):
            pytest.fail(f"Trigger accessed time.{name}")

    monkeypatch.setattr(mapping, "time", ForbiddenClock())
    trigger = Trigger(mode=mode)
    trigger.update(config.TRIGGER_ON, 0.0)
    assert trigger.update(config.TRIGGER_ON, config.TRIGGER_MIN_HOLD_MS) == (True, True)
    release = config.TRIGGER_MIN_HOLD_MS + 16
    assert trigger.update(config.TRIGGER_OFF, release)[1] is False
    ready = release + config.TRIGGER_REFRACTORY_MS
    trigger.update(config.TRIGGER_ON, ready)
    assert trigger.update(config.TRIGGER_ON, ready + config.TRIGGER_MIN_HOLD_MS)[1] is True


def test_trigger_interface():
    pressed, fired = Trigger().update(0.0, t_ms=0.0)
    assert pressed is False and fired is False


def test_mapper_interface():
    mapper = Mapper(default_mapping("SuperTuxKart"))
    s = Normalizer().update(FrameFeatures(seq=0, t_capture_ns=0, t_infer_ns=0, face=True))
    state = mapper.update(s, act={}, events=[], scales={})
    assert isinstance(state, ControlState) and not state.paused
    assert isinstance(mapper.idle, bool)
    mapper.set_paused(True)
    assert mapper.update(s, {}, [], {}).paused


# ---------------------------------------------------------------- Mapper: auto, breath, fired, idle
import numpy as np

from helm.contracts import FEATURE_DIM, N_BLEND, Signals, SipPuffEvent


def sig(t_ms=0.0, yaw=0.0, breath=0.0):
    """A Signals built directly, so the test owns the timestamp that drives every Mapper timer."""
    t_ns = int(t_ms * 1_000_000)
    return Signals(seq=1, t_capture_ns=t_ns, t_infer_ns=t_ns, face=True,
                   axes={"yaw": yaw, "pitch": 0.0, "roll": 0.0},
                   expr=np.zeros(N_BLEND, np.float32),
                   delta=np.zeros(FEATURE_DIM, np.float32), breath=breath)


def gesture_mapping(gesture, defn, target, mode):
    m = default_mapping("SuperTuxKart")
    m["gestures"][gesture] = defn
    m["buttons"] = [{"gesture": gesture, "target": target, "mode": mode}]
    return m


def test_auto_outputs_drive_triggers_axes_and_buttons():
    m = default_mapping("SuperTuxKart")
    m["auto"] = {"rt": 1.0, "ly": 0.5, "A": 1}
    state = Mapper(m).update(sig(), {}, [], {})
    assert state.rt == 1.0 and state.ly == 0.5 and "A" in state.buttons


def test_auto_accelerate_is_the_judge_profile_shape():
    """docs/SPEC.md 13: the judge profile accelerates on its own and maps nothing else."""
    m = default_mapping("SuperTuxKart")
    m["auto"] = {"rt": 1.0}
    state = Mapper(m).update(sig(yaw=0.4), {"anything": 1.0}, [], {})
    assert state.rt == 1.0 and state.buttons == frozenset()


def test_hard_puff_toggle_latches_and_unlatches_the_throttle():
    """The demo profile's accelerate: nobody can hold a puff for a whole race (docs/SPEC.md 10)."""
    mapper = Mapper(gesture_mapping("hard_puff", {"kind": "breath"}, "rt", "toggle"))
    puff = [SipPuffEvent(t_ns=0, kind="hard_puff")]

    assert mapper.update(sig(0), {}, puff, {}).rt == 1.0       # latches on the event tick
    assert mapper.update(sig(500), {}, [], {}).rt == 1.0       # stays latched with no events
    assert mapper.update(sig(1000), {}, puff, {}).rt == 0.0    # a second puff releases it


def test_breath_event_fires_a_tap_button():
    mapper = Mapper(gesture_mapping("soft_puff", {"kind": "breath"}, "Y", "tap"))
    state = mapper.update(sig(0), {}, [SipPuffEvent(t_ns=0, kind="soft_puff")], {})
    assert state.fired == ("soft_puff",) and "Y" in state.buttons


def test_a_breath_gesture_ignores_other_event_kinds():
    mapper = Mapper(gesture_mapping("hard_puff", {"kind": "breath"}, "rt", "toggle"))
    state = mapper.update(sig(0), {}, [SipPuffEvent(t_ns=0, kind="soft_sip")], {})
    assert state.rt == 0.0 and state.fired == ()


def test_fired_names_only_the_activation_tick():
    defn = {"kind": "blendshape", "sources": ["browInnerUp"], "on": 0.6, "off": 0.4}
    mapper = Mapper(gesture_mapping("brow_raise", defn, "A", "tap"))
    assert mapper.update(sig(0), {"brow_raise": 1.0}, [], {}).fired == ()     # minimum hold
    state = mapper.update(sig(100), {"brow_raise": 1.0}, [], {})
    assert state.fired == ("brow_raise",) and "A" in state.buttons
    held = mapper.update(sig(133), {"brow_raise": 1.0}, [], {})
    assert held.fired == () and "A" in held.buttons                          # still tapped, not re-fired


def test_button_target_can_be_a_trigger_pressed_full():
    defn = {"kind": "blendshape", "sources": ["jawOpen"], "on": 0.6, "off": 0.4}
    mapper = Mapper(gesture_mapping("jaw_open", defn, "lt", "hold"))
    mapper.update(sig(0), {"jaw_open": 1.0}, [], {})
    assert mapper.update(sig(100), {"jaw_open": 1.0}, [], {}).lt == 1.0


def test_fatigue_scale_lowers_the_activation_threshold():
    defn = {"kind": "blendshape", "sources": ["browInnerUp"], "on": 0.8, "off": 0.6}
    mapper = Mapper(gesture_mapping("brow_raise", defn, "A", "hold"))
    mapper.update(sig(0), {"brow_raise": 0.5}, [], {})
    assert not mapper.update(sig(100), {"brow_raise": 0.5}, [], {}).buttons

    weakened = Mapper(gesture_mapping("brow_raise", defn, "A", "hold"))
    weakened.update(sig(0), {"brow_raise": 0.5}, [], {"brow_raise": 0.5})
    state = weakened.update(sig(100), {"brow_raise": 0.5}, [], {"brow_raise": 0.5})
    assert "A" in state.buttons


def test_idle_tracks_gestures_and_axes():
    """P1's Normalizer reads this back for drift re-centering, so it is load-bearing."""
    defn = {"kind": "blendshape", "sources": ["browInnerUp"], "on": 0.6, "off": 0.4}
    mapper = Mapper(gesture_mapping("brow_raise", defn, "A", "hold"))
    mapper.update(sig(0), {}, [], {})
    assert mapper.idle
    mapper.update(sig(0), {"brow_raise": 1.0}, [], {})
    mapper.update(sig(100), {"brow_raise": 1.0}, [], {})
    assert not mapper.idle


def test_set_paused_forces_a_neutral_state():
    m = default_mapping("SuperTuxKart")
    m["auto"] = {"rt": 1.0}
    mapper = Mapper(m)
    mapper.set_paused(True)
    state = mapper.update(sig(0), {}, [], {})
    assert state.paused and state.rt == 0.0 and state.buttons == frozenset()
    mapper.set_paused(False)
    assert mapper.update(sig(10), {}, [], {}).rt == 1.0


def test_set_mapping_rebuilds_the_triggers():
    defn = {"kind": "blendshape", "sources": ["browInnerUp"], "on": 0.6, "off": 0.4}
    mapper = Mapper(gesture_mapping("brow_raise", defn, "A", "hold"))
    mapper.update(sig(0), {"brow_raise": 1.0}, [], {})
    assert "A" in mapper.update(sig(100), {"brow_raise": 1.0}, [], {}).buttons

    mapper.set_mapping(gesture_mapping("brow_raise", defn, "B", "hold"))
    mapper.update(sig(200), {"brow_raise": 1.0}, [], {})
    state = mapper.update(sig(300), {"brow_raise": 1.0}, [], {})
    assert "B" in state.buttons and "A" not in state.buttons
