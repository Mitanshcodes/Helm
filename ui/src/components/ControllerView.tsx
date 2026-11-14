// OWNER: P4
// The virtual pad as Helm drives it (the original drawing): a pressed button fills with its colour, the sticks
// move, the triggers fill. Inputs the mapping never uses are drawn faint. Shows Helm's final output
// (state.control), never raw face activations or the browser Gamepad API.
import type { HelmState, Mapping } from "../types";

type Control = HelmState["control"];
const axis = (value: number) => (Number.isFinite(value) ? Math.max(-1, Math.min(1, value)) : 0);
const trigger = (value: number) => Math.max(0, axis(value));

export const NEUTRAL_CONTROL: Control = { lx: 0, ly: 0, rx: 0, ry: 0, lt: 0, rt: 0, buttons: [] };

const BREATH = new Set(["hard_puff", "soft_puff", "soft_sip", "hard_sip"]);

/** Every pad input the mapping drives: button names, "lt"/"rt", and "LS"/"RS" for stick axes. */
export function usedInputs(mapping: Mapping | null | undefined, breathConnected: boolean): Set<string> {
  const used = new Set<string>();
  for (const b of mapping?.buttons ?? []) if (!BREATH.has(b.gesture) || breathConnected) used.add(b.target);
  for (const t of mapping?.triggers ?? []) used.add(t.target);
  for (const [t, v] of Object.entries(mapping?.auto ?? {})) if (v) used.add(t);
  for (const a of mapping?.axes ?? []) used.add(a.target.startsWith("l") ? "LS" : "RS");
  return used;
}

export function ControllerView({ control, mapping, breathConnected = false }: { control: Control; mapping?: Mapping | null; breathConnected?: boolean }) {
  const pressed = new Set(control.buttons);
  const used = mapping ? usedInputs(mapping, breathConnected) : null; // no mapping known: draw everything normally
  const state = (name: string) => `${pressed.has(name) ? " is-pressed" : ""}${used && !used.has(name) ? " unused" : ""}`;
  const button = (name: string, label: string, x: number, y: number, r = 13) => (
    <g key={name} className={`pad-button pad-${name}${state(name)}`} data-button={name}>
      <circle cx={x} cy={y} r={r} />
      <text x={x} y={y + 4}>{label}</text>
    </g>
  );
  const stick = (name: "LS" | "RS", x: number, y: number, dx: number, dy: number) => (
    <g className={`pad-stick${state(name)}`} data-stick={name}>
      <circle className="pad-well" cx={x} cy={y} r={26} />
      <path className="pad-crosshair" d={`M${x - 20} ${y}h40 M${x} ${y - 20}v40`} />
      <circle className="pad-thumb" cx={x + axis(dx) * 15} cy={y - axis(dy) * 15} r={14} />
      <text x={x} y={y + 42}>{name}</text>
    </g>
  );
  const summary = `Left stick ${axis(control.lx).toFixed(2)}; LT ${Math.round(trigger(control.lt) * 100)}%, RT ${Math.round(trigger(control.rt) * 100)}%; buttons ${control.buttons.join(", ") || "none"}`;
  return (
    <svg className="controller-view" viewBox="0 0 360 246" role="img" aria-label={summary}>
      <title>Controller output</title>
      <path className="pad-shell" d="M84 58 Q54 56 39 91 L15 191 Q8 225 33 230 Q50 233 66 213 L103 176 H257 L294 213 Q310 233 327 230 Q352 225 345 191 L321 91 Q306 56 276 58 Z" />
      {([["lt", 53, "LT"], ["rt", 249, "RT"]] as const).map(([key, x, label]) => (
        <g key={key} className={`pad-trigger${used && !used.has(key) ? " unused" : ""}`} data-trigger={key}>
          <rect className="pad-trigger-track" x={x} y="5" width="58" height="14" rx="5" />
          <rect className="pad-trigger-fill" x={x} y="5" width={58 * trigger(control[key])} height="14" rx="5" />
          <text className="pad-trigger-label" x={x + 29} y="35">
            {label} {Math.round(trigger(control[key]) * 100)}%
          </text>
        </g>
      ))}
      {([["LB", 49], ["RB", 247]] as const).map(([name, x]) => (
        <g key={name} className={`pad-button${state(name)}`} data-button={name}>
          <rect x={x} y="44" width="64" height="19" rx="7" />
          <text x={x + 32} y="58">{name}</text>
        </g>
      ))}
      {stick("LS", 85, 105, control.lx, control.ly)}
      {stick("RS", 232, 164, control.rx, control.ry)}
      {button("Y", "Y", 281, 82)}
      {button("X", "X", 254, 109)}
      {button("B", "B", 308, 109)}
      {button("A", "A", 281, 136)}
      {button("BACK", "‹", 152, 103, 11)}
      {button("START", "≡", 197, 103, 11)}
      {(
        [
          ["DPAD_UP", "↑", 133, 143],
          ["DPAD_LEFT", "←", 113, 163],
          ["DPAD_RIGHT", "→", 153, 163],
          ["DPAD_DOWN", "↓", 133, 183],
        ] as const
      ).map(([name, label, x, y]) => button(name, label, x, y, 10))}
    </svg>
  );
}
