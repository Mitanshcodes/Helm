// OWNER: P4
// The instructions while a move is being recorded (teach flow). It advances by itself: no clicks.
// Everyday face: the text to read aloud, moving around the box. Your move: each try is one calm
// "Relax, get ready" step that ends in a 3-2-1 countdown, then a pink GO card while the move is held
// (teach.takeView merges the engine's relax and ready phases so nobody is told to relax twice).
import { useMemo, useRef } from "react";
import { clamp01, humanize } from "../format";
import { pickText } from "../readingTexts";
import { STEP_READ, TAKES, takeView, type TeachFlow } from "../teach";
import type { Progress } from "../types";

// The paragraph moves around while it is read, so the "don't fire" data includes head movement like
// steering. Four places, one per quarter of the step, whatever the step's length.
const SPOTS = ["top-left", "top-right", "bottom-right", "bottom-left"];

function Segments({ value }: { value: number }) {
  const n = Math.round(clamp01(value) * 10);
  return (
    <div className="bar big" role="img" aria-label={`${Math.round(clamp01(value) * 100)} percent`}>
      {Array.from({ length: 10 }, (_, i) => (
        <span key={i} className={i < n ? "seg on" : "seg"} />
      ))}
    </div>
  );
}

export function Wizard({ progress, flow }: { progress: Progress; flow: TeachFlow | null }) {
  const reading = progress.step === STEP_READ;
  const total = useRef(TAKES);
  const tries = /Try \d+ of (\d+)/.exec(progress.prompt);
  if (tries) total.current = Number(tries[1]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const text = useMemo(() => pickText(Math.floor(Math.random() * 1000)), [reading]); // a new text each reading
  const move = flow?.name ?? "";
  const view = takeView(progress, move, total.current);

  if (reading || !view) {
    const step = clamp01(progress.progress);
    const spot = SPOTS[Math.min(SPOTS.length - 1, Math.floor(step * SPOTS.length))];
    return (
      <div className={`setup-card${reading ? " wide" : ""}`}>
        <h2 className="card-title">{flow?.withFace ? "TEACHING · PART 1 OF 2 · YOUR EVERYDAY FACE" : "TEACHING"}</h2>
        <p className="instruction" role="status" aria-live="polite">
          {progress.prompt}
        </p>
        {reading && (
          <div className="read-area">
            <p className={`read-text ${spot}`}>{text}</p>
          </div>
        )}
        <Segments value={step} />
      </div>
    );
  }

  const part = flow?.withFace ? "PART 2 OF 2 · " : "";
  return (
    <div className={`setup-card take ${view.phase}`}>
      <div className="card-top">
        <h2 className="card-title">
          TEACHING · {part}
          {humanize(move).toUpperCase()}
        </h2>
        <ol className="chips" aria-label={`Try ${view.tryNo} of ${view.total}`}>
          {Array.from({ length: view.total }, (_, i) => (
            <li key={i} className={i + 1 < view.tryNo || view.phase === "done" ? "chip done" : i + 1 === view.tryNo ? "chip now" : "chip"}>
              {i + 1 < view.tryNo || view.phase === "done" ? "✓" : `TRY ${i + 1}`}
            </li>
          ))}
        </ol>
      </div>
      <div className="take-row">
        {view.phase === "go" ? (
          <span className="count go" aria-hidden="true">
            GO
          </span>
        ) : view.count !== null ? (
          <span className="count" aria-hidden="true">
            {view.count}
          </span>
        ) : (
          <span className="count calm" aria-hidden="true">
            {view.phase === "done" ? "✓" : "…"}
          </span>
        )}
        <div>
          <p className="instruction" role="status" aria-live="polite">
            {view.headline}
          </p>
          <p className="lead">{view.sub}</p>
        </div>
      </div>
      <Segments value={view.bar} />
    </div>
  );
}
