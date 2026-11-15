// OWNER: P4
// In-browser stand-in for the Python server (?mock=1 or VITE_MOCK=1). It speaks the protocol of docs/SPEC.md
// section 8 with made-up data, so the whole dashboard can be built and shown with no backend running.
import { BROW_A, BROW_B, EYE_A, EYE_B, FACE_OVAL, LIPS, NOSE, N_LANDMARKS } from "./mesh";
import type { Command, EventMsg, HelmState, Mapping, Progress } from "./types";
import type { HelmSocket, OnMessage, OnStatus } from "./ws";

const HZ = 30;
const BREATH = ["hard_puff", "soft_puff", "soft_sip", "hard_sip"];

// The real default (profiles/_defaults/SuperTuxKart.json), so the mock looks like a fresh install.
const MAPPING: Mapping = {
  player: "sam",
  game: "SuperTuxKart",
  axes: [{ source: "yaw", target: "lx", deadzone: 0.08, curve: 1.5, invert: false }],
  triggers: [],
  gestures: {
    brow_raise: { kind: "blendshape", sources: ["browInnerUp"], on: 0.6, off: 0.4 },
    smile: { kind: "blendshape", sources: ["mouthSmileLeft", "mouthSmileRight"], combine: "max", on: 0.6, off: 0.4 },
    jaw_open: { kind: "blendshape", sources: ["jawOpen"], on: 0.7, off: 0.45 },
    eyes_closed: { kind: "blendshape", sources: ["eyeBlinkLeft", "eyeBlinkRight"], combine: "min", on: 0.85, off: 0.6 },
    hard_puff: { kind: "breath" },
    soft_puff: { kind: "breath" },
    soft_sip: { kind: "breath" },
    hard_sip: { kind: "breath" },
  },
  buttons: [
    { gesture: "brow_raise", target: "A", mode: "tap" },
    { gesture: "smile", target: "B", mode: "tap" },
    { gesture: "jaw_open", target: "Y", mode: "tap" },
    { gesture: "hard_puff", target: "Y", mode: "tap" },
    { gesture: "soft_puff", target: "RB", mode: "tap" },
    { gesture: "soft_sip", target: "LB", mode: "tap" },
    { gesture: "hard_sip", target: "START", mode: "tap" },
  ],
  auto: {},
  pause: { gesture: "eyes_closed", hold_ms: 2000 },
};

const JUDGE_MAPPING: Mapping = {
  player: "judge",
  game: "SuperTuxKart",
  axes: [{ source: "yaw", target: "lx", deadzone: 0.08, curve: 1.5, invert: false }],
  triggers: [],
  gestures: {
    brow_raise: { kind: "blendshape", sources: ["browInnerUp"], on: 0.6, off: 0.4 },
    eyes_closed: { kind: "blendshape", sources: ["eyeBlinkLeft", "eyeBlinkRight"], combine: "min", on: 0.6, off: 0.4 },
  },
  buttons: [{ gesture: "brow_raise", target: "A", mode: "tap" }],
  auto: { rt: 1.0 },
  pause: { gesture: "eyes_closed", hold_ms: 2000 },
};

const PROFILES: Record<string, string[]> = {
  demo: ["SuperTuxKart"],
  demo_webcam: ["SuperTuxKart"],
  judge: ["SuperTuxKart"],
  sam: ["SuperTuxKart"],
};
export const mockProfiles = async () => PROFILES;

type Step = { step: string; prompt: string; seconds: number };
// Mirrors sipnpuff.BreathCalibrator's three steps, so the dashboard can be developed with no board.
const BREATH_CALIBRATION: Step[] = [
  { step: "breath_rest", prompt: "Hands off the tube, breathe normally", seconds: 1.5 },
  { step: "breath_sip", prompt: "Sip hard on the tube, like a thick straw, and hold", seconds: 4 },
  { step: "breath_puff", prompt: "Now puff hard into the tube, and hold", seconds: 4 },
];
// The real steps and prompts of helm/calibration.py, shortened.
const CALIBRATION: Step[] = [
  { step: "neutral", prompt: "Look at the screen and relax your face", seconds: 3 },
  { step: "yaw_left", prompt: "Turn your head left as far as is comfortable, and hold", seconds: 2.5 },
  { step: "yaw_right", prompt: "Turn your head right as far as is comfortable, and hold", seconds: 2.5 },
  { step: "pitch_up", prompt: "Tilt your chin up as far as is comfortable, and hold", seconds: 2 },
  { step: "pitch_down", prompt: "Tilt your chin down as far as is comfortable, and hold", seconds: 2 },
  { step: "brow_raise", prompt: "Raise your eyebrows, three times", seconds: 2.5 },
  { step: "jaw_open", prompt: "Open your mouth wide, three times", seconds: 2.5 },
  { step: "smile", prompt: "Smile wide, three times", seconds: 2.5 },
  { step: "nod_up", prompt: "Nod your chin up and hold a moment, three times", seconds: 2.5 },
];
// Timings mirror what P3's TakeRecorder is expected to send; the dashboard reads them, it never assumes them.
const TAKES = 10;
const takes = (name: string): Step[] =>
  Array.from({ length: TAKES }, (_, i) => i + 1).flatMap((n) => [
    { step: `take_${n}_ready`, prompt: "Get ready…", seconds: 2 },
    { step: `take_${n}_go`, prompt: `Go! Do “${name.replace(/_/g, " ")}” and hold`, seconds: 1.5 },
    { step: `take_${n}_relax`, prompt: "Relax", seconds: 1.5 },
  ]);
const EVERYDAY_FACE: Step[] = [
  { step: "neutral", prompt: "Look at the screen and relax your face", seconds: 10 },
  { step: "read_aloud", prompt: "Read this aloud at your own pace. Mouthing the words is fine too.", seconds: 60 },
];

const bump = (phase: number, width: number) => (phase < width ? Math.sin((Math.PI * phase) / width) : 0);
const clamp = (v: number, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));

function landmarks(yaw: number, brow: number, jaw: number, eyes: number): [number, number][] {
  const pts: [number, number][] = Array.from({ length: N_LANDMARKS }, () => [-1, -1]);
  const cx = 0.5 + yaw * 0.05;
  const fx = cx + yaw * 0.035; // features shift more than the outline, which reads as a head turn
  const ring = (ids: number[], x: number, y: number, rx: number, ry: number, start = -Math.PI / 2) =>
    ids.forEach((id, k) => {
      const a = start + (2 * Math.PI * k) / ids.length;
      pts[id] = [x + rx * Math.cos(a), y + ry * Math.sin(a)];
    });
  const arc = (ids: number[], x: number, y: number, w: number) =>
    ids.forEach((id, k) => {
      const u = k / (ids.length - 1) - 0.5;
      pts[id] = [x + u * w, y + u * u * 0.06];
    });
  ring(FACE_OVAL, cx, 0.5, 0.19, 0.34);
  ring(LIPS, fx, 0.66, 0.07, 0.014 + jaw * 0.05, Math.PI);
  ring(EYE_A, fx + 0.08, 0.43, 0.04, 0.02 * (1 - 0.85 * eyes), 0);
  ring(EYE_B, fx - 0.08, 0.43, 0.04, 0.02 * (1 - 0.85 * eyes), 0);
  NOSE.forEach((id, k) => (pts[id] = [fx + yaw * 0.01 * k, 0.44 + k * 0.025]));
  arc(BROW_A, fx + 0.08, 0.365 - brow * 0.03, 0.1);
  arc(BROW_B, fx - 0.08, 0.365 - brow * 0.03, 0.1);
  return pts;
}

export function startMock(onMessage: OnMessage, onStatus: OnStatus): HelmSocket {
  const t0 = performance.now();
  let mapping = MAPPING;
  let player = "sam";
  let learned: string[] = [];
  let calibrated: "full" | "quick" | null = "full";
  let paused = false;
  let eyesSince: number | null = null; // the mock pauses like the engine: eyes shut for the hold time
  let script: { steps: Step[]; started: number; done: () => void } | null = null;
  let tick = 0;
  let breathIndex = 0;
  const breathConnected = new URLSearchParams(location.search).has("breath"); // ?mock=1&breath=1: a sensor is attached
  let lastBreathSlot = 0;
  const active: Record<string, boolean> = {};
  const tapUntil: Record<string, number> = {};
  const timers: number[] = [];

  const later = (ms: number, fn: () => void) => timers.push(window.setTimeout(fn, ms));
  const event = (name: EventMsg["name"], data: Record<string, unknown>) =>
    onMessage({ type: "event", name, data });
  const run = (steps: Step[], done: () => void) => (script = { steps, started: performance.now(), done });

  const progress = (now: number): Progress | null => {
    if (!script) return null;
    const total = script.steps.reduce((sum, s) => sum + s.seconds, 0);
    let elapsed = (now - script.started) / 1000;
    if (elapsed >= total) {
      const { done } = script;
      script = null;
      done();
      return null;
    }
    const overall = elapsed / total;
    for (const s of script.steps) {
      if (elapsed < s.seconds) return { active: true, step: s.step, prompt: s.prompt, progress: elapsed / s.seconds, overall, done: false };
      elapsed -= s.seconds;
    }
    return null;
  };

  const step = () => {
    const now = performance.now();
    const t = (now - t0) / 1000;
    const face = t % 45 < 42;
    const yawDeg = 14 * Math.sin((2 * Math.PI * t) / 7);
    const u = clamp(yawDeg / 15, -1, 1);
    const shaped = Math.abs(u) < 0.08 ? 0 : Math.sign(u) * ((Math.abs(u) - 0.08) / 0.92) ** 1.5;
    const jaw = clamp(0.4 + 0.4 * Math.sin(t / 2.3));
    const levels: Record<string, number> = {
      brow_raise: 0.04 + 0.82 * bump(t % 5, 0.9),
      smile: 0.05 + 0.85 * bump((t + 4) % 9, 0.9),
      jaw_open: 0.06 + 0.75 * bump((t + 7) % 13, 1),
      eyes_closed: 0.03 + 0.95 * bump(t % 30, 7),
    };
    const prog = progress(now);
    if (face && !prog && levels.eyes_closed >= 0.85) {
      eyesSince ??= now;
      if (now - eyesSince >= (mapping.pause?.hold_ms ?? 2000)) {
        paused = !paused;
        eyesSince = Infinity; // once per closure
      }
    } else eyesSince = null;
    const neutral = paused || !face || prog !== null;
    const fired: string[] = [];
    const buttons = new Set<string>();
    const activations: Record<string, number> = {};
    const thresholds: HelmState["thresholds"] = {};

    for (const [name, def] of Object.entries(mapping.gestures ?? {})) {
      if (def.kind === "breath") continue;
      const level = face ? levels[name] ?? 0 : 0;
      activations[name] = level;
      const on = def.on ?? 0.6;
      const off = def.off ?? 0.4;
      thresholds[name] = { on, off };
      const was = active[name] ?? false;
      active[name] = was ? level > off : level >= on;
      const binding = mapping.buttons?.find((b) => b.gesture === name);
      if (active[name] && !was && !neutral && binding) {
        fired.push(name);
        if (binding.mode === "tap") tapUntil[binding.target] = now + 120;
      }
      if (binding && !neutral && binding.mode === "hold" && active[name]) buttons.add(binding.target);
    }
    const slot = Math.floor(t / 6);
    if (slot !== lastBreathSlot && !neutral && breathConnected) {
      lastBreathSlot = slot;
      const kind = BREATH[breathIndex++ % BREATH.length];
      const binding = mapping.buttons?.find((b) => b.gesture === kind);
      if (binding) {
        fired.push(kind);
        tapUntil[binding.target] = now + 120;
      }
    }
    for (const [target, until] of Object.entries(tapUntil)) if (now < until && !neutral) buttons.add(target);
    const hasThrottle = mapping.triggers?.some((tr) => tr.target === "rt");

    onMessage({
      type: "state",
      fps: 58.2 + 0.6 * Math.sin(t / 3),
      latency_ms: { vision: 14.1 + Math.sin(t), control: 0.6, total: 31 + 2 * Math.sin(t / 2) },
      face,
      paused,
      breath_connected: breathConnected,
      profile: { player, game: mapping.game ?? "SuperTuxKart", calibrated },
      raw: face ? { yaw: yawDeg + 1.8, pitch: -1.8 + 1.5 * Math.sin(t / 3), roll: 0.6 + 0.8 * Math.sin(t / 5) } : { yaw: 0, pitch: 0, roll: 0 },
      axes: { yaw: face ? u : 0, pitch: 0, roll: 0 },
      breath: 0.5 * bump(t % 6, 0.5) * (breathIndex % 4 < 2 ? 1 : -1),
      activations,
      thresholds,
      control: { lx: neutral ? 0 : shaped, ly: 0, rx: 0, ry: 0, lt: 0, rt: neutral ? 0 : mapping.auto?.rt ?? (hasThrottle ? clamp((jaw - 0.15) / 0.7) : 0), buttons: [...buttons] },
      fired,
      progress: prog,
      gestures: { learned, reliable: ["browInnerUp", "jawOpen", "mouthSmileLeft", "mouthSmileRight"] },
      notices: t > 20 ? ["jaw_open is weakening; threshold lowered to 85%"] : [],
      mapping,
      expressions: face
        ? {
            mouthSmileLeft: 0.08 + 0.6 * bump((t + 1) % 9, 1.2),
            mouthSmileRight: 0.06 + 0.3 * bump((t + 5) % 9, 1.2),
            cheekPuff: 0.05 + 0.45 * bump((t + 3) % 11, 1.5),
          }
        : {},
    });
    if (tick++ % 2 === 0) {
      onMessage({ type: "frame", jpeg: "", landmarks: face ? landmarks(u, levels.brow_raise, levels.jaw_open, levels.eyes_closed) : null });
    }
  };

  onStatus("connecting");
  later(300, () => onStatus("open"));
  const interval = window.setInterval(step, 1000 / HZ);

  return {
    send(cmd: Command) {
      if (cmd.cmd === "pause") paused = cmd.on;
      else if (cmd.cmd === "calibrate") {
        if (cmd.mode === "breath") {
          // Breath range is not face calibration: `calibrated` tracks the face wizard only.
          run(BREATH_CALIBRATION, () =>
            event("breath_calibration_done", { max_puff_mv: 1205, max_sip_mv: 1180, notes: [] }),
          );
        } else {
          const mode = cmd.mode;
          run(mode === "quick" ? CALIBRATION.slice(0, 1) : CALIBRATION, () => {
            calibrated = mode;
            event("calibration_done", { mode, range: { yaw: [14, 15.5] } });
            // Like the engine: breath range straight after the face, only with a sensor attached.
            if (mode === "full" && breathConnected)
              run(BREATH_CALIBRATION, () => event("breath_calibration_done", { max_puff_mv: 1205, max_sip_mv: 1180, notes: [] }));
          });
        }
      } else if (cmd.cmd === "record_gesture") {
        run(takes(cmd.name), () => {
          if (!learned.includes(cmd.name)) learned = [...learned, cmd.name];
          event("gesture_trained", { name: cmd.name, accuracy: 0.93 });
        });
      } else if (cmd.cmd === "record_negative") {
        run(EVERYDAY_FACE, () => event("gesture_trained", { name: "none", accuracy: null }));
      } else if (cmd.cmd === "load_profile") {
        later(150, () => {
          const judge = cmd.player === "judge";
          player = cmd.player;
          mapping = { ...(judge ? JUDGE_MAPPING : MAPPING), player: cmd.player, game: cmd.game };
          calibrated = judge ? null : "full";
          learned = [];
          script = null;
          event("profile_loaded", { player: cmd.player, game: cmd.game });
        });
      } else if (cmd.cmd === "delete_gesture") learned = learned.filter((g) => g !== cmd.name);
      else if (cmd.cmd === "set_mapping") {
        if (!cmd.mapping.pause) event("error", { message: "Mapping rejected", cmd: "set_mapping", errors: ["A pause gesture must be set"] });
        else mapping = cmd.mapping;
      } else if (cmd.cmd === "coach_build") {
        later(900, () =>
          event("coach_result", {
            mapping: { ...MAPPING, game: cmd.game },
            rationale: [
              "Steering is on head turn, your widest range.",
              "Fire item is used most, so it goes to eyebrow raise, your strongest expression.",
              "Nitro is held, so it sits on cheek puff, which shares no muscles with the jaw throttle.",
            ],
            changes: [],
          }),
        );
      } else if (cmd.cmd === "coach_review") {
        later(900, () => event("coach_result", { mapping, rationale: [], changes: ["Cheek puff nearly fired 6 times: lowered its threshold from 0.60 to 0.52."] }));
      }
    },
    close() {
      window.clearInterval(interval);
      timers.forEach((id) => window.clearTimeout(id));
    },
  };
}
