// OWNER: P4
// Game picker, "Build my mapping", the proposed mapping with the coach's reasons, Accept, session review.
import { useEffect, useState } from "react";
import type { CoachResult, HelmState, Mapping, Send } from "../types";
import { MappingTable } from "./MappingView";

const GAMES = ["SuperTuxKart"]; // suggestions only; any game name can be typed

export function CoachPanel(props: { state: HelmState; send: Send; result: CoachResult | null; busy: boolean; apply: (m: Mapping) => void }) {
  const { state, send, result, busy, apply } = props;
  const [game, setGame] = useState(state.profile.game);
  const [accepted, setAccepted] = useState(false);
  const name = game.trim();
  const reasons = result ? [...result.rationale, ...result.changes] : [];

  useEffect(() => setGame(state.profile.game), [state.profile.game]);
  useEffect(() => setAccepted(false), [result]);

  return (
    <section className="tool">
      <div className="line">
        <input list="games" value={game} onChange={(e) => setGame(e.target.value)} aria-label="Game" />
        <datalist id="games">
          {GAMES.map((g) => (
            <option key={g} value={g} />
          ))}
        </datalist>
        <button className="btn primary" disabled={busy || !/^[A-Za-z0-9_-]{1,32}$/.test(name)} onClick={() => send({ cmd: "coach_build", game: name })}>
          Build my mapping
        </button>
      </div>
      <button className="btn" disabled={busy} onClick={() => send({ cmd: "coach_review" })}>
        Review my session
      </button>
      {busy && <p className="muted">The coach is working…</p>}

      {result && !busy && (
        <>
          <MappingTable mapping={result.mapping} />
          <ul className="reasons">
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <div className="line">
            <button
              className="btn primary"
              disabled={accepted}
              onClick={() => {
                apply(result.mapping);
                setAccepted(true);
              }}
            >
              {accepted ? "Accepted" : "Accept"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
