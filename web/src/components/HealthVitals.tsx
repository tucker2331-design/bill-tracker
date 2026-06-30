// The Health tab's at-a-glance "vitals" (owner: "quell my anxieties at a glance" — donut form, a little
// more info per ring, with some wow). Four segmented activity-ring donuts — one per category — each ring
// split into one arc per tracked metric. Calm green field; a warning/critical segment pops in saturated
// amber/red so the eye lands on the only thing that needs a look, then you scroll to the bullet graphs
// for WHICH gauge. The per-segment tone is derived by `bandTone` from the SAME bands the detail gauges
// use (single source of truth — the overview can never disagree with the detail below it).
//
// "Unknown" is a first-class tone (neutral grey, not green and not red): when a backend's payload is
// absent we show the ring as unconfirmed rather than a false all-clear ("allowed not to know, never
// pretend" — vision §7). Magnitude lives on arc length here, which Munzner ranks below position/length;
// that's acceptable for a qualitative STATUS glance (spot the non-green), and the precise numbers live in
// the bullet graphs below. Channels used for the popout: saturated hue against a muted field (Few 7.1.5).

export type VTone = "good" | "warn" | "danger" | "unknown";
export interface VitalSeg { label: string; tone: VTone; }
// Optional INDEPENDENT-verification badge merged onto a donut (vision §7 trust layer). The 5-layer durability
// guard cross-checks our self-reported numbers against OUTSIDE sources (LIS's own calendar / the MinutesBook);
// surfacing its verdict ON the matching dial — instead of a separate panel — says "here's the rollup AND an
// outside source agrees," without reading as a second data readout. `text` is the bare face; `title` (hover)
// carries the source + cadence + last-run so the freshness no longer reads as "stale" on the surface.
export type VVerify = "pass" | "fail" | "running" | "unknown" | "stale";
export interface VitalVerify { state: VVerify; text: string; title: string; url: string | null; }
export interface Vital { name: string; segs: VitalSeg[]; verify?: VitalVerify; }

const STROKE: Record<VTone, string> = {
  good: "var(--ok)",
  warn: "var(--o-carry)",   // amber
  danger: "var(--stale)",   // red — the danger reading pops
  unknown: "var(--ink-faint)", // neutral grey: present but unconfirmed (never reads as good)
};
const INK: Record<VTone, string> = {
  good: "var(--ok)", warn: "var(--o-carry)", danger: "var(--stale)", unknown: "var(--o-dead)",
};
const GLYPH: Record<VTone, string> = { good: "✓", warn: "!", danger: "✕", unknown: "?" };
// worst-of rollup: danger dominates, then warn, then unknown (can't confirm) — only an all-confirmed-good
// category reads green. So one unconfirmed metric greys the ring rather than faking a clean bill of health.
const RANK: Record<VTone, number> = { good: 0, unknown: 1, warn: 2, danger: 3 };
const worst = (segs: VitalSeg[]): VTone =>
  segs.reduce<VTone>((w, s) => (RANK[s.tone] > RANK[w] ? s.tone : w), "good");

const R = 46, SW = 11, CX = 60, C = 2 * Math.PI * R;

function statusLine(segs: VitalSeg[]): string {
  const d = segs.filter((s) => s.tone === "danger").length;
  const w = segs.filter((s) => s.tone === "warn").length;
  const u = segs.filter((s) => s.tone === "unknown").length;
  if (d) return `${d} critical`;
  if (w) return `${w} warning${w > 1 ? "s" : ""}`;
  if (u) return `${u} unconfirmed`;
  return "All clear";
}

function Donut({ v }: { v: Vital }) {
  const { segs } = v;
  const n = segs.length;
  const ok = segs.filter((s) => s.tone === "good").length;
  const overall = worst(segs);
  const slot = 360 / n;
  const gap = n > 1 ? 22 : 0;            // degrees of breathing room between arcs (rounded caps eat ~14°)
  const dash = (C * (slot - gap)) / 360; // visible arc length per segment

  return (
    <div className="hl-vcard">
      <div className="hl-donut" role="img"
        aria-label={`${v.name}: ${ok} of ${n} checks OK — ${statusLine(segs)}`}>
        <svg viewBox="0 0 120 120" aria-hidden="true">
          {/* full-circle track so the gaps read as an intentional ring, not missing data */}
          <circle cx={CX} cy={CX} r={R} fill="none" stroke="var(--line)" strokeWidth={SW} />
          {segs.map((s, i) => (
            <circle key={i} cx={CX} cy={CX} r={R} fill="none" stroke={STROKE[s.tone]}
              strokeWidth={SW} strokeLinecap="round" strokeDasharray={`${dash} ${C}`}
              transform={`rotate(${-90 + i * slot + gap / 2} ${CX} ${CX})`}>
              <title>{`${s.label} — ${s.tone}`}</title>
            </circle>
          ))}
        </svg>
        <div className="hl-donc">
          <div className="hl-donnum" style={{ color: INK[overall] }}>{ok}<span>/{n}</span></div>
          <div className="hl-donmk" style={{ color: INK[overall] }}>{GLYPH[overall]}</div>
        </div>
      </div>
      <div className="hl-vname">{v.name}</div>
      <div className="hl-vstat" style={{ color: INK[overall] }}>{statusLine(segs)}</div>
      {/* Independent-verification trust line (merged from the old "Are we right?" panel). Only on dials that
          HAVE an outside cross-check; a link when the run is reachable, else plain text. Hover for the source. */}
      {v.verify && (
        v.verify.url
          ? <a className={`hl-vverify ${v.verify.state}`} href={v.verify.url} target="_blank" rel="noreferrer" title={v.verify.title}>{v.verify.text}</a>
          : <span className={`hl-vverify ${v.verify.state}`} title={v.verify.title}>{v.verify.text}</span>
      )}
    </div>
  );
}

export function HealthVitals({ vitals }: { vitals: Vital[] }) {
  return (
    <div className="hl-vitals">
      {vitals.map((v) => <Donut key={v.name} v={v} />)}
    </div>
  );
}
