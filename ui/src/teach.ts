// OWNER: P4
// The "teach your own move" flow. It runs at the top of the page, in the same place as calibration:
//   intro (name it) -> get ready -> everyday face (once per player) -> get ready -> your move -> result.
// The "get ready" pauses belong to the dashboard so nobody is thrown straight into a recording. The recording
// steps and their timing come from P3's TakeRecorder through `progress`; nothing here assumes how long they last.
import { useCallback, useEffect, useRef, useState } from "react";
import type { Command, EventMsg, Trained } from "./types";

// Step names agreed with P3 (`Progress.step` while recording). Takes may carry a phase suffix.
export const STEP_NEUTRAL = "neutral";
export const STEP_READ = "read_aloud";
const TAKE = /^take_(\d+)(?:_(ready|go|relax))?$/;
export const isTakeStep = (step: string) => TAKE.test(step);
export const takeNumber = (step: string) => Number(TAKE.exec(step)?.[1] ?? 0);
export const takePhase = (step: string) => TAKE.exec(step)?.[2] ?? null;

export const READY_MS = 5000; // pause before each recording; Enter or "Start now" skips it
// What the button promises. Mirrors config.TAKES (5) and the take timing in P3's TakeRecorder; update with them.
export const TAKES_LABEL = "5 takes · about 40 s";

export type Stage = "intro" | "ready_face" | "face" | "ready_move" | "move" | "result";

export interface TeachFlow {
  stage: Stage;
  name: string; // the move being taught (empty during intro)
  withFace: boolean; // this run includes the everyday-face recording
  readyUntil: number; // performance.now() deadline while in a ready stage
  result: Trained | null;
}

const recording = (stage: Stage) => stage === "face" || stage === "move";

export function useTeachFlow(send: (cmd: Command) => void) {
  const [flow, setFlow] = useState<TeachFlow | null>(null);
  const faceDone = useRef(new Set<string>()); // players whose everyday face was recorded in this session
  const flowRef = useRef(flow);
  flowRef.current = flow;

  const offer = useCallback(() => setFlow({ stage: "intro", name: "", withFace: false, readyUntil: 0, result: null }), []);

  const begin = useCallback((name: string, withFace: boolean) => {
    setFlow({ stage: withFace ? "ready_face" : "ready_move", name, withFace, readyUntil: performance.now() + READY_MS, result: null });
  }, []);

  /** Leave a "get ready" pause and start recording now. */
  const go = useCallback(() => {
    const current = flowRef.current;
    if (current?.stage === "ready_face") {
      send({ cmd: "record_negative" });
      setFlow({ ...current, stage: "face" });
    } else if (current?.stage === "ready_move") {
      send({ cmd: "record_gesture", name: current.name });
      setFlow({ ...current, stage: "move" });
    }
  }, [send]);

  // Ready pauses end by themselves, so the flow needs no clicks once started.
  useEffect(() => {
    if (flow?.stage !== "ready_face" && flow?.stage !== "ready_move") return;
    const t = window.setTimeout(go, Math.max(0, flow.readyUntil - performance.now()));
    return () => window.clearTimeout(t);
  }, [flow, go]);

  /** Call for every server event. Returns true when the event was consumed by the flow. */
  const onEvent = useCallback((msg: EventMsg, player: string) => {
    const current = flowRef.current;
    if (msg.name === "gesture_trained") {
      const result = msg.data as unknown as Trained;
      if (result.name === "none") {
        faceDone.current.add(player);
        if (current?.stage === "face") setFlow({ ...current, stage: "ready_move", readyUntil: performance.now() + READY_MS });
      } else if (current?.stage === "move" && result.name === current.name) {
        setFlow({ ...current, stage: "result", result });
      }
      return true;
    }
    if (msg.name === "profile_loaded" || (msg.name === "error" && current && recording(current.stage))) setFlow(null);
    return false;
  }, []);

  const close = useCallback(() => setFlow(null), []);
  const hasFace = useCallback((player: string) => faceDone.current.has(player), []);
  return { flow, offer, begin, go, close, onEvent, hasFace };
}
