import { gvizCsvUrl, BILL_TRACKER_TAB } from "../config";
import type { Bill, BillData, Completeness, FloorEvent, HistoryRow, LatestVote, Meeting, Outcome, Chamber } from "./types";

// --- CSV (RFC4180) parser ----------------------------------------------------------------------
// gviz `tqx=out:csv` quotes any field containing a comma/quote/newline and escapes quotes as "".
// The completeness cell (R1) is a JSON blob full of commas, so a real parser (not split-on-comma)
// is required. State machine: handles quoted fields, "" escapes, and newlines inside quotes.
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }   // escaped quote
        else inQuotes = false;
      } else field += c;
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      row.push(field); field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;          // CRLF
      row.push(field); field = "";
      rows.push(row); row = [];
    } else field += c;
  }
  // flush the trailing field/row (no terminating newline)
  if (field.length > 0 || row.length > 0) { row.push(field); rows.push(row); }
  return rows;
}

function jsonOr<T>(raw: string | undefined, fallback: T): T {
  if (!raw) return fallback;
  try { return JSON.parse(raw) as T; } catch { return fallback; }
}

// Header column order written by bill_tracker.write_bill_tracker (A..R); completeness lives at T1.
// House/Senate Floor were APPENDED (Q,R) so cols A..P kept their indices; completeness moved to T.
const COL = {
  bill: 0, title: 1, status: 2, outcome: 3, patron: 4, patronId: 5, chamber: 6, crossed: 7,
  lastCommittee: 8, referrals: 9, lastAction: 10, latestVote: 11, upcoming: 12, history: 13,
  dataAsOf: 14, source: 15, floorHouse: 16, floorSenate: 17,
} as const;
const COMPLETENESS_COL = 19;         // T (S=18 is the empty spacer)
const LEGACY_COMPLETENESS_COL = 17;  // R — the pre-Floor-columns position, read as a migration fallback

// Validate a floor cell against the known enum — an unrecognized value (schema drift, the pre-migration
// empty column) reads as "" (no floor event), never a guessed stage ("allowed not to know, never pretend").
// Drift is NOT silent (Qodo #191 / pre-push audit #15): a non-empty value outside the enum is a schema-drift
// signal (the worker started writing a new vocabulary) — warn once per value so it can't collapse into a
// legitimate "no floor event" unnoticed.
const _floorDriftWarned = new Set<string>();
const floorEvent = (v: string | undefined): FloorEvent => {
  const t = (v || "").trim().toLowerCase();
  if (t === "passed" || t === "defeated") return t;
  if (t && !_floorDriftWarned.has(t)) {
    _floorDriftWarned.add(t);
    console.warn(`Bill_Tracker floor column carries an unrecognized value ${JSON.stringify(t)} — treating as "no floor event"; the worker's floor vocabulary may have drifted.`);
  }
  return "";
};

const OUTCOMES = new Set<Outcome>([
  "signed", "vetoed", "dead", "carried_over", "awaiting_governor", "in_progress",
]);

function toBill(r: string[]): Bill | null {
  const bill = (r[COL.bill] || "").trim();
  if (!bill || bill.toLowerCase() === "bill") return null;   // skip blanks / a stray header echo
  const outcomeRaw = (r[COL.outcome] || "").trim() as Outcome;
  const chamberRaw = (r[COL.chamber] || "").trim();
  // Trust the structural chamber field, but if it's ever unexpected, derive from the bill-number
  // prefix (H*/S*) rather than blind-defaulting to House and skewing the lane counts (CodeRabbit #164).
  const chamber: Chamber = chamberRaw === "Senate" || chamberRaw === "House"
    ? chamberRaw
    : (bill[0]?.toUpperCase() === "S" ? "Senate" : "House");
  return {
    bill,
    title: (r[COL.title] || "").trim(),
    statusLis: (r[COL.status] || "").trim(),
    outcome: OUTCOMES.has(outcomeRaw) ? outcomeRaw : "in_progress",
    patron: (r[COL.patron] || "").trim(),
    patronId: (r[COL.patronId] || "").trim(),
    chamber,
    crossedOver: (r[COL.crossed] || "").trim().toLowerCase() === "yes",
    floorHouse: floorEvent(r[COL.floorHouse]),
    floorSenate: floorEvent(r[COL.floorSenate]),
    lastCommittee: (r[COL.lastCommittee] || "").trim(),
    referrals: parseInt(r[COL.referrals] || "0", 10) || 0,
    latestVote: jsonOr<LatestVote>(r[COL.latestVote], { tally: "", location: "", date: "" }),
    upcoming: jsonOr<Meeting[]>(r[COL.upcoming], []),
    lastAction: (r[COL.lastAction] || "").trim(),
    history: jsonOr<HistoryRow[]>(r[COL.history], []),
    dataAsOf: (r[COL.dataAsOf] || "").trim(),
    source: (r[COL.source] || "LIS").trim(),
  };
}

// VA session code for the LIS bill link. PREFER the authoritative value the backend can stamp into
// the completeness payload (`session_code`); fall back to inferring the regular session `${year}1`
// (2026 → "20261") from the data's freshness year. (Standard #5: derive, don't hardcode — the
// inference is the documented fallback only, used until bill_tracker stamps it.)
function inferSessionCode(dataAsOf: Date | null): string {
  const year = (dataAsOf ?? new Date()).getUTCFullYear();
  return `${year}1`;
}

const FETCH_TIMEOUT_MS = 20000;

export async function loadBillData(): Promise<BillData> {
  // Bound the fetch so a stalled request can't leave the app loading forever.
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
  let text: string;
  try {
    const res = await fetch(gvizCsvUrl(BILL_TRACKER_TAB), { cache: "no-store", signal: ctrl.signal });
    if (!res.ok) throw new Error(`gviz fetch failed: HTTP ${res.status}`);
    text = await res.text();
  } catch (e) {
    throw new Error(ctrl.signal.aborted ? `data request timed out after ${FETCH_TIMEOUT_MS / 1000}s` : String((e as Error)?.message || e));
  } finally {
    clearTimeout(timer);
  }

  const rows = parseCsv(text);
  // Shape sanity-check: a 200 that isn't our CSV (an HTML error/login page, a renamed tab) must NOT
  // be parsed into a silent empty/mislabelled dataset. Require the known header.
  const header = rows[0] ?? [];
  if ((header[0] || "").trim().toLowerCase() !== "bill" || header.length < 16) {
    throw new Error("unexpected Bill_Tracker shape — header row didn't match (sheet renamed, not shared, or an error page?)");
  }
  // Read completeness at its new column (T), falling back to the OLD position (R) during the schema-
  // migration window — after this front-end deploys but BEFORE the bill worker first rewrites the sheet
  // with the appended Passed House/Senate cols, completeness is still at R. `||` picks whichever cell holds
  // the JSON; jsonOr returns null for a non-JSON cell (a stray "yes"/"no"), so it can't misparse.
  const completeness = jsonOr<Completeness | null>(header[COMPLETENESS_COL] || header[LEGACY_COMPLETENESS_COL], null);

  const bills: Bill[] = [];
  for (let i = 1; i < rows.length; i++) {
    const b = toBill(rows[i]);
    if (b) bills.push(b);
  }

  // "Data as of" = the completeness stamp if present, else the FRESHEST per-bill timestamp (not row 0,
  // which could be stale if row order ever changes).
  let dataAsOf: Date | null = null;
  const fromStamp = completeness?.checked_at_utc ? new Date(completeness.checked_at_utc) : null;
  if (fromStamp && !isNaN(fromStamp.getTime())) {
    dataAsOf = fromStamp;
  } else {
    let max = 0;
    for (const b of bills) { const t = Date.parse(b.dataAsOf); if (!isNaN(t) && t > max) max = t; }
    if (max > 0) dataAsOf = new Date(max);
  }

  const stamped = (completeness?.session_code || "").trim();
  const sessionCode = /^\d{5}$/.test(stamped) ? stamped : inferSessionCode(dataAsOf);

  return { bills, completeness, dataAsOf, sessionCode };
}
