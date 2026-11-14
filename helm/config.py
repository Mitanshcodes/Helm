# OWNER: shared (edit only your own lane's section)
"""Tunable numbers, one section per lane. Start values come from docs/SPEC.md; tune them on the demo laptop."""

# ------------------------------------------------------------------ P1: perception and runtime
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 60
MODEL_PATH = "models/face_landmarker.task"
MOCK_HZ = 30.0

ONE_EURO_MIN_CUTOFF = 1.0          # lower if steering jitters
ONE_EURO_BETA = 0.01               # raise if steering feels laggy
ONE_EURO_D_CUTOFF = 1.0
AXIS_DEADZONE = 0.08
AXIS_GAMMA = 1.5
DEFAULT_RANGE_DEG = 15.0           # per direction, when there is no calibration
MIN_RANGE_DEG = 4.0
DEFAULT_PEAK_ABOVE_NEUTRAL = 0.5   # expression peak when none was measured
DRIFT_TIME_CONSTANT_S = 30.0

CALIB_NEUTRAL_S = 3.0
CALIB_NEUTRAL_QUICK_S = 2.0
CALIB_RANGE_S = 2.5
CALIB_EXPRESSION_S = 4.0
RELIABLE_MIN_PEAK_RATIO = 0.7      # weakest peak / median peak
RELIABLE_MIN_PEAK_ABOVE_NEUTRAL = 0.15

FACE_LOST_MS = 200                 # pad goes neutral after this long without a face
STATS_WINDOW = 60                  # frames in the rolling fps and latency medians
COACH_TIMEOUT_S = 60

# ------------------------------------------------------------------ P2: control and hardware
TRIGGER_ON = 0.6
TRIGGER_OFF = 0.4
TRIGGER_MIN_HOLD_MS = 60
TRIGGER_REFRACTORY_MS = 200
TAP_MS = 120
PAUSE_HOLD_MS = 1000

KEYBOARD_AXIS_THRESHOLD = 0.3
KEYBOARD_TRIGGER_THRESHOLD = 0.3
KEYBOARD_KEYS = {"A": "space", "B": "n", "X": "backspace"}   # placeholder: check against the game's key settings

PROFILES_DIR = "profiles"          # relative to the repo root

SERIAL_BAUD = 115200
BREATH_SOFT = 0.25
BREATH_HARD = 0.65
BREATH_MIN_PRESS_MS = 80
BREATH_BASELINE_S = 2.0

# ------------------------------------------------------------------ P3: learning and evaluation
KNN_NEIGHBORS = 7
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

# ------------------------------------------------------------------ P4: product and story
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
STATE_HZ = 30
PREVIEW_FPS = 15
PREVIEW_SIZE = (320, 240)
PREVIEW_JPEG_QUALITY = 60
