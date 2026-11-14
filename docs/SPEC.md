# Helm: technical specification

How to use this file: read section 5 (contracts) and the subsection of section 6 for the file
you are editing. Read other sections only when your task touches them. Numbers marked "start
value" are meant to be tuned on the demo laptop and then stored in `helm/config.py`.

Contents: 1 Product and judging · 2 Priorities · 3 Architecture · 4 Repo tree and owners ·
5 Contracts · 6 Modules · 7 Files on disk · 8 WebSocket protocol · 9 Dashboard · 10 Sip-and-puff
hardware · 11 Coach agent · 12 Evaluation · 13 Demo profiles · 14 Bootstrap and lane plans ·
15 Fallbacks

---

## 1. Product and judging

Helm turns a webcam into an Xbox 360 controller for people who cannot hold one. Head movement
drives the analog stick, facial expressions press buttons and drive analog triggers, and Helm
learns each player's own range and gestures, including small or one-sided ones. A straw and a
pressure sensor add breath input.

The player's flow, with no mouse after launch:

1. Launch. The dashboard shows the camera with a face mesh.
2. Calibrate (under 45 s, auto-advancing): neutral, head range, expression check.
3. Optional: teach a personal gesture (five takes, then 15 s of talking and looking around).
4. Pick a game. The coach proposes a mapping from the gestures marked reliable.
5. Play. An overlay shows which inputs fire. Eyes closed for one second pauses.
6. Helm keeps adapting: neutral re-centers slowly; thresholds drop if a gesture weakens.

What is scored (so trade-offs go the right way):

- Main track rubric, four criteria: Creativity (the "ah-ha" moment), Utility (does it function,
  how deep), Charity (a specific societal need), Avidity (polish, Devpost, future plans).
- Each judge gets a presentation of at most two minutes. At least three judges visit, plus
  special-track judges. The demo will run eight or more times, with strangers in the chair.
- Entered: Entertainment (main track), Best Hardware Hack, Best Practical AI Innovation (Amazon:
  agentic behavior, adaptive intelligence, usefulness, user experience), Best Physical AI Hack
  (AI inside a physical hardware build), Best use of deepagents (LangChain).

Consequences for the build: the judge quick-start path must work for a stranger in 15 seconds;
the learned gesture and "talking does not fire inputs" must be visible; breath input must be part
of the main demo, not a side note; the coach must be a real agent loop, not one LLM call.

---

## 2. Priorities

Default build order. Musts come before Shoulds unless the user says otherwise.

| # | Feature | Priority | Owner |
|---|---|---|---|
| 1 | Virtual Xbox pad output, keyboard fallback | Must | P2 |
| 2 | Head pose to left stick, scaled to the player's range | Must | P1 |
| 3 | Expression buttons (hysteresis) and analog triggers | Must | P2 |
| 4 | Calibration: neutral, range, expression check; quick mode for judges | Must | P1 |
| 5 | Dashboard: camera + mesh, gauges, fired inputs, fps and latency, auto-advancing wizard | Must | P4 |
| 6 | Learned personal gestures with a "none" class | Must (the differentiator) | P3 |
| 7 | Pause gesture, face-lost safety | Must | P2, P1 |
| 8 | Profiles: save and load calibration, gestures, mapping | Must | P2 |
| 9 | Evaluation: latency, false triggers, restricted-range target test | Must (trimmed, see 12) | P3 |
| 10 | Sip-and-puff: events, analog level, latched throttle | Should (first) | P2 |
| 11 | Coach agent on deepagents: build mapping, review a session | Should | P1 |
| 12 | Drift re-centering (P1) and fatigue adaptation (P3) | Should | P1, P3 |
| 13 | Gesture-recording UI and mapping view | Should | P4 |
| 14 | Hands-free recalibrate while paused, audio tick on fire, voice commands | Stretch | whoever is free |


---

## 3. Architecture

One Python process, four threads, plus the React dashboard and the ESP32.

```
Webcam -> [capture thread] -> latest frame slot
                                   |
                         [pipeline thread]  (one pass per new frame)
     FaceTracker -> Normalizer -> GestureEngine -> FatigueTracker -> Mapper -> Gamepad
          P1           P1             P3               P3             P2        P2
                                   |
                          latest snapshot slot -> [server: asyncio] <-> dashboard (WebSocket)
ESP32 -> [serial thread] -> breath level + sip/puff events -> read by the pipeline thread
Coach agent runs in a worker thread on request and never touches the pipeline thread.
```

- Capture thread: reads frames continuously, keeps only the newest, stamps `t_capture_ns`.
- Pipeline thread: waits for a new frame, runs every stage in order, writes the gamepad, stamps
  `t_output_ns`, publishes a snapshot. Vision and control share this thread on purpose: control
  only has new information when a new frame has been processed.
- Serial thread: reads the ESP32 at 100 Hz.
- Server: uvicorn on the main thread. Broadcasts the snapshot at 30 Hz and a preview JPEG at
  15 fps; receives commands and calls `Runtime` methods.

Latency accounting per frame: `vision_ms = t_infer - t_capture`, `control_ms = t_output - t_infer`,
`total_ms = t_output - t_capture`. These are software latency. Motion-to-screen latency is
measured separately with slow-motion video (section 12).

---

## 4. Repo tree and owners

```
helm/                         repo root
  CLAUDE.md                   shared   project rules for Claude Code
  CLAUDE.local.md             personal one line "LANE: Pn" (gitignored)
  README.md                   P4       what Helm is, setup, how to run, architecture, results
  requirements.txt            shared   append only
  .gitignore                  shared
  helm/                       Python package
    __init__.py               shared   empty
    __main__.py               P1       calls main.main()
    contracts.py              shared   dataclasses and constants; FROZEN after bootstrap
    config.py                 shared   tunables, one section per lane
    main.py                   P1       Runtime: threads, pipeline loop, CLI
    capture.py                P1       camera thread, latest-frame slot
    vision.py                 P1       Face Landmarker wrapper -> FrameFeatures
    mock.py                   P1       mock source, record, replay
    filters.py                P1       One Euro, axis shaping, Normalizer, drift
    calibration.py            P1       Calibrator state machine (full and quick)
    coach.py                  P1       deepagents coach: build mapping, review session
    games.json                P1       control schemes of a few games, for the coach
    output.py                 P2       gamepad backends: vgamepad, keyboard, null
    mapping.py                P2       Trigger state machine, Mapper -> ControlState
    profiles.py               P2       load, save, validate calibration and mappings
    sipnpuff.py               P2       serial thread, breath level, sip/puff events
    gestures.py               P3       TakeRecorder, GestureModel (k-NN), GestureEngine
    adapt.py                  P3       FatigueTracker
    server.py                 P4       FastAPI + WebSocket, preview encoding
  firmware/sipnpuff/sipnpuff.ino  P2   ESP32 streams raw pressure
  ui/                         P4       React + Vite + TypeScript dashboard
    src/App.tsx  ws.ts  types.ts  styles.css
    src/components/CameraView.tsx  Gauges.tsx  Wizard.tsx  GestureRecorder.tsx
                   MappingView.tsx  CoachPanel.tsx  StatusBar.tsx
  eval/                       P3
    false_triggers.py         replays recorded sessions through baseline and full Helm
    latency.html              flashes a square when button A registers
    target_test.html          ring-of-targets test driven by the virtual pad
    analysis.py               reads eval/results/*.csv, writes the three charts
    PROTOCOL.md               how to run each eval, step by step
    results/                  csv and png (committed)
  profiles/                   P2       see section 7
  models/face_landmarker.task P1       committed so the demo runs offline
  tests/test_<module>.py      owner of that module
  docs/SPEC.md                shared   this file (captain edits)
  docs/status/P1.md .. P4.md  each lane's running notes
```

Work is balanced over time rather than by file count: P1 carries the critical path early
(camera to stick, then calibration), then builds the coach; P2 carries output, mapping
and all hardware; P3 carries the learning differentiator and every number on the slide; P4
carries the server, the whole dashboard, and the Devpost, slides and video.

---

## 5. Contracts (`helm/contracts.py`, frozen)

Write this file exactly as below at bootstrap. Everything that crosses a module boundary is one
of these types.

```python
from dataclasses import dataclass, field
import numpy as np

AXES = ("yaw", "pitch", "roll")
PAD_AXES = ("lx", "ly", "rx", "ry")                 # each in [-1, 1]; ly/ry positive = up
PAD_TRIGGERS = ("lt", "rt")                         # each in [0, 1]
PAD_BUTTONS = ("A", "B", "X", "Y", "LB", "RB", "START", "BACK",
               "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT", "LS", "RS")
BREATH_EVENTS = ("soft_sip", "hard_sip", "soft_puff", "hard_puff")
BLENDSHAPE_NAMES: tuple[str, ...] = (               # expected MediaPipe output order. On the first real
    "_neutral", "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight",
    "cheekPuff", "cheekSquintLeft", "cheekSquintRight", "eyeBlinkLeft", "eyeBlinkRight",
    "eyeLookDownLeft", "eyeLookDownRight", "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft",
    "eyeLookOutRight", "eyeLookUpLeft", "eyeLookUpRight", "eyeSquintLeft", "eyeSquintRight",
    "eyeWideLeft", "eyeWideRight", "jawForward", "jawLeft", "jawOpen", "jawRight", "mouthClose",
    "mouthDimpleLeft", "mouthDimpleRight", "mouthFrownLeft", "mouthFrownRight", "mouthFunnel",
    "mouthLeft", "mouthLowerDownLeft", "mouthLowerDownRight", "mouthPressLeft", "mouthPressRight",
    "mouthPucker", "mouthRight", "mouthRollLower", "mouthRollUpper", "mouthShrugLower",
    "mouthShrugUpper", "mouthSmileLeft", "mouthSmileRight", "mouthStretchLeft", "mouthStretchRight",
    "mouthUpperUpLeft", "mouthUpperUpRight", "noseSneerLeft", "noseSneerRight",
)                                                   # inference, P1 compares this with the model's own
                                                    # category names and corrects it before anyone relies on it
N_BLEND = 52
FEATURE_DIM = 56                                    # 52 blend deltas + yaw, pitch, roll + breath

@dataclass(slots=True)
class FrameFeatures:                                # P1 vision -> everyone
    seq: int
    t_capture_ns: int
    t_infer_ns: int
    face: bool
    yaw: float = 0.0                                # degrees, raw; + = player turns to their own right
    pitch: float = 0.0                              # + = chin up
    roll: float = 0.0                               # + = tilt toward their own right shoulder
    blend: np.ndarray = field(default_factory=lambda: np.zeros(N_BLEND, np.float32))
    landmarks: np.ndarray | None = None             # (478, 2) float32 in [0, 1], for the preview only

@dataclass(slots=True)
class Calibration:                                  # P1 calibration -> P2 profiles, P3 gestures
    player: str
    mode: str                                       # "full" | "quick" | "default"
    neutral: dict[str, float]                       # per axis, degrees
    range: dict[str, tuple[float, float]]           # per axis: (negative limit, positive limit), degrees, both > 0
    blend_neutral: list[float]                      # 52 resting scores
    blend_peak: dict[str, float]                    # blendshape name -> player's median peak (raw score)
    reliable: list[str]                             # blendshape names that passed the expression check

@dataclass(slots=True)
class Signals:                                      # P1 Normalizer -> P3, P2
    seq: int
    t_capture_ns: int
    t_infer_ns: int
    face: bool
    axes: dict[str, float]                          # yaw/pitch/roll in [-1, 1]: neutral removed, scaled to the
                                                    # player's range, One Euro filtered. No dead zone or curve.
    expr: np.ndarray                                # (52,) in [0, 1]: (blend - neutral) / (peak - neutral)
    delta: np.ndarray                               # (56,) classifier features: blend - neutral, axes, breath
    breath: float                                   # [-1, 1]; + puff, - sip; 0.0 with no device

@dataclass(slots=True)
class SipPuffEvent:                                 # P2 sipnpuff -> P2 mapping
    t_ns: int
    kind: str                                       # one of BREATH_EVENTS

@dataclass(slots=True)
class ControlState:                                 # P2 mapping -> P2 output, P4 server
    t_output_ns: int = 0
    lx: float = 0.0
    ly: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    lt: float = 0.0
    rt: float = 0.0
    buttons: frozenset[str] = frozenset()
    paused: bool = False
    fired: tuple[str, ...] = ()                     # gesture names that fired on this tick

@dataclass(slots=True)
class Progress:                                     # wizard and recorder -> server -> dashboard
    active: bool
    step: str                                       # machine name, e.g. "neutral", "yaw_left", "take_3", "negatives"
    prompt: str                                     # sentence shown large to the player
    progress: float                                 # 0..1 within the step
    overall: float                                  # 0..1 across the whole flow
    done: bool = False
```

Activations are a plain `dict[str, float]`: gesture name to a level in [0, 1]. Mappings and
snapshots are plain dicts in the shapes given in sections 7 and 8.

---

## 6. Modules

Each subsection gives the public interface (keep it exactly), the behavior, start values, and
what "done" means. Internal helpers are up to the owner.

### 6.1 `capture.py` (P1)

```python
class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 60): ...
    def start(self) -> None
    def stop(self) -> None
    def wait_latest(self, last_seq: int, timeout: float = 0.5) -> tuple[np.ndarray, int, int] | None
        # blocks until a frame newer than last_seq exists; returns (bgr, t_capture_ns, seq)
```

- Windows: `cv2.VideoCapture(index, cv2.CAP_DSHOW)`; set FOURCC `MJPG`, width, height, fps,
  `CAP_PROP_BUFFERSIZE = 1`. Log the fps the camera actually delivers.
- A daemon thread loops `read()` and overwrites one slot under a lock; `t_capture_ns` is taken
  right after `read()` returns. A `threading.Condition` wakes `wait_latest`.
- Done: 30+ fps steady at 640x480 on the demo laptop; 60 on a 60 fps webcam.

### 6.2 `vision.py` (P1)

```python
class FaceTracker:
    def __init__(self, model_path: str = "models/face_landmarker.task"): ...
    def process(self, bgr: np.ndarray, t_capture_ns: int, seq: int) -> FrameFeatures
    def close(self) -> None
```

- MediaPipe Tasks `FaceLandmarker`, running mode `VIDEO`, `num_faces=1`,
  `output_face_blendshapes=True`, `output_facial_transformation_matrixes=True`.
- Convert BGR to RGB, wrap in `mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)`, call
  `detect_for_video(image, ts_ms)` where `ts_ms` is an int that strictly increases (derive it
  from `t_capture_ns`; if it would repeat, add 1).
- Do not mirror the frame.
- Head pose: take the 3x3 rotation block of the 4x4 matrix, re-orthonormalize it (SVD), then
  `scipy.spatial.transform.Rotation.from_matrix(R).as_euler("yxz", degrees=True)` gives yaw,
  pitch, roll. Fix signs once so they match the comments in `FrameFeatures`; add a
  `python -m helm.vision` print test that shows yaw, pitch, roll and `jawOpen` live.
- Fill `blend` in `BLENDSHAPE_NAMES` order by category name, not by index.
- No face: return `face=False` with zeros. Set `t_infer_ns` after the call returns.
- Done: the print test shows correct signs; inference is 10 to 20 ms on CPU.

### 6.3 `mock.py` (P1)

```python
class MockSource:      # paced at 30 Hz
    def next(self) -> FrameFeatures   # yaw sweeps +-15 deg as a slow sine; browInnerUp pulses every 3 s;
                                      # jawOpen ramps up and down; face drops out for 0.5 s every 20 s
class Recorder:
    def __init__(self, path: str); def write(self, f: FrameFeatures) -> None; def close(self) -> None
class ReplaySource:
    def __init__(self, path: str, realtime: bool = True); def next(self) -> FrameFeatures | None
```

- Recording format: one `.npz` with arrays `seq, t_capture_ns, t_infer_ns, face, yaw, pitch,
  roll, blend (n, 52)`. No images are stored. `Recorder` buffers in memory and writes on close.
- These let P2, P3 and P4 work with no camera, and let P3 run evals offline. Build them
  early: the other lanes depend on them.

### 6.4 `filters.py` (P1)

```python
class OneEuro:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.01, d_cutoff: float = 1.0): ...
    def __call__(self, x: float, t_s: float) -> float
    def reset(self) -> None

def shape_axis(u: float, deadzone: float = 0.08, gamma: float = 1.5, invert: bool = False) -> float
    # dead zone, rescale, response curve, clamp to [-1, 1]; used by P2's Mapper

class Normalizer:
    def __init__(self, calib: Calibration | None = None): ...
    def set_calibration(self, calib: Calibration) -> None
    def update(self, f: FrameFeatures, breath: float = 0.0, idle: bool = False) -> Signals
```

- Axis: `u = (x - neutral) / r`, using the positive or negative limit by sign, then One Euro,
  then clamp to [-1, 1]. Start values `min_cutoff=1.0, beta=0.01, d_cutoff=1.0`; raise `beta`
  if steering feels laggy, lower `min_cutoff` if it jitters.
- `shape_axis`: `0` if `|u| < d`, else `sign(u) * ((|u| - d) / (1 - d)) ** gamma`.
- Expression scale: `e = (b - neutral_b) / (peak_b - neutral_b)`, clamped to [0, 1]. Where no
  peak is known, use `peak_b = neutral_b + 0.5`.
- `delta` = `blend - blend_neutral` (52), the three normalized axes, and `breath`.
- No calibration: neutral 0, range 15 degrees each way, blend neutral 0.
- Quick-mode auto-range: when `calib.mode == "quick"`, start from the default range and, if the
  player goes past a limit, widen that limit to the 95th percentile seen so far. Never shrink it.
- Drift (Should): when `idle` is true (no gesture active, all axes inside the dead zone),
  neutral follows the raw pose with a time constant of about 30 s.
- `face=False`: return zeros for axes and expr, and reset the One Euro filters.
- Tests: `shape_axis` edge values; One Euro passes a constant unchanged; a 10 degree range maps
  10 degrees to 1.0.

### 6.5 `calibration.py` (P1)

```python
class Calibrator:
    def __init__(self, player: str, mode: str = "full"): ...   # "full" | "quick"
    def feed(self, f: FrameFeatures, t_s: float) -> Progress
    def result(self) -> Calibration                             # valid once Progress.done is True
```

Steps auto-advance on timers. No clicks. Frames with `face=False` pause the timer.

| Step | Time | What is recorded |
|---|---|---|
| `neutral` | 3 s (quick: 2 s) | median of each axis and of all 52 blend scores |
| `yaw_left`, `yaw_right`, `pitch_up`, `pitch_down` | 2.5 s each | 95th percentile of displacement in that direction |
| `brow_raise`, `jaw_open`, `smile_left`, `smile_right`, `pucker` | 4 s each, "do it three times" | the three highest local peaks of the matching blendshape |

- Quick mode stops after `neutral` and uses the default range (15 degrees, auto-widening) and
  default peaks. It exists so a judge is playing within seconds.
- Minimum range is 4 degrees per direction; below that, keep 4 and flag it in the prompt.
- Roll is not prompted; its range defaults to 15 degrees.
- Blendshape per expression step: `browInnerUp`, `jawOpen`, `mouthSmileLeft`, `mouthSmileRight`,
  `mouthPucker`. `blend_peak[name]` is the median of the three peaks.
- Reliable when the weakest of the three peaks is at least 70% of the median peak and the
  median peak is at least 0.15 above neutral. Unreliable expressions are never offered by the coach.
- Prompts are short, second person, and say what to do now: "Look at the screen and relax your
  face", "Turn your head left as far as is comfortable, and hold".
- Done: a full calibration takes under 45 s and a stranger can follow it without help.

### 6.6 `main.py` (P1)

```python
class Runtime:
    def __init__(self, args): ...
    def start(self) -> None; def stop(self) -> None
    # called by server.py, from the asyncio thread; each just sets a request the pipeline picks up
    def start_calibration(self, mode: str) -> None
    def record_gesture(self, name: str) -> None
    def record_negative(self) -> None
    def delete_gesture(self, name: str) -> None
    def set_mapping(self, mapping: dict) -> list[str]        # returns validation errors, empty if applied
    def load_profile(self, player: str, game: str) -> None
    def save_profile(self) -> None
    def set_paused(self, on: bool) -> None
    def coach_build(self, game: str) -> None                 # runs coach in a worker thread; result arrives as an event
    def coach_review(self) -> None
    def snapshot(self) -> dict                               # the "state" message of section 8
    def preview(self) -> tuple[np.ndarray, np.ndarray | None] | None   # latest bgr frame and landmarks
    def pop_events(self) -> list[dict]                       # "event" messages queued for the dashboard
def main() -> None                                           # argparse, build Runtime, run server
```

CLI flags: `--mock`, `--replay PATH`, `--record PATH`, `--output auto|vgamepad|keyboard|null`,
`--player NAME` (default `guest`), `--game NAME` (default `SuperTuxKart`), `--camera N`,
`--port 8000`, `--no-server`, `--seconds N`, `--serial PORT|auto|off`.

Pipeline loop, one pass per new frame:

```
f       = tracker.process(frame)            (or mock/replay source)
          recorder.write(f) if recording to disk
if calibrator: prog = calibrator.feed(f); on done -> normalizer.set_calibration, save, event
s       = normalizer.update(f, breath=sip.level, idle=last_idle)
if take_recorder: prog = take_recorder.feed(s); on done -> model.fit, save, event with accuracy
act     = gestures.update(s)
scales  = fatigue.update(act, t_s)
state   = mapper.update(s, act, sip.poll(), scales)
neutral = face lost > 200 ms, or calibrating, or recording, or paused
pad.apply(neutral_state if neutral else state)
publish snapshot (latest-value slot); update rolling fps and latency (median of last 60 frames)
```

- Wrap the loop body in `try/except`: log the first occurrence of each error, apply a neutral
  state, continue.
- Session statistics for the coach and the dashboard (per gesture: fires, peak level history,
  near-misses where the level reached 80% of `on` without firing) accumulate here.
- P1 wires other lanes' classes by the names in this section. Other lanes do not edit `main.py`.
- Done: `--mock --output null --no-server --seconds 3` exits 0; with a camera the kart steers.

### 6.7 `output.py` (P2)

```python
class Gamepad:                        # base
    def apply(self, state: ControlState) -> None
    def close(self) -> None
def make_gamepad(kind: str = "auto") -> Gamepad     # auto: vgamepad on Windows if importable, else keyboard, else null
```

- `VGamepadPad`: `vgamepad.VX360Gamepad()`; `left_joystick_float`, `right_joystick_float`,
  `left_trigger_float`, `right_trigger_float`, `press_button` / `release_button` with
  `vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_*`, then `update()`. Tap one button once after creation.
  Only press or release buttons whose state changed.
- `KeyboardPad` (pynput): fallback. `lx` beyond +-0.3 holds Right or Left; `rt > 0.3` holds Up;
  `lt > 0.3` holds Down; buttons map to keys listed in `config.py`.
- `NullPad`: stores the last state; used by tests, mock mode and macOS development.
- Import `vgamepad` and `pynput` inside the classes, not at module top.
- Done: the pad shows in Windows "Set up USB game controllers" and steers SuperTuxKart from a script.

### 6.8 `mapping.py` (P2)

```python
class Trigger:
    def __init__(self, on: float = 0.6, off: float = 0.4, min_hold_ms: int = 60,
                 refractory_ms: int = 200, mode: str = "tap"): ...        # "tap" | "hold" | "toggle"
    def update(self, level: float, t_ms: float, scale: float = 1.0) -> tuple[bool, bool]
        # returns (pressed, fired). scale multiplies on/off (fatigue). fired is True on the tick it activates.

class Mapper:
    def __init__(self, mapping: dict): ...
    def set_mapping(self, mapping: dict) -> None
    def set_paused(self, on: bool) -> None
    def update(self, s: Signals, act: dict[str, float], events: list[SipPuffEvent],
               scales: dict[str, float]) -> ControlState
    @property
    def idle(self) -> bool            # no gesture pressed and all mapped axes inside their dead zones
```

- Trigger: activates when `level >= on` for `min_hold_ms`; releases when `level <= off`; cannot
  re-activate for `refractory_ms` after release. `tap`: pressed for 120 ms then released even if
  the gesture is held. `hold`: pressed while active. `toggle`: each activation flips a latch.
- Axes: `shape_axis(s.axes[source], deadzone, curve, invert)` to the target stick axis.
- Analog triggers: `clamp((level - lo) / (hi - lo))` from a gesture's activation, or from breath
  (`breath_puff` = positive part of `s.breath`, `breath_sip` = negative part).
- Buttons: a gesture's Trigger drives a target in `PAD_BUTTONS`, or `lt` / `rt` (pressed = 1.0).
- Breath events (`soft_puff` and so on) behave as gestures whose level is 1.0 on the tick the
  event arrives: they work with `tap` and `toggle`.
- `auto`: constant outputs, e.g. `{"rt": 1.0}` for auto-accelerate.
- Pause: the pause gesture held for `hold_ms` toggles `paused`. While paused, the state is
  neutral with `paused=True`, and only the pause gesture is evaluated.
- `fired` lists gestures that activated on this tick (for the overlay and the stats).
- Tests: hysteresis, minimum hold, refractory, each mode, pause toggle, analog trigger scaling.

### 6.9 `profiles.py` (P2)

```python
def load_calibration(player: str) -> Calibration | None
def save_calibration(c: Calibration) -> None
def load_mapping(player: str, game: str) -> dict            # falls back to default_mapping(game)
def save_mapping(player: str, game: str, mapping: dict) -> None
def default_mapping(game: str) -> dict
def validate_mapping(mapping: dict, calib: Calibration | None = None,
                     learned: list[str] | None = None, has_breath: bool = False) -> list[str]
def gesture_model_path(player: str) -> str
def list_profiles() -> dict[str, list[str]]                 # player -> games
```

`validate_mapping` returns human-readable errors. It checks: required keys; targets exist; no
target driven by two sources; every referenced gesture is defined; blendshape gestures use
blendshapes in `calib.reliable` (when calib is given); learned gestures exist in `learned`;
breath gestures only when `has_breath`; a pause gesture is set; two `hold` gestures do not share
a muscle group (groups: brow, jaw, mouth, eyes, breath). The coach uses this as its checker.

### 6.10 `sipnpuff.py` (P2)

```python
class SipPuff:
    def __init__(self, port: str | None = "auto"): ...      # None or "off": no device
    def start(self) -> None; def stop(self) -> None
    @property
    def connected(self) -> bool
    @property
    def level(self) -> float                                 # [-1, 1], + puff, - sip, 0 at rest
    def poll(self) -> list[SipPuffEvent]                     # events since the last call
    def calibrate(self, max_puff_mv: float, max_sip_mv: float) -> None
```

- Auto-detect: try each serial port at 115200 baud and keep the one that sends lines starting
  with `P,`. With no device, `level` is 0.0 and `poll()` is empty, and nothing else changes.
- Baseline: median of the first 2 s, then a slow rolling median while no event is active.
- `level = (mv - baseline) / max` using the puff or sip maximum by sign, clamped.
- Events: a press begins when `|level|` stays above 0.25 (soft) for 80 ms. On release, classify
  by peak: at least 0.65 is hard, otherwise soft. Emit one event per press.
- The event detector is a pure class fed `(t_ms, mv)` pairs so it can be tested with no hardware.
- Done: four distinct commands fire reliably; pulling the USB cable mid-run does not crash Helm.

### 6.11 `gestures.py` (P3)

```python
class GestureModel:
    def add_take(self, name: str, frames: np.ndarray) -> None       # frames: (n, 56) deltas from one take
    def add_negative(self, frames: np.ndarray) -> None              # "none" class
    def remove(self, name: str) -> None
    def fit(self) -> dict[str, float]                                # gesture name -> leave-one-take-out accuracy
    def predict(self, delta: np.ndarray) -> dict[str, float]         # class probabilities, including "none"
    @property
    def names(self) -> list[str]
    def save(self, path: str) -> None
    @classmethod
    def load(cls, path: str) -> "GestureModel"

class TakeRecorder:
    def __init__(self, name: str | None, takes: int = 5): ...        # name None = record negatives only (15 s)
    def feed(self, s: Signals, t_s: float) -> Progress
    def result(self) -> list[np.ndarray]

class GestureEngine:
    def __init__(self, calib: Calibration | None, gesture_defs: dict, model: GestureModel | None): ...
    def update(self, s: Signals) -> dict[str, float]                 # activation for every defined gesture
```

- Take recording: per take, "get ready" 1 s, "do it now and hold" 1 s, "relax" 1 s. Positives
  are the frames of the hold window nearest the peak: the top 60% by distance from neutral.
  Negatives: 15 s with the prompt "Talk, look around, laugh". Neutral rest frames from the
  relax windows also go to "none".
- Features: the 56-value `delta`, standardized (`StandardScaler`).
- Model: `KNeighborsClassifier(n_neighbors=7, weights="distance")`. No training step beyond
  fitting; refit whenever a take or negative is added. If two gestures confuse each other,
  switch to logistic regression behind the same interface.
- Leave-one-take-out: for each gesture, hold out each take in turn, fit on the rest, and score
  the held-out take's frames. Split negatives into five chunks the same way. Under 85%: the
  recorder's final prompt asks for three more takes or a more distinct movement.
- `GestureEngine` activation by kind:
  - `blendshape`: `s.expr` of the source; several sources combine with `min` or `max`
    (`"combine"` key, default `max`).
  - `learned`: the gesture's probability averaged over the last 4 frames, forced to 0 when the
    "none" probability is 0.3 or more.
  - `breath`: not handled here (the Mapper takes events directly); return nothing for these.
- Save format: one `.npz` with the raw takes and negatives, so the model refits on load.
- Tests: synthetic clusters separate; a "none" sample suppresses activation; save and load round-trip.
- Done: a one-sided smile learned from five takes fires on demand and does not fire while talking.

### 6.12 `adapt.py` (P3, Should)

```python
class FatigueTracker:
    def update(self, act: dict[str, float], t_s: float) -> dict[str, float]   # gesture -> threshold scale in [0.5, 1.0]
    def notices(self) -> list[str]                                            # e.g. "brow_raise is weakening; threshold lowered"
```

Track each gesture's peak level per activation over a rolling 2 minutes. If the median recent
peak falls below 75% of the first minute's, scale that gesture's thresholds by the same ratio,
never below 0.5.

### 6.13 `coach.py` (P1, Should): see section 11.

### 6.14 `server.py` (P4)

```python
def create_app(runtime: "Runtime") -> FastAPI
def run(runtime: "Runtime", host: str = "127.0.0.1", port: int = 8000) -> None
```

- One WebSocket at `/ws`. Broadcast `runtime.snapshot()` at 30 Hz, drain `runtime.pop_events()`
  each tick, and send a preview frame at 15 fps.
- Preview: resize to 320x240, mirror horizontally, JPEG quality 60, base64. Mirror landmark x
  as `1 - x`. Encoding happens here, never in the pipeline thread.
- Incoming commands (section 8) call the matching `Runtime` method. Reply to bad commands with
  an `error` event; never raise.
- Serve the built dashboard from `ui/dist` at `/` when it exists, so the demo needs one process.
- CORS open for `localhost:5173` during development.

---

## 7. Files on disk (`profiles/`, P2)

```
profiles/
  <player>/calibration.json       the Calibration dataclass
  <player>/gestures.npz           learned gesture takes and negatives (P3 writes through GestureModel.save)
  <player>/<game>.json            a mapping
  _defaults/<game>.json           default mapping per game, committed
```

Commit `_defaults/` and the tuned demo profiles. Ignore `guest/`.

Mapping format:

```json
{
  "player": "sam",
  "game": "SuperTuxKart",
  "axes": [
    {"source": "yaw", "target": "lx", "deadzone": 0.08, "curve": 1.5, "invert": false}
  ],
  "triggers": [
    {"source": "breath_sip", "target": "lt", "lo": 0.15, "hi": 0.85}
  ],
  "gestures": {
    "brow_raise":  {"kind": "blendshape", "sources": ["browInnerUp"], "on": 0.6, "off": 0.4},
    "smile":       {"kind": "blendshape", "sources": ["mouthSmileLeft", "mouthSmileRight"], "combine": "max", "on": 0.6, "off": 0.4},
    "eyes_closed": {"kind": "blendshape", "sources": ["eyeBlinkLeft", "eyeBlinkRight"], "combine": "min", "on": 0.6, "off": 0.4},
    "left_smirk":  {"kind": "learned", "on": 0.7, "off": 0.5},
    "hard_puff":   {"kind": "breath"},
    "soft_puff":   {"kind": "breath"}
  },
  "buttons": [
    {"gesture": "brow_raise", "target": "A",  "mode": "tap"},
    {"gesture": "smile",      "target": "B",  "mode": "hold"},
    {"gesture": "left_smirk", "target": "X",  "mode": "tap"},
    {"gesture": "hard_puff",  "target": "rt", "mode": "toggle"},
    {"gesture": "soft_puff",  "target": "Y",  "mode": "tap"}
  ],
  "auto": {},
  "pause": {"gesture": "eyes_closed", "hold_ms": 1000}
}
```

The numbers above are examples. Real thresholds come from calibration and tuning.

---

## 8. WebSocket protocol (`/ws`, JSON)

Server to dashboard:

```json
{"type": "state", "fps": 58.2,
 "latency_ms": {"vision": 14.1, "control": 0.6, "total": 31.0},
 "face": true, "paused": false, "breath_connected": true,
 "profile": {"player": "sam", "game": "SuperTuxKart", "calibrated": "full"},
 "raw":  {"yaw": 3.1, "pitch": -4.0, "roll": 0.5},
 "axes": {"yaw": 0.12, "pitch": -0.03, "roll": 0.0},
 "breath": 0.0,
 "activations": {"brow_raise": 0.72, "smile": 0.05, "left_smirk": 0.0},
 "thresholds":  {"brow_raise": {"on": 0.6, "off": 0.4}},
 "control": {"lx": 0.1, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 1.0, "buttons": ["A"]},
 "fired": ["brow_raise"],
 "progress": null,
 "gestures": {"learned": ["left_smirk"], "reliable": ["browInnerUp", "jawOpen"]},
 "notices": []}

{"type": "frame", "jpeg": "<base64>", "landmarks": [[0.51, 0.42], ...]}

{"type": "event", "name": "calibration_done" | "gesture_trained" | "coach_result" | "profile_loaded" | "error",
 "data": {}}
```

`progress` is a `Progress` object (section 5) while calibration or recording is active, else null.
`gesture_trained` carries `{"name", "accuracy"}`. `coach_result` carries
`{"mapping", "rationale", "changes"}`.

Dashboard to server:

```json
{"cmd": "calibrate", "mode": "full" | "quick"}
{"cmd": "record_gesture", "name": "left_smirk"}
{"cmd": "record_negative"}
{"cmd": "delete_gesture", "name": "left_smirk"}
{"cmd": "set_mapping", "mapping": {}}
{"cmd": "load_profile", "player": "sam", "game": "SuperTuxKart"}
{"cmd": "save_profile"}
{"cmd": "pause", "on": true}
{"cmd": "coach_build", "game": "SuperTuxKart"}
{"cmd": "coach_review"}
```

P4 builds against `python -m helm --mock --output null`, which serves this protocol with fake data.

---

## 9. Dashboard (`ui/`, P4)

One page. It has to read from two meters away on a judge-facing screen.

- `CameraView`: canvas with the mirrored preview and the face mesh drawn over it.
- `Gauges`: a steering bar for the left stick, bars for both triggers, one bar per gesture with
  tick marks at its on and off thresholds, and controller buttons that light when pressed. A
  gesture's row flashes when it appears in `fired`.
- `StatusBar`: fps, total latency in ms, face found or lost, paused, breath sensor connected,
  player and game.
- `Wizard`: when `progress` is not null, a full-width panel shows `prompt` in very large type
  with a progress ring for the step and a thin bar for `overall`. It advances by itself.
- `GestureRecorder` (Should): name field, "Teach a gesture" button, live take prompts, accuracy
  after training, list of learned gestures with delete.
- `MappingView` (Should): read-only table of the current mapping: gesture, target, mode. Editing
  is a JSON text box with validation errors shown underneath. No drag-and-drop editor.
- `CoachPanel` (Should): game picker, "Build my mapping", the proposed mapping with the coach's
  reasons, Accept. After play: "Review my session" lists suggested changes with Accept.
- Layout modes by query string: default (everything), `?overlay=1` (camera small, gauges and
  fired inputs only, for a window beside the game).
- Style: dark background, one accent color, large type, no decoration. Shows a clear
  "Reconnecting" state if the socket drops, and reconnects by itself.
- On load with no calibration for the current player, send `{"cmd": "calibrate", "mode": "full"}`
  automatically once a face has been visible for one second. A `?quick=1` flag sends quick mode.

---

## 10. Sip-and-puff hardware (P2)

Parts: ESP32 DevKit, MPXV7002DP differential pressure breakout (fallback: BMP280 sealed on the
tube), 10 kΩ and 20 kΩ resistors, silicone tubing, disposable straws, gooseneck clamp.

Wiring:

- Sensor VCC to the ESP32 5 V pin (VIN on USB power), GND to GND.
- Sensor OUT through 10 kΩ to GPIO34, and GPIO34 through 20 kΩ to GND. This scales 0.5 to 4.5 V
  down to 0.33 to 3.0 V. Never connect the 5 V output straight to a GPIO.
- Tube on one sensor port, the other port open to air: puffs read positive, sips negative.

Firmware (`firmware/sipnpuff/sipnpuff.ino`): at 115200 baud, every 10 ms, average 8 readings of
`analogReadMilliVolts(34)` and print `P,<millis>,<millivolts>`. Set attenuation `ADC_11db`. The
firmware only streams raw readings; every threshold lives on the laptop.

Notes:

- The MPXV7002DP spans about ±2 kPa and a firm puff can exceed that, so hard puffs may clip.
  Thresholds are fractions of the player's own calibrated maximum, so clipping is acceptable.
  If soft and hard are hard to tell apart, add a pinhole bleed (a T-piece with a small opening)
  to lower the pressure reaching the sensor.
- Throttle by breath is latched (a hard puff toggles accelerate), because nobody can hold a
  puff for a whole race. Sip is analog brake while held.
- Breath is feature 56 of the classifier input, so a learned gesture can include breath.
- Hygiene: a fresh straw per person. Never share one.
- Build it to be looked at: sensor and board fixed to a small base, tube routed along the
  gooseneck, cables tied, one labeled USB cable to the laptop.

---

## 11. Coach agent (`coach.py`, P1, Should)

Purpose: turn "this player, this game" into a working mapping, then improve it from how the
session actually went. This is the agentic and adaptive part of Helm.

```python
def build_mapping(game: str, calib: Calibration, learned: list[str], has_breath: bool) -> dict
    # returns {"mapping": <valid mapping dict>, "rationale": [str, ...]}
def review_session(mapping: dict, stats: dict, calib: Calibration, learned: list[str], has_breath: bool) -> dict
    # returns {"mapping": <valid mapping dict>, "changes": [str, ...]}
```

Build it with LangChain's `deepagents` (`create_deep_agent(model=..., tools=[...],
system_prompt=...)`, invoked with `{"messages": [...]}`). The package moves fast: read the
installed version's README or docstrings before writing against it.

Tools given to the agent (plain Python functions with docstrings):

- `get_game_controls(game)`: actions for the game from `helm/games.json`: name, whether it is
  held or tapped, how often it is used, whether it is analog, and which pad target it is bound to.
- `get_player_report()`: reliable expressions with their strength, head range per direction,
  learned gestures, whether breath is available, and (for review) per-gesture stats: fires,
  near-misses, fatigue notices, false-trigger suspects.
- `check_mapping(mapping_json)`: runs `profiles.validate_mapping` and returns the error list.
- `submit_mapping(mapping_json, reasons)`: accepted only when `check_mapping` returns no errors.

Loop the agent must follow (state it in the system prompt): read the controls, read the player
report, plan the assignment (most frequent and most time-critical actions go to the player's
strongest, least tiring gestures; held actions never share a muscle group; steering goes to the
head axis with the widest range), draft, check, fix every error, submit. For review: read the
stats, propose the smallest set of changes that addresses near-misses, false triggers and
fatigue, check, submit.

Rules:

- Local first: the agent sees a game name, gesture names and numbers. Never images or video.
- It runs in a worker thread started by `Runtime.coach_build` / `coach_review`. The result is
  queued as a `coach_result` event. It never blocks the pipeline.
- Model from the environment: `HELM_COACH_MODEL` (a `provider:model` string) plus that
  provider's API key. Time limit 60 s.
- Offline and failure path: if there is no key, no network, or the agent fails or times out,
  return the cached mapping in `profiles/_defaults/<game>.json` filtered to the player's
  reliable gestures, with the rationale "offline default". The demo must never depend on Wi-Fi.
- `games.json` covers SuperTuxKart fully and two or three other games briefly.
- Tests: with a fake model or the offline path, `build_mapping` always returns a mapping that
  passes `validate_mapping`.

---

## 12. Evaluation (`eval/`, P3)

Three numbers go on the slide, each beside a baseline. Run them while other hackers are
awake to volunteer, on a build whose control path has stopped changing. Raw data goes in `eval/results/*.csv`.

1. Latency, motion to screen. A phone films at 240 fps with the player's face and the laptop
   screen in one shot. The screen shows `eval/latency.html`, which reads the Gamepad API every
   animation frame and flashes a large square while button A is down. Do 20 sharp eyebrow
   raises; count frames from first visible eyebrow movement to the flash (about 4.2 ms per
   frame). Baseline: the same shot with a finger pressing A on a real controller. Report median
   and 90th percentile. Also report the software latency Helm logs (median `total_ms`).

2. False triggers per minute. Record once, score twice. Each participant calibrates, records
   negatives, then runs `python -m helm --record` for three minutes with control on: one minute
   reading aloud, one minute chatting, one minute watching a gameplay video. `false_triggers.py`
   replays that file through (a) a fixed-threshold baseline: any raw blendshape score crossing
   0.5 fires, no calibration, and (b) full Helm: calibrated scale, hysteresis, the learned
   "none" class. Every fire counts as false. Report the median per minute for each condition.

3. Target test with restricted movement. `eval/target_test.html` draws a ring of 9 circular
   targets; the left stick moves a cursor and button A selects. Two target widths, two
   distances. Conditions: (c) Helm with per-player scaling while the player moves no more than
   about a third of their normal range, recalibrated to that small range; (d) the same small
   movements with fixed gain and no per-player scaling. If time allows, add a mouse baseline.
   Score throughput in bits per second: `TP = IDe / MT`, `IDe = log2(De / We + 1)`,
   `We = 4.133 * SDx`. The headline is (c) against (d).

Also log: leave-one-take-out accuracy per participant, and median time from launch to first race.

Participants: the four teammates plus whoever volunteers. State on the slide that no
participant had a motor impairment and that the restricted-range condition is a proxy.

`analysis.py` produces three charts as PNG and prints the headline numbers. Every number needs a
participant count, a median and a baseline.

---

## 13. Demo profiles (P2 tunes, committed under `profiles/`)

Bind SuperTuxKart's gamepad actions once in its settings to match these targets.

`demo` (the teammate who races during the pitch, with the sensor):

| Input | Output | Game action |
|---|---|---|
| Head yaw | left stick X | steer |
| Hard puff (toggle) | RT latched | accelerate |
| Sip (analog, held) | LT | brake |
| Eyebrow raise (tap) | A | fire item |
| Smile (hold) | B | nitro |
| Learned personal gesture (tap) | X | rescue |
| Eyes closed 1 s | pause | |

`demo_webcam` (no sensor): the same, with `jaw_open` as an analog RT instead of the puff latch.

`judge` (a stranger, quick calibration): head yaw steers, `auto: {"rt": 1.0}` accelerates on its
own, eyebrow raise fires an item. Nothing else is mapped, so talking cannot trigger anything.

Split-screen: SuperTuxKart supports two local players. Player 1 is the Helm virtual pad and
player 2 is a real controller, so a hands-free player and a hands-on player race each other.

---

## 14. Bootstrap and lane plans

Bootstrap (P1, once hacking has started, before anyone else pushes):

1. Create the public GitHub repo. Add `CLAUDE.md` and `docs/SPEC.md`.
2. Create the tree in section 4. Every source file gets its `# OWNER: Pn` line and a one-line
   docstring. Write `contracts.py` exactly as section 5.
3. Stub every class and function in section 6 with the exact signatures and a minimal working
   body (pass-through or neutral), so `main.py` can already import and call everything.
4. Implement `MockSource`, `NullPad` and a first `Runtime` loop so the smoke run passes.
5. Add `requirements.txt` (`vgamepad` with the marker `; sys_platform == "win32"`),
   `.gitignore` (`CLAUDE.local.md`, `profiles/guest/`, `node_modules/`, `ui/dist/`,
   `__pycache__/`, `*.npz` outside `profiles/` and `eval/results/`), `docs/status/P1..P4.md`.
6. Commit as `bootstrap`, push. Everyone clones, creates `CLAUDE.local.md` with their lane, and starts.

Meanwhile: P2 installs SuperTuxKart, Python 3.11 and the ViGEmBus driver on the demo laptop and
confirms a virtual pad appears; P3 downloads `face_landmarker.task`; P4 scaffolds the Vite app
locally and adds it under `ui/` after cloning.

Lane work lists. Each list is in build order. Check items off in `docs/status/<lane>.md`.
There is no schedule here: the user decides when to move on.

P1, perception and runtime:

1. Bootstrap the repo (above).
2. `capture.py`: camera thread with the latest-frame slot.
3. `vision.py`: Face Landmarker wrapper, head pose with the sign test, `FrameFeatures` out.
4. `mock.py`: mock source, record, replay.
5. `filters.py`: One Euro, `shape_axis`, first `Normalizer` (uncalibrated defaults).
6. `main.py`: the real pipeline loop, CLI flags, fps and latency stats, face-lost safety.
7. `calibration.py`: full and quick modes; wire into `Runtime`; tune One Euro in the game.
8. `coach.py` and `games.json`: agent with the offline path.
9. Drift re-centering in `Normalizer`.
10. Performance and robustness pass (glasses, backlight); README pipeline section.

P2, control and hardware:

1. Demo laptop: SuperTuxKart, ViGEmBus, a virtual pad that steers the kart from a script.
2. `output.py`: vgamepad, keyboard and null backends.
3. `mapping.py`: `Trigger` (hysteresis, hold, refractory, tap/hold/toggle), then `Mapper`.
4. Pause gesture; analog triggers; `auto` outputs.
5. `profiles.py`: load, save, `validate_mapping`; default, `judge` and `demo_webcam` mappings.
6. Firmware and `sipnpuff.py`: stream, baseline, level, events, calibration.
7. Breath in the `demo` mapping (latched throttle, analog brake); hardware mounted cleanly.
8. Tune the demo profiles in the game; record a backup race video.
9. Keyboard fallback checked on a second laptop; demo table kit.

P3, learning and evaluation:

1. `gestures.py`: `GestureModel` (k-NN, leave-one-take-out) on synthetic, then recorded data.
2. `TakeRecorder`: takes and negatives with prompts.
3. `GestureEngine`: blendshape and learned activations, the "none" rule; wired live with P1.
4. Test learned gestures on three people; tune thresholds.
5. `eval/false_triggers.py`, `eval/latency.html`, `eval/target_test.html`, `eval/PROTOCOL.md`.
6. `adapt.py`: fatigue tracking.
7. Run the evals; `eval/analysis.py`; charts and headline numbers to P4.
8. Double-check every number that appears on a slide or on Devpost.

P4, product and story:

1. `server.py`: WebSocket broadcast, commands, preview encoding.
2. `ui/`: socket client and types, `CameraView` with mesh, `Gauges`, `StatusBar`, against mock.
3. `Wizard`: large prompts, auto-advance, auto-start calibration; `?quick=1` and `?overlay=1`.
4. `GestureRecorder`: teach, accuracy readout, list and delete.
5. `MappingView` and `CoachPanel`.
6. Polish for a projector; serve the built dashboard from the Python server.
7. `README.md`; Devpost text; slides; demo video under two minutes.

First prompt for each lane, after cloning and creating `CLAUDE.local.md`:
"Read CLAUDE.md, then sections 5 and 6 of docs/SPEC.md for my files. Start on the first
unchecked item in my lane's list in section 14. Write its tests, and stop to show me when the
smoke run passes."

---

## 15. Fallbacks

| Problem | Fallback |
|---|---|
| Head steering feels laggy or twitchy | Discrete mode (tilt past a threshold = full left or right), a forgiving game, and calibration becomes the headline |
| vgamepad or ViGEmBus will not install, or the game ignores the pad | Keyboard backend; SuperTuxKart plays on keys |
| Learned gestures fire while talking | Raise `on` to 0.8, require "none" under 0.2, cap at two learned gestures, record more negatives |
| k-NN confuses two gestures | Logistic regression behind the same interface |
| Bad venue lighting or a window behind the player | Ring light; turn the table |
| A judge's glasses, beard or hat confuses tracking | Judge watches the teammate, then tries the `judge` profile |
| Pressure sensor missing or dead | BMP280 sealed on the tube; with no sensor, use `demo_webcam` and drop the two hardware prizes |
| Coach or network fails | Offline default mapping (section 11) |
| Dashboard not ready | The pipeline runs headless; show the OpenCV preview window from `python -m helm.vision` |
| Running out of time | Cut the coach and fatigue adaptation first, then the mapping view |
| Evals running short on time | Latency and false triggers first; target test with teammates only |
| Demo laptop dies | Second laptop on the keyboard backend, plus the backup race video |
