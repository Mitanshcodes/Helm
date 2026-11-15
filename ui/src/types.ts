// OWNER: P4
// The WebSocket protocol of docs/SPEC.md section 8, as TypeScript types.

export type Axis = "yaw" | "pitch" | "roll";
export type CalibrationMode = "full" | "quick";
export type Connection = "connecting" | "open" | "closed";

export interface Progress {
  active: boolean;
  step: string;
  prompt: string;
  progress: number; // 0..1 within the step
  overall: number; // 0..1 across the whole flow
  done: boolean;
}

export interface Mapping {
  player?: string;
  game?: string;
  axes?: { source: string; target: string; deadzone?: number; curve?: number; invert?: boolean; gain?: number }[];
  triggers?: { source: string; target: string; lo?: number; hi?: number }[];
  gestures?: Record<string, { kind: string; sources?: string[]; combine?: string; on?: number; off?: number; min_hold_ms?: number }>;
  buttons?: { gesture: string; target: string; mode: string }[];
  auto?: Record<string, number>;
  pause?: { gesture: string; hold_ms: number } | null;
}

export interface HelmState {
  multiplayer?: MultiplayerState;
  identity?: { protected: boolean; allowed: boolean; state: string; player: string; reason: string;
    score?: number | null; face_count?: number; inference_ms?: number; face_landmarker_num_faces?: number | null };
  dev?: { enabled: boolean; recording: boolean; session: null | {
    path: string; kind: string; frames: number; saving: boolean; error: string | null;
  } };
  type: "state";
  fps: number;
  latency_ms: { vision: number; control: number; total: number };
  face: boolean;
  paused: boolean;
  breath_connected: boolean;
  profile: { player: string; game: string; calibrated: CalibrationMode | "default" | null };
  raw: Record<Axis, number>;
  axes: Record<Axis, number>;
  breath: number; // -1..1 of the player's measured range: + puff, - sip
  breath_marks?: { soft: number; hard: number }; // where a breath counts as soft and as hard
  ranges?: Record<Axis, [number, number]>; // degrees of head movement for full lock each way, sensitivity included
  activations: Record<string, number>;
  thresholds: Record<string, { on: number; off: number }>;
  control: { lx: number; ly: number; rx: number; ry: number; lt: number; rt: number; buttons: string[] };
  fired: string[];
  progress: Progress | null;
  gestures: { learned: string[]; reliable: string[] };
  notices: string[];
  mapping?: Mapping;
  expressions?: Record<string, number>; // raw blendshape scores for a watch list (asked of P1); shown when present
  catalog?: Catalog; // what the mapping editor can put on a control
}

export interface CatalogGesture {
  name: string;
  label: string;
  group: "face" | "learned" | "breath";
  definition: { kind: string; sources?: string[]; combine?: string; on?: number; off?: number; min_hold_ms?: number };
  usable: boolean; // false: this player's calibration says the expression is weak
}

export interface Catalog {
  gestures: CatalogGesture[];
  controls: Record<string, string>; // pad target -> the game's action name, e.g. A -> "fire item"
}

export interface FrameMsg {
  type: "frame";
  jpeg: string; // base64; empty when there is no picture (mock)
  landmarks: [number, number][] | null;
  faces?: { player: string | null; landmarks: [number, number][] }[];
}

export interface MultiplayerState {
  enabled: boolean;
  visible_profiles: string[];
  error: string | null;
  output_available?: boolean;
  demo?: boolean;
  controllers: { slot: number; player: string | null; connected: boolean; loading: boolean;
    mapping: Mapping | null; control: HelmState["control"] }[];
}

export interface EventMsg {
  type: "event";
  name:
    | "calibration_done"
    | "breath_calibration_done"
    | "face_id_done"
    | "captain_step"
    | "face_id_forgotten"
    | "profile_deleted"
    | "profiles_reset"
    | "gesture_trained"
    | "coach_result"
    | "profile_loaded"
    | "profile_reloaded"
    | "error";
  data: Record<string, unknown>;
}

export interface Trained {
  name: string;
  accuracy: number | null;
}

export interface CoachResult {
  mapping: Mapping;
  summary: string;
  changes: { change: string; reason: string }[]; // what changed (worked out by Helm) and why (the Captain)
  backend: "claude" | "offline";
  offline_reason: string;
  elapsed_s: number;
  request: string;
  kind: "ask" | "build" | "review";
}

export interface MappingStatus {
  errors: string[];
  applied: boolean;
}

export type ServerMsg = HelmState | FrameMsg | EventMsg;

export type Command =
  | { cmd: "set_play_mode"; mode: "singleplayer" | "multiplayer" }
  | { cmd: "assign_controller"; slot: number; player: string | null }
  | { cmd: "reload_identity" }
  | { cmd: "forget_face" }
  | { cmd: "delete_profile" }
  | { cmd: "reset_profiles" }
  | { cmd: "set_dev_mode"; on: boolean }
  | { cmd: "set_dev_recording"; on: boolean }
  | { cmd: "calibrate"; mode: CalibrationMode | "breath" }
  | { cmd: "record_gesture"; name: string }
  | { cmd: "record_negative" }
  | { cmd: "delete_gesture"; name: string }
  | { cmd: "set_mapping"; mapping: Mapping }
  | { cmd: "load_profile"; player: string; game: string }
  | { cmd: "save_profile" }
  | { cmd: "pause"; on: boolean }
  | { cmd: "coach_build"; game: string }
  | { cmd: "coach_review" }
  | { cmd: "coach_ask"; request: string };

export type Send = (cmd: Command) => void;
