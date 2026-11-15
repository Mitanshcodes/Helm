// OWNER: P4
// Steering sensitivity, under the controller. Calibration measures how far the player turns; someone who turned
// as far as they could will find steering slow. The slider divides that range (the mapping axis "gain", applied
// by the engine's Normalizer): "quick" reaches full lock with a smaller head turn. It shows the turn in degrees,
// applies after the slider settles, and saves it with a named profile.
import { useEffect, useRef, useState } from "react";
import { setAxisGain } from "../mappingEdit";
import type { HelmState, Mapping, Send } from "../types";

const MIN = 0.5; // mirrors config.STEER_GAIN_MIN / STEER_GAIN_MAX
const MAX = 3;
const SETTLE_MS = 350; // apply once the slider has been still this long
const SAVE_MS = 700; // then save (after the engine has applied it)
const SHARED = new Set(["guest", "judge"]); // never saved: the next person starts from their own setup

const SIDES: Record<string, [string, string]> = { yaw: ["left", "right"], pitch: ["down", "up"], roll: ["left", "right"] };

export function SteeringCard({ state, mapping, apply, send }: { state: HelmState; mapping: Mapping | null; apply: (m: Mapping) => void; send: Send }) {
  const axis = mapping?.axes?.find((a) => a.target === "lx");
  const applied = axis?.gain ?? 1;
  const [gain, setGain] = useState(applied);
  const dragging = useRef(false);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    if (!dragging.current) setGain(applied); // a new mapping or profile arrived
  }, [applied]);
  useEffect(() => () => timers.current.forEach((t) => window.clearTimeout(t)), []);

  if (!axis || !mapping) {
    return (
      <section className="paper-card steer-card" aria-label="Steering sensitivity">
        <h2 className="title">steering sensitivity</h2>
        <p className="caption">Steering isn't on the left stick. Put a head movement there in Mapping.</p>
      </section>
    );
  }

  const [lo, hi] = state.ranges?.[axis.source as "yaw"] ?? [20, 20];
  const scale = applied / gain; // preview while the new value is not applied yet
  const [leftWord, rightWord] = SIDES[axis.source] ?? ["one way", "the other"];
  const shared = SHARED.has(state.profile.player);

  const change = (value: number) => {
    setGain(value);
    dragging.current = true;
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [
      window.setTimeout(() => {
        dragging.current = false;
        apply(setAxisGain(mapping, "lx", value));
      }, SETTLE_MS),
      ...(shared ? [] : [window.setTimeout(() => send({ cmd: "save_profile" }), SETTLE_MS + SAVE_MS)]),
    ];
  };

  return (
    <section className="paper-card steer-card" aria-label="Steering sensitivity">
      <div className="card-head">
        <h2 className="title">steering sensitivity</h2>
        <span className="tag">{gain.toFixed(1)}×</span>
      </div>
      <p className="steer-range">
        Full turn at <b>{Math.round(lo * scale)}°</b> {leftWord} · <b>{Math.round(hi * scale)}°</b> {rightWord}
      </p>
      <label className="steer-slider">
        <span>gentle</span>
        <input
          type="range"
          min={MIN}
          max={MAX}
          step={0.1}
          value={gain}
          onChange={(e) => change(Number(e.target.value))}
          aria-label="Steering sensitivity"
          aria-valuetext={`${gain.toFixed(1)} times: full turn at ${Math.round(lo * scale)} degrees ${leftWord}, ${Math.round(hi * scale)} degrees ${rightWord}`}
        />
        <span>quick</span>
      </label>
      <div className="steer-foot">
        <p className="caption">Turning your head a lot to steer? Slide toward quick.</p>
        <button className="btn small" disabled={gain === 1} onClick={() => change(1)}>
          Reset
        </button>
      </div>
    </section>
  );
}
