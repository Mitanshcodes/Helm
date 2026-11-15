<!-- OWNER: P4 -->
# Devpost submission draft

Paste each section into the matching Devpost field. Before submitting, resolve every line marked
**TODO**: they are facts only the team has (measured numbers, what actually happened this weekend).
Do not submit with a number that was not measured.

**Title:** Helm

**Tagline:** A game controller you steer with your face. Play with whatever moves.

---

## Inspiration

About 1.3 billion people, one in six, live with a significant disability (WHO), and AbleGamers counts
46 million gamers with disabilities in the US alone. Yet every adaptive controller on the market still assumes
you can press something, and the specialist ones cost $100 to more than $500. Switch hubs need a
body part that can push a button. Sip-and-puff and mouth joysticks need a lip seal and enough
breath. Face-tracking tools exist, but they act as a mouse and keyboard on fixed thresholds, which
is built for pointing, not for steering a kart. Eye tracking asks for the one thing a player needs
free: their eyes.

Many people with limited hand and arm movement can still turn their head a little and move parts
of their face, sometimes on one side only. We wanted a controller that starts from whatever
movement a person has, instead of asking them to adapt to it.

**TODO:** add one sentence on why this team cares, if there is a true one. Leave it out otherwise.

## What it does

Helm turns a regular webcam into a full Xbox 360 controller.

- **Pick your profile and go.** A profile screen like a streaming app's: a shared Default for anyone, or
  your own profile that keeps your setup.
- **Head movement is the analog stick.** A hands-free calibration (about a minute, spoken prompts, no
  clicks) measures how far you can comfortably turn, so a small movement can still mean full stick. A
  steering-sensitivity slider fine-tunes it live. There is also a two-second quick start for a new player.
- **Expressions are buttons.** An eyebrow raise fires an item, a smile is nitro, mouth open wide is look back.
  Calibration checks which expressions work for *you*.
- **It learns your own moves.** Calibration ends by training Helm's own model on your nod, which becomes a
  button. Teach it any other movement in five tries; it also learns your "everyday face" so talking never fires.
- **Breath is one more input.** A straw on a pressure sensor gives an analog sip-to-brake and puff-to-go.
- **Tell the Captain.** An AI agent on Claude: type "my jaw gets tired" or "steering needs too much head
  turning", and it reads the game's controls and your abilities, then changes only what you asked, in about
  five seconds, with Apply and Undo.
- **Face ID.** Only you control your profile; other faces in view are ignored. In two-player mode, each
  recognized player drives their own controller.
- **It keeps adapting.** If a gesture weakens as you tire, Helm lowers its threshold and tells you.

Helm appears to Windows as a real controller, so it works with any game that accepts one, with no
mods. Closing your eyes for two seconds pauses it. Tracking, Face ID and gestures run on the laptop: video
and face data never leave it (video is saved only when dev mode is explicitly enabled). Only gesture
names and numbers go to the Captain.

## How we built it

One Python process and a React dashboard.

- **Vision:** OpenCV capture into MediaPipe Face Landmarker, which gives head pose and 52
  expression scores per frame.
- **Signal:** each player's neutral pose and range are removed and scaled, then smoothed with a One Euro filter.
- **Gestures:** thresholds with hysteresis, minimum hold and a refractory period, plus a
  personalized logistic classifier (scikit-learn) with feature selection, a "none" class, distance
  rejection and temporal confirmation for learned gestures.
- **Output:** a virtual Xbox 360 controller through vgamepad and ViGEmBus, with keyboard emulation as a fallback.
- **Breath:** an Arduino streams raw pressure over USB serial; a hands-free breath calibration sets each
  player's range, and all thresholds live on the laptop.
- **Face ID:** OpenCV's SFace recognizer, learned during calibration from your relaxed face and head
  turns. Tracking runs at full frame rate while recognition checks about six times a second beside it,
  following the verified face in between.
- **Captain:** Claude through the player's own Claude Code login. Everything it needs is in one prompt
  (the game's controls, the player's abilities, the current mapping). It answers with a short list of
  changes, and Helm applies and validates them, so it can never wipe the player's tuning. A LangChain
  deepagents agent (tools: read the controls, read the player report, check a mapping, submit) is the API
  backend, and a rule-based coach is the offline fallback.
- **Dashboard:** FastAPI WebSocket to React, Vite and TypeScript. It runs calibration with no
  clicks and shows every input as it fires.

Control stages hand off through "latest value" slots, so a slow consumer drops stale frames
instead of adding lag. Optional dev recording uses a bounded background queue. Every frame is timestamped at capture, after inference and after the
controller write, so latency is measured rather than estimated.

## Challenges we ran into

- **Smoothing versus lag.** The filter settings we started with lagged a head turn by about a
  quarter of a second in simulation. Steering needed a much more responsive setting, with the dead
  zone absorbing the jitter instead.
- **Left and right.** The expression scores refer to the player's own face, so mirroring the
  camera image before tracking silently swaps them. Helm mirrors only the preview.
- **Breath events are instantaneous.** A puff arrives as a single event, so the minimum-hold rule
  that protects expression buttons would have blocked every breath command. Breath needed its own rule.
- **Talking.** Speech moves the same muscles as deliberate gestures. That is why every player
  records a "don't fire" class.
- **Faces are not all the same.** Pucker, cheek puff and nose scrunch barely registered for us on a
  real webcam, so we replaced the fixed fourth gesture with one Helm learns per player: the nod.
- **False triggers.** Smiling lifts the jaw score; turning your head shifts expression scores. We scale every
  expression to the player's range, hold back side effects, and require a short hold.
- **Face ID cost frames.** Running recognition on every frame dropped us to 5-11 fps with people behind the
  player. Moving it beside the tracker, and following the verified face between checks, brought it back
  to full frame rate.
- **An agent that doesn't wreck your setup.** Our first coach rebuilt the whole mapping (and took 90 s). Now
  it returns only changes, which Helm applies, in about five seconds.

## Accomplishments that we're proud of

- **TODO (needs the demo):** a person sat down, calibrated without help, and finished a race hands-free.
- **22× fewer accidental presses.** While people read aloud, chatted and watched a video, Helm fired 3 false presses per minute, beside 67 for a fixed threshold (median, n = 3, three minutes each). Across all nine minutes: 24 against 520, a 95% reduction for every participant. Blinks and eyebrow movements caused 456 of the baseline's false presses and none of Helm's.
- **It learns a move from five tries.** A move each person invented was recognized on 80% of tries the model had not seen (median, n = 3; 80, 80 and 100%), and the built-in nod on 100%.
- **It keeps up.** 29.8 frames per second on a Windows laptop webcam, with face tracking taking 7.2 ms per frame.
- Calibration runs with no mouse and no keyboard, start to finish.

## What we learned

- Measuring is a feature. Stamping every frame made tuning a matter of reading numbers.
- Per-player scaling matters more than a better model: the same tracker feels unusable or natural
  depending on whether its range matches the person.
- Design for the person's actual body, not the average one: a gesture you can learn beats a gesture we
  picked.
- An AI agent is most useful when it is constrained: small, validated changes the player can undo.

## What's next for Helm

- **Testing with real users.** No one who tried Helm this weekend has a motor impairment; our
  restricted-range test is a proxy, not a substitute. The first step is reaching out to
  organizations such as AbleGamers and Makers Making Change.
- An open-source release, a Linux backend, a mouse-and-keyboard mode, and a shared library of per-game profiles.
- Beyond games: the same pipeline for desktop navigation and communication shortcuts.
- Helm stays free for players.

## Built with

Python, MediaPipe, OpenCV, scikit-learn, NumPy, SciPy, vgamepad, ViGEm, FastAPI, React, Vite,
TypeScript, Arduino, LangChain deepagents, Claude, Claude Code

---

## Submission checklist

- [ ] Every TODO above resolved or deleted
- [ ] Public GitHub repo link
- [ ] Demo video, about 2:40 (script: `docs/PITCH.md`); check the event's length limit
- [ ] Screenshots: dashboard, calibration prompt, the numbers slide, the hardware
- [ ] Every entered prize ticked: Entertainment track, Best Hardware Hack, Best Practical AI
      Innovation, Best Physical AI Hack, Best use of deepagents
- [ ] Wording check: "designed for" and "proxy test"; no claim that Helm was tested with disabled users
