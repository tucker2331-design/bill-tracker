// Health rules (v9), free of runtime imports so a bare-node golden runs the REAL code
// (test: web/src/views/__tests__/health_rules.regression.mjs).
//
// THE ONE LIST. Every ring segment, problem row and dial is computed from `Instrument[]` — the overview cannot
// disagree with the detail. The surface is BINARY (P25a, owner 2026-07-29 "no yellow"): an instrument is clean only
// when it has a value AND that value is within its limit. A missing value ("unconfirmed") is NOT clean: it reads red,
// never grey. Every instrument is "lower is better": a coverage metric is shown as the COUNT of what is missing
// (bills missing, bills with no patron), which is also P26's natural frequency.

export type Category = "Accuracy" | "Completeness" | "Freshness" | "Stability";
export const CATEGORIES: Category[] = ["Accuracy", "Completeness", "Freshness", "Stability"];
/** P24/P25: does a non-clean reading mean a PUBLISHED value is wrong? A structural field, never prose. */
export type Impeach = "yes" | "no" | "unknown";

export interface Instrument {
  id: string;
  cat: Category;
  name: string;
  value: number | null;   // null = no result this cycle
  of?: number;            // denominator, when the value is a count out of a total ("3,738 of 65,414")
  limit: number;          // the clean side of the boundary (inclusive)
  max: number;            // the dial's far end
  unit?: "h";
  impeaches: Impeach;     // what a non-clean reading says about published values
  note?: string;
}

export const isClean = (i: Instrument): boolean => i.value !== null && Number.isFinite(i.value) && i.value <= i.limit;

/** A non-instrument input to a ring (breaker armed, ledger readable, alerts clear) — same binary rule. */
export interface RingExtra { cat: Category; name: string; ok: boolean }

export interface Ring { cat: Category; segs: { name: string; ok: boolean }[]; ok: number; total: number }

export function rings(insts: Instrument[], extras: RingExtra[]): Ring[] {
  return CATEGORIES.map((cat) => {
    const segs = [
      ...insts.filter((i) => i.cat === cat).map((i) => ({ name: i.name, ok: isClean(i) })),
      ...extras.filter((e) => e.cat === cat).map((e) => ({ name: e.name, ok: e.ok })),
    ];
    return { cat, segs, ok: segs.filter((s) => s.ok).length, total: segs.length };
  });
}

/** Where the needle sits on the dial, 0..1. The left 60% of the arc (grey) runs 0 -> limit; the right 40% (red)
 *  runs limit -> max. Every dial reads the same way. A limit of 0 puts any non-zero value straight into the red. */
export function dialPos(i: Instrument): number {
  if (i.value === null || !Number.isFinite(i.value)) return 0;
  const v = Math.max(0, i.value);
  if (v <= i.limit) return i.limit > 0 ? 0.6 * (v / i.limit) : 0;
  const span = Math.max(1e-9, i.max - i.limit);
  return Math.min(1, 0.6 + 0.4 * ((v - i.limit) / span));
}

/** The freshness limit, calibrated on the worker's OBSERVED write rhythm (newest-first heartbeat ms) — the same
 *  rule the trust-surface guard applies to job liveness: the larger of twice the median gap and 1.5x the largest
 *  recent gap, never below `floorH`. A fixed 6 h limit false-alarmed every night off-season, when the bill worker
 *  writes about every 6 h. Fewer than 3 heartbeats = rhythm unknown -> the floor (stricter, never looser). */
export function rhythmLimitHours(beats: number[], floorH = 6, window = 30): number {
  const ts = beats.slice(0, window + 1);
  if (ts.length < 3) return floorH;
  const gaps = ts.slice(0, -1).map((t, k) => (t - ts[k + 1]) / 3.6e6).filter((g) => g > 0).sort((a, b) => a - b);
  if (gaps.length < 2) return floorH;
  const median = gaps[Math.floor(gaps.length / 2)], largest = gaps[gaps.length - 1];
  return Math.max(floorH, 2 * median, 1.5 * largest);
}

export interface Verdict { clean: boolean; problems: number; wrong: number; noResult: number }

/** The one verdict at the top: clean only when NOTHING is open. `wrong` counts problems whose published-value
 *  field is "yes"; `noResult` counts instruments with no value. */
export function verdictOf(insts: Instrument[], problemImpeach: Impeach[]): Verdict {
  return {
    clean: problemImpeach.length === 0,
    problems: problemImpeach.length,
    wrong: problemImpeach.filter((x) => x === "yes").length,
    noResult: insts.filter((i) => i.value === null).length,
  };
}
