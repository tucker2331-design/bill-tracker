import { useEffect, useState } from "react";
import type { Completeness } from "../data/types";
import { BulletGraph } from "../components/BulletGraph";
import { bandTone, type Band } from "../components/bands";
import { HealthVitals, type Vital, type VitalSeg, type VitalVerify } from "../components/HealthVitals";
import { loadHealth, type HealthData, type HealthAlert } from "../data/health";
import { loadVerification, type GuardRun, type GuardState } from "../data/verification";
import { loadHistory, seriesFor, seriesForPct, type HistoryData, type AlertSource } from "../data/history";
import { loadCounter, type CounterState } from "../data/incidents";

// Alert presentation (owner 2026-07-07: the feed "needs real thinking and fixing" + "colored boxes scream
// AI"). See docs/design/dashboard_and_visual_language.md. Severity now rides a small status DOT, not a
// saturated pill; the plain word is kept only for the hover title / screen readers.
const SEV_WORD: Record<string, string> = { CRITICAL: "Needs a look", WARN: "Heads up", INFO: "FYI" };
const sevWord = (s: string) => SEV_WORD[(s || "").toUpperCase()] ?? s;
const sevDot = (s: string) => (s === "CRITICAL" ? "crit" : s === "WARN" ? "warn" : s === "INFO" ? "info" : "unknown");

// Strip the internal debug tail a worker alert sometimes carries (Python reprs / tuple dumps) so the face
// shows a plain sentence, never internal representation (docs/design Part 1 §6).
const cleanMessage = (msg: string) =>
  msg.replace(/\s*(\(debug:|only-full=\[|only-in-full|only-date=|only-bill=|only-incr=).*/is, "").trim();

// Collapse a message to a stable CONDITION stem for grouping: drop volatile dates/numbers/ids + the debug
// tail so recurring firings of the SAME condition ("6 blank rows on 2026-01-29…", "5 … on 2026-02-03…", the
// per-bill "Malformed row for SB587…") group into ONE row with a count — which is what lets a condition
// self-clear cleanly instead of spawning a fresh "active" line every cycle its count changes.
const conditionStem = (msg: string) =>
  cleanMessage(msg)
    .replace(/\d{4}-\d{2}-\d{2}/g, "#date")
    .replace(/[0-9][0-9,.]*/g, "#")   // no \b: a letter→digit seam isn't a word boundary, so \bSB587 never matched (Gemini #209)
    .replace(/\s+/g, " ")
    .toLowerCase()
    .slice(0, 120);

// One recurring CONDITION, grouped from many raw firings. lastTs drives liveness (active vs self-cleared);
// count is how many cycles it fired; message is the newest (cleaned) representative text.
type Cond = { key: string; severity: string; category: string; message: string; count: number; firstTs: number; lastTs: number; source: AlertSource };
interface AlertModel { latestCycleTs: number; active: Cond[]; resolved: Cond[]; needsLook: Cond[]; notes: Cond[]; }

function groupConditions(rows: { severity: string; category: string; message: string; ts: number; source: AlertSource }[]): Cond[] {
  const byKey = new Map<string, Cond>();
  for (const a of rows) {
    // Source is part of the identity: the same wording from two workers is two conditions, judged against
    // two different cadences (see AlertSource in data/history.ts).
    const key = `${a.source}|${a.severity}|${a.category}|${conditionStem(a.message)}`;
    const e = byKey.get(key);
    if (e) {
      e.count++;
      e.firstTs = Math.min(e.firstTs, a.ts);
      if (a.ts >= e.lastTs) { e.lastTs = a.ts; e.message = cleanMessage(a.message); }
    } else {
      byKey.set(key, { key, severity: a.severity, category: a.category, message: cleanMessage(a.message), count: 1, firstTs: a.ts, lastTs: a.ts, source: a.source });
    }
  }
  return [...byKey.values()];
}
const SEV_RANK = (s: string) => (s === "CRITICAL" ? 0 : s === "WARN" ? 1 : s === "INFO" ? 2 : 3);

// Human names for the worker's error categories (Standard #4 vocabulary) — the raw ALL_CAPS token reads as
// internal jargon on the lobbyist-facing page.
const CATEGORY_LABEL: Record<string, string> = {
  TIMING_LAG: "Timing lag (routine deferrals)",
  DATA_ANOMALY: "Upstream data quirk",
  API_FAILURE: "Connection / cadence",
  PARENT_CHILD: "Parent–child linkage",
  COMMITTEE_DRIFT: "Committee drift",
  UNKNOWN: "Needs review",
  UNCATEGORIZED: "Other",
};
const catLabel = (c: string) => CATEGORY_LABEL[(c || "").toUpperCase()] ?? (c || "Other");

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
  // The days-clean counter — the visible artifact of the trust promise. Optional chrome: a failed load
  // leaves the line absent rather than blanking the tab or showing a number we cannot support.
  const [counter, setCounter] = useState<CounterState | null>(null);
  useEffect(() => {
    let alive = true;
    loadCounter().then((c) => alive && setCounter(c)).catch(() => alive && setCounter(null));
    return () => { alive = false; };
  }, []);

  if (!completeness && !h && !hErr) return <p className="center-msg">Loading operator health…</p>;

  // ── Bill-backend signals (props) ──
  const c = completeness;
  const universe = c?.universe_count ?? 0;
  const written = c?.records_written ?? 0;
  const anomalies = c?.in_history_not_in_universe?.length ?? 0;
  const completePct = universe > 0 ? (100 * written) / universe : 0;
  const patronPct = written > 0 ? (100 * (c?.patron_present ?? 0)) / written : 0;
  const driftPct = (c?.outcome_keyword_mismatch_rate ?? 0) * 100;
  const unverifiedTerminal = c?.outcome_unverified_terminal ?? 0;
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

  // ── Alert MODEL: state, not stream (docs/design/dashboard_and_visual_language.md). Metrics_History is an
  // append-only per-cycle log; a real dashboard shows what's TRUE NOW. We group raw firings into CONDITIONS
  // (by severity+category+normalized stem) and derive liveness from the latest cycle: a condition is ACTIVE
  // iff it fired in the most recent cycle, else it has SELF-RESOLVED and moves to the collapsed history.
  // This is the self-clearing the owner asked for — no worker change, no human "acknowledge". ──
  const alertModel: AlertModel | null = (() => {
    if (!hist?.available) return null;
    // The newest cycle in the store (system_metrics + system_alert rows share the cycle timestamp).
    const latestCycleTs = Math.max(0, ...hist.metricSeries.map((p) => p.ts), ...hist.alerts.map((a) => a.ts));
    const ACTIVE_TOL_MS = 6 * 60 * 1000; // "this cycle" window — well under the ~15-min in-window cadence
    const conds = groupConditions(hist.alerts);
    const byActivity = (a: Cond, b: Cond) => SEV_RANK(a.severity) - SEV_RANK(b.severity) || b.lastTs - a.lastTs;
    // Judge each condition against the clock of the worker that RAISED it (W0d). The two workers run on
    // different cadences, so a single global "latest cycle" would mark every bill-worker alert resolved as
    // soon as the calendar worker ticked — the alert would appear and vanish without ever being actionable.
    // Fall back to the global timestamp when that worker has no heartbeat yet (pre-first-run), which is the
    // old behaviour and never fabricates freshness.
    const cycleFor = (c: Cond) => hist.cycleTs[c.source] || latestCycleTs;
    const isActive = (c: Cond) => c.lastTs >= cycleFor(c) - ACTIVE_TOL_MS;
    const active = conds.filter(isActive).sort(byActivity);
    const resolved = conds.filter((c) => !isActive(c)).sort((a, b) => b.lastTs - a.lastTs);
    // "Needs a look" = only genuinely actionable, currently-live signals. A benign INFO note (blank upstream
    // rows, an overnight cadence gap) is NOT a call to action — it shows quietly, never in the verdict count.
    const needsLook = active.filter((c) => c.severity === "CRITICAL" || c.severity === "WARN");
    const notes = active.filter((c) => c.severity === "INFO" || c.severity === "UNKNOWN");
    return { latestCycleTs, active, resolved, needsLook, notes };
  })();

  // ── At-a-glance vitals: roll the gauges below into four category rings. Each segment's tone comes from
  // `bandTone` over the SAME bands the matching gauge uses, so the donut and the detail never disagree; a
  // segment whose backend payload is absent is "unknown" (grey), never a false green. ──
  const sv = (label: string, value: number, bands: Band[], known: boolean, anchor?: string): VitalSeg =>
    ({ label, tone: known ? bandTone(value, bands) : "unknown", anchor });
  // The ring reflects the SAME currently-active conditions the feed shows (self-cleared ones don't count).
  // Prefer the history-derived model; fall back to the latest cycle's live alerts when the trend store isn't
  // up yet. Only actionable CRITICAL/WARN move the ring — a benign INFO note never turns Stability amber.
  const critCount = alertModel ? alertModel.needsLook.filter((c) => c.severity === "CRITICAL").length
    : h ? h.alerts.filter((a) => a.severity === "CRITICAL").length : 0;
  const warnCount = alertModel ? alertModel.needsLook.filter((c) => c.severity === "WARN").length
    : h ? h.alerts.filter((a) => a.severity === "WARN").length : 0;

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
      sv("Section-9 · meeting actions without a time", section9 ?? 0, lower(0.5, 25, 50), section9 != null, "hl-m-section9"),
      // OUR accuracy, not LIS's internal consistency. `outcome_keyword_mismatch_rate` used to sit here and
      // is what turned this ring RED on 2026-07-25 while every published value was correct: it measures
      // LIS's status string disagreeing with LIS's own flags, and we publish the flag. It now renders as an
      // upstream observation below (no danger band, no ring). What belongs here is a value WE got wrong or
      // cannot vouch for: `impeached`, and bills whose own status says SETTLED yet carry no structural flag
      // (no legitimate steady state → an absolute floor; the in-progress population is deliberately absent).
      sv("Outcomes published wrong", c?.outcome_impeached ?? 0, lower(0.5, 1, 5), c?.outcome_impeached != null, "hl-m-impeached"),
      sv("Settled bills with no structural flag", unverifiedTerminal, lower(0.5, 5, 25), c?.outcome_unverified_terminal != null, "hl-m-unverified"),
    ], verify: vitalVerify(["accuracy_sentinel.yml", "legevent_reconcile.yml"]), verifyApplies: true, anchor: "hl-sec-accuracy" },
    { name: "Completeness", segs: [
      sv("Bill completeness · records vs universe", completePct, higher(98, 99.99, 100), !!c && universe > 0, "hl-m-complete"),
      sv("History-vs-universe anomalies", anomalies, lower(0.5, 5, 20), !!c, "hl-m-anomalies"),
      sv("Patron coverage", patronPct, higher(98, 99.99, 100), !!c && written > 0, "hl-m-patron"),
      sv("Unclassified share · router blank", unclassPct, lower(8, 15, 25), !!h && total > 0, "hl-m-unclass"),
    ], verify: vitalVerify(["completeness_tripwire.yml"]), verifyApplies: true, anchor: "hl-sec-accuracy" },
    { name: "Freshness", segs: [
      sv("Bill backend clock", billFreshH, lower(6, 12, 24), !!dataAsOf),
      sv("Calendar clock", calFreshH, lower(6, 12, 24), !!h?.calendarFreshness),
    ], verifyApplies: false, anchor: "hl-sec-freshness" },
    { name: "Stability", segs: [
      { label: "Circuit breaker", tone: !h ? "unknown" : breakerOk ? "good" : "danger", anchor: "hl-sec-status" },
      sv("Write-time invariant violations", violations ?? 0, lower(0.5, 49, 60), violations != null, "hl-m-invariants"),
      { label: "Active alerts", tone: !h ? "unknown" : critCount ? "danger" : warnCount ? "warn" : "good" },
      // THE INCIDENT LEDGER IS A RING INPUT (owner, 2026-07-28). Before this, the rings were computed purely
      // from live metrics and knew nothing about the ledger, so the page could show four green rings directly
      // above "an incident is OPEN right now". The owner's argument is the correct one: an incident severe
      // enough to reset the days-clean clock is BY DEFINITION something a ring should not call healthy.
      // Two independent verdicts about the same question will eventually contradict; the fix is to make one
      // an input to the other rather than to hope they agree.
      //
      // FAIL-CLOSED on all three non-clean states -- open, unreadable, and unseeded are each "we cannot say
      // this is clean", and none of them may render green.
      {
        label: "Incident ledger",
        tone: !counter ? "unknown"
          : counter.openNow.length > 0 ? "danger"
          : counter.wrongSheet ? "unknown"
          : !counter.available ? "unknown"
          : "good",
      },
    ], verify: vitalVerify(["sustainability_audit.yml"]), verifyApplies: true, anchor: "hl-sec-alerts" },
  ];

  return (
    <div>
      <h2 className="h">At a glance</h2>
      {/* The trust counter. Rules from docs/architecture/incident_counter.md, and each is load-bearing:
          · the DENOMINATOR always rides along — "47 days clean" alone cannot be judged (Standard #7)
          · an OPEN incident makes it red and says so; the clock reads from that incident's start
          · an unseeded ledger says exactly that, never a reassuring 0 ("allowed not to know, never pretend")
          · a stale/absent fire drill is surfaced — an untested alarm is not a working alarm */}
      {counter?.available && (
        <p className="muted" style={{ marginTop: -6, marginBottom: 14 }}>
          {counter.openNow.length > 0 ? (
            <span style={{ color: "var(--stale)", fontWeight: 600 }}>
              {/* Cap the list. On 2026-07-28 a wrong-sheet read produced ~3,645 "classes" and this line
                  rendered every one of them, burying the actual message. A count carries the signal; the
                  first few carry the detail. */}
              ▲ {counter.openNow.length === 1 ? "An incident is" : `${counter.openNow.length} incidents are`} OPEN
              right now ({counter.openNow.slice(0, 3).join(", ")}
              {counter.openNow.length > 3 && ` +${counter.openNow.length - 3} more`}) — the days-clean clock has reset.
            </span>
          ) : (
            <>
              <b style={{ color: "var(--ink)" }}>{counter.daysClean ?? "—"} days</b> since a data incident
              {counter.monitoringDays != null && <> · monitoring for <b style={{ color: "var(--ink)" }}>{counter.monitoringDays}</b> days</>}
              {counter.incidentsEver > 0 && <> · {counter.incidentsEver} recorded ever</>}
            </>
          )}
          {counter.lastDrillDays != null
            ? <> · last alarm test {counter.lastDrillDays}d ago</>
            : <> · <span title="A fire drill exercises the real write path. Without one, the alarm is untested.">alarm never tested</span></>}
          {counter.malformedRows > 0 && (
            <> · <span style={{ color: "var(--stale)" }}>⚠ {counter.malformedRows} unreadable row(s) — an incident could be hidden</span></>
          )}
        </p>
      )}
      {counter?.wrongSheet && (
        <p className="muted" style={{ marginTop: -6, marginBottom: 14 }}>
          <span style={{ color: "var(--stale)", fontWeight: 600 }}>
            ▲ The incident ledger could not be read — the response was not the Incident_Log tab.
          </span>{" "}
          Treat the days-clean figure as unknown, not clean. (gviz answers a missing tab with the first
          sheet, HTTP 200, so this is a real defect rather than an empty state.)
        </p>
      )}
      {counter && !counter.available && !counter.wrongSheet && (
        <p className="muted" style={{ marginTop: -6, marginBottom: 14 }}>
          Days-clean counter not yet seeded — the ledger has no epoch, so there is no honest number to show.
        </p>
      )}
      <HealthVitals vitals={vitals} />

      {/* ── System status: the breaker + the TWO freshnesses (different workers) ── */}
      <div className="hl-status" id="hl-sec-status">
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

      <h2 className="h" id="hl-sec-accuracy">Accuracy &amp; completeness — the lobbyist-facing guarantees</h2>
      <div className="hl-gauges">
        {h ? (
          <BulletGraph id="hl-m-section9" label="Section-9 accuracy · meeting actions without a time" value={section9 ?? 0}
            max={50} target={0} bands={lower(0.5, 25, 50)} spark={spark("meeting_unsourced")}
            sub="0 = every meeting action has a time (the project goal)" />
        ) : <CalLoading err={hErr} />}
        {/* Bill-backend gauges only render when the completeness payload is present — a null payload must NOT
            display as a real 0% / 0 (that would read as a false danger; "allowed not to know, never pretend"). */}
        {c ? (<>
          <BulletGraph id="hl-m-complete" label="Bill completeness · records written vs LIS universe" value={completePct}
            max={100} target={100} bands={higher(98, 99.99, 100)} unit="%" format={oneDp}
            sub={`${written.toLocaleString()} of ${universe.toLocaleString()} bills${anomalies ? ` · ${anomalies} in-history-not-in-universe` : ""}`} />
          <BulletGraph id="hl-m-impeached" label="Outcomes published wrong" value={c.outcome_impeached ?? 0}
            max={5} target={0} bands={lower(0.5, 1, 5)}
            sub="values we published that a later check proved incorrect — the only thing that turns this ring red" />
          <BulletGraph id="hl-m-unverified" label="Settled bills with no structural flag" value={unverifiedTerminal}
            max={25} target={0} bands={lower(0.5, 5, 25)}
            sub={`of ${(c.outcome_unverified ?? 0).toLocaleString()} flagless bills; the other ${(c.outcome_unverified_absent ?? 0).toLocaleString()} are still in progress, so no flag is owed yet`} />
          <BulletGraph id="hl-m-anomalies" label="History-vs-universe anomalies" value={anomalies}
            max={20} target={0} bands={lower(0.5, 5, 20)} sub="bills seen in HISTORY but absent from the universe (scariest silent gap)" />
        </>) : <p className="muted">Bill-backend signals unavailable (no completeness payload in Bill_Tracker R1).</p>}
      </div>

      <h2 className="h" id="hl-sec-freshness">Freshness — two workers, two clocks</h2>
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
          <BulletGraph id="hl-m-invariants" label="Write-time invariant violations" value={violations ?? 0}
            max={60} target={0} bands={lower(0.5, 49, 60)} spark={spark("invariant_violations")}
            sub="rows that failed a schema/Origin invariant at write (breaker trips at ≥50)" />
        ) : <CalLoading err={hErr} />}
        {c?.outcome_keyword_mismatch_rate != null && (
          // UPSTREAM observation, deliberately NOT an accuracy alarm: this is LIS's status string
          // disagreeing with LIS's own flags, and we publish the flag. On 2026-07-25 LIS batch-flagged
          // carryover without updating its strings and this read 12.2% — every published value correct.
          // Flat-good bands so it can be watched without ever colouring a verdict.
          <BulletGraph id="hl-m-drift" label="Upstream: LIS status text vs LIS's own flags" value={driftPct}
            max={25} target={0} bands={[{ upto: 25, tone: "good" }]} unit="%" format={oneDp}
            sub={`${(c.outcome_keyword_mismatches ?? 0).toLocaleString()} bills where LIS's two fields disagree — we publish the flag, so nothing we show is affected`} />
        )}
        {h && total > 0 && (
          <BulletGraph id="hl-m-unclass" label="Unclassified share · router returned blank" value={unclassPct}
            max={25} target={0} bands={lower(8, 15, 25)} unit="%" format={oneDp}
            spark={hist ? seriesForPct(hist, "legevent_route_blank", "total_processed") : []}
            sub={`${(m.legevent_route_blank ?? 0).toLocaleString()} of ${total.toLocaleString()} rows (floor/skeleton rows are legitimately blank)`} />
        )}
        {c && (
          <BulletGraph id="hl-m-patron" label="Patron coverage" value={patronPct}
            max={100} target={100} bands={higher(98, 99.99, 100)} unit="%" format={oneDp}
            sub={`${(c.patron_present ?? 0).toLocaleString()} of ${written.toLocaleString()} bills with a chief patron`} />
        )}
      </div>

      {/* ── Alerts: STATE, not stream. A verdict line answers "do I need to do anything?", then only the
            currently-active conditions, then a collapsed self-cleared history. See
            docs/design/dashboard_and_visual_language.md. ── */}
      <h2 className="h" id="hl-sec-alerts">Alerts</h2>
      {/* The trend store decides whether a condition is still ACTIVE, so an incomplete one can make a live
          alert look self-resolved. If any row was undateable, say so here rather than presenting a feed we
          know is partial as though it were whole (Standard #9). */}
      {hist && hist.malformedRows > 0 && (
        <p className="muted" style={{ marginTop: 0 }}>
          ⚠ {hist.malformedRows} unreadable row(s) in the alert history — this feed may be incomplete, so a
          condition shown as resolved could still be active.
        </p>
      )}
      {!h ? <CalLoading err={hErr} /> : (
        <div style={{ marginBottom: 18 }}>
          <AlertsPanel model={alertModel} liveAlerts={h.alerts} />
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

// One active condition row: a small dot carries severity, the sentence stays neutral, meta recedes right.
function AlertRow({ c }: { c: Cond }) {
  return (
    <div className="hl-arow">
      <span className={`hl-adot ${sevDot(c.severity)}`} aria-hidden="true" title={sevWord(c.severity)} />
      <span className="hl-amsg">{c.message}</span>
      <span className="hl-ameta">
        {c.count > 1 && <span className="hl-acount" title={`fired in ${c.count.toLocaleString()} cycles`}>{c.count.toLocaleString()}×</span>}
        <span className="hl-awhen">{agoText(new Date(c.lastTs))}</span>
      </span>
    </div>
  );
}

// Self-cleared history, rolled up COARSELY by category so it reads as a calm summary ("Timing lag — 300
// routine deferrals, all cleared") instead of a wall of 300 rows. Collapsed by default. This is the "it
// resolved itself" record without the noise — the abundance the owner objected to.
function ClearedHistory({ resolved }: { resolved: Cond[] }) {
  type CatRoll = { category: string; worst: string; distinct: number; firings: number; lastTs: number };
  const byCat = new Map<string, CatRoll>();
  for (const c of resolved) {
    const e = byCat.get(c.category);
    if (e) {
      e.distinct++; e.firings += c.count; e.lastTs = Math.max(e.lastTs, c.lastTs);
      if (SEV_RANK(c.severity) < SEV_RANK(e.worst)) e.worst = c.severity;
    } else {
      byCat.set(c.category, { category: c.category, worst: c.severity, distinct: 1, firings: c.count, lastTs: c.lastTs });
    }
  }
  const cats = [...byCat.values()].sort((a, b) => b.lastTs - a.lastTs);
  const mostRecent = Math.max(...resolved.map((c) => c.lastTs));
  return (
    <details className="hl-cleared">
      <summary>
        {resolved.length.toLocaleString()} {resolved.length === 1 ? "condition" : "conditions"} cleared themselves recently
        <span className="muted"> · most recent {agoText(new Date(mostRecent))}</span>
      </summary>
      <div>
        {cats.map((g) => (
          <div className="hl-arow resolved" key={g.category}>
            <span className={`hl-adot ${sevDot(g.worst)}`} aria-hidden="true" />
            <span className="hl-amsg">{catLabel(g.category)}<span className="muted"> — {g.distinct.toLocaleString()} distinct, {g.firings.toLocaleString()}× total</span></span>
            <span className="hl-ameta"><span className="hl-awhen">last seen {agoText(new Date(g.lastTs))}</span></span>
          </div>
        ))}
      </div>
    </details>
  );
}

// The Alerts panel: a verdict line, then only currently-active conditions, then a collapsed self-cleared
// history. Prefers the history-derived model (real self-clearing); falls back to the latest cycle's live
// alerts (grouped the same way) when the trend store isn't up yet. See docs/design.
function AlertsPanel({ model, liveAlerts }: { model: AlertModel | null; liveAlerts: HealthAlert[] }) {
  const [nowMs] = useState(() => Date.now()); // stable per mount — a live alert with an unparseable date reads "just now"
  let needsLook: Cond[], notes: Cond[], resolved: Cond[];
  if (model) {
    ({ needsLook, notes, resolved } = model);
  } else {
    // `liveAlerts` is the calendar worker's own SYSTEM_ALERT rows from Sheet1 (see data/health.ts) — that
    // tab has exactly one writer, so tagging them "calendar" is a structural fact, not a guess. The bill
    // worker's alerts never reach this fallback path: they arrive only via Metrics_History, i.e. the
    // `model` branch above (W0d). Without this the two workers' alerts would share one cadence judgement.
    const rows = liveAlerts.map((a) => ({ severity: a.severity, category: a.category, message: a.message, ts: Date.parse(a.date) || nowMs, source: "calendar" as AlertSource }));
    const conds = groupConditions(rows).sort((a, b) => SEV_RANK(a.severity) - SEV_RANK(b.severity) || b.lastTs - a.lastTs);
    needsLook = conds.filter((c) => c.severity === "CRITICAL" || c.severity === "WARN");
    notes = conds.filter((c) => c.severity === "INFO" || c.severity === "UNKNOWN");
    resolved = [];
  }
  const attention = needsLook.length > 0;
  const hasCrit = needsLook.some((c) => c.severity === "CRITICAL");
  const verdictClass = attention ? (hasCrit ? "attention crit" : "attention") : "clear";

  return (
    <div className="panel hl-alerts">
      <div className={`hl-verdict ${verdictClass}`}>
        <span className="hl-vdot" aria-hidden="true" />
        <span className="hl-vtext">
          {attention
            ? `${needsLook.length} ${needsLook.length === 1 ? "condition needs" : "conditions need"} a look`
            : "All clear — nothing needs your attention"}
        </span>
        {notes.length > 0 && <span className="hl-vnote">{notes.length} routine {notes.length === 1 ? "note" : "notes"}</span>}
      </div>

      {needsLook.map((c) => <AlertRow key={c.key} c={c} />)}

      {notes.length > 0 && (
        <div className="hl-notes">
          {notes.map((c) => <AlertRow key={c.key} c={c} />)}
        </div>
      )}

      {resolved.length > 0 && <ClearedHistory resolved={resolved} />}
    </div>
  );
}
