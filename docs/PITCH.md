<!-- OWNER: P4 (written by P1 at the user's request, 2026-11-15) -->
# Helm: story, video script, live demo, Q&A

One page for the whole team. The video is about 2:40, the live demo 3:00, and the Q&A 3:00.

---

## 1. The story in one breath

> **Every adaptive controller still assumes you can press something. Helm turns the webcam you already own
> into a real Xbox controller you drive with your face, your head and your breath. It learns *your* range and
> *your* moves, ignores you when you talk, and costs nothing.**

The spine, in the order the judge hears it (the reviewer's structure: problem, then the person, then how, then
why it matters):

1. **Who it's for.** People who can't use their hands well enough to hold a controller: spinal cord injury, ALS,
   muscular dystrophy, cerebral palsy, arthritis, stroke. Gaming is how their friends hang out, and they're left
   on the couch watching.
2. **How big the problem is.**
   - **1.3 billion people** (16% of the world) live with a significant disability (WHO).
   - **46 million gamers with disabilities in the US alone** (AbleGamers, 2019). Microsoft estimates **over
     400 million** worldwide.
   - Today's answers: the Xbox Adaptive Controller (about $100) still needs you to *press* something, and mouth
     controllers like the QuadStick cost **$500+**.
3. **Designed around the player, not around us.** Every feature exists because of a real limitation:

   | The player's reality | What Helm does |
   |---|---|
   | Small or uneven range of motion | Calibration measures *your* range; a small turn can be full lock. The steering slider adjusts it live. |
   | Can't press, can't hold | Head steers; expressions press; sip and puff on a straw give brake and throttle. |
   | Not everyone can make every face | It checks which expressions work *for you*, and you can teach it any move in five tries. |
   | Talking, laughing and coughing shouldn't press buttons | It learns your "everyday face" and filters it out; side effects (a smile lifting the jaw) are held back. |
   | Gets tired over a session | Thresholds adapt as a move weakens. |
   | Can't fiddle with settings | Just tell the Captain in plain words: "my jaw gets tired". |
   | Wants to play *with* friends | Face ID: only you control your profile; two players each get their own controller. |
   | Can't afford $500 hardware | A webcam you own, free software, an optional cheap Arduino straw sensor. |
   | Privacy | Video never leaves the laptop. |

4. **How we built it** (one line each):
   - **Vision:** MediaPipe tracks 478 face points and 52 expressions at 30 fps.
   - **Calibration:** per-player, about a minute, hands-free. Spoken prompts advance by themselves.
   - **Your own model:** a personal gesture model trained on *your* moves; the nod you do in calibration becomes
     a button.
   - **Output:** a virtual Xbox 360 pad (ViGEm), so *any* game works unchanged.
   - **Breath:** an Arduino plus a pressure sensor: analog sip and puff.
   - **Face ID:** SFace face recognition, so only you drive your profile and two players get two controllers.
   - **The Captain:** an agent on Claude that reads the game's controls and your abilities, and edits your mapping
     from a sentence in about 5 s.
5. **Why it matters.** It turns "watch your friends play" into "play with your friends", for free, on hardware
   people already own.

### Numbers we can say (and how to say them honestly)

| Claim | Status | How to say it |
|---|---|---|
| False triggers while talking | **Measured, n = 3, Windows laptop** | "While people read aloud, chatted and watched a video, Helm pressed something by accident 3 times a minute. A plain threshold: 67. That's 22 times fewer, a 95% cut for every person." |
| Learned moves | Measured, n = 3 | "A move each person invented was recognized 80% of the time on tries the model had never seen; the nod, 100%." |
| Software delay | Measured on the dev machine | "About 10 milliseconds from camera frame to controller inside Helm." Never call it end-to-end latency. |
| Frame rate | Measured | "30 frames a second on the Windows laptop, 7 milliseconds of face tracking per frame." |
| Captain speed | Measured | "Plain-English changes in about 5 seconds." |
| Calibration | Measured | "About a minute, no hands; a 2-second quick start for a new person." |
| End-to-end latency, pointing throughput | **Not measured** | Do not mention. If asked: "That's the next measurement; the tools are built." |

Never say we tested with people with motor impairments: we haven't (see Q&A).

---

## 2. Video script (about 2:40)

**Cast:** Mitansh (the player, limited hand mobility), Friend A (walks in with him), Friends B and C (on the couch,
playing SuperTuxKart with controllers). **Tone:** real, warm, not pity. Keep Mitansh's portrayal understated:
hands resting in his lap, no exaggerated acting.

| Time | Picture | Sound / voice-over (VO) |
|---|---|---|
| **0:00–0:06** | Hallway. Mitansh and Friend A walk and chat; his hands rest still at his sides or in his jacket. | Ambient. A: "...so they started without us?" |
| **0:06–0:14** | They enter the room. Friends B and C are mid-race, yelling, controllers in hand. B: "Get in, next race!" B holds out a controller. Mitansh looks at it, then at his hands. A beat. | Game audio and laughter. Mitansh, quietly: "...I'll just watch." |
| **0:14–0:20** | Friend A puts a hand on his shoulder, opens a laptop, smiles. | A: "Nah. Helm's got you." Music hits. **Title card: HELM.** |
| **0:20–0:42** | Text cards over slow-motion B-roll of the controllers: **"1.3 billion people live with a significant disability"** · **"46 million gamers with disabilities in the US alone"** · **"Adaptive controllers: $100 to $500+, and most still need you to press something."** | VO: "One in six people on Earth lives with a significant disability. In the US alone, forty-six million of them are gamers. The controllers built for them still cost hundreds of dollars, and most still assume you can press a button. For millions of people, game night means watching." |
| **0:42–0:55** | Screen recording: the profile screen ("who's at the helm?"). Mitansh picks New profile and types his name. | VO: "So we built Helm around one person: someone who can't use their hands. Everything it does, it does without them." |
| **0:55–1:15** | Calibration, sped up 3×: the camera with the face mesh, prompts advancing by themselves (turn left, right, raise eyebrows, smile, nod), then the done card: "Nod up learned · on X", "Face ID on". | VO: "Helm uses the webcam you already own. In about a minute, with no hands, it learns how far you can move, which expressions work *for you*, and even trains its own model on a move you choose. It learns your face too, so only you control your profile." |
| **1:15–1:40** | Split screen: Mitansh's face on one side, the game on the other. Head turns and the kart steers; eyebrows and an item fires; smile and nitro; nod and rescue. The controller graphic on the dashboard lights up in sync. | VO: "Head steers. Eyebrows fire. A smile is nitro. Helm appears to the computer as a real Xbox controller, so it works with any game, no changes." |
| **1:40–1:50** | Mitansh talks and laughs at his friends while racing. A caption reads "talking: nothing fires", then the card **"22× fewer accidental presses"**. | VO: "And it knows the difference between a gesture and a conversation. While people talked, it pressed something by accident 22 times less often than a plain face tracker." |
| **1:50–2:00** | Close-up on the straw: a sip brakes, a puff accelerates; the trigger bars fill on the dashboard. | VO: "Add a straw and a cheap pressure sensor, and breath becomes an analog brake and throttle." |
| **2:00–2:12** | Screen: the Anchor, then the Captain. Type "steering needs too much head turning". The steps appear, then "steering sensitivity 1.0 → 2.0", then Apply. | VO: "Don't want to dig through settings? Just tell the Captain, our AI agent. It reads the game's controls and your abilities, and changes only what you asked, in seconds." |
| **2:12–2:28** | Back in the room. Multiplayer: Mitansh and Friend B both on face control, each with their own controller (two pad graphics, each labeled with a name); the friends cheer; Mitansh crosses the finish line. | VO: "Face ID routes each player to their own controller. So he's not watching anymore. He's racing his friends." |
| **2:28–2:40** | The four friends on the couch, laughing. Fade to the title card: **"Helm: play with whatever moves you have."** Then the URL. | VO: "Helm. Free, private, and built on a webcam you already own. Play with whatever moves you have." |

**Shot list to grab** (do these first, in this order): (1) the skit in one or two takes; (2) the calibration screen
recording (full, sped up in editing); (3) the race with face cam and game side by side; (4) "talking while racing";
(5) a straw close-up; (6) the Captain screen recording; (7) the multiplayer finish; (8) the couch closing shot.

**Editing notes:** captions on everything (accessibility, and judges watch muted); keep VO lines exactly as written;
music under, ducked for VO; put the stats on screen as large text cards.

---

## 3. Live demo: 3:00, exact run of show

**Roles:** **Driver** (Mitansh, plays with his face and doesn't touch the laptop), **Speaker** (tells the story, one
hand on the laptop only for the Captain step), **Backup** (watches the dashboard and fixes things silently).

**Before judges arrive** (every time):
- Mitansh's profile loaded and calibrated earlier, with Face ID on and the nod on X.
- **Accelerate is set:** RT on Always on (Mapping), or a puff on RT (on/off).
- The game is in the middle of a race.
- The dashboard is on a second screen.
- The sensor is plugged in.

| Time | Speaker says | Driver / screen |
|---|---|---|
| **0:00–0:25 Problem** | "One in six people on Earth lives with a significant disability: 46 million gamers in the US alone. The controllers made for them cost $100 to $500, and almost all of them still need you to press something. If your hands don't work, game night means watching your friends play. We built Helm so that doesn't happen." | Driver already racing, hands visibly in lap. |
| **0:25–0:40 The person** | "We designed it around one person who can't use their hands. Every part of it works without them: setup, playing, even changing settings." | Driver keeps racing. |
| **0:40–1:20 Watch it** | "Mitansh is steering with his head: a small turn, because Helm learned *his* range. Eyebrows fire an item. A smile is nitro. And that nod? Helm trained its own model on *his* nod during setup; it's his rescue button. The game has no idea: Helm looks like a normal Xbox controller." | Driver: turn, eyebrows (item), smile (nitro), nod (rescue). Point at the controller graphic lighting up. |
| **1:20–1:35 Talking does nothing** | "Mitansh, say hi." | Driver talks to the judges, laughs, keeps steering: nothing fires. Speaker: "It learned his everyday face. We measured it with three people: 3 accidental presses a minute while talking, against 67 for a plain face tracker. 22 times fewer." |
| **1:35–1:50 Breath** | "Not everyone can move their face much either, so we built a sip-and-puff straw." | Driver sips (brake bar), puffs (throttle). |
| **1:50–2:15 The Captain** | "Settings are a wall for someone who can't use a mouse well. So you just say it." Type into the Captain: **"steering needs too much head turning"**. "Our agent reads the game's controls and his abilities and changes only that, in about five seconds." Apply. | Show the steps, then "steering sensitivity → 2.0", then the Apply button. Driver: "Oh, way easier." |
| **2:15–2:35 Only him** | "Helm knows who's playing." Backup leans into the camera next to Mitansh. "That's not Mitansh, so Helm ignores him completely. And in multiplayer, each person gets their own controller." | Backup's face in frame: no control change. (Optional: flip to the Multiplayer screen if it's set up.) |
| **2:35–3:00 Why it matters** | "Built in 36 hours: MediaPipe face tracking, per-player calibration, a personal gesture model, Face ID, an Arduino breath sensor, and a Claude-powered agent, all running locally. Video never leaves the laptop. Helm turns the webcam you already own into a controller, for free. Want to try it?" | Hand the seat to a judge: **Default → Skip calibration** (2 s), and they're steering. |

**If something breaks:** say "live demos" with a smile and keep talking. Have the backup video ready to play.
Face ID won't recognize the driver? Anchor → Profile → Turn off Face ID (5 s). Captain offline? Skip the step and
say "it also works offline with a built-in coach."

---

## 4. Q&A bank (3:00): short answers

- **"Is it fast enough to play?"** "Inside Helm it's about 10 ms from camera frame to controller, at 30 frames a
  second. A webcam adds its own delay. A full end-to-end measurement against a real controller is next."
- **"How do you stop accidental presses?"** "Four layers: each move is scaled to *your* range; it needs to be held
  past a threshold for a beat; when one expression causes another (a smile lifts the jaw) only the real one
  fires; and your personal model learns your everyday face as 'nothing'. With three people talking, reading
  and watching video: 3 accidental presses a minute against 67, 95% fewer for every one of them."
- **"What if someone can't move their head or face much?"** "Every input is optional and per person: breath
  alone works, small movements are scaled up, and you can teach any movement you *can* make in five tries."
- **"Have you tested with people with disabilities?"** Be honest: "Not yet. We built it in 36 hours. Our next
  step is co-designing with occupational therapists and groups like AbleGamers, and that's exactly why the setup
  is per-person and adjustable by voice-free text."
- **"How is this different from head-mouse software or eye trackers?"** "Those move a cursor. Helm is a full game
  controller: analog stick, buttons and triggers, it learns custom gestures, it filters false triggers, adds
  breath, and it's free on a normal webcam. Eye trackers cost hundreds and take your eyes off the game."
- **"Why an AI agent?"** "Configuring is the hardest part for this user. The Captain takes a sentence ('my jaw gets
  tired') and makes the smallest safe change. Helm validates every change, so it can't break your setup."
- **"Privacy?"** "Everything runs on the laptop. Video and face data never leave it; only gesture names and numbers
  go to the Captain."
- **"Business model?"** "Free and open source for players. Partnerships with rehab clinics and accessibility
  nonprofits, and per-game profiles that the community shares."
- **"What about lighting or glasses?"** "MediaPipe is robust to both; calibration adapts to the person in their
  lighting, and you can recalibrate in a minute."
- **"Which games?"** "Any game that supports an Xbox controller on PC, because Helm *is* one. We demo SuperTuxKart."
- **"What was hardest?"** "Telling a gesture from a conversation, and keeping 30 frames a second with face
  recognition running. We moved recognition to a side thread and track faces in between."

---

## 5. Before submission (owner: whoever is free)

1. ~~Two more false-trigger runs~~ Done: n = 3 on Windows, 3.0 vs 67.4 a minute, in `ui/src/results.ts`.
2. **Devpost** (`docs/devpost.md`): fill the TODOs from section 1 of this file, then add the video link.
3. **Record the video now** using the shot list. Record the race take twice.
4. **Demo laptop:**
   - Claude logged in (`claude`), online for the Captain.
   - `python -m helm.identity download` run.
   - Discard local changes to `profiles/guest/gestures.npz` before any pull.
   - The backup video downloaded locally.

Sources for the numbers: [WHO via secondary source](https://voxbooster.com/blog/adaptive-gaming-controller-customization-statistics-2026/),
[AbleGamers 46 million (TechRadar)](https://techradar.com/news/how-ablegamers-the-xbox-adaptive-controller-and-apx-are-helping-millions-of-disabled-gamers-play-the-games-they-love),
[46 million (PocketGamer.biz, Devcom 2019)](https://www.pocketgamer.biz/devcom-2019-26-of-the-us-has-a-disability-that-affects-them-playing-games),
[Microsoft 400M estimate (secondary)](https://voxbooster.com/blog/gaming-accessibility-statistics-2026),
[QuadStick $500+ (Hollywood Reporter)](https://www.hollywoodreporter.com/news/jonny-lee-miller-reflects-his-hackers-1190595),
[Xbox Adaptive Controller price](https://www.pcgamer.com/how-the-xbox-adaptive-controller-will-change-the-lives-of-millions-of-players-with-disabilities-on-pc).
