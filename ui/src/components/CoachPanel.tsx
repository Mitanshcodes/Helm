// OWNER: P4
// The Captain (the AI coach, on the player's own Claude login): tell it what you want in plain words, or use a
// quick button. It answers with changes to the CURRENT mapping (everything else stays as it is), each with its
// reason. Its steps show live while it works. Apply puts the changes in; Undo takes them back.
import { useEffect, useState } from "react";
import type { CoachResult, HelmState, Mapping, Send } from "../types";

const IDEAS = [
  "Steering needs too much head turning",
  "Gestures fire when I talk",
  "Put skid on my smile",
  "Brake by sipping on the tube",
];

/** Undo for the Captain's last applied answer. Kept by App so it survives closing the page. */
export interface CaptainUndo {
  result: CoachResult; // the answer that was applied
  before: Mapping | null; // the mapping it replaced
}

export function CoachPanel(props: {
  state: HelmState; send: Send; result: CoachResult | null; busy: boolean; steps: string[]; apply: (m: Mapping) => void;
  undo: CaptainUndo | null; setUndo: (u: CaptainUndo | null) => void;
}) {
  const { state, send, result, busy, steps, apply, undo, setUndo } = props;
  const [text, setText] = useState("");
  const [game, setGame] = useState(state.profile.game);
  const applied = undo !== null && undo.result === result;
  const before = applied ? undo.before : null;
  const request = text.trim();

  useEffect(() => setGame(state.profile.game), [state.profile.game]);

  const ask = (r: string) => {
    if (!r || busy) return;
    send({ cmd: "coach_ask", request: r });
    setText("");
  };
  const changes = result?.changes.filter((c) => c.change || c.reason) ?? [];
  const offline = result?.backend === "offline";

  return (
    <section className="tool captain">
      <form
        className="captain-ask"
        onSubmit={(e) => {
          e.preventDefault();
          ask(request);
        }}
      >
        <label className="field-label" htmlFor="captain-text">
          Tell the Captain
        </label>
        <div className="line">
          <input
            id="captain-text"
            value={text}
            maxLength={500}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. my jaw gets tired, use something else for nitro"
            autoComplete="off"
          />
          <button type="submit" className="btn primary" disabled={busy || !request}>
            Send
          </button>
        </div>
        <div className="captain-ideas">
          {IDEAS.map((idea) => (
            <button key={idea} type="button" className="btn small" disabled={busy} onClick={() => ask(idea)}>
              {idea}
            </button>
          ))}
        </div>
      </form>

      <div className="line captain-quick">
        <input value={game} onChange={(e) => setGame(e.target.value)} aria-label="Game" className="captain-game" />
        <button className="btn" disabled={busy || !/^[A-Za-z0-9_-]{1,32}$/.test(game.trim())} onClick={() => send({ cmd: "coach_build", game: game.trim() })}>
          Set me up for this game
        </button>
        <button className="btn" disabled={busy} onClick={() => send({ cmd: "coach_review" })}>
          Review my session
        </button>
      </div>

      {(busy || steps.length > 0) && !result && (
        <ol className="captain-steps" aria-live="polite">
          {steps.map((s, i) => (
            <li key={i} className={i === steps.length - 1 && busy ? "now" : "done"}>
              {s}
            </li>
          ))}
        </ol>
      )}

      {result && !busy && (
        <div className="captain-result">
          <p className="captain-meta">
            {offline ? (
              <span className="tag">Offline coach</span>
            ) : (
              <span className="tag">On your Claude account · {result.elapsed_s} s</span>
            )}{" "}
            {offline ? result.offline_reason : result.request}
          </p>
          {result.summary && <p className="captain-summary">{result.summary}</p>}
          {changes.length > 0 ? (
            <ul className="captain-changes">
              {changes.map((c, i) => (
                <li key={i}>
                  {c.change && <b>{c.change}</b>}
                  {c.reason && <span>{c.reason}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No changes needed.</p>
          )}
          {changes.some((c) => c.change) && (
            <div className="line">
              {!applied ? (
                <button
                  className="btn primary"
                  onClick={() => {
                    setUndo({ result, before: state.mapping ?? null });
                    apply(result.mapping);
                  }}
                >
                  Apply {changes.filter((c) => c.change).length} change{changes.filter((c) => c.change).length === 1 ? "" : "s"}
                </button>
              ) : (
                <>
                  <span className="result">Applied</span>
                  {before && (
                    <button
                      className="btn"
                      onClick={() => {
                        apply(before);
                        setUndo(null);
                      }}
                    >
                      Undo
                    </button>
                  )}
                  <button className="btn" onClick={() => send({ cmd: "save_profile" })}>
                    Save profile
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
