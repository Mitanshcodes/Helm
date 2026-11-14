// OWNER: P4
// "Your moves": the learned gestures with delete, and the button that opens the teach panel at the top.
import { humanize } from "../format";
import type { HelmState, Send } from "../types";

export function GestureRecorder({ state, send, busy, onTeach }: { state: HelmState; send: Send; busy: boolean; onTeach: () => void }) {
  const learned = state.gestures.learned;
  return (
    <section className="card">
      <h2>Your moves</h2>
      <p className="caption">Moves Helm learned from you. Map them to buttons in the coach or the mapping.</p>
      <ul className="list">
        {learned.map((g) => (
          <li key={g}>
            <span>{humanize(g)}</span>
            <button className="btn" disabled={busy} onClick={() => send({ cmd: "delete_gesture", name: g })}>
              Delete
            </button>
          </li>
        ))}
        {learned.length === 0 && <li className="muted">None yet</li>}
      </ul>
      <button className="btn primary teach-open" disabled={busy} onClick={onTeach}>
        Teach a move
      </button>
    </section>
  );
}
