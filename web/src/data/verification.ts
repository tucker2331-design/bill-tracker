// The operator Health tab's "Are we right?" panel (vision §7 trust layer). The 5-layer durability guard
// (docs/architecture/verification_durability.md) verifies the LIVE output against INDEPENDENT sources —
// reconciliation vs the official MinutesBook, completeness vs LIS's own calendar — but it runs in GitHub
// Actions and only ALERTS on failure, so the owner never SEES the green. This surfaces each guard's latest
// run live from the PUBLIC GitHub Actions API (read-only, no token — the guards are deliberately
// credential-free, so we read their verdict where it lives: the workflow run). Status + freshness turn
// "trust me, it's verified" into "here's the independent proof, refreshed on schedule." Layer 1 (the
// in-cycle circuit breaker) is the live chip elsewhere on the tab; this covers layers 2–5.

const REPO = "tucker2331-design/bill-tracker";

export type GuardState = "pass" | "fail" | "running" | "unknown";

export interface GuardRun {
  key: string;        // workflow filename (the API matches on this)
  label: string;      // human name
  proves: string;     // what it INDEPENDENTLY verifies (the trust statement)
  cadence: "daily" | "weekly";
  status: GuardState;
  lastRun: Date | null;
  stale: boolean;     // hasn't run within its cadence + grace → the guard itself stopped (its own failure)
  url: string | null; // link to the run
}

// The four session-agnostic guards (layers 2–5). Order = strongest "are we right?" first.
const GUARDS: { key: string; label: string; proves: string; cadence: "daily" | "weekly"; staleDays: number }[] = [
  { key: "completeness_tripwire.yml", label: "Completeness", cadence: "weekly", staleDays: 9,
    proves: "no hidden meeting — every meeting on LIS's own calendar appears in our data" },
  { key: "legevent_reconcile.yml", label: "Reconciliation", cadence: "weekly", staleDays: 9,
    proves: "our committee votes match the official MinutesBook — a source the pipeline never touches" },
  { key: "accuracy_sentinel.yml", label: "Accuracy sentinel", cadence: "daily", staleDays: 2,
    proves: "Section-9 = 0 + structural coverage, re-derived from the live sheet daily" },
  { key: "sustainability_audit.yml", label: "Sustainability audit", cadence: "weekly", staleDays: 9,
    proves: "the time-bomb sweep — capacity, schema drift, retention, dedup determinism" },
];

const CACHE_TTL_MS = 300000; // 5 min — CI verdicts change at most daily; keep GitHub API calls light

let _cache: { at: number; data: Promise<GuardRun[]> } | null = null;

export function loadVerification(): Promise<GuardRun[]> {
  const now = Date.now();
  if (!_cache || now - _cache.at > CACHE_TTL_MS) {
    _cache = { at: now, data: _load().catch((e) => { _cache = null; throw e; }) };
  }
  return _cache.data;
}

async function _load(): Promise<GuardRun[]> {
  return Promise.all(GUARDS.map(async (g): Promise<GuardRun> => {
    const base = { key: g.key, label: g.label, proves: g.proves, cadence: g.cadence };
    try {
      const url = `https://api.github.com/repos/${REPO}/actions/workflows/${g.key}/runs?per_page=1`;
      const res = await fetch(url, { headers: { Accept: "application/vnd.github+json" }, cache: "no-store" });
      if (!res.ok) throw new Error(`GitHub API HTTP ${res.status}`);
      const j = await res.json();
      const run = j.workflow_runs?.[0];
      if (!run) return { ...base, status: "unknown", lastRun: null, stale: false, url: null };
      const lastRun = run.created_at ? new Date(run.created_at) : null;
      const ageDays = lastRun ? (Date.now() - lastRun.getTime()) / 86400000 : Infinity;
      const status: GuardState =
        run.status !== "completed" ? "running" : run.conclusion === "success" ? "pass" : "fail";
      return { ...base, status, lastRun, stale: ageDays > g.staleDays, url: run.html_url ?? null };
    } catch (e) {
      // Allowed not to know, never pretend (vision §7): a failed read shows "unknown", never a fake green.
      console.warn(`Health: verification fetch failed for ${g.key}`, e);
      return { ...base, status: "unknown", lastRun: null, stale: false, url: null };
    }
  }));
}
