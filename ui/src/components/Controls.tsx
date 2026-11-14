// OWNER: P4
// What the virtual controller is doing: the pad, steering and throttle bars, breath chips, performance stats.
import { useRef } from "react";
import { clamp01, humanize } from "../format";
import type { HelmState, Mapping } from "../types";
import { ControllerView } from "./ControllerView";

const R = 70;
const BREATH: [string, string][] = [
  ["hard_puff", "Hard puff"],
  ["soft_puff", "Soft puff"],
  ["soft_sip", "Soft sip"],
  ["hard_sip", "Hard sip"],
];
const CHIP_FLASH_MS = 600;

export function StickCard({ state, mapping }: { state: HelmState; mapping: Mapping | null }) {
  const { lx, ly } = state.control;
  const deadzone = mapping?.axes?.find((a) => a.target === "lx")?.deadzone ?? 0.08;
  const x = Math.max(-1, Math.min(1, lx)) * (R - 12);
  const y = -Math.max(-1, Math.min(1, ly)) * (R - 12);
  const side = Math.abs(lx) < 0.01 ? "centered" : `${Math.round(Math.abs(lx) * 100)}% ${lx < 0 ? "left" : "right"}`;
  return (
    <section className="card">
      <h3>Steering · left stick</h3>
      <svg className="stick" viewBox="-80 -80 160 160" role="img" aria-label={`Left stick ${side}`}>
        <circle className="stick-base" r={R} />
        <line className="stick-line" x1={-R} x2={R} />
        <line className="stick-line" y1={-R} y2={R} />
        <circle className="stick-dead" r={Math.max(6, deadzone * R)} />
        <circle className="stick-dot" cx={x} cy={y} r="12" />
      </svg>
      <p className="caption center">{side.charAt(0).toUpperCase() + side.slice(1)}</p>
    </section>
  );
}

function throttleSource(mapping: Mapping | null): { title: string; caption: string } {
  const analog = mapping?.triggers?.find((t) => t.target === "rt");
  if (analog) {
    const jaw = analog.source.startsWith("jaw");
    return { title: `Throttle · ${humanize(analog.source).toLowerCase()}`, caption: jaw ? "Right trigger · half open is half speed" : "Right trigger · stronger is faster" };
  }
  const button = mapping?.buttons?.find((b) => b.target === "rt");
  if (button) {
    return { title: `Throttle · ${humanize(button.gesture).toLowerCase()}`, caption: button.mode === "toggle" ? "Right trigger · once for on, again for off" : "Right trigger" };
  }
  if (mapping?.auto?.rt) return { title: "Throttle · automatic", caption: "Right trigger · always on in this profile" };
  return { title: "Throttle", caption: "Right trigger" };
}

export function ThrottleCard({ state, mapping }: { state: HelmState; mapping: Mapping | null }) {
  const { title, caption } = throttleSource(mapping);
  const rt = clamp01(state.control.rt);
  const lt = clamp01(state.control.lt);
  return (
    <section className="card">
      <h3>{title}</h3>
      <p className="big">{Math.round(rt * 100)}%</p>
      <div className="meter plain" role="img" aria-label={`Throttle ${Math.round(rt * 100)} percent`}>
        <div className="meter-track">
          <div className="meter-fill accent" style={{ width: `${rt * 100}%` }} />
        </div>
      </div>
      <p className="caption">{caption}</p>
      {lt > 0.01 && <p className="caption">Braking {Math.round(lt * 100)}%</p>}
    </section>
  );
}

export function SipPuffCard({ state, mapping }: { state: HelmState; mapping: Mapping | null }) {
  const last = useRef<{ kind: string; t: number } | null>(null);
  const now = performance.now();
  for (const name of state.fired ?? []) if (BREATH.some(([kind]) => kind === name)) last.current = { kind: name, t: now };
  if (!state.breath_connected) return null;
  return (
    <section className="card">
      <div className="card-head">
        <h2>Sip-and-puff</h2>
        <span className="state ok">Connected</span>
      </div>
      <ul className="chips">
        {BREATH.map(([kind, label]) => {
          const target = mapping?.buttons?.find((b) => b.gesture === kind)?.target;
          const isLast = last.current?.kind === kind;
          const flash = isLast && now - last.current!.t < CHIP_FLASH_MS;
          return (
            <li key={kind} className={`chip${isLast ? " last" : ""}${flash ? " flash" : ""}`}>
              <b>{target ? target.toUpperCase() : "–"}</b>
              <span>{label}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function StatTiles({ state }: { state: HelmState }) {
  const tiles: [string, string, string][] = [
    ["Frame rate", state.fps.toFixed(0), "fps"],
    ["Total delay", state.latency_ms.total.toFixed(0), "ms"],
    ["Face tracking", state.latency_ms.vision.toFixed(1), "ms"],
  ];
  return (
    <dl className="stats" aria-label="Performance">
      {tiles.map(([name, value, unit]) => (
        <div key={name}>
          <dt>{name}</dt>
          <dd>
            {value} <span>{unit}</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** Steering as a bar that grows from the center: easier to read across a table than a stick dot. */
function SteerBar({ lx, deadzone }: { lx: number; deadzone: number }) {
  const v = Math.max(-1, Math.min(1, lx));
  const side = Math.abs(v) < 0.01 ? "Centered" : `${Math.round(Math.abs(v) * 100)}% ${v < 0 ? "left" : "right"}`;
  return (
    <div className="out-row">
      <div className="out-label">
        <span>Steering</span>
        <b>{side}</b>
      </div>
      <div className="steer" role="img" aria-label={`Steering ${side}`}>
        <div className="steer-dead" style={{ left: `${50 - deadzone * 50}%`, width: `${deadzone * 100}%` }} />
        <div className="steer-fill" style={v < 0 ? { right: "50%", width: `${-v * 50}%` } : { left: "50%", width: `${v * 50}%` }} />
        <div className="steer-mid" />
      </div>
    </div>
  );
}

function TriggerBar({ label, caption, value }: { label: string; caption: string; value: number }) {
  const pct = Math.round(clamp01(value) * 100);
  return (
    <div className="out-row">
      <div className="out-label">
        <span>
          {label} <small>{caption}</small>
        </span>
        <b>{pct}%</b>
      </div>
      <div className="meter plain" role="img" aria-label={`${label} ${pct} percent`}>
        <div className="meter-track">
          <div className="meter-fill accent" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}

/** What the virtual controller is doing right now: buttons on the pad, then steering, throttle and brake. */
export function OutputCard({ state, mapping }: { state: HelmState; mapping: Mapping | null }) {
  const { control } = state;
  const deadzone = mapping?.axes?.find((a) => a.target === "lx")?.deadzone ?? 0.08;
  const { caption } = throttleSource(mapping);
  const braking = control.lt > 0.01 || (mapping?.triggers ?? []).some((t) => t.target === "lt");
  return (
    <section className="card output">
      <div className="card-head">
        <h2>Controller</h2>
        <span className={control.buttons.length ? "pressed" : "hint"} aria-live="polite">
          {control.buttons.length ? `Pressing ${control.buttons.join(" · ")}` : "No buttons pressed"}
        </span>
      </div>
      <ControllerView control={control} />
      <div className="out-rows">
        <SteerBar lx={control.lx} deadzone={deadzone} />
        <TriggerBar label="Throttle" caption={caption.replace(/^Right trigger( · )?/, "")} value={control.rt} />
        {braking && <TriggerBar label="Brake" caption="" value={control.lt} />}
      </div>
    </section>
  );
}
