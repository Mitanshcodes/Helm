// OWNER: P4
// The Anchor's Profile page: who is playing which game, switching profile (back to the profile screen), saving,
// and measuring breath when a sip-and-puff sensor is attached.
import { humanize } from "../format";
import type { HelmState, Send } from "../types";

export const JUDGE = "judge"; // the shared quick-start identity (profiles/judge)

export function ProfileCard(props: { state: HelmState; send: Send; onSwitch: () => void; busy: boolean }) {
  const { state, send, onSwitch, busy } = props;
  const { player, game, calibrated } = state.profile;
  const shared = player === JUDGE || player === "guest";
  return (
    <section className="tool">
      <p className="profile-now">
        <mark>{humanize(player)}</mark> is playing <mark>{game}</mark>
      </p>
      <p className="caption">
        {calibrated === "full" ? "Fully calibrated." : calibrated === "quick" ? "Quick setup: resting face only." : "Not calibrated yet."}{" "}
        {shared ? "This shared profile never keeps a calibration." : "Saving keeps the calibration, mapping and moves on this laptop."}
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
