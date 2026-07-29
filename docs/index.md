---
tags: [index, meta]
updated: 2026-07-04
status: active
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
- [[state/current_status]] — **▶️ START HERE: the ONE live source — NOW / NEXT / RECENTLY LANDED (B-1 restructure 2026-07-06, MOVE-only)**
- [[state/status_archive_2026H1]] — frozen pre-B-1 history (accuracy + product narrative through 2026-07-06); reference only
- [[state/next_session]] — ⚠️ ARCHIVED (S-6): stale duplicate "what's next"; superseded by current_status
- [[state/open_anti_patterns]] — known silent fallbacks still living in the code (worker.py line debt)
- [[state/health_gauge_calibration_plan]] — **ACTIVE plan + live checklist: the 3 `/code-review` findings on PR #181 (feed-skew bands, source-feed session-awareness, Metrics_History change-feed [deferred]); persisted so it survives compaction**
- [[ny/state/current_status]] — New York-specific live status and next steps

## Audits (point-in-time expert reviews — execution specs for the implementing model)
- [[audits/build_wave_2026-07/README]] — **▶️ BUILD WAVE 2026-07-13: the CURRENT priority-ordered execution queue for Opus** (Change Ledger, parity sentinel + incident counter, war-room scoping, witness histogram) — owner-locked decisions, Fable-authored spec
- [[audits/fable_2026-07/README]] — **▶️ FABLE AUDIT HUB (2026-07-04): the priority-ordered execution queue for Opus.** Four owner-directed deliverables from the time-limited Fable session; document-only, Opus executes.
- [[audits/fable_2026-07/brain_audit]] — how the brain performed + 6 concrete changes (B-1…B-6) to close the Opus-vs-Fable gap (status-page restructure, case-law indexes, EXECUTABLE pre-push audit, CLAUDE.md de-drift, reasoning doctrine)
- [[audits/fable_2026-07/codebase_longevity_audit]] — VA+NY multi-year sustainability findings C-1…C-10 (2027 rollover halt, Sheets 10M-cell ceiling, gviz/Actions coupling, NY hardening gap, BILLS.CSV oracle canary)
- [[audits/fable_2026-07/multistate_ingestion_pa]] — PA researched (hourly XML + RSS — structured, NOT scraping); the formalized lambda architecture; the decade-grade controlled-vocabulary doctrine + 4-phase PA build plan
- [[audits/fable_2026-07/multistate_ingestion_ca_fl]] — CA (pubinfo relational export VERIFIED — votes/hearings/agendas as coded tables, daily cadence + measured-lag speed-layer experiment) + FL (site-API state; live flhouse /api/ endpoint observed; dual first-party House↔Senate oracle) vs the 10–15 min target; 4-tier state taxonomy
- [[audits/fable_2026-07/autonomy_upgrades]] — A-1/A-2 zero-touch session-follow + workbook lifecycle (owner correction; supersedes C-1/C-2's human steps)
- [[audits/fable_2026-07/50_state_scaling_architecture]] — the three 50-state blueprints: CDN inversion (worker→static JSON→edge; manifest atomicity; migration gates), Omni-Schema v1 (freeze the de-facto shape + capability flags + CI validation), Fleet (premise-corrected: per-state workflows exist; generator + national rollup + Actions graduation path)
- [[audits/fable_2026-07/sweep_findings]] — S-1…S-6: plaintext LIS key rotation-brittleness, CI golden-test blind spot, repo-root cruft, measurement caveats

## Workflow & Protocols (how we work)
- [[ny/workflow/source_scoping_protocol]] — New York source-scoping protocol: scope, plan, test, then promote
- [[ny/workflow/owner_setup]] — New York owner setup checklist for API key, sheet, and secrets
- [[workflow/hardening_is_non_negotiable]] — **owner rule: a new direction NEVER leaves in-flight work unhardened; standard-quality is the default, never traded for 'where the energy is'.**
- [[workflow/reviewer_strategy]] — **▶️ HOW TO RAISE THE CATCH RATE (owner 2026-07-27: "even Fable will only catch like 50%"). There is NO shared benchmark — vendors grade themselves — so our own 56-lesson case-law IS the benchmark. Key insight: LLM reviewers are CORRELATED, so stacking them has diminishing returns; catch rate rises with DIVERSITY OF METHOD. Our measured gaps: security ≈0, performance =1, concurrency =3 findings in 56. Free plan ranks Semgrep + mypy ABOVE another LLM bot, and proposes mutation testing as the real catch-rate measurement.**
- [[workflow/design_proposal_protocol]] — **▶️ ANTI-LOOPING RULE (owner 2026-07-25: "you are looping… come up with competing ideas, run them through our rules and checklists before I see anything"). Mandatory before ANY design reaches the owner: research the VAULT first, generate ≥2 real competing designs, self-audit every candidate against the 8 Standards + design canon + reasoning doctrine + case law, kill your own favourite, then present the vetted winner WITH the rejected options and the rule that killed each. The owner audits reasoning, never missed checklist items.**
- [[workflow/reasoning_doctrine]] — **session-start read: the 8 process moves that produce bank-grade work here (measure-first · verify-the-row · fail-open · confirm-before-advance · no silent fallback · structural-not-text · notify-only · write-back)**
- [[workflow/three_phase_protocol]] — context routing → pre-push audit → write-back mandate
- [[workflow/proposal_audit]] — the 7-point gate BEFORE any mockup/proposal is shown (the pre-push audit only gates commits)
- [[workflow/gate_scoreboard]] — is the self-check working? caught vs missed, including the misses
- [[state/va_build_queue]] — ordered VA backlog from the War Room design block (mockups → probes → foundations)
- [[knowledge/district_lookup]] — address→district (Census, no key) + the redistricting signal from the layer vintage
- [[knowledge/campaign_finance_source]] — ELECT bulk CSVs (1999→now) replace VPAP; the "go to the agency, not the aggregator" rule
- [[workflow/branching_rules]] — when to reuse vs create a branch (PR state decides)
- [[workflow/push_and_pr]] — after every commit: push, open PR, return link
- [[workflow/deploy_cloudflare_pages]] — **the decided host: React+Vite → Cloudflare Pages; repo is prepped (_redirects, node pin), owner does the 5-min dashboard Git-connect (exact settings inside)**
- [[workflow/source_miss_visibility]] — mandatory rule: no silent fallback on a source miss
- [[workflow/persistent_memory]] — this `docs/` folder IS the brain; not global memory
- [[workflow/zero_routine_maintenance]] — Standard #8: 50-state SaaS requires zero ongoing per-state maintenance; humans get pinged only for true anomalies
- [[workflow/use_tools_when_stuck]] — methodology note: consult the actual upstream source (WebFetch, API probes, etc.) alongside local reasoning, not instead of it
- [[workflow/bot_review_fold_in]] — handling Codex / Gemini PR reviews: implement, re-audit, push (bots review commits, not replies)
- [[workflow/cross_state_brain]] — **the "mega brain": generalizable lessons → SHARED brain (compounds across states); state-specific facts → per-state `docs/<state>/`. So building each state gets easier. (owner 2026-06-25)**

## Architecture
- [[ny/architecture/bill_pipeline]] — New York OpenLeg bill engine pipeline and source-to-field mapping
- [[ny/architecture/calendar_source_options]] — New York calendar source options
- [[architecture/post_c8_hardening]] — **ACTIVE: three grounded post-C8.4 hardening solutions (G-code drift alert, structural meeting_unsourced, unconfirmed rolling baseline)**
- [[architecture/pr_c8_structural_classification]] — close the 16% structurally; hard rules + gates for the implementing model
- [[architecture/incident_counter]] — **the 'N days since a data incident' counter: mechanism BUILT (9 goldens) and now FULLY UNBLOCKED + scoped (2026-07-17) — definition = the owner's sentence ("how long data holds clean before intervention"), Health-first display, verification by FIRE DRILLS on the real ledger (no sandboxes), open-incident dedup, guard-credentials decision inside. NEXT ENGINEERING PR.**
- [[architecture/text_similarity]] — **RUSHED (owner 2026-07-17, lobbyist-informed): bill-text similarity, front of line after the counter. VA full text PROBE-CONFIRMED inline (`DraftText`, + free vacode-section links); cross-state corpus = LegiScan (key is DUAL-USE with the NY oracle); MinHash/Jaccard with coarse labels calibrated on VA companion pairs; offline tool, never the worker. Owner blockers: the key + which states.**
- [[architecture/strategic_tools_placement]] — **DECISION (research-grounded): the strategic/whip tools live on a DEDICATED surface entered FROM the bill card, never ON it (the card is already the drill terminus); focus+context split.**
- [[architecture/source_precedence]] — **▶️ HOUSE RULE (owner 2026-07-25: "how are you choosing the authoritative source… in EVERY scenario?"): precedence is DERIVED from properties (published>derived · structural>text · system-of-record>mention · corroboration≠authority), never a hardcoded table of source names. When no principle applies the code does NOT pick a winner — it falls to an honest terminal rung (unverified→red, both values shown). A rung may only exist if MEASURED against the archive. Generalizes the calendar's proven ladders; exposes that the bill path has NO real provenance (`source` is the constant "LIS") — the root cause of 2026-07-25.**
- [[architecture/roster_and_votes_ingestion]] — **SCOPED by LIVE PROBE 2026-07-17 (not built): the data under the War Room. Chair/party/district/member-votes ALL confirmed structural — `CommitteeRoleTitle`=Chair, `PartyCode`, `DistrictName`, `ResponseCode`+`LegislationNumber`. Storage finding: member votes BLOW the Sheets 10M-cell ceiling → D1 or blob-mirror (not a Sheets tab). Open: companion-bill sourcing, votes-store choice, worker placement.**
- [[architecture/change_ledger]] — **the Changes tab: differ BUILT+proven (19 goldens); live wiring + tab 2027-in-session-gated (validation plan inside)**
- [[architecture/calendar_pipeline]] — LIS → worker → Sheet1 data flow + resolution priorities
- [[architecture/relative_time_chain_resolution]] — **PLANNED: order "after committee X" subcommittee chains structurally (build_time_graph fix; Section-9-sensitive; full plan before starting)**
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
- [[knowledge/legiscan_terms]] — **STUB + COMPLIANCE GATE: the temporary cross-state corpus source. Terms/scope/rate-limit/attribution must be captured BEFORE the first request (the rule that kept the VA integration clean, applied to a third party). Owner-blocked on the API key; includes the volume question the 50-state design hangs on (do dataset archives embed full text or only doc_id refs?).**
- [[knowledge/lis_api_safety]] — **CHARTER: how hard/often we may hit LIS — 5 guardrails + meeting-driven cadence (load tracks activity, never a metronome)**
- [[knowledge/lis_api_reference]] — VA LIS endpoints, auth, quirks
- [[knowledge/ny_openleg_api_reference]] — New York OpenLegislation source map and first engine contract
- [[knowledge/tba_times]] — Schedule API returns "Time TBA"; existence ≠ concrete time
- [[knowledge/lis_dom_scraping]] — headless-Chrome bypass for LIS SPA when Claude-in-Chrome is down

## Testing & Metrics
- [[ny/testing/validation_plan]] — New York fixture, dry-run, and live-write validation plan
- [[ny/testing/quality_audit]] — New York structural indicators, time coverage, health counters, and open audit items
- [[testing/va_data_quality_audit]] — **ACTIVE (owner 2026-06-25): "clean sustainable data" optimization — the live Health-tab edges to smooth (invariant_violations=1, gap-classification, unknown_refid cohort, Ledger-collapse volume, legevent recovery). Section 9 still 0.**
- [[testing/crossover_week_baseline]] — Feb 9-13, 2026 as the benchmark; PR-by-PR bug count ledger
- [[testing/crossover_audit]] — full-window tier-A audit of Sheet1 vs LIS website (ground truth)
- [[testing/edge_case_registry]] — living catalog of the edge-case SPACE per pipeline stage (Phase-C multi-session replay findings) — full-window tier-A audit of Sheet1 vs LIS website (ground truth)

## Failures / Post-Mortems
- [[ny/failures/assumptions_register]] — New York-local assumptions and failures ledger
- [[failures/meeting_unsourced_regression]] — ✅ RESOLVED post-mortem: the 0→66 was an UnboundLocalError in the agenda-links block wearing an "LIS API failed" costume (audit #105); three wrong diagnoses, fixed+hardened in #214, §9 re-merged in #215.
- [[failures/assumptions_audit]] — every busted assumption and its fix (source of truth for "why we did that"); numbered, append-only
- [[failures/gemini_review_patterns]] — recurring mistakes caught in external code review (pre-push checklist)
- [[failures/pr22_post_mortem]] — framework-level lesson: we were measuring only the bugs we wanted to see
- [[failures/legacy_calendar_versions]] — why the old app.py / shadow_v2 / v2_shadow_test / backend_worker / xray versions are relative failures (text-driven, hardcoded session, silent excepts, unthrottled polling) — the "before" picture that justifies the current architecture

## Design (how the front end should look + behave)
- [[design/information_display]] — **the design north-star: principles → actionable rules mapped to each screen + a punch-list for `web/`. Living.**
- [[design/object_page_patterns]] — **RESEARCH (fills a canon gap): the central-object page — OOUX/ORCA (our '13 features' are mostly OBJECTS + relationships, which is why the page won't silt up), the CRM record-page skeleton (compact layout = the card↔page consistency rule; next-steps vs past-activity), NN/G tab rules (the hearing-prep COMPARISON case forbids tabs), Jira's issue anatomy (the sidebar question is really control-vs-content), and the LIS-fact vs org-intel partition — prior art can't solve it, but our own canon can: partition by POSITION, never colour/opacity ([[design/information_display]] §5b/P20). Finding (a RECOMMENDATION for the owner, not a locked decision): the trust line and the Access/permission line are the SAME line, which argues the war room is not a tab but the org-owned REGION of the bill page.**
- [[design/reading_notes]] — **per-book DEEP-READ digests (Few *Information Dashboard Design* read in full; *Refactoring UI* tactics; Tufte/Hearst queued). The raw material; concrete fixes for the "screams-AI" critique.**
- [[design/ui_redesign_spec]] — **owner's 2026-06-22 UI change-list: landing relayout (calendar sliver + timeline below), smoother less-boxy timeline, shrink crossover, Floor stage?, Search bugs, the visual-identity pass + the 2026-06-23 timeline-should-BRANCH feedback.**
- [[design/ui_feedback_2026-07-04]] — **owner UI/cadence notes (2026-07-04, for later): the two freshness clocks disagree (display fix, not a cron-sync); cadence is FIXED not activity-correlated (guardrail #5 now unblocked to build); Health rings — label the two lines + explain Freshness's missing badge + make the '1 warning' descriptive & clickable; the lone live alert (HB923 blank upstream row) is a benign honest flag.**
- [[design/health_operator_tab]] — **SCOPE (Task #4): the operator Health tab — Few bullet-graph gauges w/ danger bands (PL-8), grounded in live SYSTEM_METRICS/SYSTEM_ALERT signals; Cloudflare Access gating + the data-publicity caveat.**
- [[design/dashboard_and_visual_language]] — **alerts as STATE not stream (the self-clearing feed: verdict + active-only + collapsed per-category history) + the 2026-07-07 de-AI pass APPLIED (severity/breaker/skew/header "colored boxes" → status dots). Implements the [[design/reading_notes]] canon.**

## Ideas / Deferred Work
- [[ny/ideas/data_inventory]] — New York source inventory and unresolved meeting/calendar questions
- [[ideas/lobbyist_jtbd_ideation]] — **EXPANSIVE zoom-out (2026-07-13, owner-requested): the lobbyist/bill-writer job map (JTBD + year-in-the-life + Kano + premortem), ~30 feature ideas A1–G2, competitive white space, business models, and a strawman shortlist — awaiting owner NARROWING.**
- [[ideas/product_roadmap]] — **post-accuracy direction: reviewer swap (A), product vision → LIS data inventory → UI design (B), 2027-gated items (C). The anti-looping plan.**
- [[ideas/product_identity]] — **▶️ THE NORTH STAR ABOVE THE SPECS: what this fundamentally is — a multi-state legislative OPERATING SYSTEM (brain-in-HQ + operators) over owned, health-verified data; the 3 pillars; the origin story; the per-state-sites + exec-master-site topology; VA-gold-standard-first sequencing.**
- [[ideas/product_vision]] — **LOCKED B1 product spec: four lenses, crossover-lane timeline, bill card, trust layer ("never pretend to know"). Build the front end toward this.**
- [[ideas/lis_data_inventory]] — **B2: feature → LIS data → have it?/ingest it. The completeness gap, the feed-skew map, and the DB-expansion decisions (owner §7 questions).**
- [[ideas/calendar_chain_ordering]] — **PLAN (queued): resolve "after committee X" meeting chains so they order correctly (worker `build_time_graph` fix; Section-9-validated). Owner-requested full plan before starting.**
- [[ideas/multi_state_data_strategy]] — **VISION (owner 2026-06-24/25): scaling past VA — bulk-as-truth (PA hourly bulk → macro/trends DB) + a provisional, session-gated speed layer the bulk continuously GRADES (→ self-healing architecture); on-demand "latest" button; split stores by purpose; per-state source manifest. With my challenges + the owner's decisions.**
- [[ideas/multi_state_org_structure]] — **PLAN (owner 2026-06-25): clean organization for 50 states — `core/` + `states/<code>/` code layout, one sheet/tab naming convention, `<state>_` workflows, branch pruning, shared-vs-per-state brain tags, per-state front-end config. Sequenced AFTER VA finishes.**
- [[ideas/self_healing_classification]] — **PARKED design (owner 2026-06-29): route on structural PROOF, LIS's own calendar/minutes GRADE + auto-correct, LEARN the fixes (auto-maintained dictionary). 3 owner corrections locked: (1) Prove-to-HIDE — unproven meeting-kind rows → visible Suspense lane, never the Ledger (no flooding); (2) canonical-ONLY learning (EventCode/StatusID, never free text); (3) STRUCTURAL-integrity breaker, NOT a quantity/delta count. The 50-state scale unlock, sequenced after VA.**
- [[ideas/war_room_scoping]] — **DECISION MEMO (build-wave TASK 3): 5 owner forks for the war room + shared watchlist (IA · write-path Worker+D1 · identity · MVP cut · star↔position). No code until answered.**
- [[ideas/moat_and_competition]] — **▶️ BUSINESS HAT (owner 2026-07-17, saw a vibe-coded student alt): data health is the ENTRY TICKET, not the moat. The 4 real moats that resist an AI-built clone — (1) the compounding clean ARCHIVE (can't vibe-code the past), (2) the War Room as SYSTEM-OF-RECORD (org's own intel = switching cost), (3) multi-state DATA-NETWORK effects, (4) provable TRUST as brand (strengthens as slop multiplies) — and the flywheel that compounds them. Money is in the workflow + insight layers; read layer → free/commodity.**
- [[ideas/predictive_lane]] — **DISCUSSION (owner 2026-07-17: "we can do it but carefully"): how prediction lives inside a trust-moat product. THREE TIERS — (1) measured history = our archive's payoff, low risk; (2) deterministic math = zero risk; (3) individual behavioral prediction = the dangerous one, EARNED behind a calibration harness (backtest the 2020–26 archive, Health-tab calibration SLA, self-suppress on drift, interval-not-point, unknowns-only). Tier-3 go/no-go is the owner's call.**
- [[ideas/copatrons_backfill]] — **co-patrons: sourcing CONFIRMED non-trivial (universe + BILLS.CSV are chief-only; needs the bounded ~148-call LegislationByMember whose endpoint must be DOM-discovered first). Scoped plan + guardrails; deferred, not a launch blocker.**
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
- **Frontmatter on every page:** `tags`, `updated: YYYY-MM-DD`, and `status: active | archived | stub`.
- **One concept per page.** If a page covers two separate things, split it.
- **Cross-reference instead of duplicate.** If information belongs on page A, reference it from page B with a wikilink rather than copy-pasting.
- **Update on touch.** Whenever a page is read in service of a task, update the `updated:` field if the content needs refreshing.
- **New lessons → new pages.** Each post-mortem or framework insight gets its own page in `failures/`, then a link from the index.
