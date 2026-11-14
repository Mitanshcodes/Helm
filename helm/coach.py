# OWNER: P1
"""Coach agent: build a mapping, review a session (docs/SPEC.md 11). Bootstrap stub: offline path only."""
from helm import profiles
from helm.contracts import Calibration


def build_mapping(game: str, calib: Calibration, learned: list[str], has_breath: bool) -> dict:
    """Return {"mapping": <valid mapping dict>, "rationale": [str, ...]}."""
    # TODO(P1): deepagents loop with get_game_controls, get_player_report, check_mapping, submit_mapping.
    # Keep this offline path as the fallback, filtered to the player's reliable gestures.
    return {"mapping": profiles.default_mapping(game), "rationale": ["offline default"]}


def review_session(mapping: dict, stats: dict, calib: Calibration, learned: list[str], has_breath: bool) -> dict:
    """Return {"mapping": <valid mapping dict>, "changes": [str, ...]}."""
    # TODO(P1): propose the smallest set of changes for near-misses, false triggers and fatigue.
    return {"mapping": mapping, "changes": []}
