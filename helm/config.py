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
STEER_GAIN_MIN = 0.5               # steering sensitivity (mapping axis "gain"): 2 = full lock at half the
STEER_GAIN_MAX = 3.0               # calibrated head turn, 0.5 = it takes twice the turn
AXIS_GAMMA = 2.0                   # >1 = gentle near center, full lock still at the calibrated range
DEFAULT_RANGE_DEG = 20.0           # per direction, when there is no calibration (and quick mode's start)
MIN_RANGE_DEG = 8.0                # floor on a measured range: below this, tracking jitter alone moves the stick
DEFAULT_PEAK_ABOVE_NEUTRAL = 0.5   # expression peak when none was measured
MIN_EXPRESSION_SPAN = 0.15         # floor on (peak - neutral): no calibration, old or odd, makes an expression
                                   # hair-trigger (0.05 let tracking jitter alone reach `on`)
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
CALIB_EXPRESSION_S = 4.0           # typical length of an expression step (for the overall progress bar)
CALIB_EXPRESSION_MAX_S = 10.0      # an expression step ends after 3 repetitions, or at this time
CALIB_REP_LEVEL = 0.12             # above neutral: a repetition starts; it ends below half of this
CALIB_MAX_DT_S = 0.1               # longest frame gap that counts toward a step's timer
CALIB_PEAK_SEPARATION_S = 0.4      # expression peaks closer than this count as one repetition
RELIABLE_MIN_REPS = 2              # repetitions an expression needs to count as reliable
RELIABLE_MIN_PEAK_RATIO = 0.5      # weakest counted repetition / median repetition
RELIABLE_MIN_PEAK_ABOVE_NEUTRAL = 0.12
CALIB_MIN_SPAN = 0.2               # a measured expression's scale (peak - neutral) is at least this
REST_PERCENTILE = 98               # "how much the relaxed face moves": this percentile over the neutral and turn steps
REST_SPAN_FACTOR = 2.5             # scale >= this x that, so steering with a relaxed face stays below 1/2.5 = 0.4
RELIABLE_MIN_REACH = 0.8           # reliable only if the real move reaches this share of a scale raised that way
# Calibration never prompts for these, so they are trusted without a check: blinks drive the pause
# gesture in every mapping, and quick mode also trusts the two expressions the judge profile uses.
ASSUMED_RELIABLE = ("eyeBlinkLeft", "eyeBlinkRight")
QUICK_ASSUMED_RELIABLE = ("browInnerUp", "jawOpen", "mouthSmileLeft", "mouthSmileRight", "cheekPuff")

FACE_LOST_MS = 200                 # pad goes neutral after this long without a face
STATS_WINDOW = 60                  # frames in the rolling fps and latency medians
NEAR_MISS_RATIO = 0.8              # an attempt that reaches this share of `on` without firing is a near-miss
WATCH_EXPRESSIONS = ("browInnerUp", "jawOpen", "mouthSmileLeft", "mouthSmileRight", "mouthPucker", "cheekPuff")
                                   # raw scores in the state message, so the dashboard can show unmapped ones
CROSSTALK_RATIO = 0.8              # a mapped gesture is held back while another one (no shared blendshape) is stronger
                                   # than it by this factor, measured as level / on: smiling also lifts jawOpen a bit
EXPRESSION_MIN_HOLD_MS = 100       # face expressions the coach maps must stay past `on` this long (talking twitches)
BREATH_LEVEL_ON = 0.3              # live breath gestures (breath_puff, breath_sip): press past this share of the
BREATH_LEVEL_OFF = 0.15            # player's breath range, release below this (rest noise is ~0.04)
PROFILE_WATCH_S = 1.0              # how often hand edits to profiles/<player>/*.json are picked up
FIRED_HOLD_MS = 150                # a fire stays in the state message this long, so 30 Hz states never miss it
COACH_TIMEOUT_S = 60
COACH_DEFAULT_MODEL = "anthropic:claude-opus-5-5"   # overridden by the HELM_COACH_MODEL environment variable
COACH_OPENAI_MODEL = "openai:gpt-5.5"              # used instead when only OPENAI_API_KEY is set (e.g. in .env)
COACH_BACKEND = "auto"             # "claude" (Claude Code CLI on the user's subscription), "api", "offline", or "auto":
                                   # Claude Code when installed, else an API key. HELM_COACH_BACKEND overrides it.
COACH_CLAUDE_MODEL = "sonnet"      # Claude Code model alias ("sonnet", "opus"); HELM_COACH_CLAUDE_MODEL overrides it
COACH_CLAUDE_TIMEOUT_S = 180       # whole Claude Code run, web lookups and fix-up rounds included
COACH_CLAUDE_ATTEMPTS = 3          # rounds of "here are the check errors, fix them" before the offline coach
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
# Displacement from baseline at full level; calibrate() overrides per player. Measured on the real
# UNO Q rig: rest sits mid-rail at ~2390 mV and a committed breath swings the sensor most of the way
# to a rail -- a hard sip reached 22 mV (displacement 2360) and a hard puff 4792 mV (2410). Sip is
# the stronger and far more repeatable direction; puff measured 1024, 1078 and 2410 mV across three
# tries, so its scale is set near the low end of that spread or an ordinary puff never clears
# BREATH_HARD and the latched throttle would not fire. The earlier 400.0 placeholders were ~6x too
# small, which saturated level on a light breath and left the analog brake with no usable travel.
BREATH_MAX_PUFF_MV = 1000.0
BREATH_MAX_SIP_MV = 1800.0
# Per-player breath calibration (BreathCalibrator). One prompted sip and one prompted puff.
CALIB_BREATH_REST_S = 1.5          # settle, so the rolling baseline is clean before the first peak
# Per direction. 4.0 was too short in practice: a spoken prompt takes about 3 s to read out, so
# the player heard the instruction with a second left and their breath landed in the NEXT step's
# window -- a bench run recorded a sip during the puff step for exactly this reason. The window has
# to outlast the prompt, however the prompt is delivered.
CALIB_BREATH_STEP_S = 6.0
# Full scale is this fraction of the single measured peak, NOT the peak itself. A player's best
# effort is not their typical effort: the bench rig measured one person's puff at 2410, 1024 and
# 1078 mV across three tries. Scaling to the peak would leave an ordinary puff below BREATH_HARD
# (0.65) and the latched throttle would silently fail. Half the peak means a typical breath reads
# as full effort and a maximal one simply clamps at 1.0, which costs nothing.
CALIB_BREATH_FRACTION = 0.5
# Refuse a measurement below this and keep the previous scale. A player who does not breathe during
# the step would otherwise set full scale to a few millivolts of noise, after which resting noise
# reads as a hard puff and latches the throttle by itself. Rest noise measured 12-40 mV p-p.
CALIB_BREATH_MIN_MV = 200.0
CALIB_BREATH_MAX_MV = 3000.0       # a 5 V sensor on a 10k/10k divider cannot exceed its rail
SERIAL_PROBE_S = 3.0               # a classic Uno resets when the port opens: ~1.5 s of silence first
SERIAL_READ_TIMEOUT_S = 0.2
SERIAL_RECONNECT_S = 1.0           # wait before retrying after an unplugged cable
SERIAL_STALE_S = 1.0               # no valid line for this long -> report not connected
SERIAL_LOST_S = 3.0                # no valid line for this long -> close the port and reconnect
SERIAL_DRAIN_MAX_S = 15.0          # give up draining a UNO Q backlog after this long
SERIAL_LIVE_GAP_MS = 3.0           # a readline that waited this long means the line was live
SERIAL_LIVE_STREAK = 5             # this many live reads in a row ends the drain

# ------------------------------------------------------------------ P3: learning and evaluation
LEARNED_C = 0.1
LEARNED_FEATURES_PER_CLASS = 4
LEARNED_SCALE_FLOOR = 0.05
LEARNED_NOISE_FLOOR = 0.03
LEARNED_FRAMES_PER_TAKE = 7
LEARNED_NEGATIVE_RATIO = 3
LEARNED_RADIUS_PERCENTILE = 95
LEARNED_RADIUS_EXPANSION = 1.5
LEARNED_RADIUS_MIN = 0.5
LEARNED_RADIUS_SEPARATION = 0.35
LEARNED_REJECT_FACTOR = 1.5
LEARNED_MAX_ITER = 2000
LEARNED_ON = 0.65
LEARNED_OFF = 0.45
LEARNED_CONFIRM_S = 2.0 / 30.0
LEARNED_RELEASE_S = 2.0 / 30.0
LEARNED_MAX_GAP_S = 0.2
TAKES = 5
TAKE_READY_S = 3.0                 # "get ready": long enough to hear the spoken prompt; also the face baseline
TAKE_HOLD_S = 1.5                  # seconds of the move actually held that a take records
TAKE_MOVED = 0.25                  # distance from the ready face (blinks ignored) that counts as doing the move
TAKE_NUDGE_S = 3.0                 # no move by then: the prompt asks for a bigger one
TAKE_GO_TIMEOUT_S = 8.0            # then the take ends anyway and keeps the frames furthest from the ready face
TAKE_RELAX_S = 2.5
TAKE_TOP_FRACTION = 0.6            # share of frames kept as positives when a take timed out
NEGATIVE_S = 15.0
MIN_TAKE_OUT_ACCURACY = 0.85

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
