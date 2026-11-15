"""Check the raw Windows readback adapter without touching real gamepads."""
import ctypes

import pytest

from eval.xinput_watch import Gamepad, State, read_controllers


def test_readback_keeps_simultaneous_triggers_on_distinct_windows_slots():
    def read(index, pointer):
        if index not in (1, 3):
            return 1167
        state = ctypes.cast(pointer, ctypes.POINTER(State)).contents
        state.packet = 19
        state.gamepad.rt = 255
        state.gamepad.lt = 0
        state.gamepad.lx = -12000 if index == 1 else 12000
        state.gamepad.buttons = 0x1000
        return 0

    pads = read_controllers(read)
    assert [p['index'] for p in pads] == [1, 3]
    assert [p['rt'] for p in pads] == [255, 255]
    assert [p['lx'] for p in pads] == [-12000, 12000]
    assert ctypes.sizeof(Gamepad) == 12 and ctypes.sizeof(State) == 16


def test_readback_reports_unexpected_windows_errors():
    with pytest.raises(OSError, match='XInputGetState failed'):
        read_controllers(lambda index, pointer: 5)
