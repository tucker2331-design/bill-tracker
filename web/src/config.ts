// Static config. The front end is a $0 static SPA (Cloudflare Pages) that reads the worker's output
// straight from the Google Sheet via gviz — the same proven, auth-free path the X-Ray uses. The
// "Mastermind DB" sheet must be link-readable (Anyone with the link → Viewer) for gviz to serve it.
export const SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM";
export const BILL_TRACKER_TAB = "Bill_Tracker";

// The state this deployment serves. ⚠ Standard #6 seam, flagged deliberately rather than buried: ONE
// deployment is meant to serve every state with `state` as a data dimension (migrations/0001_init.sql),
// so this constant is the temporary stand-in for "which state is this user in", NOT a licence to hardcode
// 'VA' at call sites. Every write already carries `state` explicitly; when state #2 lands this becomes a
// value on the user's profile and this constant disappears. Keeping it in ONE place is what makes that a
// deletion rather than a hunt.
export const APP_STATE = "VA";

// Google sign-in. PUBLIC by design — a client id ships in the page for every "Sign in with Google" button
// on the web, exactly like SPREADSHEET_ID above. It lives here rather than in a VITE_ env var because this
// app has no .env pattern at all: introducing one would mean a build-time setting in Cloudflare's dashboard
// that has to be remembered on every redeploy and every new environment, and whose absence fails at RUNTIME
// with a blank button. A committed constant cannot be forgotten.
// The client SECRET belongs to an authorization-code flow we deliberately do not use, and is nowhere in this
// repo. Must match GOOGLE_CLIENT_ID in wrangler.toml — the Worker checks the token's `aud` against it.
export const GOOGLE_CLIENT_ID =
  "831223695835-cqd2fmjq3l61jc1t6pr9elobra0imhf5.apps.googleusercontent.com";

// gviz CSV endpoint for a tab (matches pages/ray2.py load_sheet_df).
export const gvizCsvUrl = (tab: string) =>
  `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=${encodeURIComponent(tab)}`;

/**
 * gviz's most dangerous behaviour, in one place so every reader can guard against it.
 *
 * **Asking for a tab that does not exist returns HTTP 200 with the CSV of the FIRST sheet.** No error, no
 * status flag, no hint — just a different table wearing the right content-type. Shipped to production
 * 2026-07-28: `Incident_Log` had never been created, gviz served 11.2 MB of the calendar, column 2
 * (`SortTime`) was read as the incident CLASS, and the Health tab reported thousands of simultaneous open
 * incidents. Nothing in the stack noticed, because the data PARSED.
 *
 * So a reader must not trust the tab name it asked for — it must confirm the header it got back
 * (Standard #3: structural identity, not a hopeful assumption). Verified 2026-07-28: of the four tabs this
 * app reads, `Bill_Tracker`, `Metrics_History` and `Sheet1` exist; `Incident_Log` did not.
 *
 * @returns true when `row` starts with `expected`, cell for cell.
 */
export const headerMatches = (row: string[] | undefined, expected: readonly string[]): boolean =>
  !!row && expected.every((h, i) => (row[i] || "").trim() === h);

// Deterministic LIS bill-detail link (recovered shadow_v2.py:535) — no API, not brittle.
// Uses the DYNAMIC 5-digit session code (never hardcode 20261).
export const lisBillUrl = (sessionCode: string, billNumber: string) =>
  `https://lis.virginia.gov/bill-details/${sessionCode}/${billNumber}`;

// "Stale" threshold for the trust header. The worker runs every few hours; anything older than this
// is surfaced red. Generous off-season; the in-session bar is the worker's own freshness marker.
export const STALE_AFTER_HOURS = 12;
