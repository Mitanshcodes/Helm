// OWNER: P4
// The harbour: twelve pixel sailing ships seen from straight above (one design, twelve colours), crossing behind the camera,
// each with a two-frame pixel splash at the bow and wake at the stern. A random fleet on every page load. Decoration
// only: behind everything, hidden from screen readers, ignores the pointer, gone in high contrast or with
// Ships: off, and anchored (no sailing, one splash frame) when motion is low or reduced.
import { useState } from "react";

// The ship, bow to the right, on a 44 x 21 grid, as horizontal runs [x, y, width, key] (built from the pixel map).
const RUNS: [number, number, number, string][] = [[14, 0, 6, "K"], [13, 1, 1, "K"], [14, 1, 1, "w"], [15, 1, 2, "W"], [17, 1, 3, "1"], [20, 1, 1, "K"], [14, 2, 1, "K"], [15, 2, 1, "w"], [16, 2, 2, "W"], [18, 2, 3, "1"], [21, 2, 1, "K"], [25, 2, 5, "K"], [9, 3, 7, "K"], [16, 3, 1, "w"], [17, 3, 2, "W"], [19, 3, 2, "1"], [21, 3, 4, "K"], [25, 3, 1, "w"], [26, 3, 1, "W"], [27, 3, 3, "1"], [30, 3, 1, "K"], [6, 4, 3, "K"], [9, 4, 7, "3"], [16, 4, 1, "w"], [17, 4, 2, "W"], [19, 4, 3, "1"], [22, 4, 4, "3"], [26, 4, 1, "w"], [27, 4, 1, "W"], [28, 4, 3, "1"], [31, 4, 1, "K"], [5, 5, 1, "K"], [6, 5, 9, "3"], [15, 5, 2, "1"], [17, 5, 1, "w"], [18, 5, 2, "W"], [20, 5, 5, "1"], [25, 5, 1, "3"], [26, 5, 1, "w"], [27, 5, 2, "W"], [29, 5, 2, "1"], [31, 5, 1, "3"], [32, 5, 3, "K"], [5, 6, 1, "K"], [6, 6, 4, "1"], [10, 6, 1, "D"], [11, 6, 1, "d"], [12, 6, 3, "D"], [15, 6, 1, "d"], [16, 6, 1, "D"], [17, 6, 1, "w"], [18, 6, 2, "W"], [20, 6, 2, "1"], [22, 6, 1, "D"], [23, 6, 1, "d"], [24, 6, 2, "D"], [26, 6, 1, "1"], [27, 6, 1, "w"], [28, 6, 1, "W"], [29, 6, 3, "1"], [32, 6, 3, "3"], [35, 6, 2, "K"], [5, 7, 1, "K"], [6, 7, 2, "1"], [8, 7, 3, "D"], [11, 7, 1, "d"], [12, 7, 3, "D"], [15, 7, 1, "d"], [16, 7, 1, "D"], [17, 7, 1, "w"], [18, 7, 2, "W"], [20, 7, 3, "1"], [23, 7, 1, "d"], [24, 7, 3, "D"], [27, 7, 1, "w"], [28, 7, 2, "W"], [30, 7, 3, "1"], [33, 7, 4, "3"], [37, 7, 1, "K"], [5, 8, 1, "K"], [6, 8, 2, "1"], [8, 8, 2, "b"], [10, 8, 1, "D"], [11, 8, 1, "d"], [12, 8, 3, "D"], [15, 8, 1, "d"], [16, 8, 1, "D"], [17, 8, 2, "w"], [19, 8, 2, "W"], [21, 8, 2, "1"], [23, 8, 1, "d"], [24, 8, 3, "D"], [27, 8, 1, "w"], [28, 8, 2, "W"], [30, 8, 2, "1"], [32, 8, 2, "D"], [34, 8, 2, "1"], [36, 8, 2, "3"], [38, 8, 1, "K"], [4, 9, 1, "K"], [5, 9, 3, "1"], [8, 9, 2, "b"], [10, 9, 1, "D"], [11, 9, 1, "d"], [12, 9, 3, "D"], [15, 9, 1, "d"], [16, 9, 1, "D"], [17, 9, 2, "w"], [19, 9, 2, "W"], [21, 9, 2, "1"], [23, 9, 1, "d"], [24, 9, 3, "D"], [27, 9, 2, "w"], [29, 9, 1, "W"], [30, 9, 2, "1"], [32, 9, 3, "D"], [35, 9, 3, "1"], [38, 9, 1, "3"], [39, 9, 4, "K"], [4, 10, 1, "K"], [5, 10, 3, "1"], [8, 10, 2, "b"], [10, 10, 1, "D"], [11, 10, 1, "d"], [12, 10, 3, "D"], [15, 10, 1, "d"], [16, 10, 1, "D"], [17, 10, 2, "b"], [19, 10, 2, "W"], [21, 10, 2, "1"], [23, 10, 1, "d"], [24, 10, 3, "D"], [27, 10, 2, "b"], [29, 10, 1, "W"], [30, 10, 2, "1"], [32, 10, 3, "D"], [35, 10, 2, "1"], [37, 10, 2, "2"], [39, 10, 4, "b"], [43, 10, 1, "K"], [4, 11, 1, "K"], [5, 11, 3, "1"], [8, 11, 2, "b"], [10, 11, 1, "D"], [11, 11, 1, "d"], [12, 11, 3, "D"], [15, 11, 1, "d"], [16, 11, 1, "D"], [17, 11, 2, "w"], [19, 11, 2, "W"], [21, 11, 2, "1"], [23, 11, 1, "d"], [24, 11, 3, "D"], [27, 11, 1, "w"], [28, 11, 2, "W"], [30, 11, 2, "1"], [32, 11, 2, "D"], [34, 11, 1, "1"], [35, 11, 3, "2"], [38, 11, 3, "s"], [41, 11, 2, "K"], [5, 12, 1, "K"], [6, 12, 2, "1"], [8, 12, 2, "b"], [10, 12, 1, "D"], [11, 12, 1, "d"], [12, 12, 3, "D"], [15, 12, 1, "d"], [16, 12, 1, "D"], [17, 12, 1, "w"], [18, 12, 2, "W"], [20, 12, 3, "1"], [23, 12, 1, "d"], [24, 12, 3, "D"], [27, 12, 1, "w"], [28, 12, 2, "W"], [30, 12, 3, "1"], [33, 12, 4, "2"], [37, 12, 4, "s"], [5, 13, 1, "K"], [6, 13, 1, "2"], [7, 13, 3, "1"], [10, 13, 1, "D"], [11, 13, 1, "d"], [12, 13, 3, "D"], [15, 13, 1, "d"], [16, 13, 1, "D"], [17, 13, 1, "w"], [18, 13, 2, "W"], [20, 13, 2, "1"], [22, 13, 1, "D"], [23, 13, 1, "d"], [24, 13, 2, "D"], [26, 13, 1, "1"], [27, 13, 1, "w"], [28, 13, 1, "W"], [29, 13, 3, "1"], [32, 13, 3, "2"], [35, 13, 5, "s"], [5, 14, 1, "K"], [6, 14, 11, "2"], [17, 14, 1, "w"], [18, 14, 2, "W"], [20, 14, 3, "1"], [23, 14, 3, "2"], [26, 14, 1, "w"], [27, 14, 2, "W"], [29, 14, 2, "1"], [31, 14, 1, "2"], [32, 14, 7, "s"], [6, 15, 2, "K"], [8, 15, 1, "s"], [9, 15, 7, "2"], [16, 15, 1, "w"], [17, 15, 2, "W"], [19, 15, 3, "1"], [22, 15, 4, "2"], [26, 15, 1, "w"], [27, 15, 1, "W"], [28, 15, 3, "1"], [31, 15, 6, "s"], [8, 16, 8, "s"], [16, 16, 1, "w"], [17, 16, 2, "W"], [19, 16, 2, "1"], [21, 16, 4, "s"], [25, 16, 1, "w"], [26, 16, 1, "W"], [27, 16, 3, "1"], [30, 16, 4, "s"], [11, 17, 4, "s"], [15, 17, 1, "w"], [16, 17, 2, "W"], [18, 17, 3, "1"], [21, 17, 3, "s"], [24, 17, 1, "w"], [25, 17, 2, "W"], [27, 17, 2, "1"], [29, 17, 1, "s"], [13, 18, 1, "K"], [14, 18, 1, "w"], [15, 18, 2, "W"], [17, 18, 3, "1"], [20, 18, 1, "K"], [24, 18, 5, "K"], [12, 19, 1, "K"], [13, 19, 2, "w"], [15, 19, 2, "W"], [17, 19, 2, "1"], [19, 19, 1, "K"], [13, 20, 6, "K"]];

const FIXED: Record<string, string> = {
  K: "#141414",
  W: "#ffffff",
  w: "#e2dccf",
  D: "#d9a066",
  d: "#b98245",
  b: "#5e3b1a",
  s: "rgba(20,20,20,0.13)",
};

// mid / dark / light, replacing 1 / 2 / 3 in the map
const COLOURS: [string, string, string][] = [
  ["#e8452c", "#a8301c", "#ff8a6e"], // red
  ["#2f80ed", "#1e5bb0", "#7db4ff"], // blue
  ["#f2c230", "#b8891a", "#ffe58a"], // yellow
  ["#3dbb5a", "#25843d", "#8fe39f"], // green
  ["#ff48b0", "#c2257f", "#ff9bd3"], // pink
  ["#f28c28", "#c9661a", "#ffbe7a"], // orange
  ["#19a39a", "#11766f", "#6fd8cf"], // teal
  ["#8e5bd0", "#5d3a94", "#c6a6f2"], // purple
  ["#9bd12e", "#6e9a1c", "#cdeb8c"], // lime
  ["#3a4fc0", "#26338a", "#8f9ef0"], // navy
  ["#a0663a", "#6e4425", "#d6a47a"], // brown
  ["#2cc4e8", "#1a8aa6", "#8ce3f5"], // cyan
];

const FOAM_A: [number, number, string][] = [
  [39, 4, "F"], [42, 6, "F"], [41, 7, "F"], [41, 13, "F"], [42, 14, "F"], [39, 16, "F"],
  [1, 5, "f"], [3, 6, "f"], [2, 10, "f"], [3, 14, "f"], [1, 15, "f"],
];
const FOAM_B: [number, number, string][] = [
  [40, 3, "F"], [43, 5, "F"], [42, 7, "F"], [42, 13, "F"], [43, 15, "F"], [40, 17, "F"],
  [2, 4, "f"], [4, 6, "f"], [0, 11, "f"], [4, 14, "f"], [2, 16, "f"],
];

function Ship({ colour }: { colour: [string, string, string] }) {
  const fill = (key: string) => (key === "1" ? colour[0] : key === "2" ? colour[1] : key === "3" ? colour[2] : FIXED[key]);
  const foam = (dots: [number, number, string][]) =>
    dots.map(([x, y, k]) => <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill={k === "F" ? "#ffffff" : "#bfe3f7"} />);
  return (
    <svg className="ship" viewBox="0 0 44 21" shapeRendering="crispEdges">
      {/* shadow first, so it sits under the hull */}
      {RUNS.filter((r) => r[3] === "s").map(([x, y, w], i) => (
        <rect key={`s${i}`} x={x} y={y} width={w} height="1" fill={FIXED.s} />
      ))}
      {RUNS.filter((r) => r[3] !== "s").map(([x, y, w, k], i) => (
        <rect key={i} x={x} y={y} width={w} height="1" fill={fill(k)} />
      ))}
      <g className="foam foam-a">{foam(FOAM_A)}</g>
      <g className="foam foam-b">{foam(FOAM_B)}</g>
    </svg>
  );
}

interface Lane {
  top: number; // % of the harbour height
  colour: number;
  leftward: boolean;
  seconds: number; // time to cross
  delay: number; // negative: already part way across on load
  scale: number;
}

// Six lanes, two ships per lane. Both ships in a lane sail at the same speed, half a crossing apart, so they stay
// about half a screen apart and can never touch; lanes are far enough apart that hulls never overlap. Each lane
// always has a ship in each half of the screen, lanes alternate direction and their starting points are spread
// evenly, so the harbour stays balanced. Twelve ships, twelve colours: no two alike on screen.
const LANES = 6;
const PER_LANE = 2;

function makeFleet(): Lane[] {
  const colours = [...COLOURS.keys()].sort(() => Math.random() - 0.5);
  const lanes: Lane[] = [];
  for (let lane = 0; lane < LANES; lane++) {
    const seconds = 44 + Math.random() * 16;
    const phase = ((lane * 0.38) % 1) + Math.random() * 0.06; // spread the lanes' starting points evenly
    for (let k = 0; k < PER_LANE; k++) {
      lanes.push({
        top: 3 + (lane / (LANES - 1)) * 80,
        colour: colours[(lane * PER_LANE + k) % colours.length],
        leftward: lane % 2 === 1,
        seconds,
        delay: -((phase + k / PER_LANE) % 1) * seconds,
        scale: 1,
      });
    }
  }
  return lanes;
}

// The wake: two pale lines spreading back from the stern in a V, plus churned water in the middle, fading with
// distance. Same 21-pixel height as the ship so it lines up; drawn bow-right like the ship (mirrored with it). Two
// frames of the dashes alternate, so the water seems to stream past.
const WAKE_W = 56;
function wakeDots(frame: 0 | 1): [number, number, number][] {
  const dots: [number, number, number][] = [];
  for (let d = frame; d < WAKE_W; d += 2) {
    const x = WAKE_W - 1 - d; // d = distance behind the stern
    const fade = 1 - d / WAKE_W;
    const spread = Math.min(8, 1 + d * 0.16);
    dots.push([x, Math.round(10 - spread), fade]);
    dots.push([x, Math.round(10 + spread), fade]);
    if (d < 26 && d % 4 === frame * 2) dots.push([x, 10 + ((d >> 2) % 3) - 1, fade * 0.9]);
  }
  return dots;
}
const WAKE = [wakeDots(0), wakeDots(1)];

function Wake() {
  return (
    <svg className="wake" viewBox={`0 0 ${WAKE_W} 21`} shapeRendering="crispEdges">
      {WAKE.map((dots, f) => (
        <g key={f} className={f === 0 ? "foam foam-a" : "foam foam-b"}>
          {dots.map(([x, y, o], k) => (
            <rect key={k} x={x} y={y} width="2" height="1" fill={k % 3 === 2 ? "#ffffff" : "#9fd3ee"} opacity={o.toFixed(2)} />
          ))}
        </g>
      ))}
    </svg>
  );
}

// Ripples: little pixel wave marks scattered over the harbour on a loose grid (so both sides get some), drifting
// and shimmering slowly. Pale blue on paper: a hint of sea, not a blue background.
const RIPPLE = ["..##.....", ".#..#..#.", "#....##.."];
interface Ripple {
  left: number;
  top: number;
  delay: number;
  seconds: number;
  scale: number;
}

function makeRipples(): Ripple[] {
  const out: Ripple[] = [];
  const cols = 8;
  const rows = 5;
  for (let r = 0; r < rows; r++)
    for (let c = 0; c < cols; c++)
      out.push({
        left: ((c + 0.2 + Math.random() * 0.6) / cols) * 100,
        top: ((r + 0.15 + Math.random() * 0.7) / rows) * 100,
        delay: -Math.random() * 6,
        seconds: 4 + Math.random() * 3,
        scale: 0.8 + Math.random() * 0.5,
      });
  return out;
}

function RippleMark({ r }: { r: Ripple }) {
  return (
    <svg
      className="ripple"
      viewBox="0 0 9 3"
      shapeRendering="crispEdges"
      style={{ left: `${r.left}%`, top: `${r.top}%`, animationDelay: `${r.delay}s`, animationDuration: `${r.seconds}s`, width: `${27 * r.scale}px` }}
    >
      {RIPPLE.flatMap((row, y) => [...row].map((c, x) => (c === "#" ? <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" /> : null)))}
    </svg>
  );
}

// Swells: long, low pixel wave lines that drift slowly across the harbour.
const SWELL = "..###......###......###......###......###....";
const SWELL2 = ".#...#....#...#....#...#....#...#....#...#...";
function makeSwells(): { top: number; left: number; delay: number }[] {
  return Array.from({ length: 7 }, (_, i) => ({
    top: 6 + i * 13 + Math.random() * 5,
    left: (i % 2 === 0 ? 4 : 52) + Math.random() * 30,
    delay: -Math.random() * 20,
  }));
}

function Swell({ top, left, delay }: { top: number; left: number; delay: number }) {
  return (
    <svg className="swell" viewBox={`0 0 ${SWELL.length} 2`} shapeRendering="crispEdges" style={{ top: `${top}%`, left: `${left}%`, animationDelay: `${delay}s` }}>
      {[SWELL, SWELL2].flatMap((row, y) => [...row].map((c, x) => (c === "#" ? <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" /> : null)))}
    </svg>
  );
}

export function Fleet() {
  const [lanes] = useState(makeFleet);
  const [ripples] = useState(makeRipples);
  const [swells] = useState(makeSwells);
  return (
    <div className="fleet" aria-hidden="true">
      <div className="sea" />
      {swells.map((w, i) => (
        <Swell key={`w${i}`} {...w} />
      ))}
      {ripples.map((r, i) => (
        <RippleMark key={`r${i}`} r={r} />
      ))}
      {lanes.map((l, i) => (
        <div
          key={i}
          className={`sail${l.leftward ? " leftward" : ""}`}
          style={{
            top: `${l.top}%`,
            animationDuration: `${l.seconds}s`,
            animationDelay: `${l.delay}s`,
            ["--ship-scale" as string]: String(l.scale),
            ["--anchor-x" as string]: `${4 + ((i * 37) % 86)}%`, // where it rides at anchor when motion is low
          }}
        >
          <div className="hull">
            <Wake />
            <Ship colour={COLOURS[l.colour]} />
          </div>
        </div>
      ))}
    </div>
  );
}
