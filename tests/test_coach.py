# OWNER: P1
"""coach.py: the offline path always returns a valid mapping; the agent's tools gate submissions; failures fall back."""
import json

import pytest

from helm import coach, profiles
from helm.calibration import default_calibration


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Tests never reach the network: no key means the offline path."""
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "HELM_COACH_MODEL"):
        monkeypatch.delenv(key, raising=False)


def full_calib(reliable=("browInnerUp", "jawOpen", "mouthSmileLeft", "mouthSmileRight")):
    c = default_calibration("sam", mode="full")
    c.reliable = list(c.reliable) + list(reliable)
    return c


def test_build_mapping_offline_is_valid():
    calib = default_calibration("guest")
    result = coach.build_mapping("SuperTuxKart", calib, learned=[], has_breath=False)
    assert result["rationale"] == ["offline default"]
    assert profiles.validate_mapping(result["mapping"], calib, [], False) == []
    assert coach.check(result["mapping"], calib, [], False) == []


def test_offline_keeps_only_reliable_gestures():
    unreliable = default_calibration("guest")                     # eyes only: brow_raise must be dropped
    m = coach.offline_mapping("SuperTuxKart", unreliable, [], False)
    assert "brow_raise" not in m["gestures"] and all(b["gesture"] in m["gestures"] for b in m["buttons"])
    assert m["pause"]["gesture"] in m["gestures"]
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
        raise RuntimeError("no network")

    monkeypatch.setattr(coach, "_run_agent", boom)
    calib = full_calib()
    result = coach.build_mapping("SuperTuxKart", calib, [], False)
    assert result["rationale"] == ["offline default"] and coach.check(result["mapping"], calib, [], False) == []


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
