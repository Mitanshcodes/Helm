// OWNER: P4
// Full-width card shown while calibration or recording is active. It advances by itself: no clicks.
// While teaching a gesture it also says which part of the flow is running, counts takes, and shows the text to
// read aloud. Step lengths come from the server, so the timing can change without touching this file.
import { useMemo } from "react";
import { clamp01, humanize } from "../format";
import { pickText } from "../readingTexts";
import { STEP_READ, isTakeStep, takeNumber, takePhase, type TeachFlow } from "../teach";
import type { Progress } from "../types";

const R = 52;
const C = 2 * Math.PI * R;
// The paragraph moves around while it is read, so the "don't fire" data includes head movement like
// steering. Four places, one per quarter of the step, whatever the step's length.
const SPOTS = ["top-left", "top-right", "bottom-right", "bottom-left"];

function stageLabel(flow: TeachFlow | null, step: string): string | null {
  if (!flow) return null;
  const total = flow.withFace ? 2 : 1;
  if (flow.stage === "face") return `Part 1 of ${total} · Your everyday face`;
  const take = isTakeStep(step) ? ` · Try ${takeNumber(step)}` : "";
  return `Part ${total} of ${total} · ${humanize(flow.name)}${take}`;
}

export function Wizard({ progress, flow }: { progress: Progress; flow: TeachFlow | null }) {
  const step = clamp01(progress.progress);
  const overall = clamp01(progress.overall);
  const label = stageLabel(flow, progress.step);
  const reading = progress.step === STEP_READ;
  const phase = takePhase(progress.step); // "ready" | "go" | "relax" when P3 sends it
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const text = useMemo(() => pickText(Math.floor(Math.random() * 1000)), [reading]); // a new text each reading
  const spot = SPOTS[Math.min(SPOTS.length - 1, Math.floor(step * SPOTS.length))];

  return (
    <section className={`card wizard${reading ? " reading" : ""}${phase ? ` phase-${phase}` : ""}`} aria-live="polite">
      <div className="wizard-head">
        <svg className="ring" viewBox="0 0 120 120" role="img" aria-label={`This step is ${Math.round(step * 100)} percent done`}>
          <circle className="ring-track" cx="60" cy="60" r={R} />
          <circle className="ring-fill" cx="60" cy="60" r={R} strokeDasharray={C} strokeDashoffset={C * (1 - step)} />
        </svg>
        <div className="wizard-text">
          {label && <p className="wizard-stage">{label}</p>}
          <p className="prompt">{progress.prompt}</p>
        </div>
      </div>
      {reading && (
        <div className="read-area">
          <p className={`read-text ${spot}`}>{text}</p>
        </div>
      )}
      <div className="overall" role="img" aria-label={`Setup is ${Math.round(overall * 100)} percent done`}>
        <div style={{ width: `${overall * 100}%` }} />
      </div>
    </section>
  );
}
