# Local dev recordings

Enable **Dev mode** on the main dashboard or run `python -m helm --dev`. Enable it before starting
calibration or enrollment to capture the complete flow. Enabling it during calibration restarts
that calibration so the recording includes the beginning; enabling it during enrollment captures
only the remaining enrollment. Dev mode starts disabled unless `--dev` is passed.

While enabled, calibration, gesture enrollment and negative enrollment each create a dataset
automatically. **Record debug dataset** starts a manual dataset; **Stop recording** ends it.
Calibration or enrollment started during a manual recording stays in that same recording.
Switching profiles, disabling dev mode or shutting down closes the active recording. Normal
profile calibration and model saving continue to work as before.

Each recording creates a unique timestamped directory under `artifacts/dev-datasets/`, ignored by
Git. Change the root with `--dev-dir /path/to/datasets`. A dataset contains:

| File | Contents |
|---|---|
| `video.avi` | Original unmirrored camera frames processed by the pipeline, encoded as MJPEG; no audio. |
| `signals.jsonl` | One JSON object per video frame: raw blendshapes and pose, available preview landmarks, normalized features, class scores, gesture activations, controller output and enrollment/calibration progress. |
| `calibration.json` | Calibration at the start, replaced with the completed calibration if one is recorded. |
| `calibration_before.json` | Calibration at the start, retained when a new calibration completes. |
| `gestures.npz` | Gesture model at the start, updated after enrollment/model fitting finishes. |
| `gestures_before.npz` | Gesture model at the start, retained for comparisons. |
| `mapping.json` | Controller mapping at the start. |
| `metadata.json` | Schema version, player/game, recording kind, enrollment label, camera/mock/replay source, frame count, completion and errors. |

An uncalibrated profile saves an explicitly marked `mode: "default"` calibration, and a profile
without learned gestures saves an empty model. Guest enrollments are saved to the dataset too.
Calibration data is the neutral/range reference; the NPZ contains gesture enrollment examples
and classifier settings. Keep them together when comparing recognition across environments.

`signals.jsonl` uses zero-based `frame_index` to match video frames. `time_s` is elapsed capture
time from the first frame; raw capture and inference timestamps are monotonic nanoseconds. Video
is tagged at a nominal 30 fps, so use these signal timestamps for timing studies when capture
rate varies. The recording covers the frames consumed by Helm; the camera's latest-frame capture
can discard intervening frames. Mock/replay sources produce a synthetic preview video rather
than recovering original camera pixels. Landmark values are the existing 2D preview coordinates,
not a new 3D geometry feature vector.

Wait for **Dataset saved** before using the files. On shutdown Helm waits for pending video and
model saves. A bounded background writer performs encoding and disk I/O; if it cannot keep up,
or encoding/fitting fails, the dataset is marked incomplete and the UI reports the error. Check
`metadata.json` for `complete: true` and `model_updates_pending: 0`. Empty recordings and abruptly
killed processes are not complete datasets.

Recordings remain local until you move or delete them. The JSON signals include the model scores
and the actual controller state, so false detections can be inspected alongside the source video.
