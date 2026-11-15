<!-- OWNER: P4 -->
# Demo video script (superseded)

The current video script, live demo run of show and Q&A are in [PITCH.md](PITCH.md). The old script below
describes an earlier build (jaw throttle, the old coach); do not record from it.

## Earlier script

Target length 1:50. Record the screen and the player in one shot where possible, so viewers see
the face and the kart move together. Hands stay visibly in the lap throughout.

| Time | Picture | Voice-over |
|---|---|---|
| 0:00–0:12 | Close on the player, hands in lap, racing SuperTuxKart. The overlay window sits beside the game. | "Every adaptive controller on the market still assumes you can press something. This kart is being driven with a face." |
| 0:12–0:30 | Split: player's face and the overlay. Head turns, the steering dot follows. Jaw opens, the throttle bar rises. Eyebrow raise, the A badge lights and an item fires. | "Head steers. The jaw is the throttle, so half open is half speed. Eyebrows fire an item. Helm shows up as a real Xbox controller, so the game needs no changes." |
| 0:30–0:50 | Full dashboard. A new person sits down. The calibration prompts advance by themselves. | "Setup takes about thirty seconds and no clicks. Helm measures how far you can comfortably move, so a small movement can still mean full stick." |
| 0:50–1:10 | "Teach a gesture": five takes of a one-sided smile, then the "talk, look around" step, then the accuracy readout. The player talks; nothing fires. They smile; X fires. | "It learns your gestures from five takes, then learns what not to fire on. Talking does nothing. The gesture does." |
| 1:10–1:22 | Close on the straw and sensor. A hard puff latches the throttle; a sip brakes. The sip-and-puff chips light. | "A straw and a pressure sensor add breath: puff to go, sip to brake." |
| 1:22–1:34 | Coach panel: "Build my mapping", the proposed table and its reasons, Accept. | "A coach agent reads the game's controls and your reliable gestures, builds the mapping, checks it, and revises it after you play." |
| 1:34–1:46 | The numbers slide (`/slides.html#5`). | "We measured it: latency beside a real controller, false triggers beside a fixed threshold, and control with small movements beside fixed gain." Say the three measured numbers here. |
| 1:46–1:50 | Title slide. | "It runs on a webcam you already own, and it's free. This is Helm." |

## Before recording

- Numbers in `ui/src/results.ts` are filled in from P3's analysis. If any is still missing, cut
  the 1:34 segment to the ones that exist; never say an unmeasured number.
- Use the `demo` profile for the racer and `?overlay=1` beside the game.
- State once, on screen or in voice, that the evaluation used a restricted-range proxy and no
  participant had a motor impairment. The slide's footnote covers this if it is readable in the shot.
- A fresh straw for whoever is on camera.
- Say "designed for"; do not say Helm helps patients.

## Shots to grab as stills for Devpost

Dashboard mid-race, the calibration prompt, the numbers slide, the hardware on its mount.
