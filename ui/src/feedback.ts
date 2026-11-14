// OWNER: P4
// Spoken prompts and fire clicks. Both are offline: the voice is the operating system's own, the click is
// synthesized. Browsers block audio until the page has had one click or key press, so the first press anywhere
// unlocks both; until then they stay silent rather than fail.
import { useEffect, useRef, useState } from "react";
import type { HelmState } from "./types";

const params = new URLSearchParams(location.search);
// Only one window should make sound: the full dashboard by default, the overlay only with ?sound=1.
const DEFAULT_ON = !params.has("overlay") || params.has("sound");

let audio: AudioContext | null = null;

function context(): AudioContext | null {
  try {
    audio ??= new AudioContext();
    return audio;
  } catch {
    return null;
  }
}

function unlock() {
  void context()?.resume();
  if ("speechSynthesis" in window) speechSynthesis.speak(new SpeechSynthesisUtterance(""));
}
window.addEventListener("pointerdown", unlock, { once: true });
window.addEventListener("keydown", unlock, { once: true });

/** A short soft tick. `pitch` in Hz; a lower pitch is used for pause and resume. */
export function click(pitch = 1400) {
  const ctx = context();
  if (!ctx || ctx.state !== "running") return;
  const t = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.setValueAtTime(pitch, t);
  osc.frequency.exponentialRampToValueAtTime(pitch * 0.6, t + 0.05);
  gain.gain.setValueAtTime(0.0001, t);
  gain.gain.exponentialRampToValueAtTime(0.18, t + 0.004);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.07);
  osc.connect(gain).connect(ctx.destination);
  osc.start(t);
  osc.stop(t + 0.08);
}

export function speak(text: string) {
  if (!("speechSynthesis" in window) || !text) return;
  speechSynthesis.cancel(); // a new prompt replaces the old one; never queue stale instructions
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-US";
  u.rate = 1.05;
  speechSynthesis.speak(u);
}

/** A boolean setting remembered per window kind in this browser. Falls back to the default if storage is blocked. */
export function useSetting(name: string): [boolean, (on: boolean) => void] {
  const key = `helm.${name}.${params.has("overlay") ? "overlay" : "main"}`;
  const [on, setOn] = useState(() => {
    try {
      const saved = localStorage.getItem(key);
      return saved === null ? DEFAULT_ON : saved === "1";
    } catch {
      return DEFAULT_ON;
    }
  });
  const set = (value: boolean) => {
    setOn(value);
    try {
      localStorage.setItem(key, value ? "1" : "0");
    } catch {
      /* private window: the setting lasts for this page only */
    }
    if (!value && name === "voice" && "speechSynthesis" in window) speechSynthesis.cancel();
  };
  return [on, set];
}

/** Reads each new wizard prompt aloud, so a player turning their head away from the screen still hears it. */
export function useSpokenPrompts(state: HelmState | null, on: boolean) {
  const last = useRef<string | null>(null);
  const prompt = state?.progress?.prompt ?? null;
  useEffect(() => {
    if (prompt === last.current) return;
    last.current = prompt;
    if (on && prompt) speak(prompt);
  }, [prompt, on]);
}

/** Clicks when a controller button goes down, and a lower two-note sound when control pauses or resumes. */
export function useFireClicks(state: HelmState | null, on: boolean) {
  const buttons = useRef<Set<string>>(new Set());
  const paused = useRef<boolean | null>(null);
  useEffect(() => {
    if (!state) return;
    const now = new Set(state.control.buttons);
    const pressed = [...now].some((b) => !buttons.current.has(b));
    buttons.current = now;
    const pauseChanged = paused.current !== null && paused.current !== state.paused;
    paused.current = state.paused;
    if (!on) return;
    if (pauseChanged) {
      click(state.paused ? 700 : 500);
      window.setTimeout(() => click(state.paused ? 500 : 700), 90);
    } else if (pressed) click();
  }, [state, on]);
}
