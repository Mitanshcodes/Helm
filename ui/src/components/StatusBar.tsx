// OWNER: P4
// The top bar: the wheel and the "helm" wordmark on the left, Recalibrate on the right. Nothing else: who is
// playing lives in the Anchor's Profile page, and the camera says whether a face is found.
import type { HelmState } from "../types";
import { HelmWheel } from "./PixelIcon";

export type Status = "offline" | "calibrating" | "teaching" | "paused" | "noface" | "live";

export function statusOf(state: HelmState | null, open: boolean, teaching: boolean): Status {
  if (!open || !state) return "offline";
  if (state.progress && teaching) return "teaching";
  if (state.progress) return "calibrating";
  if (state.paused) return "paused";
  if (!state.face) return "noface";
  return "live";
}

export function Brand() {
  return (
    <div className="brand">
      <HelmWheel className="brand-wheel" size={58} />
      <span className="wordmark small">helm</span>
    </div>
  );
}

/** Sip-and-puff check: is the tube plugged in, and a live meter to sip and puff against when it is. */
export function BreathCheck({ state }: { state: HelmState }) {
  const on = state.breath_connected;
  const v = Math.max(-1, Math.min(1, state.breath ?? 0));
  const a = Math.abs(v);
  const marks = state.breath_marks ?? { soft: 0.25, hard: 0.65 };
  const words = !on ? "not plugged in" : a < marks.soft / 2 ? "resting" : `${v > 0 ? "puff" : "sip"} ${Math.round(a * 100)}%${a >= marks.hard ? " · hard" : a >= marks.soft ? " · soft" : ""}`;
  return (
    <div className={on ? "breath-check on" : "breath-check"} role="status" aria-label={`Sip-and-puff ${on ? "connected" : "not plugged in"}${on ? `, ${words}` : ""}`}>
      <span className="breath-check-label">
        <b>sip-and-puff</b> {on ? "✓" : "✗"}
      </span>
      {on ? (
        <span className="breath-check-meter" aria-hidden="true">
          <span className="end">sip</span>
          <span className="track">
            <span className="fill" style={v < 0 ? { left: `${50 + v * 50}%`, width: `${a * 50}%` } : { left: "50%", width: `${a * 50}%` }} />
            <i className="mid" />
          </span>
          <span className="end">puff</span>
        </span>
      ) : null}
      <span className="breath-check-words">{words}</span>
    </div>
  );
}

export function TopBar({ state, busy, onRecalibrate }: { state: HelmState; busy: boolean; onRecalibrate: () => void }) {
  return (
    <header className="topbar">
      <h1 className="sr-only">Helm</h1>
      <Brand />
      <BreathCheck state={state} />
      <button className="btn primary" onClick={onRecalibrate} disabled={busy} title="Measure your resting face, head range and expressions again">
        Recalibrate
      </button>
    </header>
  );
}
