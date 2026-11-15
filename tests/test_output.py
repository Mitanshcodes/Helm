# OWNER: P2
"""Bootstrap checks for output.py: NullPad works with no gamepad driver installed."""
import pytest

from helm.contracts import ControlState
from helm.output import Gamepad, NullPad, make_gamepad, second_gamepad


def test_null_pad_stores_last_state():
    pad = make_gamepad("null")
    assert isinstance(pad, NullPad) and isinstance(pad, Gamepad)
    state = ControlState(lx=0.5, buttons=frozenset({"A"}))
    pad.apply(state)
    assert pad.last is state
    pad.close()


def test_auto_always_returns_a_pad():
    assert isinstance(make_gamepad("auto"), Gamepad)


def test_unknown_backend_is_rejected():
    with pytest.raises(ValueError):
        make_gamepad("joystick")


def test_null_pad_starts_neutral():
    assert NullPad().last == ControlState()


def test_null_pad_replaces_state_including_released_buttons():
    pad = NullPad()
    pad.apply(ControlState(rt=1.0, buttons=frozenset({"A", "B"})))
    neutral = ControlState(paused=True)
    pad.apply(neutral)
    assert pad.last is neutral


def test_null_pads_have_independent_state():
    first = NullPad()
    second = NullPad()
    first.apply(ControlState(lx=1.0))
    assert second.last == ControlState()


# ---------------------------------------------------------------- real backends, with fake drivers
# vgamepad and pynput are imported lazily inside the backends, so a fake module in sys.modules
# exercises the diffing and clamping logic on any OS, with no driver and no real key presses.
import sys
import types

from helm import config
from helm.contracts import PAD_BUTTONS
from helm.output import KeyboardPad, VGamepadPad, _XUSB_NAMES, _clamp


class _FakeVPad:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.updates = 0

    def left_joystick_float(self, x_value_float, y_value_float):
        self.calls.append(("ls", x_value_float, y_value_float))

    def right_joystick_float(self, x_value_float, y_value_float):
        self.calls.append(("rs", x_value_float, y_value_float))

    def left_trigger_float(self, value_float):
        self.calls.append(("lt", value_float))

    def right_trigger_float(self, value_float):
        self.calls.append(("rt", value_float))

    def press_button(self, button):
        self.calls.append(("press", button))

    def release_button(self, button):
        self.calls.append(("release", button))

    def update(self):
        self.updates += 1

    def reset(self):
        self.calls.append(("reset",))


def _fake_vgamepad() -> types.ModuleType:
    mod = types.ModuleType("vgamepad")
    mod.XUSB_BUTTON = types.SimpleNamespace(**{x: f"<{x}>" for x in _XUSB_NAMES.values()})
    mod.VX360Gamepad = _FakeVPad
    return mod


class _FakeKeyboard:
    def __init__(self) -> None:
        self.held: set = set()

    def press(self, key):
        self.held.add(key)

    def release(self, key):
        self.held.discard(key)


def _fake_pynput() -> tuple[types.ModuleType, types.ModuleType]:
    pynput = types.ModuleType("pynput")
    keyboard = types.ModuleType("pynput.keyboard")

    class Key:
        left, right, up, down = "<left>", "<right>", "<up>", "<down>"
        space, backspace = "<space>", "<backspace>"

    class KeyCode:
        @staticmethod
        def from_char(char):
            return f"<char:{char}>"

    keyboard.Controller, keyboard.Key, keyboard.KeyCode = _FakeKeyboard, Key, KeyCode
    pynput.keyboard = keyboard
    return pynput, keyboard


@pytest.fixture
def vpad(monkeypatch):
    monkeypatch.setitem(sys.modules, "vgamepad", _fake_vgamepad())
    return VGamepadPad()


@pytest.fixture
def kbpad(monkeypatch):
    pynput, keyboard = _fake_pynput()
    monkeypatch.setitem(sys.modules, "pynput", pynput)
    monkeypatch.setitem(sys.modules, "pynput.keyboard", keyboard)
    return KeyboardPad()


def test_every_pad_button_has_an_xusb_name():
    """A missing entry would silently drop that button for the whole demo."""
    assert set(PAD_BUTTONS) == set(_XUSB_NAMES)


def test_clamp_bounds():
    assert _clamp(2.0) == 1.0 and _clamp(-2.0) == -1.0 and _clamp(0.25) == 0.25
    assert _clamp(-0.5, 0.0, 1.0) == 0.0


def test_vgamepad_taps_a_button_once_at_creation(vpad):
    """Without this tap the game may never notice the pad (docs/SPEC.md 6.7)."""
    a = f"<{_XUSB_NAMES['A']}>"
    assert vpad._pad.calls == [("press", a), ("release", a)]
    assert vpad._pad.updates == 2


def test_second_virtual_controller_is_independent_and_starts_without_a_button_press(vpad):
    second = second_gamepad(vpad)
    assert second._pad is not vpad._pad
    assert second._pad.calls == []
    second.apply(ControlState(buttons=frozenset({'B'})))
    assert second._pressed == frozenset({'B'})
    assert vpad._pressed == frozenset()


def test_keyboard_cannot_be_shared_as_two_controllers(kbpad):
    with pytest.raises(ValueError, match='keyboard'):
        second_gamepad(kbpad)


def test_vgamepad_presses_and_releases_only_changed_buttons(vpad):
    vpad._pad.calls.clear()
    vpad.apply(ControlState(buttons=frozenset({"A", "B"})))
    assert sorted(c for c in vpad._pad.calls if c[0] == "press") == [
        ("press", f"<{_XUSB_NAMES['A']}>"), ("press", f"<{_XUSB_NAMES['B']}>")]

    vpad._pad.calls.clear()
    vpad.apply(ControlState(buttons=frozenset({"B", "X"})))
    assert ("release", f"<{_XUSB_NAMES['A']}>") in vpad._pad.calls
    assert ("press", f"<{_XUSB_NAMES['X']}>") in vpad._pad.calls
    assert ("press", f"<{_XUSB_NAMES['B']}>") not in vpad._pad.calls   # B was already down


def test_vgamepad_updates_exactly_once_per_frame(vpad):
    before = vpad._pad.updates
    vpad.apply(ControlState(lx=0.5))
    assert vpad._pad.updates == before + 1


def test_vgamepad_clamps_axes_and_triggers(vpad):
    vpad._pad.calls.clear()
    vpad.apply(ControlState(lx=2.0, ly=-3.0, lt=5.0, rt=-1.0))
    assert ("ls", 1.0, -1.0) in vpad._pad.calls
    assert ("lt", 1.0) in vpad._pad.calls
    assert ("rt", 0.0) in vpad._pad.calls


def test_vgamepad_ignores_unknown_button_names(vpad):
    vpad.apply(ControlState(buttons=frozenset({"NOPE"})))   # validate_mapping is the real gate
    assert not any(c[0] == "press" for c in vpad._pad.calls[2:])


def test_keyboard_steering_switches_sides(kbpad):
    kbpad.apply(ControlState(lx=1.0))
    assert "<right>" in kbpad._kb.held
    kbpad.apply(ControlState(lx=-1.0))
    assert "<left>" in kbpad._kb.held and "<right>" not in kbpad._kb.held


def test_keyboard_inside_axis_threshold_holds_nothing(kbpad):
    kbpad.apply(ControlState(lx=config.KEYBOARD_AXIS_THRESHOLD / 2))
    assert kbpad._kb.held == set()


def test_keyboard_triggers_map_to_up_and_down(kbpad):
    kbpad.apply(ControlState(rt=1.0, lt=1.0))
    assert "<up>" in kbpad._kb.held and "<down>" in kbpad._kb.held


def test_keyboard_maps_buttons_through_config(kbpad):
    kbpad.apply(ControlState(buttons=frozenset({"A", "B"})))
    assert "<space>" in kbpad._kb.held        # config.KEYBOARD_KEYS["A"] == "space"
    assert "<char:n>" in kbpad._kb.held       # single chars go through KeyCode.from_char


def test_keyboard_neutral_state_releases_everything(kbpad):
    kbpad.apply(ControlState(lx=1.0, rt=1.0, buttons=frozenset({"A"})))
    kbpad.apply(ControlState())
    assert kbpad._kb.held == set()


def test_keyboard_close_releases_everything(kbpad):
    kbpad.apply(ControlState(lx=1.0, buttons=frozenset({"A"})))
    kbpad.close()
    assert kbpad._kb.held == set()


def test_auto_returns_nullpad_off_windows(monkeypatch):
    """A KeyboardPad on macOS would type into whatever window has focus. See decisions.md."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "vgamepad", _fake_vgamepad())
    assert isinstance(make_gamepad("auto"), NullPad)


def test_auto_prefers_vgamepad_on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "vgamepad", _fake_vgamepad())
    assert isinstance(make_gamepad("auto"), VGamepadPad)


def test_auto_falls_back_to_keyboard_when_vigembus_is_missing(monkeypatch):
    """The docs/SPEC.md 15 fallback: ViGEmBus will not install."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "vgamepad", None)     # None makes `import vgamepad` raise
    pynput, keyboard = _fake_pynput()
    monkeypatch.setitem(sys.modules, "pynput", pynput)
    monkeypatch.setitem(sys.modules, "pynput.keyboard", keyboard)
    assert isinstance(make_gamepad("auto"), KeyboardPad)


def test_auto_falls_back_to_null_when_no_driver_is_available(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "vgamepad", None)
    monkeypatch.setitem(sys.modules, "pynput", None)
    assert isinstance(make_gamepad("auto"), NullPad)
