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
// `verifyApplies: false` = this category has NO external oracle (Freshness — there's no authoritative source
// for "is our clock right"), so it shows an explicit "no outside check applies" line instead of a blank one
// that looked like a bug (F-3b). `anchor` = the id of the detail section the Status line jumps to (F-3c).
export interface Vital { name: string; segs: VitalSeg[]; verify?: VitalVerify; verifyApplies?: boolean; anchor?: string; }

const STROKE: Record<VTone, string> = {
  good: "var(--ok)",
  warn: "var(--o-carry)",   // amber
  danger: "var(--stale)",   // red — the danger reading pops
  unknown: "var(--ink-faint)", // neutral grey: present but unconfirmed (never reads as good)
};
const INK: Record<VTone, string> = {
  // unknown ink is the NEUTRAL grey, never the dead/failure hue: "unknown ≠ bad" ("allowed not to know,
  // never pretend" — §7). Was --o-dead back when that token was grey; the color-swap made --o-dead a pale
  // red, so unknown now reads on the dedicated --neutral grey (matches STROKE.unknown's intent). Qodo #188.
  good: "var(--ok)", warn: "var(--o-carry)", danger: "var(--stale)", unknown: "var(--neutral)",
};
const GLYPH: Record<VTone, string> = { good: "✓", warn: "!", danger: "✕", unknown: "?" };
// Plain words for the hover title so "1 warning" says WHICH segment(s) and how bad (F-3c).
const TONE_WORD: Record<VTone, string> = { good: "ok", warn: "warning", danger: "critical", unknown: "unconfirmed" };
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
  // F-3c: the Status rollup names WHICH segment(s) are off (hover) and, when non-green, is a click target
  // that scrolls to this category's detail section (the data is already on the page — this is just wiring).
  const nonGreen = segs.filter((s) => s.tone !== "good");
  const statusTitle = nonGreen.length
    ? `${v.name} · ${nonGreen.map((s) => `${s.label} (${TONE_WORD[s.tone]})`).join(", ")} — click to see the detail below`
    : `${v.name}: all ${n} check${n === 1 ? "" : "s"} green`;
  const drillable = nonGreen.length > 0 && !!v.anchor;
  const drill = () => {
    if (v.anchor) document.getElementById(v.anchor)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  // Expose the verification provenance to screen-readers + non-hover (touch) devices, not only the hover
  // `title` (CodeRabbit #183). Flatten the multi-line title into one spoken sentence.
  const vAria = v.verify ? `Independent verification — ${v.verify.text}. ${v.verify.title.replace(/\n/g, "; ")}` : undefined;
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
      {/* STATUS line — the LIVE rollup of this ring's own segments. Labeled "Status:" so it's not confused
          with the outside-check "Verified:" line below (F-3a). Clickable to the detail section when non-green (F-3c). */}
      {drillable ? (
        <button type="button" className="hl-vstat" style={{ color: INK[overall] }} title={statusTitle} onClick={drill}
          aria-label={`Status — ${statusLine(segs)}. ${statusTitle}`}>
          Status: {statusLine(segs)} <span className="hl-drill" aria-hidden="true">↓</span>
        </button>
      ) : (
        <div className="hl-vstat" style={{ color: INK[overall] }} title={statusTitle}>Status: {statusLine(segs)}</div>
      )}
      {/* VERIFIED line — the INDEPENDENT outside cross-check (GitHub Actions guard), a DIFFERENT thing from the
          live Status above. Labeled "Verified:" (F-3a). ALWAYS rendered so all four rings are parallel (F-3b):
          a real badge, "checking…" while guards load, or an explicit "no outside check applies" for Freshness
          (which has no external oracle) — never a blank line that reads as a missing/broken ring. */}
      {v.verifyApplies === false ? (
        <span className="hl-vverify na" title="Freshness has no external oracle — there's no authoritative source for &quot;is our clock right&quot;, so this ring has no independent cross-check. Its accuracy is the two live segment clocks above.">
          Verified: — no outside check applies
        </span>
      ) : v.verify ? (
        v.verify.url
          ? <a className={`hl-vverify ${v.verify.state}`} href={v.verify.url} target="_blank" rel="noreferrer" title={v.verify.title} aria-label={vAria}>Verified: {v.verify.text}</a>
          : <span className={`hl-vverify ${v.verify.state}`} title={v.verify.title} aria-label={vAria}>Verified: {v.verify.text}</span>
      ) : (
        <span className="hl-vverify unknown" title="Checking this category against its outside source (GitHub Actions guard)…">Verified: checking…</span>
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
