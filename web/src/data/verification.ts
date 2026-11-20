// The operator Health tab's "Are we right?" panel (vision §7 trust layer). The 5-layer durability guard
// (docs/architecture/verification_durability.md) verifies the LIVE output against INDEPENDENT sources —
// reconciliation vs the official MinutesBook, completeness vs LIS's own calendar — but it runs in GitHub
// Actions and only ALERTS on failure, so the owner never SEES the green. This surfaces each guard's latest
// verdict. Since 2026-11-20 the verdict comes from Guard_Status (the trust-surface guard reads GitHub with the
// Actions token and publishes it), not from the public GitHub API in the browser: the repo is going private and
// a token can never ship in a browser bundle (docs/ideas/going_private.md A2). Layer 1 (the in-cycle circuit
// breaker) is the live chip elsewhere on the tab; this covers layers 2–5.

import { STATE } from "../states";
import type { GuardLoad } from "./guards";
import { verdictOf, type GuardState } from "./guard_rules";

export type { GuardState };


export interface GuardRun {
  key: string;        // workflow filename (the API matches on this)
  label: string;      // human name
  proves: string;     // what it INDEPENDENTLY verifies (the trust statement)
  cadence: "daily" | "weekly";
  status: GuardState;
  lastRun: Date | null;
  stale: boolean;     // overdue against its own rhythm → the guard itself stopped (its own failure)
  url: string | null; // link to the run
}

// The four session-agnostic guards (layers 2–5). Order = strongest "are we right?" first.
const GUARDS: { key: string; label: string; proves: string; cadence: "daily" | "weekly" }[] = [
  { key: "completeness_tripwire.yml", label: "Completeness", cadence: "weekly",
    proves: `no hidden meeting — every meeting on ${STATE.sourceName}'s own calendar appears in our data` },
  { key: "legevent_reconcile.yml", label: "Reconciliation", cadence: "weekly",
    proves: "our committee votes match the official MinutesBook — a source the pipeline never touches" },
  { key: "accuracy_sentinel.yml", label: "Accuracy sentinel", cadence: "daily",
    proves: "Section-9 = 0 + structural coverage, re-derived from the live sheet daily" },
  { key: "sustainability_audit.yml", label: "Sustainability audit", cadence: "weekly",
    proves: "the time-bomb sweep — capacity, schema drift, retention, dedup determinism" },
];

/** The four guards' verdicts, from the trust-surface guard's Guard_Status rows. Pure: no network. A missing row or
 *  an unreadable tab is "unknown" (shown red) — allowed not to know, never a fake green (vision §7). */
export function guardsFromStatus(load: GuardLoad | null): GuardRun[] {
  const rows = load && load.status === "ok" ? load.rows : [];
  return GUARDS.map((g): GuardRun => {
    const row = rows.find((r) => r.check === `workflow:${g.key}`);
    const v = verdictOf(row?.state);
    return { key: g.key, label: g.label, proves: g.proves, cadence: g.cadence, status: v.status, stale: v.stale,
             lastRun: row?.lastRun ?? null, url: row?.url || null };
  });
}
