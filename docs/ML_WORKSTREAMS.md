# Parallel ML workstreams

Both workstreams target `experimental/identity-and-geometry` in the original Mitanshcodes/Helm
repository. There is no separate fork. The parent agent coordinates shared interfaces and Git.

## Ownership

| Workstream | Writable scope | Read-only dependencies |
|---|---|---|
| Gesture studies | Sibling `helm-studies` project: experiments, extracted data, reports and data-collection requests | Helm pipeline and its public extraction contracts |
| Profile identity | Helm identity modules, runtime/vision/profile/server integration, minimal existing-layout UI controls, identity tests and identity documentation | Gesture classifier, filters, mapper, calibration and study datasets |
| Parent integration | Shared contracts, this agreement, shared test/build validation and Git operations | Both workstreams' results |

The studies agent must not modify Helm files, run Git operations there, or change the identity
agent's data. It may implement feature preprocessing and candidate models inside `helm-studies`.
The identity agent must not modify `helm-studies`, `helm/gestures.py`, `helm/filters.py`,
`helm/mapping.py`, or `helm/calibration.py`. Request shared contract changes from the parent.
Neither agent switches branches, stashes, stages, commits, merges or pushes in the shared Helm
checkout. Existing participant recordings and labels are preserved; newly generated private
datasets, identity templates and model weights remain outside Git.

## Shared extraction contract

- `FaceTracker(model_path=...).process(bgr, t_capture_ns, seq)` remains callable without identity
  enrollment. Its default is ungated offline feature extraction; live identity enforcement is an
  explicit runtime integration. Keep `pose_from_matrix` and `blend_from_categories` compatible.
- `FrameFeatures.blend` remains `(52,)`; yaw/pitch/roll retain their existing conventions.
- `FrameFeatures.landmarks` remains `(478,2)` for preview compatibility.
- New optional `FrameFeatures.landmarks3d` contains raw MediaPipe `(478,3)` float32 `x,y,z`
  coordinates, or `None` when no face is available. These are normalized model coordinates, not
  metric depth. Studies must define and validate their own geometric normalization.
- `FEATURE_DIM` and the existing normalized gesture delta remain 56. Geometry is a separate
  experimental feature family, never an implicit reinterpretation of legacy enrollment arrays.
- Dev recording JSON rows serialize `frame.landmarks3d`; metadata identifies it with
  `geometry_schema: mediapipe_normalized_xyz_v1`. Mock and old replay inputs can have no geometry.
- `DevRecording.submit(..., identity=None)` optionally captures the frame's identity decision in
  a top-level `identity` field in `signals.jsonl`, copied at submission. Existing callers can omit it.
  Recording metadata lists observed `processing_modes` (identity protection and MediaPipe face
  count). Per-frame identity status records `face_landmarker_num_faces`; do not silently mix
  single-face and multi-face feature caches because their smoothing differs.
- Studies record the Helm revision, extraction source hashes, model asset hash, dataset manifest,
  preprocessing and split policy. Shared source can change during identity work, so each study
  run must detect source drift and must not silently combine incompatible feature caches.

## Gesture studies acceptance

Compare the integrated blendshape baseline with normalized 3D geometry and combined features,
trying regularized classifiers and enrollment-only feature reduction. Use actual command events
and rejection, not just frame accuracy. Include jaw-slide/pucker confusion, speaking/rest,
`random.mov`, position/lighting transfer and small enrollment sets. Existing negatives used for
model selection are validation, not an untouched final test. Limit fitting to at most one second
per long negative recording, preserving the rest for evaluation. Report uncertainty, latency,
failure cases and concrete dev-recording requests when fresh data is needed.

## Identity acceptance

Preserve the current one-player layout and one controller. Enroll a face under a chosen profile,
then admit only that profile's confirmed face to calibration, gesture enrollment and live control.
Consider multiple visible faces so a background person cannot replace or drive the active player.
Unknown, ambiguous, missing or stale identity yields neutral output; reacquisition must not fire
stale gestures. Do not silently enroll somebody while merely loading a profile. Add a usable
explicit enrollment path and clear status without redesigning the dashboard.

Use current footage for implementation checks where appropriate, but do not claim background
interference reliability until the user's forthcoming labeled recordings are evaluated. Missing
Drive uploads must not block implementation. Provide an offline validation adapter and exact
recording requirements so those clips can be tested later.
