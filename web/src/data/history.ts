// Per-cycle alert + metric HISTORY (the Health tab's trend store). The calendar worker appends THIS
// cycle's SYSTEM rows to an append-only Metrics_History tab (calendar_worker.py), so — unlike the
// always-overwritten Sheet1 — we can show alert HISTORY (what fired and when) and metric TRENDS
// (sparklines), not just a point-in-time snapshot. Auth-free gviz, same as health.ts.
//
// "Never pretend": the tab does not exist until the worker has run once after deploy, and a transient
// gviz failure is normal — BOTH degrade to an EMPTY history (the UI shows "trend will populate"), never a
// fabricated series and never a thrown error that blanks the live Health tab.
import { parseCsv } from "./gviz";
import { SPREADSHEET_ID } from "../config";

const TAB = "Metrics_History";
const FETCH_TIMEOUT_MS = 12000;
const CACHE_TTL_MS = 120000;
// Recent window: newest-first, bounded so the read stays light (the tab holds ~45d of 1-6 rows/cycle).
// ~500 rows ≈ a few days of trend + the recent alert stream — plenty for a sparkline, still ~<1 MB.
const RECENT_LIMIT = 500;
const QUERY = `select A,B,C,D order by A desc limit ${RECENT_LIMIT}`; // A=RunTimestampUTC B=Status C=Origin D=Outcome
const KNOWN_SEVERITIES = new Set(["INFO", "WARN", "CRITICAL"]);

export interface MetricPoint { ts: number; metrics: Record<string, number>; } // one resolved cycle
// TWO workers write here on DIFFERENT cadences (calendar ~15min in-window; bill far slower when quiet), so
// every alert carries the worker that raised it. Judging a bill alert against the calendar worker's clock
// would mark it "resolved" the moment the calendar ticked — the alert would land and instantly vanish.
export type AlertSource = "calendar" | "bill";
export interface HistAlert { ts: number; severity: string; category: string; message: string; source: AlertSource; }
export interface HistoryData {
  metricSeries: MetricPoint[]; // newest-first — CALENDAR worker (the sparkline series)
  alerts: HistAlert[];         // newest-first, from both workers (see `source`)
  /** Latest cycle timestamp PER WORKER, so "is this still live?" is asked of the right clock. */
  cycleTs: Record<AlertSource, number>;
  available: boolean;          // false = tab absent / unreadable (UI shows "populating", never fake-green)
  /** Rows that carried data but no parseable timestamp. >0 means this history may be INCOMPLETE, which can
   *  make a still-active alert condition look self-resolved — so it is surfaced, never silently dropped. */
  malformedRows: number;
}

const EMPTY: HistoryData = { metricSeries: [], alerts: [], cycleTs: { calendar: 0, bill: 0 }, available: false, malformedRows: 0 };

const gvizUrl = () =>
  `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=${TAB}&tq=${encodeURIComponent(QUERY)}`;

async function fetchText(u: string): Promise<string> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(u, { cache: "no-store", signal: ctrl.signal });
    if (!res.ok) throw new Error(`gviz fetch failed: HTTP ${res.status}`);
    return await res.text();
  } finally {
    clearTimeout(timer);
  }
}

// Same number-only discipline as health.parseMetrics: a missing key must stay MISSING, never coerce to a
// false-green 0 — the sparklines/canaries rely on absence to render "unknown".
function parseMetrics(cell: string): Record<string, number> {
  const out: Record<string, number> = {};
  try {
    const obj = JSON.parse(cell);
    for (const [k, v] of Object.entries(obj)) {
      if (typeof v === "number" && Number.isFinite(v)) out[k] = v;
      else if (typeof v === "string" && v.trim() !== "") {
        const n = Number(v);
        if (Number.isFinite(n)) out[k] = n;
      }
    }
  } catch { /* a single malformed row is skipped; the series simply omits that point */ }
  return out;
}

let _cache: { at: number; data: Promise<HistoryData> } | null = null;

export function loadHistory(): Promise<HistoryData> {
  const now = Date.now();
  if (!_cache || now - _cache.at > CACHE_TTL_MS) {
    // Resolve to EMPTY (not reject) on any failure: the trend store is OPTIONAL chrome over the live tab.
    _cache = { at: now, data: _loadHistory().catch((e) => { console.warn("History: trend store read failed", e); return EMPTY; }) };
  }
  return _cache.data;
}

async function _loadHistory(): Promise<HistoryData> {
  const txt = await fetchText(gvizUrl());
  // The tab not existing yet (pre-first-worker-run) comes back as an error/HTML page, NOT our CSV.
  if (txt.trimStart().startsWith("<") || /google\.visualization\.Query\.setResponse[\s\S]*"status":"error"/.test(txt)) {
    return EMPTY; // honest empty — the UI shows "trend will populate once the worker has run"
  }
  const rows = parseCsv(txt);
  const metricSeries: MetricPoint[] = [];
  const alerts: HistAlert[] = [];
  const cycleTs: Record<AlertSource, number> = { calendar: 0, bill: 0 };
  // A row we cannot date is NOT silently dropped (Standard #9 / source-miss visibility, CodeRabbit #227).
  // Dropping them quietly can hand the UI a PARTIAL history, and this store is what decides whether an
  // alert condition is still active — so missing cycles can make a live condition look self-resolved.
  // The header row is EXPECTED and identified structurally by its first cell; anything else that fails to
  // parse is a data anomaly, counted here and surfaced by the caller rather than assumed benign.
  let malformedRows = 0;
  for (const r of rows) {
    const tsRaw = (r[0] || "").trim();
    const ts = Date.parse(tsRaw);
    if (!Number.isFinite(ts)) {
      const isHeader = tsRaw === "RunTimestampUTC";          // the worker's own header, structurally known
      const isBlank = r.every((c) => !(c || "").trim());     // trailing grid padding from Sheets
      if (!isHeader && !isBlank) malformedRows++;
      continue;                                              // never guess a timestamp
    }
    const status = (r[1] || "").trim();
    const origin = (r[2] || "").trim();
    const outcome = (r[3] || "").trim();
    const pushAlert = (source: AlertSource) => {
      const m = /^\[([A-Z]+):([A-Z_]+)\]\s*(.*)$/s.exec(outcome);
      const rawSev = (status || m?.[1] || "").trim().toUpperCase();
      alerts.push({
        ts,
        severity: KNOWN_SEVERITIES.has(rawSev) ? rawSev : "UNKNOWN",
        category: (m?.[2] || "").trim().toUpperCase() || "UNCATEGORIZED",
        message: (m?.[3] || outcome).trim(),
        source,
      });
    };
    if (origin === "system_metrics") {
      metricSeries.push({ ts, metrics: parseMetrics(outcome) });
      cycleTs.calendar = Math.max(cycleTs.calendar, ts);
    } else if (origin === "system_alert") {
      pushAlert("calendar");
      cycleTs.calendar = Math.max(cycleTs.calendar, ts);
    } else if (origin === "bill_system_metrics") {
      // Heartbeat only — deliberately NOT pushed into `metricSeries`, whose keys are the calendar worker's
      // and whose points feed the sparklines. Its job is to date the bill worker's latest cycle.
      cycleTs.bill = Math.max(cycleTs.bill, ts);
    } else if (origin === "bill_system_alert") {
      pushAlert("bill");
      cycleTs.bill = Math.max(cycleTs.bill, ts);
    }
  }
  if (malformedRows) {
    // Categorised + visible, never swallowed: the trend store is optional chrome, but a partial one can
    // mis-report an ACTIVE condition as resolved, so the count travels with the data for the UI to show.
    console.warn(`[WARN:DATA_ANOMALY] Metrics_History: ${malformedRows} undateable row(s) skipped — the ` +
                 `trend/alert history may be incomplete, which can make a live condition look resolved.`);
  }
  return { metricSeries, alerts, cycleTs, malformedRows,
           available: metricSeries.length > 0 || alerts.length > 0 };
}

// The series for one metric key, OLDEST→NEWEST (sparkline draws left=old → right=now). Points where the
// key is absent are dropped, so a key only added recently still draws a clean partial line.
export function seriesFor(h: HistoryData, key: string): number[] {
  return h.metricSeries
    .filter((p) => typeof p.metrics[key] === "number")
    .slice()
    .reverse()
    .map((p) => p.metrics[key]);
}

// A PERCENTAGE series (100 * num/den) per cycle, OLDEST→NEWEST. For a gauge whose value is itself a ratio
// (e.g. unclassified share = blank/total), a raw-count spark can trend OPPOSITE to the gauge when the
// denominator moves between cycles (CodeRabbit #181) — derive both keys per point so the spark matches the
// gauge. Points missing either key, or with den<=0, are dropped (no divide-by-zero, no fabricated 0).
export function seriesForPct(h: HistoryData, numKey: string, denKey: string): number[] {
  return h.metricSeries
    .slice()
    .reverse()
    .filter((p) => typeof p.metrics[numKey] === "number" && typeof p.metrics[denKey] === "number" && p.metrics[denKey] > 0)
    .map((p) => (100 * p.metrics[numKey]) / p.metrics[denKey]);
}
