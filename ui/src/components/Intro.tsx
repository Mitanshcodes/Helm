// OWNER: P4
// The intro, printed like a riso page: the ship's wheel spins in as two ink layers (pink under blue) that land
// 8px/6px out of line, the wordmark fades up, three check lines tick off, then it clears (about 2.7 s).
// Skip with the button, Enter or Escape. With reduced motion (or Motion: Low) it shows the finished frame for
// half a second. The check lines say what is actually true right now.
import { useEffect, useRef, useState } from "react";

const FADE_AT = 2300;
const END_AT = 2700;
const STILL_MS = 500; // reduced motion: the finished frame, then gone

function still(): boolean {
  return document.documentElement.dataset.motion === "low" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function Wheel({ className }: { className: string }) {
  return (
    <svg className={className} viewBox="0 0 400 400" fill="none" stroke="currentColor" strokeLinecap="round" aria-hidden="true">
      <circle cx="200" cy="200" r="128" strokeWidth="26" />
      <path
        strokeWidth="22"
        d="M200 172V50 M219.8 180.2L306.07 93.93 M228 200H350 M219.8 219.8L306.07 306.07 M200 228V350 M180.2 219.8L93.93 306.07 M172 200H50 M180.2 180.2L93.93 93.93"
      />
      <path
        strokeWidth="40"
        d="M200 44V10 M310.31 89.69L334.35 65.65 M356 200H390 M310.31 310.31L334.35 334.35 M200 356V390 M89.69 310.31L65.65 334.35 M44 200H10 M89.69 89.69L65.65 65.65"
      />
      <circle cx="200" cy="200" r="34" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function Intro({ camera, face, engine, onDone }: { camera: boolean; face: boolean; engine: boolean; onDone: () => void }) {
  const [fading, setFading] = useState(false);
  const finish = useRef(onDone);
  finish.current = onDone;
  const finished = useRef(false);
  const skip = useRef<HTMLButtonElement>(null);
  const [calm] = useState(still);

  const done = useRef(() => {
    if (finished.current) return;
    finished.current = true;
    finish.current();
  });

  useEffect(() => {
    skip.current?.focus();
    const timers = calm
      ? [window.setTimeout(done.current, STILL_MS)]
      : [window.setTimeout(() => setFading(true), FADE_AT), window.setTimeout(done.current, END_AT)];
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" || e.key === "Enter") {
        e.preventDefault();
        done.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      timers.forEach((t) => window.clearTimeout(t));
      window.removeEventListener("keydown", onKey);
    };
  }, [calm]);

  const lines = [camera ? "printing… camera ✓" : "printing… camera… waiting", face ? "face ✓" : "face… looking", engine ? "controller ✓" : "controller… starting"];
  return (
    <div className={`intro${fading ? " fading" : ""}${calm ? " calm" : ""}`} role="status" aria-live="polite" aria-label="Helm is starting">
      <div className="intro-wheels" aria-hidden="true">
        <Wheel className="intro-wheel pink" />
        <Wheel className="intro-wheel blue" />
      </div>
      <p className="intro-word">helm</p>
      <ul className="intro-lines">
        {lines.map((line, i) => (
          <li key={i} style={{ animationDelay: `${1200 + i * 250}ms` }}>
            {line}
          </li>
        ))}
      </ul>
      <button ref={skip} className="intro-skip" onClick={() => done.current()}>
        skip →
      </button>
    </div>
  );
}
