<!-- OWNER: P4 -->
# Helm

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

Everything runs on the laptop. Video never leaves it and is never saved; only numbers (head pose,
expression scores) move between modules. The coach sees a game name, gesture names and numbers,
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
```

Create the virtual controller (start Helm) before launching the game, or the game may not see it.

Dashboard, served by Helm itself once `npm run build` has run:

| Address | What it is |
|---|---|
| `http://localhost:8000/` | The full dashboard. Calibration starts by itself the first time. |
| `http://localhost:8000/?quick=1` | Same, with a two-second quick calibration (for a first-time visitor). |
| `http://localhost:8000/?overlay=1` | Compact view for a small window beside the game. Silent unless you add `&sound=1`. |
| `http://localhost:8000/?mock=1` | The dashboard on made-up data, with no pipeline behind it. |
| `http://localhost:8000/slides.html` | The pitch slides. Arrow keys or a click move between them. |

Running the demo table: **Next visitor** in the header loads the `judge` profile and starts a quick
calibration, so each new person starts clean. The **Table setup** card switches between saved
profiles and turns two things on or off: reading setup prompts aloud (so a player turning their
head away from the screen still hears what to do) and a soft click when an input fires. Browsers
keep the page silent until it has been clicked once, so click anywhere on the dashboard after opening it.

For dashboard development, `cd ui && npm run dev` serves it on `http://localhost:5173` with live
reload, talking to a running `python -m helm` (or to nothing, with `?mock=1`).

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
- **Normalizer** removes your neutral pose, scales to your calibrated range, and smooths with a One Euro filter.
- **Gestures** are expression thresholds with hysteresis, plus a k-nearest-neighbour classifier
  for learned gestures with a "none" class.
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
