// OWNER: P4
// Name field, "Teach a gesture", live take prompts (in the Wizard), accuracy after training, learned gestures.
import { useState } from "react";
import type { HelmState, Send, Trained } from "../types";

const MIN_ACCURACY = 0.85; // below this, ask for more takes (docs/SPEC.md 6.11)

// The server accepts letters, digits and underscores, up to 32, and not the reserved class name "none".
const clean = (raw: string) => raw.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 32);

export function GestureRecorder(props: { state: HelmState; send: Send; trained: Trained | null; busy: boolean }) {
  const { state, send, trained, busy } = props;
  const [raw, setRaw] = useState("");
  const name = clean(raw);
  const valid = name !== "" && name !== "none";
  const teach = () => valid && !busy && send({ cmd: "record_gesture", name });

  return (
    <section className="card">
      <h2>Teach a gesture</h2>
      <form
        className="line"
        onSubmit={(e) => {
          e.preventDefault();
          teach();
        }}
      >
        <input value={raw} onChange={(e) => setRaw(e.target.value)} placeholder="Name it, e.g. left smirk" aria-label="Gesture name" />
        <button type="submit" className="btn primary" disabled={!valid || busy}>
          Teach
        </button>
      </form>
      <button className="btn" disabled={busy} onClick={() => send({ cmd: "record_negative" })}>
        Record what not to fire on (15 s)
      </button>

      {trained && (
        <p className={trained.accuracy !== null && trained.accuracy < MIN_ACCURACY ? "notice" : "result"}>
          {trained.name === "none" ? "Negatives recorded" : `${trained.name.replace(/_/g, " ")} learned`}
          {trained.accuracy !== null && ` · ${Math.round(trained.accuracy * 100)}% accurate on held-out takes`}
          {trained.accuracy !== null && trained.accuracy < MIN_ACCURACY && ". Teach it again for more takes, or try a more distinct movement."}
        </p>
      )}

      <ul className="list">
        {state.gestures.learned.map((g) => (
          <li key={g}>
            <span>{g.replace(/_/g, " ")}</span>
            <button className="btn" disabled={busy} onClick={() => send({ cmd: "delete_gesture", name: g })}>
              Delete
            </button>
          </li>
        ))}
        {state.gestures.learned.length === 0 && <li className="muted">No learned gestures yet</li>}
      </ul>
    </section>
  );
}
