# Two-player mode

Helm starts in Singleplayer with the existing profile setup and play flow. On the profile
selection page, choose **Multiplayer** to reveal the shared camera and two controllers.
The profile tiles move below the play area and remain available for setup and editing.

First create and fully calibrate a named profile for each player. The existing calibration
flow learns Face ID during head movements when the SFace weights are installed (see
[Face identity](IDENTITY.md)). Default/guest profiles cannot join multiplayer because
they have no persistent identity. Each player also needs their saved calibration, gestures,
and mapping for the current game; multiplayer does not enroll or train profiles itself.

Look at the camera until recognized, then choose that profile in a controller's
**Controlled by** menu. Only profiles currently recognized in the camera can be assigned,
and a profile can control only one controller. The camera draws colored face outlines and
profile names using the same colors as the profile tiles. Unknown faces remain unassigned.
Each controller displays that player's mapped live output.

Opening a profile tile returns to singleplayer setup and releases both multiplayer
controllers. Switching modes clears assignments. If a player briefly leaves the camera,
their assignment is retained and their output is neutral until their face is recognized
again. The other controller continues operating.

## Frame rate: tracking every frame, recognition beside it (P1, 2026-11-15)

Running SFace on every face of every frame tied the frame rate to the number of faces in view: on the demo laptop
5-6 fps with two people. Now `MultiFaceWorker`:

- **Every frame:** runs MediaPipe (up to 4 faces) and matches each face to the face in the same place in the
  previous frame (`FaceTracks`, overlap 0.3 or more). It labels each with its track's verified player.
- **On its own thread, about 6-7 times a second:** recognizes only the faces that need it.
  - A face with no player goes through the gallery, with the usual temporal confirmation.
  - A tracked face whose last check is older than 0.5 s gets one direct check against its own player (score and
    margin over the other profiles). A failed check clears it.
- **Control stops** when a track's last confirmation is over 1 s old. A player is on one face only.
- **Measured** with SFace slowed to laptop speed: one face 11.2 → 26.2 fps, two faces 5.8 → 26.5 fps (26 is the test
  camera's maximum).

## Recognition and output

One worker reads up to four faces from the same camera frame, computes SFace embeddings,
and compares each against all saved personal identities. The existing similarity,
competitor-margin, ambiguity, and temporal confirmation gates apply independently per
profile. Face detection order does not determine controller ownership. Gallery file
changes are checked once per second.

Each assigned player has separate normalization, calibration, gesture model, debounce,
mapping, fatigue, pause, and toggle state. Identity loss clears transient state and releases
held buttons, axes, and automatic throttle. A camera result older than 250 ms, a recognition
error, or a stalled camera releases outputs. Reacquisition requires fresh gesture holds;
a player's explicit pause state survives loss of their face.

Windows with ViGEmBus and the vgamepad backend creates two independent Xbox 360 pads.
The second pad is retained across mode changes and receives neutral output outside
multiplayer. Games may require their own join action or controller configuration.
Null output on Linux/macOS supports the live preview and routing without virtual gamepads.
Keyboard output cannot represent independent controllers, so multiplayer reports an error
with that backend.

The single physical sip-and-puff device has no multiplayer owner: both players' facial
pipelines receive zero breath and sensor events are discarded in multiplayer. Configure
face-only mappings for this version. Dev dataset recording and calibration remain available
inside individual profile pages; there is no synchronized multiplayer recording UI yet.

## Validation

`tests/test_multiplayer.py` exercises two-profile identity matching and unknown/duplicate
rejection, reordered detections, independent axes and gesture buttons, visible-only unique
assignments, face loss, stale frames, mode transitions, obsolete assignment callbacks,
and multi-face preview mirroring. Output tests check two independent virtual-driver
instances using a fake driver. These checks do not establish real-camera recognition
accuracy or two-controller compatibility with a particular Windows game.

The browser demo (`?mock=1`) supplies explicitly simulated faces and independent outputs
for UI testing. Backend `--mock` does not simulate trusted identities and cannot arm real
multiplayer sessions.
