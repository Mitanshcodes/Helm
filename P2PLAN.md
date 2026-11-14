# P2 roadmap — control and hardware

Personal working plan for lane **P2**. The authority on *what* Helm is remains `docs/SPEC.md`
(captain-owned) and `CLAUDE.md`. This file is the authority on *how P2 gets it done and who does
which part*.

**No clock times, no deadlines anywhere in this file.** Phases are ordered by dependency and
risk, and each one has a gate you can check. Pace and order are the user's call; any agent that
adds an hour estimate to this file is doing it wrong.

## What P2 owns

| File | Status |
|---|---|
| `helm/output.py` | gamepad backends: vgamepad, keyboard, null |
| `helm/mapping.py` | `Trigger` state machine, `Mapper` -> `ControlState` |
| `helm/profiles.py` | load/save/validate calibration and mappings |
| `helm/sipnpuff.py` | serial thread, breath level, sip/puff events |
| `firmware/sipnpuff/sipnpuff.ino` | ESP32 streams raw pressure |
| `profiles/` | committed defaults and tuned demo profiles |
| `tests/test_output.py` `test_mapping.py` `test_profiles.py` `test_sipnpuff.py` | tests follow the module |
| `docs/status/P2.md` | the short note teammates read |
| P2's section of `helm/config.py` | tunables, nobody else's section |
| `requirements.txt` | append only, P2's deps only |

Not P2's, ever: `contracts.py` (frozen), `main.py`, `filters.py`, `calibration.py`, `vision.py`,
`gestures.py`, `server.py`, `ui/`, `eval/`. If one of those needs to change, stop and pass the
request on — there is a prepared list in "Cross-lane requests" below.

---

## Division of labour: Claude vs Codex

The governing principle, applied to every task in this plan:

> **Claude pins the interface and integrates. Codex fills in bounded logic behind an interface
> that is already pinned. Claude reviews what Codex wrote against the spec before it lands.**

### Claude (this agent)

Strengths worth spending on: holds `SPEC.md` and the lane rules in context; cross-module and
cross-lane reasoning; spotting integration contradictions before they cost an hour; platform and
hardware specifics (ViGEm quirks, ESP32 ADC behaviour, serial lifecycle); judgment about what to
cut when the demo is at risk; prose.

Weaknesses to route around: slower and more expensive per line of mechanical code; will
over-reason a task that only needed twenty crisp test cases; drifts into adjacent scope if the
task is loosely worded.

**Claude takes:** anything that touches hardware or the OS, anything that crosses a lane
boundary, anything where a wrong call costs demo reliability, the firmware, the committed profile
JSONs, and every review pass.

### Codex (`mcp__codex-cli__codex`)

Strengths worth spending on: fast and thorough on a *bounded, well-specified* module with written
acceptance criteria; excellent at grinding out exhaustive pytest cases and edge conditions;
mechanical refactors; will not get bored on the twelfth hysteresis test.

Weaknesses to route around: **carries no project context between invocations** — this is the
single reason the three tracking files below exist; drifts on interfaces and will invent a
signature that violates frozen contracts if not handed the exact one; will edit files outside its
lane unless explicitly fenced; weaker on hardware and platform behaviour it cannot execute.

**Codex takes:** pure-logic classes and functions whose signature is already frozen in `SPEC.md`
§6, plus their test files. Nothing that imports `vgamepad`, `pynput` or `serial`. Nothing in
`firmware/`. Never a public signature change.

### The split, concretely

| Work | Owner | Why |
|---|---|---|
| `make_gamepad`, `VGamepadPad`, `KeyboardPad` | Claude | lazy imports, ViGEm post-create tap, button diffing, platform detect |
| `NullPad` | Codex | pure state holder, trivially testable |
| `Trigger` state machine | **Codex** | textbook bounded state machine, crisp criteria, many edge cases |
| `Mapper` | Claude | consumes `Signals`, activations, breath events, fatigue scales; pause semantics |
| axis + analog-trigger scaling tests | Codex | mechanical, high case count |
| `validate_mapping` | **Codex** | nine independent rules, each a test; perfect fit |
| tuple/list JSON coercion in `profiles.py` | Codex | mechanical, once Claude decides the representation |
| `default_mapping`, the committed profile JSONs | Claude | demo judgment, §13 targets |
| `BreathDetector` (pure, fed `(t_ms, mv)`) | **Codex** | spec explicitly designed it to be hardware-free |
| `SipPuff` serial thread, auto-detect, baseline | Claude | thread lifecycle, USB-unplug resilience |
| `sipnpuff.ino` | Claude | divider and ADC reasoning, see Phase 0 |
| in-game tuning, soldering, mounting, backup video | **User** | physical, cannot be delegated |

---

## Standing rule: the three working files

Both agents, every session, no exceptions. These are gitignored and personal — they are the
shared memory that Codex does not have.

### Before touching any code

Read all three, in this order: `context.md` -> `architecture.md` -> `decisions.md`.

### After every working chunk

| File | Lifetime | What goes in it |
|---|---|---|
| `context.md` | rewritten each chunk, short | What I am on right now. What just changed. Open questions. Blocked on whom. The first thing a cold agent reads. |
| `architecture.md` | updated when structure changes | How P2's code actually fits together: module map, the exact signatures *as implemented*, data in and out of P2, time-unit convention, where each tunable lives. |
| `decisions.md` | **append only, never rewritten** | Every non-obvious choice: date, decision, why, alternatives rejected, what would reverse it. |

`context.md` is not `docs/status/P2.md`. `docs/status/P2.md` is committed, short, and written for
teammates. `context.md` is private, longer, and written for the next agent.

**A task is not done until:** the module's tests pass, `python -m helm --mock --output null
--no-server --seconds 3` exits 0, `docs/status/P2.md` is updated, `context.md` reflects reality,
and `decisions.md` has an entry if a decision was made.

### Codex handoff template

Every Codex invocation gets all six of these. Paste shape:

```
Repo: /Users/avhaan/Documents/HackPrinceton/Helm   Lane: P2

1. Read context.md, architecture.md and decisions.md at the repo root before writing anything.
2. Read docs/SPEC.md section 5 (contracts) and section <6.x> only. Do not read the whole spec.
3. Your task: <one sentence>
4. Exact signature, do not change it:
   <paste verbatim from SPEC section 6.x>
5. Acceptance criteria:
   - <bullet>
   - <bullet>
6. Files you may touch: <explicit list, nothing else>
   Do NOT import vgamepad, pynput or serial. Do NOT edit helm/contracts.py or any file whose
   OWNER line is not P2. Do NOT add folders.
   If a signature or criterion looks wrong, STOP and write the question under "Open questions"
   in context.md instead of guessing.
7. Do ONLY the task in item 3. Do not start the next phase, do not implement anything in another
   file "while you are there", and do not create or modify any virtualenv. If you see adjacent work
   worth doing, list it under "Open questions" in context.md and stop.
8. When done: append your decisions to decisions.md, update context.md, and end your report with
   an explicit list of every file you changed, so the fence can be audited.
```

Codex has already crossed this fence once (see `decisions.md`, 2026-11-13): fenced to two files, it
wrote five, ran two phases ahead, and reported creating a virtualenv it did not create. The work was
in-lane and correct and was kept, but **verify its file list against `git status` and never trust its
self-reported environment claims.**

Then Claude reviews the diff against `SPEC.md` §5/§6 before it counts as landed.

---

## Phase 0 — Retire the risks that can kill the demo

Nothing else in P2 matters if this phase fails, and every failure here has a long lead time.

P1's bootstrap has landed (`39018c8`), so the tree and `contracts.py` exist and every P2 file is
stubbed with the exact signatures from §6 — including `Trigger.__init__` defaulting to
`config.TRIGGER_ON` / `TRIGGER_OFF` / `TRIGGER_MIN_HOLD_MS` / `TRIGGER_REFRACTORY_MS`, and
`config.TAP_MS`, `PAUSE_HOLD_MS`, `KEYBOARD_KEYS`, `BREATH_*` already defined in P2's section.
**Hand Codex the config constant names, not the literal numbers**, or it will hardcode them and
break the tunables rule.

`python -m helm --mock --output null --no-server --seconds 3` already exits 0 on the stubs, so
that gate is live from the first commit.

**User, on this Mac (dev machine) — none of this existed when the plan was written:**

- [ ] Python 3.11, not 3.13. `pyenv` currently offers only 3.13.14 and `.python-version` pins it;
      `requirements.txt` says 3.11 and mediapipe's wheel support for 3.13 is unreliable.
      `pyenv install 3.11.15`, then a venv in the repo (`.venv/` is already gitignored).
- [ ] `pip install -r requirements.txt` and confirm `python -m pytest -q` actually runs — pytest is
      listed but not installed, so the suite cannot run at all right now.
- [ ] Confirm `import mediapipe` works before trusting any camera path. This is the classic
      half-hour install hole (mediapipe pins numpy and protobuf); if it fights, that is a §15
      moment, not a debugging session.
- [ ] `vgamepad` is Windows-only by marker, so this Mac is a `--mock --output null` machine. All
      real pad work happens on the demo laptop.

**User, on the demo laptop (Windows):**

- [ ] Python 3.11, SuperTuxKart, **ViGEmBus driver**.
- [ ] Virtual pad appears in `joy.cpl` ("Set up USB game controllers").
- [ ] A throwaway script drives SuperTuxKart with `vgamepad` directly. Keep this script in a
      scratch directory, **not in the repo** — no new top-level folders.
- [ ] Bind SuperTuxKart's gamepad actions in its own settings to the §13 targets
      (steer = left stick X, accelerate = RT, brake = LT, fire = A, nitro = B, rescue = X).
      Easy to forget, and the whole §13 table is meaningless without it.
- [ ] Pin working versions in `requirements.txt` for P2's deps only: `vgamepad ; sys_platform ==
      "win32"`, `pynput`, `pyserial`. Append, never rewrite.

**User, on the bench (do this now, not in Phase 6):**

- [ ] Wire ESP32 + MPXV7002DP and print millivolts from the Arduino serial monitor. No Helm code.
- [ ] Confirm the reading swings both ways: puff positive, sip negative, tube on one port and the
      other port open to air.

**Claude:**

- [ ] **Use a 10k/10k divider, not the 10k/20k in SPEC §10.** With 10k/20k the ratio is 0.667, so
      a max puff lands at 3.00 V — above the ESP32's usable ADC range at `ADC_11db` (~2.45 V). The
      top of the puff range clips *at the ADC*, and soft-vs-hard puff discrimination lives exactly
      in that clipped band, so hard puffs read as unreliable and you lose a day in the firmware.
      10k/10k gives rest 1.25 V, max puff 2.25 V, max sip 0.25 V — all inside the linear band.
      Log this in `decisions.md` and tell the captain the spec table needs the change.
- [ ] Never connect the sensor's 5 V output straight to a GPIO. Sensor VCC to VIN (5 V, USB
      powered only), GPIO34 (ADC1_CH6, input only) through the divider.
- [ ] Pass the cross-lane requests below to P1 *before* Phase 4 starts.

**Gate:** a throwaway script steers the kart, and the serial monitor shows millivolts moving with
breath. Both true before writing P2 code.

---

## Cross-lane requests to pass on (blocking, hand to the captain / P1)

These came out of the spec review. The first one blocks Phase 4 and silently breaks every
committed mapping, so it goes first.

1. **`calibration.py` + `validate_mapping`: `eyes_closed` can never be a legal pause gesture.**
   §6.9 requires blendshape gestures to use names in `calib.reliable`, *and* requires a pause
   gesture to be set. But §6.5 only ever fills `reliable` from the five prompted expressions
   (`browInnerUp`, `jawOpen`, `mouthSmileLeft`, `mouthSmileRight`, `mouthPucker`).
   `eyeBlinkLeft/Right` are never measured, so every mapping in §7 and all three profiles in §13
   fail validation — and the coach's `submit_mapping` is gated on `check_mapping`, so the agent
   can never submit either. Ask P1 for: an `eyes_closed` step added to the expression check
   (preferred — you want a blink baseline anyway, and glasses affect `eyeBlink`), **or** a
   documented exemption for the pause gesture from the `reliable` rule. P2 implements whichever,
   but cannot write `validate_mapping` until it is decided.
2. **`gestures.py` (P3) has no setter.** `GestureEngine.__init__(calib, gesture_defs, model)` is
   construct-only, but `Runtime.set_mapping`, `load_profile`, calibration finishing and a gesture
   finishing training all change exactly those three things. Ask P3 for `set_mapping`,
   `set_calibration`, `set_model`. Affects P2 because `Mapper.set_mapping` and the engine must
   change together or the activations go stale.
3. **Pick one time unit.** `contracts.py` stamps `perf_counter_ns`; `Calibrator.feed` and
   `TakeRecorder.feed` take `t_s`; `Trigger.update` takes `t_ms`. Three units across four lanes
   produces bugs that look like "hysteresis is 1000x too fast". P2 will implement `Trigger` with
   `t_ms` as specified and convert at the one call site in `main.py` — but the conversion needs to
   be stated in §6.6's loop so P1 writes it correctly.
4. **The latency example in §8 contradicts §3's definition.** `total = t_output - t_capture` must
   equal `vision + control`, but the example reads `14.1 + 0.6` vs `total: 31.0`. Minor for P2,
   matters for P4's StatusBar and P3's slide.

---

## Phase 1 — `output.py`

Priority #1, Must. Blocks everything downstream — nothing else P2 writes can be seen working
until a pad exists.

- [ ] **Claude:** `make_gamepad(kind="auto")` — vgamepad on Windows if importable, else keyboard,
      else null. Import `vgamepad` and `pynput` *inside* the classes so `--mock --output null`
      runs on macOS.
- [ ] **Claude:** `VGamepadPad` — `VX360Gamepad`, the float joystick/trigger setters, `press_button`
      / `release_button` with `XUSB_BUTTON.XUSB_GAMEPAD_*`, then `update()`. Two things that cost
      an hour if missed: **create the pad before launching the game**, and **tap one button once
      after creation** or the game may never see it. Only press or release buttons whose state
      actually changed.
- [ ] **Claude:** `KeyboardPad` (pynput) — `lx` past ±0.3 holds Left/Right, `rt > 0.3` holds Up,
      `lt > 0.3` holds Down, buttons to keys from P2's section of `config.py`. This is the §15
      fallback for "ViGEmBus will not install", so it is not optional polish.
- [ ] **Codex:** `NullPad` (stores last state) + `tests/test_output.py` driving only `NullPad`.
      No test may import vgamepad or pynput.

**Gate:** smoke run exits 0 on macOS with `--output null`; on Windows the kart steers through
`Gamepad.apply(state)`, not through a raw vgamepad call.

---

## Phase 2 — `mapping.py`: `Trigger`

Priority #3, Must. The cleanest Codex task in the whole lane.

- [ ] **Claude:** decide and record the time unit (request 3 above), then hand Codex the signature.
- [ ] **Codex:** `Trigger` + its half of `tests/test_mapping.py`. Acceptance criteria to paste:
      - activates when `level >= on` sustained for `min_hold_ms`, not on a single frame
      - releases when `level <= off` (hysteresis: `off < on`)
      - cannot re-activate for `refractory_ms` after release
      - `tap`: pressed 120 ms then released even if the gesture is still held
      - `hold`: pressed while active
      - `toggle`: each activation flips a latch
      - `scale` multiplies both `on` and `off`, so the hysteresis gap stays proportional
      - returns `(pressed, fired)`; `fired` is True only on the tick it activates
      - pure: no clock reads, no I/O. Time arrives as an argument.
- [ ] **Claude:** review against §6.8. Check the refractory-plus-min-hold interaction: 60 ms hold
      plus 200 ms refractory caps tap cadence around 2.5/s, which is fine for a kart but worth
      knowing before someone calls it a bug.

**Gate:** every §6.8 test-list item passes, whole suite still under 10 s, nothing imported from
hardware.

---

## Phase 3 — `mapping.py`: `Mapper`

Priority #3 and #7, Must. Claude-led: this is where four lanes' data meets.

- [ ] **Claude:** `Mapper.update(s, act, events, scales) -> ControlState`.
      - axes via P1's `shape_axis(s.axes[source], deadzone, curve, invert)` to the stick target
      - analog triggers: `clamp((level - lo) / (hi - lo))` from an activation, or from breath
        (`breath_puff` = positive part of `s.breath`, `breath_sip` = negative part)
      - buttons: a gesture's `Trigger` drives a `PAD_BUTTONS` target, or `lt`/`rt` as 1.0
      - breath events behave as gestures with level 1.0 on the arrival tick, so they work with
        `tap` and `toggle` (this is how latched throttle works)
      - `auto`: constant outputs, e.g. `{"rt": 1.0}` for the judge profile
      - pause: the pause gesture held `hold_ms` toggles `paused`; while paused the state is
        neutral with `paused=True` and **only the pause gesture is evaluated**
      - `fired` lists gestures that activated this tick, for the overlay and session stats
      - `idle` property: no gesture pressed and all mapped axes inside their dead zones — P1 feeds
        this back into `Normalizer` drift, so it is load-bearing, not cosmetic
- [ ] **Codex:** axis-plumbing and analog-trigger scaling tests, plus the pause-toggle test.
- [ ] Note: if P1's `shape_axis` is still a bootstrap stub, test `Mapper`'s *use* of it, not its
      math. Do not reimplement it locally.

**Gate:** pause toggles and holds the pad neutral; a mapping with `auto: {"rt": 1.0}` produces a
constant throttle; all §6.8 tests green.

---

## Phase 4 — `profiles.py` and the committed mappings

Priority #8, Must. **Hard gate: cross-lane request 1 must be resolved first**, or every mapping
you write fails its own validator.

- [ ] **Codex:** `validate_mapping(mapping, calib, learned, has_breath) -> list[str]`, one test per
      rule, human-readable error strings. The rules from §6.9:
      required keys; targets exist; no target driven by two sources; every referenced gesture is
      defined; blendshape gestures use names in `calib.reliable`; learned gestures exist in
      `learned`; breath gestures only when `has_breath`; a pause gesture is set; two `hold`
      gestures do not share a muscle group (brow, jaw, mouth, eyes, breath).
      This function is also the coach's `check_mapping` tool, so its error strings are read by an
      LLM — make them say what to do, not just what is wrong.
- [ ] **Codex:** round-trip coercion. `Calibration.range` is `dict[str, tuple[float, float]]` and
      JSON gives back lists; `blend_neutral` is a `list[float]` that `Normalizer` subtracts from an
      array. Coerce on load so the type hints stop lying and object comparisons in tests work.
- [ ] **Claude:** `load_calibration` / `save_calibration` / `load_mapping` / `save_mapping` /
      `gesture_model_path` / `list_profiles`, the `profiles/` layout from §7, and
      `default_mapping(game)`.
- [ ] **Claude:** write the committed mappings — `_defaults/SuperTuxKart.json`, plus `judge`,
      `demo_webcam` and `demo` per §13. `judge` maps head yaw, `auto: {"rt": 1.0}`, eyebrow raise
      to A, and **nothing else**, so a talking stranger cannot trigger anything.
- [ ] **Claude:** add a test that walks every JSON under `profiles/_defaults/` and asserts
      `validate_mapping` returns no errors. This is the test that catches request 1 regressing.
- [ ] Consider a `"version": 1` key in the mapping format. The format will change mid-build and
      you do not want silently-wrong committed demo profiles.

**Gate:** every committed mapping validates clean; a profile saves and loads back equal.

---

## Phase 5 — Firmware and `sipnpuff.py`

Priority #10, *Should* in §2 — **but read the strategy note below before you believe that.**

- [ ] **Claude:** `firmware/sipnpuff/sipnpuff.ino`. 115200 baud, every 10 ms, average 8 readings of
      `analogReadMilliVolts(34)`, attenuation `ADC_11db`, print `P,<millis>,<millivolts>`. The
      firmware streams raw readings and nothing else — **every threshold lives on the laptop**, so
      you can retune without reflashing in front of a judge.
- [ ] **Claude:** `SipPuff` — auto-detect by trying each serial port at 115200 and keeping the one
      sending lines that start with `P,`; baseline as the median of the first 2 s then a slow
      rolling median while no event is active; `level = (mv - baseline) / max` by sign, clamped;
      `connected` property. With no device: `level` is 0.0, `poll()` is empty, nothing else in
      Helm changes behaviour.
- [ ] **Claude:** survive the cable. Pulling USB mid-run must not crash the pipeline — log once,
      go to `connected = False`, keep running. A judge will knock the cable.
- [ ] **Codex:** the pure event detector, fed `(t_ms, mv)` pairs, no serial import. Criteria:
      a press begins when `|level|` holds above 0.25 for 80 ms; on release classify by peak,
      >= 0.65 is hard else soft; exactly one event per press; four kinds
      (`soft_sip`, `hard_sip`, `soft_puff`, `hard_puff`); baseline drift does not emit events.
      Plus tests, including a replayed millivolt trace.
- [ ] **User:** if soft and hard puff stay hard to separate after the divider fix, add a pinhole
      bleed (a T-piece with a small opening) to drop the pressure reaching the sensor.

**Gate:** four distinct commands fire reliably on the bench; unplugging USB does not crash Helm;
`--serial off` behaves exactly as before.

---

## Phase 6 — Breath in the demo mapping, and the physical build

- [ ] **Claude:** the `demo` profile — hard puff toggles RT (latched accelerate, because nobody can
      hold a puff for a whole race), sip is analog LT while held, eyebrow raise taps A, smile holds
      B, the learned gesture taps X, eyes closed 1 s pauses.
- [ ] **Claude:** `demo_webcam` — the same, with `jaw_open` as analog RT instead of the puff latch.
      This is the profile that saves the demo if the sensor dies.
- [ ] **User:** build it to be looked at. Sensor and board on a small base, tube along the
      gooseneck, cables tied, one labelled USB cable. Two of the entered tracks are hardware
      tracks; judges will literally look at the build quality.
- [ ] **User:** a fresh straw per person, visibly. Never share one. Put the box on the table.

**Gate:** a full race driven by head and breath, end to end.

---

## Phase 7 — Tuning and the backup

Mostly user work; agents only write down what you found.

- [ ] **User:** tuning passes in SuperTuxKart. Thresholds, dead zones, curve, trigger lo/hi.
- [ ] **Claude:** every tuned number into P2's section of `config.py` and the profile JSONs —
      **not inline in the modules** — with the reasoning appended to `decisions.md`.
- [ ] **User:** record the backup race video. The §15 fallback for "demo laptop dies" is a second
      laptop on the keyboard backend *plus this video*. It takes one take and it has saved many
      demos.

---

## Phase 8 — Fallback kit

The §15 table is only real if the fallbacks are physically present.

- [ ] Keyboard backend verified on a second laptop, with SuperTuxKart installed there.
- [ ] Demo table kit: straws, ring light, gooseneck clamp, spare USB cables, the printed §13
      input table so a judge can read what maps to what.
- [ ] Know the two P2-owned fallbacks cold: pad ignored by the game -> keyboard backend; sensor
      dead -> `demo_webcam` and drop the two hardware prizes.

---

## Strategy note: your lane is more load-bearing than §2 admits

§1 enters four special tracks. Three of them — Best Hardware Hack, Best Physical AI Hack, and the
hardware half of Best Practical AI — depend on the sip-and-puff, which §2 ranks #10, *below* the
Must line, and §15 lists among the first things to cut.

If the team executes §2 exactly and finishes only the Musts, Helm is a polished webcam controller
with an evaluation study and **zero** hardware-track entries. That is a captain-level decision,
not a P2 decision, but P2 is the one holding the affected work, so:

- Phase 0 puts the *electrical* smoke test before any P2 code. It is cheap and it retires the
  longest-lead failure (dead sensor, wrong part, missing component) while there is still time to
  react. Do not let it slide to Phase 5 just because §14 lists the firmware at position 6.
- Raise the ranking question with the captain early, once, with the trade stated plainly: moving
  sip-and-puff above the evaluation buys two track entries and costs evaluation depth. Then
  accept the answer and stop relitigating it.

---

## Every-chunk checklist

1. Read `context.md`, `architecture.md`, `decisions.md`.
2. Read only the `SPEC.md` section for the file you are editing (§6.x) plus §5.
3. Confirm the file's `# OWNER: P2` line before editing it.
4. Write the test with the code, not after.
5. `python -m pytest -q tests/test_<module>.py`
6. `python -m helm --mock --output null --no-server --seconds 3` exits 0.
7. Update `context.md`; append to `decisions.md` if you decided something.
8. Rewrite `docs/status/P2.md` short: Done / In progress / Next / Blocked on / Decisions.
9. `git pull --rebase`, smoke run again, then commit as `P2: <what changed>`.

Never push a `main` that fails the smoke run.
