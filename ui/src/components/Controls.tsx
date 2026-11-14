// OWNER: P4
// What the virtual controller is doing: stick, throttle, breath chips, and the three performance tiles.
import { useRef } from "react";
import { clamp01, humanize } from "../format";
import type { HelmState, Mapping } from "../types";

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
    ["Frame rate", state.fps.toFixed(1), "fps"],
    ["Software delay", state.latency_ms.total.toFixed(0), "ms"],
    ["Face tracking", state.latency_ms.vision.toFixed(1), "ms"],
  ];
  return (
    <div className="tiles">
      {tiles.map(([name, value, unit]) => (
        <section key={name} className="card tile">
          <p className="tile-name">{name}</p>
          <p className="tile-value">
            {value} <span>{unit}</span>
          </p>
        </section>
      ))}
    </div>
  );
}
