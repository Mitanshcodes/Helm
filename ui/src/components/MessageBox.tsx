// OWNER: P4
// The one line under the move cards. It follows the state: paused, just calibrated, a move just fired (and which
// button it pressed), a fatigue note, or a plain hint, with its key words highlighted.
import { useRef } from "react";
import { humanize } from "../format";
import { keyText, moveName } from "../moves";
import type { HelmState, Mapping } from "../types";

const FIRE_MS = 2000;
const DONE_MS = 6000;


type Line = { lead: string; mark: string; rest: string };

// P3's notices: "jaw_open is weakening; threshold lowered to 85%".
function warm(notice: string): Line {
  const match = /^(\w+) is weakening/.exec(notice);
  if (!match) return { lead: "Heads up:", mark: "", rest: notice };
  return {
    lead: "Heads up:",
    mark: `${humanize(match[1]).toLowerCase()} is getting weaker`,
    rest: ", so Helm lowered its threshold. Take a break whenever you like.",
  };
}

export function MessageBox({ state, mapping, doneAt, hold }: { state: HelmState; mapping: Mapping | null; doneAt: number; hold: number }) {
  const last = useRef<{ line: Line; at: number } | null>(null);
  const previous = useRef<Set<string>>(new Set());
  const now = performance.now();

  // Rising edges of the engine's fired list.
  const fired = new Set(state.fired ?? []);
  for (const name of fired) {
    if (previous.current.has(name)) continue;
    const b = mapping?.buttons?.find((x) => x.gesture === name);
    if (b && !state.paused && !state.progress) {
      last.current = {
        line: {
          lead: "Nice:",
          mark: `${humanize(state.profile.player)} used ${moveName(name, state.catalog).toLowerCase()}`,
          rest: ` and the ${keyText(b.target)} button was pressed.`,
        },
        at: now,
      };
    }
  }
  previous.current = fired;

  let main: Line;
  if (state.paused) main = { lead: "Paused.", mark: `Close your eyes for ${hold} seconds`, rest: " to keep playing." };
  else if (state.progress) main = { lead: "Setting up:", mark: "", rest: state.progress.prompt };
  else if (now - doneAt < DONE_MS) main = { lead: "Calibration done!", mark: "Your moves are unlocked", rest: ". Go play!" };
  else if (last.current && now - last.current.at < FIRE_MS) main = last.current.line;
  else if (!state.face) main = { lead: "Hello?", mark: "I can't see your face", rest: ". Look at the camera." };
  else if (state.notices?.length) main = warm(state.notices[0]);
  else main = { lead: "Ready.", mark: "", rest: "Turn your head to steer. Make a move to press its button." };

  return (
    <div className="message">
      <p className="message-main" aria-live="polite">
        <b>{main.lead}</b> {main.mark && <mark>{main.mark}</mark>}
        {main.rest}
      </p>
    </div>
  );
}
