// The days-clean counter — the visible artifact of the trust promise (W1.6).
//
// Reads the append-only `Incident_Log` tab via gviz, the same read-only path every other panel uses. The
// MEANING of the number is set in docs/architecture/incident_counter.md and it is deliberately strict:
// "days we could VERIFY clean", not "days nobody complained". An unresolved unknown counts against it.
//
// Row shape: StartUTC | EndUTC | Class | Summary | DetectedBy
import { SPREADSHEET_ID } from "../config";
import { parseCsv } from "./gviz";

const TAB = "Incident_Log";

// Mirrors tools/incident_log/log.py. `_genesis` marks when monitoring began and `_drill` is a fire-drill
// exercising the real write path — neither is an incident, so neither may break the streak.
const GENESIS = "_genesis";
const DRILL = "_drill";

export interface CounterState {
  /** Days since the last incident ended, or since monitoring began. null = no epoch yet (unseeded). */
  daysClean: number | null;
  /** The DENOMINATOR (Standard #7). "47 days clean" is meaningless without "monitoring for 51". */
  monitoringDays: number | null;
  incidentsEver: number;
  /** Classes with no EndUTC. Non-empty = an incident is OPEN right now, so the surface must read red. */
  openNow: string[];
  /** Days since the last fire drill. A stale drill is itself a signal — the alarm may be untested. */
  lastDrillDays: number | null;
  /** Rows carrying data we could not read. >0 means the counter may be hiding a real incident. */
  malformedRows: number;
  /** false = the tab does not exist yet. The UI must say "not yet seeded", never a fake green. */
  available: boolean;
}

const EMPTY: CounterState = {
  daysClean: null, monitoringDays: null, incidentsEver: 0, openNow: [],
  lastDrillDays: null, malformedRows: 0, available: false,
};

const parseIso = (s: string): number | null => {
  const t = Date.parse((s || "").trim().replace(" ", "T"));
  return Number.isFinite(t) ? t : null;
};

const wholeDays = (fromMs: number, nowMs: number) =>
  Math.max(0, Math.floor((nowMs - fromMs) / 86_400_000));

export function counterFromRows(rows: string[][], now: Date = new Date()): CounterState {
  const nowMs = now.getTime();
  let latestEnd: number | null = null;   // last time we were known-clean (an incident's end, or genesis)
  let genesis: number | null = null;
  let lastDrill: number | null = null;
  let incidentsEver = 0;
  let malformedRows = 0;
  const openNow: string[] = [];

  for (const r of rows) {
    // Sheets pads the grid with blank rows; those are not data and warrant no alarm.
    if (!r.some((c) => (c || "").trim())) continue;
    // Fewer than 3 columns means Start/End/Class cannot all be read. Sheets TRIMS trailing empty cells, so
    // requiring the full 5-column header width would skip real incidents whose optional tail was trimmed —
    // the under-report bug from #225/#226. A short row with data is a DATA ANOMALY, surfaced not dropped.
    if (r.length < 3) { malformedRows++; continue; }

    const cls = (r[2] || "").trim();
    if (cls === "StartUTC" || cls === "Class") continue;      // the header, identified structurally
    const start = parseIso(r[0]);
    const end = parseIso(r[1]);

    if (cls === GENESIS) { if (start !== null) genesis = start; continue; }
    if (cls === DRILL) {
      // A drill proves the write path works. It must NOT touch the clock — same exclusion as genesis.
      const at = end ?? start;
      if (at !== null && (lastDrill === null || at > lastDrill)) lastDrill = at;
      continue;
    }
    if (!cls) { malformedRows++; continue; }                  // data present, but unclassifiable

    incidentsEver++;
    if (end === null) {
      openNow.push(cls);            // still open — the clock reads from its START, and the surface is red
      if (start !== null && (latestEnd === null || start > latestEnd)) latestEnd = start;
    } else if (latestEnd === null || end > latestEnd) {
      latestEnd = end;
    }
  }

  // No incidents yet → the streak runs from genesis. No genesis either → we have no honest epoch, so the
  // answer is null ("not yet seeded"), never 0 and never a reassuring number we cannot support.
  const clockFrom = latestEnd ?? genesis;
  return {
    daysClean: clockFrom === null ? null : wholeDays(clockFrom, nowMs),
    monitoringDays: genesis === null ? null : wholeDays(genesis, nowMs),
    incidentsEver,
    openNow,
    lastDrillDays: lastDrill === null ? null : wholeDays(lastDrill, nowMs),
    malformedRows,
    available: genesis !== null || incidentsEver > 0,
  };
}

export async function loadCounter(): Promise<CounterState> {
  const url = `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=${TAB}`;
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return EMPTY;
    const txt = await res.text();
    // A missing tab comes back as an HTML error page, not CSV — that is "not seeded yet", not a failure.
    if (txt.trimStart().startsWith("<") || /"status":"error"/.test(txt)) return EMPTY;
    return counterFromRows(parseCsv(txt));
  } catch {
    return EMPTY;   // optional chrome: the trust line must never blank the Health tab
  }
}
