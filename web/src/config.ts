// Static config. The front end is a $0 static SPA (Cloudflare Pages) that reads the worker's output
// straight from the Google Sheet via gviz — the same proven, auth-free path the X-Ray uses. The
// "Mastermind DB" sheet must be link-readable (Anyone with the link → Viewer) for gviz to serve it.
export const SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM";
export const BILL_TRACKER_TAB = "Bill_Tracker";

// gviz CSV endpoint for a tab (matches pages/ray2.py load_sheet_df).
export const gvizCsvUrl = (tab: string) =>
  `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=${encodeURIComponent(tab)}`;

// Deterministic LIS bill-detail link (recovered shadow_v2.py:535) — no API, not brittle.
// Uses the DYNAMIC 5-digit session code (never hardcode 20261).
export const lisBillUrl = (sessionCode: string, billNumber: string) =>
  `https://lis.virginia.gov/bill-details/${sessionCode}/${billNumber}`;

// "Stale" threshold for the trust header. The worker runs every few hours; anything older than this
// is surfaced red. Generous off-season; the in-session bar is the worker's own freshness marker.
export const STALE_AFTER_HOURS = 12;
