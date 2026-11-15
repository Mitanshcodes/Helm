// OWNER: P4
// The harbour's pixel ship as ready-made images (one body image and two foam frames per colour), painted once on
// a canvas and cached. Moving one image with transform is far cheaper than moving hundreds of SVG rects, which is
// what the dock and the departure animation need to stay smooth.
import { COLOURS, FIXED, FOAM_A, FOAM_B, RUNS } from "./components/Fleet";

export const SHIP_W = 44;
export const SHIP_H = 21;

export interface ShipSprite {
  body: string; // data URL, bow pointing right
  foamA: string;
  foamB: string;
}

const cache = new Map<number, ShipSprite>();

function paint(draw: (ctx: CanvasRenderingContext2D) => void): string {
  const canvas = document.createElement("canvas");
  canvas.width = SHIP_W;
  canvas.height = SHIP_H;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  draw(ctx);
  return canvas.toDataURL("image/png");
}

export function shipSprite(colour: number): ShipSprite {
  const hit = cache.get(colour);
  if (hit) return hit;
  const [mid, dark, light] = COLOURS[colour % COLOURS.length];
  const fill = (k: string) => (k === "1" ? mid : k === "2" ? dark : k === "3" ? light : FIXED[k]);
  const body = paint((ctx) => {
    for (const shadowFirst of [true, false])
      for (const [x, y, w, k] of RUNS)
        if ((k === "s") === shadowFirst) {
          ctx.fillStyle = fill(k);
          ctx.fillRect(x, y, w, 1);
        }
  });
  const foam = (dots: [number, number, string][]) =>
    paint((ctx) => {
      for (const [x, y, k] of dots) {
        ctx.fillStyle = k === "F" ? "#ffffff" : "#bfe3f7";
        ctx.fillRect(x, y, 1, 1);
      }
    });
  const sprite = { body, foamA: foam(FOAM_A), foamB: foam(FOAM_B) };
  cache.set(colour, sprite);
  return sprite;
}

/** Profile card colour -> the harbour colour index used for that profile's ship. */
export function toneColour(tone: string): number {
  return tone === "pink" ? 4 : tone === "blue" ? 1 : tone === "yellow" ? 2 : tone === "navy" ? 9 : 0;
}
