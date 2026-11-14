// OWNER: P4
// "Your moves": the learned gestures with delete, and the button that opens the teach panel at the top.
import { humanize } from "../format";
import type { HelmState, Mapping, Send } from "../types";
import { PutOnButton } from "./PutOnButton";

export function GestureRecorder(props: { state: HelmState; send: Send; busy: boolean; onTeach: () => void; mapping: Mapping | null; apply: (m: Mapping) => void }) {
  const { state, send, busy, onTeach, mapping, apply } = props;
  const learned = state.gestures.learned;
  return (
    <section className="tool">
      <p className="caption">Moves Helm learned from you. Tap a button to put a move on it (tap again to take it off).</p>
      <ul className="list">
        {learned.map((g) => (
          <li key={g} className="move-row">
            <span className="move-name">{humanize(g)}</span>
            <PutOnButton gesture={g} mapping={mapping} catalog={state.catalog} apply={apply} />
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
