// OWNER: P4
// The Anchor: every setting behind five buttons (Mapping, Captain, Your moves, Profile, Dev). A button opens that
// page over the blurred dashboard; Close, Escape or a click outside puts it away.
import { useEffect, useRef, type ReactNode } from "react";

export type TabId = "mapping" | "captain" | "moves" | "profile" | "dev";

export interface AnchorPage {
  id: TabId;
  label: string;
  blurb: string; // one line on the button
  badge?: string;
  body: ReactNode;
}

export function Anchor({ pages, open }: { pages: AnchorPage[]; open: (id: TabId) => void }) {
  return (
    <section className="anchor" aria-labelledby="anchor-title">
      <h2 id="anchor-title" className="anchor-title">
        the anchor
      </h2>
      <div className="anchor-buttons">
        {pages.map((p, i) => (
          <button key={p.id} className="anchor-btn" style={{ ["--tilt" as string]: `${[-1, 0.8, -0.6, 1, -0.8][i % 5]}deg` }} onClick={() => open(p.id)}>
            <span className="anchor-label">
              {p.label}
              {p.badge && <span className="tab-badge">{p.badge}</span>}
            </span>
            <span className="anchor-blurb">{p.blurb}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

/** One Anchor page in front of the blurred dashboard. */
export function AnchorPanel({ page, close }: { page: AnchorPage; close: () => void }) {
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeButton.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);
  return (
    <div className="layer" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <section className="paper-card anchor-panel" role="dialog" aria-modal="true" aria-labelledby={`panel-${page.id}`}>
        <div className="panel-head">
          <h2 id={`panel-${page.id}`} className="panel-title">
            {page.label}
          </h2>
          <button ref={closeButton} className="btn small" onClick={close}>
            Close ✕
          </button>
        </div>
        <div className="panel-body">{page.body}</div>
      </section>
    </div>
  );
}
