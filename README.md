<!-- OWNER: P4 -->
# Helm

This is the [experimental ML branch of Helm](https://github.com/Mitanshcodes/Helm/tree/experimental/identity-and-geometry).
It includes experimental [single-player face protection](docs/IDENTITY.md), full 3D landmark
capture, and an offline identity evaluator. Gesture-feature studies remain separate from the
operational classifier; see [docs/EXPERIMENTAL_ML.md](docs/EXPERIMENTAL_ML.md).

**A game controller you steer with your face. Play with whatever moves.**

Helm turns a webcam into an Xbox 360 controller, designed for gamers with limited hand and arm
movement. Head movement drives the analog stick, facial expressions press buttons and drive the
triggers, and Helm learns each player's own range and gestures, including small or one-sided ones.
An optional straw and pressure sensor add breath input. Because Helm shows up to Windows as a real
controller, it works with any game that accepts one, with no mods.

Built at HackPrinceton Fall '26 by a team of four.

> Status: in progress. Camera, face tracking, calibration, mapping, the virtual controller, the
> coach and the dashboard are built. Learned gestures, fatigue adaptation and the evaluation are
> still being built, so the Results section has no numbers yet.

## How it works

1. **Launch.** The dashboard shows the camera with your face outlined, so you can see Helm is tracking you.
2. **Calibrate (under 45 seconds, no clicks).** Relax, turn your head each way as far as is
   comfortable, then make five expressions three times each. Helm records your own limits, so a
   small movement can still mean full stick, and marks each expression reliable or not for you.
3. **Teach a gesture (optional).** Name any movement, do it five times, then talk and look around
   so Helm learns what not to fire on.
4. **Pick a game.** A coach agent reads the game's controls and your reliable gestures, and
   proposes a mapping. After a session it can review what happened and suggest changes.
5. **Play.** Close your eyes for one second to pause or resume.

Everything runs on the laptop. Video stays on the laptop and is saved only when dev mode is
explicitly enabled. During ordinary play, only numbers (head pose, expression scores) move between
modules. The coach sees a game name, gesture names and numbers,
never an image, and falls back to a built-in mapping when there is no network.

## Setup

Python 3.11 and Node 18 or newer. From the repo root:

```bash
pip install -r requirements.txt
cd ui && npm install && npm run build
```

- **Windows (the demo platform):** the virtual Xbox controller needs the ViGEmBus driver, which the
  `vgamepad` installer offers to install. Without it Helm falls back to keyboard emulation.
- **macOS and Linux:** everything runs except the virtual controller, which is enough for development.
- **Coach (optional):** set `HELM_COACH_MODEL` (a `provider:model` string, default
  `anthropic:claude-opus-5-5`) and that provider's API key. Without them the coach uses its offline default.

## Run

```bash
python -m helm                                  # real camera; open http://localhost:8000
python -m helm --player sam --game SuperTuxKart
python -m helm --mock --output null             # no camera, no gamepad: works on any laptop
python -m helm --record run.npz                 # save face features (no images) while running
python -m helm --replay run.npz                 # replay a saved run instead of the camera
python -m helm --dev                            # save calibration/enrollment video; enable debug recording
```

Create the virtual controller (start Helm) before launching the game, or the game may not see it.

Dashboard, served by Helm itself once `npm run build` has run:

| Address | What it is |
|---|---|
| `http://localhost:8000/` | The full dashboard. Calibration starts by itself the first time. |
| `http://localhost:8000/?quick=1` | Same, with a two-second quick calibration (for a first-time visitor). |
| `http://localhost:8000/?overlay=1` | Read-only camera/face-mesh preview above a live Xbox-style controller. Silent, no automatic calibration. |
| `http://localhost:8000/?mock=1` | The dashboard on made-up data, with no pipeline behind it. |
| `http://localhost:8000/slides.html` | The pitch slides. Arrow keys or a click move between them. |

Running the demo table: **Next visitor** in the header loads the `judge` profile and starts a quick
calibration, so each new person starts clean. The **Table setup** card switches between saved
profiles and turns two things on or off: reading setup prompts aloud (so a player turning their
head away from the screen still hears what to do) and a soft click when an input fires. Browsers
keep the page silent until it has been clicked once, so click anywhere on the dashboard after opening it.

For dashboard development, `cd ui && npm run dev` serves it on `http://localhost:5173` with live
reload, talking to a running `python -m helm` (or to nothing, with `?mock=1`).

### Dev datasets

Enable **Dev mode** in the dashboard or launch with `--dev` before calibrating or teaching gestures.
Calibration and enrollment are recorded automatically, with matching `calibration.json` and
`gestures.npz` files. **Record debug dataset** starts a separate video with frame-aligned raw
features, model scores, gesture activations and controller output. Stop it with **Stop recording**.

Datasets go to `artifacts/dev-datasets/` (ignored by Git); use `--dev-dir /path/to/datasets` to
choose another directory. See [the dev recording guide](docs/DEV_MODE.md) for the file format,
timestamps and completion checks.

### Windows game overlay

Build the UI with `cd ui && npm run build`, then start Helm normally. In a second terminal
using the same Python environment, launch the independent always-on-top viewer:

```bash
python -m pip install pywebview
python -m helm.overlay
```

The window shows the mirrored camera with MediaPipe face contours on top and a controller
underneath: both sticks, LT/RT percentages, ABXY, shoulders, D-pad, Start/Back and stick clicks.
It displays Helm's mapped output; it does not read a physical controller or confirm that the game
received it. Closing the viewer leaves Helm and the game running. Calibrate and change profiles
from the main dashboard.

Use a windowed or borderless game; exclusive fullscreen is outside this viewer's support.
Move/resize the viewer with its normal title bar and edges, then switch focus back to the game.
This first version is an opaque window and intercepts clicks inside its bounds. It requires the
[Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/).
If unavailable, the launcher prints a browser fallback.

```bash
python -m helm.overlay --port 8000 --width 400 --height 780
python -m helm.overlay --no-top           # ordinary native window
python -m helm.overlay --browser          # browser viewer on any OS (not always on top)
python -m helm.overlay --browser --mock   # simulated UI inputs; Helm still serves the built page
```

The viewer reconnects automatically and clears displayed inputs when disconnected or when no
state arrives for 1.5 seconds. Camera preview and controller updates use the existing 15/30 Hz
streams; it does not open another webcam or create another gamepad.

Profiles for SuperTuxKart are in `profiles/`: `demo` (webcam plus breath sensor), `demo_webcam`
(webcam only) and `judge` (head steering, automatic throttle, eyebrow raise fires an item; nothing
else is mapped, so talking cannot trigger anything).

## Tests

```bash
python -m pytest -q
python -m helm --mock --output null --no-server --seconds 3   # smoke run, must exit 0
```

## Architecture

One Python process, plus the React dashboard and an optional ESP32 breath sensor.

```
Webcam -> capture thread -> pipeline thread (one pass per new frame) -> virtual Xbox controller
            FaceTracker -> Normalizer -> GestureEngine -> FatigueTracker -> Mapper -> Gamepad
                                |
                      latest snapshot -> WebSocket server -> dashboard
ESP32 -> serial thread -> breath level and sip/puff events -> pipeline thread
Coach agent -> worker thread, on request; never on the pipeline thread
```

- **Capture** keeps only the newest frame. Threads share "latest value" slots that overwrite, so a
  slow consumer drops stale data instead of building lag.
- **Face tracking** is MediaPipe Face Landmarker: head pose plus 52 expression scores per frame.
- **Profile identity (experimental)** selects the enrolled person's face before control processing.
  Unknown or uncertain faces lock the controller; [setup is explicit](docs/IDENTITY.md).
- **Normalizer** removes your neutral pose, scales to your calibrated range, and smooths with a One Euro filter.
- **Gestures** are expression thresholds with hysteresis, plus a personalized logistic classifier
  for learned gestures with a "none" class and temporal confirmation.
- **Mapper** turns signals into stick, trigger and button states. If the face is lost, or
  calibration or recording is active, the controller goes neutral.
- **Output** is `vgamepad` over ViGEmBus, with keyboard emulation as the fallback.
- **Server** is FastAPI with one WebSocket: state 30 times a second, a preview frame 15 times a
  second, commands back. The dashboard is React, Vite and TypeScript with plain CSS.
- Every frame is stamped at capture, after inference and after the controller write, so latency is
  measured, not estimated.

The full design is in [docs/SPEC.md](docs/SPEC.md).

## Results

Not measured yet. Three numbers will go here, each beside a baseline, with a participant count:

| Measure | Helm | Baseline |
|---|---|---|
| Motion-to-screen latency (median, 240 fps video) | pending | a finger on a real controller |
| False triggers per minute while talking and watching | pending | one fixed threshold, no calibration |
| Target-test throughput with restricted movement | pending | fixed gain, no per-player scaling |

The method is in [eval/PROTOCOL.md](eval/PROTOCOL.md).

**Limitation:** no evaluation participant has a motor impairment. The restricted-range condition
is a proxy, not a substitute. Testing with the people Helm is designed for is the first step after
the hackathon.

## What's next

- User testing, by reaching out to organizations such as AbleGamers and Makers Making Change.
- A Linux backend, a mouse-and-keyboard mode, and a shared library of per-game profiles.
- The same pipeline for desktop navigation and communication shortcuts.

Helm is free for players.
