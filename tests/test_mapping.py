# OWNER: P2
"""Bootstrap checks for mapping.py. TODO(P2): hysteresis, minimum hold, refractory, each mode, pause, analog scaling."""
from helm.contracts import ControlState, FrameFeatures
from helm.filters import Normalizer
from helm.mapping import Mapper, Trigger
from helm.profiles import default_mapping


def test_trigger_interface():
    pressed, fired = Trigger().update(0.0, t_ms=0.0)
    assert pressed is False and fired is False


def test_mapper_interface():
    mapper = Mapper(default_mapping("SuperTuxKart"))
    s = Normalizer().update(FrameFeatures(seq=0, t_capture_ns=0, t_infer_ns=0, face=True))
    state = mapper.update(s, act={}, events=[], scales={})
    assert isinstance(state, ControlState) and not state.paused
    assert isinstance(mapper.idle, bool)
    mapper.set_paused(True)
    assert mapper.update(s, {}, [], {}).paused
