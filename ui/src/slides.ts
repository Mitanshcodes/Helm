// OWNER: P4
// Pitch slides: keyboard and click navigation, and the measured numbers filled in from results.ts.
import "@fontsource/atkinson-hyperlegible/400.css";
import "@fontsource/atkinson-hyperlegible/700.css";
import "./tokens.css";
import "./slides.css";
import { RESULTS, type Measured } from "./results";

const slides = [...document.querySelectorAll<HTMLElement>(".slide")];
const count = document.getElementById("count")!;
let index = Math.max(0, Math.min(slides.length - 1, Number(location.hash.slice(1)) - 1 || 0));

function show(next: number) {
  index = Math.max(0, Math.min(slides.length - 1, next));
  slides.forEach((slide, i) => slide.classList.toggle("current", i === index));
  count.textContent = `${index + 1} / ${slides.length}`;
  history.replaceState(null, "", `#${index + 1}`);
}

document.addEventListener("keydown", (e) => {
  if (["ArrowRight", "ArrowDown", "PageDown", " ", "Enter"].includes(e.key)) show(index + 1);
  else if (["ArrowLeft", "ArrowUp", "PageUp", "Backspace"].includes(e.key)) show(index - 1);
  else if (e.key === "Home") show(0);
  else if (e.key === "End") show(slides.length - 1);
});
document.addEventListener("click", (e) => show(index + (e.clientX < window.innerWidth / 3 ? -1 : 1)));

document.getElementById("spokes")!.innerHTML = [0, 45, 90, 135, 180, 225, 270, 315]
  .map((deg) => `<line x1="22" y1="5" x2="22" y2="11" transform="rotate(${deg} 22 22)" />`)
  .join("");

for (const card of document.querySelectorAll<HTMLElement>("[data-result]")) {
  const result: Measured = RESULTS[card.dataset.result as keyof typeof RESULTS];
  const unit = card.dataset.unit ?? "";
  const digits = Number(card.dataset.digits ?? 0);
  const value = card.querySelector(".value")!;
  const versus = card.querySelector<HTMLElement>(".versus")!;
  if (result.helm === null || result.baseline === null) {
    value.textContent = "—";
    versus.textContent = "Not measured yet";
    card.classList.add("pending");
    continue;
  }
  value.innerHTML = `${result.helm.toFixed(digits)} <span>${unit}</span>`;
  card.querySelector(".base")!.textContent = `${result.baseline.toFixed(digits)} ${unit}`;
  if (result.participants !== null) card.querySelector(".how")!.append(` · ${result.participants} participants`);
}

show(index);
