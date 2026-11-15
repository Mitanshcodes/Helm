/** Shared palette for profile tiles, face outlines, and controller assignments. */
export const HIDDEN_PROFILES = new Set(["guest", "judge", "demo", "demo_webcam", "tester"]);
const TONES = ["pink", "blue", "yellow", "navy"];
export const personalProfiles = (profiles: Record<string, string[]>) =>
  Object.keys(profiles).filter(p => !HIDDEN_PROFILES.has(p) && !p.startsWith("_")).sort();
export function profileTone(player: string, profiles: Record<string, string[]>) {
  const i = ["guest", ...personalProfiles(profiles)].indexOf(player);
  return TONES[(i >= 0 ? i : [...player].reduce((n, c) => n + c.charCodeAt(0), 0)) % TONES.length];
}
