// OWNER: P4
// Read-only viewer: no calibration, profile changes, audio, camera capture or controller writes.
import { useEffect, useState } from "react";
import { CameraView } from "./components/CameraView";
import { ControllerView, NEUTRAL_CONTROL } from "./components/ControllerView";
import { useHelmSocket } from "./useHelmSocket";
import "./overlay.css";

const ignoreEvent = () => {};
const STALE_MS = 1500;

export default function Overlay() {
  const { state, frame, connection, lastStateAt } = useHelmSocket(ignoreEvent);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, []);
  const live = connection === "open" && lastStateAt > 0 && now - lastStateAt < STALE_MS;
  const ready = live && state !== null;
  const status = !ready ? (connection === "connecting" ? "Connecting…" : "Reconnecting…")
    : state.paused ? "Paused" : state.progress ? "Setup in progress" : !state.face ? "No face found" : "Live";
  // state.control already contains the runtime's safety gating. Never infer outputs from gestures.
  const control = ready ? state.control : NEUTRAL_CONTROL;
  return (
    <main className="game-overlay">
      <header className="overlay-header">
        <h1>Helm <span>Live inputs</span></h1>
        <span className={`overlay-status${ready && state.face && !state.paused && !state.progress ? " live" : ""}`} role="status">{status}</span>
      </header>
      {state ? <CameraView frame={ready ? frame : null} state={state} compact /> : (
        <section className="overlay-camera-empty"><p>Waiting for Helm</p><span>Start Helm on this port to see your camera.</span></section>
      )}
      <section className="overlay-controller" aria-label="Live controller">
        <div className="overlay-section-head"><h2>Controller</h2><span>{ready ? "Mapped output" : "Signal unavailable"}</span></div>
        <ControllerView control={control} />
        <p className="overlay-button-readout">{control.buttons.length ? control.buttons.join(" · ") : "No buttons pressed"}</p>
      </section>
      <footer className="overlay-footer">
        <span>{ready ? `${state.fps.toFixed(0)} fps · ${state.latency_ms.total.toFixed(0)} ms` : "Inputs cleared while disconnected"}</span>
        <span>{state ? state.profile.game : "Camera + controller"}</span>
      </footer>
      {ready && state.progress && <p className="overlay-notice" role="status">{state.progress.prompt}</p>}
      {!ready && <p className="overlay-notice">Keep Helm running. This window reconnects automatically.</p>}
    </main>
  );
}
