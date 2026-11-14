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

export function TopBar({ busy, onRecalibrate }: { busy: boolean; onRecalibrate: () => void }) {
  return (
    <header className="topbar">
      <h1 className="sr-only">Helm</h1>
      <Brand />
      <button className="btn primary" onClick={onRecalibrate} disabled={busy} title="Measure your resting face, head range and expressions again">
        Recalibrate
      </button>
    </header>
  );
}
