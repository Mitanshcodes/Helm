# Single-player profile face protection

This prototype keeps one selected profile and one controller. An explicitly enrolled personal
profile admits only a confirmed matching face. Other visible faces are considered for identity
selection but never receive controllers. MediaPipe's default offline `FaceTracker.process` remains
ungated for gesture studies; live protection is a separate asynchronous camera worker.

## In the app: Face ID during calibration

A named profile's full calibration (onboarding a New profile, or Recalibrate) now starts with a **Face ID**
step, so nobody has to stop Helm and run the command below:

- **What it does:** `main.FaceEnrollment` samples the camera on a worker thread every 0.25 s. It keeps one SFace
  reference per sample with exactly one face in view, stops at 16 samples (or after 12 s), and saves them with
  `save_template`.
- **What happens next:** the profile is then protected, and the rest of the calibration runs in the protected path,
  as recommended below.
- **When it fails:** with fewer than 8 clear samples (someone else in view, face too small) Face ID is skipped,
  says why, and calibration carries on unprotected.
- **When it doesn't run:** the shared Default/guest and judge profiles, mock/replay, and a laptop without the model.
  Run `python -m helm.identity download` once on the demo laptop.

The command-line enrollment below still works, for videos and experiments.

## Deliberate enrollment

Enrollment is an explicit offline setup step, not part of ordinary calibration or profile loading.
Use a named personal profile; shared Default/guest and judge profiles remain unprotected.

From the Helm project Python environment:

```sh
python -m helm.identity download
# Stop Helm first so it releases the camera. Keep exactly one person visible.
python -m helm.identity enroll --player sam --camera 0 --seconds 8
python -m helm --player sam
```

Alternatively enroll from a separate clear-face video:

```sh
python -m helm.identity enroll --player sam --video /path/to/enrollment.mp4 --seconds 8
```

For a prerecorded sideways clip, `--rotation 90` applies a deliberate clockwise correction. An
explicit `--crop X0 Y0 X1 Y1` isolates one known enrollment subject after rotation; it is never
automatically chosen by recognition scores. Record crop/orientation provenance and exclude those
frames from evaluation. The offline evaluator supports the same rotation and `--start-seconds`
to begin a fresh admission gate after an enrollment interval.

Keep the face clear and well lit, with comfortable small turns and normal expressions. At least
eight valid samples are required; ambiguous multi-person enrollment is refused. This consistency
check does not establish that the operator selected the correct profile/person. Re-enrollment is
a deliberate replacement, so verify the selected profile and record the person alone.

Face references are saved atomically to `profiles/sam/identity.json`. A separate
`identity_required.json` marker preserves the protection requirement if references are later lost
or damaged. Keep both files private; both are Git-ignored. Loading a profile never collects or
updates biometric references. Use **Anchor → Profile → Reload face enrollment** after an explicit
offline update, or restart Helm. Calibrations and learned gesture files are not changed by face
enrollment.

Enroll identity **before** performing protected calibration and gesture enrollment. The protected
worker uses `num_faces=4`; the default offline/unprotected tracker uses `num_faces=1`. MediaPipe's
built-in landmark smoothing differs between these modes. Protecting an existing trained profile
therefore requires revalidation and usually a fresh calibration/enrollment in the protected path;
the software preserves its old calibration/model files rather than deleting them silently.
Per-frame dev identity status records `face_landmarker_num_faces` for this provenance check.

The Profile panel displays **unprotected** if a legacy personal profile has no enrollment, and
Default/guest and judge remain explicitly unprotected. Enrolled profiles are locked while loading,
on recognition failure, stale results, missing/damaged references or missing model weights.
Feature-only mock/replay has no identity pixels and cannot unlock an enrolled profile.

## Model and admission policy

The model is OpenCV Zoo's SFace MobileFaceNet ONNX model:

- [Official model directory](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)
- [Official LFS pointer and SHA-256](https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx)
- Model SHA-256: `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`
- [OpenCV alignment/feature implementation](https://github.com/opencv/opencv/blob/4.x/modules/objdetect/src/face_recognize.cpp)

Weights are downloaded only by the explicit `download` command and hash-verified before loading.
They are cached under ignored `artifacts/identity-models/`. OpenCV Zoo lists the model directory as
Apache-2.0. Camera frames and identity templates are not sent to an external service.

MediaPipe eye centers, nose landmark 1 and mouth corners 61/291 provide five-point alignment for
OpenCV's 112×112 SFace crop. OpenCV handles its expected channel preprocessing. The result is a
unit-normalized 128-value identity vector, separate from expression/gesture vectors. The stored
preprocessing identifier is versioned: changing the alignment or encoder requires re-enrollment.
This MediaPipe alignment adapter requires its own validation; model benchmark numbers obtained
with a different detector/alignment do not establish application accuracy.

Up to four visible faces are evaluated together. Each observation is compared with the selected
profile and other enrolled profiles. Admission requires cosine similarity at least 0.55, a 0.08
margin over both other visible faces and competing profiles, and at least three observations over
200 ms. These are conservative starting settings, not calibrated probabilities or guarantees.
Unknown, small, badly aligned and ambiguous faces are rejected. Detection order is never treated
as identity. Multiple faces matching the same person (including a duplicate image) cause rejection.

The worker processes the camera's latest frame and does not enqueue an unbounded backlog.
The identity result and selected MediaPipe features always come from the same captured frame.
A result older than 250 ms from capture cannot control the pad. A short interval with no newer
result may hold the last admitted control state only within that deadline. Fresh rejection
neutralizes all controls immediately, without the ordinary face-loss grace period, including
automatic throttle and breath. Loss/reacquisition clears gesture and mapper transient state,
filters and queued breath events. Calibration and gesture enrollment accept only verified
observations and use a clock that pauses during rejection.

This is convenience control isolation, not security-grade authentication: it has no liveness or
presentation-attack detection, and cannot guarantee rejection of look-alikes, photos or displays.
No background-interference reliability claim is established without labeled independent footage.

## Offline evaluation of new recordings

Enroll only from separate enrollment footage. For isolated experiments, avoid production profiles:

```sh
python -m helm.identity enroll --player subject_b --video enrollment-B.mp4 \
  --output-root artifacts/identity-validation/profiles
python eval/identity_replay.py --player subject_b \
  --profile-root artifacts/identity-validation/profiles \
  --video interference.mp4 --labels interference-labels.json \
  --output artifacts/identity-validation/interference-B
```

For a dev dataset's `video.avi`, pass its paired `--signals /path/to/signals.jsonl`. Capture
timestamps then override nominal AVI frame timing. Never use spoken instructions as the only
labels: dev recordings have no audio. Use a visual cue and/or a timestamped annotation log.

Minimal ground truth:

```json
{
  "intervals": [
    {"start_s": 0, "end_s": 10, "target_present": true},
    {"start_s": 10, "end_s": 20, "target_present": false}
  ],
  "frames": [
    {"frame_index": 0, "target_box": [0.1, 0.1, 0.5, 0.8]}
  ]
}
```

Intervals are half-open. Boxes are independently labeled normalized `[x0,y0,x1,y1]` coordinates
in the unmirrored frame; provide them for every frame on which ownership should be scored.
Presence labels can reveal admission while the owner is absent, but cannot establish which face
was selected when two people are visible. Per-frame target boxes permit that additional check.
Unlabeled intervals remain unscored, and no identity labels are inferred from recognition scores.

The evaluator writes `identity.jsonl` with selection, scores, rejection reasons, normalized boxes,
alignment errors and inference times, plus `summary.json` with labeled counts and timing. It never
creates a gamepad, learns from test footage, or alters saved enrollment. Offline wall time is not
physical camera-to-game latency; benchmark live capture separately on the target laptop.

## Recordings still needed

For each owner A and B, collect a separate 8–10 s single-person enrollment clip and two independent
60–90 s interference clips, with roles reversed between owners. Mark the intended profile visibly
or in a sidecar log. Include:

1. Owner alone making normal gestures and comfortable turns.
2. Another person entering/leaving and making exaggerated gestures behind the owner.
3. Both crossing or changing seats; the owner's brief occlusion and reappearance.
4. Owner leaving entirely while the other person deliberately attempts the owner's controls.
5. A separate session with changed lighting, distance and camera position.

Keep at least one fresh recording per owner entirely out of template collection and threshold
selection. Record the active profile, who is visible, and exact presence/occlusion intervals;
annotate target boxes for ownership checks when both are visible. A missing face, rejected owner
and wrong person admitted are different outcomes. Report them separately.
