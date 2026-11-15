# Experimental identity and geometry pipeline

Status: single-player identity protection and full 3D dev capture are implemented on this branch.
The operational gesture classifier is unchanged. The separate `helm-studies` project contains
the geometry/model comparisons and experimental agreement gates; multiplayer routing is not implemented.

See [IDENTITY.md](IDENTITY.md) for enrollment, live rejection and offline evaluation, and
[ML_WORKSTREAMS.md](ML_WORKSTREAMS.md) for the shared extraction interface and scope separation.

- Repository: https://github.com/Mitanshcodes/Helm
- Branch: `experimental/identity-and-geometry`
- Starting upstream revision: `6220c2a`

This branch explores two independent improvements. Neither assumes that increasing feature
dimensions automatically improves recognition. Keep the existing blendshape classifier as a
baseline until independent recordings show a better reliability/latency tradeoff.

## 1. Recognize people and route observations to their profiles

Add a face-identity encoder alongside MediaPipe. Start by evaluating OpenCV SFace with aligned
face crops. Identity embeddings select a profile; they are not added to the gesture classifier.
Enrollment saves several reference embeddings under a stable profile ID, separately from the
person's calibration, gesture model and game mappings. Include encoder/preprocessing versions.

The first implementation now provides explicit SFace enrollment and rejection for one selected
profile/controller. The multi-player session routing below remains a later step.

Proposed runtime flow:

1. Detect faces and associate observations with temporary track IDs. Detection order and screen
   position do not identify a person.
2. Match each track against enrolled identity templates. Require an acceptance threshold, a
   margin over competing profiles and temporal confirmation. Unknown/ambiguous tracks remain
   unassigned, and assignments must be one-to-one across active tracks and profiles.
3. Route confirmed observations through a per-player session containing its own calibration,
   filters, gesture engine, mapper, fatigue state, pause state and controller.
4. Keep controller slots stable while people move or briefly disappear. Neutralize output on
   loss/ambiguity and reset transient state before rearming after reacquisition.

Run recognition asynchronously on new tracks and periodically thereafter; benchmark its cadence
with gesture inference on the target laptop. Bind each sip/puff device to one player explicitly.
WebSocket commands, onboarding, snapshots and dev datasets need profile/track/session identifiers.
Do not update identity templates from uncertain automatic matches.

## 2. Learn gestures from richer facial features

MediaPipe produces 3D landmarks. This branch now retains both the 478 preview points' `x,y`
coordinates and all 478 `x,y,z` points, including them in dev recordings. The operational
`GestureModel` still receives its separate 56-value vector: 52 blend deltas, three head axes and
breath, and selects facial movement channels only. Full geometry is available for experiments
without silently changing legacy gesture-model inputs.

Initial exploratory studies compared 18 standalone variants and six agreement gates. Full geometry
alone did not improve the reliability tradeoff; blendshape/geometry-centroid agreement is a
candidate for a fresh holdout test. Existing recordings were reused for selection, so these are
not independent reliability claims. Research reports, private datasets and candidate models remain
in `helm-studies/artifacts/geometry-pilot-20261114`, outside this source repository.

Identity-protected live extraction uses `num_faces=4`, while the default research extractor uses
`num_faces=1`; MediaPipe smoothing and feature values differ. Enroll identity before collecting
protected calibration/gesture data, and validate that mode separately before adopting a candidate.

Compare these feature modes using the same enrollment and evaluation splits:

- Existing selected blendshape features: the baseline.
- Full MediaPipe geometry: retain `x,y,z` for 478 points, giving 1,434 raw values before preprocessing.
- Combined blendshape and geometry features, with explicit scaling for each feature family.
- A different landmark model or learned gesture embedding only if these modes leave a measurable
  failure that justifies additional compute and dependencies.

Geometry preprocessing must handle MediaPipe's coordinate conventions, translation, scale and
rigid head motion, then reference the player's neutral shape. Avoid allowing camera position or
head steering to substitute for the intended facial movement. Evaluate regularized classifiers
and, where useful, dimensionality reduction fitted only on enrollment data; a full unregularized
model is a poor default for small take counts.

Introduce versioned feature schemas recording the encoder, feature family, dimensions, ordering,
normalization and neutral reference. Preserve legacy 56-value enrollment loading. Do not silently
reinterpret existing `gestures.npz` files or overwrite a working baseline with an incompatible
experimental model. Keep identity embeddings and gesture features separate in storage and APIs.

## Implementation order

1. Preserve full 3D landmarks and extend dev recordings with versioned geometry data. Check frame
   alignment and retain the current classifier behavior.
2. Add interchangeable gesture-feature backends and offline geometry/blendshape comparisons.
3. Add identity enrollment, unknown rejection and automatic profile loading for one active player.
4. Extract per-player runtime state, add multi-face association, and route simultaneous players to
   separate controllers. Disable the shared-keyboard fallback for distinct multiplayer controllers.
5. Integrate onboarding/profile UI and record the evidence needed to choose the production variant.

## Validation before adopting a variant

Hold out complete takes and independent sessions; do not split adjacent video frames randomly.
Fit selection, scaling and dimensionality reduction within each training fold. Freeze model and
threshold choices before evaluating final negative sessions, and keep identity enrollment data
separate from identity evaluation data.

- Gesture reliability: command recall, confusion between custom movements, false commands per
  minute, and onset/release latency on speaking/rest/random-expression negatives.
- Transfer: new lighting, camera position, distance, pose and sessions for each person, including
  jaw sliding versus lip pursing.
- Identity routing: unknown people, deliberate facial gestures, two people crossing, occlusion,
  disappearance/reentry, duplicate profile enrollment and controller-assignment errors.
- Performance: capture-to-controller latency distributions, processed frame rate, CPU/memory use,
  dropped observations and recording completeness with one and two players on the target laptop.

These are experiments rather than established improvements. Existing study results do not prove
reliability for face recognition or geometry features. Keep participant footage, identity templates
and study-specific models out of source control.
