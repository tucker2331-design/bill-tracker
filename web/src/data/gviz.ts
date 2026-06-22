import { gvizCsvUrl, BILL_TRACKER_TAB } from "../config";
import type { Bill, BillData, Completeness, HistoryRow, LatestVote, Meeting, Outcome, Chamber } from "./types";

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

// Header column order written by bill_tracker.write_bill_tracker (A..P); completeness lives at R1.
const COL = {
  bill: 0, title: 1, status: 2, outcome: 3, patron: 4, patronId: 5, chamber: 6, crossed: 7,
  lastCommittee: 8, referrals: 9, lastAction: 10, latestVote: 11, upcoming: 12, history: 13,
  dataAsOf: 14, source: 15,
} as const;
const COMPLETENESS_COL = 17;   // R (Q=16 is the empty spacer)

const OUTCOMES = new Set<Outcome>([
  "signed", "vetoed", "dead", "carried_over", "awaiting_governor", "in_progress",
]);

function toBill(r: string[]): Bill | null {
  const bill = (r[COL.bill] || "").trim();
  if (!bill || bill.toLowerCase() === "bill") return null;   // skip blanks / a stray header echo
  const outcomeRaw = (r[COL.outcome] || "").trim() as Outcome;
  const chamberRaw = (r[COL.chamber] || "").trim();
  return {
    bill,
    title: (r[COL.title] || "").trim(),
    statusLis: (r[COL.status] || "").trim(),
    outcome: OUTCOMES.has(outcomeRaw) ? outcomeRaw : "in_progress",
    patron: (r[COL.patron] || "").trim(),
    patronId: (r[COL.patronId] || "").trim(),
    chamber: (chamberRaw === "Senate" ? "Senate" : "House") as Chamber,
    crossedOver: (r[COL.crossed] || "").trim().toLowerCase() === "yes",
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

// VA session code for the LIS bill link: regular session = `${year}1` (2026 → "20261"). Inferred from
// the data's freshness year for now; a future backend tweak can stamp it explicitly in the payload.
function inferSessionCode(dataAsOf: Date | null): string {
  const year = (dataAsOf ?? new Date()).getUTCFullYear();
  return `${year}1`;
}

export async function loadBillData(): Promise<BillData> {
  const res = await fetch(gvizCsvUrl(BILL_TRACKER_TAB), { cache: "no-store" });
  if (!res.ok) throw new Error(`gviz fetch failed: HTTP ${res.status}`);
  const rows = parseCsv(await res.text());
  if (rows.length === 0) throw new Error("empty Bill_Tracker sheet");

  const header = rows[0];
  const completeness = jsonOr<Completeness | null>(header[COMPLETENESS_COL], null);

  const bills: Bill[] = [];
  for (let i = 1; i < rows.length; i++) {
    const b = toBill(rows[i]);
    if (b) bills.push(b);
  }

  // Freshest record timestamp = the trust header's "data as of".
  let dataAsOf: Date | null = null;
  const stamp = completeness?.checked_at_utc || bills[0]?.dataAsOf;
  if (stamp) { const d = new Date(stamp); if (!isNaN(d.getTime())) dataAsOf = d; }

  return { bills, completeness, dataAsOf, sessionCode: inferSessionCode(dataAsOf) };
}
