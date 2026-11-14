# OWNER: P1
"""MockSource, Recorder and ReplaySource run without a camera."""
import numpy as np

from helm.contracts import BLENDSHAPE_NAMES, N_BLEND
from helm.mock import MockSource, Recorder, ReplaySource


def test_mock_source_signals():
    src = MockSource(realtime=False)
    frames = [src.next() for _ in range(30 * 21)]                  # 21 s of mock time
    assert [f.seq for f in frames[:3]] == [0, 1, 2]
    assert all(f.blend.shape == (N_BLEND,) for f in frames)
    yaws = [f.yaw for f in frames if f.face]
    assert 14.0 < max(yaws) <= 15.0 and -15.0 <= min(yaws) < -14.0
    brow = BLENDSHAPE_NAMES.index("browInnerUp")
    assert max(f.blend[brow] for f in frames) > 0.5
    lost = [f for f in frames if not f.face]
    assert 10 <= len(lost) <= 20                                   # about 0.5 s at 30 Hz
    assert all(f.yaw == 0.0 and not f.blend.any() for f in lost)


def test_record_and_replay_round_trip(tmp_path):
    path = str(tmp_path / "run.npz")
    src = MockSource(realtime=False)
    frames = [src.next() for _ in range(50)]
    rec = Recorder(path)
    for f in frames:
        rec.write(f)
    rec.close()

    replay = ReplaySource(path, realtime=False)
    out = []
    while (f := replay.next()) is not None:
        out.append(f)
    assert len(out) == len(frames)
    for a, b in zip(frames, out):
        assert a.seq == b.seq and a.face == b.face
        assert abs(a.yaw - b.yaw) < 1e-4
        assert np.allclose(a.blend, b.blend)
        assert b.t_infer_ns >= b.t_capture_ns
