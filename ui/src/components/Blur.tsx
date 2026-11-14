// OWNER: P4
// A part of the page that blurs and becomes unreachable (inert, hidden from screen readers) while calibration or
// teaching is on screen, so the player only has the card to look at.
import { useEffect, useRef, type ReactNode } from "react";

export function Blur({ on, className = "", children, as: Tag = "div", id }: { on: boolean; className?: string; children: ReactNode; as?: "div" | "section"; id?: string }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    ref.current?.toggleAttribute("inert", on); // React 18 has no inert prop
  }, [on]);
  return (
    <Tag ref={ref as never} id={id} className={`blurrable${on ? " blurred" : ""} ${className}`.trim()} aria-hidden={on || undefined}>
      {children}
    </Tag>
  );
}
