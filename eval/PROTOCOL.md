<!-- OWNER: P3 -->
# Evaluation protocol

How to run each evaluation, step by step. The design is in `docs/SPEC.md` section 12. Raw data goes in
`eval/results/`; `python eval/analysis.py` turns it into three charts, `headline.json` and the block for
`ui/src/results.ts`.

Every reported number needs a participant count, a median and a baseline. State on the slide that no
participant had a motor impairment and that the restricted-range condition is a proxy.

Run everything on the demo laptop, on a build whose control path has stopped changing, with the virtual pad
(`--output vgamepad`, the default on Windows). Use a **named player** for each participant (`--player sam`):
`guest` and `judge` never save a calibration, and the false-trigger replay needs one.

Recordings store face numbers only (head angles and blendshape scores), never video. Ask before filming.

## 1. Latency, motion to screen

What it measures: from the first visible movement of the eyebrows to the screen changing, through the whole
system (camera, tracking, the virtual pad, Windows, the browser, the display).

Setup
1. `python -m helm`. In the profile screen, pick the participant's profile, or New profile with their name, which
   runs the full setup. A is eyebrow raise in the default mapping; check it in the Anchor's Mapping page.
2. Open `eval/latency.html` in Chrome or Edge, press F11. Press any pad button once if it says "No gamepad yet".
3. Phone in slow motion at 240 fps, on a stand, framing the participant's eyebrows and the square together.
   Turn on room lights; no window behind the participant.

Run
1. Film 20 sharp eyebrow raises, about two seconds apart, relaxing fully between them.
2. Baseline: plug in a real Xbox controller (Helm can keep running) and film 20 presses of A with one finger,
   framing the finger and the square.

Count (frame by frame, in any video app that steps one frame at a time)
- Helm: from the first frame where the eyebrows visibly start to rise, to the first frame where the square
  is white. Baseline: from the first frame the finger touches the button, to the first white frame.
- One row per press in `eval/results/latency.csv`:

```
participant,condition,trial,frames,fps
sam,helm,1,31,240
sam,controller,1,12,240
```

Also note Helm's own software latency: the "Total delay" tile, or the last log line when Helm stops
(`median total latency X ms`). One row per participant in `eval/results/software_latency.csv`:
`participant,total_ms`.

## 2. False triggers per minute

What it measures: presses nobody intended, while the participant talks and watches instead of playing. Every
fire in the recording counts as false. The same frames are scored twice: (a) a fixed threshold with no
calibration (any face gesture the mapping uses crossing a raw score of 0.5 fires) and (b) full Helm
(calibrated scale, hysteresis and hold times, the learned "none" class, the 2 s pause rule).

Run, per participant
1. Set up the profile:
   - Run `python -m helm`. In the profile screen pick New profile and type their name (the name is NAME below).
     The full setup runs: head range, expressions, the nod and Face ID.
   - Then open the Anchor's Your moves page and choose Teach a move. Keep "Include the everyday face" ticked (they
     read a short text aloud). Their own move is optional.
   - Close Helm (Ctrl+C).
2. Record, without the dashboard, so the recording starts the moment the command runs and stops itself after
   exactly three minutes:

   ```
   python -m helm --player NAME --no-server --seconds 180 --record eval/results/rec_NAME.npz
   ```

   It loads NAME's saved setup. Nothing is recalibrated.
3. Start a phone timer at the same moment and have a teammate call out the minutes. Without a break:
   - minute 1: read aloud from paper or another screen (use a text that is not in `ui/src/readingTexts.ts`, so
     it is new to the model);
   - minute 2: chat with a teammate;
   - minute 3: watch a gameplay video.
4. Helm stops at 3:00 and writes the recording.

Score

```
python eval/false_triggers.py eval/results/rec_*.npz --game SuperTuxKart
```

It uses each participant's saved calibration, mapping and learned model, writes
`eval/results/false_triggers.csv` (per participant, minute and condition, with a per-gesture breakdown) and
prints the medians. A warning means a profile was missing: fix it and re-run, do not report it.

## 3. Target test with restricted movement

What it measures: how fast and accurately someone can point with small head movements, with Helm's per-player
scaling (c) against the same small movements at a fixed gain (d). Throughput in bits per second:
`TP = IDe / MT`, `IDe = log2(Ae / We + 1)`, `We = 4.133 * SDx` (ISO 9241-9, effective width).

Mapping for this test (Anchor → Mapping, then Apply): Left stick ← → = "Turn head left / right",
Left stick ↑ ↓ = "Nod chin up / down", A = Eyebrow raise. Nothing else needs to be mapped.

**Steering sensitivity** (the card under the controller) must read **1.0×** in both conditions; press Reset if not.
Otherwise the comparison is not fair.

The restricted range: ask the participant to move about a third of their normal turn and nod, every time,
in both conditions. Demonstrate it, and have a teammate watch for drift back to full movement.

Run, per participant (alternate which condition goes first between participants)
- (c) Helm, scaled: open `http://localhost:8000/` and pick a profile named `NAME_c`. Its full setup runs; in the
  turn and nod steps move only the small range. Open `eval/target_test.html`, condition "(c) Helm", cursor control
  "Rate". Start.
- (d) Fixed gain: open `http://localhost:8000/?quick=1` and pick a profile named `NAME_d`. It runs the quick setup
  (resting face only), so the range stays at the fixed 20 degrees each way. Same page, condition
  "(d) Fixed gain", same cursor control. Start.
- Use these separate `NAME_c` and `NAME_d` profiles, not NAME itself. Otherwise the restricted-range calibration
  overwrites NAME's real one, and the false-trigger scoring (which reads NAME's saved setup) would use it. Or score
  test 2 before running test 3.
- Optional mouse baseline: condition "Mouse baseline".

Each run is one practice block (not saved), then four blocks: two ring sizes by two target sizes, nine timed
selections each. Missed selections still count (they widen We). At the end the page shows throughput per
block; press "Download CSV" and move the file into `eval/results/` (`target_NAME_CONDITION.csv`).

## Also logged

One row per participant in `eval/results/participants.csv`:

```
participant,loto_accuracy,launch_to_race_s
sam,0.93,74
```

- `loto_accuracy`: the "recognized X% of the time" figure after teaching a move (as a fraction).
- `launch_to_race_s`: stopwatch from `python -m helm` to the kart moving in a race, for a first-time user.

## Analysis

```
python eval/analysis.py
```

Prints every headline number with its participant count and baseline, writes `latency.png`,
`false_triggers.png`, `throughput.png` and `headline.json` to `eval/results/`, and prints the lines to paste
into `ui/src/results.ts`. Anything not run yet is reported as "not measured". Never put an estimate on a slide.


## Local model integration

See `eval/LEARNED_GESTURES.md`. The normalized replay tool is `eval/learned_replay.py`; the upstream raw-recording evaluator is retained.
