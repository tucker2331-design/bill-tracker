// Qualitative bands shared by the Health gauges (BulletGraph) and the at-a-glance rollup (HealthVitals).
// Kept in its own module (no component export) so importing the pure `bandTone` helper from a view never
// breaks the BulletGraph component's React Fast Refresh boundary (react-refresh/only-export-components).

export type BandTone = "good" | "warn" | "danger";
export interface Band { upto: number; tone: BandTone; } // ranges ascending by `upto`; last `upto` = max

// The qualitative status a value lands in, given its bands. The overview donut derives each segment's
// tone from this same helper the gauge uses, so the at-a-glance ring and the detail bar can never
// disagree. (sorted ascending; the last band's tone is the fallback for values above every threshold.)
export function bandTone(value: number, bands: Band[]): BandTone {
  const sorted = [...bands].sort((a, b) => a.upto - b.upto);
  return (sorted.find((b) => value <= b.upto) ?? sorted[sorted.length - 1])?.tone ?? "good";
}
