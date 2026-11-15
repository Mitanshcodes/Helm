// OWNER: P4
// The calibration card shown over the blurred moves panel: step chips (NEUTRAL, RANGE, MOVES), the engine's
// prompt in large type, a 10-segment bar for the step, and a live detail line. Steps advance by themselves.
import { useRef } from "react";
import { degrees, humanize } from "../format";
import type { HelmState, Progress } from "../types";

const RANGE_STEPS = ["yaw_left", "yaw_right", "pitch_up", "pitch_down"];
const EXPR_STEPS: [string, string, string[]][] = [
  ["brow_raise", "EYEBROWS", ["browInnerUp"]],
  ["jaw_open", "JAW", ["jawOpen"]],
  ["smile", "SMILE", ["mouthSmileLeft", "mouthSmileRight"]],
  ["nod_up", "NOD", []], // a learned move: the engine trains Helm's own model on these nods
];
export type CalMode = "full" | "quick" | "breath";
export interface BreathResult {
  puff: number; // millivolts above rest at the hardest puff
  sip: number;
}

// The engine runs the breath steps (sipnpuff.BreathCalibrator) straight after the face steps when a sensor is
// attached, or alone from "Measure my breath".
const isBreath = (step: string) => step.startsWith("breath");

function chipsFor(mode: CalMode, breathConnected: boolean): string[] {
  if (mode === "quick") return ["NEUTRAL"];
  if (mode === "breath") return ["BREATH"];
  return breathConnected ? ["NEUTRAL", "RANGE", "MOVES", "BREATH"] : ["NEUTRAL", "RANGE", "MOVES"];
}

function groupOf(step: string, chips: string[]): number {
  const name = step === "neutral" ? "NEUTRAL" : RANGE_STEPS.includes(step) ? "RANGE" : isBreath(step) ? "BREATH" : "MOVES";
  return Math.max(0, chips.indexOf(name));
}

const HINT: Record<string, string> = {
  neutral: "LOOK STRAIGHT · HOLD STILL",
  yaw_left: "TURN LEFT ←",
  yaw_right: "TURN RIGHT →",
  pitch_up: "CHIN UP ↑",
  pitch_down: "CHIN DOWN ↓",
  breath_rest: "HANDS OFF THE TUBE",
  breath_sip: "SIP HARD · HOLD",
  breath_puff: "PUFF HARD · HOLD",
};
export const cameraHint = (progress: Progress | null) =>
  progress
    ? progress.step === "nod_up"
      ? "CHIN UP · HOLD · 3 TIMES"
      : HINT[progress.step] ?? (EXPR_STEPS.some(([s]) => s === progress.step) ? "MAKE THE FACE · 3 TIMES" : null)
    : null;

export interface Track {
  yaw: [number, number];
  pitch: [number, number];
  steps: string[]; // calibration steps seen, in order
}

/** Remembers how far the head went each way and which steps ran, for the detail line and the summary. */
export function useCalibrationTrack(state: HelmState | null, calibrating: boolean): Track {
  const track = useRef<Track>({ yaw: [0, 0], pitch: [0, 0], steps: [] });
  const step = state?.progress?.step;
  if (calibrating && step) {
    const t = track.current;
    if (step === "neutral" && t.steps.length > 0 && t.steps[t.steps.length - 1] !== "neutral") {
      track.current = { yaw: [0, 0], pitch: [0, 0], steps: [] }; // a new calibration started
    }
    const now = track.current;
    if (now.steps[now.steps.length - 1] !== step) now.steps.push(step);
    if (state?.face && RANGE_STEPS.includes(step)) {
      now.yaw = [Math.min(now.yaw[0], state.raw.yaw), Math.max(now.yaw[1], state.raw.yaw)];
      now.pitch = [Math.min(now.pitch[0], state.raw.pitch), Math.max(now.pitch[1], state.raw.pitch)];
    }
  }
  return track.current;
}

function Segments({ value }: { value: number }) {
  const n = Math.round(Math.max(0, Math.min(1, value)) * 10);
  return (
    <div className="bar big" role="img" aria-label={`This step is ${Math.round(value * 100)} percent done`}>
      {Array.from({ length: 10 }, (_, i) => (
        <span key={i} className={i < n ? "seg on" : "seg"} />
      ))}
    </div>
  );
}

function detail(progress: Progress, track: Track, breath: number): string {
  const step = progress.step;
  if (isBreath(step)) return `BREATH ${breath < 0 ? "SIP" : breath > 0 ? "PUFF" : ""} ${Math.round(Math.abs(breath) * 100)}%`;
  if (step === "neutral") return "Learning your resting face…";
  if (step.startsWith("yaw")) return `LEFT ${degrees(track.yaw[0])}    RIGHT ${degrees(track.yaw[1])}`;
  if (step.startsWith("pitch")) return `UP ${degrees(track.pitch[1])}    DOWN ${degrees(track.pitch[0])}`;
  const at = EXPR_STEPS.findIndex(([s]) => s === step);
  if (at < 0) return "";
  return EXPR_STEPS.map(([, label], i) => `${label} ${i < at ? "✓" : i === at ? "…" : "·"}`).join("    ");
}

export function CalibrationCard(props: { state: HelmState; progress: Progress; mode: CalMode; track: Track; onSkip?: () => void }) {
  const { state, progress, mode, track, onSkip } = props;
  const chips = chipsFor(isBreath(progress.step) && mode === "quick" ? "breath" : mode, state.breath_connected);
  const group = groupOf(progress.step, chips);
  return (
    <div className="setup-card">
      <div className="card-top">
        <h2 className="card-title">
          CALIBRATING · STEP {group + 1} OF {chips.length}
        </h2>
        <ol className="chips">
          {chips.map((c, i) => (
            <li key={c} className={i < group ? "chip done" : i === group ? "chip now" : "chip"}>
              {i < group ? `✓ ${c}` : c}
            </li>
          ))}
        </ol>
      </div>
      <p className="instruction" role="status" aria-live="polite">
        {progress.prompt}
      </p>
      <Segments value={progress.progress} />
      <p className="detail">{detail(progress, track, state.breath ?? 0)}</p>
      <hr className="dashed" />
      <div className="card-foot">
        <span>Your moves unlock when this is done.</span>
        {onSkip && (
          <button className="btn small" onClick={onSkip}>
            Skip calibration
          </button>
        )}
      </div>
    </div>
  );
}

export interface CustomResult {
  name: string;
  accuracy: number | null; // leave-one-take-out, 0..1, once the model is trained
}

export interface FaceIdResult {
  saved: boolean;
  reason: string;
}

export function CalibrationDone(props: { state: HelmState; mode: CalMode; track: Track; breath: BreathResult | null; custom?: CustomResult | null; faceId?: FaceIdResult | null }) {
  const { state, mode, track, breath, custom, faceId } = props;
  const reliable = new Set(state.gestures?.reliable ?? []);
  const faces = EXPR_STEPS.filter(([, , sources]) => sources.length > 0);
  const found = faces.filter(([, , sources]) => sources.some((s) => reliable.has(s)));
  const weak = faces.filter(([step, , sources]) => track.steps.includes(step) && !sources.some((s) => reliable.has(s)));
  const onX = state.mapping?.buttons?.some((b) => b.target === "X" && b.gesture === custom?.name);
  const breathPart = breath ? [`Breath: puff ${Math.round(breath.puff)} mV, sip ${Math.round(breath.sip)} mV`] : [];
  const parts =
    mode === "breath"
      ? breathPart
      : mode === "quick"
        ? ["Quick setup", "resting face learned"]
        : [
            `Range ${degrees(track.yaw[0])} to ${degrees(track.yaw[1])}`,
            `${found.length} ${found.length === 1 ? "move" : "moves"} found`,
            ...(weak.length ? [`${weak.map(([, l]) => l).join(", ")} too weak`] : []),
            ...breathPart,
            ...(faceId ? [faceId.saved ? "Face ID on: only you control this profile" : faceId.reason] : []),
            ...(custom
              ? [`${humanize(custom.name)} learned${custom.accuracy !== null ? ` (${Math.round(custom.accuracy * 100)}% recognized)` : ""}${onX ? " · on X" : ""}`]
              : []),
          ];
  return (
    <div className="setup-card">
      <h2 className="card-title">CALIBRATION DONE</h2>
      <p className="instruction" role="status" aria-live="polite">
        {mode === "breath" ? "All set! HELM measured your breath." : "All set! HELM learned your face."} Unlocking your dashboard…
      </p>
      <Segments value={1} />
      <p className="detail">{parts.join(" · ")}</p>
    </div>
  );
}
