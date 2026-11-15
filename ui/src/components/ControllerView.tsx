// OWNER: P4
// The virtual pad as Helm drives it, drawn as an Xbox controller in the page's flat retro style: white shell with a
// thick ink outline and a light inner edge, dark bumpers, the round guide button, View / Menu / Share, dark sticks
// with rings, a round D-pad, and dark A B X Y caps with coloured letters (the move cards use the same colours). A
// pressed button fills with its colour; inputs the mapping never uses are faint. Shows Helm's final output
// (state.control), never raw face activations or the browser Gamepad API.
import type { HelmState, Mapping } from "../types";

type Control = HelmState["control"];
const axis = (value: number) => (Number.isFinite(value) ? Math.max(-1, Math.min(1, value)) : 0);
const trigger = (value: number) => Math.max(0, axis(value));

export const NEUTRAL_CONTROL: Control = { lx: 0, ly: 0, rx: 0, ry: 0, lt: 0, rt: 0, buttons: [] };

// Breath inputs: the soft/hard events and the live ones (breath_puff, breath_sip: level, hold and analog).
const BREATH = new Set(["hard_puff", "soft_puff", "soft_sip", "hard_sip", "breath_puff", "breath_sip"]);

/** The Xbox face buttons, which have their own colour on the pad and on the move cards. */
export const FACE_COLOURED = new Set(["A", "B", "X", "Y"]);

/** Every pad input the mapping drives: button names, "lt"/"rt", and "LS"/"RS" for stick axes. */
export function usedInputs(mapping: Mapping | null | undefined, breathConnected: boolean): Set<string> {
  const used = new Set<string>();
  for (const b of mapping?.buttons ?? []) if (!BREATH.has(b.gesture) || breathConnected) used.add(b.target);
  for (const t of mapping?.triggers ?? []) if (!BREATH.has(t.source) || breathConnected) used.add(t.target);
  for (const [t, v] of Object.entries(mapping?.auto ?? {})) if (v) used.add(t);
  for (const a of mapping?.axes ?? []) used.add(a.target.startsWith("l") ? "LS" : "RS");
  return used;
}

const SHELL =
  "M170 70 C260 52 500 52 590 70 C680 90 720 150 738 260 C752 360 760 470 752 540 C746 582 690 592 664 556 " +
  "C630 510 590 440 540 412 C520 402 500 400 480 400 L280 400 C260 400 240 402 220 412 C170 440 130 510 96 556 " +
  "C70 592 14 582 8 540 C0 470 8 360 22 260 C40 150 80 90 170 70 Z";

export function ControllerView({ control, mapping, breathConnected = false }: { control: Control; mapping?: Mapping | null; breathConnected?: boolean }) {
  const pressed = new Set(control.buttons);
  const used = mapping ? usedInputs(mapping, breathConnected) : null; // no mapping known: draw everything normally
  const state = (name: string) => `${pressed.has(name) ? " is-pressed" : ""}${used && !used.has(name) ? " unused" : ""}`;

  const face = (name: "A" | "B" | "X" | "Y", x: number, y: number) => (
    <g key={name} className={`pad-button pad-face pad-${name}${state(name)}`} data-button={name}>
      <circle cx={x} cy={y} r="29" />
      <text x={x} y={y + 12}>{name}</text>
    </g>
  );
  const stick = (name: "LS" | "RS", x: number, y: number, dx: number, dy: number) => {
    const tx = x + axis(dx) * 12;
    const ty = y - axis(dy) * 12;
    return (
      <g className={`pad-stick${state(name)}`} data-stick={name}>
        <circle className="pad-well" cx={x} cy={y} r="54" />
        <circle className="pad-thumb" cx={tx} cy={ty} r="40" />
        <circle className="pad-thumb-ring" cx={tx} cy={ty} r="27" />
      </g>
    );
  };
  const dir = (name: string, x: number, y: number, w: number, h: number) => (
    <rect key={name} className={`pad-button pad-dpad${state(name)}`} data-button={name} x={x} y={y} width={w} height={h} rx="5" />
  );
  const anyDpad = ["DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"].some((d) => !used || used.has(d));

  const summary = `Xbox controller. Left stick ${axis(control.lx).toFixed(2)}; LT ${Math.round(trigger(control.lt) * 100)}%, RT ${Math.round(trigger(control.rt) * 100)}%; buttons ${control.buttons.join(", ") || "none"}`;
  return (
    <svg className="controller-view" viewBox="-6 -54 772 652" role="img" aria-label={summary}>
      <title>Controller output</title>

      {/* triggers as meters above the shoulders */}
      {([["lt", 140, "LT"], ["rt", 480, "RT"]] as const).map(([key, x, label]) => (
        <g key={key} className={`pad-trigger${used && !used.has(key) ? " unused" : ""}`} data-trigger={key}>
          <rect className="pad-trigger-track" x={x} y="-48" width="140" height="34" rx="12" />
          <rect className="pad-trigger-fill" x={x} y="-48" width={140 * trigger(control[key])} height="34" rx="12" />
          <text className="pad-trigger-label" x={x + 70} y="-24">
            {label} {Math.round(trigger(control[key]) * 100)}%
          </text>
        </g>
      ))}

      {/* bumpers peek out behind the top of the shell */}
      <path className={`pad-button pad-bumper${state("LB")}`} data-button="LB" d="M120 96 C132 52 200 30 288 36 C302 37 310 48 306 62 L300 74 L134 104 Z" />
      <path className={`pad-button pad-bumper${state("RB")}`} data-button="RB" d="M640 96 C628 52 560 30 472 36 C458 37 450 48 454 62 L460 74 L626 104 Z" />

      <path className="pad-shell" d={SHELL} />
      <path className="pad-sheen" d="M40 420 C34 480 40 530 62 556 M698 556 C720 530 726 480 720 420 M240 426 C300 418 460 418 520 426" />

      {/* guide, view, menu, share */}
      <g className="pad-guide">
        <circle cx="380" cy="112" r="31" />
        <path d="M366 96 Q380 112 394 128 M394 96 Q380 112 366 128" />
      </g>
      <g className={`pad-button pad-round${state("BACK")}`} data-button="BACK">
        <circle cx="318" cy="190" r="22" />
        <path className="pad-glyph" d="M306 181h14v11h-14z M313 188h12v10h-12" />
      </g>
      <g className={`pad-button pad-round${state("START")}`} data-button="START">
        <circle cx="442" cy="190" r="22" />
        <path className="pad-glyph" d="M432 183h20 M432 190h20 M432 197h20" />
      </g>
      <g className="pad-share">
        <rect x="352" y="228" width="56" height="26" rx="13" />
        <path className="pad-glyph" d="M370 240v6h20v-6 M380 244v-10 M375 239l5-5 5 5" />
      </g>

      {/* left stick high, D-pad low; face buttons high, right stick low */}
      {stick("LS", 196, 186, control.lx, control.ly)}
      <g className={`pad-dpad-base${anyDpad ? "" : " unused"}`}>
        <circle cx="270" cy="330" r="70" />
        <rect className="pad-dpad-arm" x="252" y="276" width="36" height="108" rx="6" />
        <rect className="pad-dpad-arm" x="216" y="312" width="108" height="36" rx="6" />
      </g>
      {dir("DPAD_UP", 252, 276, 36, 38)}
      {dir("DPAD_DOWN", 252, 346, 36, 38)}
      {dir("DPAD_LEFT", 216, 312, 38, 36)}
      {dir("DPAD_RIGHT", 286, 312, 38, 36)}
      {stick("RS", 488, 318, control.rx, control.ry)}
      {face("Y", 590, 136)}
      {face("X", 538, 188)}
      {face("B", 642, 188)}
      {face("A", 590, 240)}
    </svg>
  );
}
