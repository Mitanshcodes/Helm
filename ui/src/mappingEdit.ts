// OWNER: P4
// Pure edits on a mapping (docs/SPEC.md section 7 format), shared by the mapping editor, "Your moves" and the
// teach result. Each returns a new mapping; nothing here talks to the server. The server validates on apply.
import type { Catalog, CatalogGesture, Mapping } from "./types";

export const FACE_BUTTONS = ["A", "B", "X", "Y"] as const;
export const MORE_BUTTONS = ["LB", "RB", "START", "BACK", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT", "LS", "RS"] as const;
export const TRIGGERS = ["lt", "rt"] as const;
export const STICK_AXES = ["lx", "ly", "rx", "ry"] as const;
/** Targets offered by the one-tap "put it on a button" row. */
export const QUICK_TARGETS = ["A", "B", "X", "Y", "LB", "RB", "lt", "rt"] as const;

export const TARGET_LABEL: Record<string, string> = {
  LB: "LB", RB: "RB", START: "Start", BACK: "Back", DPAD_UP: "D-pad ↑", DPAD_DOWN: "D-pad ↓", DPAD_LEFT: "D-pad ←",
  DPAD_RIGHT: "D-pad →", LS: "Left stick click", RS: "Right stick click", lt: "LT", rt: "RT",
  lx: "Left stick ← →", ly: "Left stick ↑ ↓", rx: "Right stick ← →", ry: "Right stick ↑ ↓",
};
export const targetLabel = (t: string) => TARGET_LABEL[t] ?? t;

export const ALWAYS = "__always__"; // pseudo-gesture: the trigger or button is held on all the time
export type Mode = "tap" | "hold" | "toggle" | "analog";

const clone = (m: Mapping): Mapping => JSON.parse(JSON.stringify(m)) as Mapping;
const isTrigger = (t: string) => t === "lt" || t === "rt";

export interface Binding {
  gesture: string; // "" = nothing, ALWAYS = always on
  mode: Mode;
}

/** What drives a pad target in this mapping. */
export function bindingOf(m: Mapping | null, target: string): Binding {
  const button = m?.buttons?.find((b) => b.target === target);
  if (button) return { gesture: button.gesture, mode: button.mode as Mode };
  const trigger = m?.triggers?.find((t) => t.target === target);
  if (trigger) return { gesture: trigger.source, mode: "analog" };
  if (m?.auto && target in m.auto) return { gesture: ALWAYS, mode: "hold" };
  return { gesture: "", mode: isTrigger(target) ? "hold" : "tap" };
}

function ensureGesture(m: Mapping, name: string, catalog: Catalog | undefined) {
  m.gestures ??= {};
  if (m.gestures[name]) return;
  const def = catalog?.gestures.find((g) => g.name === name)?.definition;
  if (def) m.gestures[name] = JSON.parse(JSON.stringify(def));
}

/** Drop gesture definitions nothing uses any more, so the mapping stays readable. */
function prune(m: Mapping): Mapping {
  const used = new Set<string>([
    ...(m.buttons ?? []).map((b) => b.gesture),
    ...(m.triggers ?? []).map((t) => t.source),
    ...(m.pause?.gesture ? [m.pause.gesture] : []),
  ]);
  for (const name of Object.keys(m.gestures ?? {})) if (!used.has(name)) delete m.gestures![name];
  return m;
}

/** Put `gesture` (or nothing, or ALWAYS) on a pad target with a mode. Replaces whatever drove that target. */
export function setBinding(m: Mapping, target: string, gesture: string, mode: Mode, catalog?: Catalog): Mapping {
  const next = clone(m);
  next.buttons = (next.buttons ?? []).filter((b) => b.target !== target);
  next.triggers = (next.triggers ?? []).filter((t) => t.target !== target);
  if (next.auto) delete next.auto[target];
  if (gesture === ALWAYS) {
    next.auto = { ...(next.auto ?? {}), [target]: 1.0 };
  } else if (gesture) {
    ensureGesture(next, gesture, catalog);
    // Analog follows the gesture's level. A breath event (soft/hard sip or puff) is a single tick: never analog.
    if (mode === "analog" && isTrigger(target) && next.gestures?.[gesture]?.kind !== "breath") {
      next.triggers.push({ source: gesture, target, lo: 0.15, hi: 0.85 });
    } else {
      next.buttons.push({ gesture, target, mode: mode === "analog" ? "hold" : mode });
    }
  }
  return prune(next);
}

/** A head movement (or nothing) on a stick axis. */
export function setAxis(m: Mapping, target: string, source: string, invert: boolean): Mapping {
  const next = clone(m);
  const current = next.axes?.find((a) => a.target === target);
  next.axes = (next.axes ?? []).filter((a) => a.target !== target);
  if (source) {
    const axis: NonNullable<Mapping["axes"]>[number] = { source, target, deadzone: current?.deadzone ?? 0.08, curve: current?.curve ?? 1.5, invert };
    if (current?.gain !== undefined) axis.gain = current.gain;
    next.axes.push(axis);
  }
  return next;
}

/** Steering sensitivity on a stick axis: 2 = full lock at half the calibrated head turn, 0.5 = twice the turn. */
export function setAxisGain(m: Mapping, target: string, gain: number): Mapping {
  const next = clone(m);
  const axis = next.axes?.find((a) => a.target === target);
  if (axis) axis.gain = Math.round(gain * 100) / 100;
  return next;
}

export function setPause(m: Mapping, gesture: string, holdMs: number, catalog?: Catalog): Mapping {
  const next = clone(m);
  if (!gesture) {
    next.pause = null;
    return prune(next);
  }
  ensureGesture(next, gesture, catalog);
  next.pause = { gesture, hold_ms: holdMs };
  return prune(next);
}

/** How strongly a gesture must be made to fire: `on`, with `off` kept 0.2 below so it releases cleanly. */
export function setThreshold(m: Mapping, gesture: string, on: number): Mapping {
  const next = clone(m);
  const g = next.gestures?.[gesture];
  if (g) {
    g.on = Math.round(on * 100) / 100;
    g.off = Math.max(0.05, Math.round((on - 0.2) * 100) / 100);
  }
  return next;
}

/** How long a gesture must stay past `on` before it presses (filters out twitches while talking). */
export function setMinHold(m: Mapping, gesture: string, ms: number): Mapping {
  const next = clone(m);
  const g = next.gestures?.[gesture];
  if (g) g.min_hold_ms = ms;
  return next;
}

/** Put a learned move on a pad target (tap), with its definition, whether or not the catalog lists it yet. */
export function putLearned(m: Mapping, target: string, name: string): Mapping {
  const def = { kind: "learned", on: 0.7, off: 0.5 };
  const catalog = { gestures: [{ name, label: name, group: "learned", usable: true, definition: def }], controls: {} } as unknown as Catalog;
  return setBinding(m, target, name, "tap", catalog);
}

/** The pad targets a gesture currently drives. */
export function targetsOf(m: Mapping | null, gesture: string): string[] {
  return [
    ...(m?.buttons ?? []).filter((b) => b.gesture === gesture).map((b) => b.target),
    ...(m?.triggers ?? []).filter((t) => t.source === gesture).map((t) => t.target),
  ];
}

export function gestureLabel(catalog: Catalog | undefined, name: string): string {
  if (name === ALWAYS) return "Always on";
  const found: CatalogGesture | undefined = catalog?.gestures.find((g) => g.name === name);
  return found?.label ?? name.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}
