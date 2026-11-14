<!-- OWNER: P4 -->
# Helm

Helm turns a webcam into an Xbox 360 controller for people who cannot hold one. Head movement drives
the analog stick, facial expressions press buttons and drive the triggers, and Helm learns each
player's own range and gestures, including small or one-sided ones. An optional straw and pressure
sensor add breath input.

Built at HackPrinceton Fall '26 by a team of four.

> Status: bootstrap. The repo tree, the shared contracts and a mock pipeline are in place. The
> camera, the gamepad output, learned gestures and the dashboard are being built.

## Setup

Python 3.11 and Node 18 or newer. From the repo root:

```bash
pip install -r requirements.txt
cd ui && npm install
```

On Windows, the virtual Xbox controller also needs the ViGEmBus driver.

## Run

```bash
python -m helm                        # real camera, picks the gamepad backend
python -m helm --mock --output null   # no camera, no gamepad: works on any laptop
python -m helm --record run.npz       # save face features while running
python -m helm --replay run.npz       # replay a saved run instead of the camera

cd ui && npm run dev                  # dashboard on http://localhost:5173
```

Tests and the smoke run:

```bash
python -m pytest -q
python -m helm --mock --output null --no-server --seconds 3
```

## Architecture

One Python process, plus the React dashboard and an optional ESP32 breath sensor.

```
Webcam -> capture thread -> pipeline thread -> virtual gamepad
            FaceTracker -> Normalizer -> GestureEngine -> FatigueTracker -> Mapper -> Gamepad
                                |
                      latest snapshot -> WebSocket server -> dashboard
ESP32 -> serial thread -> breath level and sip/puff events -> pipeline thread
```

The full design is in [docs/SPEC.md](docs/SPEC.md).

## Results

TODO(P4): latency, false triggers per minute and target-test throughput, each beside its baseline.
