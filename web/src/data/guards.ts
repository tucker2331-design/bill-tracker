// The trust-surface guard's verdicts (`Guard_Status`, written every 6 h by tools/verification/trust_surface_guard.py
// from the SAME verdicts that open/close incidents in the days-clean ledger), including each scheduled job's last
// run and its last 10 results. All of it is read through the signed-in Worker: nothing here calls GitHub from the
// browser, so the page keeps working with the repo private (docs/ideas/going_private.md A2). Any failed read is
// "unavailable" / "unknown" — which the page shows red.
import { sheetUrl, headerMatches } from "../config";
import { apiFetch } from "../state/auth";
import { parseCsv } from "./gviz";
import { parseRecent, type RunMark } from "./guard_rules";

export type { RunMark };

export const GUARD_HEADER = ["CheckedUTC", "Check", "Label", "State", "SinceUTC", "LastSuccessUTC", "FailuresInARow",
  "ExpectedEvery", "Detail", "URL"] as const;
/** Appended by the guard on 2026-11-20. Optional: a sheet written by an older guard lacks them, and the page then
 *  says "history unreadable" for the strip instead of guessing. */
export const GUARD_HEADER_RUNS = ["LastRunUTC", "Recent"] as const;
/** Mirrors trust_surface_guard.STATES_OK: these states open no incident. */
export const GUARD_OK = new Set(["ok", "disabled", "running", "not_yet_due"]);

export interface GuardRow {
  checked: Date | null; check: string; label: string; state: string; since: Date | null; lastSuccess: Date | null;
  fails: number; every: string; detail: string; url: string;
  /** Newest completed run that actually ran; null when the guard did not publish it. */
  lastRun: Date | null;
  /** Last 10 completed runs, newest first; null when the guard did not publish them (history unreadable). */
  recent: RunMark[] | null;
}
export type GuardLoad = { status: "ok"; rows: GuardRow[] } | { status: "unavailable" };

const d = (s: string) => { const t = Date.parse((s || "").trim()); return Number.isFinite(t) ? new Date(t) : null; };

export async function loadGuardStatus(): Promise<GuardLoad> {
  try {
    const res = await apiFetch(sheetUrl("Guard_Status"), { cache: "no-store" });
    if (!res.ok) return { status: "unavailable" };
    const rows = parseCsv(await res.text());
    if (!headerMatches(rows[0], GUARD_HEADER)) return { status: "unavailable" };   // gviz's wrong-sheet trap
    const runs = headerMatches(rows[0].slice(GUARD_HEADER.length), GUARD_HEADER_RUNS);
    return { status: "ok", rows: rows.slice(1).filter((r) => (r[1] || "").trim()).map((r) => ({
      checked: d(r[0]), check: r[1].trim(), label: (r[2] || "").trim(), state: (r[3] || "").trim(),
      since: d(r[4]), lastSuccess: d(r[5]), fails: parseInt(r[6] || "0", 10) || 0, every: (r[7] || "").trim(),
      detail: (r[8] || "").trim(), url: (r[9] || "").trim(),
      lastRun: runs ? d(r[10]) : null, recent: parseRecent(r[11], runs),
    })) };
  } catch (e) {
    console.warn("Guard_Status: read failed", e);
    return { status: "unavailable" };
  }
}
