// OWNER: P4
// Game picker, "Build my mapping", the proposed mapping with the coach's reasons, Accept, session review.
import type { HelmState, Send } from "../types";

export function CoachPanel({ state, send }: { state: HelmState; send: Send }) {
  // TODO(P4): game picker, show the coach_result event (mapping, rationale, changes), Accept sends set_mapping.
  return (
    <section className="panel">
      <h2>Coach</h2>
      <button onClick={() => send({ cmd: "coach_build", game: state.profile.game })}>Build my mapping</button>
      <button onClick={() => send({ cmd: "coach_review" })}>Review my session</button>
    </section>
  );
}
