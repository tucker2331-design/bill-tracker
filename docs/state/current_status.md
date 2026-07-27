---
tags: [state, live]
updated: 2026-07-15
status: active
---

# Current Status

**Owner:** Tucker Ward
**Live site:** https://bill-tracker.tucker2331.workers.dev (Cloudflare Workers static-assets; deploy green). **Sheets:** VA·Live `1PQD…JGKM` · VA·Archive `1AA-d…QeA` · VA·Ops `1X7wa4b…` (naming schema `<Jurisdiction> · <Role>`).
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0. **Achieved + holding (Section 9 = 0 since 2026-06-06).**
**Benchmark window:** Full 2026 VA GA session (2026-01-14 → 2026-05-01). **VA GA is ADJOURNED — HISTORY is static until the 2027 session. Pre-launch: lobbyists are not using the product yet.**

> **MOVE-only page (B-1, 2026-07-06):** ≤3 items in NOW, the ordered queue in NEXT, ≤5 one-liners in RECENTLY
> LANDED. Finishing a task MOVES its line NOW→RECENTLY LANDED and evicts the oldest; nothing is appended
> below. Full history: [[log]] (PR-by-PR) + [[state/status_archive_2026H1]] (frozen pre-B-1 narrative).

## NOW
- **PRODUCT IDENTITY banked (2026-07-15): [[ideas/product_identity]]** — the north star above the specs (a
  multi-state legislative operating system; 3 pillars: complete health-verified data · strategic tools ·
  team coordination; brain-in-HQ + operators; per-state sites + an exec-gated master site LATER). **Sequencing
  (owner-locked): finish VA to the gold standard ENTIRELY, then dupe per state — touch nothing else until
  then.** New standing rule: [[workflow/hardening_is_non_negotiable]] (a direction never leaves in-flight work
  unhardened). Design decision: strategic/whip tools go on a DEDICATED surface, not the crowded bill card
  ([[architecture/strategic_tools_placement]]).
- **WAR ROOM BUILD-OUT UNDERWAY (owner 2026-07-17: "go for the max while it's shut down for building").** Mockup v3 owner-approved; roster/vote ingest **SCOPED via live LIS probe** — chair (`CommitteeRoleTitle`), party (`PartyCode`), district, and member votes (`ResponseCode`+`LegislationNumber`) ALL confirmed structural ([[architecture/roster_and_votes_ingestion]]). Storage finding: member votes exceed the Sheets 10M-cell ceiling → D1/blob, not a tab. **Predictive lane opened as a 3-tier plan** ([[ideas/predictive_lane]]): measured-history + deterministic-math build first; individual prediction (Tier 3) gated behind a calibration harness, owner's go/no-go. **MAINTENANCE WAVE — COMPLETE, 8 of 8 (2026-07-27)** (not complete: W1 is unbuilt — an earlier version of this line said "COMPLETE" while listing W1 as not built, which was self-contradictory). Everything below except W1 is merged to main with green CI, goldens, and — where the rate limit allowed — a bot review folded in.
  **W0** owner-reported bugs — calendar clipping fixed + LIVE, accuracy ring lands on the failing metric, `outcome_origin` provenance so the adjudication verdict survives, bill-worker alerts reach the Health panel (#227).
  **W1** incident counter — **SHIPPED (#235)**: module, guard wiring and ledger workflow were already in place; the Health-tab display was the missing piece. Denominator always shown, an OPEN incident reads red from its start, an unseeded ledger says so rather than showing a reassuring 0, genesis/drill rows never break the streak. Six goldens run the real TypeScript through node so the Python and TS cannot drift on the honesty rules.
  **W2** VA native text scanner (#232) · **W3** comparer CALIBRATED on real bills (+0.846 separation) · **W4** companion detection + drift (#233) — remaining text-corpus residuals tracked in [[architecture/text_similarity]] (cross-state corpus is blocked on Open States' bulk downloads requiring a login; VA-only work is done) · **W5** VOTE.CSV answered — the whole per-member matrix (318,282 pairs) is already in a blob we fetch · **W6** Open States adopted over LegiScan (public domain, no attestation) with a hard request budget · **W7** CLAUDE.md cadence-drift guard.
  **Reviewer bench rebuilt** ([[workflow/reviewer_strategy]]): Semgrep + mypy added as deterministic layers — mypy immediately caught a gspread signature bug that would have broken the trust counter's first write, and the house rules caught our own new code swallowing a corrupt-file error (#234). **Gemini is permanently OUT** — Google shut the free consumer GitHub reviewer down 2026-07-17; review is enterprise-paid only. **CodeRabbit is the only free LLM reviewer for a private repo.**
  **ROSTER INGEST — SHIPPED (#236), the last hard blocker under the War Room.** Live-verified on session 20261: 148 members, 25 committees, H21's chair correctly identified (C.E. Cliff Hayes Jr.), party split 16D/9R, district resolved, zero misses, 4 requests. The live run caught a bug the goldens could not — the member-detail payload is WRAPPED under `Members`, so districts came back empty on real data while a flat fake passed; the fake now mirrors the wire. Votes deliberately excluded (VOTE.CSV already holds all 318,282 pairs).
  **NEXT: the War Room.** Its three stated blockers are now down to one — roster ingest ✅ shipped, the mockup ✅ drawn and approved; remaining are the **roster-row fact/intel boundary** (the one unresolved design spot) and the **MVP cut (D4)**. Then the write path (Worker+D1+Access) and build.
- **VA accuracy state: CLEAR + holding (2026-07-12).** The 0→66 regression is root-caused and closed ([[failures/assumptions_audit#105]] — an `UnboundLocalError` in the agenda block wearing an API-outage costume; §9 and cache-warmth both innocent). All four deferred pieces shipped + live-verified: agenda/meeting links (#214), §9 anchor ladder re-merge (#215), the scroll affordance (#216), and the last engineering residual — the label-based agenda-FETCH target (#217, [[state/open_anti_patterns]] #13, now resolved). No open VA engineering items; the only open PR is the Codex NY-probe (#175, NY). **Standing watch each cycle:** `meeting_unsourced=0`, breaker clear, `anchor_unresolved` stays 1, agenda/link drift canaries quiet. Everything below in NEXT is owner-gated (infra/decision), not blocked on me.

## NEXT (needs owner infra / a decision — then I execute)
1. ~~Enable A-2 Part 2 manually~~ **NO LONGER OWNER-GATED — the worker auto-shards the witness itself at 6M** (`_autoshard_witness_if_full`, zero-touch, fail-closed). Nothing for the owner to run. `archive.py shard-witness` + `WITNESS_WORKBOOK=ops` remain as manual overrides only. [[audits/fable_2026-07/autonomy_upgrades]].
2. **C-8 Part 2** — NY independent oracle (reconciliation) ([[audits/fable_2026-07/codebase_longevity_audit]]). **RE-SCOPE NEEDED (2026-07-27): it assumed a LegiScan key, and LegiScan is rejected** ([[knowledge/legiscan_terms]] — its free key demands a non-commercial + internal-use-only attestation). Re-point at **Open States** NY data (public domain, key already set as `OPENSTATES_API_KEY`). No longer owner-blocked.
3. **Multi-state — ONE STATE AT A TIME (owner directive 2026-07-07; notes preserved, do NOT lose):** tackle each new state as its own scoped project. Notes are banked and safe:
   - PA ingestion plan → [[audits/fable_2026-07/multistate_ingestion_pa]]
   - CA + FL research → [[audits/fable_2026-07/multistate_ingestion_ca_fl]]
   - 50-state decoupling (CDN inversion + Omni-Schema + Fleet) → [[audits/fable_2026-07/50_state_scaling_architecture]]
   - NY is the live 2nd state (its own brain: [[ny/state/current_status]]); C-8 Part 2 (LegiScan oracle) is its next step.
4. Optional/low-value: **S-3** (attic-move deprecated repo-root files — cosmetic, breaks the paused worker's manual dispatch; do only if you want the cleanup); ~~**B-4 finish**~~ **DONE 2026-07-27** — the mechanical half shipped as W7 (a pre-push guard that fails if CLAUDE.md re-acquires a hardcoded cadence).
5. **Incident counter — UNBLOCKED + fully scoped, the NEXT ENGINEERING PR** (owner 2026-07-17: "we need to prove it"). Definition = the owner's sentence (manual interventions count); Health-first; guards = sentinel/tripwire/reconciliation. Verification = **fire drills on the real ledger** (owner killed the sandbox idea) — a `_drill` class runs the full production write path, excluded from the clock like `_genesis`. Scoping pass 2 in [[architecture/incident_counter]]: open-incident dedup (a 3-day outage must be ONE row, closed on recovery-PASS), guard-creds decision (all three guard workflows are creds-free today), denominator display ("N days clean · monitoring for M"), **genesis seeded the same day as the PR — every un-seeded day is thrown-away provable trust**.
6. **WAR ROOM — MOCKUP v1 DRAWN, awaiting owner review:** https://claude.ai/code/artifact/ef78b6ce-4d68-410d-918d-20db9ad6605c (two screens, product's real tokens, nothing built). **IA DECIDED by owner 2026-07-17: it IS its own tab, named the War Room** — "bill page" is dead as a name (owner: *"call it the war room… it's cross data from other states even"*; and *"we have a bills tab, it's called Search"*). My "two places" argument for folding it into a bill page was **wrong and is retracted** (a War Room tab can show LIS context itself — there is no split). Shape = **your bills → drill in**; the all-bills dashboard is redundant because **the landing timeline already is the portfolio view** (owner's point). Decisions banked ([[ideas/war_room_scoping]]): star = binary tracking (D5); write path = Worker+D1 (D2, verified free-tier, portability/canary/decoupling as design law); identity = Access, 1-month session, no name-pick. **Design research CLOSED** ([[design/object_page_patterns]]; rules → [[design/information_display]] §5b/P20–P20a, §5c/P21–P22). **Design reading CLOSED 2026-07-17** (to the limit of free primary sources; the books are paid + marked 🔒). It answered *"what is the bill page?"* — **there is no bill page: verified in code, `web/` has NO routing at all, so a bill has no URL.** In ORCA terms the card + the lists are two of the Bill object's representations and we **never built its detail** — that's the "page". Input canon also landed ([[design/information_display]] §5c/P21–P22) because the war room is the product's first WRITE surface and had none. Blocking the BUILD: (a) the **mockup** (owner's standing rule: mock up before code) — next action; (b) **member/committee roster ingestion — we ingest none of it, though it is confirmed AVAILABLE on our LIS key** ([[architecture/strategic_tools_placement]]): an unbuilt ingest, not a missing source; (c) the roster-row fact/intel boundary (the one unresolved design spot); (d) the MVP cut (D4) — ORCA says make it by downgrading OBJECTS, not by trimming features.
- Also open (owner-triggered): `/code-review ultra`; co-patrons backfill (scoped, deferred — [[ideas/copatrons_backfill]]).

## RECENTLY LANDED (newest first; full detail in [[log]])
- **2026-07-13 — BUILD WAVE executed ([[audits/build_wave_2026-07/README]]): endpoint-parity audit (#220/#221), docket-drop histogram (#222), Change-Ledger differ + 26 goldens (#223/#224), incident-counter mechanism + 9 goldens (#225), war-room memo. Worker untouched.** Gated remainder now tracked in NEXT: Change-Ledger live feed + Changes tab → 2027-in-season; incident-counter wiring → owner decisions.
- **2026-07-13 — #219 MERGED: the card bundle LIVE + the Opus build-wave spec banked.** Next-meeting row (Option 2) verified on prod (HB463 · Cohen → "Tue, Jul 21 · 10:00 AM · in 7 days" + real agenda/livestream links); dashed unplaceable (amber = one meaning now); grey crossover chip; patron on list cards; two-step untrack (+ multi-star capture fix). Execution queue for the next sessions: [[audits/build_wave_2026-07/README]].
- **2026-07-12 — #217 MERGED (VA queue emptied): label-based agenda-FETCH target.** The bill-extraction FETCH stopped mining livestream/registration pages — `_agenda_fetch_target` selects by label (real agenda → committee homepage → nothing). Live before/after: 82 retargeted to the real agenda PDF, 15 registration/notice pages dropped, 0 real agendas lost. `WORKER_OUTPUT_LOGIC_VERSION`→`2026-07-12.3`; closes [[state/open_anti_patterns]] #13. Also #216 (scroll affordance) merged + the owner's Drive reorganized (production sheet renamed off "Test Mastermind").
- **2026-07-12 — #214 + #215 MERGED: the 0→66 root-caused (UnboundLocalError in an API-outage costume), agenda links + §9 anchor ladder BOTH live, verified.** All three trip cycles carried the literal alert naming the unbound variable in `Metrics_History`; the broad schedule `except` had disguised a code bug as an LIS outage through three wrong diagnoses. Fixed placement, split the except (code bugs now alert CRITICAL/UNKNOWN with type+line), added the pyflakes pre-push gate (check 17), folded the §9 rung telemetry into SYSTEM_METRICS. Restored audit #102-#104 (lost in the revert), new lesson #105. [[failures/assumptions_audit#105]], [[failures/gemini_review_patterns]] #55/#56.
- **2026-07-11 — auto-refresh + Option-A calendar + B-7 guard + witness fix LIVE; agenda/§9 worker HOTFIXED out.** Re-shipped #211 minus §9 (#212 merged), but its first full recompute tripped the breaker at `meeting_unsourced=66` — same as the §9 merge, proving §9 innocent. Reverted the WORKER to known-good; kept the breaker-safe frontend + B-7 + witness. Fold-in lessons: [[failures/gemini_review_patterns]] #53/#54. [[ideas/meeting_agenda_links]], [[ideas/auto_refresh_on_new_data]].

## Watch items
- **⏰ 2027 SESSION OPEN → activate the gated build-wave features.** When the worker detects the 2027 regular
  session (session rollover), the Change-Ledger live feed + Changes tab become validatable and the docket-drop
  histogram becomes measurable. To do at session open: (1) dry-run `tools/change_ledger/` per
  [[architecture/change_ledger]]'s validation plan, verify rows vs LIS, then ship the Changes tab; (2) re-run
  `witness_histogram.yml` for the real docket-drop hour → update [[ideas/lobbyist_jtbd_ideation]] §2/A2. This
  is the standing reminder the "2027-gated" work points back to.
- **⚠️ REVIEWER BENCH IS DOWN TO ONE — audited 2026-07-27.** Evidence from PR #232's own comments:
  **Gemini** — *"the consumer version of Gemini Code Assist on GitHub has been sunset"* → **dead**.
  **Codex** — *"You have reached your Codex usage limits for code reviews"* → **out of quota** (it said this
  again after an explicit `@codex review`). **Qodo** — *"reviews are paused because your trial has…"* →
  **the permanent free tier is gone**; it is a 14-day trial now. **CodeRabbit** — *"Review limit reached…
  next review available in 3 minutes"* → **alive but rate-limited** (free tier ≈ 4 PR reviews/hour, 200
  files/hour), and it is the ONLY one left.
  **Consequence I caused: PR #232 merged with ZERO review coverage** — I opened three PRs in quick succession
  and outran the one remaining reviewer. Re-requested after the fact.
  **Rule going forward: space PRs to CodeRabbit's cadence, and never merge on green CI alone when the review
  slot was skipped** — CI proves the tests pass, not that the design is right.
  **Full strategy + the measurement plan: [[workflow/reviewer_strategy]]** — key finding: LLM reviewers are
  CORRELATED, so stacking them has diminishing returns; catch rate rises with DIVERSITY OF METHOD. Our own
  56-lesson record shows the real gaps are **security (≈0 findings), performance (1), concurrency (3)**, so
  the ranked free adds are **Semgrep (security) + mypy (types) ABOVE another LLM bot**, plus **mutation
  testing** as the only honest way to answer "what IS our catch rate?". All three await an owner decision.
  **Free options for a PRIVATE repo (researched 2026-07-27):** *PR-Agent* (open-source, self-hosted, no
  licensing cost) and *Semgrep* (security-focused, free ≤10 contributors) are the only genuinely free adds;
  *Sourcery* is free for OPEN-SOURCE repos only and *Greptile* has no free tier, so neither helps us.
- ~~**Gemini Code Assist bot sunsets 2026-07-17**~~ (consumer install blocked since 06-18; still reviewing PRs until then). Replacement bench (CodeRabbit + Qodo + Codex) already live. No action unless a gap appears after 07-17.

## What changes this page
Anything that changes "what is Tucker working on right now?" — opening/closing/merging a PR, shifting the goal, pausing/resuming a thread. Updated every session per the MOVE-only rule above; historical narrative goes to [[log]], never here.
