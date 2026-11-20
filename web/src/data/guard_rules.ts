// Pure rules for the Health page's job verdicts, read from the Guard_Status tab.
//
// WHY (2026-11-20, docs/ideas/going_private.md A2): the page used to read each job's run history straight from
// the PUBLIC GitHub Actions API in the browser, with no token. A private repo answers that with 404, and a token
// can never ship in a browser bundle. The trust-surface guard already reads GitHub every 6 h with the Actions
// token (actions: read) and writes Guard_Status; it now also writes each job's last run and its last 10 results,
// and the page reads them through the signed-in Worker like every other sheet read.
//
// Dependency-free on purpose: CI transpiles this one file alone (web/tools/ts2mjs.mjs) for its regression test.

export type RunMark = "pass" | "fail" | "none";
export type GuardState = "pass" | "fail" | "running" | "unknown";

/** Guard_Status's `Recent` cell ("pfn…", newest first) -> marks. null = the column is absent (an older guard run)
 *  or the cell is not that shape: the page then shows "history unreadable", never an invented strip. */
export function parseRecent(cell: string | undefined, present: boolean): RunMark[] | null {
  if (!present) return null;
  const s = (cell ?? "").trim();
  if (!/^[pfn]{0,30}$/.test(s)) return null;
  return Array.from(s, (c): RunMark => (c === "p" ? "pass" : c === "f" ? "fail" : "none"));
}

/** The guard's state for one workflow -> the Health ring's verdict. `overdue` keeps its last good result but is
 *  stale (judge_runs checks failures BEFORE overdue, so an overdue job's last real run succeeded). Anything the guard
 *  could not judge (never_run, not_yet_due, disabled, unknown, or no row at all) is unknown — never a pass. */
export function verdictOf(state: string | undefined): { status: GuardState; stale: boolean } {
  switch (state) {
    case "ok": return { status: "pass", stale: false };
    case "overdue": return { status: "pass", stale: true };
    case "failing":
    case "never_succeeded": return { status: "fail", stale: false };
    case "running": return { status: "running", stale: false };
    default: return { status: "unknown", stale: false };
  }
}
