// OWNER: P4
// OPTIONS footer: text size, contrast, motion, ships, sound, and "replay intro". Saved in this browser. Text size
// scales the whole page; contrast and motion are attributes on <html> that the stylesheet reads.
import { useEffect, useState } from "react";

export type TextSize = "1" | "1.12" | "1.25";
export interface Options {
  text: TextSize;
  contrast: "std" | "high";
  motion: "on" | "low";
  ships: "on" | "off"; // the pixel ships sailing behind the camera
}

const KEY = "helm.options";
const DEFAULTS: Options = { text: "1", contrast: "std", motion: "on", ships: "on" };

export function useOptions(): [Options, (o: Partial<Options>) => void] {
  const [options, setOptions] = useState<Options>(() => {
    try {
      return { ...DEFAULTS, ...(JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<Options>) };
    } catch {
      return DEFAULTS;
    }
  });
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.contrast = options.contrast;
    root.dataset.motion = options.motion;
    root.dataset.ships = options.ships;
    root.style.setProperty("--zoom", options.text);
    try {
      localStorage.setItem(KEY, JSON.stringify(options));
    } catch {
      /* not remembered */
    }
  }, [options]);
  return [options, (o) => setOptions((prev) => ({ ...prev, ...o }))];
}

function Group<T extends string>({ label, value, choices, onChange }: { label: string; value: T; choices: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="opt-group" role="group" aria-label={label}>
      <span className="opt-label">{label}</span>
      {choices.map(([v, text]) => (
        <button key={v} className={v === value ? "btn opt on" : "btn opt"} aria-pressed={v === value} onClick={() => onChange(v)}>
          {text}
        </button>
      ))}
    </div>
  );
}

export function OptionsBar(props: { options: Options; set: (o: Partial<Options>) => void; sound: boolean; setSound: (on: boolean) => void; onReplayIntro: () => void }) {
  const { options, set, sound, setSound, onReplayIntro } = props;
  return (
    <footer className="options">
      <h2 className="opt-title">OPTIONS</h2>
      <Group label="TEXT" value={options.text} choices={[["1", "A"], ["1.12", "A+"], ["1.25", "A++"]]} onChange={(text) => set({ text })} />
      <Group label="CONTRAST" value={options.contrast} choices={[["std", "STD"], ["high", "HIGH"]]} onChange={(contrast) => set({ contrast })} />
      <Group label="MOTION" value={options.motion} choices={[["on", "ON"], ["low", "LOW"]]} onChange={(motion) => set({ motion })} />
      <Group label="SHIPS" value={options.ships} choices={[["on", "ON"], ["off", "OFF"]]} onChange={(ships) => set({ ships })} />
      <Group label="SOUND" value={sound ? "on" : "off"} choices={[["on", "ON"], ["off", "OFF"]]} onChange={(v) => setSound(v === "on")} />
      <button className="btn replay" onClick={onReplayIntro}>
        REPLAY INTRO
      </button>
    </footer>
  );
}
