// OWNER: P4
// Casting off, as a camera pan: the chosen ship sails straight down out of its slip, and the view pans down after
// it, the dock scrolling up and away while the dashboard slides into place from below. The ship stays with the dock
// and never appears on the dashboard. The dock (a copy of the profile page) and the dashboard move together as one
// "world" (dock on top, dashboard 100vh below), the dashboard already rendered underneath so nothing loads mid-pan.
// One Web Animations timeline, transform and opacity only. Escape skips to the end; other input is ignored.
import { useLayoutEffect, useRef, type ReactNode, type RefObject } from "react";
import type { SailInfo } from "./ProfilePicker";

// Times are measured from this layer's mount, which is the end of the 450 ms cast-off wiggle on the dock.
const SAIL_MS = 2100;
const SAIL_EASE = "cubic-bezier(.5,0,.75,.35)"; // starts slow, speeds up
const PAN_AT = 900; // 1350 ms after the click
const PAN_MS = 1700;
const PAN_EASE = "cubic-bezier(.65,0,.35,1)";

export function Departure({ mainRef, picker, onDone }: { sail: SailInfo; mainRef: RefObject<HTMLElement>; picker: ReactNode; onDone: () => void }) {
  const layer = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const l = layer.current;
    const main = mainRef.current;
    if (!l) return onDone();
    const scrolled = window.scrollY;
    window.scrollTo(0, 0); // the dashboard is shown from its top; the dock copy keeps the dock's own scroll offset
    const vh = window.innerHeight;
    const ship = l.querySelector<HTMLElement>(".dock-col.gone .moored");

    const anims: Animation[] = [];
    if (ship) {
      ship.style.willChange = "transform";
      anims.push(ship.animate([{ transform: "translateY(0)" }, { transform: `translateY(${0.75 * vh}px)` }], { duration: SAIL_MS, easing: SAIL_EASE, fill: "forwards" }));
    }
    const pan = { duration: PAN_MS, delay: PAN_AT, easing: PAN_EASE, fill: "both" as const };
    l.style.willChange = "transform";
    anims.push(l.animate([{ transform: `translateY(${-scrolled}px)` }, { transform: `translateY(${-scrolled - vh}px)` }], pan));
    if (main) {
      // The dashboard sits one screen below the dock. It has a CSS zoom, so its px are scaled: undo that.
      const zf = main.getBoundingClientRect().width / main.offsetWidth || 1;
      main.style.willChange = "transform";
      anims.push(main.animate([{ transform: `translateY(${vh / zf}px)` }, { transform: "translateY(0)" }], pan));
    }

    let ended = false;
    const cleanUp = () => {
      window.removeEventListener("keydown", onKey, true);
      anims.forEach((a) => a.cancel()); // the end state is the dashboard at rest: no leftover offset
      if (main) main.style.willChange = "";
    };
    const end = () => {
      if (ended) return;
      ended = true;
      cleanUp();
      onDone();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") end();
      e.stopPropagation();
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey, true);
    Promise.all(anims.map((a) => a.finished)).then(end, () => undefined);
    return () => {
      if (!ended) {
        ended = true;
        cleanUp();
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="sail-stage" onPointerDownCapture={(e) => e.preventDefault()} onClickCapture={(e) => e.stopPropagation()}>
      <div className="sail-dock" ref={layer}>
        {picker}
      </div>
    </div>
  );
}
