// OWNER: P4
// The WebSocket protocol of docs/SPEC.md section 8, as TypeScript types.

export type Axis = "yaw" | "pitch" | "roll";
export type CalibrationMode = "full" | "quick";

export interface Progress {
  active: boolean;
  step: string;
  prompt: string;
  progress: number; // 0..1 within the step
  overall: number; // 0..1 across the whole flow
  done: boolean;
}

export interface HelmState {
  type: "state";
  fps: number;
  latency_ms: { vision: number; control: number; total: number };
  face: boolean;
  paused: boolean;
  breath_connected: boolean;
  profile: { player: string; game: string; calibrated: CalibrationMode | "default" | null };
  raw: Record<Axis, number>;
  axes: Record<Axis, number>;
  breath: number;
  activations: Record<string, number>;
  thresholds: Record<string, { on: number; off: number }>;
  control: { lx: number; ly: number; rx: number; ry: number; lt: number; rt: number; buttons: string[] };
  fired: string[];
  progress: Progress | null;
  gestures: { learned: string[]; reliable: string[] };
  notices: string[];
}

export interface FrameMsg {
  type: "frame";
  jpeg: string; // base64
  landmarks: [number, number][] | null;
}

export interface EventMsg {
  type: "event";
  name: "calibration_done" | "gesture_trained" | "coach_result" | "profile_loaded" | "error";
  data: Record<string, unknown>;
}

export type ServerMsg = HelmState | FrameMsg | EventMsg;

export type Command =
  | { cmd: "calibrate"; mode: CalibrationMode }
  | { cmd: "record_gesture"; name: string }
  | { cmd: "record_negative" }
  | { cmd: "delete_gesture"; name: string }
  | { cmd: "set_mapping"; mapping: Record<string, unknown> }
  | { cmd: "load_profile"; player: string; game: string }
  | { cmd: "save_profile" }
  | { cmd: "pause"; on: boolean }
  | { cmd: "coach_build"; game: string }
  | { cmd: "coach_review" };

export type Send = (cmd: Command) => void;
