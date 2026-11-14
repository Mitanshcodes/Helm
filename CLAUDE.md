# Helm

Hands-free game controller, built at HackPrinceton Fall '26 by a team of four in 36 hours.
Webcam -> MediaPipe face tracking -> per-player calibration and learned gestures -> a virtual
Xbox 360 controller that any game accepts. An optional ESP32 sip-and-puff sensor adds breath input.

Full technical spec: `docs/SPEC.md`. It is long. Read only the section you need (see below).

## Start of every session

1. Find your lane. `CLAUDE.local.md` contains a line `LANE: P1` (or P2, P3, P4). If you cannot
   see a lane, ask which teammate you are working with before editing anything.
2. Read `docs/status/<lane>.md`. These are your own running notes from earlier sessions.
3. Before editing `helm/<name>.py`, read its section in `docs/SPEC.md` (section 6, one
   subsection per file) and section 5 (contracts). Do not load the whole spec.
4. Work on whatever the user asks for. If they do not say, take the next unchecked item in your
   lane's list (`docs/SPEC.md` section 14). The user decides pace and order; never bring up
   schedules or deadlines.

## Lanes and file ownership

| Lane | Role | Owns |
|---|---|---|
| P1 | Perception and runtime | `helm/main.py` `capture.py` `vision.py` `mock.py` `filters.py` `calibration.py` `coach.py` `games.json`, `models/` |
| P2 | Control and hardware | `helm/output.py` `mapping.py` `profiles.py` `sipnpuff.py`, `firmware/`, `profiles/` |
| P3 | Learning and evaluation | `helm/gestures.py` `adapt.py`, `eval/` |
| P4 | Product and story | `helm/server.py`, `ui/`, `README.md` |
| Shared | Everyone | `helm/contracts.py` (frozen), `helm/config.py` (your own section only), `requirements.txt` (append only), `.gitignore` |

Tests follow the module: `tests/test_mapping.py` belongs to whoever owns `mapping.py`.
Status notes follow the lane: `docs/status/P2.md` belongs to P2.

Ownership rules:

- Every source file starts with `# OWNER: Pn` (or `// OWNER: Pn`). Edit only files your lane owns.
- If you need a change in someone else's file, stop. Tell the user the exact request to pass on
  (file, function, signature, behavior). Do not duplicate their code or work around it.
- `helm/contracts.py` is frozen after bootstrap. It changes only when the captain agrees.
- Do not add top-level folders, rename files, or move code between modules. The tree in
  `docs/SPEC.md` section 4 is the structure. New files go inside your own area with an OWNER line.

## Commands

```bash
# Python 3.11. From the repo root.
pip install -r requirements.txt

python -m helm                      # real camera, auto-picks the gamepad backend
python -m helm --mock --output null # no camera, no gamepad: works on any laptop
python -m helm --record run.npz     # save FrameFeatures while running
python -m helm --replay run.npz     # replay a saved run instead of the camera
python -m helm --player sam --game SuperTuxKart

python -m pytest -q                                                # all tests, must stay under 10 s
python -m pytest -q tests/test_mapping.py                          # one module
python -m helm --mock --output null --no-server --seconds 3        # smoke run, must exit 0

cd ui && npm install && npm run dev  # dashboard on http://localhost:5173, talks to ws://localhost:8000/ws
```

A change is done when: the module's tests pass, the smoke run exits 0, and
`docs/status/<lane>.md` is updated.

## What matters this weekend

Judges get two minutes per team. A stranger sits down, calibrates, and steers a kart with their
face. Reliability beats features every time.

- Default build order is the priority list in `docs/SPEC.md` section 2. The user can override it.
- Prefer the simplest thing that works on the demo laptop (Windows). No frameworks, no
  abstraction layers, no config systems, no plugin patterns. One class or a few functions per file.
- Never let the pipeline crash. On any exception in the loop: log once, send a neutral
  controller state, keep running.
- Safe defaults: if the face is lost, or calibration or recording is active, the pad is neutral.
- If something is not working after about 20 minutes, stop and propose the fallback from
  `docs/SPEC.md` section 15 instead of digging deeper.

## Control-loop rules (anything called from the pipeline thread)

- No blocking I/O, no `sleep`, no network, no disk writes, no per-frame `print` or logging.
- No queues between threads. Threads share "latest value" slots that overwrite, so a slow
  consumer drops stale data instead of building lag.
- The LLM coach, profile saves and JPEG encoding run off the pipeline thread.
- Stamp times with `time.perf_counter_ns()`. Latency is measured, never estimated.

## Code style

- Python 3.11, type hints on public functions, dataclasses from `helm/contracts.py` at module
  boundaries. Keep each module's public interface exactly as the spec lists it.
- Tunable numbers live in `helm/config.py` under your lane's section, not inline.
- Pure logic (filters, triggers, classifier, profile validation, sip-and-puff event detection)
  gets a small pytest file that runs without a camera, gamepad or serial port.
- Hardware and OS access (camera, vgamepad, serial, pynput) is imported lazily inside the class
  that needs it, so `--mock --output null` runs on macOS and Linux.
- UI: React + Vite + TypeScript, plain CSS, no component library, no state library.

## Git

- Trunk-based: everyone commits to `main`. Files do not overlap between lanes, so conflicts are rare.
- Before every push: `git pull --rebase`, then the smoke run. Never push a `main` that fails it.
- Small commits, message prefixed with the lane: `P2: hysteresis and tap/hold/toggle modes`.
- The repo must stay public and must contain only code written after hacking began
  (Fri Nov 13, 8:00 PM ET). Do not paste in code from earlier prototypes.

## Gotchas that will cost an hour if forgotten

- Never mirror the frame before inference. MediaPipe's Left/Right scores refer to the subject's
  own face. Mirror only the preview (and its landmarks) for display.
- `detect_for_video` needs strictly increasing integer millisecond timestamps.
- Blendshape index 0 is `_neutral`. Use names from `contracts.BLENDSHAPE_NAMES`, never raw indices.
- Some blendshapes barely move in practice. Check any score with a print test before relying on
  it (`cheekPuff` first). Calibration marks each expression reliable or not; respect that flag.
- Check head-pose signs once with a print test: turn left, watch yaw.
- Create the virtual pad before launching the game, and send one button tap after creating it,
  or the game may not see it.
- Windows camera: open with `cv2.CAP_DSHOW`, request MJPG, set buffer size 1.
- ESP32: use an ADC1 pin (GPIO32 to 39). The sensor output must go through the divider.
- Never map a single blink. Only an eye closure longer than one second counts (pause).

## Keep `docs/status/<lane>.md` current

After each working chunk, rewrite it (short): Done, In progress, Next, Blocked on, Decisions.
A fresh session later will have nothing else to go on.
