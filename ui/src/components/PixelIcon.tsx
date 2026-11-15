// OWNER: P4
// Simple ink line drawings for the move cards (a face doing the move, inside a circle), and the ship's wheel.
import type { IconName } from "../moves";

const EYES = (
  <>
    <circle cx="9" cy="10.5" r="1.1" fill="currentColor" stroke="none" />
    <circle cx="15" cy="10.5" r="1.1" fill="currentColor" stroke="none" />
  </>
);

const ART: Record<IconName, JSX.Element> = {
  turn: (
    <>
      {EYES}
      <path d="M9.5 15h5" />
      <path d="M2.5 12h2.5M3.8 10.6 2.5 12l1.3 1.4M21.5 12H19M20.2 10.6l1.3 1.4-1.3 1.4" />
    </>
  ),
  nod: (
    <>
      {EYES}
      <path d="M9.5 15h5M12 2.5v2.5M10.7 3.8 12 2.5l1.3 1.3M12 21.5V19M10.7 20.2l1.3 1.3 1.3-1.3" />
    </>
  ),
  tilt: (
    <>
      {EYES}
      <path d="M9.5 15.5l5-1" />
    </>
  ),
  brow: (
    <>
      <path d="M7 7.2q2-1.6 4 0M13 7.2q2-1.6 4 0" />
      {EYES}
      <path d="M9.5 15.5h5" />
    </>
  ),
  smile: (
    <>
      {EYES}
      <path d="M8 14q4 4 8 0" />
    </>
  ),
  jaw: (
    <>
      {EYES}
      <ellipse cx="12" cy="16" rx="2.3" ry="3" />
    </>
  ),
  eyes: (
    <>
      <path d="M7.5 10.5q1.5 1.4 3 0M13.5 10.5q1.5 1.4 3 0" />
      <path d="M9.5 15.5q2.5 1.2 5 0" />
    </>
  ),
  pucker: (
    <>
      {EYES}
      <path d="M12 13.5q2 1 0 2q2 1 0 2" />
    </>
  ),
  cheek: (
    <>
      {EYES}
      <path d="M10 15.5h4" />
      <path d="M5.5 13.5q-1 2 .5 3.5M18.5 13.5q1 2-.5 3.5" />
    </>
  ),
  nose: (
    <>
      <path d="M7.5 10.5l3-.8M16.5 10.5l-3-.8" />
      <path d="M12 11v3.2l-1.4.8M10 12.6l-1.2-.6M14 12.6l1.2-.6" />
      <path d="M9.5 16.5h5" />
    </>
  ),
  breath: (
    <>
      {EYES}
      <circle cx="12" cy="15.5" r="1.2" />
      <path d="M15 15.5h4M15.5 13.5l2.5-1M15.5 17.5l2.5 1" />
    </>
  ),
  star: <path d="M12 5.5l1.9 4 4.3.5-3.2 2.9.9 4.3L12 15l-3.9 2.2.9-4.3-3.2-2.9 4.3-.5z" />,
  auto: <path d="M8 8l4.5 4L8 16M12.5 8l4.5 4-4.5 4" />,
  dot: <circle cx="12" cy="12" r="2.5" />,
};

export function FaceIcon({ name, size = 44 }: { name: IconName; size?: number }) {
  return (
    <svg className="face-icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="11" />
      {ART[name] ?? ART.dot}
    </svg>
  );
}

/** The ship's wheel: eight spokes with handles around a hub. */
export function HelmWheel({ className, size = 160 }: { className?: string; size?: number }) {
  const spokes = [0, 45, 90, 135, 180, 225, 270, 315];
  return (
    <svg className={className} width={size} height={size} viewBox="-50 -50 100 100" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" aria-hidden="true">
      <circle r="27" />
      <circle r="7" fill="currentColor" />
      {spokes.map((deg) => (
        <g key={deg} transform={`rotate(${deg})`}>
          <path d="M0 -8V-44" />
        </g>
      ))}
    </svg>
  );
}
