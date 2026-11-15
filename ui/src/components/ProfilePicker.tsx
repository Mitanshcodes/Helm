// OWNER: P4
// "Who's at the helm?": the profile screen after the intro, laid out as a dock. Each profile is a taped-down card
// above a boardwalk, its name tag on the boards, and its pixel ship moored in a slip; picking one casts the ship
// off (the sailing and the zoom into the dashboard are App's Departure layer). Default is the shared profile anyone can use (a fresh setup each time, nothing
// kept); then every profile someone made here; then "New profile". Profiles that ship in the repo for the team
// (demo, demo_webcam, judge, ...) are not shown.
import { useEffect, useRef, useState } from "react";
import { humanize } from "../format";
import type { IconName } from "../moves";
import { DEFAULT_PLAYER } from "./ProfileCard";
import { FaceIcon, HelmWheel } from "./PixelIcon";
import type { FrameMsg, HelmState, Send } from "../types";
import { HIDDEN_PROFILES, profileTone } from "../profiles";
import { MultiplayerPanel } from "./MultiplayerPanel";
import { SeaBackdrop } from "./Fleet";
import { shipSprite, toneColour } from "../shipSprite";

const HIDDEN = HIDDEN_PROFILES;
const ICONS: IconName[] = ["brow", "jaw", "nose", "nod", "star"];
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
    { id: DEFAULT_PLAYER, label: "Default", note: "anyone · fresh setup each time", icon: "smile" },
    ...saved.map((id, i) => ({ id, label: humanize(id), note: "saved on this laptop", icon: ICONS[i % ICONS.length] })),
  ];
}

export interface SailInfo {
  rect: DOMRect; // where the moored ship sits on screen (bow down)
  colour: number; // harbour colour index of this profile's ship
  label: string;
}

const CAST_MS = 450; // ropes off and a wiggle, then the ship sails

function still(): boolean {
  return document.documentElement.dataset.motion === "low" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** A ship moored in its slip, bow pointing down to sea, with two ropes from the pier posts to the stern. */
function Mooring({ colour, empty }: { colour: number; empty?: boolean }) {
  const sprite = empty ? null : shipSprite(colour);
  return (
    <span className="dock-slip" aria-hidden="true">
      <i className="pier left" />
      <i className="pier right" />
      {!empty && (
        <svg className="ropes" viewBox="0 0 220 60" preserveAspectRatio="none">
          <path d="M9 2 Q 50 40 100 46" />
          <path d="M211 2 Q 170 40 120 46" />
        </svg>
      )}
      <span className={empty ? "moored empty" : "moored"}>
        {sprite && (
          <>
            <img src={sprite.body} alt="" draggable={false} />
            <img className="moored-foam a" src={sprite.foamA} alt="" draggable={false} />
            <img className="moored-foam b" src={sprite.foamB} alt="" draggable={false} />
          </>
        )}
      </span>
    </span>
  );
}

export function ProfilePicker(props: { profiles: Record<string, string[]>; ready: boolean; onPick: (player: string, sail?: SailInfo) => void;
  state: HelmState | null; frame: FrameMsg | null; send: Send; departing?: string }) {
  const { profiles, ready, onPick, state, frame, send, departing } = props;
  const multiplayer = state?.multiplayer?.enabled ?? false;
  const [creating, setCreating] = useState(false);
  const [raw, setRaw] = useState("");
  const [casting, setCasting] = useState<string | null>(departing ?? null);
  const first = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const cols = useRef(new Map<string, HTMLElement>());
  const name = raw.trim().toLowerCase().replace(/\s+/g, "_");
  const valid = PROFILE_NAME.test(name) && !HIDDEN.has(name);
  const list = tiles(profiles);

  useEffect(() => {
    if (!departing) first.current?.focus();
  }, [departing]);
  useEffect(() => {
    if (creating) input.current?.focus();
  }, [creating]);

  // Pick: ropes come off and the ship wiggles, then it sails (App's Departure layer takes over). Escape skips the wait.
  const cast = (id: string, label: string, colour: number) => {
    if (casting || !ready) return;
    if (still()) return onPick(id);
    setCasting(id);
    let done = false;
    const go = () => {
      if (done) return;
      done = true;
      window.removeEventListener("keydown", onKey, true);
      const moored = cols.current.get(id)?.querySelector(".moored");
      if (moored) onPick(id, { rect: moored.getBoundingClientRect(), colour, label });
      else onPick(id);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") go();
      e.stopPropagation();
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey, true);
    window.setTimeout(go, CAST_MS);
  };

  const castLabel = casting ? (list.find((t) => t.id === casting)?.label ?? humanize(casting)) : "";
  const newColour = toneColour(profileTone(name || "new", profiles));

  return (
    <main className={`picker${multiplayer ? " is-multiplayer" : ""}${departing ? " departing" : ""}${casting ? " casting" : ""}`} aria-labelledby="picker-title">
      <div className="picker-brand" aria-hidden="true">
        <HelmWheel className="brand-wheel" size={52} />
        <span className="wordmark small">helm</span>
      </div>
      <h1 id="picker-title" className="picker-title">
        who's at the <span className="blue">helm</span>?
      </h1>
      <div className="play-mode-toggle" role="group" aria-label="Play mode">
        <button type="button" className={!multiplayer ? "selected" : ""} aria-pressed={!multiplayer} disabled={!ready || Boolean(casting)}
          onClick={() => send({ cmd: "set_play_mode", mode: "singleplayer" })}>Singleplayer</button>
        <button type="button" className={multiplayer ? "selected" : ""} aria-pressed={multiplayer} disabled={!ready || Boolean(casting)}
          onClick={() => send({ cmd: "set_play_mode", mode: "multiplayer" })}>Multiplayer</button>
      </div>
      <div className="multiplayer-reveal" aria-hidden={!multiplayer}>
        <div>{state && multiplayer && <MultiplayerPanel state={state} frame={frame} profiles={profiles} send={send} ready={ready} />}</div>
      </div>
      {multiplayer && <p className="caption multiplayer-profile-hint">Need to set up or edit a player? Open their profile below.</p>}
      <p className="dock-lede">Pick your ship. It casts off and sails you in.</p>
      <div className="dock">
        <i className="boardwalk" aria-hidden="true" />
        <SeaBackdrop />
        <ul className="dock-cols" role="list">
          {list.map((t, i) => {
            const tone = profileTone(t.id, profiles);
            const colour = toneColour(tone);
            const leaving = casting === t.id;
            return (
              <li
                key={t.id}
                ref={(el) => {
                  if (el) cols.current.set(t.id, el);
                }}
                className={`dock-col${leaving ? " leaving" : ""}${departing === t.id ? " gone" : ""}`}
                style={{ ["--tilt" as string]: `${TILTS[i % TILTS.length]}deg` }}
              >
                <button
                  ref={i === 0 ? first : undefined}
                  className="dock-btn"
                  disabled={!ready || (Boolean(casting) && !leaving)}
                  aria-label={`${t.label}. ${t.note.charAt(0).toUpperCase()}${t.note.slice(1)}. Sail out as ${t.label}.`}
                  onClick={() => cast(t.id, t.label, colour)}
                >
                  <span className="dock-card">
                    <span className={`avatar ${tone}`}>
                      <FaceIcon name={t.icon} size={84} />
                    </span>
                  </span>
                  <span className="dock-tag">{t.label}</span>
                  <Mooring colour={colour} />
                  <span className="dock-note">{t.note}</span>
                </button>
              </li>
            );
          })}
          <li
            ref={(el) => {
              if (el) cols.current.set("__new", el);
            }}
            className={`dock-col new${casting && casting === name ? " leaving" : ""}${departing && departing === name ? " gone" : ""}`}
            style={{ ["--tilt" as string]: `${TILTS[list.length % TILTS.length]}deg` }}
          >
            {creating ? (
              <form
                className="dock-btn as-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!valid || !ready) return;
                  const col = cols.current.get("__new");
                  if (col) cols.current.set(name, col);
                  cast(name, humanize(name), newColour);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setCreating(false);
                }}
              >
                <span className="dock-card new-form">
                  <label className="field-label" htmlFor="new-profile">
                    Your name
                  </label>
                  <input id="new-profile" ref={input} value={raw} onChange={(e) => setRaw(e.target.value)} maxLength={32} autoComplete="off" />
                  <span className="tile-note">
                    {raw && !PROFILE_NAME.test(name) ? "Letters, numbers, - and _ only" : raw && HIDDEN.has(name) ? "That name is taken" : "Setup runs first (about 40 s) and learns your face, then it's kept"}
                  </span>
                  <span className="new-actions">
                    <button type="submit" className="btn primary small" disabled={!valid || !ready || Boolean(casting)}>
                      Start
                    </button>
                    <button type="button" className="btn small" onClick={() => setCreating(false)}>
                      Cancel
                    </button>
                  </span>
                </span>
                <span className="dock-tag">{raw ? humanize(name) : "New profile"}</span>
                {casting && casting === name ? <Mooring colour={newColour} /> : <Mooring colour={0} empty />}
                <span className="dock-note">keeps your setup and moves</span>
              </form>
            ) : (
              <button className="dock-btn" disabled={!ready || Boolean(casting)} onClick={() => setCreating(true)} aria-label="New profile. Keeps your setup and moves.">
                <span className="dock-card">
                  <span className="avatar add" aria-hidden="true">
                    +
                  </span>
                </span>
                <span className="dock-tag">New profile</span>
                <Mooring colour={0} empty />
                <span className="dock-note">keeps your setup and moves</span>
              </button>
            )}
          </li>
        </ul>
      </div>
      <p className="picker-foot">{ready ? "You can switch ships any time from the Anchor." : "Waiting for Helm to start…"}</p>
      <p className="sr-only" aria-live="polite">
        {casting && !departing ? `Casting off as ${castLabel}…` : ""}
      </p>
    </main>
  );
}
