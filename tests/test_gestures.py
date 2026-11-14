# OWNER: P3
"""gestures.py: synthetic clusters separate, "none" suppresses, steering does not hide a gesture, save/load."""
import numpy as np
import pytest

from helm import config
from helm.contracts import BLENDSHAPE_NAMES, FEATURE_DIM, N_BLEND, FrameFeatures, Progress, Signals
from helm.filters import Normalizer
from helm.gestures import GestureEngine, GestureModel, TakeRecorder
from helm.profiles import default_mapping

YAW = N_BLEND                                      # index of yaw in the 56-value delta
B = {name: i for i, name in enumerate(BLENDSHAPE_NAMES)}
rng = np.random.default_rng(0)


def frames(n: int, noise: float = 0.02, yaw: float = 0.0, **blend: float) -> np.ndarray:
    x = rng.normal(0.0, noise, (n, FEATURE_DIM)).astype(np.float32)
    for name, value in blend.items():
        x[:, B[name]] += value
    x[:, YAW] += yaw
    return x


def talking(n: int) -> np.ndarray:
    """Negatives: jaw moving, both smile corners together, looking around."""
    x = frames(n)
    x[:, B["jawOpen"]] += rng.uniform(0.0, 0.5, n)
    both = rng.uniform(0.0, 0.4, n)
    x[:, B["mouthSmileLeft"]] += both
    x[:, B["mouthSmileRight"]] += both
    x[:, YAW] += rng.uniform(-1.0, 1.0, n)
    return x


def trained() -> GestureModel:
    m = GestureModel()
    for _ in range(5):
        m.add_take("left_smirk", frames(18, mouthSmileLeft=0.6))
        m.add_take("pucker", frames(18, mouthPucker=0.6))
    m.add_negative(talking(450))
    m.add_negative(frames(60))                     # relaxed rest frames
    return m


def signals(delta: np.ndarray, face: bool = True, expr: np.ndarray | None = None) -> Signals:
    return Signals(seq=0, t_capture_ns=0, t_infer_ns=0, face=face, axes={"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
                   expr=np.zeros(N_BLEND, np.float32) if expr is None else expr, delta=delta, breath=0.0)


def best(m: GestureModel, x: np.ndarray) -> str:
    p = m.predict(x)
    return max(p, key=p.get)


def test_synthetic_clusters_separate():
    m = trained()
    accuracy = m.fit()
    assert m.names == ["left_smirk", "pucker"]
    assert accuracy["left_smirk"] >= config.MIN_TAKE_OUT_ACCURACY and accuracy["pucker"] >= 0.85
    assert accuracy["none"] >= 0.85
    assert best(m, frames(1, mouthSmileLeft=0.6)[0]) == "left_smirk"
    assert best(m, frames(1, mouthPucker=0.6)[0]) == "pucker"
    assert best(m, frames(1)[0]) == "none"
    p = m.predict(frames(1)[0])
    assert set(p) == {"left_smirk", "pucker", "none"} and sum(p.values()) == pytest.approx(1.0)


def test_steering_does_not_hide_a_gesture():
    """Takes are recorded facing the screen; in the game the head is turned to steer."""
    m = trained()
    m.fit()
    hits = sum(best(m, x) == "left_smirk" for x in frames(50, yaw=0.7, mouthSmileLeft=0.6))
    assert hits >= 45


def test_engine_learned_fires_on_demand_but_not_while_talking():
    m = trained()
    m.fit()
    defs = {"left_smirk": {"kind": "learned", "on": 0.7, "off": 0.5}}
    engine = GestureEngine(None, defs, m)
    talk = [engine.update(signals(x))["left_smirk"] for x in talking(200)]
    assert max(talk) < 0.7                                              # never reaches "on" while talking
    smirk = [engine.update(signals(x))["left_smirk"] for x in frames(10, mouthSmileLeft=0.6)]
    assert smirk[-1] >= 0.7


def test_none_suppresses_and_face_loss_resets():
    m = trained()
    m.fit()
    engine = GestureEngine(None, {"left_smirk": {"kind": "learned"}}, m)
    smirk = frames(1, mouthSmileLeft=0.6)[0]
    for _ in range(config.LEARNED_SMOOTH_FRAMES):
        level = engine.update(signals(smirk))["left_smirk"]
    assert level > 0.9
    for _ in range(config.LEARNED_SMOOTH_FRAMES // 2):                  # a few neutral frames: P(none) >= 0.3
        level = engine.update(signals(frames(1)[0]))["left_smirk"]
    assert level == 0.0
    assert engine.update(signals(smirk, face=False))["left_smirk"] == 0.0
    assert engine.update(signals(smirk))["left_smirk"] > 0.9            # no stale history after the loss


def test_engine_blendshape_combine_and_breath():
    defs = dict(default_mapping("SuperTuxKart")["gestures"],
                smile={"kind": "blendshape", "sources": ["mouthSmileLeft", "mouthSmileRight"]},
                hard_puff={"kind": "breath"}, left_smirk={"kind": "learned", "on": 0.7, "off": 0.5})
    expr = np.zeros(N_BLEND, np.float32)
    expr[B["eyeBlinkLeft"]], expr[B["eyeBlinkRight"]] = 0.9, 0.2
    expr[B["mouthSmileLeft"]], expr[B["browInnerUp"]] = 0.7, 0.5
    act = GestureEngine(None, defs, None).update(signals(np.zeros(FEATURE_DIM, np.float32), expr=expr))
    assert set(act) == set(defs) - {"hard_puff"}
    assert act["eyes_closed"] == pytest.approx(0.2)                     # combine: min (both eyes)
    assert act["smile"] == pytest.approx(0.7)                           # default combine: max
    assert act["brow_raise"] == pytest.approx(0.5)
    assert act["left_smirk"] == 0.0                                     # no model yet
    lost = GestureEngine(None, defs, None).update(signals(np.zeros(FEATURE_DIM, np.float32), face=False, expr=expr))
    assert all(v == 0.0 for v in lost.values())


def test_single_class_and_empty_models_say_none():
    m = GestureModel()
    assert m.fit() == {} and m.predict(np.zeros(FEATURE_DIM))["none"] == 1.0
    m.add_take("left_smirk", frames(10, mouthSmileLeft=0.6))
    m.fit()
    assert m.predict(frames(1, mouthSmileLeft=0.6)[0]) == {"left_smirk": 0.0, "none": 1.0}
    with pytest.raises(ValueError):
        m.add_take("x", np.zeros((3, 5)))


def test_remove_and_save_load_round_trip(tmp_path):
    m = trained()
    m.fit()
    path = str(tmp_path / "sam" / "gestures.npz")
    m.save(path)
    loaded = GestureModel.load(path)
    assert loaded.names == m.names
    for x in (frames(1, mouthSmileLeft=0.6)[0], frames(1, mouthPucker=0.6)[0], talking(1)[0]):
        assert loaded.predict(x) == pytest.approx(m.predict(x))
    loaded.remove("pucker")
    loaded.fit()
    assert loaded.names == ["left_smirk"] and "pucker" not in loaded.predict(frames(1)[0])


def _run_recorder(rec: TakeRecorder, delta_at, fps: float = 30.0, lose_face=None) -> list[Progress]:
    progs, t = [], 0.0
    while True:
        face = not (lose_face and lose_face[0] <= t < lose_face[1])
        p = rec.feed(signals(delta_at(t, progs[-1] if progs else None), face=face), t)
        progs.append(p)
        if p.done:
            return progs
        t += 1 / fps
        assert t < 60


def test_take_recorder_keeps_the_held_frames():
    rec = TakeRecorder("left_smirk", takes=5)
    take_s = config.TAKE_READY_S + config.TAKE_HOLD_S + config.TAKE_RELAX_S

    def delta(t, _):                               # smirks a bit late and ramps up during the hold window
        phase = t % take_s - config.TAKE_READY_S
        level = 0.6 * min(1.0, max(0.0, (phase - 0.2) / 0.3)) if 0.0 <= phase < config.TAKE_HOLD_S else 0.0
        return frames(1, noise=0.0, mouthSmileLeft=level)[0]

    progs = _run_recorder(rec, delta)
    assert [s for s in dict.fromkeys(p.step for p in progs if p.active)] == [f"take_{k}" for k in range(1, 6)]
    assert "now" in progs[40].prompt and len(progs) / 30.0 == pytest.approx(5 * take_s, abs=0.2)
    takes = rec.result()
    assert len(takes) == 5 and len(rec.rest) == 5
    for take in takes:
        assert take.shape[1] == FEATURE_DIM
        assert len(take) == pytest.approx(config.TAKE_TOP_FRACTION * 30 * config.TAKE_HOLD_S, abs=2)
        assert take[:, B["mouthSmileLeft"]].min() > 0.2                 # the slow start was dropped
    assert all(np.abs(rest).max() == 0.0 for rest in rec.rest)          # relaxed face only


def test_negatives_recorder_and_face_loss():
    rec = TakeRecorder(None)
    progs = _run_recorder(rec, lambda t, _: talking(1)[0], lose_face=(2.0, 3.0))
    assert {p.step for p in progs if p.active} == {"negatives"}
    assert any("can't see" in p.prompt for p in progs)
    (negatives,) = rec.result()
    assert len(negatives) == pytest.approx(30 * config.NEGATIVE_S, abs=2)
    assert len(progs) / 30.0 == pytest.approx(config.NEGATIVE_S + 1.0, abs=0.2)   # the timer paused for 1 s


def test_normalizer_signals_feed_the_recorder():
    s = Normalizer().update(FrameFeatures(seq=0, t_capture_ns=0, t_infer_ns=0, face=True))
    assert isinstance(TakeRecorder("x").feed(s, 0.0), Progress)
