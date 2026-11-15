# OWNER: P1
"""Coach agent: build a mapping for this player and game, then review a session (docs/SPEC.md section 11).

The agent runs on LangChain deepagents with the model named by HELM_COACH_MODEL (a provider:model string),
or by default Claude when ANTHROPIC_API_KEY is set, else OpenAI when OPENAI_API_KEY is. Keys may live in the
repo's gitignored .env. It sees a game name, gesture names and
numbers, never images. With no key, no network, a failure or a timeout, both functions fall back to an
offline path that needs nothing: the default mapping filtered to the player's reliable gestures, and a
rule-based review. Both run on a worker thread (Runtime.coach_build / coach_review), never the pipeline.
"""
import copy
import dataclasses
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from helm import config, profiles
from helm.contracts import BLENDSHAPE_NAMES, BREATH_EVENTS, PAD_AXES, PAD_BUTTONS, PAD_TRIGGERS, Calibration

log = logging.getLogger("helm.coach")

_GAMES_PATH = Path(__file__).resolve().parent / "games.json"
_BREATH_SOURCES = ("breath_puff", "breath_sip")
_MUSCLE = {"brow": "brow", "jaw": "jaw", "mouth": "mouth", "cheek": "mouth", "nose": "mouth", "eye": "eyes"}

SYSTEM_PROMPT = """You are Helm's coach. Helm turns a player's face (head pose, expressions, learned personal \
gestures) and optionally breath (sip and puff) into a virtual Xbox controller. Your job is to give one \
player the best mapping for one game, using only what this player can do reliably.

Work in this order and use the tools:
1. get_game_controls: read the game's actions, how often each is used, whether it is held or tapped, and its pad target.
2. get_player_report: read which expressions are reliable and how strong they are, head range per direction, \
learned gestures, whether breath is available, and (for a review) per-gesture session statistics.
3. Plan. Steering or the main analog axis goes to the head axis with the widest range. The most frequent and \
most time-critical actions go to the player's strongest, least tiring gestures. Held actions never share a \
muscle group (brow, jaw, mouth, eyes, breath). Rare actions can go to weaker gestures or stay unmapped. \
Never use an expression that is not in the reliable list. If the player cannot comfortably hold accelerate, \
use "auto": {"rt": 1.0}, or a breath toggle when breath is available. Always map all four face buttons A, B, \
X and Y, each to a different gesture from usable_gestures (the report lists them strongest first); \
check_mapping rejects a mapping that leaves one empty while a usable gesture is still unused.
4. Draft the mapping JSON, call check_mapping, fix every error it reports, and repeat until it returns no errors.
5. Call submit_mapping with the final JSON and one short reason per decision. You are done when it is accepted.

For a session review: read the statistics, then propose the smallest set of changes that fixes near-misses \
(attempts that reached 80% of the threshold without firing: lower `on` and `off` a little), false triggers \
(fires the player did not intend, often a very high fires_per_min: raise `on`, or move the action to a \
stronger gesture) and fatigue notices. Keep everything else exactly as it is. Submit with one reason per change.

Mapping format (JSON):
{"player": str, "game": str,
 "axes": [{"source": "yaw"|"pitch"|"roll", "target": "lx"|"ly"|"rx"|"ry", "deadzone": 0.08, "curve": 1.5, "invert": false}],
 "triggers": [{"source": "<gesture name>"|"breath_puff"|"breath_sip", "target": "lt"|"rt", "lo": 0.15, "hi": 0.85}],
 "gestures": {"<name>": {"kind": "blendshape", "sources": ["<blendshape>", ...], "combine": "max"|"min", "on": 0.6, "off": 0.4}
              | {"kind": "learned", "on": 0.7, "off": 0.5} | {"kind": "breath"} | {"kind": "breath_level", "on": 0.3, "off": 0.15}},
 "buttons": [{"gesture": "<name>", "target": "<button or lt/rt>", "mode": "tap"|"hold"|"toggle"}],
 "auto": {"rt": 1.0},
 "pause": {"gesture": "<name>", "hold_ms": 2000}}
A learned gesture's name must be one of the player's learned gestures. A breath gesture's name is one of \
soft_sip, hard_sip, soft_puff, hard_puff and needs a breath sensor: it fires once, when the breath ends, so use \
it for "tap" or "toggle". A "breath_level" gesture is named breath_puff or breath_sip: it is pressed for as long \
as the player blows (or sips) past "on", so use it for "hold" actions such as brake or drift. Keep the pause gesture as eyes closed \
(eyeBlinkLeft + eyeBlinkRight, combine "min", on 0.85, off 0.6) held 2000 ms unless the report says the eyes are unreliable. \
"on" must be greater than "off", both in (0, 1)."""


# ------------------------------------------------------------------ data the tools expose

_games_cache: dict | None = None


def _games() -> dict:
    """games.json, read once (the pipeline thread builds the editor catalog from it and must not touch disk)."""
    global _games_cache
    if _games_cache is None:
        _games_cache = json.loads(_GAMES_PATH.read_text())
    return _games_cache


def game_controls(game: str) -> dict:
    """The game's entry in games.json, or an error dict listing the known games."""
    games = _games()
    if game in games:
        return games[game]
    lower = {g.lower(): g for g in games}
    if game.lower() in lower:
        return games[lower[game.lower()]]
    return {"error": f"unknown game {game!r}", "known_games": sorted(games)}


def player_report(calib: Calibration, learned: list[str], has_breath: bool, stats: dict | None = None) -> dict:
    """What the player can do, as plain numbers. No images, no raw frames."""
    expressions = []
    for name in sorted(usable_expressions(calib)):
        if name not in BLENDSHAPE_NAMES:
            continue
        i = BLENDSHAPE_NAMES.index(name)
        neutral = calib.blend_neutral[i] if len(calib.blend_neutral) > i else 0.0
        peak = calib.blend_peak.get(name)
        expressions.append({
            "blendshape": name,
            "muscle_group": _muscle_group(name),
            "strength_above_neutral": None if peak is None else round(peak - neutral, 3),
            "measured": peak is not None,
        })
    report = {
        "player": calib.player,
        "calibration": calib.mode,
        "head_range_degrees": {axis: {"negative": round(lo, 1), "positive": round(hi, 1)}
                               for axis, (lo, hi) in calib.range.items()},
        "head_axis_meaning": {"yaw": "negative = turn left, positive = turn right",
                              "pitch": "negative = chin down, positive = chin up",
                              "roll": "negative = tilt left, positive = tilt right"},
        "reliable_expressions": expressions,
        "unreliable_or_untested": "every other blendshape: never use them",
        "usable_gestures": [{"name": n, "definition": g, "what_the_player_does": d}
                            for n, g, d in _candidates(calib, learned, has_breath)],
        "learned_gestures": list(learned),
        "breath_sensor": has_breath,
    }
    if stats is not None:
        report["session"] = stats
    return report


def _muscle_group(blendshape: str) -> str:
    for prefix, group in _MUSCLE.items():
        if blendshape.startswith(prefix):
            return group
    return "other"


# ------------------------------------------------------------------ checking

def check(mapping: dict, calib: Calibration, learned: list[str], has_breath: bool) -> list[str]:
    """profiles.validate_mapping plus the coach's own guarantees, so a submitted mapping always works."""
    errors = list(profiles.validate_mapping(mapping, calib, learned, has_breath))
    errors += [e for e in _own_errors(mapping, calib, learned, has_breath) if e not in errors]
    return errors


def _own_errors(m: dict, calib: Calibration, learned: list[str], has_breath: bool) -> list[str]:
    errors: list[str] = []
    if not isinstance(m, dict):
        return ["the mapping must be a JSON object"]
    for key in ("axes", "triggers", "gestures", "buttons", "auto", "pause"):
        if key not in m:
            errors.append(f"missing key {key!r}")
    gestures = m.get("gestures") if isinstance(m.get("gestures"), dict) else {}
    reliable = usable_expressions(calib)
    for name, g in gestures.items():
        kind = g.get("kind") if isinstance(g, dict) else None
        if kind == "blendshape":
            sources = g.get("sources") or []
            if not sources:
                errors.append(f"gesture {name!r} has no sources")
            for s in sources:
                if s not in BLENDSHAPE_NAMES:
                    errors.append(f"gesture {name!r}: {s!r} is not a blendshape name")
                elif s not in reliable:
                    errors.append(f"gesture {name!r}: {s!r} is not reliable for this player")
        elif kind == "learned":
            if name not in learned:
                errors.append(f"gesture {name!r} is learned but the player has no learned gesture by that name")
        elif kind == "breath":
            if name not in BREATH_EVENTS:
                errors.append(f"breath gesture {name!r} must be one of {list(BREATH_EVENTS)}")
            if not has_breath:
                errors.append(f"gesture {name!r} needs the breath sensor, which is not connected")
        elif kind == "breath_level":
            if name not in _BREATH_SOURCES:
                errors.append(f"live breath gesture {name!r} must be one of {list(_BREATH_SOURCES)}")
            if not has_breath:
                errors.append(f"gesture {name!r} needs the breath sensor, which is not connected")
        else:
            errors.append(f"gesture {name!r} has unknown kind {kind!r}")
        if isinstance(g, dict) and kind in ("blendshape", "learned", "breath_level"):
            on, off = g.get("on"), g.get("off")
            if not (isinstance(on, (int, float)) and isinstance(off, (int, float)) and 0 < off < on < 1):
                errors.append(f"gesture {name!r}: need 0 < off < on < 1, got on={on} off={off}")
    targets: list[str] = []
    for a in m.get("axes", []):
        if a.get("source") not in ("yaw", "pitch", "roll"):
            errors.append(f"axis source {a.get('source')!r} must be yaw, pitch or roll")
        if a.get("target") not in PAD_AXES:
            errors.append(f"axis target {a.get('target')!r} must be one of {list(PAD_AXES)}")
        targets.append(a.get("target"))
    for t in m.get("triggers", []):
        src = t.get("source")
        if src in _BREATH_SOURCES:
            if not has_breath:
                errors.append(f"trigger source {src!r} needs the breath sensor")
        elif src not in gestures:
            errors.append(f"trigger source {src!r} is not a defined gesture")
        if t.get("target") not in PAD_TRIGGERS:
            errors.append(f"trigger target {t.get('target')!r} must be lt or rt")
        targets.append(t.get("target"))
    for b in m.get("buttons", []):
        if b.get("gesture") not in gestures:
            errors.append(f"button gesture {b.get('gesture')!r} is not defined in gestures")
        if b.get("target") not in PAD_BUTTONS and b.get("target") not in PAD_TRIGGERS:
            errors.append(f"button target {b.get('target')!r} is not a pad button or trigger")
        if b.get("mode") not in ("tap", "hold", "toggle"):
            errors.append(f"button mode {b.get('mode')!r} must be tap, hold or toggle")
        targets.append(b.get("target"))
    for target in (m.get("auto") or {}):
        if target not in PAD_AXES and target not in PAD_TRIGGERS and target not in PAD_BUTTONS:
            errors.append(f"auto target {target!r} is not a pad output")
        targets.append(target)
    for t in sorted({t for t in targets if targets.count(t) > 1 and t is not None}):
        errors.append(f"target {t!r} is driven by more than one source")
    pause = m.get("pause") or {}
    if pause.get("gesture") not in gestures:
        errors.append("a pause gesture must be set and defined in gestures")
    missing = _missing_face_buttons(m)
    spare = [n for n, _, _ in _spare(m, calib, learned, has_breath)]
    if missing and spare:
        errors.append(f"face buttons {', '.join(missing)} are unmapped: map each to a different unused gesture "
                      f"from {spare}")
    return errors


# ------------------------------------------------------------------ offline path

def offline_mapping(game: str, calib: Calibration, learned: list[str], has_breath: bool) -> dict:
    """The default mapping for the game, minus what this player cannot do, with every face button filled. Valid."""
    return _offline(game, calib, learned, has_breath)[0]


def _offline(game: str, calib: Calibration, learned: list[str], has_breath: bool) -> tuple[dict, list[str]]:
    m = copy.deepcopy(profiles.default_mapping(game))
    m["player"], m["game"] = calib.player, game
    gestures = m.get("gestures", {})
    reliable = usable_expressions(calib)

    def usable(g: dict, name: str) -> bool:
        kind = g.get("kind")
        if kind == "blendshape":
            return bool(g.get("sources")) and all(s in reliable for s in g["sources"])
        if kind == "learned":
            return name in learned
        if kind == "breath":
            return has_breath and name in BREATH_EVENTS
        if kind == "breath_level":
            return has_breath and name in _BREATH_SOURCES
        return False

    m["gestures"] = gestures = {n: g for n, g in gestures.items() if usable(g, n)}
    m["buttons"] = [b for b in m.get("buttons", []) if b.get("gesture") in gestures]
    m["triggers"] = [t for t in m.get("triggers", [])
                     if (t.get("source") in _BREATH_SOURCES and has_breath) or t.get("source") in gestures]
    m.setdefault("axes", [])
    m.setdefault("auto", {})
    if (m.get("pause") or {}).get("gesture") not in gestures:
        gestures["eyes_closed"] = {"kind": "blendshape", "sources": ["eyeBlinkLeft", "eyeBlinkRight"],
                                   "combine": "min", "on": config.PAUSE_ON, "off": config.PAUSE_OFF}
        m["pause"] = {"gesture": "eyes_closed", "hold_ms": config.PAUSE_HOLD_MS}
    _fill(m, game, calib, learned, has_breath)
    if check(m, calib, learned, has_breath):
        m = _minimal_mapping(game, calib)              # last resort: steer and pause, plus what can be filled
        _fill(m, game, calib, learned, has_breath)
    return m, describe(m, game)


# Face expressions gestures are built from, in default preference order: name, blendshapes (read as their max),
# on, off, plain words. Left and right smiles are one gesture: tracking cannot tell them apart reliably. Pucker was
# dropped (awkward), then cheek puff and nose scrunch (MediaPipe barely moved them on the test laptop). The fourth
# face button is a learned move instead: full calibration ends by training "nod_up". Old mappings keep working.
_EXPRESSIONS = (
    ("brow_raise", ("browInnerUp",), 0.6, 0.4, "eyebrow raise"),
    ("smile", ("mouthSmileLeft", "mouthSmileRight"), 0.6, 0.4, "smile"),
    ("jaw_open", ("jawOpen",), 0.7, 0.45, "mouth open wide"),
)


def breath_level_gesture() -> dict:
    """A live breath gesture (breath_puff or breath_sip): its level is the pressure, 0..1 of the player's range."""
    return {"kind": "breath_level", "on": config.BREATH_LEVEL_ON, "off": config.BREATH_LEVEL_OFF}


def expression_gesture(sources: tuple[str, ...], on: float, off: float) -> dict:
    g = {"kind": "blendshape", "sources": list(sources), "on": on, "off": off,
         "min_hold_ms": config.EXPRESSION_MIN_HOLD_MS}
    if len(sources) > 1:
        g["combine"] = "max"
    return g
_FACE_BUTTONS = ("A", "B", "X", "Y")
_FREQUENCY_RANK = {"constant": 0, "often": 1, "occasional": 2, "rare": 3}


def usable_expressions(calib: Calibration) -> set[str]:
    """Blendshapes the coach may use. After a full calibration, the ones that passed the check; otherwise also
    the ones quick mode trusts (profiles.validate_mapping only checks reliability after a full calibration)."""
    usable = set(calib.reliable)
    if calib.mode != "full":
        usable |= set(config.QUICK_ASSUMED_RELIABLE)
    return usable


def _candidates(calib: Calibration, learned: list[str], has_breath: bool) -> list[tuple[str, dict, str]]:
    """Every gesture this player can use for a button, best first: (name, definition, what the player does).
    Learned moves first (the player taught them on purpose), then expressions, strongest measured first,
    then breath."""
    usable = usable_expressions(calib)

    def strength(sources: tuple[str, ...]) -> float:
        best = -1.0                                    # unmeasured: after the measured ones, in default order
        for blend in sources:
            peak = calib.blend_peak.get(blend)
            if peak is not None:
                i = BLENDSHAPE_NAMES.index(blend)
                best = max(best, peak - (calib.blend_neutral[i] if len(calib.blend_neutral) > i else 0.0))
        return best

    out = [(n, {"kind": "learned", "on": 0.7, "off": 0.5}, f"your move \"{n.replace('_', ' ')}\"")
           for n in learned]
    face = sorted((e for e in _EXPRESSIONS if set(e[1]) <= usable), key=lambda e: -strength(e[1]))
    out += [(n, expression_gesture(srcs, on, off), words) for n, srcs, on, off, words in face]
    if has_breath:
        out += [("breath_puff", breath_level_gesture(), "puff into the tube"),
                ("breath_sip", breath_level_gesture(), "sip on the tube")]
        out += [(n, {"kind": "breath"}, n.replace("_", " ")) for n in ("hard_puff", "hard_sip", "soft_puff", "soft_sip")]
    return out


def gesture_catalog(calib: Calibration, learned: list[str], has_breath: bool, game: str) -> dict:
    """Everything the dashboard's mapping editor can put on a control: each gesture with the definition to
    insert, plain words, and whether this player can use it; plus the game's action name per pad target."""
    usable = usable_expressions(calib)
    gestures = [{"name": n, "label": w[0].upper() + w[1:], "group": "face",
                 "definition": expression_gesture(srcs, on, off), "usable": set(srcs) <= usable}
                for n, srcs, on, off, w in _EXPRESSIONS]
    gestures.append({"name": "eyes_closed", "label": "Close both eyes", "group": "face", "usable": True,
                     "definition": {"kind": "blendshape", "sources": ["eyeBlinkLeft", "eyeBlinkRight"],
                                    "combine": "min", "on": config.PAUSE_ON, "off": config.PAUSE_OFF}})
    gestures += [{"name": n, "label": n.replace("_", " ").capitalize(), "group": "learned", "usable": True,
                  "definition": {"kind": "learned", "on": 0.7, "off": 0.5}} for n in learned]
    if has_breath:
        gestures += [{"name": n, "label": label, "group": "breath", "usable": True, "definition": breath_level_gesture()}
                     for n, label in (("breath_puff", "Puff (live)"), ("breath_sip", "Sip (live)"))]
        gestures += [{"name": n, "label": n.replace("_", " ").capitalize() + " (when you stop)",
                      "group": "breath", "usable": True, "definition": {"kind": "breath"}} for n in BREATH_EVENTS]
    controls = {a["target"]: a["name"] for a in game_controls(game).get("actions", [])
                if isinstance(a, dict) and "target" in a}
    return {"gestures": gestures, "controls": controls}


def _used(m: dict) -> tuple[set[str], set[str]]:
    """Gesture names that drive something, and the blendshapes behind them."""
    gestures = m.get("gestures") if isinstance(m.get("gestures"), dict) else {}
    names = {b.get("gesture") for b in m.get("buttons", []) if isinstance(b, dict)}
    names |= {t.get("source") for t in m.get("triggers", []) if isinstance(t, dict)}
    names.add((m.get("pause") or {}).get("gesture"))
    sources = {s for n in names for s in ((gestures.get(n) or {}).get("sources") or [])}
    return names, sources


def _spare(m: dict, calib: Calibration, learned: list[str], has_breath: bool) -> list[tuple[str, dict, str]]:
    names, sources = _used(m)
    return [(n, g, d) for n, g, d in _candidates(calib, learned, has_breath)
            if n not in names and not set(g.get("sources") or []) & sources]


def _missing_face_buttons(m: dict) -> list[str]:
    taken = {b.get("target") for b in m.get("buttons", []) if isinstance(b, dict)}
    return [t for t in _FACE_BUTTONS if t not in taken]


def _fill(m: dict, game: str, calib: Calibration, learned: list[str], has_breath: bool) -> None:
    """Map every empty face button (most used action first) to the best unused gesture, and make a constant
    held trigger (accelerate) automatic when nothing drives it."""
    actions = {a["target"]: a for a in game_controls(game).get("actions", []) if isinstance(a, dict) and "target" in a}
    gestures = m.setdefault("gestures", {})
    buttons = m.setdefault("buttons", [])
    missing = sorted(_missing_face_buttons(m), key=lambda t: _FREQUENCY_RANK.get(actions.get(t, {}).get("frequency"), 4))
    pool = _spare(m, calib, learned, has_breath)
    for target in missing:
        if not pool:
            break
        held = actions.get(target, {}).get("kind") == "held"
        # A breath event lasts one tick and cannot be held: a held action takes the next gesture that can be,
        # and only if none is left gets an event, as a tap.
        pick = next((i for i, (_, d, _) in enumerate(pool) if not held or d["kind"] != "breath"), 0)
        name, definition, _ = pool.pop(pick)
        if gestures.get(name, {}).get("kind") != definition["kind"]:
            gestures[name] = definition
        mode = "hold" if held and definition["kind"] != "breath" else "tap"
        buttons.append({"gesture": name, "target": target, "mode": mode})
    driven = ({b.get("target") for b in buttons} | {t.get("target") for t in m.get("triggers", [])}
              | set(m.get("auto") or {}))
    rt = actions.get("rt")
    if rt and rt.get("frequency") == "constant" and "rt" not in driven:
        m.setdefault("auto", {})["rt"] = 1.0


def describe(m: dict, game: str) -> list[str]:
    """One plain line per face button and the throttle, for the dashboard."""
    actions = {a["target"]: a["name"] for a in game_controls(game).get("actions", []) if isinstance(a, dict) and "target" in a}
    gestures = m.get("gestures") or {}
    words = {n: w for n, _, _, _, w in _EXPRESSIONS}

    def what(name: str) -> str:
        g = gestures.get(name) or {}
        if g.get("kind") == "learned":
            return f"your move \"{name.replace('_', ' ')}\""
        if g.get("kind") == "blendshape":
            for _, srcs, _, _, w in _EXPRESSIONS:
                if set(g.get("sources") or []) == set(srcs):
                    return w
        return words.get(name, name.replace("_", " "))

    lines = []
    by_target = {b.get("target"): b for b in m.get("buttons", []) if isinstance(b, dict)}
    for target in _FACE_BUTTONS:
        action = f" ({actions[target]})" if target in actions else ""
        b = by_target.get(target)
        if b:
            hold = ", hold it" if b.get("mode") == "hold" else ""
            lines.append(f"{target}{action}: {what(b['gesture'])}{hold}")
        else:
            lines.append(f"{target}{action}: unmapped, no reliable gesture left (teach a move or recalibrate)")
    if (m.get("auto") or {}).get("rt"):
        lines.append(f"{actions.get('rt', 'Right trigger').capitalize()}: automatic, always on")
    pause = m.get("pause") or {}
    if pause.get("gesture"):
        lines.append(f"Pause: {what(pause['gesture']).replace('eyes closed', 'close your eyes')} for "
                     f"{pause.get('hold_ms', config.PAUSE_HOLD_MS) / 1000:g} s")
    return lines


def _minimal_mapping(game: str, calib: Calibration) -> dict:
    return {
        "player": calib.player, "game": game,
        "axes": [{"source": "yaw", "target": "lx", "deadzone": config.AXIS_DEADZONE, "curve": config.AXIS_GAMMA,
                  "invert": False}],
        "triggers": [],
        "gestures": {"eyes_closed": {"kind": "blendshape", "sources": ["eyeBlinkLeft", "eyeBlinkRight"],
                                     "combine": "min", "on": config.PAUSE_ON, "off": config.PAUSE_OFF}},
        "buttons": [], "auto": {"rt": 1.0},
        "pause": {"gesture": "eyes_closed", "hold_ms": config.PAUSE_HOLD_MS},
    }


def offline_review(mapping: dict, stats: dict, calib: Calibration, learned: list[str],
                   has_breath: bool) -> tuple[dict, list[str]]:
    """Small, rule-based threshold changes from the session statistics."""
    m = copy.deepcopy(mapping)
    changes: list[str] = []
    step = config.COACH_THRESHOLD_STEP
    for name, s in (stats.get("gestures") or {}).items():
        g = m.get("gestures", {}).get(name)
        if not g or "on" not in g or "off" not in g:
            continue
        on, off = float(g["on"]), float(g["off"])
        fires, near = int(s.get("fires", 0)), int(s.get("near_misses", 0))
        if s.get("fires_per_min", 0.0) >= config.COACH_FALSE_TRIGGER_PER_MIN and on + step < 0.95:
            g["on"], g["off"] = round(on + step, 2), round(off + step, 2)
            changes.append(f"{name} fired {s['fires_per_min']} times a minute, likely by accident: "
                           f"raised its threshold to {g['on']}.")
        elif near >= config.COACH_MIN_NEAR_MISSES and near >= fires and off - step > 0.1:
            g["on"], g["off"] = round(on - step, 2), round(off - step, 2)
            changes.append(f"{name} nearly fired {near} times without firing: lowered its threshold to {g['on']}.")
    for notice in stats.get("notices") or []:
        changes.append(f"Noted: {notice}")
    if check(m, calib, learned, has_breath):
        return mapping, []
    return m, changes


# ------------------------------------------------------------------ the agent

class _Session:
    """Tools for one agent run. submit_mapping only accepts a mapping with no errors."""

    def __init__(self, game: str, calib: Calibration, learned: list[str], has_breath: bool,
                 stats: dict | None = None):
        self.game, self.calib, self.learned, self.has_breath, self.stats = game, calib, learned, has_breath, stats
        self.submitted: tuple[dict, list[str]] | None = None
        self.closed = threading.Event()                # set on timeout: late submissions are ignored
        self.offline_reason = ""                       # why the agent did not run or finish, for the dashboard

    def tools(self) -> list:
        session = self

        def get_game_controls(game: str) -> str:
            """Return the game's actions as JSON: name, held or tapped, how often it is used, analog or not, and
            the controller target it is bound to. Unknown games return the list of known games."""
            return json.dumps(game_controls(game or session.game))

        def get_player_report() -> str:
            """Return the player's abilities as JSON: reliable expressions with their strength, head range per
            direction in degrees, learned gestures, whether the breath sensor is connected and, for a review,
            per-gesture session statistics (fires, near-misses, fires per minute, peak levels) and fatigue notices."""
            return json.dumps(player_report(session.calib, session.learned, session.has_breath, session.stats))

        def check_mapping(mapping_json: str) -> str:
            """Validate a mapping given as a JSON string. Returns a JSON list of errors; an empty list means valid."""
            try:
                mapping = json.loads(mapping_json)
            except json.JSONDecodeError as e:
                return json.dumps([f"not valid JSON: {e}"])
            return json.dumps(check(mapping, session.calib, session.learned, session.has_breath))

        def submit_mapping(mapping_json: str, reasons: list[str]) -> str:
            """Submit the final mapping as a JSON string with one short reason per decision or change.
            Accepted only when check_mapping reports no errors; otherwise returns the errors to fix."""
            try:
                mapping = json.loads(mapping_json)
            except json.JSONDecodeError as e:
                return f"rejected: not valid JSON: {e}"
            errors = check(mapping, session.calib, session.learned, session.has_breath)
            if errors:
                return "rejected, fix these errors and submit again: " + json.dumps(errors)
            if session.closed.is_set():
                return "rejected: the time limit has passed"
            mapping["player"], mapping["game"] = session.calib.player, session.game
            session.submitted = (mapping, [str(r) for r in reasons])
            return "accepted"

        return [get_game_controls, get_player_report, check_mapping, submit_mapping]


_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
_env_loaded = False


def _load_env() -> None:
    """Read KEY=value lines from the repo's .env (gitignored) once. Variables already set win."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    try:
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _model_name() -> str:
    """HELM_COACH_MODEL if set; otherwise Anthropic when its key is present, else OpenAI when its key is."""
    _load_env()
    if os.environ.get("HELM_COACH_MODEL"):
        return os.environ["HELM_COACH_MODEL"]
    if not _has_credentials(config.COACH_DEFAULT_MODEL) and os.environ.get("OPENAI_API_KEY"):
        return config.COACH_OPENAI_MODEL
    return config.COACH_DEFAULT_MODEL


def _has_credentials(model: str) -> bool:
    provider = model.split(":", 1)[0] if ":" in model else ""
    keys = {"anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"), "openai": ("OPENAI_API_KEY",),
            "google_genai": ("GOOGLE_API_KEY", "GEMINI_API_KEY")}.get(provider)
    return keys is None or any(os.environ.get(k) for k in keys)   # unknown providers: let the agent try


# ------------------------------------------------------------------ Claude Code (the user's subscription)

_CLAUDE_SYSTEM = """You are Helm's coach. Helm turns a player's face (head pose, expressions, learned personal \
gestures) and optionally breath into a virtual Xbox 360 controller. Give this player the best mapping for this game.

1. Controls first. If the message includes the game's controls, use them. If it does not, search the web for the \
game's default Xbox controller layout and work out which actions matter most (held all the time, frequent, \
rare). List the actions you used in `controls` as "target: action", e.g. "A: jump".
2. Plan. Steering or the main movement axis goes to head turning (yaw). The most frequent, time-critical actions \
go to the player's strongest gestures; rare ones to weaker gestures. Map all four face buttons A, B, X and Y, each \
to a different gesture from usable_gestures (strongest first). Use only gestures from usable_gestures, with the \
definition given there. An action held almost all the time (accelerate, run) is better as "auto": {"rt": 1.0} \
than a held face. Use mode "hold" for held actions, "tap" for tapped ones, "toggle" for on/off ones. Keep the \
pause gesture as eyes closed held 2000 ms.
3. For a session review, change as little as possible: lower `on`/`off` by 0.05 for near-misses, raise them for \
gestures that fire far too often, and fill any empty face button.

Return the complete mapping as structured output, with one reason per decision in `reasons`, each a single \
plain sentence of at most 15 words that a player reads (e.g. "Brow raise fires items: your strongest, quickest \
move."). Helm checks the mapping; if it has errors you will get them back and must return a corrected complete \
mapping.

Pad targets are case-sensitive and exactly: buttons """ + ", ".join(PAD_BUTTONS) + """; triggers lt, rt; \
stick axes lx, ly, rx, ry.

""" + SYSTEM_PROMPT[SYSTEM_PROMPT.index("Mapping format (JSON):"):]

_CLAUDE_SCHEMA = {
    "type": "object",
    "properties": {
        "controls": {"type": "array", "items": {"type": "string"}},
        "mapping": {"type": "object"},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["mapping", "reasons"],
}


def _backend() -> str:
    _load_env()
    choice = (os.environ.get("HELM_COACH_BACKEND") or config.COACH_BACKEND).lower()
    if choice == "auto":
        return "claude" if _claude_cli() else "api"
    return choice


def _claude_cli() -> str | None:
    """The Claude Code executable (claude, or claude.cmd on Windows), from PATH or the usual install folders."""
    return find_claude()


def _claude_context(session: _Session, task: str) -> str:
    controls = game_controls(session.game)
    known = "error" not in controls
    lines = [task, ""]
    if known:
        lines.append(f"The game's controls (Helm's table for {session.game}):")
        lines.append(json.dumps(controls, indent=1))
    else:
        lines.append(f"Helm has no control table for {session.game!r}. Search the web for its default Xbox "
                     "controller layout first.")
    lines += ["", "The player:", json.dumps(player_report(session.calib, session.learned, session.has_breath,
                                                          session.stats), indent=1)]
    return "\n".join(lines)


def _run_claude(session: _Session, task: str) -> tuple[dict, list[str]] | None:
    """Ask Claude Code (logged in with the user's Claude subscription) for a mapping; check it and send the
    errors back until it passes. Returns (mapping, reasons) or None, with session.offline_reason set."""
    exe = _claude_cli()
    if not exe:
        session.offline_reason = "Claude Code is not installed (install it and run `claude` once to log in)"
        return None
    model = os.environ.get("HELM_COACH_CLAUDE_MODEL", config.COACH_CLAUDE_MODEL)
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    cmd = [exe, "-p", "--output-format", "json", "--model", model, "--no-session-persistence", "--effort", os.environ.get("HELM_CAPTAIN_EFFORT", config.CAPTAIN_EFFORT),
           "--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch,WebFetch",
           "--system-prompt", _CLAUDE_SYSTEM, "--json-schema", json.dumps(_CLAUDE_SCHEMA)]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    base = _claude_context(session, task)
    prompt = base
    deadline = time.monotonic() + config.COACH_CLAUDE_TIMEOUT_S
    for _ in range(config.COACH_CLAUDE_ATTEMPTS):
        remaining = deadline - time.monotonic()
        if remaining < 5:
            break
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                                  timeout=remaining, env=env, cwd=tempfile.gettempdir(), creationflags=flags)
        except subprocess.TimeoutExpired:
            session.offline_reason = f"Claude took longer than {config.COACH_CLAUDE_TIMEOUT_S} s"
            return None
        try:
            data = json.loads(proc.stdout or "{}")
        except ValueError:
            data = {}
        out = data.get("structured_output") if isinstance(data, dict) else None
        if data.get("is_error") or not isinstance(out, dict) or not isinstance(out.get("mapping"), dict):
            text = f"{data.get('result') or ''} {proc.stderr or ''}".strip()
            log.warning("coach: Claude Code failed (exit %s): %s", proc.returncode, text[:300])
            session.offline_reason = ("Claude Code is not logged in (run `claude` once and log in)"
                                      if "login" in text.lower() or "log in" in text.lower()
                                      else f"Claude Code failed: {_short_reason(text) or 'no answer'}")
            return None
        mapping = out["mapping"]
        mapping["player"], mapping["game"] = session.calib.player, session.game
        reasons = [str(r) for r in out.get("reasons") or []]
        controls = [str(c) for c in out.get("controls") or []]
        errors = check(mapping, session.calib, session.learned, session.has_breath)
        if not errors:
            if controls and "error" in game_controls(session.game):
                reasons.insert(0, "Controls found: " + "; ".join(controls))
            return mapping, reasons
        log.info("coach: Claude's mapping had %d errors, asking for a fix", len(errors))
        prompt = (base + "\n\nYour previous mapping:\n" + json.dumps(mapping) + "\n\nHelm rejected it. Fix every "
                  "one of these errors and return the complete corrected mapping:\n- " + "\n- ".join(errors))
    session.offline_reason = session.offline_reason or "Claude's mapping still had errors after several tries"
    return None


def _ask(session: _Session, task: str) -> tuple[dict, list[str]] | None:
    """Claude Code on the subscription when available (or chosen), else the API agent; None means offline."""
    backend = _backend()
    if backend == "offline":
        session.offline_reason = "the coach is set to offline"
        return None
    if backend == "claude":
        return _run_claude(session, task)
    return _run_agent(session, task)


def _run_agent(session: _Session, task: str) -> tuple[dict, list[str]] | None:
    """Run the deep agent with a time limit. Returns (mapping, reasons) or None on any failure."""
    model = _model_name()
    if not _has_credentials(model):
        log.info("coach: no API key for %s, using the offline path", model)
        session.offline_reason = ("Claude Code is not installed and no API key is set (install Claude Code and run "
                                  "`claude` once to log in)")
        return None
    outcome: dict = {}

    def run() -> None:
        try:
            from deepagents import create_deep_agent
            from langchain.chat_models import init_chat_model

            kwargs = {"max_tokens": 16000} if model.startswith("anthropic:") else {}
            agent = create_deep_agent(model=init_chat_model(model, **kwargs), tools=session.tools(),
                                      system_prompt=SYSTEM_PROMPT, name="helm-coach")
            agent.invoke({"messages": [{"role": "user", "content": task}]},
                         config={"recursion_limit": config.COACH_RECURSION_LIMIT})
        except Exception as e:                         # network, auth, model or tool errors: offline path
            outcome["error"] = f"{type(e).__name__}: {e}"

    worker = threading.Thread(target=run, name="coach-agent", daemon=True)
    worker.start()
    worker.join(config.COACH_TIMEOUT_S)
    session.closed.set()
    if worker.is_alive():
        log.warning("coach: timed out after %s s, using the offline path", config.COACH_TIMEOUT_S)
        session.offline_reason = f"{model} took longer than {config.COACH_TIMEOUT_S} s"
        return None
    if "error" in outcome:
        log.warning("coach: agent failed (%s), using the offline path", outcome["error"])
        session.offline_reason = _short_reason(outcome["error"])
    elif session.submitted is None:
        session.offline_reason = f"{model} finished without submitting a valid mapping"
    return session.submitted


def _short_reason(error: str) -> str:
    """One readable line for the dashboard, e.g. the provider's "no credits" message."""
    lower = error.lower()
    if "credit" in lower or "quota" in lower or "billing" in lower:
        return "the API account is out of credits"
    if "401" in error or "authentication" in lower or "api key" in lower:
        return "the API key was rejected"
    if "connect" in lower or "timeout" in lower or "network" in lower:
        return "no connection to the model"
    return error.split("\n")[0][:120]


def _offline_note(session: _Session) -> list[str]:
    return [f"Coach offline: {session.offline_reason}"] if session.offline_reason else []


# ------------------------------------------------------------------ public interface

def build_mapping(game: str, calib: Calibration, learned: list[str], has_breath: bool) -> dict:
    """Return {"mapping": <valid mapping dict>, "rationale": [str, ...]}."""
    session = _Session(game, calib, learned, has_breath)
    task = (f"Build the best mapping for player {calib.player!r} playing {game!r}. "
            "Read the controls and the player report, plan, check, fix, and submit.")
    try:
        result = _ask(session, task)
    except Exception as e:
        log.warning("coach: %s, using the offline path", e)
        session.offline_reason = _short_reason(f"{type(e).__name__}: {e}")
        result = None
    if result is not None:
        return {"mapping": result[0], "rationale": result[1]}
    mapping, lines = _offline(game, calib, learned, has_breath)
    return {"mapping": mapping, "rationale": ["Offline coach (built without the AI model):", *lines,
                                              *_offline_note(session)]}


def review_session(mapping: dict, stats: dict, calib: Calibration, learned: list[str], has_breath: bool) -> dict:
    """Return {"mapping": <valid mapping dict>, "changes": [str, ...]}."""
    game = mapping.get("game", "SuperTuxKart")
    # Expressions already in the mapping were chosen (often by hand): the review may keep them even if weak.
    chosen = {s for g in (mapping.get("gestures") or {}).values() if isinstance(g, dict) for s in g.get("sources") or []}
    calib = dataclasses.replace(calib, reliable=list(dict.fromkeys([*calib.reliable, *sorted(chosen)])))
    session = _Session(game, calib, learned, has_breath, stats)
    task = ("Review this session and improve the current mapping with the smallest set of changes. "
            f"Current mapping: {json.dumps(mapping)}")
    try:
        result = _ask(session, task)
    except Exception as e:
        log.warning("coach: %s, using the offline path", e)
        session.offline_reason = _short_reason(f"{type(e).__name__}: {e}")
        result = None
    if result is not None:
        return {"mapping": result[0], "changes": result[1]}
    filled: list[str] = []
    if check(mapping, calib, learned, has_breath):     # fill empty face buttons; rebuild only if that is not enough
        candidate = copy.deepcopy(mapping)
        before = _missing_face_buttons(candidate)
        _fill(candidate, game, calib, learned, has_breath)
        if not check(candidate, calib, learned, has_breath):
            mapping = candidate
            filled = [line for line in describe(candidate, game) if line[:1] in before and "unmapped" not in line]
            filled = [f"Mapped an empty button: {line}" for line in filled]
        else:
            mapping = offline_mapping(game, calib, learned, has_breath)
            filled = ["The mapping no longer fit this player, so it was rebuilt:", *describe(mapping, game)]
    reviewed, changes = offline_review(mapping, stats, calib, learned, has_breath)
    changes = filled + changes
    return {"mapping": reviewed,
            "changes": (changes or ["offline review: no changes needed"]) + _offline_note(session)}


# ------------------------------------------------------------------ the Captain: talk to it, it edits your mapping
#
# One fast Claude Code call on the player's own Claude login (no API key, no web search for a known game, no
# plugins or MCP servers). Everything it needs is in the message: the game's controls, what this player can do,
# the current mapping and the request. It answers with a short list of CHANGES, never a whole mapping, and Helm
# applies them to the current mapping, so every setting it does not name (steering sensitivity, sliders, hold
# times) stays exactly as it was. Helm checks the result; a change that does not fit is skipped and reported, and
# only a result that still fails validation is sent back once to be fixed.

CAPTAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "changes": {"type": "array", "items": {"type": "object", "properties": {
            "op": {"enum": ["button", "clear", "analog", "auto", "threshold", "steering", "axis", "pause"]},
            "target": {"type": "string"}, "gesture": {"type": "string"},
            "mode": {"enum": ["tap", "hold", "toggle"]}, "source": {"type": "string"},
            "value": {"type": "number"}, "on": {"type": "number"}, "off": {"type": "number"},
            "min_hold_ms": {"type": "number"}, "gain": {"type": "number"}, "deadzone": {"type": "number"},
            "curve": {"type": "number"}, "invert": {"type": "boolean"}, "hold_ms": {"type": "number"},
            "reason": {"type": "string"}},
            "required": ["op", "reason"]}},
    },
    "required": ["summary", "changes"],
}

CAPTAIN_SYSTEM = """You are the Captain inside Helm, a hands-free game controller: head movement drives the sticks, \
face expressions and learned personal moves press buttons, and an optional sip-and-puff sensor adds breath. You \
change the player's CURRENT mapping to do what they ask, as little as possible, and explain each change in one \
short sentence a player reads (at most 15 words).

Answer with a list of changes. Each change is one operation:
- {"op":"button","target":T,"gesture":G,"mode":"tap"|"hold"|"toggle"}: G presses T (a pad button or lt/rt). \
"hold" for actions held down (nitro, skid, brake), "tap" for presses, "toggle" for on/off.
- {"op":"clear","target":T}: nothing drives T any more.
- {"op":"analog","target":"lt"|"rt","source":G}: the trigger follows how strongly G is made (breath_sip, \
breath_puff, or an expression).
- {"op":"auto","target":T,"value":1}: T is held all the time (e.g. accelerate); value 0 removes it.
- {"op":"threshold","gesture":G,"on":0..1,"off":0..1,"min_hold_ms":ms}: how hard G must be made: raise "on" (and \
"min_hold_ms" to 150-250) if it fires by accident, lower it if it is hard to trigger. Keep off about 0.2 below on.
- {"op":"steering","gain":0.5..3,"deadzone":0..0.3,"curve":1..3,"invert":bool}: steering on the left stick. Higher \
gain = less head turn for full lock (use it when steering needs too much turning); lower gain or a bigger \
deadzone when it is twitchy.
- {"op":"axis","target":"lx"|"ly"|"rx"|"ry","source":"yaw"|"pitch"|"roll"|"none","invert":bool}: a head movement \
on a stick axis.
- {"op":"pause","gesture":G,"hold_ms":ms}: the gesture held to pause and resume.
Use only gesture names from the player's gesture list. Prefer gestures marked usable; a gesture marked weak only \
when the player asks for it. Never give two different targets the same gesture unless asked. Held actions should \
not share a muscle group. If the request needs nothing changed, return no changes and say why in the summary. \
Keep the summary to one sentence. Be quick: no long deliberation. After the structured output, reply with \
just: done"""


def _claude_paths() -> list[str]:
    """Where Claude Code usually lives, for when it is not on PATH (a terminal opened before the install)."""
    home = Path.home()
    found = [shutil.which("claude"), os.environ.get("HELM_CLAUDE_PATH")]
    if sys.platform == "win32":
        appdata, local = os.environ.get("APPDATA", ""), os.environ.get("LOCALAPPDATA", "")
        found += [str(home / ".local" / "bin" / "claude.exe"), str(Path(appdata) / "npm" / "claude.cmd"),
                  str(Path(local) / "Programs" / "claude" / "claude.exe"), str(home / ".claude" / "local" / "claude.exe")]
    else:
        found += [str(home / ".local" / "bin" / "claude"), str(home / ".claude" / "local" / "claude"),
                  "/opt/homebrew/bin/claude", "/usr/local/bin/claude"]
    return [p for p in found if p]


def find_claude() -> str | None:
    """The Claude Code executable, from PATH or the usual install folders."""
    for path in _claude_paths():
        if Path(path).is_file():
            return path
    return None


def _gesture_menu(calib: Calibration, learned: list[str], has_breath: bool, game: str) -> dict[str, dict]:
    """Every gesture the Captain may use: name -> {definition, label, usable}."""
    return {g["name"]: g for g in gesture_catalog(calib, learned, has_breath, game)["gestures"]}


def _binding_text(m: dict, target: str, menu: dict) -> str:
    def label(name: str) -> str:
        return (menu.get(name) or {}).get("label", name.replace("_", " "))
    for b in m.get("buttons") or []:
        if b.get("target") == target:
            return f"{label(b.get('gesture', '?'))} ({b.get('mode', 'tap')})"
    for t in m.get("triggers") or []:
        if t.get("target") == target:
            return f"{label(t.get('source', '?'))} (analog)"
    if (m.get("auto") or {}).get(target):
        return "always on"
    for a in m.get("axes") or []:
        if a.get("target") == target:
            return f"head {a.get('source')}"
    return "nothing"


def _drivers_removed(m: dict, target: str) -> None:
    m["buttons"] = [b for b in m.get("buttons") or [] if b.get("target") != target]
    m["triggers"] = [t for t in m.get("triggers") or [] if t.get("target") != target]
    if target in (m.get("auto") or {}):
        del m["auto"][target]


def apply_changes(mapping: dict, changes: list[dict], menu: dict) -> tuple[dict, list[dict], list[str]]:
    """Apply the Captain's changes to a copy of `mapping`. Returns (new mapping, applied changes, skipped notes).
    A change that does not fit (unknown gesture or target, bad numbers) is skipped, not guessed."""
    m = copy.deepcopy(mapping)
    for key, empty in (("buttons", []), ("triggers", []), ("axes", []), ("gestures", {}), ("auto", {})):
        if not isinstance(m.get(key), type(empty)):
            m[key] = copy.deepcopy(empty)
    applied, skipped = [], []

    def need_gesture(name: str) -> bool:
        if name in m["gestures"]:
            return True
        if name in menu:
            m["gestures"][name] = copy.deepcopy(menu[name]["definition"])
            return True
        return False

    def number(c: dict, key: str, lo: float, hi: float) -> float | None:
        v = c.get(key)
        return min(max(float(v), lo), hi) if isinstance(v, (int, float)) else None

    for c in changes:
        op, target, gesture = c.get("op"), c.get("target"), c.get("gesture")
        try:
            if op == "button":
                if target not in PAD_BUTTONS + PAD_TRIGGERS or not gesture or not need_gesture(gesture):
                    raise ValueError(f"cannot put {gesture!r} on {target!r}")
                mode = c.get("mode") if c.get("mode") in ("tap", "hold", "toggle") else "tap"
                if m["gestures"][gesture].get("kind") == "breath" and mode == "hold":
                    mode = "tap"                   # a breath event lasts one tick: it cannot be held
                _drivers_removed(m, target)
                m["buttons"].append({"gesture": gesture, "target": target, "mode": mode})
            elif op == "clear":
                if target not in PAD_BUTTONS + PAD_TRIGGERS + PAD_AXES:
                    raise ValueError(f"unknown target {target!r}")
                _drivers_removed(m, target)
                m["axes"] = [a for a in m["axes"] if a.get("target") != target]
            elif op == "analog":
                source = c.get("source") or gesture
                if target not in PAD_TRIGGERS or not source or (source not in _BREATH_SOURCES and not need_gesture(source)):
                    raise ValueError(f"cannot drive {target!r} from {source!r}")
                if source in _BREATH_SOURCES:
                    need_gesture(source)
                if (m["gestures"].get(source) or {}).get("kind") == "breath":
                    raise ValueError(f"{source} fires once, it cannot be analog")
                _drivers_removed(m, target)
                m["triggers"].append({"source": source, "target": target, "lo": 0.15, "hi": 0.85})
            elif op == "auto":
                if target not in PAD_BUTTONS + PAD_TRIGGERS + PAD_AXES:
                    raise ValueError(f"unknown target {target!r}")
                value = float(c.get("value", 1.0))
                _drivers_removed(m, target)
                if value:
                    m["auto"][target] = value
            elif op == "threshold":
                g = m["gestures"].get(gesture)
                if not isinstance(g, dict) or "on" not in g:
                    raise ValueError(f"{gesture!r} is not in the mapping")
                on = number(c, "on", 0.1, 0.95)
                if on is not None:
                    g["on"] = round(on, 2)
                    g["off"] = round(number(c, "off", 0.05, on - 0.05) or max(0.05, on - 0.2), 2)
                hold = number(c, "min_hold_ms", 0, 500)
                if hold is not None and g.get("kind") != "breath":
                    g["min_hold_ms"] = int(hold)
            elif op == "steering":
                axis = next((a for a in m["axes"] if a.get("target") == "lx"), None)
                if axis is None:
                    raise ValueError("steering is not on the left stick")
                for key, lo, hi in (("gain", config.STEER_GAIN_MIN, config.STEER_GAIN_MAX), ("deadzone", 0.0, 0.3),
                                    ("curve", 1.0, 3.0)):
                    v = number(c, key, lo, hi)
                    if v is not None:
                        axis[key] = round(v, 2)
                if isinstance(c.get("invert"), bool):
                    axis["invert"] = c["invert"]
            elif op == "axis":
                source = c.get("source")
                if target not in PAD_AXES or source not in ("yaw", "pitch", "roll", "none"):
                    raise ValueError(f"cannot put head {source!r} on {target!r}")
                current = next((a for a in m["axes"] if a.get("target") == target), None)
                m["axes"] = [a for a in m["axes"] if a.get("target") != target]
                if source != "none":
                    new = dict(current or {"deadzone": config.AXIS_DEADZONE, "curve": config.AXIS_GAMMA, "invert": False})
                    new.update(source=source, target=target)
                    if isinstance(c.get("invert"), bool):
                        new["invert"] = c["invert"]
                    m["axes"].append(new)
            elif op == "pause":
                if not gesture or not need_gesture(gesture):
                    raise ValueError(f"cannot pause with {gesture!r}")
                hold = number(c, "hold_ms", 1000, 4000)
                m["pause"] = {"gesture": gesture, "hold_ms": int(hold) if hold else (m.get("pause") or {}).get("hold_ms", config.PAUSE_HOLD_MS)}
            else:
                raise ValueError(f"unknown change {op!r}")
            applied.append(c)
        except (ValueError, TypeError) as e:
            skipped.append(f"Skipped a change: {e}")
    used = ({b.get("gesture") for b in m["buttons"]} | {t.get("source") for t in m["triggers"]}
            | {(m.get("pause") or {}).get("gesture")})
    m["gestures"] = {n: g for n, g in m["gestures"].items() if n in used}
    return m, applied, skipped


def mapping_diff(old: dict, new: dict, menu: dict) -> list[str]:
    """What changed, in plain words, worked out from the two mappings (not from what the model says it did)."""
    lines = []
    targets = list(PAD_AXES) + list(PAD_TRIGGERS) + list(PAD_BUTTONS)
    for t in targets:
        a, b = _binding_text(old, t, menu), _binding_text(new, t, menu)
        if a != b:
            lines.append(f"{t}: {a} → {b}")
    for name, g in (new.get("gestures") or {}).items():
        before = (old.get("gestures") or {}).get(name) or {}
        for key, word in (("on", "sensitivity"), ("min_hold_ms", "hold time")):
            if key in g and before.get(key) not in (None, g[key]) and name in (old.get("gestures") or {}):
                label = (menu.get(name) or {}).get("label", name)
                lines.append(f"{label} {word}: {before.get(key)} → {g[key]}")
    lx_old = next((a for a in old.get("axes") or [] if a.get("target") == "lx"), {})
    lx_new = next((a for a in new.get("axes") or [] if a.get("target") == "lx"), {})
    for key, word in (("gain", "steering sensitivity"), ("deadzone", "steering dead zone"), ("curve", "steering curve"),
                      ("invert", "steering inverted")):
        if lx_old and lx_new and lx_old.get(key, 1.0 if key == "gain" else None) != lx_new.get(key, 1.0 if key == "gain" else None):
            lines.append(f"{word}: {lx_old.get(key, 1.0 if key == 'gain' else '-')} → {lx_new.get(key)}")
    if (old.get("pause") or {}) != (new.get("pause") or {}):
        lines.append(f"pause: {(old.get('pause') or {}).get('gesture')} → {(new.get('pause') or {}).get('gesture')}")
    return lines


def _captain_errors(m: dict, calib: Calibration, learned: list[str], has_breath: bool) -> list[str]:
    """Structural checks only: the player may choose a weak expression or leave a button empty on purpose."""
    from helm.mapping import Mapper
    errors = profiles.validate_mapping(m, dataclasses.replace(calib, reliable=list(BLENDSHAPE_NAMES)), learned, has_breath)
    if not errors:
        try:
            Mapper(m)
        except (ValueError, TypeError, AttributeError) as e:
            errors = [f"{type(e).__name__}: {e}"]
    return errors


def _captain_prompt(request: str, mapping: dict, calib: Calibration, learned: list[str], has_breath: bool,
                    game: str, stats: dict | None, menu: dict) -> str:
    controls = game_controls(game)
    known = "error" not in controls
    report = player_report(calib, learned, has_breath, stats)
    lines = [f"Player request: {request}", "", f"Game: {game}"]
    if known:
        lines += ["Its controls (target, action, held or tapped, how often):"]
        lines += [f"- {a.get('target')}: {a.get('name')} ({a.get('kind')}, {a.get('frequency')})"
                  for a in controls.get("actions", []) if isinstance(a, dict)]
    else:
        lines.append("Helm has no table for this game: use what you know of its default Xbox controller layout.")
    lines += ["", "Gestures this player can use (name: what they do; usable or weak):"]
    lines += [f"- {n}: {g['label']} ({'usable' if g.get('usable') else 'weak'}, {g['definition'].get('kind')})"
              for n, g in menu.items()]
    head = report.get("head_range_degrees", {}).get("yaw", {})
    lines += ["", f"Head turn for full steering: {head.get('negative')}° left, {head.get('positive')}° right "
              f"(calibration: {calib.mode}). Breath sensor: {'connected' if has_breath else 'not connected'}."]
    lines += ["", "Current mapping:"]
    targets = list(PAD_AXES) + list(PAD_TRIGGERS) + list(PAD_BUTTONS)
    lines += [f"- {t}: {_binding_text(mapping, t, menu)}" for t in targets if _binding_text(mapping, t, menu) != "nothing"]
    lx = next((a for a in mapping.get("axes") or [] if a.get("target") == "lx"), None)
    if lx:
        lines.append(f"- steering: gain {lx.get('gain', 1.0)}, deadzone {lx.get('deadzone')}, curve {lx.get('curve')}, "
                     f"invert {lx.get('invert', False)}")
    for name, g in (mapping.get("gestures") or {}).items():
        if "on" in g:
            lines.append(f"- {name} thresholds: on {g['on']}, off {g.get('off')}, hold {g.get('min_hold_ms', config.TRIGGER_MIN_HOLD_MS)} ms")
    pause = mapping.get("pause") or {}
    if pause.get("gesture"):
        lines.append(f"- pause: {pause['gesture']} held {pause.get('hold_ms')} ms")
    if stats and stats.get("gestures"):
        lines += ["", f"This session ({stats.get('active_s', 0)} s of play), per gesture: fires, near-misses (almost "
                      "fired), fires per minute:"]
        lines += [f"- {n}: {s.get('fires')} fires, {s.get('near_misses')} near-misses, {s.get('fires_per_min')}/min"
                  for n, s in stats["gestures"].items()]
        for notice in stats.get("notices") or []:
            lines.append(f"- note: {notice}")
    return "\n".join(lines)


def _call_claude(exe: str, prompt: str, web: bool, timeout_s: float) -> dict:
    """One Claude Code call on the user's login. Returns the structured output or raises RuntimeError."""
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    model = os.environ.get("HELM_COACH_CLAUDE_MODEL", config.CAPTAIN_MODEL)
    cmd = [exe, "-p", "--output-format", "json", "--model", model, "--no-session-persistence", "--effort", os.environ.get("HELM_CAPTAIN_EFFORT", config.CAPTAIN_EFFORT),
           "--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands",
           "--tools", "WebSearch,WebFetch" if web else "", "--system-prompt", CAPTAIN_SYSTEM,
           "--json-schema", json.dumps(CAPTAIN_SCHEMA)]
    if web:
        cmd += ["--allowedTools", "WebSearch,WebFetch"]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=timeout_s,
                              env=env, cwd=tempfile.gettempdir(), creationflags=flags)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Claude took longer than {timeout_s:.0f} s")
    try:
        data = json.loads(proc.stdout or "{}")
    except ValueError:
        data = {}
    out = data.get("structured_output") if isinstance(data, dict) else None
    if data.get("is_error") or not isinstance(out, dict) or not isinstance(out.get("changes"), list):
        text = f"{data.get('result') or ''} {proc.stderr or ''}".strip()
        if "login" in text.lower() or "log in" in text.lower() or "/login" in text:
            raise RuntimeError("Claude Code is not logged in (run `claude` once and log in)")
        raise RuntimeError(f"Claude Code failed: {_short_reason(text) or 'no answer'}")
    return out


def ask_captain(request: str, mapping: dict, calib: Calibration, learned: list[str], has_breath: bool,
                game: str, stats: dict | None = None, on_step=None, kind: str = "ask") -> dict:
    """Ask the Captain to change the current mapping. Returns {"mapping", "changes": [{"change", "reason"}],
    "summary", "backend": "claude"|"offline", "offline_reason", "elapsed_s"}. Never raises.
    kind "build" (set me up for `game`) and "review" (this session) fall back to the offline coach without Claude."""
    started = time.monotonic()
    step = on_step or (lambda text: None)
    menu = _gesture_menu(calib, learned, has_breath, game)
    base = copy.deepcopy(mapping)
    if kind == "build" and base.get("game") != game:  # another game: start from its defaults, keep steering settings
        fresh = profiles.default_mapping(game)
        lx = next((a for a in base.get("axes") or [] if a.get("target") == "lx"), None)
        for a in fresh.get("axes") or []:
            if lx and a.get("target") == "lx":
                a.update({k: lx[k] for k in ("gain", "deadzone", "curve", "invert") if k in lx})
        fresh["player"], fresh["game"] = calib.player, game
        base = fresh

    def result(m: dict, changes: list[dict], summary: str, backend: str, reason: str = "") -> dict:
        elapsed = round(time.monotonic() - started, 1)
        step(f"Done in {elapsed} s" if backend == "claude" else f"Captain offline: {reason}")
        return {"mapping": m, "changes": changes, "summary": summary, "backend": backend, "offline_reason": reason,
                "elapsed_s": elapsed, "rationale": [summary] if summary else []}

    def offline(reason: str) -> dict:
        if kind == "build":
            m, lines = _offline(game, calib, learned, has_breath)
            lx = next((a for a in mapping.get("axes") or [] if a.get("target") == "lx"), None)
            for a in m.get("axes") or []:
                if lx and a.get("target") == "lx":
                    a.update({k: lx[k] for k in ("gain", "deadzone", "curve", "invert") if k in lx})
            return result(m, [{"change": d, "reason": "offline coach"} for d in mapping_diff(mapping, m, menu)],
                          "Built without the AI: the default layout filtered to your moves.", "offline", reason)
        if kind == "review":
            m, notes = offline_review(base, stats or {}, calib, learned, has_breath)
            return result(m, [{"change": n, "reason": "offline coach"} for n in notes],
                          "Reviewed without the AI: small threshold changes from your session.", "offline", reason)
        return result(base, [], "", "offline", reason)

    _load_env()
    if (os.environ.get("HELM_COACH_BACKEND") or config.COACH_BACKEND).lower() == "offline":
        return offline("the Captain is set to offline")
    exe = find_claude()
    if not exe:
        return offline("Claude Code was not found (looked on PATH and in the usual install folders). Install it "
                       "and run `claude` once to log in")
    web = "error" in game_controls(game)
    step(f"Reading {game}'s controls and your moves" if not web else f"Looking up {game}'s controls")
    prompt = _captain_prompt(request, base, calib, learned, has_breath, game, stats, menu)
    deadline = started + config.CAPTAIN_TIMEOUT_S * (2 if web else 1)
    try:
        step("Asking Claude")
        try:
            out = _call_claude(exe, prompt, web, min(deadline - time.monotonic(), config.CAPTAIN_TRY_S * (2 if web else 1)))
        except RuntimeError as e:
            if "longer than" not in str(e) or deadline - time.monotonic() < 8:
                raise
            step("Claude is slow right now; asking again")
            out = _call_claude(exe, prompt, web, deadline - time.monotonic())
        step(f"Claude proposed {len(out['changes'])} change{'s' if len(out['changes']) != 1 else ''}; checking them")
        new, applied, skipped = apply_changes(base, out["changes"], menu)
        errors = _captain_errors(new, calib, learned, has_breath)
        if errors and deadline - time.monotonic() > 5:
            step(f"Fixing {len(errors)} problem{'s' if len(errors) != 1 else ''}")
            retry = (prompt + "\n\nYour previous changes:\n" + json.dumps(out["changes"]) + "\n\nApplied to the mapping "
                     "they gave these errors; return a corrected list of changes:\n- " + "\n- ".join(errors))
            out = _call_claude(exe, retry, web, deadline - time.monotonic())
            new, applied, skipped = apply_changes(base, out["changes"], menu)
            errors = _captain_errors(new, calib, learned, has_breath)
        if errors:
            raise RuntimeError("its changes still did not fit: " + errors[0])
    except RuntimeError as e:
        log.warning("captain: %s", e)
        return offline(str(e))
    new["player"], new["game"] = calib.player, game
    changes = _explained_changes(mapping, base, applied, menu) + [{"change": "", "reason": s} for s in skipped]
    return result(new, changes, str(out.get("summary", "")), "claude")


def _explained_changes(original: dict, base: dict, applied: list[dict], menu: dict) -> list[dict]:
    """Each applied change's effect (worked out from the mappings) with its own reason. Effects of starting from
    another game's defaults come first, without a reason of their own."""
    out = [{"change": d, "reason": "the new game's default layout"} for d in mapping_diff(original, base, menu)]
    current = base
    for c in applied:
        nxt, _, _ = apply_changes(current, [c], menu)
        lines = mapping_diff(current, nxt, menu)
        out += [{"change": d, "reason": str(c.get("reason", "")) if i == 0 else ""} for i, d in enumerate(lines)]
        current = nxt
    return out
