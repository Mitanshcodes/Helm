// OWNER: P4
// Read-only table of the current mapping (gesture, target, mode) and a JSON box with validation errors.
import type { HelmState, Send } from "../types";

export function MappingView({ state, send }: { state: HelmState; send: Send }) {
  // TODO(P4): the server does not send the mapping yet; agree with P1 how the dashboard gets it.
  // Editing is a JSON text box sent with set_mapping; show the returned errors underneath.
  void send;
  return (
    <section className="panel">
      <h2>Mapping</h2>
      <p>
        {state.profile.player} · {state.profile.game}
      </p>
    </section>
  );
}
