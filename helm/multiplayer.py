"""Shared face recognition and two isolated, explicitly assigned controller sessions."""
from dataclasses import asdict, dataclass
import threading
import time

import numpy as np

from helm import config, profiles
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


def _box(landmarks):
    p = np.asarray(landmarks, np.float32)
    return float(p[:, 0].min()), float(p[:, 1].min()), float(p[:, 0].max()), float(p[:, 1].max())


def _iou(a, b):
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


class FaceTrack:
    """One face followed across frames by position. `player` is who the last identity check said it is."""
    __slots__ = ('box', 'player', 'verified_t')

    def __init__(self, box):
        self.box, self.player, self.verified_t = box, None, 0.0

    def owner(self, now):
        """The verified player, while the last check is fresh enough."""
        return self.player if self.player and now - self.verified_t <= config.IDENTITY_HOLD_S else None


class FaceTracks:
    """Matches each frame's faces to the faces of the frame before by overlap (greedy, best first). A face that
    overlaps no track starts a new, unverified one; tracks with no face this frame end."""
    def __init__(self):
        self.tracks: list[FaceTrack] = []

    def match(self, boxes):
        pairs = sorted(((_iou(b, t.box), i, j) for i, b in enumerate(boxes) for j, t in enumerate(self.tracks)),
                       reverse=True)
        chosen, used_faces, used_tracks = {}, set(), set()
        for overlap, i, j in pairs:
            if overlap < config.IDENTITY_FOLLOW_IOU or i in used_faces or j in used_tracks:
                continue
            chosen[i] = self.tracks[j]
            used_faces.add(i)
            used_tracks.add(j)
        out = []
        for i, b in enumerate(boxes):
            track = chosen.get(i) or FaceTrack(b)
            track.box = b
            out.append(track)
        self.tracks = out
        return out


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
        self._tracks_lock = threading.Lock()
        self._tracks = FaceTracks()
        self._tracks_generation = -1
        self._pending = None                       # the newest frame for the identity thread
        self._templates = {}
        self._identity_error = None

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
        """Every frame: MediaPipe (up to 4 faces), faces matched to tracks by overlap, each labelled with its track's
        verified player. Face recognition (SFace) runs beside this on its own thread (`_identify_loop`), so the frame
        rate does not depend on how many faces are in view."""
        from helm.vision import FaceTracker
        tracker = None
        last_seq = -1
        identify = threading.Thread(target=self._identify_loop, name='multiplayer-identity', daemon=True)
        identify.start()
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
                    tracker = tracker or FaceTracker(num_faces=4)
                    got = self.camera.wait_latest(last_seq, timeout=.1)
                    if got is None:
                        continue
                    image, capture_ns, last_seq = got
                    faces = tracker.process_all(image, capture_ns, last_seq)
                    now = time.monotonic()
                    with self._tracks_lock:
                        if self._tracks_generation != current:
                            self._tracks, self._tracks_generation = FaceTracks(), current
                        tracks = self._tracks.match([_box(f.landmarks) for f in faces])
                        owners = [t.owner(now) for t in tracks]
                        self._pending = (image, faces, tracks, capture_ns, current)
                    seen, matches = set(), {}
                    for index, player in enumerate(owners):  # one player, one face: a duplicate claim drops both
                        if player is None:
                            continue
                        if player in seen:
                            matches = {k: v for k, v in matches.items() if v != player}
                        else:
                            matches[index] = player
                        seen.add(player)
                    infer_ns = time.perf_counter_ns()
                    for face in faces:
                        face.t_infer_ns = infer_ns
                    error = self._identity_error
                    if error:
                        self._publish(current, error=error)
                    else:
                        self._publish(current, MultiFrame(image, faces, matches, current, last_seq, capture_ns))
                except Exception as e:
                    self._publish(current, error=f'Face tracking unavailable: {e}')
                    self._stop.wait(.2)
        finally:
            if tracker:
                tracker.close()

    def _identify_loop(self):
        """Beside the tracker, about 1/IDENTITY_CHECK_INTERVAL_S times a second: recognize the faces that need it.
        A face with no player goes through the full gallery (with P3's temporal confirmation). A tracked face whose
        last check is older than MULTI_REVERIFY_S gets one direct check against its own player's references (score
        and margin over the other profiles); a failed check clears it. Faces verified recently are skipped, so a
        round usually embeds zero or one face, not all of them."""
        encoder = gallery = None
        signature, generation = None, -1
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                with self._tracks_lock:
                    pending, self._pending = self._pending, None
                if pending is None:
                    self._stop.wait(.02)
                    continue
                image, faces, tracks, capture_ns, current = pending
                updated = gallery_signature()
                if gallery is None or updated != signature or current != generation:
                    signature, generation = updated, current
                    templates = [load_template(identity_path(p.name), p.name)
                                 for p in sorted(profiles._ROOT.iterdir())
                                 if p.is_dir() and not p.name.startswith('_')
                                 and p.name not in profiles.SHARED_PLAYERS
                                 and (p / 'identity.json').exists()]
                    gallery = FaceGallery(templates)
                    self._templates = {t.player: t for t in templates}
                    encoder = encoder or SFace()
                now = time.monotonic()
                need = [t.player is None or now - t.verified_t > config.MULTI_REVERIFY_S for t in tracks]
                if any(need):
                    embeddings = []
                    for face, check in zip(faces, need):
                        try:
                            embeddings.append(encoder.embed(image, face) if check else None)
                        except ValueError:
                            embeddings.append(None)
                    new = [e if t.player is None else None for e, t in zip(embeddings, tracks)]
                    matches = gallery.identify(new, capture_ns / 1e9) if any(e is not None for e in new) else {}
                    with self._tracks_lock:
                        for index, (track, emb) in enumerate(zip(tracks, embeddings)):
                            if emb is None:
                                continue
                            if track.player is not None:             # re-check the player it already is
                                if self._still(track.player, emb):
                                    track.verified_t = time.monotonic()
                                else:
                                    track.player = None
                            elif index in matches:
                                for other in self._tracks.tracks:     # a player is on one face only
                                    if other is not track and other.player == matches[index]:
                                        other.player = None
                                track.player, track.verified_t = matches[index], time.monotonic()
                self._identity_error = None
            except Exception as e:
                gallery = None
                self._identity_error = f'Face recognition unavailable: {e}'
                self._stop.wait(.2)
            self._stop.wait(max(0.0, config.IDENTITY_CHECK_INTERVAL_S - (time.monotonic() - started)))

    def _still(self, player, embedding):
        """A tracked face re-checked: still `player`, clearly ahead of every other profile?"""
        target = self._templates.get(player)
        if target is None:
            return False
        score = target.score(embedding)
        others = max((t.score(embedding) for name, t in self._templates.items() if name != player), default=-1.0)
        return score >= target.threshold and score - others >= target.margin


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
