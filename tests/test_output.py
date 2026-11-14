# OWNER: P2
"""Bootstrap checks for output.py: NullPad works with no gamepad driver installed."""
import pytest

from helm.contracts import ControlState
from helm.output import Gamepad, NullPad, make_gamepad


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
