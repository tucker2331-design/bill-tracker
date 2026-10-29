// The trust-surface guard's verdicts (`Guard_Status`, written every 6 h by tools/verification/trust_surface_guard.py
// from the SAME verdicts that open/close incidents in the days-clean ledger) + each scheduled job's last runs.
// Guard_Status is read through the signed-in Worker; run history comes from the public GitHub Actions API (the
// same read-only, token-free path verification.ts uses). Any failed read is "unknown" — which the page shows red.
import { sheetUrl, headerMatches } from "../config";
import { apiFetch } from "../state/auth";
import { parseCsv } from "./gviz";

export const GUARD_HEADER = ["CheckedUTC", "Check", "Label", "State", "SinceUTC", "LastSuccessUTC", "FailuresInARow",
  "ExpectedEvery", "Detail", "URL"] as const;
/** Mirrors trust_surface_guard.STATES_OK: these states open no incident. */
export const GUARD_OK = new Set(["ok", "disabled", "running", "not_yet_due"]);

export interface GuardRow {
  checked: Date | null; check: string; label: string; state: string; since: Date | null; lastSuccess: Date | null;
  fails: number; every: string; detail: string; url: string;
}
export type GuardLoad = { status: "ok"; rows: GuardRow[] } | { status: "unavailable" };

const d = (s: string) => { const t = Date.parse((s || "").trim()); return Number.isFinite(t) ? new Date(t) : null; };

export async function loadGuardStatus(): Promise<GuardLoad> {
  try {
    const res = await apiFetch(sheetUrl("Guard_Status"), { cache: "no-store" });
    if (!res.ok) return { status: "unavailable" };
    const rows = parseCsv(await res.text());
    if (!headerMatches(rows[0], GUARD_HEADER)) return { status: "unavailable" };   // gviz's wrong-sheet trap
    return { status: "ok", rows: rows.slice(1).filter((r) => (r[1] || "").trim()).map((r) => ({
      checked: d(r[0]), check: r[1].trim(), label: (r[2] || "").trim(), state: (r[3] || "").trim(),
      since: d(r[4]), lastSuccess: d(r[5]), fails: parseInt(r[6] || "0", 10) || 0, every: (r[7] || "").trim(),
      detail: (r[8] || "").trim(), url: (r[9] || "").trim(),
    })) };
  } catch (e) {
    console.warn("Guard_Status: read failed", e);
    return { status: "unavailable" };
  }
}

export type RunMark = "pass" | "fail" | "none";
const REPO = "tucker2331-design/bill-tracker";
const FETCH_TIMEOUT_MS = 12000;

/** Last `n` completed runs of one workflow file, newest first; null = the history could not be read. */
export async function loadRuns(file: string, n = 10): Promise<RunMark[] | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${file}/runs?status=completed&per_page=${n}`,
      { signal: ctrl.signal, headers: { Accept: "application/vnd.github+json" } });
    if (!res.ok) return null;
    const body = await res.json();
    return (body?.workflow_runs ?? []).map((r: { conclusion?: string }) =>
      r.conclusion === "success" ? "pass" : r.conclusion === "failure" || r.conclusion === "timed_out" ? "fail" : "none");
  } catch (e) {
    console.warn(`run history for ${file}: read failed`, e);
    return null;
  } finally {
    clearTimeout(timer);
  }
}
