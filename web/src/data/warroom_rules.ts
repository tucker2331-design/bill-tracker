// War Room rules, kept free of runtime imports so a bare-node golden can run the REAL code
// (web/tools/ts2mjs.mjs; test: web/src/data/__tests__/warroom.regression.mjs).
//
// 1. The served calls (tools/calibration/serve_calls.py -> the private `War_Room_Calls` tab, one row per bill).
// 2. The four list groups and the order inside each (owner brief, 2026-10-29).
// Nothing here writes a sentence per case (P25): every string the page shows is a fixed template over these fields.

export type Call = "yes" | "no" | "cant_call";

export interface MemberCall {
  who: string;
  party: string;
  p: number;                                  // the model's chance of a yes, 0..1
  call: Call;                                 // yes / no only when |p - .5| >= .31 (pre-registered); else cant_call
  actual: "yes" | "no" | "";                  // the recorded ballot (replay); "" when the vote has not happened
  ev: Record<string, [number, number]>;       // k-of-n inputs measured BEFORE the vote (mpat, mroom, sim, msubj)
}

export interface BillCalls {
  bill: string; session: string; room: string; voteDate: string;
  ballots: number; yesNeeded: number; calledYes: number; calledNo: number; cantCall: number; actualYes: number;
  members: MemberCall[];
}

export interface CallsSummary {
  mode: string; testYear: number; callEdge: number;
  ballots: number; called: number; calledRight: number; cantCall: number; bills: number; generatedUtc: string;
}

export type CallsLoad =
  | { status: "ok"; byBill: Map<string, BillCalls>; summary: CallsSummary | null }
  | { status: "unavailable"; reason: "no_tab" | "bad_header" | "empty" };

export const CALLS_HEADER = ["Bill", "Session", "Room", "VoteDate", "Ballots", "YesNeeded", "CalledYes", "CalledNo",
  "CantCall", "ActualYes", "Members (JSON)"] as const;
const SUMMARY_COL = 12;                       // M1, clear of the data columns (serve_calls.SUMMARY_CELL)

const int = (s: string | undefined) => { const n = parseInt((s || "").trim(), 10); return Number.isFinite(n) ? n : 0; };
const CALLS = new Set<Call>(["yes", "no", "cant_call"]);

function members(raw: string | undefined): MemberCall[] | null {
  try {
    const v = JSON.parse(raw || "");
    if (!Array.isArray(v)) return null;
    return v.filter((m) => m && typeof m.who === "string" && CALLS.has(m.call)).map((m) => ({
      who: m.who, party: String(m.party || ""), p: Number(m.p), call: m.call as Call,
      actual: m.actual === "yes" || m.actual === "no" ? m.actual : "",
      ev: m.ev && typeof m.ev === "object" ? m.ev : {},
    }));
  } catch {
    return null;                              // an unreadable row is counted by the caller, never shown as calls
  }
}

function summary(cell: string | undefined): CallsSummary | null {
  try {
    const s = JSON.parse(cell || "");
    if (!s || typeof s.called !== "number") return null;
    return { mode: String(s.mode || ""), testYear: Number(s.test_year), callEdge: Number(s.call_edge),
      ballots: s.ballots, called: s.called, calledRight: s.called_right, cantCall: s.cant_call, bills: s.bills,
      generatedUtc: String(s.generated_utc || "") };
  } catch {
    return null;
  }
}

/** Parse the whole tab. The header is CONFIRMED, cell for cell (gviz serves the first sheet for a missing tab). */
export function parseCallsGrid(rows: string[][]): CallsLoad {
  const head = rows[0];
  if (!head) return { status: "unavailable", reason: "empty" };
  if (!CALLS_HEADER.every((h, i) => (head[i] || "").trim() === h)) return { status: "unavailable", reason: "bad_header" };
  const byBill = new Map<string, BillCalls>();
  let unreadable = 0;
  for (const r of rows.slice(1)) {
    const bill = (r[0] || "").trim();
    if (!bill) continue;                      // empty Sheets padding below the data, not a row
    const m = members(r[10]);
    if (!m) { unreadable++; continue; }       // counted and reported below
    byBill.set(`${(r[1] || "").trim()}|${bill}`, {
      bill, session: (r[1] || "").trim(), room: (r[2] || "").trim(), voteDate: (r[3] || "").trim(),
      ballots: int(r[4]), yesNeeded: int(r[5]), calledYes: int(r[6]), calledNo: int(r[7]), cantCall: int(r[8]),
      actualYes: int(r[9]), members: m,
    });
  }
  if (unreadable) console.warn(`War_Room_Calls: ${unreadable} row(s) unreadable — those bills show "can't call".`);
  return { status: "ok", byBill, summary: summary(head[SUMMARY_COL]) };
}

/** The calls for one of the app's bills. The tab keys sessions the Open States way ("2026"); the app uses LIS's
 *  5-digit code ("20261" = 2026 regular). Only the REGULAR session maps; a special session never borrows its calls. */
export function callsFor(byBill: Map<string, BillCalls>, bill: string, sessionCode: string): BillCalls | null {
  const m = /^(\d{4})1$/.exec(sessionCode);
  return m ? byBill.get(`${m[1]}|${bill}`) ?? null : null;
}

// ── the list ─────────────────────────────────────────────────────────────────────────────────────────────────────
export type WrGroup = "next7" | "later" | "none" | "decided";
export const WR_GROUPS: { id: WrGroup; label: string }[] = [
  { id: "next7", label: "Heard in the next 7 days" },
  { id: "later", label: "Scheduled later" },
  { id: "none", label: "Nothing scheduled" },
  { id: "decided", label: "Decided" },
];

const DECIDED = new Set(["signed", "vetoed", "dead", "carried_over"]);

/** "YYYY-MM-DD" from an ISO or M/D/YYYY date; "" when unreadable (then the bill counts as nothing scheduled). */
export function dateKeyOf(raw: string | undefined): string {
  const s = (raw || "").trim();
  let m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(s);
  if (m) return `${m[1]}-${m[2].padStart(2, "0")}-${m[3].padStart(2, "0")}`;
  m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(s);
  return m ? `${m[3]}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}` : "";
}

const plusDays = (key: string, n: number) => {
  const [y, mo, d] = key.split("-").map(Number);
  const t = new Date(Date.UTC(y, mo - 1, d + n));
  return `${t.getUTCFullYear()}-${String(t.getUTCMonth() + 1).padStart(2, "0")}-${String(t.getUTCDate()).padStart(2, "0")}`;
};

/** Decided bills are decided whatever the calendar says; otherwise the next hearing date sorts the bill. */
export function groupOf(outcome: string, nextDate: string, today: string): WrGroup {
  if (DECIDED.has(outcome)) return "decided";
  const k = dateKeyOf(nextDate);
  if (!k || k < today) return "none";
  return k <= plusDays(today, 7) ? "next7" : "later";
}

export interface WrItem { bill: string; calls: BillCalls | null }

const byNumber = (a: WrItem, b: WrItem) => a.bill.localeCompare(b.bill, undefined, { numeric: true });

/** Inside a group with a next room: least likely to pass first — most called-yes still NEEDED, then most called
 *  no, then most can't call. A bill that already has enough called yes needs 0 and so falls to the bottom. Bills
 *  with no member data cannot be ranked and follow, in bill-number order. Groups with no next room keep bill-number
 *  order. A structural ordering of counts, never a judgement (P27). */
export function sortGroup(items: WrItem[], group: WrGroup): WrItem[] {
  if (group === "none" || group === "decided") return [...items].sort(byNumber);
  const need = (c: BillCalls) => Math.max(0, c.yesNeeded - c.calledYes);
  return [...items].sort((a, b) => {
    if (!a.calls || !b.calls) return a.calls ? -1 : b.calls ? 1 : byNumber(a, b);
    return need(b.calls) - need(a.calls) || b.calls.calledNo - a.calls.calledNo
      || b.calls.cantCall - a.calls.cantCall || byNumber(a, b);
  });
}
