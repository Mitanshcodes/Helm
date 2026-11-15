import { useMemo } from "react";
import { humanize } from "../format";
import { profileTone } from "../profiles";
import type { FrameMsg, HelmState, Send } from "../types";
import { CameraView } from "./CameraView";
import { ControllerView, NEUTRAL_CONTROL } from "./ControllerView";

export function MultiplayerPanel({ state, frame, profiles, send, ready }: {
  state: HelmState; frame: FrameMsg | null; profiles: Record<string, string[]>; send: Send; ready: boolean;
}) {
  const multi = state.multiplayer;
  const tones = useMemo(() => Object.fromEntries(
    [...new Set([...Object.keys(profiles), ...(multi?.visible_profiles ?? [])])].map(p => [p, profileTone(p, profiles)]),
  ), [profiles, multi?.visible_profiles.join("|")]);
  return <section className="multiplayer-stage" aria-label="Multiplayer controllers">
    <div className="multiplayer-camera">
      <CameraView frame={frame} state={state} size="hero" profileTones={tones} />
      {multi?.demo && <p className="caption">Demo faces and simulated controller outputs</p>}
      <p className="caption" role="status">{multi?.error
        ? "Face recognition is unavailable. Check Face ID setup in your profile."
        : multi?.visible_profiles.length
          ? `${multi.visible_profiles.length} ${multi.visible_profiles.length === 1 ? "profile" : "profiles"} recognized`
          : "Look at the camera with an enrolled profile to join."}</p>
      {multi?.output_available === false && <p className="caption">Output preview · virtual gamepads are unavailable on this device.</p>}
    </div>
    <div className="multiplayer-controllers">
      {[0, 1].map(slot => {
        const controller = multi?.controllers[slot];
        const assigned = controller?.player;
        const visible = multi?.visible_profiles ?? [];
        const connected = Boolean(ready && controller?.connected);
        const other = multi?.controllers.filter(c => c.slot !== slot).map(c => c.player) ?? [];
        return <section key={slot} className="multiplayer-controller paper-card" aria-label={`Controller ${slot + 1}`}
          style={{ ["--player-color" as string]: `var(--${assigned ? profileTone(assigned, profiles) : "blue"})` }}>
          <div className="card-head"><h2 className="title">Controller {slot + 1}</h2>
            <span className={`multiplayer-status ${connected ? "connected" : ""}`}>{controller?.loading ? "Loading…" : connected ? "Connected" : assigned ? "Waiting for face" : "Not assigned"}</span>
          </div>
          <label className="multiplayer-assignment">Controlled by
            <select aria-label={`Profile for controller ${slot + 1}`} value={assigned ?? ""} disabled={!ready || controller?.loading}
              onChange={e => send({ cmd: "assign_controller", slot, player: e.target.value || null })}>
              <option value="">Choose a recognized profile</option>
              {assigned && !visible.includes(assigned) && <option value={assigned} disabled>{humanize(assigned)} · away</option>}
              {visible.map(player => <option key={player} value={player} disabled={other.includes(player)}>{humanize(player)}{other.includes(player) ? " · already assigned" : ""}</option>)}
            </select>
          </label>
          <ControllerView control={connected ? controller?.control ?? NEUTRAL_CONTROL : NEUTRAL_CONTROL} mapping={controller?.mapping} />
        </section>;
      })}
    </div>
  </section>;
}
