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
