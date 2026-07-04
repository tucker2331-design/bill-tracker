---
tags: [audit, fable, architecture, scaling, 50-states, cdn, schema, fleet]
updated: 2026-07-04
status: active
---

# FABLE — 50-state scaling architecture: the three blueprints

Requested via Gemini review before closing the audit. **Fable's verdict up front:** Blueprint 1 (CDN
inversion) is the real new build and the keystone; Blueprint 2 (Omni-Schema) is formalization of a
de-facto standard that already exists in the code; Blueprint 3 (Fleet) is needed, **but its premise is
corrected below** — no monolithic 50-state cron exists or was ever planned; the per-state fleet already
exists in embryo (VA calendar / VA bills / NY bills each run their own workflow, cron, and concurrency
group). What Blueprint 3 actually solves is platform limits at ~15+ states, not a timeout in a design
nobody proposed.

**Explicitly deferred (do NOT build now):** a database/warehouse (static JSON serves the product; an
analytical store is a later, separate decision), message queues, Kubernetes/orchestration — all staged
for fleet sizes we don't have. Boring beats clever at decade scale.

---

## Blueprint 1 — Inverting the database: worker → static JSON → CDN edge

**Problem quantified:** today the browser reads Google Sheets through the undocumented `gviz` CSV
endpoint (~5 MB Sheet1 pulls), which requires link-readable sheets and has unpublished rate limits; the
product workbook lives under a hard 10M-cell cap ([[audits/fable_2026-07/codebase_longevity_audit]] C-2:
already ~4–5M measured). ×50 states, every one of those properties is disqualifying.

**Target architecture (the inversion):** Sheets stops being the product database and becomes (at most)
the workers' internal ops store. The worker's LAST step each cycle publishes the lobbyist-facing product
as **versioned static JSON to a CDN/edge host**; the web UI reads ONLY that.

1. **Payloads (per state, per cycle)** — the Omni-Schema instances of Blueprint 2:
   - `/{state}/bills.json` — the bill records (VA today: 3,645 × ~1 KB ≈ 4 MB raw, ~500 KB gzipped —
     trivial for edge hosting; split per-view if any state's payload nears ~10 MB raw).
   - `/{state}/calendar.json` — the meeting records (replaces the 5 MB Sheet1 projection with the
     ~200 KB the calendar actually renders).
   - `/{state}/health.json` — the operator signals (metrics snapshot, alerts, canaries, freshness).
   - `/{state}/manifest.json` — tiny: schema_version, cycle timestamp, payload ETag/hashes, session
     code, capability flags. **The manifest is the pointer-stability answer** (A-2's requirement): IDs,
     workbooks, sessions can all change behind it; readers only ever know the manifest URL.
   - `/national/manifest.json` — the fleet rollup: per-state status + freshness (Blueprint 3's health
     surface).
2. **Host:** Cloudflare R2 + CDN (or Pages) — already the roadmap's deploy target; free tier covers 50
   states of JSON thousands of times over. GitHub Pages is the acceptable fallback host. Publishing =
   one `rclone`/API upload step appended to each worker workflow; credentials = one write-scoped token
   secret (rotatable, unlike the gviz surface which has no credentials to rotate).
3. **Atomicity + versioning:** write payloads under content-hashed names (`bills.<hash>.json`), then
   swap `manifest.json` last (single-object PUT = atomic). Readers never see a torn cycle. Keep the last
   N manifests as `manifest.<ts>.json` — free time-travel for debugging and the replay ethic.
4. **Failure honesty (the §7 rule at the transport layer):** if a cycle fails, the manifest is simply
   not swapped — readers keep last-known-good WITH its honest `generated_at` (the UI already renders
   "data as of"). A worker that cannot publish alerts through the existing channels; the front end never
   sees a partial write.
5. **Front-end change:** `web/src/data/*` gains a `staticJson` loader (manifest → payloads, ETag-cached);
   gviz demoted to fallback during migration, deleted at 3 states. The trust header reads the manifest's
   timestamps — strictly more honest than inferring from row cells.
6. **Migration path (no big-bang):** Phase i — VA workers dual-publish (Sheets canonical, JSON shadow);
   diff the JSON against the gviz-derived state for N cycles (a reconciliation gate, like every other
   migration here). Phase ii — front end flips to JSON-first. Phase iii — lobbyist-facing tabs stop
   being written; Sheets remains ops-only (or is fully retired per A-2's ops-shard). NY onboards
   JSON-only; every later state never touches gviz.
- **Validation gates:** N-cycle diff = 0; page-load bytes drop measured (~5 MB → < 1 MB); a deliberate
  mid-publish kill leaves readers on the previous coherent manifest; front end functions with the gviz
  domain blocked.
- **Effort:** ~2–3 days including the dual-publish soak. **Sequencing: with A-1/A-2, ahead of any new
  state** — every state added before the inversion deepens the gviz hole.

## Blueprint 2 — The Omni-Schema: one normalized payload, per-state adapters, capability flags

**Corrected framing:** this already half-exists — `ny_bill_tracker.py` deliberately emits the VA-shaped
record ("keeps the same lobbyist-facing output shape"), and `web/src/data/types.ts` + the completeness
object are the de-facto schema. The blueprint FREEZES it as a versioned contract instead of a
convention, and adds the missing concept: **capabilities**.

1. **Contract artifacts (in-repo, versioned):** `schema/omni/v1/bill.schema.json`,
   `meeting.schema.json`, `health.schema.json`, `manifest.schema.json` (JSON Schema). The current Bill
   shape is v1 verbatim — bill id, title, status_raw (the state's authoritative string, ALWAYS carried),
   outcome (normalized enum), chamber, floor events, committee position, votes, history, provenance
   (`source`, `data_as_of`, `origin/time_class`-style flags). Normalized enums live in the schema;
   **every record keeps the state's raw string next to the normalized value** (the VA rule — show the
   source, never only our interpretation).
2. **Adapters, not forks:** each state worker is an adapter with exactly one job — bind state sources to
   omni-records ([[ideas/multi_state_org_structure]]'s `states/<code>/` layout). Everything downstream
   of the omni-record (reconciler, health counters, publisher, UI) is shared `core/`. The 4-tier source
   taxonomy ([[audits/fable_2026-07/multistate_ingestion_ca_fl]]) lives entirely inside adapters.
3. **Capability flags (the honest-schema move):** each state's manifest declares what it can know:
   `{"meeting_times": "full|partial|none", "floor_votes": …, "committee_agendas": …, "vote_rollcalls":
   …}` — derived from the state's source contract (e.g. NY: Assembly committee data "none" — already
   documented in its completeness object; this generalizes that). The UI renders absent capabilities as
   honestly-absent features, never empty-looking data. **A state can be onboarded thin and deepen later
   without schema churn.**
4. **Enum governance:** normalized enums (outcome, event class, time class) extend by PR to the schema
   files with a version bump; adapters that can't map a state value use the schema's `other` + raw
   string + a counter (the unproven-lane pattern at schema level). CI validates every published payload
   against the schema (a 20-line check in the publish step) — an adapter cannot ship an off-contract
   payload.
- **Validation gates:** VA + NY payloads validate against v1 unchanged (proving v1 = reality); one
  synthetic "thin state" fixture renders correctly in the UI with capabilities honestly absent.
- **Effort:** ~1–2 days (schema files + CI validator + capability plumbing). Do alongside Blueprint 1
  (the payloads it publishes ARE these schemas).

## Blueprint 3 — The Fleet: decoupled per-state workers (premise corrected)

**Correction on record:** there is no monolithic 50-state cron to rescue. Today each state-concern is
already an independent workflow with its own cron, runtime, and concurrency group — one state's failure
already cannot block another's update. The real 50-state problems are quieter:

1. **Platform concurrency + scheduler throttling.** GitHub Actions caps concurrent jobs per plan and
   deprioritizes busy scheduled workflows (we've already measured ~12-min queue delays with THREE
   workflows). Fifty states × (bills + calendar + guards) ≈ 150+ scheduled workflows is beyond polite
   use. **Design:** (a) staggered crons generated, not hand-picked — minute offsets derived from a hash
   of the state code (the jitter charter, fleet-wide); (b) per-state concurrency groups
   (`{state}-worker`) exactly like today's; (c) session-aware cadence per state — each state's adapter
   knows its legislature's calendar, so out-of-session states run daily, in-session states run at their
   speed-layer cadence (most of the year, most states are quiet: the fleet's AVERAGE load is a fraction
   of its peak, and Standard #8's activity-correlated principle is what makes 50 states fit at all).
2. **Workflow generation, not workflow copying.** One template + `tools/fleet/generate_workflows.py`
   emits `states/<code>` workflows from each state's manifest (cadence, secrets names, workbook/artifact
   targets). Hand-edited per-state YAML ×50 is the CLAUDE.md-drift failure mode at fleet scale; generated
   files carry a DO-NOT-EDIT header and a CI check that regeneration is clean (same discipline as the
   ray2/calendar_xray diff-identity rule, mechanized).
3. **Shared-nothing state.** Per-state storage namespaces (workbook or artifact set per state — never
   co-located, the C-2 lesson), per-state caches, per-state locks. The ONLY shared artifact is the
   national manifest, written by whichever state finished last (content-hashed, last-writer-wins is safe
   because it aggregates immutable per-state manifests).
4. **Fleet health = a rollup, not a new system.** `/national/manifest.json` aggregates each state's
   freshness + guard status; the Health surface gets a 50-cell state grid (green/amber/red per state)
   reading it. One state down shows one red cell and pages nobody (its own guards alert per its own
   thresholds); NATIONAL alerting fires only on fleet-wide patterns (≥ N states stale simultaneously =
   platform problem, not state problem).
5. **The graduation path (named now, executed later):** Actions remains the fleet substrate until
   ~12–15 active states or until measured queue delays exceed the speed-layer budget. The workers are
   already substrate-portable in shape (env-config + Python + no Actions-specific logic); the exit is
   containerizing the same workers onto Cloud Run jobs / Fly machines with per-state schedulers, keeping
   Actions for guards/CI. Decision gate documented, not prematurely executed.
- **Validation gates:** workflow generator round-trips today's three workers unchanged; a chaos test
  (disable VA's workflow for a day) leaves NY publishing + national manifest correctly showing one stale
  state; measured queue delay at 5 states stays under 2× cadence.
- **Effort:** generator + rollup ~2 days when the 3rd state onboards; the graduation path is a
  documented trigger, not work.

## Execution order (per the owner)
**A-1 → A-2 → Blueprint 1 (CDN inversion, with Blueprint 2's schemas as its payload format) → Blueprint
3's generator at the 3rd state.** Blueprints 2 and 3 deliberately ride existing milestones rather than
standing alone — formalization is cheap when it travels with work that was happening anyway.

See also [[audits/fable_2026-07/autonomy_upgrades]] (A-1/A-2), [[audits/fable_2026-07/codebase_longevity_audit]] (C-2/C-3 evidence), [[audits/fable_2026-07/multistate_ingestion_pa]] + [[audits/fable_2026-07/multistate_ingestion_ca_fl]] (the adapters this fleet runs), [[ideas/multi_state_org_structure]], [[workflow/zero_routine_maintenance]].
