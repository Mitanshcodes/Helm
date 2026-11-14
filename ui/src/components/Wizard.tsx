// OWNER: P4
// Full-width card shown while calibration or recording is active. It advances by itself: no clicks.
import { clamp01 } from "../format";
import type { Progress } from "../types";

const R = 52;
const C = 2 * Math.PI * R;

export function Wizard({ progress }: { progress: Progress }) {
  const step = clamp01(progress.progress);
  const overall = clamp01(progress.overall);
  return (
    <section className="card wizard" aria-live="polite">
      <svg className="ring" viewBox="0 0 120 120" role="img" aria-label={`This step is ${Math.round(step * 100)} percent done`}>
        <circle className="ring-track" cx="60" cy="60" r={R} />
        <circle className="ring-fill" cx="60" cy="60" r={R} strokeDasharray={C} strokeDashoffset={C * (1 - step)} />
      </svg>
      <p className="prompt">{progress.prompt}</p>
      <div className="overall" role="img" aria-label={`Setup is ${Math.round(overall * 100)} percent done`}>
        <div style={{ width: `${overall * 100}%` }} />
      </div>
    </section>
  );
}
