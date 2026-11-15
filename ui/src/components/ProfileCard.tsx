// OWNER: P4
// The Anchor's Profile page: who is playing which game, switching profile (back to the profile screen), saving,
// and measuring breath when a sip-and-puff sensor is attached.
import { humanize } from "../format";
import type { HelmState, Send } from "../types";

export const JUDGE = "judge"; // a shared identity from earlier builds (profiles/judge); never saves a calibration
export const DEFAULT_PLAYER = "guest"; // the "Default" profile: shared, a fresh setup for each person

export function ProfileCard(props: { state: HelmState; send: Send; onSwitch: () => void; busy: boolean }) {
  const { state, send, onSwitch, busy } = props;
  const { player, game, calibrated } = state.profile;
  const shared = player === JUDGE || player === DEFAULT_PLAYER;
  return (
    <section className="tool">
      <p className="profile-now">
        <mark>{player === DEFAULT_PLAYER ? "Default" : humanize(player)}</mark> is playing <mark>{game}</mark>
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
        {state.breath_connected && (
          <button className="btn" disabled={busy} onClick={() => send({ cmd: "calibrate", mode: "breath" })} title="Measures how hard you can sip and puff">
            Measure my breath
          </button>
        )}
      </div>
    </section>
  );
}
