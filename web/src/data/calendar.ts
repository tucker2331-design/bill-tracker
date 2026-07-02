// The full Calendar — the lobbyist's "by time" lens (vision §3c). The perfected calendar subsystem
// (calendar_worker.py → Sheet1) is the engine; this reads its output the same auth-free gviz way the
// X-Ray does (pages/ray2.py load_sheet_df). Sheet1 lives in the SAME workbook as Bill_Tracker, so the
// existing SPREADSHEET_ID + a column projection are all we need — no new credentials, no backend change.
//
// We pull only the 7 columns the calendar needs (Date,Time,SortTime,Committee,Bill,Outcome,Origin) via a
// gviz `tq` projection — ~5 MB vs ~9 MB full — and lazy-load it ONLY when the Calendar tab opens (keeps
// the landing fast). A meeting = a (date, committee, time) where people were in a room; the Ledger-Updates
// collapse (admin actions, no time) and the executive/meta rows are NOT meetings and are excluded.
import { parseCsv } from "./gviz";
import { SPREADSHEET_ID } from "../config";
import { parseLisDate, dayKey } from "./dates";
import type { Chamber } from "./types";

export type MeetingKind = "floor" | "committee";

// Floor SESSION MARKERS (a chamber convening / reconvening / recessing / adjourning) vs actual committee
// meetings. DISPLAY-ONLY heuristic: it only chooses how a row is STYLED (quiet session tissue vs a meeting
// card) — it never hides, drops, or re-counts a row, so it is NOT the structural-completeness path Standard
// #3 governs (a misclassification shows the wrong style, never wrong/missing data). There is no structural
// floor/committee field in Sheet1 (LIS encodes it only in the meeting NAME), and the calendar WORKER already
// floor-detects on these same LIS verbs — this mirrors that classification, it doesn't invent one.
//   ASSUMES: LIS names floor markers with convene/reconvene/adjourn/recess (+ conjugations) — e.g.
//     "House Convenes", "Senate adjourned", "House recessed until…". Caucuses ("Rural Caucus") are group
//     meetings, not floor markers, so they stay "committee" (no verb match).
//   BREAKS: a committee whose name contained one of those WHOLE words would misclassify (none in the VA
//     committee list today); the pattern is word-bounded + conjugation-explicit to avoid substring over-match
//     (Gemini/Qodo #186). The relative-time "…after adjournment of X" phrase lives in the TIME field, not the
//     name, so a relative-timed committee meeting is never misread as floor.
// Pure + exported so the classification is one testable place (CodeRabbit #186); web/ has no unit runner yet
// (the CI structural tests are Python-only), so it's covered by tsc + the live preview for now.
const FLOOR_MARKER = /\b(?:re)?conven(?:es?|ed)\b|\badjourn(?:s|ed)?\b|\brecess(?:es|ed)?\b/i;
export function classifyMeetingKind(committee: string): MeetingKind {
  return FLOOR_MARKER.test(committee) ? "floor" : "committee";
}

export interface AgendaItem { bill: string; action: string; }

export interface Meeting {
  dateKey: string;       // local YYYY-MM-DD
  committee: string;     // chamber-qualified meeting name ("House Appropriations", "Senate Convenes")
  chamber: Chamber | null;
  kind: MeetingKind;
  time: string;          // display, e.g. "9:00 AM" — or "Time TBA" when no concrete time is published
  tba: boolean;          // true when LIS published the meeting but no concrete time (never hidden — §7)
  minutes: number;       // sort key — minutes past midnight (from the worker's SortTime, the authority)
  bills: AgendaItem[];   // real bills on the agenda (deduped; empty for skeleton/commission meetings)
}

export interface CalendarData {
  byDay: Map<string, Meeting[]>;  // dateKey -> meetings (sorted by time)
  minKey: string;                 // earliest / latest meeting day (YYYY-MM-DD), "" if none
  maxKey: string;
  totalMeetings: number;
  dataAsOf: Date | null;          // the calendar subsystem's own freshness (Sheet1!AA1)
}

// Crossover — the session "guillotine": the last day a bill may be acted on in its chamber of origin
// (vision §3b). The front end can't derive it (no LIS access), so it's pinned per session from the
// published VA session calendar. We only ever mark a date we actually know — a wrong guillotine would
// mislead (vision §7, "never pretend"). TODO(backend): have bill_tracker stamp the session's crossover
// date into the completeness payload so this becomes structural instead of a constant.
export const CROSSOVER_BY_SESSION: Record<string, string> = {
  "20261": "2026-02-17", // 2026 Regular Session — Tue Feb 17 (last day to act in house of origin)
};

const SHEET1_TAB = "Sheet1";
const PROJECTION = "select A,B,C,D,E,F,G,J,L"; // Date,Time,SortTime,Status,Committee,Bill,Outcome,Origin,LegEventRoute
const FETCH_TIMEOUT_MS = 30000;               // the projected Sheet1 is ~5 MB

const META_ORIGINS = new Set(["system_alert", "system_metrics"]);
const LEDGER_COMMITTEE = "📋 Ledger Updates"; // [PLACEHOLDER "Ledger Updates"] the worker's admin collapse — these are NOT meetings (no time expectation); excluded from the calendar below.
const GOVERNOR_COMMITTEE = "🏛️ Governor";       // dated executive actions — not a meeting (out of scope v1)
// CANCELLED is the structural cancellation flag the worker derives from the LIS Schedule API's own
// `IsCancelled` field (calendar_worker.py ~L4936) → Sheet1 Status column. LIS placeholds a cancelled
// committee slot with an empty time, which is why most "Time TBA" rows were cancelled placeholders, not
// gatherings. BUT cancellation must be judged at the MEETING level, never the row: the flag is sometimes
// propagated onto rows for a slot where a meeting actually HAPPENED (real votes recorded — e.g. a
// subcommittee "reporting (10-Y 0-N)"). So we drop a meeting ONLY when it is cancelled AND carries no real
// meeting action (LegEventRoute=="meeting"); a cancelled slot with a recorded vote is kept (it occurred).
const CANCELLED_STATUS = "cancelled";
const MEETING_ROUTE = "meeting"; // the subsystem's verdict that a real gathering/vote happened in this row
// A time is non-concrete (can't place a meeting by clock time) for these worker placeholders.
const NON_CONCRETE = new Set(["", "nan", "none", "time tba", "tba", "journal entry", "ledger"]);
const BILL_RE = /^[HS][BJR]\d+$/; // VA bill ids: HB/SB/HJ/SJ/HR/SR + number (skeleton rows hold addresses)

function isConcreteTime(time: string): boolean {
  const t = time.trim().toLowerCase();
  if (NON_CONCRETE.has(t)) return false;
  if (t.startsWith("⏱")) return false; // ⏱️ [NO_SCHEDULE_MATCH] / [NO_CONVENE_ANCHOR]
  return true;
}

// The worker sometimes carries LIS's dynamic-time DESCRIPTION (e.g. "Immediately upon adjournment of House
// Education") instead of a clock time — this is exactly what the LIS website shows, so we keep it, but strip
// the trailing link markers / newlines the schedule feed appends so it reads as a clean time phrase.
function cleanTime(time: string): string {
  return time.split(/[\r\n]/)[0].replace(/\s*\((?:Agenda|View Meeting|Meeting Materials)\)\s*/gi, "").trim();
}

function normalizeBill(raw: string): string | null {
  const s = raw.trim().replace(/\s+/g, "").toUpperCase();
  return BILL_RE.test(s) ? s : null;
}

// Parse a clock string to minutes past midnight. Handles 12-hour ("7:30 AM", "9:00 a.m.", "~12:06 PM")
// and bare 24-hour ("08:00", "17:42"); returns null for relative/TBA strings that aren't a clock time.
function clockMinutes(t: string): number | null {
  const s = t.trim().replace(/^~/, "");
  const m = /^(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?/i.exec(s);
  if (m) {
    const h = (+m[1]) % 12;
    return (m[3].toLowerCase() === "p" ? h + 12 : h) * 60 + (+m[2]);
  }
  const h24 = /^(\d{1,2}):(\d{2})$/.exec(s); // SortTime is 24h
  return h24 ? (+h24[1]) * 60 + (+h24[2]) : null;
}

// Sort key — minutes past midnight. Prefer the DISPLAYED clock time so the agenda's order matches what the
// reader sees; fall back to the worker's SortTime for relative ("X min after adjournment") / TBA meetings
// whose display isn't a clock; last resort sorts to end of day.
function toMinutes(sortTime: string, displayTime: string): number {
  return clockMinutes(displayTime) ?? clockMinutes(sortTime) ?? (24 * 60 + 1);
}

async function fetchText(url: string, timeoutMs: number): Promise<string> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { cache: "no-store", signal: ctrl.signal });
    if (!res.ok) throw new Error(`gviz fetch failed: HTTP ${res.status}`);
    return await res.text();
  } catch (e) {
    throw new Error(ctrl.signal.aborted ? `calendar request timed out after ${timeoutMs / 1000}s` : String((e as Error)?.message || e));
  } finally {
    clearTimeout(timer);
  }
}

// Sheet1!AA1 is the calendar subsystem's public freshness marker (last fully-successful cycle, UTC) —
// the stable contract documented for exactly this. Optional: failure must not block the calendar.
async function fetchFreshness(): Promise<Date | null> {
  try {
    const url = `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=${SHEET1_TAB}&headers=0&range=AA1`;
    const txt = await fetchText(url, 8000);
    const cell = (parseCsv(txt)?.[0]?.[0] || "").trim();
    const d = cell ? new Date(cell) : null;
    return d && !isNaN(d.getTime()) ? d : null;
  } catch (e) {
    // Optional must not mean SILENT (Qodo): freshness is non-blocking, but operators/devs still need an
    // observable signal when Sheet1!AA1 can't be read — surface it rather than swallow (Standard #4).
    console.warn("calendar freshness (Sheet1!AA1) read failed; freshness shows 'unknown'", e);
    return null;
  }
}

// Session cache: the Calendar tab unmounts on tab-switch, so memoize the (~5 MB) load for the page's life
// — re-opening the tab is then instant and rapid toggles dedupe to one in-flight fetch. A full reload
// re-fetches (the only refresh path needed off-season; the data is static once the GA adjourns).
let _calPromise: Promise<CalendarData> | null = null;

export function loadCalendar(): Promise<CalendarData> {
  if (!_calPromise) {
    _calPromise = _loadCalendar().catch((e) => { _calPromise = null; throw e; }); // let a failed load retry
  }
  return _calPromise;
}

async function _loadCalendar(): Promise<CalendarData> {
  const url = `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=${SHEET1_TAB}&tq=${encodeURIComponent(PROJECTION)}`;
  // Freshness rides along in parallel; it never blocks or fails the calendar.
  const [text, dataAsOf] = await Promise.all([fetchText(url, FETCH_TIMEOUT_MS), fetchFreshness()]);

  const rows = parseCsv(text);
  const header = rows[0] ?? [];
  // Shape guard: a 200 that isn't our projected CSV (renamed tab, error page) must not parse to a silent
  // empty calendar. The projection's header is exactly these 9 names (…Origin col 7, LegEventRoute col 8).
  if ((header[0] || "").trim().toLowerCase() !== "date" || (header[8] || "").trim().toLowerCase() !== "legeventroute") {
    throw new Error("unexpected Sheet1 shape — calendar header didn't match (tab renamed, not shared, or an error page?)");
  }

  // Group rows into meetings keyed by (day, committee, time). Projected cols:
  // 0 Date · 1 Time · 2 SortTime · 3 Status · 4 Committee · 5 Bill · 6 Outcome · 7 Origin · 8 LegEventRoute
  const groups = new Map<string, Meeting>();
  // Per-meeting cancellation judgement (meeting-level, not row-level): was any row CANCELLED, and did any
  // row record a real meeting action? A meeting is dropped only when cancelled AND no real action occurred.
  const flags = new Map<string, { cancelled: boolean; held: boolean }>();
  for (let i = 1; i < rows.length; i++) {
    const r = rows[i];
    const origin = (r[7] || "").trim();
    if (META_ORIGINS.has(origin)) continue;
    const committee = (r[4] || "").trim();
    // The Ledger collapse (admin, no meeting) + executive actions + meta rows are not meetings. Everything
    // else is kept (parity with the LIS calendar) unless it's a cancelled placeholder (judged below).
    if (!committee || committee === LEDGER_COMMITTEE || committee === GOVERNOR_COMMITTEE) continue;
    const dt = parseLisDate(r[0]);
    if (!dt) continue;

    const rawTime = (r[1] || "").trim();
    const concrete = isConcreteTime(rawTime);
    const dk = dayKey(dt);
    const sortTime = (r[2] || "").trim();
    const key = `${dk}|${committee}|${sortTime}`;
    let m = groups.get(key);
    if (!m) {
      const chamber: Chamber | null = committee.startsWith("House") ? "House"
        : committee.startsWith("Senate") ? "Senate" : null;
      // Floor session markers vs committee meetings — see classifyMeetingKind (display-only; word-bounded).
      const kind: MeetingKind = classifyMeetingKind(committee);
      // [PLACEHOLDER "Time TBA"] honest display marker when LIS published no ScheduleTime — never a hidden
      // or guessed time; superseded below by a concrete time (L194) or LIS's verbatim Description (L203+).
      m = { dateKey: dk, committee, chamber, kind, time: concrete ? cleanTime(rawTime) : "Time TBA",
        tba: !concrete, minutes: toMinutes(sortTime, rawTime), bills: [] };
      groups.set(key, m);
      flags.set(key, { cancelled: false, held: false });
    } else if (concrete && m.tba) {
      m.time = cleanTime(rawTime); m.tba = false; m.minutes = toMinutes(sortTime, rawTime); // a real time supersedes TBA
    }
    const f = flags.get(key)!;
    if ((r[3] || "").trim().toLowerCase() === CANCELLED_STATUS) f.cancelled = true;
    if ((r[8] || "").trim().toLowerCase() === MEETING_ROUTE) f.held = true;
    const billRaw = (r[5] || "").trim();
    const bill = normalizeBill(billRaw);
    if (bill) {
      if (!m.bills.some((x) => x.bill === bill)) m.bills.push({ bill, action: (r[6] || "").trim() });
    } else if (m.tba && m.time === "Time TBA" && billRaw && billRaw.toLowerCase() !== "no agenda listed.") {
      // Skeleton schedule row: the worker copies LIS's verbatim Description into the Bill column
      // (calendar_worker.py ~L5082). When LIS published no ScheduleTime, that Description IS the time LIS
      // itself shows ("Immediately after Transportation & Public Safety"). We DISPLAY that structural field
      // verbatim instead of "Time TBA" — pure pass-through of an API-returned value, no marker-matching /
      // extraction / derivation (Standard #3: structural, trustworthy without intervention; if LIS rephrases
      // we just show the new phrasing). cleanTime only drops HTML-less link labels + newlines for display.
      const note = cleanTime(billRaw);
      if (note) m.time = note;
    }
  }

  // Bucket by day; drop cancelled placeholders (cancelled AND no real meeting action ever recorded there).
  // Sort meetings by time, bills by number within each meeting.
  const byDay = new Map<string, Meeting[]>();
  for (const [key, m] of groups) {
    const f = flags.get(key)!;
    if (f.cancelled && !f.held) continue; // cancelled, nothing happened → not on the calendar
    m.bills.sort((a, b) => a.bill.localeCompare(b.bill, undefined, { numeric: true }));
    (byDay.get(m.dateKey) ?? byDay.set(m.dateKey, []).get(m.dateKey)!).push(m);
  }
  for (const ms of byDay.values()) {
    ms.sort((a, b) => a.minutes - b.minutes || a.committee.localeCompare(b.committee));
  }

  const keys = [...byDay.keys()].sort();
  let totalMeetings = 0;
  for (const ms of byDay.values()) totalMeetings += ms.length; // kept meetings (cancelled placeholders dropped)
  return {
    byDay,
    minKey: keys[0] || "",
    maxKey: keys[keys.length - 1] || "",
    totalMeetings,
    dataAsOf,
  };
}
