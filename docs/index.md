---
tags: [index, meta]
updated: 2026-06-25
---

# Project Brain — Index

The catalog of every page in this wiki. Open this first when looking something up. The LLM should also read this before answering any substantive question so it knows what pages already exist (don't duplicate, update in place).

Links use Obsidian `[[wikilink]]` format. Obsidian resolves by filename; path-qualified when the filename is ambiguous.

## Meta
- [[README]] — vault entry; how this brain is structured and how to maintain it
- [[index]] — this file
- [[log]] — chronological, append-only record of ingests / decisions / PRs / lint passes
- [[ny/README]] — **New York START HERE**; separate NY brain entry while the NY engine is being retuned
- [[ny/index]] — catalog of the New York brain section

## State (live trackers — read these to know what's happening NOW)
- [[state/next_session]] — **▶️ START HERE: the next-session kickoff — current state + the owner queue (read books → Calendar feature → Health bullet-graph tab) + how we work**
- [[state/current_status]] — active focus, open PR, current bug count, what's next
- [[state/open_anti_patterns]] — known silent fallbacks still living in the code (worker.py line debt)
- [[ny/state/current_status]] — New York-specific live status and next steps

## Workflow & Protocols (how we work)
- [[ny/workflow/source_scoping_protocol]] — New York source-scoping protocol: scope, plan, test, then promote
- [[ny/workflow/owner_setup]] — New York owner setup checklist for API key, sheet, and secrets
- [[workflow/three_phase_protocol]] — context routing → pre-push audit → write-back mandate
- [[workflow/branching_rules]] — when to reuse vs create a branch (PR state decides)
- [[workflow/push_and_pr]] — after every commit: push, open PR, return link
- [[workflow/source_miss_visibility]] — mandatory rule: no silent fallback on a source miss
- [[workflow/persistent_memory]] — this `docs/` folder IS the brain; not global memory
- [[workflow/zero_routine_maintenance]] — Standard #8: 50-state SaaS requires zero ongoing per-state maintenance; humans get pinged only for true anomalies
- [[workflow/use_tools_when_stuck]] — methodology note: consult the actual upstream source (WebFetch, API probes, etc.) alongside local reasoning, not instead of it
- [[workflow/bot_review_fold_in]] — handling Codex / Gemini PR reviews: implement, re-audit, push (bots review commits, not replies)

## Architecture
- [[ny/architecture/bill_pipeline]] — New York OpenLeg bill engine pipeline and source-to-field mapping
- [[ny/architecture/calendar_source_options]] — New York calendar source options: Senate OpenLeg first, Assembly official-source path, visible no-time/source-gap states
- [[architecture/post_c8_hardening]] — **ACTIVE: three grounded post-C8.4 hardening solutions (G-code drift alert, structural meeting_unsourced, unconfirmed rolling baseline)**
- [[architecture/pr_c8_structural_classification]] — close the 16% structurally; hard rules + gates for the implementing model
- [[architecture/calendar_pipeline]] — LIS → worker → Sheet1 data flow + resolution priorities
- [[architecture/alerting]] — bug-notification protocol: in-sheet `SYSTEM_ALERT` / GitHub failure email / Slack ops channel; which tripwire fires when, and how to wire Slack
- [[architecture/scalability_audit]] — standing standards-compliance audit (scalable / sustainable / zero-maintenance?); re-run after any architecturally-significant change
- [[architecture/stress_test_failure_modes]] — adversarial failure-mode audit: what breaks tomorrow / in 6 months / in 2 years, with severity + status
- [[architecture/verification_durability]] — the FIVE-layer continuous guard (breaker / daily sentinel / weekly reconciliation / completeness / **sustainability audit**); how next session won't silently regress
- [[architecture/session_archive]] — per-session output archival to a separate workbook (capacity + the trend-tracking foundation); `tools/session_archive/`

## Tooling (verification)
- `tools/verification/completeness_tripwire.py` — no-hidden-meeting guarantee (LIS calendar vs Sheet1, code-join)

## Domain Knowledge
- [[knowledge/history_refid_namespace]] — refid = typed namespace (vote-join, batch-notice law); VOTE/BILLS.CSV; SPA-shell false-200s
- [[knowledge/lis_api_authorization]] — **RULE: LIS API authorized for 2025/2026 ONLY; pre-2025 via legacylis CSV**
- [[knowledge/lis_api_safety]] — **CHARTER: how hard/often we may hit LIS — 5 guardrails + meeting-driven cadence (load tracks activity, never a metronome)**
- [[knowledge/lis_api_reference]] — VA LIS endpoints, auth, quirks
- [[knowledge/ny_openleg_api_reference]] — New York OpenLegislation source map and first engine contract
- [[knowledge/tba_times]] — Schedule API returns "Time TBA"; existence ≠ concrete time
- [[knowledge/lis_dom_scraping]] — headless-Chrome bypass for LIS SPA when Claude-in-Chrome is down

## Testing & Metrics
- [[ny/testing/validation_plan]] — New York fixture, dry-run, and live-write validation plan
- [[ny/testing/quality_audit]] — New York structural indicators, time coverage, health counters, and open audit items
- [[testing/crossover_week_baseline]] — Feb 9-13, 2026 as the benchmark; PR-by-PR bug count ledger
- [[testing/crossover_audit]] — full-window tier-A audit of Sheet1 vs LIS website (ground truth)
- [[testing/edge_case_registry]] — living catalog of the edge-case SPACE per pipeline stage (Phase-C multi-session replay findings) — full-window tier-A audit of Sheet1 vs LIS website (ground truth)

## Failures / Post-Mortems
- [[ny/failures/assumptions_register]] — New York-local assumptions and failures ledger
- [[failures/assumptions_audit]] — every busted assumption and its fix (source of truth for "why we did that"); numbered, append-only
- [[failures/gemini_review_patterns]] — recurring mistakes caught in external code review (pre-push checklist)
- [[failures/pr22_post_mortem]] — framework-level lesson: we were measuring only the bugs we wanted to see
- [[failures/legacy_calendar_versions]] — why the old app.py / shadow_v2 / v2_shadow_test / backend_worker / xray versions are relative failures (text-driven, hardcoded session, silent excepts, unthrottled polling) — the "before" picture that justifies the current architecture

## Design (how the front end should look + behave)
- [[design/information_display]] — **the design north-star: principles → actionable rules mapped to each screen + a punch-list for `web/`. Living.**
- [[design/reading_notes]] — **per-book DEEP-READ digests (Few *Information Dashboard Design* read in full; *Refactoring UI* tactics; Tufte/Hearst queued). The raw material; concrete fixes for the "screams-AI" critique.**
- [[design/ui_redesign_spec]] — **owner's 2026-06-22 UI change-list: landing relayout (calendar sliver + timeline below), smoother less-boxy timeline, shrink crossover, Floor stage?, Search bugs, the visual-identity pass.**

## Ideas / Deferred Work
- [[ny/ideas/data_inventory]] — New York source inventory and unresolved meeting/calendar questions
- [[ideas/product_roadmap]] — **post-accuracy direction: reviewer swap (A), product vision → LIS data inventory → UI design (B), 2027-gated items (C). The anti-looping plan.**
- [[ideas/product_vision]] — **LOCKED B1 product spec: four lenses, crossover-lane timeline, bill card, trust layer ("never pretend to know"). Build the front end toward this.**
- [[ideas/lis_data_inventory]] — **B2: feature → LIS data → have it?/ingest it. The completeness gap, the feed-skew map, and the DB-expansion decisions (owner §7 questions).**
- [[ideas/future_improvements]] — things on deck, priority-tagged

## Raw / Source (out of scope of this wiki)
The codebase itself (`calendar_worker.py`, `pages/ray2.py`, etc.) is the raw layer. The wiki describes it but does not duplicate it.

## Tooling
- `tools/crossover_audit/` — runnable pipeline for the full-window LIS audit; see [[testing/crossover_audit]] for context.
- `tools/verification/` — the **Accuracy Sentinel** (daily Section-9 + unclassified + partial-sheet guard; session-agnostic) and the **Sustainability Audit** (`sustainability_audit.py`, weekly — the executable 5-trigger time-bomb sweep; durability Layer 5). See [[architecture/verification_durability]].
- `tools/witness_retention/` — the **L3b Witness retention prune** (`prune.py`, daily — deletes `Schedule_Witness` rows >90d; shares the worker concurrency group for exclusive tab access).
- `tools/session_archive/` — the **Session Archive** (`archive.py`, workflow_dispatch — preserves each session's output + the C7_1a corpus in a separate archive workbook; verify / snapshot-session / migrate-c7). See [[architecture/session_archive]].
- `tools/reconciliation/` — the **Reconciliation Tripwire** (weekly diff vs the independent official MinutesBook).
- `tools/c7_section9_verify/` — read-only check of the X-Ray Section 9 count against LIVE Sheet1 (the production artifact, not a sidecar tool). The reusable form of the verification method [[failures/assumptions_audit#62]] mandates; run after re-hydrating the LegEvent cache.

---

## Conventions (for the LLM maintaining this wiki)

- **Wikilinks over markdown links** where possible — Obsidian's graph view and backlinks depend on `[[name]]` syntax.
- **Section-anchored wikilinks** when pointing at a specific header in another page: `[[page#Section Header|display text]]`. Lets Obsidian jump straight to the header on click. Don't write `[[page]] → "Section"` with a manual arrow — the section anchor is the link.
- **Frontmatter on every page:** `tags`, `updated: YYYY-MM-DD`, optional `status: active | archived | stub`.
- **One concept per page.** If a page covers two separate things, split it.
- **Cross-reference instead of duplicate.** If information belongs on page A, reference it from page B with a wikilink rather than copy-pasting.
- **Update on touch.** Whenever a page is read in service of a task, update the `updated:` field if the content needs refreshing.
- **New lessons → new pages.** Each post-mortem or framework insight gets its own page in `failures/`, then a link from the index.
