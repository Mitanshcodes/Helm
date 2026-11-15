<!-- OWNER: P2 -->
# Helm metrics tracker

Every number Helm claims anywhere — slides, README, Devpost, the pitch — and where it comes from.
P2 owns getting these. The design is `docs/SPEC.md` section 12; the step-by-step is `eval/PROTOCOL.md`.

**The one rule: never put an estimate on a slide.** A number is either measured, with a participant
count and a baseline beside it, or it reads "not measured". `eval/analysis.py` already enforces this —
anything missing prints as "not measured" rather than being guessed. Do not work around it.

Status vocabulary used below:

- **MEASURED** — real data in `eval/results/`, reproducible by re-running the tool.
- **BENCH** — measured once on real hardware, recorded in `docs/status/P2.md`, not in `eval/results/`.
- **NOT MEASURED** — no data. This is where almost everything sits right now.

---

## 1. Status board

Checked against a clean run of `python eval/analysis.py` (2026-11-15): all three headline numbers
print "not measured", and `ui/src/results.ts` is still all `null`.

| # | Metric | Baseline it is reported against | Lands in | Status | Gate |
|---|---|---|---|---|---|
| **H1** | Motion-to-screen latency, median + p90 | real controller, finger press | `latency.csv` | NOT MEASURED | 240 fps phone + human |
| **H2** | False triggers per minute | fixed 0.5 threshold, no calibration | `false_triggers.csv` | **MEASURED n=1**: 11.00 vs 23.67 (§12) | 2 more participants |
| **H3** | Pointing throughput, bits/s | same small movements at fixed gain | `target_*.csv` | NOT MEASURED | human at the target page |
| F1 | Software latency, median `total_ms` | — (reported alongside H1) | §11 | **MEASURED: 9.57 ms**, 1 person, dev machine | 3 study participants on the laptop |
| F2 | Learned-gesture accuracy (leave-one-take-out) | — | `participants.csv` | **MEASURED, 3 profiles** (§8) | 3 real participants |
| F3 | Launch to first race, seconds | — | `participants.csv` | NOT MEASURED | demo laptop + game |
| F4 | Participant count *n* | — | `participants.csv` | **1 of 3** (p1) | 2 more humans |
| B1 | Breath rest baseline and noise | — | §9 | **MEASURED live: 2392 mV, 40 mV p-p, sd 2.9** | — |
| B2 | Breath committed-swing displacement | rest noise | §9 | **MEASURED live: sip 1954-2372, puff 1479-2394 mV (n=4 each)** | — |
| B3 | Serial link line-loss rate | — | `docs/status/P2.md` | BENCH | — |
| B4 | Per-player breath calibration, accepted | refusal floor | `profiles/<p>/breath.json` | **MEASURED** (§9) | — |
| B5 | Breath event latency (release-classified) | — | §10 | **MEASURED** | — |
| R1 | Test suite runtime | CLAUDE.md's 10 s cap | CI/local | **MEASURED: 12.76 s, 418 tests — over cap** | — |
| R2 | Smoke run exit code | must be 0 | local | MEASURED (0) | — |

---

## 2. The three headline numbers

These are what a judge sees. Each needs *n*, a median and a baseline.

### H1 — Motion-to-screen latency

What it measures: first visible eyebrow movement → the screen changing. The whole chain: camera,
tracking, virtual pad, Windows, browser, display. Software latency alone (F1) is **not** this number
and must not be reported as it.

- Tool: `eval/latency.html` (flashes a square while A is down), filmed at 240 fps.
- Data: `eval/results/latency.csv` — `participant,condition,trial,frames,fps`, condition `helm` or
  `controller`, 20 trials each. One frame at 240 fps ≈ 4.2 ms.
- Reported: pooled median and p90 for both conditions, with trial count and *n*.
- Chart: `latency.png`.

### H2 — False triggers per minute

What it measures: presses nobody intended, while the participant talks and watches instead of playing.
Every fire in the recording counts as false.

- Record: `python -m helm --player NAME --no-server --seconds 180 --record eval/results/rec_NAME.npz`
  — stops itself at exactly 3:00, so the minute segments line up: 1 min reading aloud, 1 min chatting,
  1 min watching gameplay. Needs a **named** profile; `guest` and `judge` never save a calibration.
- Score: `python eval/false_triggers.py eval/results/rec_*.npz --game SuperTuxKart`.
  Same frames scored twice — (a) raw blendshape crossing 0.5, no calibration, no hysteresis;
  (b) full Helm: calibration, hysteresis, hold times, the learned "none" class, the pause rule.
- Reported: median per minute per condition. Chart: `false_triggers.png`.
- A warning that a profile was missing means fix it and re-run. **Do not report a run with warnings.**
- Use a reading text that is *not* in `ui/src/readingTexts.ts`, or the model has seen it.

### H3 — Pointing throughput with restricted movement

What it measures: how well per-player scaling beats a fixed gain when someone can only move a little.
This is the differentiator metric. `TP = IDe / MT`, `IDe = log2(Ae / We + 1)`, `We = 4.133 · SDx`
(ISO 9241-9).

- Tool: `eval/target_test.html`, 9 targets, two ring sizes × two target sizes, 9 timed selections per
  block, one unsaved practice block first.
- Conditions: **(c)** profile `NAME_c`, full setup calibrated to about a third of their normal range;
  **(d)** profile `NAME_d` via `?quick=1`, fixed 20° each way.
- **Steering sensitivity must read 1.0× in both conditions**, or the comparison is void.
- Separate `NAME_c` / `NAME_d` profiles exist so the restricted calibration never overwrites `NAME`'s
  real one — which H2's scoring reads. Alternative: score H2 before running H3.
- Data: `eval/results/target_NAME_CONDITION.csv` (the page's Download CSV). Chart: `throughput.png`.
- Misses still count; they widen `We`. Optional mouse baseline if there is time.

---

## 3. Footnote numbers

| Metric | How | Notes |
|---|---|---|
| F1 software latency | the dashboard's "Total delay" tile, or the `median total latency X ms` line Helm prints on exit | one row per participant in `software_latency.csv`; `total_ms = t_output - t_capture` |
| F2 LOTO accuracy | the "recognized X% of the time" figure after teaching a move, as a fraction | it classifies the median of each held-out take — **not** event recall, and not a false-trigger figure |
| F3 launch to first race | stopwatch from `python -m helm` to the kart moving, first-time user | the 15-second judge quick-start claim lives or dies here |
| F4 participant count | — | minimum 3; teammates are fine |

Both F2 and F3 go in `eval/results/participants.csv`: `participant,loto_accuracy,launch_to_race_s`.

### Mandatory disclaimer

Every slide or page carrying these numbers states: **no participant had a motor impairment, and the
restricted-range condition is a proxy.** `analysis.py` prints this line on every run. It is not
optional, and it is the honest framing of a 36-hour study.

---

## 4. P2 hardware metrics (our lane, already partly measured)

Not in SPEC section 12, but these are what make the hardware and physical-AI claims real. Measured on
the bench on the real UNO Q rig; recorded in `docs/status/P2.md`. Repeated here so they are findable.

| Metric | Value | Status |
|---|---|---|
| B1 rest baseline | ≈ 2390 mV (mid-rail), ADC step 2 mV | BENCH, 1 rig |
| B1 rest noise | 12–40 mV peak to peak | BENCH |
| B2 hard sip | 22 mV absolute → 2360 mV displacement; repeats 2360 / 2360 / 1766 | BENCH, 1 person |
| B2 hard puff | 4792 mV absolute → 2410 mV displacement; repeats 2410 / 1024 / 1078 | BENCH, 1 person |
| B2 noise margin | 40 mV noise vs a 450 mV soft-sip threshold → **>10×** | BENCH |
| B3 serial link | 7520 of 7521 lines parsed clean, ≈ 68 lines/s | BENCH |
| B4 per-player calibration | accepted: sip 1175, puff 740 mV (§9) | **MEASURED** |
| B5 breath event latency | release-classified, so ≈ 200 ms after the breath stops | NOT MEASURED |

Two things worth stating plainly when these get quoted:

- Puff is **not repeatable** (2410 / 1024 / 1078) and sip is (2360 / 2360 / 1766). That asymmetry is
  why `BREATH_MAX_PUFF_MV` (1000) and `BREATH_MAX_SIP_MV` (1800) differ, and why calibration takes
  **half** the measured peak, not the peak. Quoting a single best puff as "the" figure would be wrong.
- B4 is the highest-value 60 seconds available: unit tests cover the happy path with faked peaks only,
  and the two real bench attempts were both *refused* by the 200 mV floor (the breath landed in the
  next prompt's window — since fixed, `CALIB_BREATH_STEP_S` is now 6.0 s). The refusal floor working
  on real hardware is itself a result, but it is not a measured range.

---

## 5. Repo health (R1, R2)

| Metric | Target | Now |
|---|---|---|
| R1 test suite runtime | under 10 s (CLAUDE.md) | **12.76 s at 418 tests — over the cap** |
| R2 `--mock --output null --no-server --seconds 3` | exit 0 | 0 |

R1 is not from any one lane's changes; it crept up. The honest fix is lazy-importing `mediapipe` and
`deepagents` rather than deleting tests, and it is cross-lane — raise it with the captain before touching
anyone's imports.

---

## 6. Who can produce what

Split honestly, because most of this cannot be done at a keyboard.

**Doable now, at a keyboard, no hardware (P2's Claude session):**

- This tracker, and keeping it current.
- A full **synthetic dry run** of the toolchain before any participant sits down: generate a mock
  recording, score it, run `analysis.py`, confirm the CSV schemas the tools *write* match the ones
  `analysis.py` *reads*, and that the charts render. Catching a schema mismatch now costs minutes;
  catching it with three participants already recorded costs the whole study.
- Housekeeping that blocks the laptop work: stop tracking `profiles/*/gestures.npz` (they change on
  every calibration, so `git pull` complains on the laptop), and fix
  `tests/test_output.py::test_auto_falls_back_to_null_when_no_driver_is_available`.
- Writing up whatever comes back, and handing P4 the `results.ts` block and `headline.json`.

**Needs the Windows demo laptop (a human at that machine):**

- Anything through a real pad: ViGEmBus, `vgamepad`, binding SuperTuxKart. F3, and H1's `controller`
  baseline. This Mac returns `NullPad` by design, so no gamepad path can be exercised here.
- The keyboard fallback on a second laptop.

**Needs humans and a phone (cannot be automated at all):**

- H1: filming at 240 fps and counting frames by eye. 40 clips per participant.
- H2: being recorded for 3 minutes reading, chatting and watching.
- H3: sitting at the target page for 4 blocks × 9 selections, twice.
- B4: one person breathing into the tube through the dashboard button.
- The Face ID check: a second person stepping in front of the camera.

**Needs another lane:**

- `eval/*.py` and `eval/PROTOCOL.md` are **P3-owned** (`# OWNER: P3`). P2 writing *data* into
  `eval/results/` is fine and is the intent of the handoff; changing the scoring scripts is not.
  If a script needs a fix, send P3 the exact request. `ui/src/results.ts` is **P4-owned** — hand over
  the printed block, do not paste it in.

---

## 8. What has actually been measured (offline, 2026-11-15, commit f0abe64)

Taken on a macOS dev machine: no gamepad, no participants, no hardware. Raw data in
`eval/results/offline_current_checkout.json`. **None of this is H1, H2 or H3** — those still need
humans and the Windows laptop. Do not let these numbers be quoted as the study.

### F2 — Learned-gesture accuracy: MEASURED

`GestureModel.fit()` on the three committed profiles' real recorded takes.

| Profile | Learned move | LOTO accuracy | `none` class |
|---|---|---|---|
| `demo` | `sliding_jaw_right` | **1.00** | 1.00 |
| `guest` | `sliding_jaw`, `sliding_right` | **1.00**, **1.00** | 0.80 |
| `judge` | `jaw_moving`, `sliding_jaw_right` | **1.00**, **1.00** | 0.55 |

**All 5 learned classes: 100%.** That is the number the dashboard reports after teaching a move.

The `none` column is the one to pay attention to: for `judge`, 5 of 11 held-out everyday-face takes
were labelled as a gesture. Read alone that looks like a false-trigger rate. It is not — see below.

### Offline false triggers: 3.13 per minute, and a finding

Leave-one-negative-take-out: hold out one recorded everyday-face take, refit on the rest, replay the
held-out take through the real `GestureEngine` and `Mapper` (P3's `eval/learned_replay.evaluate`,
unchanged). The held-out take is never in the training data.

- **27 held-out takes, 57.5 s of everyday face, 3 false fires → 3.13 per minute pooled.**
- **24 of 27 takes totally clean.**
- All 3 fires were `guest` under the *default* mapping, which puts every learned gesture on A.
  **Under both real game mappings (`demo`, `judge`): zero fires.**

**The finding worth knowing:** `judge`'s `none` LOTO accuracy is 0.55, but its false-trigger replay
fires **zero** times. The two disagree because `classify_take` labels a whole take by its median
score, while the engine requires a score above 0.65 sustained for ~67 ms *and* passing distance
rejection. A take can be median-labelled a gesture and never once cross the engine's gate. So
`loto_accuracy`'s `none` column **overstates** false triggers, and the engine's qualification gating
is doing real work. This is the concrete reason the warning in §3 about `loto_accuracy` matters.

Caveats, which are large: 57.5 s against the protocol's 540 s; timestamps synthesised at 30 fps
because recordings carry none; takes of 0.5–14.8 s, so one fire in a 1.3 s take reports as 47/min
(the pooled rate is the honest one); enrollment negatives rather than a fresh session of reading,
chatting and watching. **Three committed dev profiles are not three participants.**

### F1 — Software latency: PARTIAL

| Path | Median | Frames | What it is |
|---|---|---|---|
| Control path only (`--mock`) | **0.23 ms** (0.28 / 0.23 / 0.21 over 3 runs) | 1808 | normalize → gestures → mapper → pad. Mock bypasses MediaPipe. |
| ~~Full pipeline, "real camera"~~ | ~~4.54 ms~~ | 151 | **VOID — taken on a black camera.** See §11. |

Superseded by §11, which has the real figure.

### R1 — Suite runtime: MEASURED, failing

**415 tests, 13.68 s** against CLAUDE.md's 10 s cap. Smoke run exits 0 (30.1 fps, 0.29 ms median).

### Reproducing

The two scripts live in the session scratchpad, not the repo, because `eval/` is P3-owned. They
import `helm.gestures` and `eval/learned_replay` unchanged. If these numbers are going to be
re-run by anyone else, they need a home — that is a request to send P3, not a file for P2 to add.

---

## 9. B4 closed: the first accepted breath calibration (2026-11-15)

`BreathCalibrator` had never once succeeded end to end across three sessions. It does now, on the
real UNO Q rig, with a human: **`accepted = True`, no refusal notes, scales applied.**

| | peak | scale set (peak x 0.5) | config default |
|---|---|---|---|
| Sip | 2350 mV | **1175** | 1800 |
| Puff | 1479 mV | **740** | 1000 |

### Why it had always failed, and it was never the breather

The step window was consumed by its own prompt. Measured at the mac's speech rate:

| step | window before | spoken prompt |
|---|---|---|
| rest | 1.5 s | 3.55 s |
| sip | 6.0 s | **4.48 s** |
| puff | 6.0 s | 3.64 s |

A 4.48 s prompt in a 6.0 s step left ~1.5 s to react and sip hard, and the rest step ended 2 s
before its own prompt finished, so the sip window opened — and reset the peak — while the player
was still being told to keep their hands off the tube. The earlier 4.0 → 6.0 s fix assumed a ~3 s
prompt and so did not clear it.

### The fix, and the mistake inside the fix

`CALIB_BREATH_STEP_S` 6.0 → 10.0, plus `CALIB_BREATH_LEAD_S`: the step's opening lead is not
measured and everything after it is.

The first attempt measured only the *trailing* 4 s instead, which is the opposite mistake and was
caught by the user, not by a test: a player who reacts promptly peaks early and has nothing left by
the end of the step, so a trailing window discards exactly the people it should serve. Live run
with a 2.5 s lead: **the sip crossed the floor 0.4 s after the window opened** — a slightly faster
reaction would have been thrown away again. Lead is now **1.5 s**, which only has to clear the
involuntary exhale after releasing a hard sip (the previous step's tail), not the prompt — there is
no pressure while the player is being talked to. Three tests pin an early reaction, a late one, and
pressure during the lead.

### Repeatability, correcting an earlier claim

Across four efforts each on this rig and person:

| | measurements (mV) | range |
|---|---|---|
| Sip | 2072, 2372, 1954, 2350 | 1954–2372, tight |
| Puff | 1932, 2394, 2394, **1479** | 1479–2394, **variable** |

An earlier note here said puff had become repeatable and the config's 1800/1000 sip/puff asymmetry
was no longer justified. The fourth measurement contradicts that: puff still varies by over 900 mV.
The bench's original reasoning stands, and `CALIB_BREATH_FRACTION = 0.5` (half the peak, not the
peak) is doing necessary work. **Do not collapse the two scales to one number.**

### Still open

B5, breath event latency. Events are release-classified, so the event lands after the breath stops;
the ~200 ms figure in §4 is an estimate, not a measurement. It needs one 20 s live run with three
quick puffs, timing breath onset against the event reaching `poll()`. No phone needed, contrary to
what the status board said.

---

## 10. B5 measured: breath event latency (2026-11-15)

Live on the real rig, timing breath onset and release in host time against the event reaching
`SipPuff.poll()`. No phone needed; the earlier note that this required high-speed film was wrong.

| | median | range | n |
|---|---|---|---|
| **Release -> event** | **0 ms** | 0-0 | 5 |
| Onset -> event | 1199 ms | 779-1709 | 5 |

**The software adds no measurable delay.** The event is emitted on the same sample on which the
level falls back through `BREATH_SOFT`. Sample period is ~15 ms at 67 lines/s, so 0 ms means within
one sample.

**What players actually feel is the hold, not latency.** Because events are release-classified, the
action lands when the breath *stops*: 0.8-1.7 s after they start puffing, entirely their own hold
duration. `docs/status/P2.md` estimates "about 200 ms later than it feels like it should" -- that is
4-8x too small, and it is not a latency figure at all.

### Demo consequence, and a decision for the captain

The `demo` mapping latches RT (accelerate) on `hard_puff`. So the kart starts moving 0.8-1.7 s
after the player begins puffing, not when they begin. On a race start that is visible.

It is fixable: a hard breath can be recognised *during* the press, as soon as the level crosses
`BREATH_HARD` and `BREATH_MIN_PRESS_MS` has elapsed, instead of waiting for release to classify
strength. That would cut the felt delay to about 80 ms. It changes `SipPuffEvent` semantics that
the `Mapper` and its tests rely on, so it is not a P2-only call -- raise it before the demo.

### Release chatter is correctly suppressed

Four efforts appeared as a hard sip released and bounced around the threshold: peaks 0.36-0.37,
holds 14-31 ms. **All four produced no event.** `BREATH_MIN_PRESS_MS = 80` is now validated against
real release behaviour rather than synthetic samples -- a cough or a release bounce cannot fire the
pad.

---

## 11. F1 measured, and a camera trap that voided an earlier number (2026-11-15)

**Median total latency 9.57 ms**, 584 frames at 30 fps, one person on the dev machine.
Face found in **99.8% of frames** (583/584), with real movement (yaw -15.9 to -1.2 deg, pitch +9.1
to +22.9 deg) and real expressions (blendshape peak 0.93), so the tracker was genuinely working
rather than idling.

`total_ms = t_output - t_capture`: capture, MediaPipe inference, normalisation, gestures, mapping
and the pad write. It is **software latency only** and is never the motion-to-screen figure (H1),
which additionally carries the camera's own exposure and readout, Windows, the display and the
game.

### The trap, worth 15 minutes to anyone who repeats this

This machine exposes **two** cameras. Index 0 is black; index 1 is the real one. Nothing in the log
says so -- `helm.capture` cheerfully reports `camera 0 opened: 640x480, driver reports 30 fps` and
the pipeline runs at a steady 30 fps on pure black frames.

An earlier run here recorded 4.54 ms as the full-pipeline latency on index 0. It was wrong by more
than 2x, because MediaPipe does far less work when there is no face to land marks on. A latency
measurement with no face in it is not a conservative estimate, it is a different measurement.

**Check the camera before trusting any face number**: `--camera N`, and confirm the face-found rate
is near 100%. A run with a low face rate is not a slow run, it is a blind one.

### Not written to `software_latency.csv`, on purpose

`analysis.py` reads that file and pools it into the study. This figure is one person on a macOS dev
machine, not a study participant on the demo laptop with its own camera and CPU. Pooling the two
would quietly mix machines inside a single reported median. The study's rows belong to the study;
this number lives here.

---

## 12. H2 measured, participant 1 (2026-11-15)

The first headline number with real data. `analysis.py` now emits a `falseTriggers` line instead of
"not measured".

Recording: `p1`, 5397 frames, 29.9 fps, exactly 180.0 s, **face found in 100% of frames**. Full
setup plus Teach a move with the everyday face ticked (negatives went from 7 takes / 341 rows to
18 takes / 1173 rows). Median software latency on this run was 9.28 ms, corroborating §11's 9.57 ms
on an independent sample.

| condition | false triggers per minute |
|---|---|
| Fixed 0.5 threshold, no calibration | **23.67** |
| **Helm** | **11.00** |

F2 for this participant: `move_2` 1.00, `nod_up` 1.00, `none` 0.944.

### Per-minute breakdown, which matters more than the headline

| minute | baseline | Helm |
|---|---|---|
| reading aloud | 9 (eyes 6, smile 3) | 7 (smile 5, nod 2) |
| chatting | 41 (smile 25, eyes 15, jaw 1) | 22 (smile 14, nod 6, jaw 2) |
| watching video | 21 (**eyes 21**) | 4 (nod 4) |

**1. The pause rule is a complete success: eye-closure false triggers 42 -> 0.** Every blink that
fooled the fixed threshold was rejected by the 2 s hold. This is the cleanest result in the data.

**2. `smile` is the problem gesture.** 14 of Helm's 22 fires while chatting are smiles; the
participant was talking to a friend. `smile` -> B (nitro) means a player who enjoys themselves
fires nitro constantly. **This quantitatively justifies the `judge` profile's minimal mapping**
(yaw steer, auto throttle, eyebrow only) rather than leaving it a hunch. Consider dropping `smile`
from `demo` too.

**3. The learned gesture is charged unfairly.** `nod_up` fired 12 times, but the baseline has no
learned class and cannot fire it at all. Helm is being penalised for a capability the baseline
lacks. State this whenever the comparison is reported.

### Caveats that must travel with the number

- **n = 1.** The protocol wants 3. Any slide carrying this says n=1 until that changes.
- **Collected on a macOS dev machine, not the demo laptop.** If participants 2 and 3 run on
  Windows, do not pool them into one median: different camera, different CPU, different tracking.
  Either finish all three here, or treat this as a pilot and redo it there.
- 11/min is a false trigger every 5.5 s. That is a mapping problem more than a tracking problem,
  and the breakdown names the gesture responsible.

---

## 7. Order of work

From P1's handoff at the top of `docs/status/P2.md`. Not a schedule, a dependency order.

1. Dry-run the toolchain on synthetic data (keyboard, now).
2. Housekeeping: the `gestures.npz` tracking and the flaky test (keyboard, now).
3. Laptop setup and a real run-through; write down what is broken.
4. B4: one real human breath measurement. Sixty seconds, highest value per second of anything here.
5. Per participant, in this order: profile + teach a move → H2 record and score → H3 (c) and (d) →
   H1 filming → `participants.csv` row.
6. `python eval/analysis.py`; commit `eval/results/`; hand P4 the block and `headline.json`.
7. Demo prep: tune the demo profile in the game, backup race video, keyboard fallback, table kit.

H2 before H3 per participant, or the restricted calibration overwrites the profile H2's scoring reads.
