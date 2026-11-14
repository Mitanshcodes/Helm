// OWNER: P4
// Name field, "Teach a gesture", live take prompts, accuracy after training, learned gestures with delete.
import type { HelmState, Send } from "../types";

export function GestureRecorder({ state, send }: { state: HelmState; send: Send }) {
  // TODO(P4): name field and "Teach a gesture" (record_gesture), record_negative, accuracy from the
  // gesture_trained event.
  return (
    <section className="panel">
      <h2>Learned gestures</h2>
      <ul>
        {state.gestures.learned.map((name) => (
          <li key={name}>
            {name} <button onClick={() => send({ cmd: "delete_gesture", name })}>Delete</button>
          </li>
        ))}
      </ul>
    </section>
  );
}
