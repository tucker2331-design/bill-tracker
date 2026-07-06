import { useEffect, useState } from "react";
import type { Completeness } from "../data/types";
import { BulletGraph } from "../components/BulletGraph";
import { bandTone, type Band } from "../components/bands";
import { HealthVitals, type Vital, type VitalSeg, type VitalVerify } from "../components/HealthVitals";
import { loadHealth, type HealthData } from "../data/health";
import { loadVerification, type GuardRun, type GuardState } from "../data/verification";
import { loadHistory, seriesFor, seriesForPct, type HistoryData } from "../data/history";

// The operator / Health tab (vision §3f + §7): the trust signals the system ALREADY produces, as Few
// bullet graphs with danger bands (PL-8 / owner's "RPM redline"). Bill-backend signals arrive via props
// (App loaded Bill_Tracker R1); calendar-subsystem signals load here from Sheet1 (lightweight, health.ts).
// "Allowed not to know; never to pretend." Access-gated to the owner + a few (Cloudflare Access — see
// docs/design/health_operator_tab.md). Calibration: bands from the worker's breaker thresholds + steady state.

// Band presets. lowerBetter: good→warn→DANGER (danger on the right; the bar grows INTO the redline).
const lower = (good: number, warn: number, max: number): Band[] =>
  [{ upto: good, tone: "good" }, { upto: warn, tone: "warn" }, { upto: max, tone: "danger" }];
// higherBetter: DANGER→warn→good (danger on the left; the bar fills toward the good target on the right).
const higher = (danger: number, warn: number, max = 100): Band[] =>
  [{ upto: danger, tone: "danger" }, { upto: warn, tone: "warn" }, { upto: max, tone: "good" }];

// Feed-skew is dominated by the BILL backend's clock vs the calendar worker's ~15min. A HEALTHY skew is up
// to ~6h BY DESIGN; derive the chip thresholds from that cadence so it only warns when the skew exceeds what
// the cadence explains (was a flat 3h/8h → amber during every normal bill cycle). [code-review finding #1]
// HEURISTIC (Standard #1): ASSUMES bill_tracker.yml stays on its 6h cron (`40 */6 * * *`); it BREAKS (false
// "in sync" or false "lagging") if that cron changes; there is no runtime cross-check — this is a UI display
// band, not a data-path heuristic — so if the cron cadence changes, update BILL_CADENCE_H to match it.
const BILL_CADENCE_H = 6;
const SKEW_OK_H = BILL_CADENCE_H + 1;        // ≤7h: within one bill cycle (+1h jitter/queue) = healthy
const SKEW_WARN_H = BILL_CADENCE_H * 2 + 1;  // ≤13h: bill backend missed a scheduled run; >13h = stalled

const hoursSince = (d: Date | null) => (d ? (Date.now() - d.getTime()) / 3.6e6 : NaN);
const hrs = (n: number) => (Number.isFinite(n) ? `${n.toFixed(1)}` : "—");
const oneDp = (n: number) => n.toFixed(1);
const agoText = (d: Date | null) => {
  if (!d) return "";
  const h = (Date.now() - d.getTime()) / 3.6e6;
  if (h < 1) return "just now";
  if (h < 24) return `${Math.round(h)}h ago`;
  return `${Math.round(h / 24)}d ago`;
};

export function Health({ completeness, dataAsOf }: { completeness: Completeness | null; dataAsOf: Date | null }) {
  const [h, setH] = useState<HealthData | null>(null);
  const [hErr, setHErr] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    loadHealth().then((d) => alive && setH(d)).catch((e) => alive && setHErr(String(e?.message || e)));
    return () => { alive = false; };
  }, []);
  const [guards, setGuards] = useState<GuardRun[] | null>(null);
  useEffect(() => {
    let alive = true;
    loadVerification().then((d) => alive && setGuards(d)).catch(() => alive && setGuards([]));
    return () => { alive = false; };
  }, []);
  // Per-cycle trend store (Metrics_History). Optional chrome: a null/empty result leaves the gauges as
  // point-in-time only (no sparkline), never blanks the tab.
  const [hist, setHist] = useState<HistoryData | null>(null);
  useEffect(() => {
    let alive = true;
    loadHistory().then((d) => alive && setHist(d)).catch(() => alive && setHist(null));
    return () => { alive = false; };
  }, []);
  const spark = (key: string) => (hist ? seriesFor(hist, key) : []);

  if (!completeness && !h && !hErr) return <p className="center-msg">Loading operator health…</p>;

  // ── Bill-backend signals (props) ──
  const c = completeness;
  const universe = c?.universe_count ?? 0;
  const written = c?.records_written ?? 0;
  const anomalies = c?.in_history_not_in_universe?.length ?? 0;
  const completePct = universe > 0 ? (100 * written) / universe : 0;
  const patronPct = written > 0 ? (100 * (c?.patron_present ?? 0)) / written : 0;
  const driftPct = (c?.outcome_keyword_mismatch_rate ?? 0) * 100;
  const billFreshH = hoursSince(dataAsOf);

  // ── Calendar-subsystem signals (Sheet1) ──
  const m = h?.metrics ?? {};
  const total = m.total_processed ?? 0;
  const section9 = m.meeting_unsourced;          // the core accuracy metric
  const violations = m.invariant_violations;
  const unclassPct = total > 0 ? (100 * (m.legevent_route_blank ?? 0)) / total : 0;
  const calFreshH = hoursSince(h?.calendarFreshness ?? null);
  const breakerOk = h ? !h.breakerTrip : true;

  // ── Upstream-vocabulary CANARIES (green-state). The worker records each drift monitor's outcome into
  // SYSTEM_METRICS: -1 = couldn't determine (unknown), 0 = ran clean, N = N novel value(s) = drift. Surfacing
  // the GREEN state (not just the drift alert) proves the watchers are ALIVE — silence could also mean a dead
  // canary. A missing key (older worker) and -1 both render "unknown", never a false ✓. ──
  const canaryDefs: { key: string; label: string }[] = [
    { key: "canary_status_grouping", label: "Legislation status vocabulary" },
    { key: "canary_governor_eventcodes", label: "Governor action codes" },
    { key: "canary_refid_shape", label: "Refid namespaces" },
    { key: "canary_scheduletype", label: "Schedule types" },
    { key: "canary_referencetype", label: "Reference types" },
  ];
  const canaries = canaryDefs.map(({ key, label }) => {
    const v = m[key];
    const state = v == null || v < 0 ? "unknown" : v === 0 ? "clean" : "drift";
    return { label, state, count: state === "drift" ? v : 0 };
  });

  // ── Feed-skew: the two subsystems write on independent clocks (bill backend vs calendar worker). A large
  // gap means the picture is internally inconsistent — a bill's history moved but the calendar hasn't caught
  // up (or vice-versa). Computed from the two freshness clocks the tab already has (front-end only — the
  // deeper per-source skew is scoped as a follow-up). Only meaningful when BOTH clocks are known. ──
  const feedSkewH = Number.isFinite(billFreshH) && Number.isFinite(calFreshH) ? Math.abs(billFreshH - calFreshH) : NaN;

  // ── Source-feed freshness (the grounded "per-bill freshness"): age of the HISTORY.CSV blob the bill
  // data is bulk re-derived from. The worker writes minutes; -1 / absent = unknown (older worker or no
  // Last-Modified this cycle) and must NOT render as a fresh 0. ──
  const blobAgeMin = m.history_blob_age_min;
  const blobAgeKnown = typeof blobAgeMin === "number" && blobAgeMin >= 0;
  const blobAgeH = blobAgeKnown ? blobAgeMin / 60 : NaN;
  // Source-feed severity is meaningful ONLY during an ACTIVE session: off-season HISTORY.CSV legitimately
  // doesn't change (no new actions), so a large blob age is EXPECTED, not a fault. The gauge is HIDDEN when
  // sessionActive is null (Sheet1!S1 unreadable) — see its render guard — because BulletGraph has no neutral
  // tone and an all-good band on an UNKNOWN session would be a false-green (CodeRabbit + Qodo #182). So these
  // bands are only used for the two KNOWN states: ACTIVE → redline, ADJOURNED → all-good (honest: we KNOW the
  // blob is meant to be static off-season). HEURISTIC (Standard #1): the in-session 12/24/48h redline is
  // PROVISIONAL — LIS's real HISTORY.CSV refresh cadence isn't measured yet; it BREAKS (false-warn) if LIS
  // refreshes slower than ~12h in-season; REFINE once Metrics_History has real blob-age data. [finding #3]
  const sessionActive = h?.sessionActive ?? null;
  const blobAgeBands: Band[] = sessionActive === true ? lower(12, 24, 48) : [{ upto: 1e9, tone: "good" }];

  // ── Alert HISTORY: Metrics_History holds one row per cycle, so a persistent alert (e.g. a standing
  // TIMING_LAG) repeats every cycle it fires. A raw dump would flood; the useful view AGGREGATES distinct
  // alerts (by severity+category+message) with a fire COUNT + first/last-seen — "what has fired, and how
  // often," which a point-in-time snapshot can't show. Newest-last-seen first. ──
  const alertHistory = (() => {
    if (!hist?.available || hist.alerts.length === 0) return null;
    type Distinct = { severity: string; category: string; message: string; count: number; firstTs: number; lastTs: number };
    const byKey = new Map<string, Distinct>();
    for (const a of hist.alerts) {
      const k = `${a.severity}|${a.category}|${a.message}`;
      const e = byKey.get(k);
      if (e) { e.count++; e.firstTs = Math.min(e.firstTs, a.ts); e.lastTs = Math.max(e.lastTs, a.ts); }
      else byKey.set(k, { severity: a.severity, category: a.category, message: a.message, count: 1, firstTs: a.ts, lastTs: a.ts });
    }
    // Collapse HIGH-VOLUME routine categories so they don't flood the feed. A category
    // with many DISTINCT messages (e.g. per-bill TIMING_LAG deferrals) is a routine
    // aggregate, not N separate anomalies (Standard #8) — group it into one expandable
    // summary. Categories with few distinct alerts (breaker, drift, API failure — the
    // genuine "needs a human" signals) stay fully expanded. (Owner 2026-07-03: the feed
    // read as alarming from ~471 benign deferral WARNs; the worker also stopped emitting
    // them per-row, so this is belt-and-suspenders + handles the historical backlog.)
    const COLLAPSE_AT = 8;
    const groups = new Map<string, Distinct[]>();
    for (const d of byKey.values()) (groups.get(`${d.severity}|${d.category}`) ?? groups.set(`${d.severity}|${d.category}`, []).get(`${d.severity}|${d.category}`)!).push(d);
    type Single = { kind: "single" } & Distinct;
    type Group = { kind: "group"; severity: string; category: string; distinct: number; totalCount: number; lastTs: number; items: Distinct[] };
    const out: (Single | Group)[] = [];
    for (const [, ds] of groups) {
      if (ds.length > COLLAPSE_AT) {
        out.push({ kind: "group", severity: ds[0].severity, category: ds[0].category, distinct: ds.length,
          totalCount: ds.reduce((s, d) => s + d.count, 0), lastTs: Math.max(...ds.map((d) => d.lastTs)),
          items: ds.sort((a, b) => b.lastTs - a.lastTs) });
      } else {
        for (const d of ds) out.push({ kind: "single", ...d });
      }
    }
    return out.sort((x, y) => y.lastTs - x.lastTs);
  })();

  // ── At-a-glance vitals: roll the gauges below into four category rings. Each segment's tone comes from
  // `bandTone` over the SAME bands the matching gauge uses, so the donut and the detail never disagree; a
  // segment whose backend payload is absent is "unknown" (grey), never a false green. ──
  const sv = (label: string, value: number, bands: Band[], known: boolean): VitalSeg =>
    ({ label, tone: known ? bandTone(value, bands) : "unknown" });
  const critCount = h ? h.alerts.filter((a) => a.severity === "CRITICAL").length : 0;
  const warnCount = h ? h.alerts.filter((a) => a.severity === "WARN").length : 0;

  // Independent-verification badge per dial (replaces the standalone "Are we right?" panel). Each category
  // rolls up the guards that cross-check it against an OUTSIDE source (LIS calendar / MinutesBook); shows the
  // worst-of status, with the source + cadence + last-run in the HOVER title so the bare freshness no longer
  // reads as "stale" on the face. A category with no guard (Freshness) gets no badge; while guards load → none.
  const VRANK: Record<GuardState, number> = { pass: 0, unknown: 1, running: 2, fail: 3 };
  const vitalVerify = (keys: string[]): VitalVerify | undefined => {
    if (!guards) return undefined;                         // still loading → no badge yet
    const gs = guards.filter((g) => keys.includes(g.key));
    // vitalVerify is only ever called with REAL guard keys, so an empty match means verification LOADED but
    // returned nothing (GitHub Actions unreachable → guards === []). Show "— unverifiable" rather than drop
    // the badge, which would falsely read as "this dial has no independent check" ("never pretend" — CodeRabbit #183).
    if (gs.length === 0) return { state: "unknown", text: "— unverifiable", title: "Independent verification unavailable — couldn't reach GitHub Actions.", url: null };
    const worstG = gs.reduce((w, g) => (VRANK[g.status] > VRANK[w.status] ? g : w), gs[0]);
    const anyStale = gs.some((g) => g.stale && g.status === "pass");
    const state: VitalVerify["state"] =
      worstG.status === "fail" ? "fail"
      : worstG.status === "running" ? "running"
      : worstG.status === "unknown" ? "unknown"
      : anyStale ? "stale" : "pass";
    // NAME the check on the badge face (owner 2026-07-03: "what does 'independently confirmed' mean —
    // how can Stability be confirmed WITH a warning?"). The generic wording read as "everything on this
    // ring is fine," contradicting a live amber segment. The badge covers only the named OUTSIDE
    // cross-check (e.g. the sustainability audit); the ring segments above are the LIVE internal signals
    // — two different things, so say which one this is.
    // A NON-pass badge names only the guard(s) actually IN the worst state (Qodo + CodeRabbit #192):
    // with two guards on a dial, "✕ A + B check FAILED" would smear a passing B with A's failure.
    const names = gs.map((g) => g.label).join(" + ");
    const worstNames = gs.filter((g) => g.status === worstG.status).map((g) => g.label).join(" + ");
    const text =
      state === "fail" ? `✕ ${worstNames} check FAILED`
      : state === "running" ? `${worstNames} check running…`
      : state === "unknown" ? "— unverifiable"
      : state === "stale" ? `✓ ${names} check passed · re-check overdue`
      : `✓ ${names} check passed`;
    const title = gs.map((g) => `${g.label} (${g.cadence}${g.lastRun ? `, ${agoText(g.lastRun)}` : ", never run"}): ${g.proves}`).join("\n")
      + "\n\nThis badge reports the named OUTSIDE cross-check only; the ring above shows the live internal signals — a warning there and a passing check here can coexist.";
    return { state, text, title, url: worstG.url };
  };

  // `verifyApplies` + `anchor` drive F-3 (see HealthVitals): the outside-check line is explicit even where
  // there's no oracle (Freshness), and each Status rollup jumps to its own detail section when non-green.
  const vitals: Vital[] = [
    { name: "Accuracy", segs: [
      sv("Section-9 · meeting actions without a time", section9 ?? 0, lower(0.5, 25, 50), section9 != null),
      sv("Outcome drift · keyword↔structural", driftPct, lower(0.1, 1, 2), c?.outcome_keyword_mismatch_rate != null),
    ], verify: vitalVerify(["accuracy_sentinel.yml", "legevent_reconcile.yml"]), verifyApplies: true, anchor: "hl-sec-accuracy" },
    { name: "Completeness", segs: [
      sv("Bill completeness · records vs universe", completePct, higher(98, 99.99, 100), !!c && universe > 0),
      sv("History-vs-universe anomalies", anomalies, lower(0.5, 5, 20), !!c),
      sv("Patron coverage", patronPct, higher(98, 99.99, 100), !!c && written > 0),
      sv("Unclassified share · router blank", unclassPct, lower(8, 15, 25), !!h && total > 0),
    ], verify: vitalVerify(["completeness_tripwire.yml"]), verifyApplies: true, anchor: "hl-sec-accuracy" },
    { name: "Freshness", segs: [
      sv("Bill backend clock", billFreshH, lower(6, 12, 24), !!dataAsOf),
      sv("Calendar clock", calFreshH, lower(6, 12, 24), !!h?.calendarFreshness),
    ], verifyApplies: false, anchor: "hl-sec-freshness" },
    { name: "Stability", segs: [
      { label: "Circuit breaker", tone: !h ? "unknown" : breakerOk ? "good" : "danger" },
      sv("Write-time invariant violations", violations ?? 0, lower(0.5, 49, 60), violations != null),
      { label: "Active alerts", tone: !h ? "unknown" : critCount ? "danger" : warnCount ? "warn" : "good" },
    ], verify: vitalVerify(["sustainability_audit.yml"]), verifyApplies: true, anchor: "hl-sec-alerts" },
  ];

  return (
    <div>
      <h2 className="h">At a glance</h2>
      <HealthVitals vitals={vitals} />

      {/* ── System status: the breaker + the TWO freshnesses (different workers) ── */}
      <div className="hl-status">
        {!h ? (
          // Don't claim "armed" before the calendar-worker payload loads — that's a false green when we
          // simply don't know yet (CodeRabbit #167; "never pretend"). Show the unknown state instead.
          <span className="hl-breaker unknown">● Circuit breaker — awaiting calendar worker</span>
        ) : (
          <span className={`hl-breaker ${breakerOk ? "ok" : "trip"}`}>
            {breakerOk ? "● Circuit breaker armed" : "▲ BREAKER TRIPPED"}
          </span>
        )}
        {h && !breakerOk && h.breakerTrip && (
          <span className="muted" style={{ fontSize: 12 }}>
            tripped {String((h.breakerTrip as { trip_utc?: string }).trip_utc ?? "")} — Sheet1 holds last-known-good
          </span>
        )}
      </div>

      {/* The old standalone "Are we right? · independent verification" panel was MERGED onto the at-a-glance
          dials above (each donut now carries an "independently confirmed" trust line from the same guards) —
          it read as a second data readout next to the gauges; on the dial it reads as "an outside source
          agrees." See HealthVitals `verify` + `vitalVerify` above. */}

      {/* ── Upstream watchers (drift-canary GREEN-STATE): the five vocabulary monitors that catch LIS
            changing its own codes/shapes. They alert on drift; this shows the ALL-CLEAR too, so silence is
            "actively checked" not "the canary died." "?" = the worker couldn't determine it this cycle. ── */}
      <h2 className="h">Upstream watchers {h && <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· is LIS still speaking our language?</span>}</h2>
      {h ? (
        <div className="hl-canaries panel">
          {canaries.map((cn) => (
            <div key={cn.label} className={`hl-canary ${cn.state}`}>
              <span className="hl-cdot" aria-hidden="true" />
              <span className="hl-clabel">{cn.label}</span>
              <span className="hl-cstat">
                {cn.state === "clean" ? "✓ no drift" : cn.state === "drift" ? `▲ ${cn.count} new value${cn.count === 1 ? "" : "s"}` : "? not checked"}
              </span>
            </div>
          ))}
          <div className="hl-vfoot muted">
            Each watcher diffs LIS's live vocabulary against the structural router's. A “?” means the worker
            couldn't reach the upstream list this cycle — never read it as healthy.
          </div>
        </div>
      ) : <CalLoading err={hErr} />}

      <h2 className="h" id="hl-sec-accuracy" style={{ scrollMarginTop: 84 }}>Accuracy &amp; completeness — the lobbyist-facing guarantees</h2>
      <div className="hl-gauges">
        {h ? (
          <BulletGraph label="Section-9 accuracy · meeting actions without a time" value={section9 ?? 0}
            max={50} target={0} bands={lower(0.5, 25, 50)} spark={spark("meeting_unsourced")}
            sub="0 = every meeting action has a time (the project goal)" />
        ) : <CalLoading err={hErr} />}
        {/* Bill-backend gauges only render when the completeness payload is present — a null payload must NOT
            display as a real 0% / 0 (that would read as a false danger; "allowed not to know, never pretend"). */}
        {c ? (<>
          <BulletGraph label="Bill completeness · records written vs LIS universe" value={completePct}
            max={100} target={100} bands={higher(98, 99.99, 100)} unit="%" format={oneDp}
            sub={`${written.toLocaleString()} of ${universe.toLocaleString()} bills${anomalies ? ` · ${anomalies} in-history-not-in-universe` : ""}`} />
          <BulletGraph label="History-vs-universe anomalies" value={anomalies}
            max={20} target={0} bands={lower(0.5, 5, 20)} sub="bills seen in HISTORY but absent from the universe (scariest silent gap)" />
        </>) : <p className="muted">Bill-backend signals unavailable (no completeness payload in Bill_Tracker R1).</p>}
      </div>

      <h2 className="h" id="hl-sec-freshness" style={{ scrollMarginTop: 84 }}>Freshness — two workers, two clocks</h2>
      <div className="hl-gauges">
        {dataAsOf ? (
          <BulletGraph label="Bill backend · hours since last good run" value={billFreshH}
            max={24} target={0} bands={lower(6, 12, 24)} unit=" h" format={hrs}
            sub={c?.checked_at_utc || dataAsOf.toISOString()} />
        ) : <p className="muted">Bill-backend freshness unknown (no timestamp).</p>}
        {h ? (
          <BulletGraph label="Calendar subsystem · hours since last good cycle" value={calFreshH}
            max={24} target={0} bands={lower(6, 12, 24)} unit=" h" format={hrs}
            sub={h.calendarFreshness?.toISOString() || "Sheet1!AA1 unreadable"} />
        ) : <CalLoading err={hErr} />}
        {/* Source feed: HISTORY.CSV's OWN age. Bills are bulk re-derived from this blob, so they can't go
            stale one-at-a-time — they go stale TOGETHER when LIS stops refreshing the blob, which the two
            cycle clocks above can't see (a green cycle over a stale source). This is the grounded form of
            "per-bill freshness." Only shown when the worker reported a Last-Modified (>= 0). */}
        {/* Render only when we can MEANINGFULLY interpret the blob age — i.e., the session state is KNOWN.
            When sessionActive is null (Sheet1!S1 unreadable) the gauge's meaning is undetermined and an
            all-good band would be a false-green (BulletGraph has no neutral tone), so hide it — never pretend
            (the value is uninterpretable without session context anyway). [CodeRabbit + Qodo #182] */}
        {h && blobAgeKnown && sessionActive !== null && (
          <BulletGraph label="Source feed · HISTORY.CSV blob age (hours since LIS refreshed it)" value={blobAgeH}
            max={48} target={0} bands={blobAgeBands} unit=" h" format={hrs}
            spark={spark("history_blob_age_min").filter((v) => v >= 0)}
            sub={sessionActive
              ? "in-session: stale here while the cycle clocks are green = LIS stopped feeding us (provisional bands; refine once the blob's refresh cadence is measured)"
              : "off-season: HISTORY.CSV legitimately doesn't change (no new actions) — shown for reference, not alarmed"} />
        )}
      </div>
      {/* Feed-skew: the gap BETWEEN the two clocks. Small = the subsystems agree on "now"; large = one feed
          lagged the other and the picture is momentarily inconsistent. Only shown when both clocks are known. */}
      {Number.isFinite(feedSkewH) && (
        <div className={`hl-skew ${feedSkewH <= SKEW_OK_H ? "ok" : feedSkewH <= SKEW_WARN_H ? "warn" : "danger"}`}>
          <span className="hl-skewdot" aria-hidden="true" />
          Feed-skew · the two clocks are <strong>{hrs(feedSkewH)} h</strong> apart
          <span className="muted"> — {feedSkewH <= SKEW_OK_H ? "in sync (the bill backend refreshes every 6h)" : feedSkewH <= SKEW_WARN_H ? "the bill backend is overdue for its 6h refresh" : "a subsystem has stalled — one clock is far behind the other"}</span>
        </div>
      )}

      <h2 className="h">Pipeline health</h2>
      <div className="hl-gauges">
        {h ? (
          <BulletGraph label="Write-time invariant violations" value={violations ?? 0}
            max={60} target={0} bands={lower(0.5, 49, 60)} spark={spark("invariant_violations")}
            sub="rows that failed a schema/Origin invariant at write (breaker trips at ≥50)" />
        ) : <CalLoading err={hErr} />}
        {c?.outcome_keyword_mismatch_rate != null && (
          <BulletGraph label="Outcome drift · keyword↔structural mismatch" value={driftPct}
            max={2} target={0} bands={lower(0.1, 1, 2)} unit="%" format={oneDp}
            sub="self-calibrating reconciliation vs LIS's own flags (steady ≈ 0.03%)" />
        )}
        {h && total > 0 && (
          <BulletGraph label="Unclassified share · router returned blank" value={unclassPct}
            max={25} target={0} bands={lower(8, 15, 25)} unit="%" format={oneDp}
            spark={hist ? seriesForPct(hist, "legevent_route_blank", "total_processed") : []}
            sub={`${(m.legevent_route_blank ?? 0).toLocaleString()} of ${total.toLocaleString()} rows (floor/skeleton rows are legitimately blank)`} />
        )}
        {c && (
          <BulletGraph label="Patron coverage" value={patronPct}
            max={100} target={100} bands={higher(98, 99.99, 100)} unit="%" format={oneDp}
            sub={`${(c.patron_present ?? 0).toLocaleString()} of ${written.toLocaleString()} bills with a chief patron`} />
        )}
      </div>

      {/* ── Alert feed: the operator's "needs a human" list (Standard #8). When the Metrics_History trend
            store is populated, show the rolling HISTORY (distinct alerts + how often + last-seen); until then,
            fall back to the latest cycle's live alerts from Sheet1. ── */}
      <h2 className="h" id="hl-sec-alerts" style={{ scrollMarginTop: 84 }}>Alerts {h && <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· {alertHistory ? "recent history — what has fired and how often" : "latest from the calendar worker"}</span>}</h2>
      {!h ? <CalLoading err={hErr} /> : alertHistory ? (
        alertHistory.length === 0 ? (
          <p className="muted" style={{ marginBottom: 18 }}>No alerts in the recent window — the worker is running clean.</p>
        ) : (
          <div className="panel" style={{ marginBottom: 18 }}>
            {alertHistory.map((a) => a.kind === "group" ? (
              <details key={`g|${a.severity}|${a.category}`} className="hl-alertgroup">
                <summary className="hl-alert">
                  <span className={`hl-sev ${a.severity.toLowerCase()}`}>{a.severity}</span>
                  {a.category && <span className="hl-cat">{a.category}</span>}
                  <span className="hl-amsg"><strong>{a.distinct.toLocaleString()}</strong> distinct alerts (routine aggregate — expand to inspect)</span>
                  <span className="hl-acount" title={`${a.totalCount} total occurrences across ${a.distinct} distinct alerts`}>×{a.totalCount.toLocaleString()}</span>
                  <span className="hl-adate">{agoText(new Date(a.lastTs))}</span>
                </summary>
                <div style={{ paddingLeft: 8 }}>
                  {a.items.slice(0, 100).map((d) => (
                    <div key={`${d.severity}|${d.category}|${d.message}`} className="hl-alert">
                      <span className="hl-amsg">{d.message}</span>
                      {d.count > 1 && <span className="hl-acount" title={`fired in ${d.count} cycles`}>×{d.count}</span>}
                      <span className="hl-adate">{agoText(new Date(d.lastTs))}</span>
                    </div>
                  ))}
                  {a.items.length > 100 && <div className="muted" style={{ padding: "4px 0" }}>…and {(a.items.length - 100).toLocaleString()} more</div>}
                </div>
              </details>
            ) : (
              <div key={`s|${a.severity}|${a.category}|${a.message}`} className="hl-alert">
                <span className={`hl-sev ${a.severity.toLowerCase()}`}>{a.severity}</span>
                {a.category && <span className="hl-cat">{a.category}</span>}
                <span className="hl-amsg">{a.message}</span>
                {a.count > 1 && <span className="hl-acount" title={`fired in ${a.count} cycles`}>×{a.count}</span>}
                <span className="hl-adate">{agoText(new Date(a.lastTs))}</span>
              </div>
            ))}
          </div>
        )
      ) : h.alerts.length === 0 ? (
        <p className="muted" style={{ marginBottom: 18 }}>No active alerts — the worker is running clean.</p>
      ) : (
        <div className="panel" style={{ marginBottom: 18 }}>
          {h.alerts.map((a, i) => (
            <div key={i} className="hl-alert">
              <span className={`hl-sev ${a.severity.toLowerCase()}`}>{a.severity}</span>
              {a.category && <span className="hl-cat">{a.category}</span>}
              <span className="hl-amsg">{a.message}</span>
              {a.date && <span className="hl-adate">{a.date}</span>}
            </div>
          ))}
        </div>
      )}

      {/* ── Structural classification distribution (drift in the router is visible) ── */}
      {h && total > 0 && (
        <>
          <h2 className="h">Where the rows went · structural router</h2>
          <div className="hl-dist panel" style={{ marginBottom: 18 }}>
            {([
              ["meeting", m.legevent_route_meeting ?? 0, "var(--ok)"],
              ["admin", m.legevent_route_admin ?? 0, "var(--ink-soft)"],
              ["executive", m.legevent_route_executive ?? 0, "var(--o-await)"],
              ["blank", m.legevent_route_blank ?? 0, "var(--ink-faint)"],
            ] as const).map(([k, v, col]) => (
              <div key={k} className="hl-distrow">
                <span className="hl-distk">{k}</span>
                <span className="hl-distbar"><span style={{ width: `${(100 * v) / total}%`, background: col }} /></span>
                <span className="hl-distv">{v.toLocaleString()} · {((100 * v) / total).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Raw counters for deep inspection ── */}
      {h && Object.keys(m).length > 0 && (
        <details className="hl-raw">
          <summary>Raw SYSTEM_METRICS · {Object.keys(m).length} counters</summary>
          <div className="hl-rawgrid">
            {Object.entries(m).map(([k, v]) => (
              <div key={k} className="hl-rawcell"><span className="hl-rawk">{k}</span><span className="hl-rawv">{v.toLocaleString()}</span></div>
            ))}
          </div>
        </details>
      )}

      <p className="muted hl-foot">
        Operator view (vision §3f) — the diagnostics the workers already emit, read live from the sheet.
        Bands are calibrated from the worker's breaker thresholds + steady state, not magic numbers.
        {hErr && <span style={{ color: "var(--stale)" }}> · calendar signals unavailable: {hErr}</span>}
      </p>
    </div>
  );
}

function CalLoading({ err }: { err: string | null }) {
  return err
    ? <p className="muted" style={{ color: "var(--stale)" }}>Calendar signals unavailable: {err}</p>
    : <p className="muted">Loading calendar-subsystem signals…</p>;
}
