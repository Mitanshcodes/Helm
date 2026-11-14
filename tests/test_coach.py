# OWNER: P1
"""The offline path always returns a mapping that passes validate_mapping."""
from helm import coach, profiles
from helm.calibration import default_calibration


def test_build_mapping_offline_is_valid():
    calib = default_calibration("guest")
    result = coach.build_mapping("SuperTuxKart", calib, learned=[], has_breath=False)
    assert result["rationale"]
    assert profiles.validate_mapping(result["mapping"], calib, [], False) == []


def test_review_session_shape():
    calib = default_calibration("guest")
    mapping = profiles.default_mapping("SuperTuxKart")
    result = coach.review_session(mapping, {}, calib, learned=[], has_breath=False)
    assert set(result) == {"mapping", "changes"}
