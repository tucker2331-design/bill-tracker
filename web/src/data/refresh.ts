import { SPREADSHEET_ID, BILL_TRACKER_TAB } from "../config";

// The CHEAP half of the freshness-gate (docs/ideas/auto_refresh_on_new_data): a single-cell read (~22 bytes)
// that tells us whether a feed was rewritten, WITHOUT re-downloading the 6.7 MB bill payload or the 5.7 MB
// calendar payload. The App polls these on an interval + on window-focus; only when a stamp actually advances
// does it do the full re-fetch. Off-season (data static for days) this costs a few bytes a minute and the
// gate never opens.
//
//   Bill feed:     Bill_Tracker!O2  — the worker's per-cycle "Data As Of (UTC)" stamp on the first data row.
//   Calendar feed: Sheet1!AA1       — the calendar worker's last-fully-successful-cycle UTC.
//
// We compare the RAW STRING, not a parsed Date: any change means "reload". A blank/failed read returns ""
// and the caller treats "" as "unknown — don't trigger a refresh", so a transient network blip never causes
// a spurious reload (it can only ever MISS a refresh, never invent one).
const SHEET1 = "Sheet1";
const CELL_TIMEOUT_MS = 10000;

async function readCell(tab: string, cell: string): Promise<string> {
  const url = `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv`
    + `&sheet=${encodeURIComponent(tab)}&headers=0&range=${cell}`;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), CELL_TIMEOUT_MS);
  try {
    const res = await fetch(url, { cache: "no-store", signal: ctrl.signal });
    if (!res.ok) return "";
    // gviz CSV wraps a single value in quotes ("…"); strip one surrounding pair.
    return (await res.text()).trim().replace(/^"(.*)"$/s, "$1").trim();
  } catch {
    return ""; // unknown — the caller must not read this as a change
  } finally {
    clearTimeout(timer);
  }
}

export const fetchBillStamp = (): Promise<string> => readCell(BILL_TRACKER_TAB, "O2");
export const fetchCalendarStamp = (): Promise<string> => readCell(SHEET1, "AA1");
