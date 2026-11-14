// OWNER: P4
// Table setup: which profile is loaded, the "Next visitor" reset, and the sound settings.
import { useEffect, useState } from "react";
import { humanize } from "../format";
import type { HelmState, Send } from "../types";

export const JUDGE = "judge"; // the shared quick-start identity (profiles/judge)

export function ProfileCard(props: {
  state: HelmState;
  send: Send;
  profiles: Record<string, string[]>;
  voice: boolean;
  setVoice: (on: boolean) => void;
  clicks: boolean;
  setClicks: (on: boolean) => void;
}) {
  const { state, send, profiles, voice, setVoice, clicks, setClicks } = props;
  const current = `${state.profile.player}/${state.profile.game}`;
  const options = Object.entries(profiles).flatMap(([player, games]) => games.map((game) => `${player}/${game}`));
  if (!options.includes(current)) options.unshift(current);
  const [choice, setChoice] = useState(current);
  useEffect(() => setChoice(current), [current]);
  const [player, game] = choice.split("/");

  return (
    <section className="card">
      <h2>Table setup</h2>
      <label className="field-label" htmlFor="profile">
        Profile
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
          Load
        </button>
      </div>
      <p className="caption">Loading a profile brings its mapping, calibration and learned gestures. Judge never keeps a calibration.</p>

      <div className="toggles">
        <label className="toggle">
          <input type="checkbox" checked={voice} onChange={(e) => setVoice(e.target.checked)} />
          <span>Read setup prompts aloud</span>
        </label>
        <label className="toggle">
          <input type="checkbox" checked={clicks} onChange={(e) => setClicks(e.target.checked)} />
          <span>Click when an input fires</span>
        </label>
      </div>
      <button className="btn" onClick={() => send({ cmd: "save_profile" })}>
        Save this profile
      </button>
    </section>
  );
}
