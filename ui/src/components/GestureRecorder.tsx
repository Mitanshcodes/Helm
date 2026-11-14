// OWNER: P4
// "Teach a gesture": name it first (pre-filled, so nobody has to type), then Helm learns the player's everyday
// face once, then records the movement. The large prompts run in the Wizard; this card starts the flow, shows
// the result and lists what has been learned.
import { useEffect, useState } from "react";
import { humanize } from "../format";
import type { TeachFlow } from "../teach";
import type { HelmState, Send, Trained } from "../types";

const MIN_ACCURACY = 0.85; // below this, ask for more takes (docs/SPEC.md 6.11)

// The server accepts letters, digits and underscores, up to 32, and not the reserved class name "none".
const clean = (raw: string) =>
  raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 32);

function suggestedName(learned: string[]): string {
  for (let n = learned.length + 1; ; n++) if (!learned.includes(`move_${n}`)) return `Move ${n}`;
}

export function GestureRecorder(props: {
  state: HelmState;
  send: Send;
  trained: Trained | null;
  flow: TeachFlow | null;
  hasFace: boolean;
  start: (name: string, withFace: boolean) => void;
}) {
  const { state, send, trained, flow, hasFace, start } = props;
  const learned = state.gestures.learned;
  const needsFace = !hasFace && learned.length === 0; // a player with learned gestures has an everyday face on file
  const [raw, setRaw] = useState(() => suggestedName(learned));
  const [edited, setEdited] = useState(false);
  const [withFace, setWithFace] = useState(needsFace);
  const name = clean(raw);
  const valid = name !== "" && name !== "none";
  const busy = state.progress !== null || flow !== null;
  const exists = learned.includes(name);

  const learnedKey = learned.join(",");
  useEffect(() => {
    if (!edited) setRaw(suggestedName(learned));
  }, [learnedKey, edited]); // eslint-disable-line react-hooks/exhaustive-deps
  // Back to the sensible default whenever a run ends, the player changes, or their first gesture lands.
  useEffect(() => {
    if (!flow) setWithFace(needsFace);
  }, [needsFace, state.profile.player, flow]);

  const begin = () => {
    if (!valid || busy) return;
    start(name, withFace);
    setEdited(false);
  };

  const weak = trained !== null && trained.name !== "none" && trained.accuracy !== null && trained.accuracy < MIN_ACCURACY;

  return (
    <section className="card">
      <h2>Teach a gesture</h2>
      <ol className="teach-steps">
        <li className={withFace ? "" : "skipped"}>
          <b>Your everyday face</b>
          <span>Relax, then read a short text aloud, so talking never fires anything. Once per player.</span>
        </li>
        <li>
          <b>Your movement</b>
          <span>Any movement you can repeat, however small, even on one side.</span>
        </li>
      </ol>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          begin();
        }}
      >
        <label className="field-label" htmlFor="gesture-name">
          Name
        </label>
        <div className="line">
          <input
            id="gesture-name"
            value={raw}
            onChange={(e) => {
              setRaw(e.target.value);
              setEdited(true);
            }}
            aria-describedby="gesture-name-hint"
          />
          <button type="submit" className="btn primary" disabled={!valid || busy}>
            Start
          </button>
        </div>
        <p id="gesture-name-hint" className="caption">
          {exists ? `${humanize(name)} is already learned: this adds more takes to it.` : "Keep the suggested name or type your own."}
        </p>
        <label className="toggle">
          <input type="checkbox" checked={withFace} disabled={busy} onChange={(e) => setWithFace(e.target.checked)} />
          <span>{needsFace ? "Record the everyday face first" : "Record the everyday face again"}</span>
        </label>
      </form>

      {flow && (
        <p className="result" aria-live="polite">
          Teaching {humanize(flow.name)}: {flow.stage === "face" ? "everyday face" : "your movement"}
        </p>
      )}
      {!flow && trained && trained.name !== "none" && (
        <div className={weak ? "outcome weak" : "outcome"} aria-live="polite">
          <b>{humanize(trained.name)} learned</b>
          {trained.accuracy !== null && <span>{Math.round(trained.accuracy * 100)}% accurate on takes it had not seen</span>}
          {weak && (
            <>
              <span>Helm sometimes mixes it up with other movements. More takes usually fix that, or try a more distinct movement.</span>
              <button className="btn" onClick={() => start(trained.name, false)}>
                Add more takes
              </button>
            </>
          )}
        </div>
      )}
      {!flow && trained?.name === "none" && <p className="result">Everyday face recorded</p>}

      <ul className="list">
        {learned.map((g) => (
          <li key={g}>
            <span>{humanize(g)}</span>
            <button className="btn" disabled={busy} onClick={() => send({ cmd: "delete_gesture", name: g })}>
              Delete
            </button>
          </li>
        ))}
        {learned.length === 0 && <li className="muted">No learned gestures yet</li>}
      </ul>
    </section>
  );
}
