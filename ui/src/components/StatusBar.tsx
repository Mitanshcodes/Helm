// OWNER: P4
// Header (wordmark, player and game, live status pill, Recalibrate, Pause) and the paused banner.
import type { CalibrationMode, Connection, HelmState, Send } from "../types";

function WheelIcon() {
  const spokes = [0, 45, 90, 135, 180, 225, 270, 315];
  return (
    <svg className="wheel" viewBox="0 0 44 44" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" aria-hidden="true">
      <circle cx="22" cy="22" r="11" />
      <circle cx="22" cy="22" r="3.2" />
      {spokes.map((deg) => (
        <line key={deg} x1="22" y1="5" x2="22" y2="11" transform={`rotate(${deg} 22 22)`} />
      ))}
    </svg>
  );
}

function status(state: HelmState, connection: Connection): { tone: "ok" | "warn" | "off"; text: string } {
  if (connection !== "open") return { tone: "off", text: "Disconnected" };
  if (state.progress) return { tone: "ok", text: "Setting up" };
  if (state.paused) return { tone: "warn", text: "Paused" };
  if (!state.face) return { tone: "warn", text: "No face found" };
  return { tone: "ok", text: "Live — tracking your face" };
}

export function StatusBar(props: {
  state: HelmState;
  connection: Connection;
  send: Send;
  mode: CalibrationMode;
  compact: boolean;
  onNextVisitor?: () => void;
  onTeach?: () => void;
}) {
  const { state, connection, send, mode, compact, onNextVisitor, onTeach } = props;
  const { tone, text } = status(state, connection);
  const who = [state.profile?.player, state.profile?.game].filter(Boolean).map((s, i) => (i === 0 ? s.charAt(0).toUpperCase() + s.slice(1) : s));
  return (
    <header className="header">
      <div className="brand">
        <WheelIcon />
        <h1>Helm</h1>
        {who.length > 0 && !compact && <span className="who">{who.join(" · ")}</span>}
      </div>
      <div className="header-actions">
        <span className={`pill ${tone}`} aria-live="polite">
          <span className="dot" />
          {text}
        </span>
        {!compact && (
          <>
            <button className="btn" disabled={state.progress !== null} onClick={() => send({ cmd: "calibrate", mode })}>
              Recalibrate
            </button>
            {onTeach && (
              <button className="btn" disabled={state.progress !== null} onClick={onTeach}>
                Teach a move
              </button>
            )}
            {onNextVisitor && (
              <button className="btn" onClick={onNextVisitor} title="Load the judge profile and run a quick calibration">
                Next visitor
              </button>
            )}
            <button className="btn primary" onClick={() => send({ cmd: "pause", on: !state.paused })}>
              {state.paused ? "Resume" : "Pause · or close eyes 1 s"}
            </button>
          </>
        )}
      </div>
    </header>
  );
}

export function StatusBanner({ state }: { state: HelmState }) {
  if (!state.paused || state.progress) return null;
  return (
    <div className="banner" role="status">
      Paused — close your eyes for 1 second to resume
    </div>
  );
}
