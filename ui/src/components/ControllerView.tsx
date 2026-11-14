// OWNER: P4
// Displays Helm's final mapped output, never the browser Gamepad API or raw face activations.
import type { HelmState } from "../types";

type Control = HelmState["control"];
const axis = (value: number) => Number.isFinite(value) ? Math.max(-1, Math.min(1, value)) : 0;
const trigger = (value: number) => Math.max(0, axis(value));

export const NEUTRAL_CONTROL: Control = { lx: 0, ly: 0, rx: 0, ry: 0, lt: 0, rt: 0, buttons: [] };

export function ControllerView({ control }: { control: Control }) {
  const pressed = new Set(control.buttons);
  const button = (name: string, label: string, x: number, y: number, r = 13) => (
    <g key={name} className={`pad-button${pressed.has(name) ? " is-pressed" : ""}`} data-button={name}>
      <circle cx={x} cy={y} r={r} />
      <text x={x} y={y + 4}>{label}</text>
    </g>
  );
  const stick = (name: "LS" | "RS", x: number, y: number, dx: number, dy: number) => (
    <g className={`pad-stick${pressed.has(name) ? " is-pressed" : ""}`} data-stick={name}>
      <circle className="pad-well" cx={x} cy={y} r={26} />
      <path className="pad-crosshair" d={`M${x - 20} ${y}h40 M${x} ${y - 20}v40`} />
      <circle className="pad-thumb" cx={x + axis(dx) * 15} cy={y - axis(dy) * 15} r={14} />
      <text x={x} y={y + 42}>{name}</text>
    </g>
  );
  const summary = `Left stick ${axis(control.lx).toFixed(2)}, ${axis(control.ly).toFixed(2)}; right stick ${axis(control.rx).toFixed(2)}, ${axis(control.ry).toFixed(2)}; LT ${Math.round(trigger(control.lt) * 100)}%, RT ${Math.round(trigger(control.rt) * 100)}%; buttons ${control.buttons.join(", ") || "none"}`;
  return (
    <svg className="controller-view" viewBox="0 0 360 246" role="img" aria-label={summary}>
      <title>Controller output</title>
      <path className="pad-shell" d="M84 58 Q54 56 39 91 L15 191 Q8 225 33 230 Q50 233 66 213 L103 176 H257 L294 213 Q310 233 327 230 Q352 225 345 191 L321 91 Q306 56 276 58 Z" />
      {([['lt', 53, 'LT'], ['rt', 249, 'RT']] as const).map(([key, x, label]) => (
        <g key={key} data-trigger={key}>
          <rect className="pad-trigger-track" x={x} y="5" width="58" height="14" rx="5" />
          <rect className="pad-trigger-fill" x={x} y="5" width={58 * trigger(control[key])} height="14" rx="5" />
          <text className="pad-trigger-label" x={x + 29} y="35">{label} {Math.round(trigger(control[key]) * 100)}%</text>
        </g>
      ))}
      {([['LB', 49], ['RB', 247]] as const).map(([name, x]) => (
        <g key={name} className={`pad-button${pressed.has(name) ? " is-pressed" : ""}`} data-button={name}>
          <rect x={x} y="44" width="64" height="19" rx="7" /><text x={x + 32} y="58">{name}</text>
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
      {([
        ["DPAD_UP", "↑", 133, 143], ["DPAD_LEFT", "←", 113, 163],
        ["DPAD_RIGHT", "→", 153, 163], ["DPAD_DOWN", "↓", 133, 183],
      ] as const).map(([name, label, x, y]) => button(name, label, x, y, 10))}
    </svg>
  );
}
