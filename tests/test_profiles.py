# OWNER: P2
"""Bootstrap checks for profiles.py. TODO(P2): save/load round trips and every validate_mapping rule."""
from helm import profiles
from helm.contracts import AXES, N_BLEND, Calibration
from dataclasses import asdict
import json
import pytest

MAPPING_KEYS = {"player", "game", "axes", "triggers", "gestures", "buttons", "auto", "pause"}


def calibration_sample():
    return Calibration(player="sam", mode="full", neutral={axis: 0.0 for axis in AXES},
                       range={axis: (4.0, 15.0) for axis in AXES},
                       blend_neutral=[0.0] * N_BLEND, blend_peak={"jawOpen": 0.8},
                       reliable=["jawOpen"])


def test_calibration_json_round_trip_restores_contract_types():
    original = calibration_sample()
    decoded = json.loads(json.dumps(asdict(original)))
    restored = profiles._calibration_from_dict(decoded)
    assert restored == original
    assert all(isinstance(limits, tuple) for limits in restored.range.values())
    assert isinstance(restored.blend_neutral, list)
    assert isinstance(decoded["range"]["yaw"], list)
    restored.blend_neutral[0] = 1.0
    restored.reliable.append("browInnerUp")
    assert decoded["blend_neutral"][0] == 0.0
    assert decoded["reliable"] == ["jawOpen"]


@pytest.mark.parametrize("field,value", [
    ("range", {"yaw": [4, 15]}),
    ("range", {axis: [4] for axis in AXES}),
    ("blend_neutral", [0] * (N_BLEND - 1)),
])
def test_calibration_conversion_rejects_wrong_dimensions(field, value):
    decoded = asdict(calibration_sample())
    decoded[field] = value
    with pytest.raises(ValueError):
        profiles._calibration_from_dict(decoded)


def test_default_mapping_has_the_section_7_shape():
    for game in ("SuperTuxKart", "SomeGameWithNoDefaultFile"):
        m = profiles.default_mapping(game)
        assert set(m) == MAPPING_KEYS and m["game"] == game
        assert m["pause"]["gesture"] in m["gestures"]


def test_load_mapping_falls_back_to_default():
    assert profiles.load_mapping("nobody", "SuperTuxKart") == profiles.default_mapping("SuperTuxKart")


def test_interface():
    assert profiles.load_calibration("nobody") is None
    assert profiles.validate_mapping(profiles.default_mapping("SuperTuxKart")) == []
    assert profiles.gesture_model_path("sam").endswith("gestures.npz")
    assert isinstance(profiles.list_profiles(), dict)


@pytest.fixture
def mapping():
    """Independent, hardware-free mapping with the required safety pause."""
    return {
        "player": "sam", "game": "TestGame",
        "axes": [{"source": "yaw", "target": "lx"}],
        "triggers": [{"source": "breath_sip", "target": "lt"}],
        "gestures": {
            "jaw": {"kind": "blendshape", "sources": ["jawOpen"]},
            "eyes_closed": {"kind": "blendshape", "sources": ["eyeBlinkLeft", "eyeBlinkRight"]},
        },
        "buttons": [{"gesture": "jaw", "target": "A", "mode": "hold"}],
        "auto": {"rt": 1.0}, "pause": {"gesture": "eyes_closed"},
    }


def assert_error(errors, *parts):
    assert any(all(part in error for part in parts) for error in errors), errors


def test_validate_valid_mapping_preserves_input_and_allows_uncalibrated_pause(mapping):
    before = json.dumps(mapping, sort_keys=True)
    calib = calibration_sample()
    assert profiles.validate_mapping(mapping, calib=calib, learned=[]) == []
    assert json.dumps(mapping, sort_keys=True) == before
    assert calib.reliable == ["jawOpen"]


@pytest.mark.parametrize("key", sorted(MAPPING_KEYS))
def test_validate_required_keys(mapping, key):
    del mapping[key]
    assert_error(profiles.validate_mapping(mapping), key, "missing", "add")


@pytest.mark.parametrize("section,target", [
    ("axes", "A"), ("axes", "rt"), ("triggers", "lx"), ("triggers", "A"),
    ("buttons", "lx"), ("buttons", "Z"), ("auto", "Z"),
])
def test_validate_target_categories_give_owner_and_allowed_choices(mapping, section, target):
    if section == "auto":
        mapping[section] = {target: 1.0}
    else:
        mapping[section][0]["target"] = target
    errors = profiles.validate_mapping(mapping)
    assert_error(errors, section, target, "use one of")
    if section == "buttons":
        assert_error(errors, "jaw", target, "A, B, X, Y")


@pytest.mark.parametrize("section,targets", [
    ("axes", ("lx", "ly", "rx", "ry")),
    ("triggers", ("lt", "rt")),
    ("buttons", ("A", "B", "X", "Y", "LB", "RB", "START", "BACK", "DPAD_UP",
                 "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT", "LS", "RS", "lt", "rt")),
    ("auto", ("lx", "ly", "rx", "ry", "lt", "rt", "A", "B", "X", "Y", "LB", "RB",
              "START", "BACK", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT", "LS", "RS")),
])
def test_validate_accepts_every_legal_target(mapping, section, targets):
    for target in targets:
        mapping.update(axes=[], triggers=[], buttons=[], auto={})
        mapping[section] = ({target: 1.0} if section == "auto" else
                            [{"source": "yaw", "gesture": "jaw", "target": target, "mode": "tap"}])
        assert profiles.validate_mapping(mapping) == [], (section, target)


@pytest.mark.parametrize("first,second,target", [
    ("axes", "axes", "lx"), ("axes", "auto", "lx"),
    ("triggers", "triggers", "rt"), ("triggers", "buttons", "rt"),
    ("triggers", "auto", "rt"), ("buttons", "buttons", "A"),
    ("buttons", "auto", "A"),
])
def test_validate_duplicate_targets_across_all_drivers(mapping, first, second, target):
    mapping.update(axes=[], triggers=[], buttons=[], auto={})
    for section in (first, second):
        if section == "auto":
            mapping[section][target] = 1.0
        else:
            mapping[section].append({"source": "yaw", "gesture": "jaw", "target": target, "mode": "tap"})
    assert_error(profiles.validate_mapping(mapping), target, first, second, "remove one driver")


@pytest.mark.parametrize("section", ["buttons", "pause"])
def test_validate_referenced_gestures_must_be_defined(mapping, section):
    entry = mapping[section][0] if section == "buttons" else mapping[section]
    entry["gesture"] = "missing_smile"
    assert_error(profiles.validate_mapping(mapping), section, "missing_smile", "defined", "define")


@pytest.mark.parametrize("pause", [{}, {"gesture": ""}, {"gesture": "   "}, {"gesture": None}])
def test_validate_pause_gesture_is_required(mapping, pause):
    mapping["pause"] = pause
    assert_error(profiles.validate_mapping(mapping), "pause.gesture", "set it")


def test_validate_reliability_checks_every_source_even_unused_gestures(mapping):
    mapping["gestures"]["smile"] = {"kind": "blendshape", "sources": ["jawOpen", "mouthSmileRight"]}
    assert profiles.validate_mapping(mapping) == []
    errors = profiles.validate_mapping(mapping, calib=calibration_sample())
    assert len(errors) == 1
    assert_error(errors, "smile", "mouthSmileRight", "calib.reliable", "recalibrate")


def test_validate_pause_exemption_follows_selected_gesture(mapping):
    mapping["gestures"]["safety"] = mapping["gestures"].pop("eyes_closed")
    mapping["pause"]["gesture"] = "safety"
    assert profiles.validate_mapping(mapping, calib=calibration_sample()) == []
    mapping["gestures"]["eyes_closed"] = {"kind": "blendshape", "sources": ["eyeBlinkLeft"]}
    assert_error(profiles.validate_mapping(mapping, calib=calibration_sample()),
                 "eyes_closed", "eyeBlinkLeft", "calib.reliable")


@pytest.mark.parametrize("gesture", ["jaw", "eyes_closed"])
@pytest.mark.parametrize("with_calib", [False, True])
def test_validate_unknown_blendshape_even_for_pause_without_calibration(mapping, gesture, with_calib):
    mapping["gestures"][gesture]["sources"] = ["imaginaryMuscle"]
    calib = calibration_sample() if with_calib else None
    if calib is not None:
        calib.reliable.append("imaginaryMuscle")
    assert_error(profiles.validate_mapping(mapping, calib=calib), gesture, "imaginaryMuscle",
                 "replace", "contracts.BLENDSHAPE_NAMES")


def test_validate_learned_availability_only_when_supplied(mapping):
    mapping["gestures"]["left_smirk"] = {"kind": "learned"}
    assert profiles.validate_mapping(mapping) == []
    assert profiles.validate_mapping(mapping, learned=["left_smirk"]) == []
    assert_error(profiles.validate_mapping(mapping, learned=[]), "left_smirk", "train")
    assert_error(profiles.validate_mapping(mapping, learned=["other"]), "left_smirk", "train")


@pytest.mark.parametrize("event", ["soft_sip", "hard_sip", "soft_puff", "hard_puff"])
def test_validate_breath_requires_device_even_when_unused(mapping, event):
    mapping["gestures"][event] = {"kind": "breath"}
    assert_error(profiles.validate_mapping(mapping), event, "connect", "has_breath=True")
    assert profiles.validate_mapping(mapping, has_breath=True) == []


def test_validate_breath_name_must_be_a_contract_event(mapping):
    mapping["gestures"]["big_puff"] = {"kind": "breath"}
    assert_error(profiles.validate_mapping(mapping, has_breath=True),
                 "big_puff", "rename", "soft_sip, hard_sip, soft_puff, hard_puff")


@pytest.mark.parametrize("group,sources", [
    ("brow", ["browInnerUp", "browDownLeft"]),
    ("jaw", ["jawOpen", "jawLeft"]),
    ("mouth", ["mouthSmileLeft", "mouthPucker"]),
    ("eyes", ["eyeBlinkLeft", "eyeWideRight"]),
    ("cheek", ["cheekPuff", "cheekSquintRight"]),
    ("nose", ["noseSneerLeft", "noseSneerRight"]),
    ("breath", None),
])
def test_validate_hold_conflicts_derive_groups_from_sources(mapping, group, sources):
    names = ("soft_sip", "hard_puff") if group == "breath" else ("arbitrary_one", "arbitrary_two")
    for index, name in enumerate(names):
        mapping["gestures"][name] = ({"kind": "breath"} if sources is None else
                                      {"kind": "blendshape", "sources": [sources[index]]})
    mapping["buttons"] = [{"gesture": names[0], "target": "A", "mode": "hold"},
                          {"gesture": names[1], "target": "B", "mode": "hold"}]
    errors = profiles.validate_mapping(mapping, has_breath=True)
    assert len(errors) == 1
    assert_error(errors, *names, f"'{group}'", "change one mode")


def test_validate_composite_hold_occupies_all_source_groups(mapping):
    mapping["gestures"]["combo"] = {"kind": "blendshape", "sources": ["mouthSmileLeft", "jawOpen"]}
    mapping["buttons"].append({"gesture": "combo", "target": "B", "mode": "hold"})
    assert_error(profiles.validate_mapping(mapping), "jaw", "combo", "muscle group 'jaw'", "change")


@pytest.mark.parametrize("mode", ["tap", "toggle"])
def test_validate_only_hold_buttons_conflict(mapping, mode):
    mapping["buttons"].append({"gesture": "jaw", "target": "B", "mode": mode})
    assert profiles.validate_mapping(mapping) == []


def test_validate_hold_allows_distinct_groups_and_skips_learned(mapping):
    mapping["gestures"].update(
        mouth={"kind": "blendshape", "sources": ["mouthSmileLeft", "mouthSmileRight"]},
        learned_one={"kind": "learned"}, learned_two={"kind": "learned"},
    )
    mapping["buttons"].extend([
        {"gesture": "mouth", "target": "B", "mode": "hold"},
        {"gesture": "learned_one", "target": "X", "mode": "hold"},
        {"gesture": "learned_two", "target": "Y", "mode": "hold"},
    ])
    assert profiles.validate_mapping(mapping, learned=["learned_one", "learned_two"]) == []


def test_validate_collects_independent_actionable_errors(mapping):
    del mapping["player"]
    mapping["axes"][0]["target"] = "Z"
    mapping["buttons"][0]["gesture"] = "absent"
    mapping["pause"] = {}
    errors = profiles.validate_mapping(mapping)
    assert_error(errors, "player", "add")
    assert_error(errors, "Z", "use one of")
    assert_error(errors, "absent", "defined")
    assert_error(errors, "pause.gesture", "set it")


@pytest.mark.parametrize("key,value,description", [
    ("axes", None, "axes"), ("triggers", {}, "triggers"),
    ("buttons", [None], "buttons[0]"), ("auto", [], "auto"),
    ("pause", None, "pause"), ("gestures", [], "gestures"),
])
def test_validate_malformed_sections_return_repair_messages(mapping, key, value, description):
    mapping[key] = value
    assert_error(profiles.validate_mapping(mapping), description, "must be", "replace")


def test_validate_malformed_nested_values_return_errors(mapping):
    mapping["buttons"][0].update(gesture=[], target={})
    mapping["gestures"].update(broken=None, bad_sources={"kind": "blendshape", "sources": "jawOpen"})
    mapping["gestures"]["jaw"]["sources"] = [[]]
    errors = profiles.validate_mapping(mapping)
    assert_error(errors, "buttons[0]", "use one of")
    assert_error(errors, "buttons[0]", "choose a defined gesture")
    assert_error(errors, "broken", "provide")
    assert_error(errors, "bad_sources", "sources", "use names")
    assert_error(errors, "jaw", "unknown blendshape", "replace")


def test_validate_non_object_mapping_returns_repair_message():
    assert_error(profiles.validate_mapping(None), "mapping", "object", "provide")


# ---------------------------------------------------- committed profiles, persistence, listing
from pathlib import Path

_PROFILES = Path(__file__).resolve().parent.parent / "profiles"
# Mappings only: calibration.json is not a mapping, and `guest` is the throwaway player that a
# run creates and .gitignore excludes (docs/SPEC.md 7).
COMMITTED = sorted(f for f in _PROFILES.rglob("*.json")
                   if f.stem not in ("calibration", "breath") and f.parent.name != "guest")


def calibrated_player():
    """A full calibration whose reliable list is exactly the five expressions the calibration
    wizard actually measures (docs/SPEC.md 6.5)."""
    return Calibration(
        player="sam", mode="full", neutral={axis: 0.0 for axis in AXES},
        range={axis: (12.0, 12.0) for axis in AXES}, blend_neutral=[0.0] * N_BLEND,
        blend_peak={n: 0.7 for n in ("browInnerUp", "jawOpen", "mouthSmileLeft",
                                     "mouthSmileRight", "noseSneerLeft", "noseSneerRight")},
        reliable=["browInnerUp", "jawOpen", "mouthSmileLeft", "mouthSmileRight", "noseSneerLeft", "noseSneerRight"])


def test_there_are_committed_profiles_to_check():
    assert COMMITTED, "profiles/ has no committed mappings; the demo has nothing to load"


@pytest.mark.parametrize("path", COMMITTED, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_every_committed_mapping_validates(path):
    """The guard that catches a spec rule change silently invalidating the demo profiles."""
    mapping = json.loads(path.read_text())
    learned = [n for n, g in mapping["gestures"].items() if g.get("kind") == "learned"]
    has_breath = any(g.get("kind") == "breath" for g in mapping["gestures"].values())

    assert profiles.validate_mapping(mapping, learned=learned, has_breath=has_breath) == []
    assert profiles.validate_mapping(mapping, calib=calibrated_player(), learned=learned,
                                     has_breath=has_breath) == []


@pytest.mark.parametrize("path", COMMITTED, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_every_committed_mapping_declares_its_own_player_and_game(path):
    mapping = json.loads(path.read_text())
    assert mapping["game"] == path.stem
    assert mapping["player"] == path.parent.name


def test_judge_profile_maps_nothing_a_talking_stranger_could_trigger():
    """docs/SPEC.md 13: auto-accelerate, steering, one button. Nothing else."""
    mapping = json.loads((Path(__file__).resolve().parent.parent
                          / "profiles" / "judge" / "SuperTuxKart.json").read_text())
    assert mapping["auto"] == {"rt": 1.0}
    assert [b["target"] for b in mapping["buttons"]] == ["A"]
    assert mapping["triggers"] == []


def test_demo_profile_latches_throttle_and_brakes_on_sip():
    """docs/SPEC.md 13: nobody can hold a puff for a whole race, so throttle is latched."""
    mapping = json.loads((Path(__file__).resolve().parent.parent
                          / "profiles" / "demo" / "SuperTuxKart.json").read_text())
    throttle = next(b for b in mapping["buttons"] if b["target"] == "rt")
    assert throttle["gesture"] == "hard_puff" and throttle["mode"] == "toggle"
    assert any(t["source"] == "breath_sip" and t["target"] == "lt" for t in mapping["triggers"])


@pytest.fixture
def profile_root(tmp_path, monkeypatch):
    """Redirect profiles/ at a tmp dir: tests must never write into the committed folder."""
    monkeypatch.setattr(profiles, "_ROOT", tmp_path)
    return tmp_path


def test_calibration_save_load_round_trip(profile_root):
    original = calibrated_player()
    profiles.save_calibration(original)
    assert profiles.load_calibration("sam") == original
    assert all(isinstance(v, tuple) for v in profiles.load_calibration("sam").range.values())


def test_mapping_save_load_round_trip(profile_root):
    mapping = profiles.default_mapping("SuperTuxKart")
    mapping["player"] = "sam"
    profiles.save_mapping("sam", "SuperTuxKart", mapping)
    assert profiles.load_mapping("sam", "SuperTuxKart") == mapping


def test_missing_and_corrupt_profiles_fall_back_safely(profile_root):
    assert profiles.load_calibration("ghost") is None
    assert profiles.load_mapping("ghost", "SuperTuxKart") == profiles.default_mapping("SuperTuxKart")

    (profile_root / "broken").mkdir()
    (profile_root / "broken" / "calibration.json").write_text("{not json")
    (profile_root / "broken" / "SuperTuxKart.json").write_text("[]")
    assert profiles.load_calibration("broken") is None
    assert profiles.load_mapping("broken", "SuperTuxKart") == profiles.default_mapping("SuperTuxKart")


def test_save_is_atomic_and_leaves_no_temp_file(profile_root):
    profiles.save_calibration(calibrated_player())
    assert list((profile_root / "sam").glob("*.tmp")) == []


def test_list_profiles_skips_defaults_and_calibration_files(profile_root):
    profiles.save_calibration(calibrated_player())
    profiles.save_mapping("sam", "SuperTuxKart", profiles.default_mapping("SuperTuxKart"))
    profiles.save_mapping("sam", "Trackmania", profiles.default_mapping("Trackmania"))
    profiles.save_mapping("_defaults", "SuperTuxKart", profiles.default_mapping("SuperTuxKart"))
    assert profiles.list_profiles() == {"sam": ["SuperTuxKart", "Trackmania"]}


def test_list_profiles_on_the_real_folder_finds_the_demo_players():
    found = profiles.list_profiles()
    assert "_defaults" not in found
    for player in ("demo", "demo_webcam", "judge"):
        assert found.get(player) == ["SuperTuxKart"]


def test_guest_calibration_is_never_persisted(profile_root):
    """A judge must never inherit the previous judge's head range and neutral pose. Persisting
    `guest` would also make the suite depend on whether a smoke run happened to run first."""
    guest = calibrated_player()
    guest.player = profiles.GUEST_PLAYER
    profiles.save_calibration(guest)
    assert not (profile_root / profiles.GUEST_PLAYER).exists()
    assert profiles.load_calibration(profiles.GUEST_PLAYER) is None


def test_guest_calibration_left_on_disk_is_still_ignored(profile_root):
    """Stale files predate the rule, so loading must ignore them rather than trust them."""
    (profile_root / profiles.GUEST_PLAYER).mkdir()
    (profile_root / profiles.GUEST_PLAYER / "calibration.json").write_text(
        json.dumps(asdict(calibrated_player())))
    assert profiles.load_calibration(profiles.GUEST_PLAYER) is None


@pytest.mark.parametrize("player", sorted(profiles.SHARED_PLAYERS))
def test_shared_identities_never_persist_calibration(profile_root, player):
    """`guest` and `judge` are taken in turns by strangers (docs/SPEC.md 13). Persisting either
    means the second judge of the day silently inherits the first judge's calibration."""
    person = calibrated_player()
    person.player = player
    profiles.save_calibration(person)
    assert not (profile_root / player).exists()
    assert profiles.load_calibration(player) is None


def test_named_players_still_persist(profile_root):
    for player in ("demo", "demo_webcam", "sam"):
        person = calibrated_player()
        person.player = player
        profiles.save_calibration(person)
        assert profiles.load_calibration(player) == person


def test_shared_identities_keep_their_committed_mapping():
    """Only calibration is throwaway: the judge profile's mapping must still load."""
    assert profiles.load_mapping("judge", "SuperTuxKart")["auto"] == {"rt": 1.0}
