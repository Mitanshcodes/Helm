<!-- OWNER: P1 -->
# Tuning gestures by hand

How a face gesture turns into a button press, which number changes what, and where to change it while
the game is running.

## How a press happens

For each expression, MediaPipe gives a raw score from 0 to 1 every frame. Helm turns it into a **level**:

```
level = (score - neutral) / (peak - neutral)        clipped to 0..1
```

- `neutral` is your relaxed face and `peak` your full expression, both measured in calibration. Level 1.0
  means "as big as you did it in calibration".
- A button **presses** when the level stays at or above `on` for `min_hold_ms`.
- It **releases** when the level drops to `off` or below.
- If two mapped gestures are both up, the weaker one is ignored when the stronger is well past its own
  threshold (`CROSSTALK_RATIO`). A smile also lifts the jaw score a little; this stops it pressing Y.
- The dashboard's "Face controls" tiles show each live level against its `on` line. Use them to see what
  is happening.

## Use a named player

Calibrations for `guest` and `judge` are not saved to their profiles. Dev mode saves a separate
calibration copy in its dataset; see [DEV_MODE.md](DEV_MODE.md). For an editable saved profile, start with a name:

```
python -m helm --player mitansh
```

Calibrate once, then press **Save profile** in the Mapping tab. That writes both files below.

## The fast way: the Mapping tab

Mapping tab, "How hard each gesture must be made":

- **Slider = `on`.** Move it right if a gesture fires by accident; left if it does not fire.
- **Time = `min_hold_ms`.** Raise it to 150 or 200 ms if talking sets a gesture off. Lower it if a press
  feels late.

Press **Apply** to use the change now, then **Save profile** to keep it.

## Editing the files directly

Helm checks these files once a second while running. When you save in your editor, the change is applied
straight away and the dashboard says "Applied your edits to ...". If a file has a typo or a bad value,
the dashboard shows the error and Helm keeps using the previous version. No restart is needed.

### `profiles/<player>/SuperTuxKart.json` (the mapping)

```json
"gestures": {
  "brow_raise": {"kind": "blendshape", "sources": ["browInnerUp"], "on": 0.6, "off": 0.4, "min_hold_ms": 100},
  "smile": {"kind": "blendshape", "sources": ["mouthSmileLeft", "mouthSmileRight"], "combine": "max", "on": 0.6, "off": 0.4, "min_hold_ms": 100}
},
"buttons": [{"gesture": "brow_raise", "target": "A", "mode": "tap"}],
"axes": [{"source": "yaw", "target": "lx", "deadzone": 0.08, "curve": 1.5, "invert": false}],
"pause": {"gesture": "eyes_closed", "hold_ms": 2000}
```

| Field | What it does | Typical change |
|---|---|---|
| `on` | Level needed to press, 0..1. | Fires by accident: 0.7 to 0.8. Will not fire: 0.45 to 0.5. |
| `off` | Level below which it releases. Must be lower than `on`. | Keep about 0.2 below `on`. |
| `min_hold_ms` | How long the level must stay past `on` before pressing. | Talking sets it off: 150 to 200. Feels late: 60. |
| `sources` | Which MediaPipe scores make the gesture. | Names from `helm/contracts.py` `BLENDSHAPE_NAMES`. |
| `combine` | With two sources: `max` = either one, `min` = both. | |
| `mode` | `tap` = short press. `hold` = held as long as you hold the face. `toggle` = press on, press off. | Drift or accelerate: `hold`. |
| `gain` | Steering sensitivity: your calibrated head range is divided by it (0.5 to 3). The "steering sensitivity" slider under the controller sets it. | Turning your head a lot to steer: 1.5 to 2. |
| `deadzone` | Steering ignores head turns smaller than this share of your range. | Car wanders: 0.12. |
| `curve` | Above 1, small turns steer gently and big turns still reach full lock. | Twitchy: 2.0 to 2.5. |
| `invert` | Flips the steering direction. | |
| `pause.hold_ms` | How long the eyes stay shut to pause or resume. | |

### `profiles/<player>/calibration.json` (your measurements)

| Field | What it means | Typical change |
|---|---|---|
| `range.yaw` | `[left, right]`: degrees of head turn that give full steering lock. | Steering too twitchy: raise both (for example 25). Need to turn too far: lower them (minimum 8). |
| `range.pitch` | `[down, up]`, the same for nodding. | |
| `neutral.yaw`, `neutral.pitch` | Head angle when looking straight ahead. | The car pulls to one side with your head straight: move `neutral.yaw` toward your real straight-ahead angle (the camera panel shows the live "Turn (yaw)"). |
| `blend_peak` | Raw score of your full expression, by name. | A gesture fires too easily: raise its peak by 0.1. Hard to reach: lower it. Delete an entry to use the default (neutral + 0.5). |
| `blend_neutral` | 52 raw scores of your relaxed face, in `BLENDSHAPE_NAMES` order. | Rarely needs editing. Recalibrate instead. |
| `reliable` | Expressions calibration found clear. Only the coach uses this. You can map anything by hand. | |

`on` and `blend_peak` both control how big a move must be. Prefer `on`: it is one number per gesture and
the dashboard shows it. Change `blend_peak` only when even `on` 0.9 is too easy, or 0.45 too hard.

## Symptom to fix

| What you see | Try first | Then |
|---|---|---|
| A gesture fires on its own while you talk or steer | `on` +0.1 | `min_hold_ms` 150 to 200 |
| The wrong button fires with a gesture (smile also presses Y) | `on` +0.1 on the wrong one | Lower `CROSSTALK_RATIO` in `helm/config.py`, for example 0.7 |
| A gesture does not fire | `on` 0.5, and watch its tile while doing it | Lower its `blend_peak`, or recalibrate it bigger |
| Fires twice for one move | `off` lower (0.3) | |
| Steering too twitchy | `range.yaw` up | `curve` 2.0 to 2.5 |
| Gestures get easier to trigger the longer you play | Fatigue adaptation lowers thresholds after the first minute | `FATIGUE_MIN_SCALE = 1.0` in `helm/config.py` turns it off (P3's setting: tell P3) |

## Sip-and-puff

### How breath is measured

1. **Arduino.** The board reads the pressure sensor about 70 times a second and sends
   `P,<millis>,<millivolts>`. About 2400 mV means no breath; a sip pulls it down and a puff pushes it up.
2. **Baseline.** On connect, Helm takes the median of the first 2 s as the resting value. While nobody is
   breathing into the tube, it keeps following slow drift.
3. **Level.** Each sample becomes a signed level from -1 to 1:
   `(millivolts - baseline) / max_puff_mv` for a puff, or `/ max_sip_mv` for a sip.
   - The sign is the direction. The size is the strength: 0.5 is half of a firm breath, and 1.0 is a firm
     breath or harder.
   - `max_puff_mv` and `max_sip_mv` are half of your strongest breath in "Measure my breath", or the defaults
     1000 and 1800.
4. **Events.** Separately, each breath is classified when it ends:
   - It must last at least 80 ms.
   - Its peak decides the strength: under 0.65 is soft, 0.65 or more is hard.
   - So you get one of `soft_puff`, `hard_puff`, `soft_sip`, `hard_sip`.

### What you can map (Mapping tab, "Breath" group, shown once the sensor is connected)

| Pick | What it does | Good for |
|---|---|---|
| **Puff (live)** / **Sip (live)** | Level-based. Presses as soon as the breath passes `on` (30% by default) and stays pressed while you keep breathing. On LT or RT with **Analog**, the trigger follows the breath strength: a gentle sip is a light brake. | Brake, accelerate, drift: anything held or analog. |
| **Hard puff (when you stop)**, etc. | Fires once, about 200 ms after the breath ends, knowing whether it was soft or hard. Offered only as **Tap** or **On / off**. | Separate soft and hard actions; a latched throttle (On / off). |

A live breath gesture cannot tell soft from hard: a hard puff passes through every lower level on the way
up. To get two actions from one direction, use the "when you stop" events.

### Checking it on the dashboard

- **Breath strip:** once the board is connected, a sip/puff strip appears in the "your moves → the buttons"
  header, next to "Measure my breath".
  - Sip fills left of the middle and puff fills right, with ticks at soft (25%) and hard (65%).
  - It also shows the strength in words, for example "puff 51% · soft".
- **Move cards:** every breath input that is mapped gets one, showing its strength against its notches. It
  turns pink ("FIRING!") while it presses.
- **Not connected:** if the mapping uses breath but no board is found, the header says "Breath sensor not
  connected". Helm checks the ports every second.
- **"Measure my breath"** sets `max_puff_mv` and `max_sip_mv` for this player. It also runs by itself
  after a face calibration when the board is connected.

### Tuning breath

- **The live gestures' `on` slider** in the Mapping tab goes down to 10%. Lower it if you have to blow too
  hard; raise it if breathing or talking sets it off.
- **`profiles/<player>/breath.json`:** `{"max_puff_mv": 1000, "max_sip_mv": 1800}`. Lower a value to make
  that direction reach 100% with less effort. It is applied live, like the other files.
- **`helm/config.py`:**
  - `BREATH_SOFT` 0.25 and `BREATH_HARD` 0.65: where the events count as soft and hard.
  - `BREATH_LEVEL_ON` 0.3 and `BREATH_LEVEL_OFF` 0.15: defaults for the live gestures.
  - `BREATH_MIN_PRESS_MS` 80.

## Numbers in `helm/config.py` (restart Helm after changing)

| Name | Default | What it does |
|---|---|---|
| `CROSSTALK_RATIO` | 0.8 | Lower holds back side effects more. Too low blocks two moves made at once. |
| `MIN_EXPRESSION_SPAN` | 0.15 | Smallest `peak - neutral` ever used, so no expression is hair-trigger. |
| `CALIB_MIN_SPAN` | 0.2 | Smallest scale calibration will measure for an expression. |
| `REST_SPAN_FACTOR` | 2.5 | Calibration makes each scale at least this many times what your relaxed face does while you turn your head, so steering alone stays below `off`. |
| `EXPRESSION_MIN_HOLD_MS` | 100 | `min_hold_ms` the coach puts on face gestures. |
| `TRIGGER_MIN_HOLD_MS` | 60 | `min_hold_ms` for gestures that do not set one (P2's setting). |
| `AXIS_DEADZONE`, `AXIS_GAMMA` | 0.08, 2.0 | Steering defaults for new mappings. |
| `ONE_EURO_MIN_CUTOFF` | 1.0 | Lower = smoother, laggier steering. |

After changing calibration code or these numbers, recalibrate. Old `calibration.json` files keep the old
measurements.
