# OWNER: P1
"""coach.py: the offline path always returns a valid mapping; the agent's tools gate submissions; failures fall back."""
import json

import pytest

from helm import coach, config, profiles
from helm.calibration import default_calibration


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Tests never reach the network: no key means the offline path."""
    monkeypatch.setattr(coach, "_env_loaded", True)               # never read the real .env
    monkeypatch.setattr(coach, "_claude_cli", lambda: None)       # never launch the real Claude Code
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "HELM_COACH_MODEL", "OPENAI_API_KEY",
                "HELM_COACH_BACKEND", "HELM_COACH_CLAUDE_MODEL"):
        monkeypatch.delenv(key, raising=False)


def test_model_choice_follows_the_keys(monkeypatch, tmp_path):
    assert not coach._has_credentials(coach._model_name())                 # no key: offline path
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert coach._model_name() == config.COACH_OPENAI_MODEL
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert coach._model_name() == config.COACH_DEFAULT_MODEL               # Claude first when both are set
    monkeypatch.setenv("HELM_COACH_MODEL", "openai:gpt-test")
    assert coach._model_name() == "openai:gpt-test"


def test_dotenv_is_read_once_and_does_not_override(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("# keys\nexport OPENAI_API_KEY='sk-from-file'\nHELM_COACH_MODEL=openai:gpt-file\n")
    monkeypatch.setattr(coach, "_ENV_PATH", env)
    monkeypatch.setattr(coach, "_env_loaded", False)
    monkeypatch.setenv("HELM_COACH_MODEL", "openai:already-set")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert coach._model_name() == "openai:already-set"
    import os
    assert os.environ["OPENAI_API_KEY"] == "sk-from-file"


def full_calib(reliable=("browInnerUp", "jawOpen", "mouthSmileLeft", "mouthSmileRight")):
    c = default_calibration("sam", mode="full")
    c.reliable = list(c.reliable) + list(reliable)
    return c


def test_build_mapping_offline_is_valid():
    calib = default_calibration("guest")
    learned = ["nod_up"]                                                     # full calibration trains this one
    result = coach.build_mapping("SuperTuxKart", calib, learned=learned, has_breath=False)
    assert result["rationale"][0].startswith("Offline coach") and "no API key" in result["rationale"][-1]
    assert {b["target"] for b in result["mapping"]["buttons"]} >= {"A", "B", "X", "Y"}
    assert result["mapping"]["auto"] == {"rt": 1.0}                        # accelerate is held all race
    assert profiles.validate_mapping(result["mapping"], calib, learned, False) == []
    assert coach.check(result["mapping"], calib, learned, False) == []


def test_offline_keeps_only_reliable_gestures():
    unreliable = full_calib(reliable=())                          # full calibration, eyes only: no buttons
    m = coach.offline_mapping("SuperTuxKart", unreliable, [], False)
    assert "brow_raise" not in m["gestures"] and m["buttons"] == []
    assert m["pause"]["gesture"] in m["gestures"] and coach.check(m, unreliable, [], False) == []
    assert any("unmapped" in line for line in coach.describe(m, "SuperTuxKart"))
    reliable = full_calib()
    m2 = coach.offline_mapping("SuperTuxKart", reliable, [], False)
    assert "brow_raise" in m2["gestures"] and coach.check(m2, reliable, [], False) == []


def test_offline_for_an_unknown_game_is_still_valid():
    calib = full_calib()
    m = coach.offline_mapping("NoSuchGame", calib, [], False)
    assert coach.check(m, calib, [], False) == [] and m["axes"]


def test_check_catches_what_the_coach_must_never_submit():
    calib = full_calib(reliable=("browInnerUp",))
    m = profiles.default_mapping("SuperTuxKart")
    m["gestures"]["pucker"] = {"kind": "blendshape", "sources": ["mouthPucker"], "on": 0.6, "off": 0.4}
    m["gestures"]["left_smirk"] = {"kind": "learned", "on": 0.7, "off": 0.5}
    m["gestures"]["hard_puff"] = {"kind": "breath"}
    m["buttons"] += [{"gesture": "pucker", "target": "A", "mode": "tap"},
                     {"gesture": "ghost", "target": "Q", "mode": "spin"}]
    errors = " | ".join(coach.check(m, calib, learned=[], has_breath=False))
    for expected in ("not reliable", "no learned gesture", "breath sensor", "'ghost'", "'Q'", "'spin'",
                     "more than one source"):
        assert expected in errors


def test_submit_mapping_only_accepts_valid_mappings():
    calib = full_calib()
    session = coach._Session("SuperTuxKart", calib, [], False)
    tools = {t.__name__: t for t in session.tools()}
    assert json.loads(tools["get_game_controls"]("SuperTuxKart"))["actions"]
    report = json.loads(tools["get_player_report"]())
    assert {e["blendshape"] for e in report["reliable_expressions"]} >= {"browInnerUp", "jawOpen"}
    assert "rejected" in tools["submit_mapping"]("{not json", ["x"])
    bad = profiles.default_mapping("SuperTuxKart")
    bad["pause"] = {}
    assert json.loads(tools["check_mapping"](json.dumps(bad)))
    assert "rejected" in tools["submit_mapping"](json.dumps(bad), ["x"]) and session.submitted is None
    good = coach.offline_mapping("SuperTuxKart", calib, [], False)
    assert json.loads(tools["check_mapping"](json.dumps(good))) == []
    assert tools["submit_mapping"](json.dumps(good), ["steer with yaw"]) == "accepted"
    assert session.submitted[1] == ["steer with yaw"]


def test_agent_result_is_used_when_submitted(monkeypatch):
    calib = full_calib()
    good = coach.offline_mapping("SuperTuxKart", calib, [], False)
    monkeypatch.setattr(coach, "_run_agent", lambda session, task: (good, ["brow raise fires items"]))
    result = coach.build_mapping("SuperTuxKart", calib, [], False)
    assert result == {"mapping": good, "rationale": ["brow raise fires items"]}


def test_agent_failure_falls_back(monkeypatch):
    def boom(session, task):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(coach, "_run_agent", boom)
    calib = full_calib()
    result = coach.build_mapping("SuperTuxKart", calib, [], False)
    assert result["rationale"][0].startswith("Offline coach")
    assert result["rationale"][-1] == "Coach offline: no connection to the model"
    assert coach.check(result["mapping"], calib, [], False) == []


def test_out_of_credits_is_reported_plainly():
    msg = "OpenAIRateLimitError: Error code: 429 - You have no credits remaining. Add credits to continue"
    assert coach._short_reason(msg) == "the API account is out of credits"
    assert coach._short_reason("AuthenticationError: 401 invalid api key") == "the API key was rejected"


def test_review_session_shape():
    calib = default_calibration("guest")
    mapping = profiles.default_mapping("SuperTuxKart")
    result = coach.review_session(mapping, {}, calib, learned=[], has_breath=False)
    assert set(result) == {"mapping", "changes"}
    assert coach.check(result["mapping"], calib, [], False) == []


def test_offline_review_tunes_thresholds():
    calib = full_calib()
    mapping = coach.offline_mapping("SuperTuxKart", calib, [], False)
    on = mapping["gestures"]["brow_raise"]["on"]
    near = {"gestures": {"brow_raise": {"fires": 1, "near_misses": 5, "fires_per_min": 0.5}}, "notices": []}
    result = coach.review_session(mapping, near, calib, [], False)
    assert result["mapping"]["gestures"]["brow_raise"]["on"] < on and "nearly fired" in result["changes"][0]
    noisy = {"gestures": {"brow_raise": {"fires": 40, "near_misses": 0, "fires_per_min": 12.0}}, "notices": []}
    result = coach.review_session(mapping, noisy, calib, [], False)
    assert result["mapping"]["gestures"]["brow_raise"]["on"] > on
    assert mapping["gestures"]["brow_raise"]["on"] == on                    # the input is not mutated


def test_deepagents_wiring_with_a_scripted_model(monkeypatch):
    """The real agent graph with a fake model: tools are offered, a bad submission is rejected, a good one used."""
    pytest.importorskip("deepagents")
    import langchain.chat_models
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    calib = full_calib()
    good = coach.offline_mapping("SuperTuxKart", calib, [], False)
    script = [
        [{"name": "get_game_controls", "args": {"game": "SuperTuxKart"}, "id": "1"}],
        [{"name": "get_player_report", "args": {}, "id": "2"}],
        [{"name": "submit_mapping", "args": {"mapping_json": "{}", "reasons": ["bad"]}, "id": "3"}],
        [{"name": "submit_mapping", "args": {"mapping_json": json.dumps(good), "reasons": ["yaw steers"]}, "id": "4"}],
    ]

    class Scripted(BaseChatModel):
        step: int = 0

        def bind_tools(self, tools, **kwargs):
            return self

        @property
        def _llm_type(self) -> str:
            return "scripted"

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            calls = script[self.step] if self.step < len(script) else []
            self.step += 1
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="" if calls else "done",
                                                                            tool_calls=calls))])

    model = Scripted()
    monkeypatch.setenv("HELM_COACH_MODEL", "fake:scripted")
    monkeypatch.setattr(langchain.chat_models, "init_chat_model", lambda name, **kw: model)
    result = coach.build_mapping("SuperTuxKart", calib, [], False)
    assert result["rationale"] == ["yaw steers"] and result["mapping"]["gestures"] == good["gestures"]
    assert model.step == 5


def test_every_face_button_is_filled_with_the_best_spare_gesture():
    """Smiles failed the check: B (nitro, held) gets the first learned move, X the next one (calibration's nod)."""
    calib = full_calib(reliable=("browInnerUp", "jawOpen"))
    calib.blend_peak = {"browInnerUp": 0.8, "jawOpen": 0.9}
    m = coach.offline_mapping("SuperTuxKart", calib, ["left_smirk", "nod_up"], False)
    by_target = {b["target"]: b for b in m["buttons"]}
    assert set(by_target) == {"A", "B", "X", "Y"}
    assert by_target["A"]["gesture"] == "brow_raise" and by_target["Y"]["gesture"] == "jaw_open"   # layout kept
    assert by_target["B"] == {"gesture": "left_smirk", "target": "B", "mode": "hold"}
    assert by_target["X"] == {"gesture": "nod_up", "target": "X", "mode": "tap"}
    assert len({b["gesture"] for b in m["buttons"]}) == 4
    assert coach.check(m, calib, ["left_smirk", "nod_up"], False) == []


def test_check_rejects_an_empty_face_button_while_a_gesture_is_spare():
    calib = default_calibration("guest", mode="quick")
    m = coach.offline_mapping("SuperTuxKart", calib, ["nod_up"], False)
    m["buttons"] = [b for b in m["buttons"] if b["target"] != "Y"]
    errors = coach.check(m, calib, ["nod_up"], False)
    assert any("face buttons Y are unmapped" in e and "jaw_open" in e for e in errors)


def test_review_fills_an_empty_button_instead_of_rebuilding():
    calib = default_calibration("guest", mode="quick")
    mapping = coach.offline_mapping("SuperTuxKart", calib, ["nod_up"], False)
    mapping["gestures"]["brow_raise"]["on"] = 0.7                          # a player's own tuning
    mapping["gestures"]["brow_raise"]["off"] = 0.5
    mapping["buttons"] = [b for b in mapping["buttons"] if b["target"] != "X"]
    result = coach.review_session(mapping, {"gestures": {}, "notices": []}, calib, ["nod_up"], False)
    assert {b["target"] for b in result["mapping"]["buttons"]} >= {"A", "B", "X", "Y"}
    assert result["mapping"]["gestures"]["brow_raise"]["on"] == 0.7        # tuning kept
    assert any(c.startswith("Mapped an empty button: X") for c in result["changes"])


def test_player_report_lists_usable_gestures_for_the_agent():
    report = coach.player_report(default_calibration("guest", mode="quick"), ["left_smirk"], False)
    names = [g["name"] for g in report["usable_gestures"]]
    assert names[0] == "left_smirk" and {"brow_raise", "smile", "jaw_open"} <= set(names)


class FakeClaude:
    """Stands in for subprocess.run of `claude -p`: replays scripted structured outputs, records the prompts."""

    def __init__(self, outputs):
        self.outputs, self.prompts, self.cmds, self.envs = list(outputs), [], [], []

    def __call__(self, cmd, input, env, **kwargs):
        import subprocess
        self.cmds.append(cmd)
        self.prompts.append(input)
        self.envs.append(env)
        out = self.outputs.pop(0)
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(out), stderr="")


def test_claude_code_on_the_subscription_fixes_its_errors(monkeypatch):
    calib = default_calibration("sam", mode="quick")
    good = coach.offline_mapping("SuperTuxKart", calib, ["nod_up"], False)
    bad = json.loads(json.dumps(good))
    bad["buttons"] = [b for b in bad["buttons"] if b["target"] != "Y"]            # leaves a face button empty
    fake = FakeClaude([
        {"is_error": False, "structured_output": {"mapping": bad, "reasons": ["first try"]}},
        {"is_error": False, "structured_output": {"mapping": good, "reasons": ["brow fires items"]}},
    ])
    monkeypatch.setattr(coach, "_claude_cli", lambda: "/usr/local/bin/claude")
    monkeypatch.setattr(coach.subprocess, "run", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-be-used")
    result = coach.build_mapping("SuperTuxKart", calib, ["nod_up"], False)
    assert result["rationale"] == ["brow fires items"] and coach.check(result["mapping"], calib, ["nod_up"], False) == []
    assert len(fake.prompts) == 2 and "face buttons Y are unmapped" in fake.prompts[1]
    assert "fire item" in fake.prompts[0] and "usable_gestures" in fake.prompts[0]
    assert all("ANTHROPIC_API_KEY" not in env for env in fake.envs)              # the login, never the key
    cmd = fake.cmds[0]
    assert cmd[cmd.index("--tools") + 1] == "WebSearch,WebFetch" and "--json-schema" in cmd


def test_unknown_game_asks_claude_to_look_up_the_controls(monkeypatch):
    calib = default_calibration("sam", mode="quick")
    mapping = coach.offline_mapping("NoSuchGame", calib, [], False)
    fake = FakeClaude([{"is_error": False, "structured_output": {
        "mapping": mapping, "reasons": ["jump on brow"], "controls": ["A: jump", "X: dash"]}}])
    monkeypatch.setattr(coach, "_claude_cli", lambda: "claude")
    monkeypatch.setattr(coach.subprocess, "run", fake)
    result = coach.build_mapping("NoSuchGame", calib, [], False)
    assert "Search the web" in fake.prompts[0]
    assert result["rationale"] == ["Controls found: A: jump; X: dash", "jump on brow"]


def test_claude_not_logged_in_falls_back_offline(monkeypatch):
    fake = FakeClaude([{"is_error": True, "result": "Not logged in · Please run /login"}])
    monkeypatch.setattr(coach, "_claude_cli", lambda: "claude")
    monkeypatch.setattr(coach.subprocess, "run", fake)
    calib = default_calibration("sam", mode="quick")
    result = coach.build_mapping("SuperTuxKart", calib, [], False)
    assert result["rationale"][0].startswith("Offline coach") and "not logged in" in result["rationale"][-1]
    assert coach.check(result["mapping"], calib, [], False) == []
