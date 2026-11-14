# OWNER: P1
"""Coach agent: build a mapping for this player and game, then review a session (docs/SPEC.md section 11).

The agent runs on LangChain deepagents with the model named by HELM_COACH_MODEL (a provider:model string,
default anthropic:claude-opus-5-5) plus that provider's API key. It sees a game name, gesture names and
numbers, never images. With no key, no network, a failure or a timeout, both functions fall back to an
offline path that needs nothing: the default mapping filtered to the player's reliable gestures, and a
rule-based review. Both run on a worker thread (Runtime.coach_build / coach_review), never the pipeline.
"""
import copy
import json
import logging
import os
import threading
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
use "auto": {"rt": 1.0}, or a breath toggle when breath is available.
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
              | {"kind": "learned", "on": 0.7, "off": 0.5} | {"kind": "breath"}},
 "buttons": [{"gesture": "<name>", "target": "<button or lt/rt>", "mode": "tap"|"hold"|"toggle"}],
 "auto": {"rt": 1.0},
 "pause": {"gesture": "<name>", "hold_ms": 2000}}
A learned gesture's name must be one of the player's learned gestures. A breath gesture's name is one of \
soft_sip, hard_sip, soft_puff, hard_puff and needs a breath sensor. Keep the pause gesture as eyes closed \
(eyeBlinkLeft + eyeBlinkRight, combine "min") held 1000 ms unless the report says the eyes are unreliable. \
"on" must be greater than "off", both in (0, 1)."""


# ------------------------------------------------------------------ data the tools expose

def game_controls(game: str) -> dict:
    """The game's entry in games.json, or an error dict listing the known games."""
    games = json.loads(_GAMES_PATH.read_text())
    if game in games:
        return games[game]
    lower = {g.lower(): g for g in games}
    if game.lower() in lower:
        return games[lower[game.lower()]]
    return {"error": f"unknown game {game!r}", "known_games": sorted(games)}


def player_report(calib: Calibration, learned: list[str], has_breath: bool, stats: dict | None = None) -> dict:
    """What the player can do, as plain numbers. No images, no raw frames."""
    expressions = []
    for name in calib.reliable:
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
    reliable = set(calib.reliable)
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
        else:
            errors.append(f"gesture {name!r} has unknown kind {kind!r}")
        if isinstance(g, dict) and kind in ("blendshape", "learned"):
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
    return errors


# ------------------------------------------------------------------ offline path

def offline_mapping(game: str, calib: Calibration, learned: list[str], has_breath: bool) -> dict:
    """The default mapping for the game, with everything this player cannot do removed. Always valid."""
    m = copy.deepcopy(profiles.default_mapping(game))
    m["player"], m["game"] = calib.player, game
    gestures = m.get("gestures", {})
    reliable = set(calib.reliable)

    def usable(g: dict, name: str) -> bool:
        kind = g.get("kind")
        if kind == "blendshape":
            return bool(g.get("sources")) and all(s in reliable for s in g["sources"])
        if kind == "learned":
            return name in learned
        if kind == "breath":
            return has_breath and name in BREATH_EVENTS
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
    if check(m, calib, learned, has_breath):
        m = _minimal_mapping(game, calib)              # last resort: steer and pause only
    return m


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


def _model_name() -> str:
    return os.environ.get("HELM_COACH_MODEL", config.COACH_DEFAULT_MODEL)


def _has_credentials(model: str) -> bool:
    provider = model.split(":", 1)[0] if ":" in model else ""
    keys = {"anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"), "openai": ("OPENAI_API_KEY",),
            "google_genai": ("GOOGLE_API_KEY", "GEMINI_API_KEY")}.get(provider)
    return keys is None or any(os.environ.get(k) for k in keys)   # unknown providers: let the agent try


def _run_agent(session: _Session, task: str) -> tuple[dict, list[str]] | None:
    """Run the deep agent with a time limit. Returns (mapping, reasons) or None on any failure."""
    model = _model_name()
    if not _has_credentials(model):
        log.info("coach: no API key for %s, using the offline path", model)
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
        return None
    if "error" in outcome:
        log.warning("coach: agent failed (%s), using the offline path", outcome["error"])
    return session.submitted


# ------------------------------------------------------------------ public interface

def build_mapping(game: str, calib: Calibration, learned: list[str], has_breath: bool) -> dict:
    """Return {"mapping": <valid mapping dict>, "rationale": [str, ...]}."""
    session = _Session(game, calib, learned, has_breath)
    task = (f"Build the best mapping for player {calib.player!r} playing {game!r}. "
            "Read the controls and the player report, plan, check, fix, and submit.")
    try:
        result = _run_agent(session, task)
    except Exception as e:
        log.warning("coach: %s, using the offline path", e)
        result = None
    if result is not None:
        return {"mapping": result[0], "rationale": result[1]}
    return {"mapping": offline_mapping(game, calib, learned, has_breath), "rationale": ["offline default"]}


def review_session(mapping: dict, stats: dict, calib: Calibration, learned: list[str], has_breath: bool) -> dict:
    """Return {"mapping": <valid mapping dict>, "changes": [str, ...]}."""
    game = mapping.get("game", "SuperTuxKart")
    session = _Session(game, calib, learned, has_breath, stats)
    task = ("Review this session and improve the current mapping with the smallest set of changes. "
            f"Current mapping: {json.dumps(mapping)}")
    try:
        result = _run_agent(session, task)
    except Exception as e:
        log.warning("coach: %s, using the offline path", e)
        result = None
    if result is not None:
        return {"mapping": result[0], "changes": result[1]}
    if check(mapping, calib, learned, has_breath):     # the current mapping no longer fits this player
        mapping = offline_mapping(game, calib, learned, has_breath)
    reviewed, changes = offline_review(mapping, stats, calib, learned, has_breath)
    return {"mapping": reviewed, "changes": changes or ["offline review: no changes needed"]}
