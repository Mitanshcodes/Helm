// OWNER: P4
// The card for teaching your own move, shown over the blurred moves panel: a short introduction with the name,
// a calm "get ready" pause before each recording, and the result. The recordings themselves run in the Wizard.
import { useEffect, useRef, useState } from "react";
import { speak } from "../feedback";
import { humanize } from "../format";
import { READY_MS, TAKES_LABEL, type TeachFlow } from "../teach";
import type { HelmState, Mapping } from "../types";
import { PutOnButton } from "./PutOnButton";

const MIN_ACCURACY = 0.85; // below this, offer more takes (docs/SPEC.md 6.11)

// The server accepts letters, digits and underscores, up to 32, and not the reserved class name "none".
export const cleanName = (raw: string) =>
  raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 32);

function suggestedName(learned: string[]): string {
  for (let n = learned.length + 1; ; n++) if (!learned.includes(`move_${n}`)) return `Move ${n}`;
}

interface Props {
  state: HelmState;
  flow: TeachFlow;
  hasFace: boolean;
  voice: boolean;
  begin: (name: string, withFace: boolean) => void;
  go: () => void;
  offer: () => void;
  close: () => void;
  mapping: Mapping | null;
  apply: (m: Mapping) => void;
}

function Intro({ state, hasFace, begin, close }: Props) {
  const learned = state.gestures.learned;
  const needsFace = !hasFace && learned.length === 0;
  const [raw, setRaw] = useState(() => suggestedName(learned));
  const [withFace, setWithFace] = useState(needsFace);
  const input = useRef<HTMLInputElement>(null);
  const name = cleanName(raw);
  const valid = name !== "" && name !== "none";

  useEffect(() => input.current?.select(), []);

  return (
    <div className="setup-card wide">
      <h2 className="card-title">NEW MOVE · OPTIONAL · {withFace ? "ABOUT 2 MIN" : TAKES_LABEL.toUpperCase()}</h2>
      <p className="instruction">Teach HELM your own move.</p>
      <p className="lead">Any movement you can repeat works: a small one, a slow one, or one on just one side of your face.</p>
      <ol className="plan">
        {withFace && (
          <li>
            <b>Your everyday face.</b> Relax, then read a short text aloud, so talking never sets anything off.
          </li>
        )}
        <li>
          <b>Your move, a few times.</b> When the card turns dark and says GO, do it and hold. Then relax.
        </li>
        <li>
          <b>See how well it learned.</b> Then put it on a button.
        </li>
      </ol>
      <form
        className="teach-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) begin(name, withFace);
        }}
      >
        <label className="field-label" htmlFor="move-name">
          NAME YOUR MOVE
        </label>
        <input id="move-name" ref={input} value={raw} onChange={(e) => setRaw(e.target.value)} />
        <p className="fine">
          {learned.includes(name) ? `${humanize(name)} is already learned: this adds more tries to it.` : "Keep this name or type your own."}
        </p>
        <label className="check">
          <input type="checkbox" checked={withFace} onChange={(e) => setWithFace(e.target.checked)} />
          <span>{needsFace ? "Include the everyday face (needed once)" : "Record the everyday face again"}</span>
        </label>
        <div className="card-actions">
          <button type="submit" className="btn primary" disabled={!valid}>
            START ▶
          </button>
          <button type="button" className="btn" onClick={close}>
            NOT NOW
          </button>
        </div>
      </form>
    </div>
  );
}

function Ready({ flow, go, close, voice }: Props) {
  const [now, setNow] = useState(() => performance.now());
  const face = flow.stage === "ready_face";
  const title = face ? "First, your everyday face." : `Now your move: ${humanize(flow.name)}.`;
  const body = face
    ? "Look at the screen and relax. Then a short text appears: read it aloud at your own pace. Mouthing the words is fine."
    : "Get ready, do your move on GO and hold it, then relax. It repeats a few times.";

  useEffect(() => {
    const t = window.setInterval(() => setNow(performance.now()), 200);
    return () => window.clearInterval(t);
  }, []);
  useEffect(() => {
    if (voice) speak(`${title} ${face ? "Look at the screen and relax." : "Do it when the screen says go."}`);
  }, [title, face, voice]);

  const left = Math.max(0, flow.readyUntil - now);
  const seconds = Math.ceil(left / 1000);
  const n = Math.round((left / READY_MS) * 10);
  return (
    <div className="setup-card">
      <h2 className="card-title">{flow.withFace ? (face ? "GET READY · PART 1 OF 2" : "GET READY · PART 2 OF 2") : "GET READY"}</h2>
      <div className="ready-row">
        <span className="count" aria-label={`Starting in ${seconds} seconds`}>
          {seconds}
        </span>
        <div>
          <p className="instruction" role="status" aria-live="polite">
            {title}
          </p>
          <p className="lead">{body}</p>
        </div>
      </div>
      <div className="bar big" aria-hidden="true">
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className={i < n ? "seg on" : "seg"} />
        ))}
      </div>
      <div className="card-actions">
        <button className="btn primary" onClick={go}>
          START NOW ▶
        </button>
        <button className="btn" onClick={close}>
          CANCEL
        </button>
      </div>
    </div>
  );
}

function Result({ state, flow, begin, offer, close, mapping, apply }: Props) {
  const result = flow.result;
  const accuracy = result?.accuracy ?? null;
  const weak = accuracy !== null && accuracy < MIN_ACCURACY;
  return (
    <div className="setup-card wide">
      <h2 className="card-title">{weak ? "ALMOST THERE" : "MOVE LEARNED"}</h2>
      <p className="instruction" role="status" aria-live="polite">
        {humanize(flow.name)} learned!
      </p>
      <p className="lead">
        {accuracy === null
          ? "HELM has your move. Put it on a button:"
          : weak
            ? `HELM recognized it ${Math.round(accuracy * 100)}% of the time on tries it had not seen. A few more tries usually fix that, or try a more distinct movement.`
            : `HELM recognized it ${Math.round(accuracy * 100)}% of the time on tries it had not seen. Put it on a button:`}
      </p>
      {!weak && <PutOnButton gesture={flow.name} mapping={mapping} catalog={state.catalog} apply={apply} />}
      <div className="card-actions">
        {weak && (
          <button className="btn primary" onClick={() => begin(flow.name, false)}>
            ADD MORE TRIES
          </button>
        )}
        <button className={weak ? "btn" : "btn primary"} onClick={close}>
          DONE
        </button>
        <button className="btn" onClick={offer}>
          TEACH ANOTHER
        </button>
      </div>
    </div>
  );
}

export function TeachPanel(props: Props) {
  const { flow } = props;
  return (
    <div className="teach" key={flow.stage}>
      {flow.stage === "intro" && <Intro {...props} />}
      {(flow.stage === "ready_face" || flow.stage === "ready_move") && <Ready {...props} />}
      {flow.stage === "result" && <Result {...props} />}
      {(flow.stage === "face" || flow.stage === "move") && (
        <div className="setup-card">
          <p className="instruction">Saving…</p>
        </div>
      )}
    </div>
  );
}
