// OWNER: P4
// CAMERA panel: the preview tinted to the screen's palette with a dashed face mesh over it, the turn / tilt /
// roll boxes, and the stats box. The server already mirrors the picture and the landmarks (docs/SPEC.md 6.14),
// so nothing is flipped here.
import { useEffect, useRef } from "react";
import { degrees, humanize } from "../format";
import { CLOSED_CONTOURS, FACE_OVAL, OPEN_CONTOURS } from "../mesh";
import type { FrameMsg, HelmState } from "../types";

const W = 640;
const H = 480;

// The face mesh as in the first dashboard: faint landmark dots and solid blue contours over the normal picture.
function drawMesh(ctx: CanvasRenderingContext2D, points: [number, number][], color?: string, clear = true) {
  if (clear) ctx.clearRect(0, 0, W, H);
  const mesh = color || getComputedStyle(document.documentElement).getPropertyValue("--mesh").trim() || "#38bdf8";
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

export type CameraSize = "compact" | "hero" | "stage"; // overlay window, dashboard centrepiece, focus view

export function CameraView({ frame, state, compact, size, hint, profileTones }: { frame: FrameMsg | null; state: HelmState; compact?: boolean; size?: CameraSize; hint?: string | null; profileTones?: Record<string, string> }) {
  const variant: CameraSize = size ?? (compact ? "compact" : "hero");
  const video = useRef<HTMLCanvasElement>(null);
  const mesh = useRef<HTMLCanvasElement>(null);
  const image = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    const v = video.current?.getContext("2d");
    const m = mesh.current?.getContext("2d");
    if (!v || !m) return;
    if (!frame) {
      if (image.current) image.current.onload = null;
      v.clearRect(0, 0, W, H);
      m.clearRect(0, 0, W, H);
      return;
    }
    const paint = (picture: HTMLImageElement | null) => {
      if (picture) v.drawImage(picture, 0, 0, W, H);
      else v.clearRect(0, 0, W, H);
      if (state.multiplayer?.enabled) {
        m.clearRect(0, 0, W, H);
        const styles = getComputedStyle(document.documentElement);
        for (const face of frame.faces ?? []) {
          const player = face.player && state.multiplayer.visible_profiles.includes(face.player) ? face.player : null;
          const color = styles.getPropertyValue(`--${player ? profileTones?.[player] ?? "blue" : "ink"}`).trim();
          m.shadowColor = styles.getPropertyValue("--white").trim();
          m.shadowBlur = 3;
          drawMesh(m, face.landmarks, color, false);
          m.shadowBlur = 0;
          const valid = FACE_OVAL.map(i => face.landmarks[i]).filter(p => p && Number.isFinite(p[0]) && Number.isFinite(p[1]));
          if (!valid.length) continue;
          const label = player ? humanize(player) : "Unrecognized";
          m.font = 'bold 18px sans-serif';
          const width = Math.min(W - 8, m.measureText(label).width + 20);
          const x = Math.max(4, Math.min(W - width - 4, Math.min(...valid.map(p => p[0])) * W));
          const y = Math.max(4, Math.min(H - 30, Math.min(...valid.map(p => p[1])) * H - 34));
          m.fillStyle = styles.getPropertyValue("--white").trim();
          m.fillRect(x, y, width, 28);
          m.strokeStyle = color;
          m.lineWidth = 3;
          m.strokeRect(x, y, width, 28);
          m.fillStyle = styles.getPropertyValue("--ink").trim();
          m.fillText(label, x + 10, y + 20, width - 16);
        }
      } else if (frame.landmarks) drawMesh(m, frame.landmarks);
      else m.clearRect(0, 0, W, H);
    };
    if (!frame.jpeg) return paint(null);
    const img = (image.current ??= new Image());
    img.onload = () => paint(img);
    img.src = `data:image/jpeg;base64,${frame.jpeg}`;
    return () => {
      img.onload = null;
    };
  }, [frame, profileTones, state.multiplayer?.enabled, state.multiplayer?.visible_profiles.join("|")]);

  const multiplayer = state.multiplayer?.enabled;
  const found = Boolean(frame) && (multiplayer ? Boolean(frame?.faces?.length) : state.face);
  const identityLocked = !multiplayer && state.identity?.protected && !state.identity.allowed;
  return (
    <figure className={`polaroid ${variant}`}>
      <div className="camera">
        <canvas ref={video} className="camera-video" width={W} height={H} aria-hidden="true" />
        <canvas
          ref={mesh}
          className="camera-mesh"
          width={W}
          height={H}
          role="img"
          aria-label={!frame ? "No camera picture yet" : found ? multiplayer ? "Camera preview with faces outlined and profile labels" : "Camera preview with your face outlined" : "Camera preview, no face found"}
        />
        {!frame && <p className="camera-msg">no camera picture yet</p>}
        {frame && !found && <p className="camera-msg">{identityLocked ? "waiting for the enrolled person" : "move into view"}</p>}
        {!multiplayer && frame && state.face && state.paused && !state.progress && <p className="camera-msg">paused · close your eyes {(state.mapping?.pause?.hold_ms ?? 2000) / 1000} s to resume</p>}
        {hint && <p className="camera-hint">{hint}</p>}
      </div>
      <figcaption>
        <div className="card-head">
          <h2 className="title">the camera</h2>
          <span className="face-flag">{identityLocked ? "🔒 profile locked" : found ? "✓ face found" : frame ? "✗ no face" : "✗ no video"}</span>
        </div>
        {variant !== "compact" && <p className="caption">Video never leaves this laptop.</p>}
        {!multiplayer && <p className="pose">
          {(
            [
              ["Turn", state.raw?.yaw ?? 0],
              ["Tilt", state.raw?.pitch ?? 0],
              ["Roll", state.raw?.roll ?? 0],
            ] as const
          ).map(([name, value]) => (
            <span key={name}>
              {name} <b>{degrees(value)}</b>
            </span>
          ))}
        </p>}
      </figcaption>
    </figure>
  );
}

/** Round rubber stamps: frame rate, face-to-game delay, and how long reading the face takes. */
export function StatStamps({ state }: { state: HelmState }) {
  const stamps: [string, string, string, string][] = [
    ["pink", state.fps.toFixed(0), "fps", "frame rate"],
    ["blue", state.latency_ms.total.toFixed(0), "ms", "face → game"],
    ["ink", state.latency_ms.vision.toFixed(1), "ms", "reading face"],
  ];
  return (
    <section className="stamps" aria-label="Performance">
      <h2 className="title">stamped stats</h2>
      <div className="stamp-row">
        {stamps.map(([tone, value, unit, label], i) => (
          <div key={label} className={`stamp ${tone}`} style={{ ["--tilt" as string]: `${[-6, 5, -3][i]}deg` }}>
            <b>{value}</b>
            <span>{unit}</span>
            <small>{label}</small>
          </div>
        ))}
      </div>
    </section>
  );
}
