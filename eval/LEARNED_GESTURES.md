<!-- OWNER: P3 -->
# Learned-gesture integration

The existing `GestureModel` API now uses the best observed **blendshape** variant from the separate
Helm studies: regularized logistic regression with feature selection and distance rejection.
It is experimental. Raw landmark features have not been compared, and independent control
reliability is not established.

## Use and behavior

Use the existing dashboard's **Teach Helm your own move** flow: everyday-face negatives, then five
comfortable takes per gesture. Recording, background fitting, deletion, mapping and profile APIs
remain connected. Each player trains their own profile; research participants are not defaults.

Training samples up to seven frames per positive take and negatives at up to three times the largest
positive class. It selects four discriminative channels per gesture and unions them, with a 0.05
standard-deviation floor. Candidates are the 51 facial movement channels; neutral, head axes and
breath cannot become learned classifier features. The study profiles selected 8, 8 and 9 channels.
L2 logistic regression uses C=0.1 and balanced weights. Predictions far from their enrollment center
are rejected to `none` (enrollment-derived radius, rejection factor 1.5). Explicit negatives are needed
before arming; invalid inputs return `none`. Scores are not calibrated guarantees of correctness.

`GestureEngine` qualifies a mapped winner above 0.65 for about 67 ms, then outputs a binary hold level
until its score stays below 0.45 for about 67 ms. A new gesture needs release and a new hold. Face loss,
stale/nonmonotonic timestamps and publication of a newly fitted model reset qualification. Timers use
signal timestamps, independent of frame rate. Four-frame probability smoothing has been removed.

Explicit mapping `on` values can make qualification stricter; an explicit `min_hold_ms` can request
a longer hold. The Mapper consumes learned qualified levels without a second debounce, preserving
tap/hold/toggle modes and refractory. Built-in blendshape/breath controls retain their behavior.
Binary learned levels also prevent fatigue scaling from bypassing the confidence/rejection gate.
They are qualified commands, not analog facial intensity.

Positive peak selection ignores steering/breath excursions. Validation holds out complete positive
takes and negative arrays, fitting selection/scaling within each fold. Its reported quality score
classifies the median of each held-out take's scores; it is not event recall or a new-session
false-trigger measurement.

## Persistence and data use

`profiles/<player>/gestures.npz` retains raw `frames`, `labels` and `groups`, written atomically.
New version-2 files add training settings so refits preserve a saved profile's settings. Legacy raw-take
NPZ profiles load and refit with the new backend. The application needs no study pickle/module paths.
Neutral calibration stays in its existing separate calibration file; new players need their own.

The one-second-per-long-file fitting cap applied to the study dataset. The app retains its explicit
15-second everyday-face enrollment, with bounded negative sampling. Evaluation clips never enter
fitting automatically. This integration adds no ambient self-training.

## Replay all-negative normalized features

Input NPZ: `X` shaped `(n,56)`, strictly increasing `timestamp_s`, and `face` flags. Generate `X`
using that player's saved neutral calibration; raw MediaPipe scores are not interchangeable.

```sh
python eval/learned_replay.py \
  --model profiles/my_player/gestures.npz \
  --features /path/to/negative_features.npz \
  --output /path/to/false-events.json
```

Optional `--mapping profiles/my_player/MyGame.json` checks that mapping's outputs. Otherwise every
learned gesture is connected to an in-memory button mapping for counting. No camera/gamepad/live
output is created. Loading refits saved enrollment only, never the evaluated clip. The formal
fixed-threshold baseline and restricted-range study remain separate unfinished evaluations.

## Evidence and limits

Integrated scores match the three research profiles within `2.3e-8`, with save/load agreement.
The real engine/Mapper replay reproduces **five false commands in 55.97 seconds** on the new negative
`random.mov`, at 2.97, 3.43, 7.87, 47.50 and 49.53 seconds. It was not used for fitting or tuning.
The earlier exploratory result (28/30 brief attempts and zero events in 128.5 seconds of negatives)
reused recordings for selection and did not generalize. Integration preserves that failure; it is not
a reliability fix. Freeze the variant before a fresh-session test. If this failure becomes training
data, reserve a different new clip for independent evaluation.

Historical integration checks against upstream `f8016b3` are in `eval/results/learning_integration.json`;
their test counts describe that earlier snapshot, not the latest checkout. Private participant recordings,
vectors and fitted research profiles remain outside the source repository. Checks:

```sh
python -m pytest -q
python -m helm --mock --output null --no-server --serial off --seconds 3
```
