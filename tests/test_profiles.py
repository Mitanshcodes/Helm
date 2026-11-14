# OWNER: P2
"""Bootstrap checks for profiles.py. TODO(P2): save/load round trips and every validate_mapping rule."""
from helm import profiles

MAPPING_KEYS = {"player", "game", "axes", "triggers", "gestures", "buttons", "auto", "pause"}


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
