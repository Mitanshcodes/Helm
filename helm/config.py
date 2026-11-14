# OWNER: shared (edit only your own lane's section)
"""Tunable numbers, one section per lane. Start values come from docs/SPEC.md; tune them on the demo laptop."""

# ------------------------------------------------------------------ P1: perception and runtime
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 60
MODEL_PATH = "models/face_landmarker.task"
MOCK_HZ = 30.0
YAW_SIGN = -1.0                    # head-pose signs; check with `python -m helm.vision` and flip here if wrong
PITCH_SIGN = -1.0
ROLL_SIGN = 1.0

ONE_EURO_MIN_CUTOFF = 1.0          # lower if steering jitters
ONE_EURO_BETA = 1.0                # raise if steering feels laggy. Spec's 0.01 is for pixel units; on our
                                   # normalized axes it lagged a head turn ~270 ms in simulation, 1.0 lags ~1 frame
ONE_EURO_D_CUTOFF = 1.0
AXIS_DEADZONE = 0.08
AXIS_GAMMA = 2.0                   # >1 = gentle near center, full lock still at the calibrated range
DEFAULT_RANGE_DEG = 20.0           # per direction, when there is no calibration (and quick mode's start)
MIN_RANGE_DEG = 8.0                # floor on a measured range: below this, tracking jitter alone moves the stick
DEFAULT_PEAK_ABOVE_NEUTRAL = 0.5   # expression peak when none was measured
MIN_EXPRESSION_SPAN = 0.05         # floor on (peak - neutral) so expr never divides by ~0
AUTO_RANGE_SAMPLES = 1800          # quick mode: excursions kept per axis and direction (~60 s at 30 fps)
AUTO_RANGE_MIN_SAMPLES = 10        # quick mode: excursions needed before a limit widens
DRIFT_TIME_CONSTANT_S = 30.0
DRIFT_MAX_FRACTION = 0.5           # drift never moves neutral more than this share of the range

CALIB_NEUTRAL_S = 3.0
CALIB_NEUTRAL_QUICK_S = 2.0
CALIB_RANGE_S = 3.0                # shortest a head-range step can be
CALIB_RANGE_MOVED_DEG = 6.0        # a range step waits until the head is at least this far from neutral...
CALIB_RANGE_HOLD_S = 1.5           # ...for this long (the spoken prompt alone takes ~3 s)
CALIB_RANGE_TIMEOUT_S = 8.0        # then moves on anyway, using what it measured
CALIB_EXPRESSION_S = 4.0
CALIB_MAX_DT_S = 0.1               # longest frame gap that counts toward a step's timer
CALIB_PEAK_SEPARATION_S = 0.4      # expression peaks closer than this count as one repetition
RELIABLE_MIN_PEAK_RATIO = 0.7      # weakest peak / median peak
RELIABLE_MIN_PEAK_ABOVE_NEUTRAL = 0.15
# Calibration never prompts for these, so they are trusted without a check: blinks drive the pause
# gesture in every mapping, and quick mode also trusts the two expressions the judge profile uses.
ASSUMED_RELIABLE = ("eyeBlinkLeft", "eyeBlinkRight")
QUICK_ASSUMED_RELIABLE = ("browInnerUp", "jawOpen", "mouthSmileLeft", "mouthSmileRight", "mouthPucker")

FACE_LOST_MS = 200                 # pad goes neutral after this long without a face
STATS_WINDOW = 60                  # frames in the rolling fps and latency medians
NEAR_MISS_RATIO = 0.8              # an attempt that reaches this share of `on` without firing is a near-miss
WATCH_EXPRESSIONS = ("browInnerUp", "jawOpen", "mouthSmileLeft", "mouthSmileRight", "mouthPucker", "cheekPuff")
                                   # raw scores in the state message, so the dashboard can show unmapped ones
FIRED_HOLD_MS = 150                # a fire stays in the state message this long, so 30 Hz states never miss it
COACH_TIMEOUT_S = 60
COACH_DEFAULT_MODEL = "anthropic:claude-opus-5-5"   # overridden by the HELM_COACH_MODEL environment variable
COACH_OPENAI_MODEL = "openai:gpt-5.5"              # used instead when only OPENAI_API_KEY is set (e.g. in .env)
COACH_RECURSION_LIMIT = 60         # agent graph steps before it gives up
COACH_THRESHOLD_STEP = 0.05        # offline review: how far one change moves on/off
COACH_MIN_NEAR_MISSES = 3          # offline review: near-misses before a threshold is lowered
COACH_FALSE_TRIGGER_PER_MIN = 6.0  # offline review: fires per minute treated as accidental

# ------------------------------------------------------------------ P2: control and hardware
TRIGGER_ON = 0.6
TRIGGER_OFF = 0.4
TRIGGER_MIN_HOLD_MS = 60
TRIGGER_REFRACTORY_MS = 200
TAP_MS = 120
PAUSE_HOLD_MS = 2000               # eyes held shut this long toggles pause (and resume)
PAUSE_ON = 0.85                    # eyes_closed level that counts as shut: squinting or glancing down stays below
PAUSE_OFF = 0.6

KEYBOARD_AXIS_THRESHOLD = 0.3
KEYBOARD_TRIGGER_THRESHOLD = 0.3
KEYBOARD_KEYS = {"A": "space", "B": "n", "X": "backspace"}   # placeholder: check against the game's key settings

PROFILES_DIR = "profiles"          # relative to the repo root

SERIAL_BAUD = 115200
BREATH_SOFT = 0.25
BREATH_HARD = 0.65
BREATH_MIN_PRESS_MS = 80
BREATH_BASELINE_S = 2.0
BREATH_BASELINE_WINDOW_S = 5.0     # rolling median window, only while no press is active
BREATH_MAX_PUFF_MV = 400.0         # displacement from baseline at full level; calibrate() overrides
BREATH_MAX_SIP_MV = 400.0
SERIAL_PROBE_S = 3.0               # a classic Uno resets when the port opens: ~1.5 s of silence first
SERIAL_READ_TIMEOUT_S = 0.2
SERIAL_RECONNECT_S = 1.0           # wait before retrying after an unplugged cable
SERIAL_STALE_S = 1.0               # no valid line for this long -> report not connected
SERIAL_LOST_S = 3.0                # no valid line for this long -> close the port and reconnect
SERIAL_DRAIN_MAX_S = 15.0          # give up draining a UNO Q backlog after this long
SERIAL_LIVE_GAP_MS = 3.0           # a readline that waited this long means the line was live
SERIAL_LIVE_STREAK = 5             # this many live reads in a row ends the drain

# ------------------------------------------------------------------ P3: learning and evaluation
KNN_NEIGHBORS = 7
KNN_POSE_WEIGHT = 0.3              # head pose counts less than the face, so a gesture made while steering still counts
NEGATIVE_CHUNKS = 5                # negatives are split this many ways for leave-one-out accuracy
TAKES = 5
TAKE_READY_S = 1.0
TAKE_HOLD_S = 1.0
TAKE_RELAX_S = 1.0
TAKE_TOP_FRACTION = 0.6            # share of hold-window frames kept as positives
NEGATIVE_S = 15.0
MIN_TAKE_OUT_ACCURACY = 0.85
LEARNED_SMOOTH_FRAMES = 4
NONE_SUPPRESS = 0.3                # learned activation is 0 when P("none") reaches this

FATIGUE_WINDOW_S = 120.0
FATIGUE_BASELINE_S = 60.0
FATIGUE_DROP_RATIO = 0.75
FATIGUE_MIN_SCALE = 0.5
FATIGUE_ATTEMPT_LEVEL = 0.3        # an activation counts as an attempt once it rises past this; its peak is kept
FATIGUE_MIN_PEAKS = 3              # peaks needed in both the baseline and the recent window before scaling

# ------------------------------------------------------------------ P4: product and story
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
STATE_HZ = 30
PREVIEW_FPS = 15
PREVIEW_SIZE = (320, 240)
PREVIEW_JPEG_QUALITY = 60
