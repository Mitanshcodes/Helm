# OWNER: shared
import json
import time
import threading
import numpy as np

from helm import profiles
from helm.contracts import FrameFeatures, Progress
from helm.gestures import GestureModel
from helm.dev_recording import DevRecording
from helm.main import Runtime, parse_args
from helm.server import handle_command


def runtime(tmp_path, monkeypatch, dev=True):
    monkeypatch.setattr(profiles, '_ROOT', tmp_path/'profiles')
    args = ['--mock', '--output', 'null', '--serial', 'off', '--no-server', '--dev-dir', str(tmp_path/'data')]
    return Runtime(parse_args(args+(['--dev'] if dev else [])))


def frame(rt, i):
    rt._video_frame = np.full((120,160,3), 40+i, np.uint8)
    t = time.perf_counter_ns()+i*33_333_333
    rt._step(FrameFeatures(seq=i, t_capture_ns=t, t_infer_ns=t, face=True))


def check_dataset(path):
    import cv2
    rows = [json.loads(x) for x in (path/'signals.jsonl').read_text().splitlines()]
    meta = json.loads((path/'metadata.json').read_text())
    cap = cv2.VideoCapture(str(path/'video.avi'))
    frames = 0
    while cap.read()[0]: frames += 1
    cap.release()
    assert meta['complete'] and len(rows)==frames==meta['frames']
    assert [r['frame_index'] for r in rows]==list(range(frames))
    assert all(len(r['signals']['delta'])==56 and 'scores' in r for r in rows)
    assert (path/'calibration.json').exists() and (path/'gestures.npz').exists()
    return rows


def test_manual_video_and_signals_match_and_have_context(tmp_path, monkeypatch):
    rt = runtime(tmp_path, monkeypatch)
    assert handle_command(rt, '{"cmd":"set_dev_recording","on":true}') is None
    for i in range(6): frame(rt, i)
    rt.set_dev_recording(False)
    frame(rt,6)
    rt.stop()
    path=next((tmp_path/'data').iterdir())
    assert len(check_dataset(path))==6
    assert rt._dev_sessions[0].error is None


def test_normal_mode_creates_no_datasets_and_command_is_validated(tmp_path, monkeypatch):
    rt=runtime(tmp_path,monkeypatch,False)
    assert handle_command(rt, '{"cmd":"set_dev_mode","on":"yes"}')['name']=='error'
    for i in range(3):frame(rt,i)
    rt.stop()
    assert not (tmp_path/'data').exists()


def test_calibration_video_includes_completion_and_guest_calibration(tmp_path,monkeypatch):
    monkeypatch.setattr('helm.calibration._QUICK_STEPS', (('neutral',.08,'Relax',('neutral',)),))
    rt=runtime(tmp_path,monkeypatch)
    rt.start_calibration('quick')
    for i in range(6):frame(rt,i)
    rt.stop()
    path=next((tmp_path/'data').iterdir())
    rows=check_dataset(path)
    assert len(rows)>=3 and not rt._calibrator
    assert json.loads((path/'calibration.json').read_text())['mode']=='quick'
    assert json.loads((path/'calibration_before.json').read_text())['mode']=='default'


def test_enrollment_saves_fitted_model_even_after_video_stops(tmp_path,monkeypatch):
    class Recorder:
        def __init__(self,name):self.name=name;self.rest=[np.zeros((8,56),np.float32)]
        def feed(self,s,t):return Progress(False,'done','done',1,1,True)
        def result(self):
            x=np.zeros((8,56),np.float32);x[:,44]=.7;return [x]
    monkeypatch.setattr('helm.main.TakeRecorder',Recorder)
    rt=runtime(tmp_path,monkeypatch)
    rt.record_gesture('smile')
    frame(rt,0)
    rt.stop()
    path=next((tmp_path/'data').iterdir())
    assert len(check_dataset(path))==1
    assert GestureModel.load(str(path/'gestures.npz')).names==['smile']
    assert json.loads((path/'metadata.json').read_text())['label']=='smile'


def test_model_update_keeps_dataset_pending_until_model_is_saved(tmp_path,monkeypatch):
    rt=runtime(tmp_path,monkeypatch)
    rt.set_dev_recording(True)
    frame(rt,0)
    recording=rt._dev_session
    recording.model_update_started()
    rt.set_dev_recording(False)
    frame(rt,1)
    recording.wait()
    assert recording.status()['saving']
    assert not json.loads((recording.path/'metadata.json').read_text())['complete']
    recording.save_model(GestureModel())
    recording.model_update_finished()
    assert not recording.status()['saving']
    check_dataset(recording.path)
    rt.stop()


def test_encoder_failure_marks_dataset_incomplete(tmp_path,monkeypatch):
    class FailedEncoder:
        def __init__(self,*args):pass
        def isOpened(self):return False
        def release(self):pass
    monkeypatch.setattr('cv2.VideoWriter',FailedEncoder)
    rt=runtime(tmp_path,monkeypatch)
    rt.set_dev_recording(True)
    frame(rt,0)
    rt.stop()
    recording=rt._dev_sessions[0]
    metadata=json.loads((recording.path/'metadata.json').read_text())
    assert not metadata['complete']
    assert 'encoder' in metadata['error']
    assert recording.status()['error']


def test_older_fit_cannot_overwrite_latest_enrollment(tmp_path,monkeypatch):
    rt=runtime(tmp_path,monkeypatch)
    rt.set_dev_recording(True)
    frame(rt,0)
    recording=rt._dev_session
    old=recording.model_update_started()
    new=recording.model_update_started()
    model=GestureModel()
    model.add_take('latest',np.full((8,56),.4,np.float32))
    recording.save_model(model,new)
    recording.model_update_finished()
    recording.save_model(GestureModel(),old)
    recording.model_update_finished()
    rt.stop()
    with np.load(recording.path/'gestures.npz') as data:
        assert 'latest' in data['labels']
    check_dataset(recording.path)


def test_queue_overflow_stops_capture_without_blocking(tmp_path,monkeypatch):
    release=threading.Event()
    monkeypatch.setattr(DevRecording,'_run',lambda self,*args:release.wait(5))
    recording=DevRecording(tmp_path,'manual','guest','game',None,None,{})
    try:
        for _ in range(64):assert recording._put(('frame',))
        assert not recording._put(('frame',))
        assert recording._stop.is_set()
        assert 'could not keep up' in recording.error
    finally:
        release.set()
        recording.wait()
