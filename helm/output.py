# OWNER: P2
"""Gamepad backends: vgamepad, keyboard, null (docs/SPEC.md 6.7)."""
import sys

from helm import config
from helm.contracts import ControlState


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


class Gamepad:
    """Base class. apply() is called once per frame from the pipeline thread."""

    def apply(self, state: ControlState) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class NullPad(Gamepad):
    """Stores the last state. Used by tests, mock mode and macOS development."""

    def __init__(self) -> None:
        self.last = ControlState()

    def apply(self, state: ControlState) -> None:
        self.last = state


# ControlState button name -> vgamepad XUSB_BUTTON member name.
_XUSB_NAMES = {
    "A": "XUSB_GAMEPAD_A",
    "B": "XUSB_GAMEPAD_B",
    "X": "XUSB_GAMEPAD_X",
    "Y": "XUSB_GAMEPAD_Y",
    "LB": "XUSB_GAMEPAD_LEFT_SHOULDER",
    "RB": "XUSB_GAMEPAD_RIGHT_SHOULDER",
    "START": "XUSB_GAMEPAD_START",
    "BACK": "XUSB_GAMEPAD_BACK",
    "DPAD_UP": "XUSB_GAMEPAD_DPAD_UP",
    "DPAD_DOWN": "XUSB_GAMEPAD_DPAD_DOWN",
    "DPAD_LEFT": "XUSB_GAMEPAD_DPAD_LEFT",
    "DPAD_RIGHT": "XUSB_GAMEPAD_DPAD_RIGHT",
    "LS": "XUSB_GAMEPAD_LEFT_THUMB",
    "RS": "XUSB_GAMEPAD_RIGHT_THUMB",
}


class VGamepadPad(Gamepad):
    """Virtual Xbox 360 pad through ViGEmBus. Windows only."""

    def __init__(self) -> None:
        import vgamepad   # lazy: Windows only, and only when this backend is chosen

        self._pad = vgamepad.VX360Gamepad()
        self._buttons = {
            name: getattr(vgamepad.XUSB_BUTTON, xusb)
            for name, xusb in _XUSB_NAMES.items()
            if hasattr(vgamepad.XUSB_BUTTON, xusb)
        }
        self._pressed: frozenset[str] = frozenset()
        # Tap one button once after creation or the game may never notice the pad.
        a = self._buttons["A"]
        self._pad.press_button(button=a)
        self._pad.update()
        self._pad.release_button(button=a)
        self._pad.update()

    def apply(self, state: ControlState) -> None:
        self._pad.left_joystick_float(x_value_float=_clamp(state.lx), y_value_float=_clamp(state.ly))
        self._pad.right_joystick_float(x_value_float=_clamp(state.rx), y_value_float=_clamp(state.ry))
        self._pad.left_trigger_float(value_float=_clamp(state.lt, 0.0, 1.0))
        self._pad.right_trigger_float(value_float=_clamp(state.rt, 0.0, 1.0))

        want = frozenset(b for b in state.buttons if b in self._buttons)
        for name in self._pressed - want:            # only buttons whose state changed
            self._pad.release_button(button=self._buttons[name])
        for name in want - self._pressed:
            self._pad.press_button(button=self._buttons[name])
        self._pressed = want

        self._pad.update()                            # one update per frame

    def close(self) -> None:
        try:
            self._pad.reset()
            self._pad.update()
        except Exception:
            pass


class KeyboardPad(Gamepad):
    """pynput fallback for when ViGEmBus is unavailable (docs/SPEC.md 15)."""

    def __init__(self) -> None:
        from pynput.keyboard import Controller, Key, KeyCode   # lazy

        self._kb = Controller()
        self._axis_keys = {"left": Key.left, "right": Key.right, "up": Key.up, "down": Key.down}
        self._keys = {}
        for button, name in config.KEYBOARD_KEYS.items():
            key = getattr(Key, name, None)
            if key is None and len(name) == 1:
                key = KeyCode.from_char(name)
            if key is not None:
                self._keys[button] = key
        self._held: set = set()

    def apply(self, state: ControlState) -> None:
        want: set = set()
        if state.lx >= config.KEYBOARD_AXIS_THRESHOLD:
            want.add(self._axis_keys["right"])
        elif state.lx <= -config.KEYBOARD_AXIS_THRESHOLD:
            want.add(self._axis_keys["left"])
        if state.rt > config.KEYBOARD_TRIGGER_THRESHOLD:
            want.add(self._axis_keys["up"])
        if state.lt > config.KEYBOARD_TRIGGER_THRESHOLD:
            want.add(self._axis_keys["down"])
        for button in state.buttons:
            key = self._keys.get(button)
            if key is not None:
                want.add(key)

        for key in self._held - want:                 # only keys whose state changed
            self._kb.release(key)
        for key in want - self._held:
            self._kb.press(key)
        self._held = want

    def close(self) -> None:
        for key in self._held:
            try:
                self._kb.release(key)
            except Exception:
                pass
        self._held = set()


def make_gamepad(kind: str = "auto") -> Gamepad:
    """auto: vgamepad on Windows if importable, else keyboard, else null.

    The vgamepad -> keyboard chain is Windows-only on purpose: on macOS and Linux `auto` returns
    NullPad, because a KeyboardPad there would type into whatever window has focus during
    development. See decisions.md.
    """
    if kind == "null":
        return NullPad()
    if kind == "vgamepad":
        return VGamepadPad()
    if kind == "keyboard":
        return KeyboardPad()
    if kind != "auto":
        raise ValueError(f"unknown gamepad backend: {kind}")

    if sys.platform != "win32":
        return NullPad()
    try:
        return VGamepadPad()
    except Exception:
        pass
    try:
        return KeyboardPad()
    except Exception:
        return NullPad()
