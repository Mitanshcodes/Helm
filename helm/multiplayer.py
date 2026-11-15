"""Shared face recognition and two isolated, explicitly assigned controller sessions."""
from dataclasses import asdict, dataclass
import threading
import time

import numpy as np

from helm import profiles
from helm.adapt import FatigueTracker
from helm.contracts import ControlState, FrameFeatures
from helm.filters import Normalizer
from helm.gestures import GestureEngine, GestureModel
from helm.mapping import Mapper
from helm.output import VGamepadPad
from helm.identity import IdentityGate, MAX_AGE_S, SFace, identity_path, load_template


def gallery_signature():
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size)
                 for p in sorted(profiles._ROOT.glob('*/identity*.json')) if p.is_file())


class FaceGallery:
    """Open-set, one-to-one identification; detector ordering never determines a player."""
    def __init__(self, templates):
        self.gates = {t.player: IdentityGate(t, [o for o in templates if o.player != t.player])
                      for t in templates}

    def identify(self, embeddings, t_s):
        matches = {}
        for player, gate in self.gates.items():
            index, status = gate.choose(embeddings, t_s)
            if index is not None:
                matches.setdefault(index, []).append(player)
        return {index: players[0] for index, players in matches.items() if len(players) == 1}


@dataclass
class MultiFrame:
    image: np.ndarray
    faces: list[FrameFeatures]
    matches: dict[int, str]
    generation: int
    seq: int
    capture_ns: int


class MultiFaceWorker:
    """Vision/identity only. Controller output remains on Runtime's pipeline thread."""
    def __init__(self, camera):
        self.camera = camera
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._enabled = False
        self._generation = 0
        self._latest = None
        self._error = None
        self._thread = None

    def configure(self, enabled):
        with self._condition:
            self._enabled = enabled
            self._generation += 1
            self._latest = None
            self._error = None
            self._condition.notify_all()
            return self._generation

    def start(self):
        self._thread = threading.Thread(target=self._run, name='multiplayer-vision', daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        if self._thread:
            self._thread.join(timeout=2)

    def wait_latest(self, seq):
        with self._condition:
            self._condition.wait_for(lambda: self._stop.is_set() or self._error is not None or
                                     (self._latest is not None and self._latest.seq > seq), .05)
            result = self._latest
            if result is not None and result.seq > seq:
                return result, self._error
            return None, self._error

    def _publish(self, generation, result=None, error=None):
        with self._condition:
            if generation == self._generation and self._enabled:
                self._latest, self._error = result, error
                self._condition.notify_all()

    def _run(self):
        from helm.vision import FaceTracker
        tracker = encoder = gallery = None
        generation = -1
        signature = None
        last_seq = -1
        checked_at = 0.0
        try:
            while not self._stop.is_set():
                with self._condition:
                    self._condition.wait_for(lambda: self._stop.is_set() or self._enabled, .1)
                    enabled, current = self._enabled, self._generation
                if self._stop.is_set():
                    break
                if not enabled:
                    continue
                try:
                    now = time.monotonic()
                    if current != generation or now - checked_at > 1:
                        checked_at = now
                        updated = gallery_signature()
                        if current != generation or updated != signature or gallery is None:
                            generation, signature = current, updated
                            templates = [load_template(identity_path(p.name), p.name)
                                         for p in sorted(profiles._ROOT.iterdir())
                                         if p.is_dir() and not p.name.startswith('_')
                                         and p.name not in profiles.SHARED_PLAYERS
                                         and (p / 'identity.json').exists()]
                            gallery = FaceGallery(templates)
                            encoder = encoder or SFace()
                            tracker = tracker or FaceTracker(num_faces=4)
                    got = self.camera.wait_latest(last_seq, timeout=.1)
                    if got is None:
                        continue
                    image, capture_ns, last_seq = got
                    faces = tracker.process_all(image, capture_ns, last_seq)
                    embeddings = []
                    for face in faces:
                        try:
                            embeddings.append(encoder.embed(image, face))
                        except ValueError:
                            embeddings.append(None)
                    matches = gallery.identify(embeddings, capture_ns / 1e9)
                    infer_ns = time.perf_counter_ns()
                    for face in faces:
                        face.t_infer_ns = infer_ns
                    self._publish(current, MultiFrame(image, faces, matches, current, last_seq, capture_ns))
                except Exception as e:
                    gallery = None
                    self._publish(current, error=f'Face recognition unavailable: {e}')
                    self._stop.wait(.2)
        finally:
            if tracker:
                tracker.close()


class PlayerSession:
    def __init__(self, player, game, calibration, mapping, model, crosstalk):
        self.player, self.game = player, game
        self.calibration, self.mapping, self.model = calibration, mapping, model
        self.crosstalk = crosstalk
        self.control = ControlState()
        self.connected = False
        self.reset()

    def reset(self):
        paused = getattr(getattr(self, 'mapper', None), '_paused', False)
        self.normalizer = Normalizer(self.calibration)
        self.normalizer.set_gains({a['source']: a.get('gain', 1) for a in self.mapping.get('axes', [])
                                   if a.get('source') in ('yaw', 'pitch', 'roll')})
        self.engine = GestureEngine(self.calibration, self.mapping.get('gestures', {}), self.model)
        self.mapper = Mapper(self.mapping)
        self.mapper.set_paused(paused)
        self.fatigue = FatigueTracker()
        self.idle = True
        self.control = ControlState()

    def update(self, frame):
        if not self.connected:
            self.reset()
        self.connected = True
        signals = self.normalizer.update(frame, breath=0, idle=self.idle)
        act = self.engine.update(signals)
        defs = self.mapping.get('gestures', {})
        used = {b.get('gesture') for b in self.mapping.get('buttons', [])}
        used |= {t.get('source') for t in self.mapping.get('triggers', [])}
        pause = (self.mapping.get('pause') or {}).get('gesture')
        competitors = {name: (float(d['on']), frozenset(d.get('sources', []) if d.get('kind') == 'blendshape' else ()))
                       for name, d in defs.items() if name in used and name != pause
                       and d.get('kind') in ('blendshape', 'learned') and d.get('on', 0) > 0}
        act = self.crosstalk(act, competitors)
        scales = self.fatigue.update(act, frame.t_capture_ns / 1e9)
        self.control = self.mapper.update(signals, act, [], scales)
        self.idle = self.mapper.idle
        return self.control

    def lose(self):
        if self.connected:
            self.reset()
        self.connected = False
        self.control = ControlState()


def load_player(player, game, crosstalk):
    if player in profiles.SHARED_PLAYERS:
        raise ValueError('Choose a personal profile with face enrollment')
    load_template(identity_path(player), player)
    path = profiles.gesture_model_path(player)
    from pathlib import Path
    model = GestureModel.load(path) if Path(path).exists() else None
    return PlayerSession(player, game, profiles.load_calibration(player),
                         profiles.load_mapping(player, game), model, crosstalk)


class MultiplayerControllers:
    """Pipeline-thread owner of assignments and output. Lost identity always releases the pad."""
    def __init__(self, primary):
        self.pads = [primary, None]
        self.sessions = [None, None]
        self.visible = []
        self.error = None
        self.capture_ns = 0
        self.enabled = False
        self.loading = [False, False]

    def assign(self, slot, session):
        if session is not None:
            if session.player not in self.visible:
                raise ValueError('That profile is not currently recognized in the camera')
            if any(s and s.player == session.player for i, s in enumerate(self.sessions) if i != slot):
                raise ValueError('That profile already controls the other controller')
        self.pads[slot].apply(ControlState())
        self.sessions[slot] = session
        self.loading[slot] = False

    def process(self, result, now_ns=None):
        now_ns = time.perf_counter_ns() if now_ns is None else now_ns
        if not 0 <= now_ns - result.capture_ns <= MAX_AGE_S * 1e9:
            self.lose_all()
            return False
        self.capture_ns = result.capture_ns
        self.error = None
        found = {player: result.faces[index] for index, player in result.matches.items()}
        self.visible = sorted(found)
        for slot, session in enumerate(self.sessions):
            control = ControlState()
            if session:
                if session.player in found:
                    control = session.update(found[session.player])
                else:
                    session.lose()
            if self.pads[slot]:
                self.pads[slot].apply(control)
        return True

    def expire(self, now_ns=None):
        now_ns = time.perf_counter_ns() if now_ns is None else now_ns
        if now_ns - self.capture_ns > MAX_AGE_S * 1e9:
            self.lose_all()

    def lose_all(self):
        self.visible = []
        for pad, session in zip(self.pads, self.sessions):
            if pad:
                pad.apply(ControlState())
            if session:
                session.lose()

    def snapshot(self):
        slots = []
        for i, session in enumerate(self.sessions):
            control = asdict(session.control if session else ControlState())
            control['buttons'] = sorted(control['buttons'])
            control['fired'] = list(control['fired'])
            slots.append(dict(slot=i, player=session.player if session else None,
                              connected=bool(session and session.connected), loading=self.loading[i],
                              mapping=session.mapping if session else None, control=control))
        return dict(enabled=self.enabled, visible_profiles=list(self.visible), controllers=slots, error=self.error,
                    output_available=isinstance(self.pads[0], VGamepadPad))
