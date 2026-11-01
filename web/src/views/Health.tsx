// Health (v9, owner-approved 2026-10-27; built 2026-10-29). Visual-first, and audited against docs/design:
//  * ONE instrument list (data/health_rules.ts) feeds the rings, the problems table and the dials — the overview
//    cannot disagree with the detail.
//  * BINARY (P25a, owner "no yellow"): grey = verified clean, RED = anything else — wrong, unconfirmed, unreadable.
//    WHY it is red is a small-caps text field, never a softer colour. Unconfirmed is red, never grey.
//  * P26: counts as "k of n"; a coverage metric is shown as the count of what is MISSING.
//  * P24/P25: problems are rows of structural fields (check, state, since, affects, published values wrong, fix).
//  * The freshness limits follow each worker's observed write rhythm (Metrics_History heartbeats), not a fixed 6 h.
import { SOURCE } from "../config";
import { STATE } from "../states";
import { loadCalendarFreshness } from "../data/calendar";
import { useEffect, useMemo, useState } from "react";
import type { Completeness } from "../data/types";
import { loadHealth, type HealthData, type HealthAlert } from "../data/health";
import { loadVerification, type GuardRun } from "../data/verification";
import { loadHistory, type HistoryData, type AlertSource } from "../data/history";
import { loadCounter, type CounterState } from "../data/incidents";
import { loadGuardStatus, loadRuns, GUARD_OK, type GuardLoad, type RunMark } from "../data/guards";
import {
  isClean, rings, dialPos, rhythmLimitHours, verdictOf, type Instrument, type Impeach, type RingExtra, type Category,
} from "../data/health_rules";

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

const hoursSince = (d: Date | null) => (d ? (Date.now() - d.getTime()) / 3.6e6 : NaN);
const agoText = (d: Date | null) => {
  if (!d) return "";
  const h = (Date.now() - d.getTime()) / 3.6e6;
  if (h < 1) return "just now";
  if (h < 24) return `${Math.round(h)}h ago`;
  return `${Math.round(h / 24)}d ago`;
};
const n = (v: number) => v.toLocaleString();
const shortDay = (d: Date | null) => d ? d.toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "—";
// Guard_Status is rewritten every 6 h; three missed runs (with GitHub's schedule slippage) means the watcher itself
// has stopped — a problem in its own right, since nothing else would notice.
const GUARD_STALE_H = 18;
// Which independent guard checks each category ("outside check"); Freshness has none.
const OUTSIDE: Partial<Record<Category, string>> = {
  Accuracy: "accuracy_sentinel.yml", Completeness: "completeness_tripwire.yml", Stability: "sustainability_audit.yml",
};

interface Problem { check: string; state: string; since: string; affects: string; wrong: Impeach; fix: { text: string; url: string } | null }

// One Health screen for every state (owner 2026-11-01: "the designed VA Health screen, fed by PA's own checks").
// A state whose health is "intake" has no Virginia guard jobs, incident ledger, circuit breaker or calendar-subsystem
// counters, so those parts are not read and not drawn (hidden, never shown empty). Its instruments are its own job's
// checks (STATE.intakeChecks) + completeness + both data ages; its alerts and rhythm come from the same
// Metrics_History heartbeat rows Virginia's bill job writes.
export function Health({ completeness, dataAsOf }: { completeness: Completeness | null; dataAsOf: Date | null }) {
  const intake = STATE.features.health === "intake";
  const [h, setH] = useState<HealthData | null>(null);
  const [hErr, setHErr] = useState<string | null>(null);
  const [guards, setGuards] = useState<GuardRun[] | null>(null);
  const [hist, setHist] = useState<HistoryData | null>(null);
  const [counter, setCounter] = useState<CounterState | null>(null);
  const [gs, setGs] = useState<GuardLoad | null>(null);
  const [runs, setRuns] = useState<Record<string, RunMark[] | null>>({});
  const [calAsOf, setCalAsOf] = useState<Date | null | undefined>(undefined);
  useEffect(() => {
    let alive = true;
    if (intake) {
      loadHistory().then((d) => alive && setHist(d)).catch(() => alive && setHist(null));
      loadCalendarFreshness().then((d) => alive && setCalAsOf(d)).catch(() => alive && setCalAsOf(null));
      return () => { alive = false; };
    }
    loadHealth().then((d) => alive && setH(d)).catch((e) => alive && setHErr(String(e?.message || e)));
    loadVerification().then((d) => alive && setGuards(d)).catch(() => alive && setGuards([]));
    loadHistory().then((d) => alive && setHist(d)).catch(() => alive && setHist(null));
    loadCounter().then((c) => alive && setCounter(c)).catch(() => alive && setCounter(null));
    loadGuardStatus().then((g) => {
      if (!alive) return;
      setGs(g);
      if (g.status !== "ok") return;
      for (const r of g.rows) {
        if (!r.check.startsWith("workflow:")) continue;
        const file = r.check.slice("workflow:".length);
        loadRuns(file).then((m) => { if (alive) setRuns((x) => ({ ...x, [file]: m })); });
      }
    });
    return () => { alive = false; };
  }, [intake]);

  // ── THE ONE LIST ──
  const c = completeness, m = h?.metrics ?? {};
  const universe = c?.universe_count ?? 0, written = c?.records_written ?? 0, total = m.total_processed ?? 0;
  const billLimit = rhythmLimitHours(hist?.beats.bill ?? []), calLimit = rhythmLimitHours(hist?.beats.calendar ?? []);
  const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : null);
  // Rebuilt every render (ten objects): the data ages read the clock, so a memo kept them stale (Gemini #250).
  const intakeInsts: Instrument[] = [
    { id: "missing", cat: "Completeness", name: "Bills missing from our list", value: c && universe > 0 ? universe - written : null, of: universe || undefined, limit: 0, max: 20, impeaches: "no" },
    ...STATE.intakeChecks.map((k): Instrument => ({ id: k.key, cat: k.cat, name: k.label,
      value: num((c as unknown as Record<string, unknown> | null)?.[k.key]), limit: k.limit, max: Math.max(10, k.limit * 4), impeaches: "unknown" })),
    { id: "billage", cat: "Freshness", name: "Bill data age", value: dataAsOf ? +hoursSince(dataAsOf).toFixed(1) : null, limit: billLimit, max: billLimit * 4, unit: "h", impeaches: "no" },
    { id: "calage", cat: "Freshness", name: "Calendar data age", value: calAsOf ? +hoursSince(calAsOf).toFixed(1) : null, limit: billLimit, max: billLimit * 4, unit: "h", impeaches: "no" },
  ];
  const vaInsts: Instrument[] = [
    { id: "s9", cat: "Accuracy", name: "Meeting actions without a time", value: num(m.meeting_unsourced), limit: 0, max: 50, impeaches: "yes" },
    { id: "wrong", cat: "Accuracy", name: "Outcomes published wrong", value: num(c?.outcome_impeached), limit: 0, max: 5, impeaches: "yes" },
    { id: "noflag", cat: "Accuracy", name: "Settled bills with no flag", value: num(c?.outcome_unverified_terminal), limit: 0, max: 25, impeaches: "unknown" },
    { id: "missing", cat: "Completeness", name: "Bills missing from our list", value: c && universe > 0 ? universe - written : null, of: universe || undefined, limit: 0, max: 20, impeaches: "no" },
    { id: "hist", cat: "Completeness", name: "Bills in history, not in the bill list", value: c ? c.in_history_not_in_universe?.length ?? 0 : null, limit: 0, max: 20, impeaches: "no" },
    { id: "patron", cat: "Completeness", name: "Bills with no chief patron", value: c && written > 0 ? c.patron_missing ?? written - (c.patron_present ?? 0) : null, of: written || undefined, limit: 0, max: 20, impeaches: "no" },
    // the old 8% band, expressed as the count it allows out of this cycle's rows
    { id: "unclass", cat: "Completeness", name: "Rows with no class", value: h && total > 0 ? m.legevent_route_blank ?? 0 : null, of: total || undefined, limit: Math.floor(0.08 * total), max: Math.floor(0.25 * total) || 1, impeaches: "no" },
    { id: "billage", cat: "Freshness", name: "Bill data age", value: dataAsOf ? +hoursSince(dataAsOf).toFixed(1) : null, limit: billLimit, max: billLimit * 4, unit: "h", impeaches: "no" },
    { id: "calage", cat: "Freshness", name: "Calendar data age", value: h?.calendarFreshness ? +hoursSince(h.calendarFreshness).toFixed(1) : null, limit: calLimit, max: calLimit * 4, unit: "h", impeaches: "no" },
    { id: "inv", cat: "Stability", name: "Rows failing a format rule at write", value: num(m.invariant_violations), limit: 0, max: 60, impeaches: "no", note: "breaker trips at 50" },
  ];
  const insts = intake ? intakeInsts : vaInsts;

  // ── alert state (unchanged model: self-clearing conditions, judged on each worker's own clock) ──
  const alertModel: AlertModel | null = useMemo(() => {
    if (!hist?.available) return null;
    const latestCycleTs = Math.max(0, ...hist.metricSeries.map((p) => p.ts), ...hist.alerts.map((a) => a.ts));
    const ACTIVE_TOL_MS = 6 * 60 * 1000;
    const conds = groupConditions(hist.alerts);
    const byActivity = (a: Cond, b: Cond) => SEV_RANK(a.severity) - SEV_RANK(b.severity) || b.lastTs - a.lastTs;
    const cycleFor = (x: Cond) => hist.cycleTs[x.source] || latestCycleTs;
    const isActive = (x: Cond) => x.lastTs >= cycleFor(x) - ACTIVE_TOL_MS;
    const active = conds.filter(isActive).sort(byActivity);
    const resolved = conds.filter((x) => !isActive(x)).sort((a, b) => b.lastTs - a.lastTs);
    const needsLook = active.filter((x) => x.severity === "CRITICAL" || x.severity === "WARN");
    const notes = active.filter((x) => x.severity === "INFO" || x.severity === "UNKNOWN");
    return { latestCycleTs, active, resolved, needsLook, notes };
  }, [hist]);
  const liveNeedsLook = alertModel ? alertModel.needsLook.length : (h?.alerts ?? []).filter((a) => a.severity === "CRITICAL" || a.severity === "WARN").length;

  if (!completeness && !h && !hErr && !intake) return <p className="center-msg">Loading health…</p>;

  const ledgerOk = !!counter && counter.available && !counter.wrongSheet && counter.malformedRows === 0;
  const extras: RingExtra[] = intake ? [
    { cat: "Stability", name: "No alert needs a look", ok: hist !== null && liveNeedsLook === 0 },
    { cat: "Stability", name: "Heartbeat readable", ok: !!hist?.available },
  ] : [
    { cat: "Stability", name: "Circuit breaker armed", ok: !!h && !h.breakerTrip },
    { cat: "Stability", name: "No alert needs a look", ok: hist !== null && liveNeedsLook === 0 },
    { cat: "Stability", name: "Incident ledger readable, nothing open", ok: ledgerOk && counter!.openNow.length === 0 },
  ];
  const ring = rings(insts, extras);

  // ── problems: every not-clean check, as fields ──
  const problems: Problem[] = [];
  const guardRows = gs?.status === "ok" ? gs.rows : [];
  const checkedAt = guardRows.reduce<Date | null>((a, r) => (r.checked && (!a || r.checked > a) ? r.checked : a), null);
  if (!intake && gs && gs.status !== "ok") problems.push({ check: "Watched jobs (Guard_Status)", state: "unreadable", since: "this read", affects: "every scheduled job", wrong: "unknown", fix: null });
  else if (!intake && gs && hoursSince(checkedAt) > GUARD_STALE_H) problems.push({ check: "Trust-surface guard", state: "stale", since: shortDay(checkedAt), affects: "every scheduled job", wrong: "unknown", fix: null });
  for (const r of guardRows) {
    if (GUARD_OK.has(r.state)) continue;
    const [name, proves] = r.label.split(" — ");
    problems.push({ check: name, state: r.state.replace(/_/g, " "), since: shortDay(r.since), affects: proves || r.detail || "—",
      wrong: "unknown", fix: r.url ? { text: "latest run", url: r.url } : null });
  }
  if (intake) { /* no incident ledger for this state: not read, not a problem */ }
  else if (!ledgerOk) problems.push({ check: "Incident ledger", state: counter?.wrongSheet ? "wrong sheet" : counter?.available ? "unreadable rows" : "unreadable", since: "this read", affects: "days clean", wrong: "unknown", fix: null });
  // Every ring input that is not clean is ALSO a problem row (Codex #250): the verdict must never read clean beside
  // a red ring. Same fields, one row per input.
  else if (counter!.openNow.length > 0) problems.push({ check: "Open incident", state: "open", since: "—", affects: counter!.openNow.join(", "), wrong: "unknown", fix: null });
  if (intake) { /* no circuit breaker for this state */ }
  else if (!h) problems.push({ check: "Circuit breaker", state: "no result", since: "this read", affects: "every write", wrong: "unknown", fix: null });
  else if (h.breakerTrip) problems.push({ check: "Circuit breaker", state: "tripped", since: "this read", affects: "every write", wrong: "unknown", fix: null });
  if (hist === null || !hist.available) problems.push({ check: "Alert history", state: "unreadable", since: "this read", affects: "alerts", wrong: "unknown", fix: null });
  else if (hist.malformedRows > 0) problems.push({ check: "Alert history", state: "incomplete", since: "this read",
    affects: `${n(hist.malformedRows)} undateable rows — a live alert could read as cleared`, wrong: "unknown", fix: null });
  if (liveNeedsLook > 0) problems.push({ check: "Alerts", state: "need a look", since: "this read", affects: `${liveNeedsLook} condition${liveNeedsLook === 1 ? "" : "s"}`, wrong: "unknown", fix: null });
  for (const i of insts) {
    if (isClean(i)) continue;
    problems.push({ check: i.name, state: i.value === null ? "no result" : "over limit", since: "this read",
      affects: i.value === null ? i.cat.toLowerCase() : `${fmtVal(i)} · limit ${fmtLimit(i)}`,
      wrong: i.value === null ? "unknown" : i.impeaches, fix: null });
  }
  const v = verdictOf(insts, problems.map((p) => p.wrong));

  return (
    <div className="hx">
      <div className="hx-verdict">
        <span className={`st${v.clean ? "" : " red"}`}>{v.clean ? "verified clean" : "not verified clean"}</span>
        <span><b>{v.problems}</b> open problems</span>
        <span><b>{v.wrong}</b> published values known wrong</span>
        <span><b>{v.noResult}</b> instruments with no result</span>
        <span className="sub">as of {new Date().toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</span>
      </div>

      <div className={`hx-glance${intake ? " solo" : ""}`}>
        {!intake && <DaysClean counter={counter} />}
        <div className="hx-rings">
          {ring.map((r) => {
            const guard = OUTSIDE[r.cat] ? guards?.find((g) => g.key === OUTSIDE[r.cat]) : undefined;
            const outside = intake ? { text: `${STATE.name}'s own checks`, red: false } : !OUTSIDE[r.cat] ? { text: "no outside check", red: false }
              : guard && guard.status === "pass" && !guard.stale ? { text: "outside check ✓", red: false }
              : { text: `outside check ${guard ? (guard.stale ? "stale" : guard.status) : "unknown"}`, red: true };
            return (
              <div className="g" key={r.cat}>
                <RingSvg segs={r.segs.map((s) => s.ok)} />
                <div className="gn">{r.cat}</div>
                <div className={`gc${r.ok < r.total ? " red" : ""}`}>{r.ok} of {r.total} clean</div>
                <div className={`gv${outside.red ? " red" : ""}`}>{outside.text}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="hx-sec"><span>Open problems</span><span className="n">{problems.length}</span></div>
      <div className="hx-tile hx-tw">
        {problems.length === 0 ? <p className="muted" style={{ margin: 0 }}>Nothing open.</p> : (
          <table className="hx-ptab">
            <thead><tr><th>Check</th><th>State</th><th>Since</th><th>Affects</th><th>Published values wrong</th><th>Fix</th></tr></thead>
            <tbody>{problems.map((p, k) => (
              <tr key={k}><td>{p.check}</td><td><span className="st red">{p.state}</span></td><td className="num">{p.since}</td>
                <td>{p.affects}</td><td><span className={`st${p.wrong === "no" ? "" : " red"}`}>{p.wrong}</span></td>
                <td>{p.fix ? <a href={p.fix.url} target="_blank" rel="noopener noreferrer">{p.fix.text} ↗</a> : "—"}</td></tr>
            ))}</tbody>
          </table>
        )}
      </div>

      <div className="hx-sec"><span>Instruments</span><span className="n">needle in grey = fine · needle in red = over the limit</span></div>
      <div className="hx-row hx-r3">{insts.map((i) => <Dial key={i.id} i={i} />)}</div>

      {!intake && <>
      <div className="hx-sec"><span>Scheduled jobs · last 10 runs</span>
        <span className="n">{guardRows.filter((r) => r.check.startsWith("workflow:")).length} jobs + {guardRows.filter((r) => !r.check.startsWith("workflow:")).length} check · {guardRows.filter((r) => !GUARD_OK.has(r.state)).length} not ok</span></div>
      <div className="hx-tile hx-beats">
        {gs?.status !== "ok" ? <p className="red" style={{ margin: 0 }}>Job list unreadable.</p> : guardRows.map((r) => {
          const file = r.check.startsWith("workflow:") ? r.check.slice(9) : "";
          const marks = file ? runs[file] : undefined;
          const bad = !GUARD_OK.has(r.state);
          return (
            <div className="hx-beat" key={r.check}>
              <span className={`jn${bad ? " red" : ""}`}>{r.label.split(" — ")[0]}{r.state === "disabled" ? " · switched off" : ""}</span>
              <span className="runs" aria-label={marks ? `last runs: ${marks.join(", ")}` : "run history unavailable"}>
                {Array.from({ length: 10 }, (_, k) => {
                  const mk = marks ? marks[9 - k] : undefined;   // oldest left, newest right
                  return <i key={k} className={mk === "pass" ? "p" : mk === "fail" ? "f" : marks === null ? "u" : ""} />;
                })}
              </span>
              <span className="ls">{r.lastSuccess ? agoText(r.lastSuccess) : "never"}</span>
            </div>
          );
        })}
      </div>
      <div className="hx-legend"><span><i className="p" />passed</span><span><i className="f" />failed</span><span><i />no run</span><span><i className="u" />history unreadable</span></div>

      <div className="hx-sec"><span>Last 90 days</span><span className="n">{counter?.monitoringDays != null ? `monitoring for ${counter.monitoringDays} of 90` : "record not started"}</span></div>
      <div className="hx-tile">
        <div className="hx-strip">{(counter?.strip ?? []).map((d, k) => <i key={k} className={d === "incident" ? "f" : d === "unmeasured" ? "u" : ""} />)}</div>
        <div className="hx-legend"><span><i />clean</span><span><i className="f" />incident</span><span><i className="u" />not measured</span></div>
      </div>

      <div className="hx-row hx-r3" style={{ marginTop: 28 }}>
        <Watchers h={h} c={c} />
        <RowsByClass m={m} total={total} known={!!h} />
      </div>

      </>}

      <div className="hx-tile" style={{ marginTop: 12 }}>
        <details className="hx-alerts">
          <summary><span className="lbl">Alerts</span> {liveNeedsLook ? <span className="red">{liveNeedsLook} need a look</span> : "nothing needs your attention"}
            {alertModel && <span className="muted"> · {alertModel.notes.length} notes · {alertModel.resolved.length} cleared</span>}
            {hist && hist.malformedRows > 0 && <span className="red"> · history incomplete ({n(hist.malformedRows)} undateable rows)</span>} ›</summary>
          <AlertsPanel model={alertModel} liveAlerts={h?.alerts ?? []} />
        </details>
        {!intake && <details className="hx-alerts">
          <summary><span className="lbl">Raw system counters</span> {Object.keys(m).length} ›</summary>
          <div className="hx-raw">{Object.entries(m).sort(([a], [b]) => a.localeCompare(b)).map(([k, val]) => (
            <div key={k}><span>{k}</span><b>{n(val)}</b></div>))}</div>
        </details>}
        {hErr && <p className="red" style={{ marginBottom: 0 }}>Calendar signals unavailable: {hErr}</p>}
      </div>
    </div>
  );
}

const fmtVal = (i: Instrument) => i.value === null ? "?" : i.unit ? `${i.value} h` : i.of ? `${n(i.value)} of ${n(i.of)}` : n(i.value);
const fmtLimit = (i: Instrument) => i.unit ? `${+i.limit.toFixed(1)} h` : i.of ? `${n(i.limit)} of ${n(i.of)}` : n(i.limit);

function DaysClean({ counter }: { counter: CounterState | null }) {
  const unread = !counter || !counter.available || counter.wrongSheet;
  return (
    <div className="g days">
      <div className="big">{unread ? "?" : counter!.daysClean ?? "?"}</div>
      <div className="gn">Days clean</div>
      {unread ? <div className="gc red">{counter?.wrongSheet ? "wrong sheet read" : "ledger unreadable"}</div> : <>
        <div className="gc">monitoring for {counter!.monitoringDays ?? "?"} days</div>
        {counter!.openNow.length > 0 && <div className="gc red">{counter!.openNow.length} open now</div>}
        <div className={`gv${counter!.lastDrillDays === null ? " red" : ""}`}>{counter!.lastDrillDays === null ? "alarm never tested" : `last drill ${counter!.lastDrillDays} d ago`}</div>
      </>}
    </div>
  );
}

function RingSvg({ segs }: { segs: boolean[] }) {
  const r = 22, circ = 2 * Math.PI * r, gap = segs.length > 1 ? 3 : 0, seg = circ / Math.max(1, segs.length);
  return (
    <svg width="64" height="64" viewBox="0 0 56 56" aria-hidden="true" className="gfx">
      {segs.map((ok, k) => (
        <circle key={k} r={r} cx="28" cy="28" fill="none" stroke={ok ? "#6E787E" : "var(--red)"} strokeWidth="7"
          strokeDasharray={`${seg - gap} ${circ - seg + gap}`} strokeDashoffset={-k * seg} transform="rotate(-90 28 28)" />
      ))}
    </svg>
  );
}

// A dial like a car's rev counter: grey arc = 0 up to the limit, red arc = past the limit, needle = now.
const ARC = (f: number): [number, number] => { const a = Math.PI * (1 - f); return [60 + 46 * Math.cos(a), 56 - 46 * Math.sin(a)]; };
const arcPath = (f0: number, f1: number) => { const [x0, y0] = ARC(f0), [x1, y1] = ARC(f1); return `M${x0.toFixed(1)} ${y0.toFixed(1)} A46 46 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`; };

function Dial({ i }: { i: Instrument }) {
  const known = i.value !== null, ok = isClean(i), [nx, ny] = ARC(dialPos(i));
  return (
    <div className={`hx-tile hx-gauge${known ? "" : " unk"}`} role="img"
      aria-label={`${i.name}: ${known ? fmtVal(i) : "no result"}; limit ${fmtLimit(i)}; ${ok ? "fine" : known ? "over the limit" : "unconfirmed"}`}>
      <svg width="120" height="72" viewBox="0 0 120 72" aria-hidden="true">
        <path d={arcPath(0, 0.6)} fill="none" stroke="#4A5257" strokeWidth="9" />
        <path d={arcPath(0.6, 1)} fill="none" stroke="var(--red)" strokeOpacity=".75" strokeWidth="9" />
        {known ? <>
          <line x1="60" y1="56" x2={(60 + (nx - 60) * 0.82).toFixed(1)} y2={(56 + (ny - 56) * 0.82).toFixed(1)}
            stroke={ok ? "var(--ink)" : "var(--red)"} strokeWidth="3" strokeLinecap="round" />
          <circle cx="60" cy="56" r="4" fill={ok ? "var(--ink)" : "var(--red)"} />
        </> : <text x="60" y="50" textAnchor="middle" fontSize="20" fontWeight="700" fill="var(--red)">?</text>}
        <text x="4" y="70">0</text>
        <text x="118" y="70" textAnchor="end">{i.unit ? `${Math.round(i.max)} h` : n(i.max)}</text>
      </svg>
      <div style={{ minWidth: 0 }}>
        <div className="nm">{i.name}</div>
        <div className={`val${known && !ok ? " red" : ""}`}>{known ? fmtVal(i) : "?"}</div>
        <div className="foot">limit {fmtLimit(i)}{i.note ? ` · ${i.note}` : ""} {!known ? <span className="st red">no result</span> : !ok ? <span className="st red">over limit</span> : null}</div>
      </div>
    </div>
  );
}

const CANARIES: [string, string][] = [
  ["canary_status_grouping", "Legislation status vocabulary"], ["canary_governor_eventcodes", "Governor action codes"],
  ["canary_refid_shape", "Refid namespaces"], ["canary_scheduletype", "Schedule types"], ["canary_referencetype", "Reference types"],
];

function Watchers({ h, c }: { h: HealthData | null; c: Completeness | null }) {
  const m = h?.metrics ?? {};
  const rows: { label: string; mark: string; red: boolean }[] = CANARIES.map(([k, label]) => {
    const val = m[k];
    return val == null || val < 0 ? { label, mark: "?", red: true } : val === 0 ? { label, mark: "✓", red: false } : { label: `${label} · ${val} new`, mark: "✕", red: true };
  });
  rows.push(!h ? { label: "Circuit breaker", mark: "?", red: true } : h.breakerTrip ? { label: "Circuit breaker tripped", mark: "✕", red: true } : { label: "Circuit breaker armed", mark: "✓", red: false });
  // LIS disagreeing with ITSELF (status text vs its own flags). We publish the flag, so this never impeaches a
  // published value — it is an upstream observation, shown as its count.
  const mm = c?.outcome_keyword_mismatches, of = (c?.outcome_structural ?? 0) + (c?.outcome_keyword_fallback ?? 0);
  rows.push(mm == null ? { label: `${SOURCE} status text vs its own flags`, mark: "?", red: true }
    : { label: `${SOURCE} status text vs its own flags · ${n(mm)} of ${n(of)} differ`, mark: mm ? "≠" : "✓", red: false });
  return (
    <div className="hx-tile">
      <div className="lbl">Upstream watchers · is {SOURCE} still speaking our language?</div>
      <div className="hx-ticks">{rows.map((r) => <div key={r.label}><b className={r.red ? "red" : ""}>{r.mark}</b>{r.label}</div>)}</div>
    </div>
  );
}

function RowsByClass({ m, total, known }: { m: Record<string, number>; total: number; known: boolean }) {
  const parts: [string, number, string][] = [["meeting", m.legevent_route_meeting ?? 0, "#9AA3A8"], ["admin", m.legevent_route_admin ?? 0, "#5D676D"],
    ["executive", m.legevent_route_executive ?? 0, "#C9D0D4"], ["no class", m.legevent_route_blank ?? 0, "#3A4146"]];
  return (
    <div className="hx-tile">
      <div className="lbl">Where the rows went · of {known ? n(total) : "?"}</div>
      {!known || total === 0 ? <p className="red">No result.</p> : <>
        <div className="hx-stack">{parts.map(([k, val, col]) => <span key={k} style={{ width: `${(100 * val) / total}%`, background: col }} title={`${k}: ${n(val)}`} />)}</div>
        <div className="hx-legend">{parts.map(([k, val, col]) => <span key={k}><i style={{ background: col }} />{k} {n(val)}</span>)}</div>
      </>}
    </div>
  );
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

