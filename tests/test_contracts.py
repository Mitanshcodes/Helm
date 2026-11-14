# OWNER: shared
"""The frozen contracts stay self-consistent."""
import numpy as np

from helm import contracts as c


def test_blendshape_names_match_count():
    assert len(c.BLENDSHAPE_NAMES) == c.N_BLEND == 52
    assert len(set(c.BLENDSHAPE_NAMES)) == c.N_BLEND
    assert c.BLENDSHAPE_NAMES[0] == "_neutral"
    assert c.FEATURE_DIM == c.N_BLEND + len(c.AXES) + 1


def test_dataclass_defaults():
    f = c.FrameFeatures(seq=0, t_capture_ns=0, t_infer_ns=0, face=False)
    assert f.blend.shape == (c.N_BLEND,) and f.blend.dtype == np.float32
    state = c.ControlState()
    assert state.buttons == frozenset() and state.fired == () and not state.paused
