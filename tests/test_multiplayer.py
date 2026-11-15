"""Independent outputs and open-set identity admission through the actual per-player pipelines."""
import json
import time

import numpy as np
import pytest

from helm.contracts import BLENDSHAPE_NAMES, FrameFeatures
from helm.identity import Template
from helm.main import Runtime, hold_back_crosstalk, parse_args
from helm.multiplayer import FaceGallery, MultiFrame, MultiplayerControllers, PlayerSession
from helm.output import NullPad, second_gamepad
from helm.server import encode_preview, handle_command


def embedding(i):
    v = np.zeros(128, np.float32)
    v[i] = 1
    return v


def test_gallery_matches_profiles_independently_of_face_order_and_rejects_unknown():
    gallery = FaceGallery([Template('alex', np.array([embedding(0)])), Template('sam', np.array([embedding(1)]))])
    for t in [0, .1, .21]:
        matched = gallery.identify([embedding(1), embedding(0), embedding(2)], t)
    assert matched == {0: 'sam', 1: 'alex'}
    assert gallery.identify([embedding(0), embedding(1)], .24) == {0: 'alex', 1: 'sam'}
    assert gallery.identify([embedding(2)], .3) == {}


def test_duplicate_face_is_ambiguous_and_does_not_arm():
    gallery = FaceGallery([Template('alex', np.array([embedding(0)]))])
    for t in [0, .1, .3]:
        assert gallery.identify([embedding(0), embedding(0)], t) == {}


def session(player, axis):
    return PlayerSession(player, 'game', None, dict(axes=[dict(source=axis, target='lx', deadzone=0, curve=1)],
                                                   auto={'rt': .6}, gestures={}, buttons=[]), None, hold_back_crosstalk)


def result(seq=0, matches=None, capture=None):
    ns = time.perf_counter_ns() if capture is None else capture
    faces = [FrameFeatures(seq, ns, ns, True, yaw=10, pitch=0),
             FrameFeatures(seq, ns, ns, True, yaw=0, pitch=-10)]
    return MultiFrame(np.zeros((120, 160, 3), np.uint8), faces,
                      {0: 'alex', 1: 'sam'} if matches is None else matches, 1, seq, ns)


def manager():
    m = MultiplayerControllers(NullPad())
    m.pads[1] = second_gamepad(m.pads[0])
    m.enabled = True
    m.process(result())
    return m


def test_two_profiles_drive_separate_outputs_and_detection_order_does_not_swap_them():
    m = manager()
    m.assign(0, session('alex', 'yaw'))
    m.assign(1, session('sam', 'pitch'))
    r = result(1)
    m.process(r)
    assert m.pads[0].last.lx > 0 and m.pads[1].last.lx < 0
    r.faces.reverse()
    r.matches = {0: 'sam', 1: 'alex'}
    m.process(r)
    assert m.pads[0].last.lx > 0 and m.pads[1].last.lx < 0
    assert m.sessions[0].normalizer is not m.sessions[1].normalizer
    assert m.sessions[0].mapper is not m.sessions[1].mapper


def test_assignment_requires_visible_profile_and_disallows_duplicate_assignment():
    m = manager()
    with pytest.raises(ValueError, match='not currently'):
        m.assign(0, session('unknown', 'yaw'))
    m.assign(0, session('alex', 'yaw'))
    with pytest.raises(ValueError, match='already controls'):
        m.assign(1, session('alex', 'pitch'))


def test_lost_face_neutralizes_only_its_controller_including_automatic_throttle():
    m = manager()
    m.assign(0, session('alex', 'yaw'))
    m.assign(1, session('sam', 'pitch'))
    m.process(result(1))
    assert m.pads[0].last.rt == m.pads[1].last.rt == .6
    m.process(result(2, {1: 'sam'}))
    assert m.pads[0].last.rt == 0 and m.pads[0].last.lx == 0
    assert m.pads[1].last.rt == .6 and m.sessions[1].connected
    assert not m.sessions[0].connected


def test_stale_frames_and_camera_stall_release_all_outputs():
    m = manager()
    m.assign(0, session('alex', 'yaw'))
    r = result(1)
    m.process(r)
    m.expire(r.capture_ns + 251_000_000)
    assert not m.visible and m.pads[0].last.rt == 0
    assert not m.process(r, r.capture_ns + 251_000_000)
    assert m.snapshot()['controllers'][0]['control']['rt'] == 0


def test_gesture_buttons_do_not_cross_profiles_and_loss_requires_a_new_hold():
    m = manager()
    mapping = dict(gestures={'smile': dict(kind='blendshape', sources=['mouthSmileLeft'], on=.6, off=.3,
                                          min_hold_ms=100)},
                   buttons=[dict(gesture='smile', target='A', mode='hold')])
    m.assign(0, PlayerSession('alex', 'game', None, mapping, None, hold_back_crosstalk))
    m.assign(1, PlayerSession('sam', 'game', None, mapping, None, hold_back_crosstalk))
    base = time.perf_counter_ns()

    def step(dt, matches=None):
        r = result(matches=matches, capture=base + int(dt * 1e9))
        r.faces[0].blend[BLENDSHAPE_NAMES.index('mouthSmileLeft')] = .9
        m.process(r, r.capture_ns)

    step(0)
    step(.15)
    assert m.pads[0].last.buttons == frozenset({'A'})
    assert not m.pads[1].last.buttons
    step(.18, {1: 'sam'})
    assert not m.pads[0].last.buttons
    step(.20)
    assert not m.pads[0].last.buttons
    step(.35)
    assert m.pads[0].last.buttons == frozenset({'A'})


def test_preview_mirrors_every_face_and_preserves_profile_labels():
    points = np.array([[.2, .3], [.7, .8]], np.float32)
    preview = encode_preview(np.zeros((80, 120, 3), np.uint8), None,
                             [{'player': 'sam', 'landmarks': points}])
    assert preview['faces'][0]['player'] == 'sam'
    np.testing.assert_allclose(preview['faces'][0]['landmarks'], [[.8, .3], [.3, .8]])
    assert preview['landmarks'] is None
    np.testing.assert_allclose(points[0], [.2, .3])


@pytest.mark.parametrize('command', [
    {'cmd': 'set_play_mode', 'mode': 'maybe'},
    {'cmd': 'assign_controller', 'slot': True, 'player': 'sam'},
    {'cmd': 'assign_controller', 'slot': 2, 'player': 'sam'},
    {'cmd': 'assign_controller', 'slot': 0, 'player': '../sam'},
    {'cmd': 'assign_controller', 'slot': 0},
])
def test_wire_commands_validate_mode_slot_and_profile(command):
    assert handle_command(object(), json.dumps(command))['name'] == 'error'


def test_runtime_defaults_to_singleplayer_and_switching_releases_both_pads():
    rt = Runtime(parse_args(['--mock', '--output', 'null', '--no-server', '--serial', 'off']))
    try:
        assert not rt.snapshot()['multiplayer']['enabled']
        rt._do_play_mode('multiplayer')
        assert rt._multiplayer.enabled
        rt._multiplayer.visible = ['alex']
        rt._multiplayer.assign(0, session('alex', 'yaw'))
        rt._multiplayer.process(result())
        assert rt._pad.last.rt == .6
        rt._do_play_mode('singleplayer')
        assert rt._pad.last.rt == 0 and rt._multiplayer.pads[1].last.rt == 0
        assert not rt._multiplayer.enabled and rt._multiplayer.sessions == [None, None]
    finally:
        rt.stop()


def test_late_assignment_from_previous_mode_cannot_reactivate_a_controller():
    rt = Runtime(parse_args(['--mock', '--output', 'null', '--no-server', '--serial', 'off']))
    try:
        rt._do_play_mode('multiplayer')
        version, generation = rt._assignment_versions[0], rt._multi_generation
        rt._do_play_mode('singleplayer')
        rt._do_finish_assignment(0, session('alex', 'yaw'), version, generation, None)
        assert rt._multiplayer.sessions[0] is None and rt._pad.last.rt == 0
    finally:
        rt.stop()


def test_multiplayer_training_commands_require_opening_a_profile_first():
    rt = Runtime(parse_args(['--mock', '--output', 'null', '--no-server', '--serial', 'off']))
    try:
        rt._do_play_mode('multiplayer')
        for call in (lambda: rt._do_calibrate('full'), lambda: rt._do_record('smile'),
                     lambda: rt._do_dev_recording(True)):
            with pytest.raises(ValueError, match='profile'):
                call()
        assert rt._calibrator is None and rt._take_recorder is None
    finally:
        rt.stop()


def test_tracks_follow_faces_by_overlap_and_verification_expires(monkeypatch):
    from helm import config
    from helm.multiplayer import FaceTracks
    tracks = FaceTracks()
    a, b = tracks.match([(.1, .1, .3, .3), (.6, .1, .8, .3)])
    a.player, a.verified_t = 'alex', time.monotonic()
    moved = tracks.match([(.62, .1, .82, .3), (.12, .1, .32, .3)])       # order swapped, both moved a little
    assert moved[1] is a and moved[1].owner(time.monotonic()) == 'alex' and moved[0] is b and b.owner(time.monotonic()) is None
    new = tracks.match([(.4, .5, .5, .6)])                               # alex left, a stranger elsewhere
    assert new[0] is not a and new[0].player is None
    a.verified_t = time.monotonic() - config.IDENTITY_HOLD_S - .1
    assert a.owner(time.monotonic()) is None                             # no fresh check: no control


def test_recheck_needs_score_and_margin_over_the_other_profiles():
    from helm.multiplayer import MultiFaceWorker
    w = MultiFaceWorker(camera=None)
    w._templates = {'alex': Template('alex', np.array([embedding(0)])), 'sam': Template('sam', np.array([embedding(1)]))}
    assert w._still('alex', embedding(0)) and not w._still('alex', embedding(1)) and not w._still('nobody', embedding(0))
    both = (embedding(0) + embedding(1)) / np.sqrt(2)                    # looks like either: not clearly alex
    assert not w._still('alex', both)


def test_windows_throttling_opt_out_is_a_no_op_elsewhere():
    import sys
    from helm.main import exempt_from_throttling
    if sys.platform != "win32":
        assert exempt_from_throttling() is False
