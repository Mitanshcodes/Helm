// OWNER: P4
// The measured numbers shown on the slides. P3 supplies them from eval/analysis.py; until then they stay
// null and the slide says "not measured yet". Never put an estimate here.

export interface Measured {
  helm: number | null;
  baseline: number | null;
  participants: number | null;
}

export const RESULTS: Record<"latency" | "falseTriggers" | "throughput", Measured> = {
  latency: { helm: null, baseline: null, participants: null }, // median motion-to-screen, ms; baseline = real controller
  falseTriggers: { helm: null, baseline: null, participants: null }, // median per minute; baseline = fixed threshold 0.5
  throughput: { helm: null, baseline: null, participants: null }, // bits/s, restricted movement; baseline = fixed gain
};
