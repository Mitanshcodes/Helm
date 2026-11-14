// OWNER: P4
// Canvas with the mirrored preview and the face mesh drawn over it.
import type { FrameMsg } from "../types";

export function CameraView({ frame }: { frame: FrameMsg | null }) {
  // TODO(P4): draw frame.jpeg on a canvas and the landmarks over it. The server already mirrors both.
  return (
    <section className="panel">
      <h2>Camera</h2>
      {frame ? <img src={`data:image/jpeg;base64,${frame.jpeg}`} alt="Camera preview" /> : <p>No preview yet</p>}
    </section>
  );
}
