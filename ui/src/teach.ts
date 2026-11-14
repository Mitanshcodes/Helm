// OWNER: P4
// The "teach your own move" flow. It runs in the focus view (instructions over a big camera), like calibration:
//   intro (name it) -> [get ready -> everyday face, once per player] -> your move, a few tries -> result.
// The recording steps and their timing come from P3's TakeRecorder through `progress`. Each try there is
// take_N_ready ("relax, then get ready"), take_N_go ("now, and hold") and take_N_relax ("and relax"). Two relax
// prompts in a row confused people into moving at the wrong time, so the dashboard shows a try's relax and the
// next try's ready as ONE step, "Relax, get ready", ending in a 3-2-1 countdown to GO (see `takeView`).
import { useCallback, useEffect, useRef, useState } from "react";
import { humanize } from "./format";
import type { Command, EventMsg, Progress, Trained } from "./types";

// Step names agreed with P3 (`Progress.step` while recording). Takes may carry a phase suffix.
export const STEP_NEUTRAL = "neutral";
export const STEP_READ = "read_aloud";
const TAKE = /^take_(\d+)(?:_(ready|go|relax))?$/;
export const isTakeStep = (step: string) => TAKE.test(step);
export const takeNumber = (step: string) => Number(TAKE.exec(step)?.[1] ?? 0);
export const takePhase = (step: string) => TAKE.exec(step)?.[2] ?? null;

export const READY_MS = 5000; // pause before the everyday-face recording; Enter or "Start now" skips it
// Mirrors of P3's config (TAKES, TAKE_READY_S); update with them. Used for the countdown and the labels only.
export const TAKES = 5;
export const TAKE_READY_S = 3;
export const TAKES_LABEL = "5 tries · about 40 s";

export type Stage = "intro" | "ready_face" | "face" | "move" | "result";

export interface TeachFlow {
  stage: Stage;
  name: string; // the move being taught (empty during intro)
  withFace: boolean; // this run includes the everyday-face recording
  readyUntil: number; // performance.now() deadline while in a ready stage
  result: Trained | null;
}

const recording = (stage: Stage) => stage === "face" || stage === "move";

/** What the player sees during a try: one "relax, get ready" step (relax + next ready), then GO, then done. */
export interface TakeView {
  phase: "prep" | "go" | "done";
  tryNo: number; // the try this step leads to (prep) or is (go)
  total: number;
  headline: string;
  sub: string;
  count: number | null; // 3, 2, 1 in the last seconds before GO
  bar: number; // 0..1 across the whole step as the player sees it
}

const RELAX_SHARE = 0.45; // of the merged "relax, get ready" bar

export function takeView(progress: Progress, move: string, total: number = TAKES): TakeView | null {
  const n = takeNumber(progress.step);
  const phase = takePhase(progress.step);
  if (!n || !phase) return null;
  const p = Math.max(0, Math.min(1, progress.progress));
  const what = humanize(move).toLowerCase();
  if (phase === "go") {
    const nudge = progress.prompt.startsWith("A little bigger");
    return { phase: "go", tryNo: n, total, headline: `${humanize(move)}: now! Hold it`, sub: nudge ? "A little bigger" : "Hold it until the bar is full", count: null, bar: p };
  }
  if (phase === "relax" && n >= total) {
    return { phase: "done", tryNo: n, total, headline: "Relax. That was the last one!", sub: "Helm is learning your move…", count: null, bar: p };
  }
  const next = phase === "relax" ? n + 1 : n;
  const first = phase === "ready" && n === 1;
  const count = phase === "ready" ? Math.max(1, Math.ceil((1 - p) * TAKE_READY_S)) : null;
  return {
    phase: "prep",
    tryNo: next,
    total,
    headline: `Relax, get ready to ${what}`,
    sub: count === null ? "Keep your face still and relaxed" : `Do it on GO in ${count}…`,
    count,
    bar: first ? p : phase === "relax" ? p * RELAX_SHARE : RELAX_SHARE + p * (1 - RELAX_SHARE),
  };
}

/** What to say aloud for a recording step, or null to stay quiet (the merged step is spoken once). */
export function spokenTake(progress: Progress, move: string, total: number = TAKES): string | null | undefined {
  const n = takeNumber(progress.step);
  const phase = takePhase(progress.step);
  if (!n || !phase) return undefined; // not a take: say the engine's prompt
  const what = humanize(move).toLowerCase();
  if (phase === "go") return progress.prompt.startsWith("A little bigger") ? `A little bigger. ${what}, and hold` : `${what} now, and hold`;
  if (phase === "relax") return n >= total ? "Relax. All done." : "Relax, and get ready for the next one.";
  return n === 1 ? `Relax, and get ready to ${what}.` : null;
}

export function useTeachFlow(send: (cmd: Command) => void) {
  const [flow, setFlow] = useState<TeachFlow | null>(null);
  const faceDone = useRef(new Set<string>()); // players whose everyday face was recorded in this session
  const flowRef = useRef(flow);
  flowRef.current = flow;

  const offer = useCallback(() => setFlow({ stage: "intro", name: "", withFace: false, readyUntil: 0, result: null }), []);

  // The move's own tries start with their own "relax, get ready" step, so there is no extra waiting card first.
  const recordMove = useCallback((current: TeachFlow) => {
    send({ cmd: "record_gesture", name: current.name });
    setFlow({ ...current, stage: "move" });
  }, [send]);

  const begin = useCallback((name: string, withFace: boolean) => {
    const next: TeachFlow = { stage: "ready_face", name, withFace, readyUntil: performance.now() + READY_MS, result: null };
    if (withFace) setFlow(next);
    else recordMove(next);
  }, [recordMove]);

  /** Leave the everyday-face "get ready" pause and start recording now. */
  const go = useCallback(() => {
    const current = flowRef.current;
    if (current?.stage === "ready_face") {
      send({ cmd: "record_negative" });
      setFlow({ ...current, stage: "face" });
    }
  }, [send]);

  // The ready pause ends by itself, so the flow needs no clicks once started.
  useEffect(() => {
    if (flow?.stage !== "ready_face") return;
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
        if (current?.stage === "face") recordMove(current);
      } else if (current?.stage === "move" && result.name === current.name) {
        setFlow({ ...current, stage: "result", result });
      }
      return true;
    }
    if (msg.name === "profile_loaded" || (msg.name === "error" && current && recording(current.stage))) setFlow(null);
    return false;
  }, [recordMove]);

  const close = useCallback(() => setFlow(null), []);
  const hasFace = useCallback((player: string) => faceDone.current.has(player), []);
  return { flow, offer, begin, go, close, onEvent, hasFace };
}
