# OWNER: P1
"""calibration.py: step timing, face-lost pause, measured range and its floor, peaks and the reliable flag."""
import math

import numpy as np
import pytest

from helm import config
from helm.calibration import Calibrator, default_calibration, top_peaks
from helm.contracts import AXES, BLENDSHAPE_NAMES, N_BLEND, Calibration, FrameFeatures, Progress

FPS = 30


def test_default_calibration():
    c = default_calibration("guest")
    assert c.mode == "default" and set(c.neutral) == set(AXES) and len(c.blend_neutral) == N_BLEND
    assert all(lo > 0 and hi > 0 for lo, hi in c.range.values())
    assert set(config.ASSUMED_RELIABLE) <= set(c.reliable)


def test_top_peaks():
    t = np.arange(0, 4, 1 / FPS)
    v = 0.6 * np.clip(np.sin(2 * math.pi * t * 0.75), 0, None)       # three bumps in 4 s
    v[np.argmin(abs(t - 1 / 3))] = 0.7                               # one is higher
    peaks = top_peaks(v, t)
    assert len(peaks) == 3 and peaks[0] == pytest.approx(0.7)
    assert top_peaks(np.zeros(0), np.zeros(0)) == []
    assert len(top_peaks(np.array([0.1, 0.5, 0.1]), np.array([0.0, 0.1, 0.2]))) == 1


class Player:
    """Synthetic player that follows the calibration prompts."""

    def __init__(self, yaw_left=20.0, yaw_right=25.0, up=12.0, down=2.0, weak=("mouthPucker",), neutral_yaw=3.0,
                 react_s=0.0):
        self.yaw_left, self.yaw_right, self.up, self.down = yaw_left, yaw_right, up, down
        self.weak, self.neutral_yaw = weak, neutral_yaw
        self.react_s = react_s                     # seconds into a step before the player starts moving
        self.i = 0

    def frame(self, step: str, t_in_step: float, face: bool = True) -> FrameFeatures:
        self.i += 1
        yaw, pitch = self.neutral_yaw, -4.0
        blend = np.full(N_BLEND, 0.02, np.float32)
        if t_in_step < self.react_s:
            pass
        elif step == "yaw_left":
            yaw -= self.yaw_left
        elif step == "yaw_right":
            yaw += self.yaw_right
        elif step == "pitch_up":
            pitch += self.up
        elif step == "pitch_down":
            pitch -= self.down
        name = {"brow_raise": "browInnerUp", "jaw_open": "jawOpen", "smile": "mouthSmileLeft",
                "pucker": "mouthPucker"}.get(step)
        if name:
            amp = 0.1 if name in self.weak else 0.7
            blend[BLENDSHAPE_NAMES.index(name)] += amp * max(0.0, math.sin(2 * math.pi * t_in_step * 0.75))
        return FrameFeatures(seq=self.i, t_capture_ns=0, t_infer_ns=0, face=face, yaw=yaw, pitch=pitch, roll=1.0,
                             blend=blend)


def run(cal: Calibrator, player: Player, lose_face_at: float | None = None) -> tuple[list[Progress], float]:
    t, progs, step, step_t0 = 0.0, [], "neutral", 0.0
    while True:
        face = not (lose_face_at is not None and lose_face_at <= t < lose_face_at + 1.0)
        p = cal.feed(player.frame(step, t - step_t0, face), t)
        progs.append(p)
        if p.done:
            return progs, t
        if p.step != step:
            step, step_t0 = p.step, t
        t += 1 / FPS
        assert t < 120, "calibration never finished"


def test_full_calibration_measures_the_player():
    cal = Calibrator("sam", "full")
    progs, t = run(cal, Player())
    steps = [p.step for p in progs if p.active]
    assert list(dict.fromkeys(steps)) == ["neutral", "yaw_left", "yaw_right", "pitch_up", "pitch_down",
                                          "brow_raise", "jaw_open", "smile", "pucker"]
    assert t < 45
    overall = [p.overall for p in progs]
    assert overall == sorted(overall) and progs[-1].overall == 1.0

    c = cal.result()
    assert isinstance(c, Calibration) and c.mode == "full" and c.player == "sam"
    assert c.neutral["yaw"] == pytest.approx(3.0) and c.neutral["pitch"] == pytest.approx(-4.0)
    assert c.range["yaw"][0] == pytest.approx(20.0, abs=0.5) and c.range["yaw"][1] == pytest.approx(25.0, abs=0.5)
    assert c.range["pitch"][1] == pytest.approx(12.0, abs=0.5)
    assert c.range["pitch"][0] == config.MIN_RANGE_DEG              # 2 degrees down is below the floor
    assert c.range["roll"] == (config.DEFAULT_RANGE_DEG, config.DEFAULT_RANGE_DEG)
    assert any("down" in n for n in cal.notes)
    assert c.blend_peak["browInnerUp"] == pytest.approx(0.72, abs=0.02)
    for name in ("browInnerUp", "jawOpen", "mouthSmileLeft", "mouthSmileRight"):
        assert name in c.reliable
    assert "mouthPucker" not in c.reliable                          # 0.1 above neutral is too weak
    assert set(config.ASSUMED_RELIABLE) <= set(c.reliable)
    assert len(c.blend_neutral) == N_BLEND and c.blend_neutral[0] == pytest.approx(0.02)


def test_small_range_is_flagged_in_the_next_prompt():
    cal = Calibrator("sam", "full")
    progs, _ = run(cal, Player())
    pitch_down_end = [p for p in progs if p.step == "brow_raise"][0]
    assert "small" in pitch_down_end.prompt


def test_range_steps_wait_for_a_slow_player():
    """Someone still listening to the spoken prompt turns late: the step waits instead of measuring nothing."""
    cal = Calibrator("sam", "full")
    progs, _ = run(cal, Player(react_s=3.5))
    c = cal.result()
    assert c.range["yaw"][0] == pytest.approx(20.0, abs=0.5) and c.range["yaw"][1] == pytest.approx(25.0, abs=0.5)
    assert c.range["pitch"][1] == pytest.approx(12.0, abs=0.5)
    assert not any("left" in n or "right" in n for n in cal.notes)
    waiting = [p for p in progs if p.step == "yaw_left"]
    assert any("further left" in p.prompt for p in waiting)            # nudged once the minimum time passed
    assert len(waiting) / FPS >= 3.5 + config.CALIB_RANGE_HOLD_S - 0.1


def test_range_step_gives_up_on_no_movement():
    cal = Calibrator("sam", "full")
    progs, _ = run(cal, Player(yaw_left=0.0))
    assert len([p for p in progs if p.step == "yaw_left"]) / FPS == pytest.approx(config.CALIB_RANGE_TIMEOUT_S, abs=0.1)
    assert cal.result().range["yaw"][0] == config.MIN_RANGE_DEG and any("left" in n for n in cal.notes)


def test_face_lost_pauses_the_timer():
    cal_a = Calibrator("a", "quick")
    _, t_a = run(cal_a, Player())
    cal_b = Calibrator("b", "quick")
    progs, t_b = run(cal_b, Player(), lose_face_at=0.5)
    assert t_b == pytest.approx(t_a + 1.0, abs=0.1)
    assert any("can't see" in p.prompt for p in progs)


def test_quick_mode_is_neutral_only():
    cal = Calibrator("judge", "quick")
    progs, t = run(cal, Player())
    assert {p.step for p in progs if p.active} == {"neutral"}
    assert t == pytest.approx(config.CALIB_NEUTRAL_QUICK_S, abs=0.1)
    c = cal.result()
    assert c.mode == "quick" and c.neutral["yaw"] == pytest.approx(3.0)
    assert c.range["yaw"] == (config.DEFAULT_RANGE_DEG, config.DEFAULT_RANGE_DEG)
    assert set(config.QUICK_ASSUMED_RELIABLE) <= set(c.reliable)


def test_bad_mode_is_rejected():
    with pytest.raises(ValueError):
        Calibrator("x", "slow")
