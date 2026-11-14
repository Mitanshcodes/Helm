// OWNER: P4
// "Who's at the helm?": the profile screen after the intro, one taped-down tile per profile, like picking a
// profile on a streaming service. Judge is the shared 15-second setup (nothing saved); Tester and every saved
// player keep their calibration, mapping and moves; "New profile" makes one from a name.
import { useEffect, useRef, useState } from "react";
import { humanize } from "../format";
import type { IconName } from "../moves";
import { JUDGE } from "./ProfileCard";
import { FaceIcon, HelmWheel } from "./PixelIcon";

export const TESTER = "tester";
const HIDDEN = new Set(["guest", JUDGE, TESTER]); // judge and tester are always first; guest is the CLI default
const TONES = ["pink", "blue", "yellow", "navy"];
const ICONS: IconName[] = ["smile", "brow", "jaw", "pucker", "cheek", "nod"];
const TILTS = [-2, 1.5, -1, 2, -1.5, 1];
export const PROFILE_NAME = /^[A-Za-z0-9_-]{1,32}$/; // the server's rule: it becomes a folder name

interface Tile {
  id: string;
  label: string;
  note: string;
  icon: IconName;
}

function tiles(profiles: Record<string, string[]>): Tile[] {
  const saved = Object.keys(profiles)
    .filter((p) => !HIDDEN.has(p) && !p.startsWith("_"))
    .sort();
  return [
    { id: JUDGE, label: "Judge", note: "15-second setup · nothing saved", icon: "star" },
    { id: TESTER, label: "Tester", note: profiles[TESTER] ? "saved on this laptop" : "full setup, then saved", icon: "smile" },
    ...saved.map((id, i) => ({ id, label: humanize(id), note: "saved on this laptop", icon: ICONS[(i + 2) % ICONS.length] })),
  ];
}

export function ProfilePicker(props: { profiles: Record<string, string[]>; ready: boolean; onPick: (player: string) => void }) {
  const { profiles, ready, onPick } = props;
  const [creating, setCreating] = useState(false);
  const [raw, setRaw] = useState("");
  const first = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const name = raw.trim().toLowerCase().replace(/\s+/g, "_");
  const valid = PROFILE_NAME.test(name) && name !== "guest";
  const list = tiles(profiles);

  useEffect(() => first.current?.focus(), []);
  useEffect(() => {
    if (creating) input.current?.focus();
  }, [creating]);

  return (
    <main className="picker" aria-labelledby="picker-title">
      <div className="picker-brand" aria-hidden="true">
        <HelmWheel className="brand-wheel" size={52} />
        <span className="wordmark small">helm</span>
      </div>
      <h1 id="picker-title" className="picker-title">
        who's at the <span className="blue">helm</span>?
      </h1>
      <ul className="picker-tiles" role="list">
        {list.map((t, i) => (
          <li key={t.id} style={{ ["--tilt" as string]: `${TILTS[i % TILTS.length]}deg` }}>
            <button ref={i === 0 ? first : undefined} className="profile-tile" disabled={!ready} onClick={() => onPick(t.id)}>
              <span className={`avatar ${TONES[i % TONES.length]}`}>
                <FaceIcon name={t.icon} size={96} />
              </span>
              <span className="tile-name">{t.label}</span>
              <span className="tile-note">{t.note}</span>
            </button>
          </li>
        ))}
        <li style={{ ["--tilt" as string]: `${TILTS[list.length % TILTS.length]}deg` }}>
          {creating ? (
            <form
              className="profile-tile new-form"
              onSubmit={(e) => {
                e.preventDefault();
                if (valid && ready) onPick(name);
              }}
              onKeyDown={(e) => {
                if (e.key === "Escape") setCreating(false);
              }}
            >
              <label className="field-label" htmlFor="new-profile">
                Your name
              </label>
              <input id="new-profile" ref={input} value={raw} onChange={(e) => setRaw(e.target.value)} maxLength={32} autoComplete="off" />
              <span className="tile-note">{raw && !valid ? "Letters, numbers, - and _ only" : "A full setup runs first, about 40 s"}</span>
              <div className="new-actions">
                <button type="submit" className="btn primary small" disabled={!valid || !ready}>
                  Start
                </button>
                <button type="button" className="btn small" onClick={() => setCreating(false)}>
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <button className="profile-tile add" disabled={!ready} onClick={() => setCreating(true)}>
              <span className="avatar add" aria-hidden="true">
                +
              </span>
              <span className="tile-name">New profile</span>
              <span className="tile-note">for someone new</span>
            </button>
          )}
        </li>
      </ul>
      <p className="picker-foot">{ready ? "Pick a profile to start. You can switch any time in the Anchor." : "Waiting for Helm to start…"}</p>
    </main>
  );
}
