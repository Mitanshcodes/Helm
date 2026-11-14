// OWNER: P4
// The setup tools (mapping, coach, learned moves, profile and sound) as one tabbed card, so the live view above
// stays uncluttered. The chosen tab is remembered in this browser.
import { useEffect, useState, type ReactNode } from "react";

export type TabId = "mapping" | "coach" | "moves" | "profile" | "dev";
const KEY = "helm.setupTab";

export function useSetupTab(): [TabId, (t: TabId) => void] {
  const [tab, setTab] = useState<TabId>(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved === "mapping" || saved === "coach" || saved === "moves" || saved === "profile" || saved === "dev") return saved;
    } catch {
      /* storage blocked: default tab */
    }
    return "mapping";
  });
  useEffect(() => {
    try {
      localStorage.setItem(KEY, tab);
    } catch {
      /* not remembered: fine */
    }
  }, [tab]);
  return [tab, setTab];
}

export function SetupTabs(props: { tab: TabId; setTab: (t: TabId) => void; tabs: { id: TabId; label: string; badge?: string; body: ReactNode }[] }) {
  const { tab, setTab, tabs } = props;
  const active = tabs.find((t) => t.id === tab) ?? tabs[0];
  return (
    <section className="paper-card setup" id="setup">
      <div className="setup-head">
        <h2 className="display small">the back pages</h2>
        <div className="tabs" role="tablist" aria-label="Setup">
          {tabs.map((t) => (
            <button
              key={t.id}
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={t.id === active.id}
              aria-controls={`panel-${t.id}`}
              className={t.id === active.id ? "tab active" : "tab"}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {t.badge && <span className="tab-badge">{t.badge}</span>}
            </button>
          ))}
        </div>
      </div>
      <div className="setup-body" role="tabpanel" id={`panel-${active.id}`} aria-labelledby={`tab-${active.id}`}>
        {active.body}
      </div>
    </section>
  );
}
