// OWNER: P4
// The masthead: the "helm" wordmark printed over the wheel, the issue line, who is playing what, the buttons
// (Next visitor, Recalibrate or Skip, Pause), and the round status stamp.
import { humanize } from "../format";
import type { HelmState } from "../types";
import { Blur } from "./Blur";
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

const STAMP: Record<Status, string> = {
  offline: "OFFLINE",
  calibrating: "SETUP",
  teaching: "LEARNING",
  paused: "PAUSED",
  noface: "NO FACE",
  live: "LIVE",
};

export function Wordmark() {
  return (
    <div className="wordmark-wrap" aria-hidden="true">
      <HelmWheel className="wordmark-wheel" size={96} />
      <span className="wordmark">helm</span>
    </div>
  );
}

export function StatusStamp({ status }: { status: Status }) {
  return (
    <div className={`status-stamp ${status}`} role="status">
      <small>STATUS</small>
      <b>{STAMP[status]}</b>
    </div>
  );
}

export function Header(props: {
  state: HelmState;
  status: Status;
  setup: boolean; // calibration or teaching is on screen: the live-only buttons are faded and unreachable
  canSkip: boolean;
  hold: number;
  onNextPlayer?: () => void;
  onPause: () => void;
  onRecalibrate: () => void;
  onSkip: () => void;
}) {
  const { state, status, setup, canSkip, hold, onNextPlayer, onPause, onRecalibrate, onSkip } = props;
  const skipping = status === "calibrating" && canSkip;
  return (
    <header className="masthead">
      <h1 className="sr-only">Helm</h1>
      <Wordmark />
      <div className="masthead-text">
        <p className="kicker">ISSUE #1 · HACKPRINCETON FALL '26</p>
        <p className="who">
          <mark>{humanize(state.profile.player)}</mark> is playing <mark>{state.profile.game}</mark> with their face.
        </p>
        <div className="masthead-actions">
          {onNextPlayer && (
            <Blur on={setup} className="inline">
              <button className="btn" onClick={onNextPlayer} title="Load the guest profile and run a quick calibration">
                Next visitor
              </button>
            </Blur>
          )}
          {skipping ? (
            <button className="btn" onClick={onSkip} title="Stop the full calibration and only learn the resting face (2 s)">
              Skip calibration
            </button>
          ) : (
            <button className="btn" onClick={onRecalibrate} disabled={state.progress !== null}>
              Recalibrate
            </button>
          )}
          <Blur on={setup} className="inline">
            <button className="btn pink" aria-pressed={state.paused} onClick={onPause}>
              <b>{state.paused ? "Resume" : "Pause"}</b> <small>· or close eyes {hold} s</small>
            </button>
          </Blur>
        </div>
      </div>
      <StatusStamp status={status} />
    </header>
  );
}
