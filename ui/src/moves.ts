// OWNER: P4
// The rows of the MOVES -> BUTTONS panel, derived from the live mapping and state. Display only: the engine
// decides what fires; a row is "firing" when the engine reports it (fired list, pressed buttons, stick out).
import { degrees, humanize } from "./format";
import type { Catalog, HelmState, Mapping } from "./types";

export type IconName =
  | "turn" | "nod" | "tilt" | "brow" | "smile" | "jaw" | "eyes" | "pucker" | "cheek" | "breath" | "star" | "auto" | "dot";

export interface MoveRow {
  id: string;
  name: string;
  icon: IconName;
  key: string; // what the key box shows: "A", "LX", "RT", "II"
  keyLabel: string; // the same, spoken: "A button", "left stick", "pause"
  kind: "steer" | "button" | "trigger" | "pause" | "unmapped";
  level: number; // 0..1, or -1..1 for steer
  on?: number; // fire threshold (solid notch)
  off?: number; // let-go threshold (hollow notch)
  measure: string; // what the value is: "turn", "strength", "held", "output"
  value: string;
  mode: string;
  firing: boolean;
}

const KEY: Record<string, string> = {
  START: "≡", BACK: "⧉", DPAD_UP: "↑", DPAD_DOWN: "↓", DPAD_LEFT: "←", DPAD_RIGHT: "→",
  lx: "LX", ly: "LY", rx: "RX", ry: "RY", lt: "LT", rt: "RT",
};
const KEY_SPOKEN: Record<string, string> = {
  START: "Menu button", BACK: "View button", lx: "left stick", ly: "left stick", rx: "right stick", ry: "right stick",
  lt: "left trigger", rt: "right trigger", LB: "left bumper", RB: "right bumper",
};
export const keyText = (target: string) => KEY[target] ?? target.toUpperCase();
export const keySpoken = (target: string) => KEY_SPOKEN[target] ?? `${keyText(target)} button`;

const HEAD: Record<string, [string, IconName]> = { yaw: ["Turn head", "turn"], pitch: ["Nod head", "nod"], roll: ["Tilt head", "tilt"] };
const BREATH = new Set(["hard_puff", "soft_puff", "soft_sip", "hard_sip"]);

export function moveName(name: string, catalog?: Catalog): string {
  if (name === "eyes_closed") return "Close eyes";
  return catalog?.gestures.find((g) => g.name === name)?.label ?? humanize(name);
}

export function iconFor(name: string, mapping: Mapping | null, learned: string[]): IconName {
  const def = mapping?.gestures?.[name];
  const sources = (def?.sources ?? []).join(" ");
  if (def?.kind === "learned" || learned.includes(name)) return "star";
  if (BREATH.has(name) || def?.kind === "breath") return "breath";
  const text = `${name} ${sources}`;
  if (/brow/i.test(text)) return "brow";
  if (/smile/i.test(text)) return "smile";
  if (/jaw|mouth_open/i.test(text)) return "jaw";
  if (/eyes|blink/i.test(text)) return "eyes";
  if (/pucker/i.test(text)) return "pucker";
  if (/cheek/i.test(text)) return "cheek";
  return "dot";
}

const MODE: Record<string, string> = { tap: "TAP", hold: "HOLD", toggle: "ON/OFF" };

/** Seconds the pause gesture has been held, measured here from the activation crossing its "on" threshold. */
export class HoldClock {
  private since: number | null = null;
  seconds(level: number, on: number, now: number): number {
    if (level >= on) this.since ??= now;
    else this.since = null;
    return this.since === null ? 0 : (now - this.since) / 1000;
  }
}

export function buildRows(state: HelmState, mapping: Mapping | null, pauseHeld: number): MoveRow[] {
  const live = state.face && !state.paused && !state.progress;
  const fired = new Set(state.fired ?? []);
  const pressed = new Set(state.control.buttons);
  const learned = state.gestures?.learned ?? [];
  const level = (name: string) => (state.face ? state.activations?.[name] ?? 0 : 0);
  const rows: MoveRow[] = [];
  const used = new Set<string>();

  for (const axis of mapping?.axes ?? []) {
    const [name, icon] = HEAD[axis.source] ?? [humanize(axis.source), "dot"];
    const v = (state.control as unknown as Record<string, number>)[axis.target] ?? 0;
    rows.push({
      id: `axis-${axis.target}`, name, icon, key: keyText(axis.target), keyLabel: keySpoken(axis.target), kind: "steer",
      level: Math.max(-1, Math.min(1, v)), measure: "turn", value: degrees(state.raw?.[axis.source as "yaw"] ?? 0),
      mode: axis.target === "lx" ? "STEER" : "STICK", firing: live && Math.abs(v) > 0.1,
    });
  }

  for (const b of mapping?.buttons ?? []) {
    if (BREATH.has(b.gesture) && !state.breath_connected) continue;
    used.add(b.gesture);
    const breath = BREATH.has(b.gesture);
    const lv = breath ? Math.max(0, (b.gesture.endsWith("puff") ? 1 : -1) * (state.breath ?? 0)) : level(b.gesture);
    rows.push({
      id: `btn-${b.gesture}-${b.target}`, name: moveName(b.gesture, state.catalog), icon: iconFor(b.gesture, mapping, learned),
      key: keyText(b.target), keyLabel: keySpoken(b.target), kind: "button", level: lv, on: state.thresholds?.[b.gesture]?.on,
      off: state.thresholds?.[b.gesture]?.off, measure: "strength", value: lv.toFixed(2), mode: MODE[b.mode] ?? b.mode.toUpperCase(),
      firing: live && (fired.has(b.gesture) || pressed.has(b.target)),
    });
  }

  for (const t of mapping?.triggers ?? []) {
    used.add(t.source);
    const out = t.target === "lt" ? state.control.lt : state.control.rt;
    rows.push({
      id: `trig-${t.target}`, name: moveName(t.source, state.catalog), icon: iconFor(t.source, mapping, learned),
      key: keyText(t.target), keyLabel: keySpoken(t.target), kind: "trigger", level: level(t.source), measure: "output",
      value: `${Math.round(out * 100)}%`, mode: "ANALOG", firing: live && out > 0.05,
    });
  }

  for (const [target, v] of Object.entries(mapping?.auto ?? {})) {
    if (!v) continue;
    const out = target === "lt" ? state.control.lt : target === "rt" ? state.control.rt : v;
    rows.push({
      id: `auto-${target}`, name: target === "rt" ? "Accelerate" : `${keyText(target)} always on`, icon: "auto",
      key: keyText(target), keyLabel: keySpoken(target), kind: "trigger", level: out, measure: "output",
      value: `${Math.round(out * 100)}%`, mode: "AUTO", firing: false,
    });
  }

  const pause = mapping?.pause;
  if (pause) {
    used.add(pause.gesture);
    const hold = pause.hold_ms / 1000;
    rows.push({
      id: "pause", name: moveName(pause.gesture, state.catalog), icon: iconFor(pause.gesture, mapping, learned),
      key: "II", keyLabel: "pause", kind: "pause", level: Math.min(1, pauseHeld / hold), on: 1,
      measure: "held", value: `${pauseHeld.toFixed(1)} s`, mode: `HOLD ${hold} S`, firing: state.face && !state.progress && pauseHeld > 0.3,
    });
  }

  // Gestures Helm tracks that nothing uses yet, such as a newly learned move.
  for (const name of Object.keys(state.activations ?? {})) {
    if (used.has(name)) continue;
    const lv = level(name);
    rows.push({
      id: `free-${name}`, name: moveName(name, state.catalog), icon: iconFor(name, mapping, learned), key: "–",
      keyLabel: "nothing yet", kind: "unmapped", level: lv, on: state.thresholds?.[name]?.on, off: state.thresholds?.[name]?.off,
      measure: "strength", value: lv.toFixed(2),
      mode: "NOT SET", firing: false,
    });
  }
  return rows;
}

/** Pause hold in seconds from the mapping (the engine's default is 2 s). */
export const holdSeconds = (mapping: Mapping | null | undefined) => (mapping?.pause?.hold_ms ?? 2000) / 1000;
