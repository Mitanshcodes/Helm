"""Identity admission, persistence, freshness and single-controller isolation without biometric fixtures."""
import json
import time
from types import SimpleNamespace

import numpy as np
import pytest

from helm import profiles
from helm.contracts import FrameFeatures, Progress
from helm.identity import (IdentityGate, IdentityResult, IdentityWorker, Template, identity_path,
                           identity_required, load_template, save_template)
from helm.main import Runtime, parse_args
from helm.profiles import default_mapping


def vector(i=0):
    out = np.zeros(128, np.float32)
    out[i] = 1
    return out


def template(player='b', i=0):
    return Template(player, np.tile(vector(i), (8, 1)))


def confirm(gate, observations, start=0):
    result = None
    for t in (start, start+.1, start+.2):
        result = gate.choose(observations, t)
    return result


def test_identity_persistence_explicit_profile_binding_and_missing_file_stays_protected(tmp_path):
    path = save_template('b', [vector()]*8, tmp_path)
    loaded = load_template(path, 'b')
    assert loaded.score(vector()) == pytest.approx(1)
    with pytest.raises(ValueError, match='profile'):
        load_template(path, 'a')
    path.unlink()
    assert identity_required('b', tmp_path)
    with pytest.raises(FileNotFoundError):
        load_template(path, 'b')
    assert not identity_required('never_enrolled', tmp_path)


def test_template_without_marker_still_requires_identity_and_corruption_is_an_error(tmp_path):
    path = save_template('b', [vector()]*8, tmp_path)
    path.with_name('identity_required.json').unlink()
    assert identity_required('b', tmp_path)
    data = json.loads(path.read_text())
    data['preprocessing'] = 'incompatible'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='incompatible'):
        load_template(path, 'b')
    with pytest.raises(ValueError, match='named'):
        save_template('guest', [vector()]*8, tmp_path)


def test_wrong_face_unknown_and_missing_face_never_admit():
    for observations in ([vector(1)], [None], []):
        chosen, status = confirm(IdentityGate(template()), observations)
        assert chosen is None and not status['allowed']


def test_legitimate_face_is_selected_even_when_detector_order_changes():
    gate = IdentityGate(template(), [template('a', 1)])
    assert gate.choose([vector(1), vector()], 0)[0] is None
    assert gate.choose([vector(), vector(1)], .1)[0] is None
    i, status = gate.choose([vector(1), vector()], .2)
    assert i == 1 and status['allowed'] and status['selected_index'] == 1
    i, _ = gate.choose([vector(), vector(1)], .3)
    assert i == 0


def test_duplicate_faces_or_competing_profile_template_are_ambiguous():
    for gate, observations in ((IdentityGate(template()), [vector(), vector()]),
                               (IdentityGate(template(), [template('duplicate')]), [vector()])):
        chosen, status = confirm(gate, observations)
        assert chosen is None and status['state'] == 'ambiguous'


def test_loss_and_nonmonotonic_timestamps_require_fresh_confirmation():
    gate = IdentityGate(template())
    assert confirm(gate, [vector()])[1]['allowed']
    assert not gate.choose([vector(1)], .3)[1]['allowed']
    assert not gate.choose([vector()], .4)[1]['allowed']
    assert not gate.choose([vector()], .5)[1]['allowed']
    assert gate.choose([vector()], .6)[1]['allowed']
    assert not gate.choose([vector()], .6)[1]['allowed']
    assert not gate.choose([vector()], 1.2)[1]['allowed']


def test_worker_rejects_stale_results_and_old_profile_generation(monkeypatch):
    worker = IdentityWorker(None)
    first = worker.configure('b')
    frame = FrameFeatures(3, 1_000_000_000, 1_000_000_000, True)
    result = IdentityResult(frame, np.zeros((2, 2, 3), np.uint8), {'allowed': True, 'state': 'recognized'}, first)
    worker._publish(first, result)
    monkeypatch.setattr('helm.identity.time.perf_counter_ns', lambda: 1_050_000_000)
    assert worker.wait_latest(2, 0)[0] is result
    assert worker.wait_latest(3, 0)[1]['allowed']          # no new result, still within deadline
    monkeypatch.setattr('helm.identity.time.perf_counter_ns', lambda: 1_251_000_000)
    assert worker.wait_latest(2, 0)[1]['state'] == 'stale'
    assert not worker.wait_latest(3, 0)[1]['allowed']
    worker.configure('c')
    worker._publish(first, result)
    assert worker._latest is None and worker._status['player'] == 'c'


def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, '_ROOT', tmp_path)
    save_template('b', [vector()]*8)
    return Runtime(parse_args(['--mock', '--player', 'b', '--output', 'null', '--serial', 'off', '--no-server']))


FACE = np.tile([[.4, .4], [.6, .6]], (239, 1)).astype(np.float32)   # 478 landmarks in a box (.4, .4)-(.6, .6)


def step(rt, seq, t_s, admitted):
    """One tracked frame of the face at FACE. Admitted = the face check last verified a face at that spot (gestures
    run at full rate on the tracker; the check runs beside it, main._follow_verified ties the two together)."""
    rt._verified_box = (.4, .4, .6, .6) if admitted else None
    rt._verified_t = time.monotonic()
    rt._identity_status.update(state='recognized' if admitted else 'rejected')
    ns = round(t_s*1e9)
    rt._step(FrameFeatures(seq, ns, ns, True, landmarks=FACE))


def test_rejection_immediately_neutralizes_auto_output_without_face_loss_grace(tmp_path, monkeypatch):
    rt = runtime(tmp_path, monkeypatch)
    mapping = default_mapping('SuperTuxKart')
    mapping['auto'] = {'rt': .8}
    rt._do_set_mapping(mapping)
    now = time.perf_counter()
    step(rt, 0, now, True)
    assert rt._pad.last.rt == pytest.approx(.8)
    rt._fired_until['old'] = time.perf_counter_ns()+1_000_000_000
    step(rt, 1, now+.01, False)
    assert rt._pad.last.rt == rt._pad.last.lt == rt._pad.last.lx == 0
    assert not rt._pad.last.buttons and not rt._pad.last.fired and not rt._fired_until
    assert not rt.snapshot()['face']
    assert rt._normalizer.neutral == rt._normalizer._calib_neutral
    rt.stop()


@pytest.mark.parametrize('field', ['_calibrator', '_take_recorder', '_breath_cal'])
def test_setup_collects_only_verified_samples_and_time_freezes_during_loss(tmp_path, monkeypatch, field):
    rt = runtime(tmp_path, monkeypatch)
    observed = []
    def feed(*args):
        observed.append(args[-1])
        return Progress(True, 'test', 'test', .1, .1)
    setattr(rt, field, SimpleNamespace(feed=feed))
    now = time.perf_counter()
    step(rt, 0, now, False)
    assert observed == []
    step(rt, 1, now+.03, True)
    assert observed == [0]
    step(rt, 2, now+30, False)
    step(rt, 3, now+30.03, True)
    assert observed == [0, 0]
    step(rt, 4, now+30.06, True)
    assert observed[-1] == pytest.approx(.03, abs=1e-5)
    rt.stop()


def test_mock_feature_replay_cannot_bypass_enrolled_profile(tmp_path, monkeypatch):
    rt = runtime(tmp_path, monkeypatch)
    f = rt._next_features()
    rt._step(f)
    assert rt.snapshot()['identity']['state'] == 'no_pixels'
    assert rt.snapshot()['identity']['protected'] and not rt.snapshot()['face']
    rt.stop()


def test_no_frame_identity_lock_does_not_block_reload_or_profile_commands(tmp_path, monkeypatch):
    rt = runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(rt, '_next_features', lambda: None)
    called = []
    def reload():
        called.append(True)
        rt._stop.set()
    monkeypatch.setattr(rt, '_do_identity_reload', reload)
    rt.reload_identity()
    rt._loop()
    assert called
    rt._stop.clear()
    original = rt._do_apply_profile
    def apply(*args):
        original(*args)
        rt._stop.set()
    monkeypatch.setattr(rt, '_do_apply_profile', apply)
    rt._request('apply_profile', 'other', 'SuperTuxKart', None, default_mapping('SuperTuxKart'), None)
    rt._loop()
    assert rt.player == 'other' and not rt._identity_required
    assert not rt._identity_admitted
    rt.stop()


def test_stalled_camera_expired_identity_clears_previous_controller_state(tmp_path, monkeypatch):
    from helm.contracts import ControlState
    rt = runtime(tmp_path, monkeypatch)
    rt._source = None
    rt._identity_allowed = rt._identity_admitted = True
    rt._pad.apply(ControlState(rt=.9, buttons=frozenset({'A'})))
    def expired(*args, **kwargs):
        rt._stop.set()
        return None, dict(protected=True, allowed=False, state='stale', player='b', reason='expired')
    rt._identity_worker = SimpleNamespace(wait_latest=expired, close=lambda: None)
    rt._loop()
    assert rt._pad.last.rt == 0 and not rt._pad.last.buttons
    assert not rt._identity_admitted
    assert not rt.snapshot()['identity']['allowed']
    rt.stop()


def test_offline_presence_labels_do_not_claim_ownership_without_boxes():
    from eval.identity_replay import summarize
    rows = [dict(allowed=True, inference_ms=10, over_budget=False, target_present=False),
            dict(allowed=False, inference_ms=12, over_budget=False, target_present=True)]
    summary = summarize(rows)
    assert summary['presence_labels']['admitted_when_target_absent'] == 1
    assert 'ownership_labels' not in summary


def test_gestures_follow_the_verified_face_between_checks(tmp_path, monkeypatch):
    """Tracking runs at full rate; the face check runs beside it. Control follows the face the check last verified
    while it moves, never a face somewhere else, and stops when no check has confirmed it for IDENTITY_HOLD_S."""
    from helm import config
    rt = runtime(tmp_path, monkeypatch)

    def frame(x0):
        box = np.tile([[x0, .4], [x0 + .2, .6]], (239, 1)).astype(np.float32)
        return FrameFeatures(1, 0, 0, True, landmarks=box)

    rt._verified_box, rt._verified_t = (.4, .4, .6, .6), time.monotonic()
    assert rt._follow_verified(frame(.42))                    # the same face, moved a little
    assert rt._follow_verified(frame(.46))                    # keeps following it
    assert not rt._follow_verified(frame(.05))                # someone else, on the other side of the picture
    rt._verified_t = time.monotonic() - config.IDENTITY_HOLD_S - .1
    assert not rt._follow_verified(frame(.46))                # no fresh "recognized" check: control stops
    rt.stop()
