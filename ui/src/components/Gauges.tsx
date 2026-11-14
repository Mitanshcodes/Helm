// OWNER: P4
// Steering bar, trigger bars, one bar per gesture with on/off ticks, controller buttons, fired flashes.
import type { HelmState } from "../types";

export function Gauges({ state }: { state: HelmState }) {
  // TODO(P4): real bars. The stub prints the numbers so the data path is visible.
  return (
    <section className="panel">
      <h2>Gauges</h2>
      <p>
        Stick {state.control.lx.toFixed(2)} · LT {state.control.lt.toFixed(2)} · RT {state.control.rt.toFixed(2)} · Yaw{" "}
        {state.axes.yaw.toFixed(2)}
      </p>
      <ul>
        {Object.entries(state.activations).map(([name, level]) => (
          <li key={name} className={state.fired.includes(name) ? "accent" : ""}>
            {name}: {level.toFixed(2)}
          </li>
        ))}
      </ul>
    </section>
  );
}
