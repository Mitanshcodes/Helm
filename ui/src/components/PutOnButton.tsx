// OWNER: P4
// One tap to put a learned move on a controller input (teach result and "Your moves"). Applies at once.
import { QUICK_TARGETS, setBinding, targetLabel, targetsOf } from "../mappingEdit";
import type { Catalog, Mapping } from "../types";

export function PutOnButton(props: { gesture: string; mapping: Mapping | null; catalog?: Catalog; apply: (m: Mapping) => void }) {
  const { gesture, mapping, catalog, apply } = props;
  if (!mapping) return null;
  const current = targetsOf(mapping, gesture);
  return (
    <div className="put-on" role="group" aria-label={`Put ${gesture.replace(/_/g, " ")} on a button`}>
      {QUICK_TARGETS.map((t) => {
        const on = current.includes(t);
        const action = catalog?.controls?.[t];
        return (
          <button
            key={t}
            className={on ? "put-target on" : "put-target"}
            aria-pressed={on}
            title={action ? `${targetLabel(t)}: ${action}` : targetLabel(t)}
            onClick={() => apply(setBinding(mapping, t, on ? "" : gesture, t === "lt" || t === "rt" ? "hold" : "tap", catalog))}
          >
            {targetLabel(t)}
          </button>
        );
      })}
    </div>
  );
}
