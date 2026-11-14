// OWNER: P4
// The "teach a gesture" flow: name it, learn the player's everyday face (once per player), then record the
// movement. The steps and their timing come from P3's TakeRecorder through `progress`; nothing here assumes
// how long a step lasts, so the recording times can change without touching the dashboard.
import { useCallback, useRef, useState } from "react";
import type { Command, EventMsg, Trained } from "./types";

// Step names agreed with P3 (`Progress.step` while recording).
export const STEP_NEUTRAL = "neutral";
export const STEP_READ = "read_aloud";
export const isTakeStep = (step: string) => /^take_\d+$/.test(step);
export const takeNumber = (step: string) => Number(step.split("_")[1]);

export type Stage = "face" | "move";

export interface TeachFlow {
  name: string; // the gesture being taught
  stage: Stage;
  withFace: boolean; // true when this run includes the everyday-face recording
}

/** Drives the two recordings in order and remembers which players already have an everyday face recorded. */
export function useTeachFlow(send: (cmd: Command) => void) {
  const [flow, setFlow] = useState<TeachFlow | null>(null);
  const [trained, setTrained] = useState<Trained | null>(null);
  const faceDone = useRef(new Set<string>()); // players whose everyday face was recorded in this session
  const flowRef = useRef(flow);
  flowRef.current = flow;

  const start = useCallback(
    (name: string, withFace: boolean) => {
      setTrained(null);
      setFlow({ name, stage: withFace ? "face" : "move", withFace });
      send(withFace ? { cmd: "record_negative" } : { cmd: "record_gesture", name });
    },
    [send],
  );

  /** Call for every server event. Returns true when the event belonged to the flow. */
  const onEvent = useCallback(
    (msg: EventMsg, player: string) => {
      const current = flowRef.current;
      if (msg.name === "gesture_trained") {
        const result = msg.data as unknown as Trained;
        if (result.name === "none") {
          faceDone.current.add(player);
          if (current?.stage === "face") {
            setFlow({ ...current, stage: "move" });
            send({ cmd: "record_gesture", name: current.name });
          } else setTrained(result);
          return true;
        }
        setTrained(result);
        if (current && result.name === current.name) setFlow(null);
        return true;
      }
      if (msg.name === "profile_loaded" || msg.name === "error" || msg.name === "calibration_done") {
        // Anything that replaces the recording ends the flow; the server never resumes it.
        if (msg.name === "profile_loaded") setTrained(null);
        setFlow(null);
      }
      return false;
    },
    [send],
  );

  const reset = useCallback(() => setFlow(null), []);
  const hasFace = useCallback((player: string) => faceDone.current.has(player), []);
  return { flow, trained, start, onEvent, reset, hasFace };
}
