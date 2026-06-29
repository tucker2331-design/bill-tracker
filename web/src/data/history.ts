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
export interface HistAlert { ts: number; severity: string; category: string; message: string; }
export interface HistoryData {
  metricSeries: MetricPoint[]; // newest-first
  alerts: HistAlert[];         // newest-first
  available: boolean;          // false = tab absent / unreadable (UI shows "populating", never fake-green)
}

const EMPTY: HistoryData = { metricSeries: [], alerts: [], available: false };

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
  for (const r of rows) {
    const tsRaw = (r[0] || "").trim();
    const ts = Date.parse(tsRaw);
    if (!Number.isFinite(ts)) continue; // skip a header or unparseable row, never guess a timestamp
    const status = (r[1] || "").trim();
    const origin = (r[2] || "").trim();
    const outcome = (r[3] || "").trim();
    if (origin === "system_metrics") {
      metricSeries.push({ ts, metrics: parseMetrics(outcome) });
    } else if (origin === "system_alert") {
      const m = /^\[([A-Z]+):([A-Z_]+)\]\s*(.*)$/s.exec(outcome);
      const rawSev = (status || m?.[1] || "").trim().toUpperCase();
      alerts.push({
        ts,
        severity: KNOWN_SEVERITIES.has(rawSev) ? rawSev : "UNKNOWN",
        category: (m?.[2] || "").trim().toUpperCase() || "UNCATEGORIZED",
        message: (m?.[3] || outcome).trim(),
      });
    }
  }
  return { metricSeries, alerts, available: metricSeries.length > 0 || alerts.length > 0 };
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
