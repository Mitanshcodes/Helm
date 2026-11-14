// OWNER: P4
// fps, total latency, face found or lost, paused, breath sensor, player and game.
import type { HelmState } from "../types";

export function StatusBar({ state }: { state: HelmState }) {
  // TODO(P4): styling for the judge-facing screen.
  return (
    <header className="panel status">
      <span>{state.fps.toFixed(0)} fps</span>
      <span>{state.latency_ms.total.toFixed(0)} ms</span>
      <span className={state.face ? "accent" : ""}>{state.face ? "Face found" : "Face lost"}</span>
      {state.paused && <span>Paused</span>}
      <span>{state.breath_connected ? "Breath sensor on" : "No breath sensor"}</span>
      <span>
        {state.profile.player} · {state.profile.game}
      </span>
    </header>
  );
}
