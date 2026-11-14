// OWNER: P4
// Profile: which profile is loaded, loading another, and saving this one. Sound lives in the OPTIONS footer.
import { useEffect, useState } from "react";
import { humanize } from "../format";
import type { HelmState, Send } from "../types";

export const JUDGE = "judge"; // the shared quick-start identity (profiles/judge)

export function ProfileCard({ state, send, profiles }: { state: HelmState; send: Send; profiles: Record<string, string[]> }) {
  const current = `${state.profile.player}/${state.profile.game}`;
  const options = Object.entries(profiles).flatMap(([player, games]) => games.map((game) => `${player}/${game}`));
  if (!options.includes(current)) options.unshift(current);
  const [choice, setChoice] = useState(current);
  useEffect(() => setChoice(current), [current]);
  const [player, game] = choice.split("/");

  return (
    <section className="tool">
      <label className="field-label" htmlFor="profile">
        PROFILE
      </label>
      <div className="line">
        <select id="profile" value={choice} onChange={(e) => setChoice(e.target.value)}>
          {options.map((o) => {
            const [p, g] = o.split("/");
            return (
              <option key={o} value={o}>
                {humanize(p)} · {g}
              </option>
            );
          })}
        </select>
        <button className="btn primary" disabled={choice === current} onClick={() => send({ cmd: "load_profile", player, game })}>
          LOAD
        </button>
        <button className="btn" onClick={() => send({ cmd: "save_profile" })}>
          SAVE THIS PROFILE
        </button>
      </div>
      <p className="fine">Loading a profile brings its mapping, calibration and learned moves. The guest profile never keeps a calibration.</p>
    </section>
  );
}
