# OWNER: P3
"""Learned-gesture safety, persistence and timing through the real Mapper."""
import numpy as np
import pytest

from helm import config
from helm.contracts import BLENDSHAPE_NAMES, FEATURE_DIM, N_BLEND, Signals
from helm.gestures import GestureEngine, GestureModel
from helm.mapping import Mapper


def enrollment() -> GestureModel:
    rng = np.random.default_rng(84)
    model = GestureModel()
    for label, feature in [("a_smile", "mouthSmileLeft"), ("z_pucker", "mouthPucker")]:
        for _ in range(5):
            x = rng.normal(0, .01, (16, FEATURE_DIM)).astype(np.float32)
            x[:, BLENDSHAPE_NAMES.index(feature)] += .6
            model.add_take(label, x)
    model.add_negative(rng.normal(0, .01, (120, FEATURE_DIM)).astype(np.float32))
    model.fit()
    return model


def smile() -> np.ndarray:
    x = np.zeros(FEATURE_DIM, np.float32)
    x[BLENDSHAPE_NAMES.index("mouthSmileLeft")] = .6
    return x


def test_pose_breath_and_neutral_channel_cannot_change_prediction():
    model = enrollment()
    x = smile()
    expected = model.predict(x)
    assert max(expected, key=expected.get) == "a_smile"
    x[0] = 9
    x[N_BLEND:] = [1, -1, .8, 1]
    assert model.predict(x) == expected


def test_confident_extrapolation_is_rejected_and_bad_input_is_neutral():
    model = enrollment()
    assert model.predict(smile() * 20)["none"] == 1
    for x in [np.full(FEATURE_DIM, np.nan), np.full(FEATURE_DIM, np.inf), np.zeros(5)]:
        assert model.predict(x)["none"] == 1


def test_two_gestures_without_none_examples_are_not_armed():
    model = GestureModel()
    model.add_take("a", np.tile(smile(), (10, 1)))
    model.add_take("b", np.tile(smile() * .5, (10, 1)))
    assert model.fit() == {}
    assert model.predict(smile()) == {"a": 0, "b": 0, "none": 1}


def test_copy_delete_cannot_emit_removed_class_while_refitting():
    original = enrollment()
    modified = original.copy()
    modified.remove("a_smile")
    assert "a_smile" not in modified.predict(smile())
    assert modified.predict(smile())["none"] == 1
    assert original.predict(smile())["a_smile"] > .65


def test_legacy_profiles_load_and_new_profiles_preserve_training_settings(tmp_path, monkeypatch):
    model = enrollment()
    old = tmp_path / "old.npz"
    groups = model._groups()
    np.savez(old, frames=np.concatenate([x for _, x in groups]),
             labels=np.array([name for name, x in groups for _ in x]),
             groups=np.concatenate([np.repeat(i, len(x)) for i, (_, x) in enumerate(groups)]))
    loaded = GestureModel.load(str(old))
    assert loaded.predict(smile()) == pytest.approx(model.predict(smile()))
    path = str(tmp_path / "new.npz")
    model.save(path)
    monkeypatch.setattr(config, "LEARNED_C", 20)
    monkeypatch.setattr(config, "LEARNED_FEATURES_PER_CLASS", 1)
    assert GestureModel.load(path).predict(smile()) == pytest.approx(model.predict(smile()))


class Scores:
    def predict(self, delta):
        return {"none": float(delta[0]), "move": float(delta[1]), "other": float(delta[2])}


def signal(t, p=(.05, .95, 0), face=True):
    delta = np.zeros(FEATURE_DIM, np.float32)
    delta[:3] = p
    return Signals(seq=0, t_capture_ns=round(t * 1e9), t_infer_ns=round(t * 1e9), face=face,
                   axes={"yaw": 0, "pitch": 0, "roll": 0}, expr=np.zeros(N_BLEND), delta=delta, breath=0)


def engine(defs=None):
    return GestureEngine(None, defs or {"move": {"kind": "learned"}, "other": {"kind": "learned"}}, Scores())


def test_confirmation_release_and_competing_class_require_deliberate_new_hold():
    e = engine()
    assert e.update(signal(0))["move"] == 0
    assert e.update(signal(1/30))["move"] == 0
    assert e.update(signal(2/30))["move"] == 1
    # A competitor cannot fire while the old class is still releasing.
    assert e.update(signal(3/30, (.05, 0, .95))) == {"move": 1, "other": 0}
    assert e.update(signal(4/30, (.05, 0, .95)))["other"] == 0
    assert e.update(signal(5/30, (.05, 0, .95))) == {"move": 0, "other": 0}
    assert e.update(signal(6/30, (.05, 0, .95)))["other"] == 0
    assert e.update(signal(7/30, (.05, 0, .95)))["other"] == 0
    assert e.update(signal(8/30, (.05, 0, .95)))["other"] == 1


def test_one_frame_spike_face_loss_and_stale_samples_cannot_complete_hold():
    e = engine()
    assert e.update(signal(0))["move"] == 0
    assert e.update(signal(.03, (1, 0, 0)))["move"] == 0
    assert e.update(signal(.06))["move"] == 0
    assert e.update(signal(.09, face=False))["move"] == 0
    assert e.update(signal(.12))["move"] == 0
    assert e.update(signal(.5))["move"] == 0
    assert e.update(signal(.5))["move"] == 0


@pytest.mark.parametrize("mode", ["tap", "hold", "toggle"])
def test_mapper_consumes_qualified_learned_levels_without_second_debounce(mode):
    defs = {"move": {"kind": "learned", "on": .65, "off": .45}}
    e = engine(defs)
    mapper = Mapper({"gestures": defs, "buttons": [{"gesture": "move", "target": "A", "mode": mode}]})
    fired = []
    for i in range(10):
        s = signal(i/30)
        state = mapper.update(s, e.update(s), [], {})
        if state.fired:
            fired.append(i)
            assert "A" in state.buttons
    assert fired == [2]


def test_explicit_longer_mapping_hold_is_applied_once_in_engine():
    defs = {"move": {"kind": "learned", "min_hold_ms": 200}}
    e = engine(defs)
    mapper = Mapper({"gestures": defs, "buttons": [{"gesture": "move", "target": "A", "mode": "hold"}]})
    fires = []
    for i in range(12):
        s = signal(i/30)
        if mapper.update(s, e.update(s), [], {}).fired:
            fires.append(i)
    assert fires == [6]


@pytest.mark.parametrize("fps", [15, 30, 60])
def test_confirmation_uses_elapsed_time_instead_of_a_frame_count(fps):
    e = engine()
    first = None
    for i in range(fps):
        if e.update(signal(i/fps))["move"]:
            first = i/fps
            break
    assert first == pytest.approx(config.LEARNED_CONFIRM_S, abs=1/fps)
    assert first >= config.LEARNED_CONFIRM_S - 1e-9
