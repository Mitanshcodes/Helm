# OWNER: P2
"""Load, save and validate calibrations and mappings (docs/SPEC.md 6.9, 7). Bootstrap stubs: defaults only."""
import json
from pathlib import Path

from helm import config
from helm.contracts import Calibration

_ROOT = Path(__file__).resolve().parent.parent / config.PROFILES_DIR


def load_calibration(player: str) -> Calibration | None:
    # TODO(P2): read profiles/<player>/calibration.json.
    return None


def save_calibration(c: Calibration) -> None:
    # TODO(P2): write profiles/<player>/calibration.json. Never called from the pipeline thread.
    pass


def load_mapping(player: str, game: str) -> dict:
    """Falls back to default_mapping(game)."""
    # TODO(P2): read profiles/<player>/<game>.json when it exists.
    return default_mapping(game)


def save_mapping(player: str, game: str, mapping: dict) -> None:
    # TODO(P2): write profiles/<player>/<game>.json.
    pass


def default_mapping(game: str) -> dict:
    path = _ROOT / "_defaults" / f"{game}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {
        "player": "_defaults",
        "game": game,
        "axes": [{"source": "yaw", "target": "lx", "deadzone": config.AXIS_DEADZONE, "curve": config.AXIS_GAMMA,
                  "invert": False}],
        "triggers": [],
        "gestures": {"eyes_closed": {"kind": "blendshape", "sources": ["eyeBlinkLeft", "eyeBlinkRight"],
                                     "combine": "min", "on": config.TRIGGER_ON, "off": config.TRIGGER_OFF}},
        "buttons": [],
        "auto": {},
        "pause": {"gesture": "eyes_closed", "hold_ms": config.PAUSE_HOLD_MS},
    }


def validate_mapping(mapping: dict, calib: Calibration | None = None,
                     learned: list[str] | None = None, has_breath: bool = False) -> list[str]:
    """Human-readable errors, empty when the mapping is valid. The coach uses this as its checker."""
    # TODO(P2): required keys, targets exist, no target driven twice, gestures defined, reliable
    # blendshapes only, learned gestures exist, breath only with a sensor, pause set, hold gestures
    # do not share a muscle group.
    return []


def gesture_model_path(player: str) -> str:
    return str(_ROOT / player / "gestures.npz")


def list_profiles() -> dict[str, list[str]]:
    """player -> games"""
    # TODO(P2): scan the profiles folder.
    return {}
