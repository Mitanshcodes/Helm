// OWNER: P4
// Read-only viewer beside the game (?overlay=1): no calibration, profile changes, audio, camera capture or
// controller writes. Same LCD look as the dashboard.
import { useEffect, useState } from "react";
import { CameraView } from "./components/CameraView";
import { ControllerView, NEUTRAL_CONTROL } from "./components/ControllerView";
import { useOptions } from "./components/OptionsBar";
import { useHelmSocket } from "./useHelmSocket";
import "./overlay.css";

const ignoreEvent = () => {};
const STALE_MS = 1500;

export default function Overlay() {
  const { state, frame, connection, lastStateAt } = useHelmSocket(ignoreEvent);
  useOptions(); // same contrast, motion and text size as the main window
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, []);
  const live = connection === "open" && lastStateAt > 0 && now - lastStateAt < STALE_MS;
  const ready = live && state !== null;
  const status = !ready ? (connection === "connecting" ? "CONNECTING…" : "RECONNECTING…")
    : state.paused ? "II PAUSED" : state.progress ? "● SETTING UP" : !state.face ? "□ NO FACE" : "▶ LIVE";
  // state.control already contains the runtime's safety gating. Never infer outputs from gestures.
  const control = ready ? state.control : NEUTRAL_CONTROL;
  return (
    <main className="screen game-overlay">
      <header className="overlay-header">
        <span className="wordmark small" aria-hidden="true">helm</span>
        <h1 className="sr-only">Helm</h1>
        <span className="tag" role="status">{status.toLowerCase()}</span>
      </header>
      <section className="camera-col">
        {state ? <CameraView frame={ready ? frame : null} state={state} compact /> : <p className="camera-msg static">WAITING FOR HELM</p>}
      </section>
      <section className="paper-card" aria-label="Live controller">
        <p className={control.buttons.length ? "pad-pressing on" : "pad-pressing"}>
          {control.buttons.length ? `Pressing ${control.buttons.join(" + ")}` : "No buttons pressed"}
        </p>
        <ControllerView control={control} mapping={state?.mapping} breathConnected={state?.breath_connected} />
      </section>
      <footer className="overlay-footer fine">
        <span>{ready ? `${state.fps.toFixed(0)} FPS · ${state.latency_ms.total.toFixed(0)} MS` : "Inputs cleared while disconnected"}</span>
        <span>{state ? state.profile.game.toUpperCase() : ""}</span>
      </footer>
      {ready && state.progress && <p className="overlay-notice paper-card" role="status">{state.progress.prompt}</p>}
      {!ready && <p className="overlay-notice paper-card">Keep HELM running. This window reconnects by itself.</p>}
    </main>
  );
}
