// OWNER: P4
// Camera card: the preview with the face mesh drawn over it, and the head-pose readout underneath.
// The server already mirrors the picture and the landmarks (docs/SPEC.md 6.14), so nothing is flipped here.
import { useEffect, useRef } from "react";
import { degrees } from "../format";
import { CLOSED_CONTOURS, OPEN_CONTOURS } from "../mesh";
import type { FrameMsg, HelmState } from "../types";

const W = 640;
const H = 480;

function drawMesh(ctx: CanvasRenderingContext2D, points: [number, number][]) {
  const style = getComputedStyle(document.documentElement);
  const mesh = style.getPropertyValue("--mesh").trim() || "#5eead4";
  const seen = (p?: [number, number]) => p !== undefined && p[0] >= 0 && p[0] <= 1 && p[1] >= 0 && p[1] <= 1;

  ctx.fillStyle = mesh;
  ctx.globalAlpha = 0.35;
  for (const p of points) if (seen(p)) ctx.fillRect(p[0] * W - 1, p[1] * H - 1, 2, 2);
  ctx.globalAlpha = 1;

  ctx.strokeStyle = mesh;
  ctx.lineWidth = 2.5;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  const trace = (ids: number[], close: boolean) => {
    if (!ids.every((id) => seen(points[id]))) return;
    ctx.beginPath();
    ids.forEach((id, k) => (k === 0 ? ctx.moveTo(points[id][0] * W, points[id][1] * H) : ctx.lineTo(points[id][0] * W, points[id][1] * H)));
    if (close) ctx.closePath();
    ctx.stroke();
  };
  CLOSED_CONTOURS.forEach((ids) => trace(ids, true));
  OPEN_CONTOURS.forEach((ids) => trace(ids, false));
}

function PoseReadout({ raw }: { raw: HelmState["raw"] }) {
  const items: [string, number][] = [
    ["Turn (yaw)", raw.yaw],
    ["Tilt (pitch)", raw.pitch],
    ["Roll", raw.roll],
  ];
  return (
    <dl className="readouts">
      {items.map(([name, value]) => (
        <div key={name}>
          <dt>{name}</dt>
          <dd>{degrees(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function CameraView({ frame, state, compact }: { frame: FrameMsg | null; state: HelmState; compact: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const image = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    const ctx = canvas.current?.getContext("2d");
    if (!ctx || !frame) return;
    const paint = (picture: HTMLImageElement | null) => {
      if (picture) ctx.drawImage(picture, 0, 0, W, H);
      else ctx.clearRect(0, 0, W, H);
      if (frame.landmarks) drawMesh(ctx, frame.landmarks);
    };
    if (!frame.jpeg) return paint(null);
    const img = (image.current ??= new Image());
    img.onload = () => paint(img);
    img.src = `data:image/jpeg;base64,${frame.jpeg}`;
  }, [frame]);

  return (
    <section className="card">
      <div className="card-head">
        <h2>Camera</h2>
        <span className={state.face ? "state ok" : "state warn"}>{state.face ? "Face found" : "No face found"}</span>
      </div>
      <div className="camera-panel">
        <canvas ref={canvas} width={W} height={H} role="img" aria-label={state.face ? "Camera preview with your face outlined" : "Camera preview, no face found"} />
        {!frame && <div className="camera-message quiet">No camera picture yet</div>}
        {frame && !state.face && <div className="camera-message">Move into view</div>}
        {!compact && <p className="camera-caption">Preview is mirrored · video never leaves this laptop</p>}
      </div>
      {!compact && state.raw && <PoseReadout raw={state.raw} />}
    </section>
  );
}
