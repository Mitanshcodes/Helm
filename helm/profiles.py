# OWNER: P2
"""Load, save and validate calibrations and mappings (docs/SPEC.md 6.9, 7). Bootstrap stubs: defaults only."""
import json
from dataclasses import asdict
from pathlib import Path

from helm import config
from helm.contracts import AXES, N_BLEND, Calibration


def _calibration_from_dict(data: dict) -> Calibration:
    """Restore JSON containers to contract types without mutating the decoded data."""
    ranges = data["range"]
    if set(ranges) != set(AXES) or any(len(limits) != 2 for limits in ranges.values()):
        raise ValueError("calibration range needs two limits for each of yaw, pitch and roll")
    if len(data["blend_neutral"]) != N_BLEND:
        raise ValueError(f"calibration blend_neutral needs {N_BLEND} values")
    restored = dict(data)
    restored["neutral"] = {axis: float(value) for axis, value in data["neutral"].items()}
    restored["range"] = {axis: tuple(float(value) for value in limits) for axis, limits in ranges.items()}
    restored["blend_neutral"] = [float(value) for value in data["blend_neutral"]]
    restored["blend_peak"] = {name: float(value) for name, value in data["blend_peak"].items()}
    restored["reliable"] = list(data["reliable"])
    return Calibration(**restored)

_ROOT = Path(__file__).resolve().parent.parent / config.PROFILES_DIR
_METADATA_STEMS = frozenset({'calibration', 'breath', 'identity', 'identity_required'})

# The default player from `--player`, and the identity every judge uses. Its calibration is never
# persisted: a stranger must always start from a fresh calibration, never inherit the previous
# stranger's head range and neutral pose. docs/SPEC.md 7 already treats `guest/` as throwaway.
GUEST_PLAYER = "guest"

# Shared identities that strangers take turns using. Their calibration is never persisted, so the
# second judge of the day cannot inherit the first judge's head range and neutral pose. Named
# players (`demo`, `demo_webcam`, `sam`) do persist -- that is the point of having a name.
SHARED_PLAYERS = frozenset({GUEST_PLAYER, "judge"})


def _write_json(path: Path, payload: dict) -> None:
    """Write through a temp file in the same directory, so a crash mid-write cannot leave a
    half-written profile behind. Never called from the pipeline thread."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def load_calibration(player: str) -> Calibration | None:
    """None when there is no calibration on disk, or when the file is unusable.

    A corrupt profile must not stop the demo: the caller falls back to default calibration, which
    is the same safe path as a player who has not calibrated yet.
    """
    if player in SHARED_PLAYERS:
        return None
    path = _ROOT / player / "calibration.json"
    try:
        return _calibration_from_dict(json.loads(path.read_text()))
    except (OSError, ValueError, TypeError, KeyError):
        return None


def save_calibration(c: Calibration) -> None:
    if c.player in SHARED_PLAYERS:
        return
    _write_json(_ROOT / c.player / "calibration.json", asdict(c))


def load_breath(player: str) -> tuple[float, float] | None:
    """(max_puff_mv, max_sip_mv) for this player, or None to use the config defaults.

    Breath range lives beside the calibration rather than inside it: `Calibration` is frozen and
    has no breath fields, and the range describes the player's lungs and this particular sensor,
    not their face. Shared identities never persist it, for the same reason they never persist a
    calibration -- the next stranger must not inherit the last one's lung strength.
    """
    if player in SHARED_PLAYERS:
        return None
    try:
        data = json.loads((_ROOT / player / "breath.json").read_text())
        puff, sip = float(data["max_puff_mv"]), float(data["max_sip_mv"])
    except (OSError, ValueError, TypeError, KeyError):
        return None
    if not (0.0 < puff <= config.CALIB_BREATH_MAX_MV and 0.0 < sip <= config.CALIB_BREATH_MAX_MV):
        return None          # a corrupt range would drive the pad on its own; fall back to defaults
    return puff, sip


def save_breath(player: str, max_puff_mv: float, max_sip_mv: float) -> None:
    if player in SHARED_PLAYERS:
        return
    _write_json(_ROOT / player / "breath.json",
                {"max_puff_mv": float(max_puff_mv), "max_sip_mv": float(max_sip_mv)})


def load_mapping(player: str, game: str) -> dict:
    """Falls back to default_mapping(game) when the player has no mapping for it."""
    if game.casefold() in _METADATA_STEMS:
        raise ValueError('Game name is reserved for profile metadata')
    path = _ROOT / player / f"{game}.json"
    try:
        mapping = json.loads(path.read_text())
    except (OSError, ValueError):
        return default_mapping(game)
    return mapping if isinstance(mapping, dict) else default_mapping(game)


def save_mapping(player: str, game: str, mapping: dict) -> None:
    if game.casefold() in _METADATA_STEMS:
        raise ValueError('Game name is reserved for profile metadata')
    # Stamp the owner. A new player's mapping starts life as default_mapping(), which carries
    # "player": "_defaults", and saving it unchanged left every profile on disk claiming to belong
    # to _defaults. Copy rather than mutate: the caller's dict is usually the live mapping.
    _write_json(_ROOT / player / f"{game}.json", {**mapping, "player": player, "game": game})


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
                                     "combine": "min", "on": config.PAUSE_ON, "off": config.PAUSE_OFF}},
        "buttons": [],
        "auto": {},
        "pause": {"gesture": "eyes_closed", "hold_ms": config.PAUSE_HOLD_MS},
    }


def validate_mapping(mapping: dict, calib: Calibration | None = None,
                     learned: list[str] | None = None, has_breath: bool = False) -> list[str]:
    """Human-readable errors, empty when the mapping is valid. The coach uses this as its checker."""
    from helm.contracts import (
        BLENDSHAPE_NAMES, BREATH_EVENTS, PAD_AXES, PAD_BUTTONS, PAD_TRIGGERS,
    )

    errors = []
    if not isinstance(mapping, dict):
        return ["mapping must be an object; provide the section 7 mapping keys and values"]

    required = ("player", "game", "axes", "triggers", "gestures", "buttons", "auto", "pause")
    for key in required:
        if key not in mapping:
            errors.append(f"mapping is missing required key '{key}'; add '{key}'")

    # Recover empty containers after malformed input so the coach gets all useful errors.
    sections = {}
    for key, expected in (("axes", list), ("triggers", list), ("gestures", dict),
                          ("buttons", list), ("auto", dict), ("pause", dict)):
        value = mapping.get(key, expected())
        if not isinstance(value, expected):
            shape = "a list of objects" if expected is list else "an object"
            errors.append(f"mapping key '{key}' must be {shape}; replace its value with {shape}")
            value = expected()
        sections[key] = value

    gestures = sections["gestures"]
    pause = sections["pause"].get("gesture")
    if not isinstance(pause, str) or not pause.strip():
        errors.append("pause.gesture is missing or empty; set it to a gesture defined in 'gestures'")
    elif pause not in gestures:
        errors.append(f"pause.gesture '{pause}' is not defined in 'gestures'; define it or choose a defined gesture")

    driven = {}

    def check_target(target, owner, allowed):
        if target not in allowed:
            errors.append(f"{owner} targets {target!r}, which is not an allowed pad target; "
                          f"use one of {', '.join(allowed)}")
        if not isinstance(target, str):
            return
        if target in driven:
            errors.append(f"target '{target}' is driven by both {driven[target]} and {owner}; "
                          "remove one driver or choose a different target")
        else:
            driven[target] = owner

    held_groups = {}
    for section, allowed in (("axes", PAD_AXES), ("triggers", PAD_TRIGGERS),
                             ("buttons", PAD_BUTTONS + PAD_TRIGGERS)):
        for index, entry in enumerate(sections[section]):
            location = f"{section}[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{location} must be an object; replace it with a mapping entry")
                continue
            source_key = "gesture" if section == "buttons" else "source"
            source = entry.get(source_key)
            owner = f"{location} ({source_key} {source!r})"
            check_target(entry.get("target"), owner, allowed)
            if section != "buttons":
                continue
            if not isinstance(source, str) or source not in gestures:
                errors.append(f"{owner} references an undefined gesture; add {source!r} to 'gestures' "
                              "or choose a defined gesture")
                continue
            gesture = gestures[source]
            if entry.get("mode") != "hold" or not isinstance(gesture, dict):
                continue
            for group in sorted(_mapping_muscle_groups(gesture)):
                if group in held_groups:
                    errors.append(f"{owner} and {held_groups[group]} both use muscle group '{group}' "
                                  "in 'hold' mode; change one mode or use a different muscle group")
                else:
                    held_groups[group] = owner

    for target in sections["auto"]:
        check_target(target, f"auto[{target!r}]", PAD_AXES + PAD_TRIGGERS + PAD_BUTTONS)

    # Only a full calibration runs the expression check, so only then does `reliable` mean
    # anything. After quick or default calibration it is empty because nothing was measured --
    # "unknown", not "nothing works". Enforcing it there would forbid every facial gesture for a
    # judge on the 15-second quick path, including the brow raise the judge profile needs.
    checks_reliability = calib is not None and calib.mode == "full"

    for name, gesture in gestures.items():
        if not isinstance(gesture, dict):
            errors.append(f"gesture {name!r} must be an object; provide its kind and settings")
            continue
        kind = gesture.get("kind")
        if kind == "blendshape":
            sources = gesture.get("sources", [])
            if not isinstance(sources, list):
                errors.append(f"gesture {name!r} sources must be a list; use names from contracts.BLENDSHAPE_NAMES")
                continue
            for source in sources:
                if source not in BLENDSHAPE_NAMES:
                    errors.append(f"gesture {name!r} sources contains unknown blendshape {source!r}; "
                                  f"replace it with a name from contracts.BLENDSHAPE_NAMES: {', '.join(BLENDSHAPE_NAMES)}")
                elif checks_reliability and name != pause and source not in calib.reliable:
                    options = ", ".join(calib.reliable) or "(none passed the expression check)"
                    errors.append(f"gesture {name!r} uses blendshape '{source}', which is not in calib.reliable; "
                                  f"use one of {options}, or recalibrate to establish reliability")
        elif kind == "learned" and learned is not None and name not in learned:
            errors.append(f"learned gesture {name!r} is not in 'learned'; train it or choose an available learned gesture")
        elif kind == "breath":
            if not has_breath:
                errors.append(f"breath gesture {name!r} requires a breath device; connect one and set has_breath=True "
                              "or remove this gesture")
            if name not in BREATH_EVENTS:
                errors.append(f"breath gesture {name!r} is not a breath event; rename it to one of {', '.join(BREATH_EVENTS)}")

    return errors


def _mapping_muscle_groups(gesture: dict) -> set[str]:
    """A composite blendshape gesture occupies every muscle group in its sources."""
    if gesture.get("kind") == "breath":
        return {"breath"}
    if gesture.get("kind") != "blendshape":
        return set()
    sources = gesture.get("sources", [])
    if not isinstance(sources, list):
        return set()
    prefixes = (("brow", "brow"), ("jaw", "jaw"), ("mouth", "mouth"),
                ("eye", "eyes"), ("cheek", "cheek"), ("nose", "nose"))
    return {group for source in sources if isinstance(source, str)
            for prefix, group in prefixes if source.startswith(prefix)}


def gesture_model_path(player: str) -> str:
    return str(_ROOT / player / "gestures.npz")


def list_profiles() -> dict[str, list[str]]:
    """player -> the games that player has a mapping for. `_defaults` is not a player. A player with only a
    calibration, learned moves, breath range or Face ID (no mapping saved yet) is listed with no games, so a profile
    made in the dashboard shows up in the profile screen straight after its first calibration."""
    found: dict[str, list[str]] = {}
    if not _ROOT.is_dir():
        return found
    for folder in sorted(_ROOT.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        games = sorted(f.stem for f in folder.glob("*.json")
                       if f.stem.casefold() not in _METADATA_STEMS)
        has_identity = any((folder / name).exists() for name in ('identity.json', 'identity_required.json'))
        has_setup = any((folder / name).exists() for name in ('calibration.json', 'gestures.npz', 'breath.json'))
        if games or has_identity or has_setup:
            found[folder.name] = games
    return found
