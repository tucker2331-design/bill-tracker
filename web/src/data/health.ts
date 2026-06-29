// The operator/Health tab's calendar-subsystem signals (vision §3f). The bill backend's completeness
// payload arrives via props (App already loads Bill_Tracker R1); THIS loads the calendar subsystem's live
// health from Sheet1 — but LIGHTWEIGHT: a gviz `tq WHERE` grabs only the two SYSTEM rows (~2 KB, not the
// ~5 MB full sheet) plus `range=` reads for the AA1 freshness + W1 breaker-trip cells. Auth-free gviz, no
// new backend. These are operational metrics the worker already emits (Standard #4 self-describing errors).
import { parseCsv } from "./gviz";
import { SPREADSHEET_ID } from "../config";

const SHEET1 = "Sheet1";
const FETCH_TIMEOUT_MS = 12000;
const CACHE_TTL_MS = 120000; // operator data must stay current — re-fetch after 2 min (not cached forever)
const META_QUERY = "select A,D,G,J where J = 'system_metrics' or J = 'system_alert'"; // Date,Status,Outcome,Origin
const KNOWN_SEVERITIES = new Set(["INFO", "WARN", "CRITICAL"]); // the worker's Status vocabulary (Standard #4)

export interface HealthAlert {
  severity: string;   // INFO | WARN | CRITICAL (the worker's Status cell, structural)
  category: string;   // TIMING_LAG | DATA_ANOMALY | API_FAILURE | … (from our own [SEV:CAT] tag)
  message: string;
  date: string;
}

export interface HealthData {
  metrics: Record<string, number>;          // SYSTEM_METRICS numeric counters (meeting_unsourced, …)
  alerts: HealthAlert[];                     // SYSTEM_ALERT rows (the operator's "needs a human" feed)
  calendarFreshness: Date | null;            // Sheet1!AA1 — the CALENDAR worker's own last-good cycle (≠ bill backend)
  breakerTrip: Record<string, unknown> | null; // Sheet1!W1 — null when healthy; the trip JSON when the breaker fired
}

const gvizUrl = (params: string) =>
  `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=${SHEET1}&${params}`;

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

// The SYSTEM_METRICS payload is a JSON object of counters (mostly numbers; a couple of strings like
// gap_cause). Keep the numeric ones for the gauges; pass-through, no derivation.
function parseMetrics(cell: string): Record<string, number> {
  const out: Record<string, number> = {};
  try {
    const obj = JSON.parse(cell);
    for (const [k, v] of Object.entries(obj)) {
      // Only keep genuine numbers (or non-empty numeric strings). Number(null)/Number("")/Number(false)
      // all coerce to 0, which would turn an ABSENT metric into a false-green 0 — the Health vitals rely
      // on a missing key staying missing so they render "unknown" (CodeRabbit #167; "never pretend").
      if (typeof v === "number" && Number.isFinite(v)) {
        out[k] = v;
      } else if (typeof v === "string" && v.trim() !== "") {
        const n = Number(v);
        if (Number.isFinite(n)) out[k] = n;
      }
    }
  } catch (e) {
    // Optional ≠ silent (Standard #4): a malformed metrics row surfaces an empty gauge set, but the dev/
    // operator still needs to know the SYSTEM_METRICS JSON didn't parse — warn rather than swallow.
    console.warn("Health: SYSTEM_METRICS row is not valid JSON; gauges will be empty", e);
  }
  return out;
}

function firstCell(txt: string): string {
  return (parseCsv(txt)?.[0]?.[0] || "").trim();
}

// TTL cache: serve a recent load instantly (tab re-opens) but RE-FETCH after the TTL so operator data is
// never stale-forever; a failed load clears the cache so the next open retries.
let _cache: { at: number; data: Promise<HealthData> } | null = null;

export function loadHealth(): Promise<HealthData> {
  const now = Date.now();
  if (!_cache || now - _cache.at > CACHE_TTL_MS) {
    _cache = { at: now, data: _loadHealth().catch((e) => { _cache = null; throw e; }) };
  }
  return _cache.data;
}

async function _loadHealth(): Promise<HealthData> {
  const [metaTxt, aa1Txt, w1Txt] = await Promise.all([
    fetchText(gvizUrl(`tq=${encodeURIComponent(META_QUERY)}`)),
    // The freshness + breaker cells are optional: a failed read must not blank the whole tab. Surface a
    // console warning (Standard #4: optional ≠ silent) and fall back to "unknown"/healthy.
    fetchText(gvizUrl("range=AA1&headers=0")).catch((e) => { console.warn("Health: AA1 freshness read failed", e); return ""; }),
    fetchText(gvizUrl("range=W1&headers=0")).catch((e) => { console.warn("Health: W1 breaker read failed", e); return ""; }),
  ]);

  // Shape guard: a 200 that isn't our CSV (an HTML login/error page) must not parse to a silent empty set.
  if (metaTxt.trimStart().startsWith("<")) {
    throw new Error("unexpected Sheet1 response — not CSV (sheet renamed, not link-readable, or an error page?)");
  }

  const rows = parseCsv(metaTxt);
  let metrics: Record<string, number> = {};
  const alerts: HealthAlert[] = [];
  // A column-select gviz CSV emits NO header row here, so iterate ALL rows; the Origin check below filters
  // out any stray header ("Origin") naturally — never skip row 0 (that dropped the SYSTEM_ALERT row).
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    const origin = (r[3] || "").trim();
    if (origin === "system_metrics") {
      metrics = parseMetrics(r[2] || "");
    } else if (origin === "system_alert") {
      const msg = (r[2] || "").trim();
      // Our own structured tag "[SEV:CATEGORY] message" — internal format we control (not LIS prose).
      const m = /^\[([A-Z]+):([A-Z_]+)\]\s*(.*)$/s.exec(msg);
      // VALIDATE the severity against the worker's known vocabulary — an unrecognized value is flagged
      // "UNKNOWN" (never silently coerced to INFO; "allowed not to know, never pretend"). Category likewise
      // normalized to a clean non-empty token for display.
      const rawSev = (r[1] || m?.[1] || "").trim().toUpperCase();
      alerts.push({
        severity: KNOWN_SEVERITIES.has(rawSev) ? rawSev : "UNKNOWN",
        category: (m?.[2] || "").trim().toUpperCase() || "UNCATEGORIZED",
        message: (m?.[3] || msg).trim(),
        date: (r[0] || "").trim(),
      });
    }
  }

  const aa1 = firstCell(aa1Txt);
  const calendarFreshness = aa1 && !isNaN(Date.parse(aa1)) ? new Date(aa1) : null;

  const w1 = firstCell(w1Txt);
  let breakerTrip: Record<string, unknown> | null = null;
  if (w1.startsWith("{")) {
    try { breakerTrip = JSON.parse(w1); } catch { console.warn("Health: W1 present but not JSON", w1.slice(0, 80)); }
  }

  return { metrics, alerts, calendarFreshness, breakerTrip };
}
