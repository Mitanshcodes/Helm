// OWNER: P4
// "your moves -> the buttons": one taped-down card per move with its face icon, mode, the button it presses in
// big letters, a bar with a solid notch (fires) and a hollow notch (lets go), and the live value. A firing card
// fills pink and says FIRING!. The last card is the "teach a new move" coupon. ControllerCard is the pad.
import { forwardRef } from "react";
import { TAKES_LABEL } from "../teach";
import type { MoveRow } from "../moves";
import { keyText, moveName } from "../moves";
import type { HelmState, Mapping } from "../types";
import { ControllerView, usedInputs } from "./ControllerView";
import { FaceIcon } from "./PixelIcon";

const TILTS = [-1.2, 0.9, -0.5, 1.3, -0.9, 0.6, -1.4, 1.0]; // pasted up by hand, the same way every time

function Bar({ row }: { row: MoveRow }) {
  if (row.kind === "steer") {
    const x = 50 + row.level * 50;
    return (
      <div className="bar steer" aria-hidden="true">
        <i className="notch solid" style={{ left: "50%" }} />
        <b className="dot" style={{ left: `${x}%` }} />
      </div>
    );
  }
  const pct = Math.max(0, Math.min(1, row.level)) * 100;
  return (
    <div className="bar" aria-hidden="true">
      <span className="fill" style={{ width: `${pct}%` }} />
      {row.off !== undefined && <i className="notch hollow" style={{ left: `${Math.min(100, row.off * 100)}%` }} />}
      {row.on !== undefined && <i className="notch solid" style={{ left: `${Math.min(100, row.on * 100)}%` }} />}
    </div>
  );
}

function Card({ row, index }: { row: MoveRow; index: number }) {
  const what = row.kind === "unmapped" ? `${row.name} is not on a button yet` : `${row.name} presses ${row.keyLabel}`;
  const label = `${what}.${row.firing ? " Firing now." : ""} ${row.measure} ${row.value}.`;
  return (
    <li
      className={`move${row.firing ? " firing" : ""}${row.kind === "unmapped" ? " unmapped" : ""}`}
      style={{ ["--tilt" as string]: `${TILTS[index % TILTS.length]}deg` }}
      role="listitem"
      aria-label={label}
    >
      <div className="move-top" aria-hidden="true">
        <FaceIcon name={row.icon} />
        <span className="move-mode">{row.firing ? "FIRING!" : row.mode}</span>
      </div>
      <h3 className="move-name" aria-hidden="true">
        {row.name.toLowerCase()}
      </h3>
      <div className="move-key" aria-hidden="true">
        <span className="presses">presses</span>
        {row.kind === "pause" ? <span className="sticker">pause</span> : <span className={row.kind === "unmapped" ? "letter none" : "letter"}>{row.key}</span>}
      </div>
      <Bar row={row} />
      <div className="move-value" aria-hidden="true">
        <span>{row.measure}</span>
        <b>{row.value}</b>
      </div>
    </li>
  );
}

export const MovesPanel = forwardRef<HTMLHeadingElement, {
  state: HelmState;
  rows: MoveRow[];
  onTeach: () => void;
  teachBusy: boolean;
  onMeasureBreath: () => void;
}>(function MovesPanel({ state, rows, onTeach, teachBusy, onMeasureBreath }, heading) {
  return (
    <>
      <div className="section-head">
        <h2 className="display" ref={heading} tabIndex={-1}>
          your moves <span className="arrow">→</span> <span className="blue">the buttons</span>
        </h2>
        <p className="note">
          Solid notch fires · hollow notch lets go
          {state.breath_connected && (
            <button className="btn small" disabled={teachBusy} onClick={onMeasureBreath} title="Measures how hard you can sip and puff">
              Measure my breath
            </button>
          )}
        </p>
      </div>
      <ul className="moves" role="list" aria-label="Your moves and the buttons they press">
        {rows.map((r, i) => (
          <Card key={r.id} row={r} index={i} />
        ))}
        <li className="coupon-wrap" style={{ ["--tilt" as string]: `${TILTS[rows.length % TILTS.length]}deg` }}>
          <button className="coupon" onClick={onTeach} disabled={teachBusy}>
            <span className="coupon-top">
              CUT OUT &amp; KEEP
              <svg className="scissors" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
                <circle cx="6" cy="6" r="3" />
                <circle cx="6" cy="18" r="3" />
                <path d="M8.1 8.1 20 20M8.1 15.9 20 4" />
              </svg>
            </span>
            <span className="coupon-title">teach a new move</span>
            <span className="coupon-plus" aria-hidden="true">+</span>
            <span className="coupon-foot">{TAKES_LABEL}</span>
          </button>
        </li>
      </ul>
      {rows.length === 0 && <p className="empty-note">No moves are mapped yet. Open the setup pages below and build a mapping with the coach.</p>}
    </>
  );
});

/** The pad as Helm drives it, with a "pressing" sticker and a one-line summary. */
export function ControllerCard({ state, mapping }: { state: HelmState; mapping: Mapping | null }) {
  const used = usedInputs(mapping, state.breath_connected);
  const pressed = state.control.buttons.filter((b) => used.has(b));
  const lx = state.control.lx;
  const steer = Math.abs(lx) < 0.05 ? "centre" : `${lx < 0 ? "left" : "right"} ${Math.round(Math.abs(lx) * 100)}%`;
  const legend = (mapping?.buttons ?? [])
    .filter((b) => used.has(b.target) && !/_(puff|sip)$/.test(b.gesture))
    .map((b) => `${keyText(b.target)} ${moveName(b.gesture, state.catalog).toLowerCase()}`);
  return (
    <>
      <div className="card-head">
        <h2 className="title">the controller</h2>
        <span className="tag" aria-live="polite">
          {state.paused ? "paused" : pressed.length ? `pressing ${pressed.join(" + ")}` : "nothing pressed"}
        </span>
      </div>
      <ControllerView control={state.control} mapping={mapping} breathConnected={state.breath_connected} />
      <p className="pad-line">
        <b>Steering:</b> {steer} · <b>Throttle:</b> {Math.round(state.control.rt * 100)}%
      </p>
      {legend.length > 0 && <p className="pad-legend">{legend.join(" · ")}</p>}
    </>
  );
}
