// OWNER: P4
// The card shown while a move is being recorded (teach flow). It advances by itself: no clicks. It says which
// part is running, counts tries, inverts on "go", and shows the text to read aloud. Step lengths come from the
// server, so the timing can change without touching this file.
import { useMemo } from "react";
import { clamp01, humanize } from "../format";
import { pickText } from "../readingTexts";
import { STEP_READ, isTakeStep, takeNumber, takePhase, type TeachFlow } from "../teach";
import type { Progress } from "../types";

// The paragraph moves around while it is read, so the "don't fire" data includes head movement like
// steering. Four places, one per quarter of the step, whatever the step's length.
const SPOTS = ["top-left", "top-right", "bottom-right", "bottom-left"];

function stageLabel(flow: TeachFlow | null, step: string): string {
  if (!flow) return "RECORDING";
  const total = flow.withFace ? 2 : 1;
  if (flow.stage === "face") return `LEARNING · PART 1 OF ${total} · EVERYDAY FACE`;
  const take = isTakeStep(step) ? ` · TRY ${takeNumber(step)}` : "";
  return `LEARNING · PART ${total} OF ${total} · ${humanize(flow.name).toUpperCase()}${take}`;
}

export function Wizard({ progress, flow }: { progress: Progress; flow: TeachFlow | null }) {
  const step = clamp01(progress.progress);
  const reading = progress.step === STEP_READ;
  const phase = takePhase(progress.step); // "ready" | "go" | "relax"
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const text = useMemo(() => pickText(Math.floor(Math.random() * 1000)), [reading]); // a new text each reading
  const spot = SPOTS[Math.min(SPOTS.length - 1, Math.floor(step * SPOTS.length))];
  const n = Math.round(step * 10);

  return (
    <div className={`setup-card${phase === "go" ? " go" : ""}${reading ? " wide" : ""}`}>
      <h2 className="card-title">{stageLabel(flow, progress.step)}</h2>
      <p className="instruction" role="status" aria-live="polite">
        {progress.prompt}
      </p>
      {reading && (
        <div className="read-area">
          <p className={`read-text ${spot}`}>{text}</p>
        </div>
      )}
      <div className="bar big" role="img" aria-label={`This step is ${Math.round(step * 100)} percent done`}>
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className={i < n ? "seg on" : "seg"} />
        ))}
      </div>
      <p className="detail">Overall {Math.round(clamp01(progress.overall) * 100)}%</p>
    </div>
  );
}
