// OWNER: P4
// The Captain (the AI coach): game picker, "Build my mapping", the proposed mapping with its reasons, Accept,
// session review.
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
      <p className="caption">The Captain looks up the game's controls and puts your strongest moves on the buttons that matter most.</p>
      {busy && <p className="muted">The Captain is working… (up to a couple of minutes when it looks a game up)</p>}

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
