// OWNER: P4
// The top-of-page panel for teaching your own move: a short introduction with the name, a calm "get ready"
// pause before each recording, and the result. The recordings themselves run in the Wizard.
import { useEffect, useRef, useState } from "react";
import { speak } from "../feedback";
import { humanize } from "../format";
import { READY_MS, type TeachFlow } from "../teach";
import type { HelmState, Mapping } from "../types";
import { PutOnButton } from "./PutOnButton";

const MIN_ACCURACY = 0.85; // below this, offer more takes (docs/SPEC.md 6.11)
const R = 44;
const C = 2 * Math.PI * R;

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
    <div className="teach-intro">
      <div className="teach-copy">
        <p className="eyebrow">Optional · about {withFace ? "2 minutes" : "40 seconds"}</p>
        <h2 className="teach-title">Teach Helm your own move</h2>
        <p className="teach-lead">
          Any movement you can repeat works: a small one, a slow one, or one on just one side of your face. Helm learns it from you.
        </p>
        <ol className="teach-plan">
          {withFace && (
            <li>
              <b>Your everyday face.</b> Relax for a moment, then read a short text aloud, so talking never sets anything off.
            </li>
          )}
          <li>
            <b>Your move, a few times.</b> When the screen turns blue and says go, do it and hold. Then relax.
          </li>
          <li>
            <b>See how well it learned.</b> You can add more tries if it needs them.
          </li>
        </ol>
      </div>
      <form
        className="teach-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) begin(name, withFace);
        }}
      >
        <label className="field-label" htmlFor="move-name">
          Name your move
        </label>
        <input id="move-name" ref={input} value={raw} onChange={(e) => setRaw(e.target.value)} />
        <p className="caption">
          {learned.includes(name) ? `${humanize(name)} is already learned: this adds more tries to it.` : "Keep this name or type your own."}
        </p>
        <label className="toggle">
          <input type="checkbox" checked={withFace} onChange={(e) => setWithFace(e.target.checked)} />
          <span>{needsFace ? "Include the everyday face (needed once)" : "Record the everyday face again"}</span>
        </label>
        <div className="teach-actions">
          <button type="submit" className="btn primary big" disabled={!valid}>
            Start
          </button>
          <button type="button" className="btn" onClick={close}>
            Not now
          </button>
        </div>
      </form>
    </div>
  );
}

function Ready({ flow, go, close, voice }: Props) {
  const [now, setNow] = useState(() => performance.now());
  const face = flow.stage === "ready_face";
  const title = face ? "First, your everyday face" : `Now your move: ${humanize(flow.name)}`;
  const body = face
    ? "Look at the screen and relax. Then a short text appears: read it aloud at your own pace. Mouthing the words is fine."
    : "Get ready on Get ready, do your move on Go and hold it, then relax. It repeats a few times.";

  useEffect(() => {
    const t = window.setInterval(() => setNow(performance.now()), 200);
    return () => window.clearInterval(t);
  }, []);
  useEffect(() => {
    if (voice) speak(`${title}. ${face ? "Look at the screen and relax." : "Do it when the screen says go."}`);
  }, [title, face, voice]);

  const left = Math.max(0, flow.readyUntil - now);
  const seconds = Math.ceil(left / 1000);
  return (
    <div className="teach-ready">
      <svg className="countdown" viewBox="0 0 100 100" role="img" aria-label={`Starting in ${seconds} seconds`}>
        <circle className="ring-track" cx="50" cy="50" r={R} />
        <circle className="ring-fill" cx="50" cy="50" r={R} strokeDasharray={C} strokeDashoffset={C * (1 - left / READY_MS)} />
        <text x="50" y="50" dominantBaseline="central" textAnchor="middle">
          {seconds}
        </text>
      </svg>
      <div className="teach-copy">
        <p className="eyebrow">{flow.withFace ? (face ? "Part 1 of 2" : "Part 2 of 2") : "Get ready"}</p>
        <h2 className="teach-title">{title}</h2>
        <p className="teach-lead">{body}</p>
        <div className="teach-actions">
          <button className="btn primary" onClick={go}>
            Start now
          </button>
          <button className="btn" onClick={close}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function Result({ state, flow, begin, offer, close, mapping, apply }: Props) {
  const result = flow.result;
  const accuracy = result?.accuracy ?? null;
  const weak = accuracy !== null && accuracy < MIN_ACCURACY;
  return (
    <div className={weak ? "teach-result weak" : "teach-result"}>
      <div className="teach-copy">
        <p className="eyebrow">{weak ? "Almost there" : "Done"}</p>
        <h2 className="teach-title">{humanize(flow.name)} learned</h2>
        <p className="teach-lead">
          {accuracy === null
            ? "Helm has your move. Put it on a button:"
            : weak
              ? `Helm recognized it ${Math.round(accuracy * 100)}% of the time on tries it had not seen. A few more tries usually fix that, or try a more distinct movement.`
              : `Helm recognized it ${Math.round(accuracy * 100)}% of the time on tries it had not seen. Put it on a button:`}
        </p>
        {!weak && <PutOnButton gesture={flow.name} mapping={mapping} catalog={state.catalog} apply={apply} />}
      </div>
      <div className="teach-actions">
        {weak && (
          <button className="btn primary" onClick={() => begin(flow.name, false)}>
            Add more tries
          </button>
        )}
        <button className={weak ? "btn" : "btn primary"} onClick={offer}>
          Teach another move
        </button>
        <button className="btn" onClick={close}>
          Done
        </button>
      </div>
    </div>
  );
}

export function TeachPanel(props: Props) {
  const { flow } = props;
  const panel = useRef<HTMLElement>(null);

  // Opened from further down the page (the "Teach a move" button in Your moves): glide back to the top, where
  // the panel lives. When it is already in view, leave the page where it is.
  useEffect(() => {
    const top = panel.current?.getBoundingClientRect().top ?? 0;
    if (top < 0 || top > window.innerHeight * 0.6) window.scrollTo({ top: 0, behavior: "smooth" });
  }, [flow.stage]);

  return (
    <section ref={panel} className="card teach-panel" aria-live="polite" key={flow.stage}>
      {flow.stage === "intro" && <Intro {...props} />}
      {(flow.stage === "ready_face" || flow.stage === "ready_move") && <Ready {...props} />}
      {flow.stage === "result" && <Result {...props} />}
      {(flow.stage === "face" || flow.stage === "move") && <p className="teach-lead">Saving…</p>}
    </section>
  );
}
