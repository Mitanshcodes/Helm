// OWNER: P4
// "Your gestures" card: one row per gesture with its button badge, live level, fire and release ticks, and
// the adaptation notices underneath.
import { useRef } from "react";
import { bindingOf, clamp01, humanize } from "../format";
import type { HelmState, Mapping } from "../types";

// Expressions worth watching even when the mapping does not use them, to see how well each one is detected
// for this player. Left and right are the player's own sides.
const WATCH: [string, string][] = [
  ["mouthPucker", "Pucker"],
  ["cheekPuff", "Cheek puff"],
];

const FLASH_MS = 450; // how long a row reads "Firing" after a tap, so it can be seen from across a table

function PauseIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">
      <rect x="3" y="2" width="3.5" height="12" rx="1" />
      <rect x="9.5" y="2" width="3.5" height="12" rx="1" />
    </svg>
  );
}

function InfoIcon() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <line x1="12" y1="11" x2="12" y2="16.5" />
      <line x1="12" y1="7.5" x2="12" y2="7.6" />
    </svg>
  );
}

function suffix(mode: string | undefined, learned: boolean, holdMs: number | undefined): string | null {
  if (mode === "pause") return `hold ${(holdMs ?? 2000) / 1000} s to pause or resume`;
  const parts = [mode === "hold" ? "hold" : mode === "toggle" ? "on / off" : null, learned ? "learned from your takes" : null];
  return parts.filter(Boolean).join(" · ") || null;
}

interface RowProps {
  name: string;
  level: number;
  firing: boolean;
  target?: string;
  note: string | null;
  on?: number;
  off?: number;
}

function reliability(state: HelmState, source: string): { tone: "ok" | "warn" | "off"; text: string } {
  if (state.profile.calibrated !== "full") return { tone: "off", text: "Not checked yet" };
  return (state.gestures?.reliable ?? []).includes(source)
    ? { tone: "ok", text: "Reliable for you" }
    : { tone: "warn", text: "Weak for you" };
}

function WatchRow({ label, level, check }: { label: string; level: number; check: { tone: string; text: string } }) {
  return (
    <li className="gesture watch">
      <div className="gesture-top">
        <span className="gesture-name">
          {label}
          <span className={`mini-pill ${check.tone}`}>{check.text}</span>
        </span>
      </div>
      <div className="gesture-bottom">
        <div className="meter" role="img" aria-label={`${label} raw score ${level.toFixed(2)}`}>
          <div className="meter-track">
            <div className="meter-fill" style={{ width: `${clamp01(level) * 100}%` }} />
          </div>
        </div>
        <span className="score">{level.toFixed(2)}</span>
      </div>
    </li>
  );
}

function GestureRow({ name, level, firing, target, note, on, off }: RowProps) {
  const title = humanize(name);
  return (
    <li className={`gesture${firing ? " firing" : ""}${target === "pause" ? " pause" : ""}`}>
      <div className="gesture-top">
        <span className={target ? "badge" : "badge none"} aria-label={target ? `Button ${target}` : "Not mapped"}>
          {target === "pause" ? <PauseIcon /> : (target ?? "–").toUpperCase()}
        </span>
        <span className="gesture-name">
          {title}
          {note && <span className="suffix">{note}</span>}
        </span>
        {firing && <span className="firing-pill">Firing</span>}
      </div>
      <div className="gesture-bottom">
        <div className="meter" role="img" aria-label={`${title} level ${level.toFixed(2)}${on !== undefined ? `, fires at ${on.toFixed(2)}` : ""}`}>
          <div className="meter-track">
            <div className="meter-fill" style={{ width: `${clamp01(level) * 100}%` }} />
          </div>
          {off !== undefined && <span className="tick off" style={{ left: `${clamp01(off) * 100}%` }} />}
          {on !== undefined && <span className="tick on" style={{ left: `${clamp01(on) * 100}%` }} />}
        </div>
        <span className="score">{level.toFixed(2)}</span>
      </div>
    </li>
  );
}

// P3's notices are terse ("cheek_puff is weakening; threshold lowered"). Say the same thing warmly.
function warm(notice: string): string {
  const match = /^(\w+) is weakening/.exec(notice);
  if (!match) return notice;
  return `${humanize(match[1])} is getting weaker, so Helm lowered its threshold. Take a break whenever you like.`;
}

export function Gauges({ state, mapping }: { state: HelmState; mapping: Mapping | null }) {
  const { activations, thresholds, control } = state;
  const flashAt = useRef<Record<string, number>>({});
  const previous = useRef<Record<string, number>>({});
  const now = performance.now();

  // A fire lasts one pipeline tick and the socket sends 30 states a second, so also count a level rising
  // through its "on" threshold: a fire that falls between two states is still shown.
  const live = state.face && !state.paused && !state.progress;
  for (const name of state.fired ?? []) flashAt.current[name] = now;
  for (const [name, level] of Object.entries(activations ?? {})) {
    const on = thresholds?.[name]?.on;
    if (live && on !== undefined && level >= on && (previous.current[name] ?? 0) < on) flashAt.current[name] = now;
    previous.current[name] = level;
  }

  const analog = new Set((mapping?.triggers ?? []).map((t) => t.source)); // shown on the throttle card instead
  const order = (mapping?.buttons ?? []).map((b) => b.gesture);
  const names = Object.keys(activations ?? {})
    .filter((name) => !analog.has(name))
    .sort((a, b) => (order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99));

  return (
    <section className="card">
      <div className="card-head">
        <h2>Face controls</h2>
        <span className="hint legend">
          <i className="tick-key on" /> fires <i className="tick-key off" /> releases
        </span>
      </div>
      {names.length === 0 && <p className="muted">No gestures are mapped yet. Build a mapping with the coach below.</p>}
      <ul className="gestures">
        {names.map((name) => {
          const binding = bindingOf(mapping, name);
          const learned = mapping?.gestures?.[name]?.kind === "learned" || (state.gestures?.learned ?? []).includes(name);
          const pressed = binding !== null && control.buttons.includes(binding.target);
          const firing = live && (pressed || now - (flashAt.current[name] ?? -Infinity) < FLASH_MS);
          return (
            <GestureRow
              key={name}
              name={name}
              level={state.face ? activations[name] : 0}
              firing={firing}
              target={binding?.target}
              note={suffix(binding?.mode, learned, mapping?.pause?.hold_ms)}
              on={thresholds?.[name]?.on}
              off={learned ? undefined : thresholds?.[name]?.off}
            />
          );
        })}
      </ul>
      {(() => {
        const used = new Set(Object.values(mapping?.gestures ?? {}).flatMap((g) => g.sources ?? []));
        const watch = WATCH.filter(([source]) => !used.has(source) && state.expressions?.[source] !== undefined);
        if (watch.length === 0) return null;
        return (
          <>
            <div className="watch-head">
              <h3>Also watching</h3>
              <span className="hint">Raw scores, not mapped to anything</span>
            </div>
            <ul className="gestures">
              {watch.map(([source, label]) => (
                <WatchRow key={source} label={label} level={state.face ? state.expressions![source] : 0} check={reliability(state, source)} />
              ))}
            </ul>
          </>
        );
      })()}
      <div aria-live="polite">
        {(state.notices ?? []).map((notice) => (
          <p key={notice} className="notice">
            <InfoIcon />
            <span>{warm(notice)}</span>
          </p>
        ))}
      </div>
    </section>
  );
}
