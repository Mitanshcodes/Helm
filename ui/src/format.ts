// OWNER: P4
// Small text helpers shared by the cards.
import type { Mapping } from "./types";

const NAMES: Record<string, string> = { brow_raise: "Eyebrow raise", breath_puff: "Puff", breath_sip: "Sip" };

/** brow_raise -> "Eyebrow raise", left_smile -> "Left smile". */
export function humanize(name: string): string {
  const text = NAMES[name] ?? name.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Signed degrees with a real minus sign: "+6.2°", "−1.8°". */
export function degrees(value: number): string {
  return `${value < 0 ? "−" : "+"}${Math.abs(value).toFixed(1)}°`;
}

export const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

/** The button, trigger or pause action a gesture drives in this mapping, if any. */
export function bindingOf(mapping: Mapping | null, gesture: string): { target: string; mode: string } | null {
  const button = mapping?.buttons?.find((b) => b.gesture === gesture);
  if (button) return button;
  if (mapping?.pause?.gesture === gesture) return { target: "pause", mode: "pause" };
  return null;
}
