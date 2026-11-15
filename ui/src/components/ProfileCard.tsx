// OWNER: P4
// The Anchor's Profile page: who is playing which game, switching profile (back to the profile screen), saving,
// measuring breath when a sip-and-puff sensor is attached, Face ID, and deleting the profile.
import { useState } from "react";
import { humanize } from "../format";
import type { HelmState, Send } from "../types";

export const JUDGE = "judge"; // a shared identity from earlier builds (profiles/judge); never saves a calibration
export const DEFAULT_PLAYER = "guest"; // the "Default" profile: shared, a fresh setup for each person
// Profiles that ship in the repo: the engine refuses to delete them (main.BUILT_IN_PROFILES).
export const BUILT_IN = new Set(["guest", "judge", "demo", "demo_webcam"]);

/** A button that asks once more before doing something that cannot be undone. */
export function ConfirmButton(props: { label: string; question: string; confirm: string; disabled?: boolean; onConfirm: () => void }) {
  const { label, question, confirm, disabled, onConfirm } = props;
  const [asking, setAsking] = useState(false);
  if (!asking)
    return (
      <button className="btn danger" disabled={disabled} onClick={() => setAsking(true)}>
        {label}
      </button>
    );
  return (
    <span className="confirm" role="alertdialog" aria-label={question}>
      <span>{question}</span>
      <button
        className="btn danger-solid"
        onClick={() => {
          setAsking(false);
          onConfirm();
        }}
      >
        {confirm}
      </button>
      <button className="btn" onClick={() => setAsking(false)} autoFocus>
        Cancel
      </button>
    </span>
  );
}

export function ProfileCard(props: { state: HelmState; send: Send; onSwitch: () => void; busy: boolean }) {
  const { state, send, onSwitch, busy } = props;
  const { player, game, calibrated } = state.profile;
  const shared = player === JUDGE || player === DEFAULT_PLAYER;
  return (
    <section className="tool">
      <p className="profile-now">
        <mark>{player === DEFAULT_PLAYER ? "Default" : humanize(player)}</mark> is playing <mark>{game}</mark>
      </p>
      <p className="caption" role="status">
        Face identity: {state.identity?.protected ? state.identity.allowed ? "recognized" : "controls locked" : "unprotected"}.
        {" "}{state.identity?.state === "error" ? "Face protection could not start; controls are locked." : state.identity?.reason ?? "No face enrollment: this profile accepts any face."}
        {!shared && <>{" "}A full calibration also learns your face (Face ID) while you turn your head; opening a profile never learns a new face.</>}
      </p>
      <p className="caption">
        {calibrated === "full" ? "Fully calibrated." : calibrated === "quick" ? "Quick setup: resting face only." : "Not calibrated yet."}{" "}
        {shared ? "The default profile never keeps a calibration: each person sets up fresh. Make your own profile to keep it." : "Saving keeps the calibration, mapping and moves on this laptop."}
      </p>
      <div className="line">
        <button className="btn primary" onClick={onSwitch}>
          Switch profile
        </button>
        <button className="btn" onClick={() => send({ cmd: "save_profile" })}>
          Save this profile
        </button>
        {!shared && <button className="btn" disabled={busy} onClick={() => send({ cmd: "reload_identity" })}>Reload face enrollment</button>}
        {!shared && state.identity?.protected && (
          <button className="btn" disabled={busy} onClick={() => send({ cmd: "forget_face" })} title="Anyone can then control this profile; recalibrate to learn your face again">
            Turn off Face ID
          </button>
        )}
        {state.breath_connected && (
          <button className="btn" disabled={busy} onClick={() => send({ cmd: "calibrate", mode: "breath" })} title="Measures how hard you can sip and puff">
            Measure my breath
          </button>
        )}
      </div>
      {!BUILT_IN.has(player) && (
        <div className="line danger-zone">
          <ConfirmButton
            label="Delete profile"
            question={`Delete ${humanize(player)} for good? Its setup, mappings, moves and Face ID go.`}
            confirm="Yes, delete"
            disabled={busy}
            onConfirm={() => send({ cmd: "delete_profile" })}
          />
        </div>
      )}
    </section>
  );
}
