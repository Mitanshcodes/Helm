// OWNER: P4
// Full-width panel shown while calibration or recording is active. It advances by itself.
import type { Progress } from "../types";

export function Wizard({ progress }: { progress: Progress }) {
  // TODO(P4): very large prompt, a progress ring for the step, a thin bar for overall.
  return (
    <section className="panel wizard">
      <p className="prompt">{progress.prompt}</p>
      <progress value={progress.progress} max={1} />
      <progress value={progress.overall} max={1} />
    </section>
  );
}
