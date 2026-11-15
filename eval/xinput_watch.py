"""Read Windows' actual Xbox-controller states while Helm and the game run.

    python eval/xinput_watch.py --seconds 30 --output xinput.jsonl

This is read-only: it creates no controllers and sends no inputs. Hold acceleration
on one player, then both, then release each independently. Indices are Windows'
0-based XInput slots, not Helm profile/controller labels. Disconnect other pads
if you want to attribute the observed devices to Helm unambiguously.
"""
import argparse
import ctypes
import json
import math
import sys
import time
from contextlib import nullcontext


class Gamepad(ctypes.Structure):
    # Fixed-width Windows types, even when imported by tests on another OS.
    _fields_ = [('buttons', ctypes.c_uint16), ('lt', ctypes.c_uint8), ('rt', ctypes.c_uint8),
                ('lx', ctypes.c_int16), ('ly', ctypes.c_int16),
                ('rx', ctypes.c_int16), ('ry', ctypes.c_int16)]


class State(ctypes.Structure):
    _fields_ = [('packet', ctypes.c_uint32), ('gamepad', Gamepad)]


def load_xinput():
    if sys.platform != 'win32':
        raise OSError('XInput monitoring must run on the Windows computer running Helm')
    for name in ('xinput1_4.dll', 'xinput1_3.dll', 'xinput9_1_0.dll'):
        try:
            dll = ctypes.WinDLL(name, winmode=0x800)  # Windows System32 only
        except OSError:
            continue
        read = dll.XInputGetState
        read.argtypes = (ctypes.c_uint32, ctypes.POINTER(State))
        read.restype = ctypes.c_uint32
        return read
    raise OSError('No Windows XInput DLL could be loaded')


def read_controllers(read):
    pads = []
    for index in range(4):
        state = State()
        status = read(index, ctypes.byref(state))
        if status == 1167:  # ERROR_DEVICE_NOT_CONNECTED
            continue
        if status != 0:
            raise OSError(status, f'XInputGetState failed for slot {index}')
        pad = state.gamepad
        pads.append(dict(index=index, packet=state.packet,
                         **{name: int(getattr(pad, name)) for name, _ in Gamepad._fields_}))
    return pads


def positive_seconds(text):
    value = float(text)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError('Use a finite positive number')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=positive_seconds, default=30)
    parser.add_argument('--output', help='Optional JSONL log of the OS-level states')
    args = parser.parse_args()
    try:
        read = load_xinput()
        with open(args.output, 'w', encoding='utf-8') if args.output else nullcontext(None) as log:
            print('Hold P1 accelerate, add P2, then release each independently. Ctrl+C stops.')
            print('RT/LT: 0-255; Xbox buttons: hex mask; slots: Windows indices (not Helm labels).')
            started = time.monotonic()
            while (elapsed := time.monotonic() - started) < args.seconds:
                pads = read_controllers(read)
                row = dict(time_s=round(elapsed, 3), controllers=pads)
                if log:
                    log.write(json.dumps(row) + '\n')
                    log.flush()
                description = ' | '.join(f"slot {p['index']}: RT={p['rt']:3} LT={p['lt']:3} "
                                         f"LX={p['lx']:6} buttons={p['buttons']:04x}" for p in pads)
                print(f'{elapsed:5.1f}s  {description or "No XInput controllers connected"}', flush=True)
                time.sleep(.1)
    except KeyboardInterrupt:
        pass
    except OSError as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
