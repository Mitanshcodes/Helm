# OWNER: P3
"""Offline evaluation counts actual mapped activations, never raw positive frames."""
from types import SimpleNamespace

import numpy as np
import pytest

from eval.learned_replay import evaluate
from helm.contracts import FEATURE_DIM
from helm.gestures import GestureModel


def scoring_model():
    return SimpleNamespace(names=["move"], _fitted=SimpleNamespace(clf=True),
                           predict=lambda row: {"none": 1-float(row[1]), "move": float(row[1])})


def test_false_replay_counts_one_sustained_activation_and_its_timestamp():
    x = np.zeros((30, FEATURE_DIM), np.float32)
    x[:, 1] = .95
    result = evaluate(scoring_model(), x, np.arange(30)/30, np.ones(30, bool))
    assert result["duration_s"] == pytest.approx(1)
    assert result["false_events"] == 1
    assert result["false_per_minute"] == pytest.approx(60)
    assert result["events"] == [{"time_s": pytest.approx(2/30), "gesture": "move"}]


def test_no_face_does_not_count_a_positive_score_as_a_command():
    x = np.zeros((30, FEATURE_DIM), np.float32)
    x[:, 1] = .95
    result = evaluate(scoring_model(), x, np.arange(30)/30, np.zeros(30, bool))
    assert result["face_frames"] == result["false_events"] == 0


def test_invalid_or_untrained_input_cannot_report_a_successful_quiet_test():
    x = np.zeros((3, FEATURE_DIM), np.float32)
    with pytest.raises(ValueError, match="positive enrollment"):
        evaluate(GestureModel(), x, np.arange(3)/30, np.ones(3, bool))
    with pytest.raises(ValueError, match="strictly increasing"):
        evaluate(scoring_model(), x, np.zeros(3), np.ones(3, bool))
