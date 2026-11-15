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
| **H2** | False triggers per minute | fixed 0.5 threshold, no calibration | `false_triggers.csv` | NOT MEASURED | 3 min recording per human |
| **H3** | Pointing throughput, bits/s | same small movements at fixed gain | `target_*.csv` | NOT MEASURED | human at the target page |
| F1 | Software latency, median `total_ms` | — (reported alongside H1) | `software_latency.csv` | NOT MEASURED | any real camera run |
| F2 | Learned-gesture accuracy (leave-one-take-out) | — | `participants.csv` | NOT MEASURED | teach-a-move per human |
| F3 | Launch to first race, seconds | — | `participants.csv` | NOT MEASURED | demo laptop + game |
| F4 | Participant count *n* | — | `participants.csv` | 0 of 3 minimum | 3 humans |
| B1 | Breath rest baseline and noise | — | `docs/status/P2.md` | BENCH | — |
| B2 | Breath committed-swing displacement | rest noise | `docs/status/P2.md` | BENCH | — |
| B3 | Serial link line-loss rate | — | `docs/status/P2.md` | BENCH | — |
| B4 | Per-player breath calibration, accepted | refusal floor | `profiles/<p>/breath.json` | NOT MEASURED | one human breath |
| B5 | Breath event latency (release-classified) | — | nowhere yet | NOT MEASURED | bench + phone |
| R1 | Test suite runtime | CLAUDE.md's 10 s cap | CI/local | **FAILING** (~15 s) | — |
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
| B4 per-player calibration | **0 valid human measurements** | NOT MEASURED |
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
| R1 test suite runtime | under 10 s (CLAUDE.md) | **≈ 15 s at 411 tests — over the cap** |
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
