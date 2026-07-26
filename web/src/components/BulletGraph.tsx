// A Few bullet graph (PL-8 / owner's "RPM redline"): a horizontal track with qualitative GOOD/WARNING/
// DANGER bands behind a single thin MEASURE bar = the current value, plus a TARGET tick = the goal. The
// value's color follows the band it lands in, so a danger reading pops red (preattentive, Munzner popout).
// Direction-agnostic: the CALLER orders the band tones (danger-left for higher-is-better, danger-right for
// lower-is-better), so this component never needs to know which way is "good".

import { bandTone, type Band, type BandTone } from "./bands";
import { Sparkline } from "./Sparkline";
export type { Band, BandTone } from "./bands"; // re-export for existing `import … from "./BulletGraph"` callers

const BAND_BG: Record<BandTone, string> = {
  good: "var(--bg-good)",
  warn: "var(--bg-warn)",
  danger: "var(--bg-danger)",
};
const TONE_INK: Record<BandTone, string> = {
  good: "var(--ok)",
  warn: "var(--o-carry)", // amber
  danger: "var(--stale)", // red — the danger reading
};

export interface BulletGraphProps {
  /** DOM id so a Vitals ring can scroll straight to the metric that is actually failing (F-3c / W0b). */
  id?: string;
  label: string;
  value: number;
  max: number;
  target?: number;
  bands: Band[];
  format?: (n: number) => string;
  unit?: string;
  sub?: string; // small caption (e.g. the denominator — PL-7)
  spark?: number[];          // optional per-cycle trend (Metrics_History); <2 points renders "—"
  sparkLowerBetter?: boolean; // polarity for the trend tint (default true: rising = worse)
}

export function BulletGraph({ id, label, value, max, target, bands, format, unit, sub, spark, sparkLowerBetter = true }: BulletGraphProps) {
  const safeMax = max > 0 ? max : 1;
  const pct = (v: number) => Math.max(0, Math.min(1, v / safeMax)) * 100;
  const sorted = [...bands].sort((a, b) => a.upto - b.upto);
  const tone: BandTone = bandTone(value, bands);
  const fmt = format ?? ((n: number) => n.toLocaleString());
  const u = unit ?? "";

  let prev = 0;
  const segs = sorted.map((b, i) => {
    const left = pct(prev), width = pct(b.upto) - pct(prev);
    prev = b.upto;
    return <span key={i} className="bg-band" style={{ left: `${left}%`, width: `${width}%`, background: BAND_BG[b.tone] }} />;
  });

  return (
    <div className="bg-row" id={id} role="group"
      aria-label={`${label}: ${fmt(value)}${u} — ${tone}${target != null ? `, target ${fmt(target)}${u}` : ""}`}>
      <div className="bg-head">
        <span className="bg-label">{label}</span>
        {spark && <span className="bg-spark" title="trend (recent cycles)"><Sparkline values={spark} lowerBetter={sparkLowerBetter} /></span>}
        <span className="bg-value" style={{ color: TONE_INK[tone] }}>{fmt(value)}{u}</span>
      </div>
      <div className="bg-track">
        {segs}
        <span className="bg-measure" style={{ width: `${pct(value)}%`, background: TONE_INK[tone] }} />
        {target != null && <span className="bg-target" style={{ left: `${pct(target)}%` }} title={`target ${fmt(target)}${u}`} />}
      </div>
      {sub && <div className="bg-sub">{sub}</div>}
    </div>
  );
}
