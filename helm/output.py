# OWNER: P2
"""Gamepad backends: vgamepad, keyboard, null (docs/SPEC.md 6.7). Bootstrap: only NullPad works."""
from helm.contracts import ControlState


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


class VGamepadPad(Gamepad):
    def __init__(self) -> None:
        # TODO(P2): import vgamepad here; VX360Gamepad(); tap one button once after creation;
        # in apply() only press or release buttons whose state changed, then update().
        raise NotImplementedError("vgamepad backend is not implemented yet; use --output null")


class KeyboardPad(Gamepad):
    def __init__(self) -> None:
        # TODO(P2): import pynput here; lx beyond +-0.3 holds Right/Left, rt > 0.3 holds Up,
        # lt > 0.3 holds Down, buttons map through config.KEYBOARD_KEYS.
        raise NotImplementedError("keyboard backend is not implemented yet; use --output null")


def make_gamepad(kind: str = "auto") -> Gamepad:
    """auto: vgamepad on Windows if importable, else keyboard, else null."""
    if kind == "auto":
        return NullPad()   # TODO(P2): pick a real backend once one exists
    if kind == "null":
        return NullPad()
    if kind == "vgamepad":
        return VGamepadPad()
    if kind == "keyboard":
        return KeyboardPad()
    raise ValueError(f"unknown gamepad backend: {kind}")
