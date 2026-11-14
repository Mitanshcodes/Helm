# OWNER: shared (FROZEN after bootstrap; changes only when the captain agrees)
"""Dataclasses and constants that cross module boundaries. Copied from docs/SPEC.md section 5."""
from dataclasses import dataclass, field
import numpy as np

AXES = ("yaw", "pitch", "roll")
PAD_AXES = ("lx", "ly", "rx", "ry")                 # each in [-1, 1]; ly/ry positive = up
PAD_TRIGGERS = ("lt", "rt")                         # each in [0, 1]
PAD_BUTTONS = ("A", "B", "X", "Y", "LB", "RB", "START", "BACK",
               "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT", "LS", "RS")
BREATH_EVENTS = ("soft_sip", "hard_sip", "soft_puff", "hard_puff")
BLENDSHAPE_NAMES: tuple[str, ...] = (               # expected MediaPipe output order. On the first real
    "_neutral", "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight",
    "cheekPuff", "cheekSquintLeft", "cheekSquintRight", "eyeBlinkLeft", "eyeBlinkRight",
    "eyeLookDownLeft", "eyeLookDownRight", "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft",
    "eyeLookOutRight", "eyeLookUpLeft", "eyeLookUpRight", "eyeSquintLeft", "eyeSquintRight",
    "eyeWideLeft", "eyeWideRight", "jawForward", "jawLeft", "jawOpen", "jawRight", "mouthClose",
    "mouthDimpleLeft", "mouthDimpleRight", "mouthFrownLeft", "mouthFrownRight", "mouthFunnel",
    "mouthLeft", "mouthLowerDownLeft", "mouthLowerDownRight", "mouthPressLeft", "mouthPressRight",
    "mouthPucker", "mouthRight", "mouthRollLower", "mouthRollUpper", "mouthShrugLower",
    "mouthShrugUpper", "mouthSmileLeft", "mouthSmileRight", "mouthStretchLeft", "mouthStretchRight",
    "mouthUpperUpLeft", "mouthUpperUpRight", "noseSneerLeft", "noseSneerRight",
)                                                   # inference, P1 compares this with the model's own
                                                    # category names and corrects it before anyone relies on it
N_BLEND = 52
FEATURE_DIM = 56                                    # 52 blend deltas + yaw, pitch, roll + breath

@dataclass(slots=True)
class FrameFeatures:                                # P1 vision -> everyone
    seq: int
    t_capture_ns: int
    t_infer_ns: int
    face: bool
    yaw: float = 0.0                                # degrees, raw; + = player turns to their own right
    pitch: float = 0.0                              # + = chin up
    roll: float = 0.0                               # + = tilt toward their own right shoulder
    blend: np.ndarray = field(default_factory=lambda: np.zeros(N_BLEND, np.float32))
    landmarks: np.ndarray | None = None             # (478, 2) float32 in [0, 1], for the preview only

@dataclass(slots=True)
class Calibration:                                  # P1 calibration -> P2 profiles, P3 gestures
    player: str
    mode: str                                       # "full" | "quick" | "default"
    neutral: dict[str, float]                       # per axis, degrees
    range: dict[str, tuple[float, float]]           # per axis: (negative limit, positive limit), degrees, both > 0
    blend_neutral: list[float]                      # 52 resting scores
    blend_peak: dict[str, float]                    # blendshape name -> player's median peak (raw score)
    reliable: list[str]                             # blendshape names that passed the expression check

@dataclass(slots=True)
class Signals:                                      # P1 Normalizer -> P3, P2
    seq: int
    t_capture_ns: int
    t_infer_ns: int
    face: bool
    axes: dict[str, float]                          # yaw/pitch/roll in [-1, 1]: neutral removed, scaled to the
                                                    # player's range, One Euro filtered. No dead zone or curve.
    expr: np.ndarray                                # (52,) in [0, 1]: (blend - neutral) / (peak - neutral)
    delta: np.ndarray                               # (56,) classifier features: blend - neutral, axes, breath
    breath: float                                   # [-1, 1]; + puff, - sip; 0.0 with no device

@dataclass(slots=True)
class SipPuffEvent:                                 # P2 sipnpuff -> P2 mapping
    t_ns: int
    kind: str                                       # one of BREATH_EVENTS

@dataclass(slots=True)
class ControlState:                                 # P2 mapping -> P2 output, P4 server
    t_output_ns: int = 0
    lx: float = 0.0
    ly: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    lt: float = 0.0
    rt: float = 0.0
    buttons: frozenset[str] = frozenset()
    paused: bool = False
    fired: tuple[str, ...] = ()                     # gesture names that fired on this tick

@dataclass(slots=True)
class Progress:                                     # wizard and recorder -> server -> dashboard
    active: bool
    step: str                                       # machine name, e.g. "neutral", "yaw_left", "take_3", "negatives"
    prompt: str                                     # sentence shown large to the player
    progress: float                                 # 0..1 within the step
    overall: float                                  # 0..1 across the whole flow
    done: bool = False
