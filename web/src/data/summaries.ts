// Bill summaries — LIS's own staff-written summaries (Summaries.csv), written by bill_tracker.py to their OWN
// tab and read here LAZILY, one bill per query, when a bill card opens. They are ~3.8 MB of text, so they must
// never ride on the main Bill_Tracker load (already ~7 MB).
//
// Three honest states, never collapsed (pre-push audit #15):
//   ok          — the bill has one or more summary versions
//   none        — the tab answered (header verified) and LIS has no summary for this bill
//   unavailable — the tab is missing / the wrong tab came back / the fetch failed. Shown as "not available",
//                 never as "none" — gviz serves the FIRST sheet for a missing tab (config.headerMatches).
import { parseCsv } from "./gviz";
import { SPREADSHEET_ID, headerMatches } from "../config";

const TAB = "Bill_Summaries";
const EXPECTED_HEADER = ["Bill", "Summary Type", "Stage Rank", "Summary"] as const;
const FETCH_TIMEOUT_MS = 12000;

export interface SummaryVersion {
  type: string;          // LIS's SUMMARY_TYPE, verbatim ("SUMMARY AS PASSED", ...)
  rank: number | null;   // lifecycle stage from the worker; null = a type the worker didn't recognize
  text: string;          // plain text (tags stripped by the worker; rendered as text, never as HTML)
}
export type SummaryResult =
  | { status: "ok"; latest: SummaryVersion; others: SummaryVersion[] }
  | { status: "none" }
  | { status: "unavailable" };

/** Order versions newest-stage first. Only a RANKED version can be "latest": an unrecognized type is kept and
 *  shown among the others, never promoted on a guess. Same-rank ties keep LIS's order. */
export function pickLatest(versions: SummaryVersion[]): SummaryResult {
  if (versions.length === 0) return { status: "none" };
  const ranked = versions.filter((v) => v.rank !== null);
  if (ranked.length === 0) return { status: "ok", latest: versions[0], others: versions.slice(1) };
  let best = ranked[0];
  for (const v of ranked) if ((v.rank as number) > (best.rank as number)) best = v;
  return { status: "ok", latest: best, others: versions.filter((v) => v !== best) };
}

/** "SUMMARY AS PASSED HOUSE" -> "Summary as passed House". Case only; the words stay LIS's. */
export function typeLabel(t: string): string {
  const s = t.trim().toLowerCase().replace(/\bhouse\b/g, "House").replace(/\bsenate\b/g, "Senate")
    .replace(/\bgovernor's\b/g, "Governor's");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const _cache = new Map<string, Promise<SummaryResult>>();

export function loadSummary(bill: string): Promise<SummaryResult> {
  const id = bill.replace(/\s/g, "").toUpperCase();
  if (!/^[A-Z]+\d+$/.test(id)) return Promise.resolve({ status: "unavailable" });   // never interpolate junk into a query
  const hit = _cache.get(id);
  if (hit) return hit;
  const p = _load(id).catch((e) => {
    console.warn(`Summaries: read failed for ${id}`, e);
    _cache.delete(id);                     // a transient failure must not stick for the session
    return { status: "unavailable" } as SummaryResult;
  });
  _cache.set(id, p);
  return p;
}

async function _load(id: string): Promise<SummaryResult> {
  const q = `select A,B,C,D where A = '${id}'`;
  const url = `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=${TAB}&tq=${encodeURIComponent(q)}`;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
  let text: string;
  try {
    const res = await fetch(url, { cache: "no-store", signal: ctrl.signal });
    if (!res.ok) return { status: "unavailable" };
    text = await res.text();
  } finally {
    clearTimeout(timer);
  }
  const rows = parseCsv(text);
  if (!headerMatches(rows[0], EXPECTED_HEADER)) return { status: "unavailable" };
  const versions: SummaryVersion[] = rows.slice(1)
    .filter((r) => (r[0] || "").trim() === id && (r[3] || "").trim() !== "")
    .map((r) => {
      const n = Number((r[2] || "").trim());
      return { type: (r[1] || "").trim(), rank: (r[2] || "").trim() !== "" && Number.isFinite(n) ? n : null, text: r[3].trim() };
    });
  return pickLatest(versions);
}
