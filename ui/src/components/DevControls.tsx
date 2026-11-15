// OWNER: shared (development dataset capture)
import type { HelmState, Send } from "../types";
import { ConfirmButton } from "./ProfileCard";

export function DevControls({ state, send }: { state: HelmState; send: Send }) {
  const dev = state.dev;
  const manual = dev?.recording && dev.session?.kind === "manual";
  return <section className="dev-controls" aria-label="Development recording">
    <label><input type="checkbox" checked={dev?.enabled ?? false}
      onChange={e => send({ cmd: "set_dev_mode", on: e.target.checked })} /> Dev mode</label>
    {dev?.enabled && <>
      <span>Camera video and model signals are saved locally.</span>
      <button className="btn" disabled={dev.recording && !manual}
        onClick={() => send({ cmd: "set_dev_recording", on: !manual })}>
        {manual ? "Stop recording" : "Record debug dataset"}
      </button>
      <span role="status">{dev.session?.error ? "Dataset incomplete" : dev.recording ? `Recording ${dev.session?.kind} · ${dev.session?.frames ?? 0} frames`
        : dev.session?.saving ? "Saving dataset…" : dev.session ? "Dataset saved" : "Ready"}</span>
      {dev.session && <small>{dev.session.path}</small>}
      {dev.session?.error && <strong role="alert">{dev.session.error}</strong>}
    </>}
    <div className="line danger-zone">
      <ConfirmButton label="Reset state" disabled={state.progress !== null}
        question="Delete every profile made on this laptop, and every Face ID? Built-in profiles stay."
        confirm="Yes, reset" onConfirm={() => send({ cmd: "reset_profiles" })} />
    </div>
  </section>;
}
