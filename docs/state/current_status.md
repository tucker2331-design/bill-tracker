---
tags: [state, live]
updated: 2026-07-10
status: active
---

# Current Status

**Owner:** Tucker Ward
**Live site:** https://bill-tracker.tucker2331.workers.dev (Cloudflare Workers static-assets; deploy green). **Sheets:** VA·Live `1PQD…JGKM` · VA·Archive `1AA-d…QeA` · VA·Ops `1X7wa4b…` (naming schema `<Jurisdiction> · <Role>`).
**Project goal:** Calendar 100% accuracy vs LIS website. Metric: [[testing/crossover_week_baseline|X-Ray Section 9 bug count]] → 0 + unclassified → 0. **Achieved + holding (Section 9 = 0 since 2026-06-06).**
**Benchmark window:** Full 2026 VA GA session (2026-01-14 → 2026-05-01). **VA GA is ADJOURNED — HISTORY is static until the 2027 session. Pre-launch: lobbyists are not using the product yet.**

> **MOVE-only page (B-1, 2026-07-06):** ≤3 items in NOW, the ordered queue in NEXT/READY, ≤5 one-liners in
> RECENTLY LANDED. Finishing a task MOVES its line NOW→RECENTLY LANDED and evicts the oldest; nothing is
> appended below. Full history: [[log]] (PR-by-PR) + [[state/status_archive_2026H1]] (frozen pre-B-1 narrative).
>
> **READY exists because NEXT was defined as "needs owner infra / a decision" (2026-07-10).** That left
> unblocked engineering residuals with NO lane — not NOW, not NEXT — so they survived only inside plan pages
> in `ideas/` and were invisible to every "is the to-do clear?" check. That is exactly how the §9 relative-time
> residual sat for a week. Enforced by `tools/open_loops.py`: a page declaring `open_loop:` in its frontmatter
> MUST be wikilinked from this page, and a page marked `status: shipped` may not declare one.

## NOW
- **`claude/calendar-landing-polish` pushed (3 commits), PR not yet opened.** §9 anchor ladder + `_committee_parent` multiset/lineage fix; Option-A calendar colours; What's-new times; 2/3 landing; Search rebuild; reserved-colour tags. Gates: SAFETY 0/2,889 published clocks move · RESOLUTION `relative_unresolved` 19→1 (the survivor is a correct refusal) · 118 pure-logic checks. Open the PR, then fold in bot reviews per [[workflow/bot_review_fold_in]].
- **Meeting + agenda links (owner 2026-07-08: GO).** The worker already extracts `agenda_url` (`calendar_worker.py` ~L5517). Needs: a new Sheet1 column (**grow the 29-col grid carefully — an off-grid cell is what caused [[failures/assumptions_audit#99]]**) + the link surfaced in the front-end's click-to-expand meeting card.

## NEXT (needs owner infra / a decision — then I execute)
1. ~~Enable A-2 Part 2 manually~~ **NO LONGER OWNER-GATED — the worker auto-shards the witness itself at 6M** (`_autoshard_witness_if_full`, zero-touch, fail-closed). Nothing for the owner to run. `archive.py shard-witness` + `WITNESS_WORKBOOK=ops` remain as manual overrides only. [[audits/fable_2026-07/autonomy_upgrades]].
2. **C-8 Part 2** — NY independent oracle (reconciliation) ([[audits/fable_2026-07/codebase_longevity_audit]]). Needs a **LegiScan API key** + terms check. (C-8's vocab-canary gap is already largely closed — re-measured.)
3. **Multi-state — ONE STATE AT A TIME (owner directive 2026-07-07; notes preserved, do NOT lose):** tackle each new state as its own scoped project. Notes are banked and safe:
   - PA ingestion plan → [[audits/fable_2026-07/multistate_ingestion_pa]]
   - CA + FL research → [[audits/fable_2026-07/multistate_ingestion_ca_fl]]
   - 50-state decoupling (CDN inversion + Omni-Schema + Fleet) → [[audits/fable_2026-07/50_state_scaling_architecture]]
   - NY is the live 2nd state (its own brain: [[ny/state/current_status]]); C-8 Part 2 (LegiScan oracle) is its next step.
4. Optional/low-value: **S-3** (attic-move deprecated repo-root files — cosmetic, breaks the paused worker's manual dispatch; do only if you want the cleanup); **B-4 finish** (audit CLAUDE.md's remaining volatile facts).
- Also open (owner-triggered): `/code-review ultra`; co-patrons backfill (scoped, deferred — [[ideas/copatrons_backfill]]).

## READY (unblocked — no owner input needed; I can execute any of these)
*The lane that did not exist until 2026-07-10. Every `open_loop:` page in the vault must appear here (or in
NOW/NEXT), or `tools/open_loops.py` fails the pre-push audit.*
1. **Two latent debts** — [[architecture/scalability_audit]]: (a) HISTORY-vs-LegEvent **date drift** — the calendar places a row by HISTORY date, which can be 1–2 days off LIS's authoritative LegEvent date; preferring the LegEvent date fixes 3 residual Section-9 rows *and* a latent calendar-accuracy bug (do it only for unambiguous single-occurrence events). (b) `_clean_legevent_cell` **heals silently** — a flood of normalized cells (an upstream schema change) would not surface. Trivial Standard-#4/#9 counter.
2. **Dead constant `TERMINAL_DESCRIPTION_PATTERNS = ()`** (`calendar_worker.py:1797`) — `_is_terminal_description` short-circuits to `False` on every call, so the branch has never once fired. It was to be populated "in PR-C7.2 after observing real LIS response shapes"; that PR never came. Either populate it from observed shapes or delete the branch. Tracked in [[state/open_anti_patterns]].
3. **[[design/ui_redesign_spec]] item 4 (Floor stage)** — *blocked on a dependency, not on the owner*: the backend must first emit a floor/passed-chamber signal. Listed so it stays visible rather than dissolving into a plan page.

## RECENTLY LANDED (newest first; full detail in [[log]])
- **2026-07-10 — §9 anchor ladder + two live mis-anchors fixed (pushed, PR pending)** — `relative_unresolved` 19→1 (survivor is a *correct* refusal: a 2025 row anchored to a prior session's recess). Found + fixed two pre-existing `_committee_parent` defects: token **sets** collapsed LIS's repeated-word subcommittee naming into its own parent, and the "deterministic" **alphabetical tie-break** was a coin flip that resolved correctly only because `"labor" < "public"`. Measured 209 matches → 207 identical, 2 corrected, 0 lost. [[failures/assumptions_audit#100]] / [[#101]] / [[#102]], [[ideas/calendar_chain_ordering]] §9d.
- **2026-07-10 — de-AI visual pass COMPLETE + reserved-colour doctrine** — finality is the fill (solid = final verdict, tint = still in play, grey = routine); dots removed site-wide; Option-A calendar (time is the accent); masthead top bar; Search rebuilt (origin-vs-now chamber, pagination, no 400-row cut); landing sized to 2/3 with the timeline peeking. Doctrine: [[design/dashboard_and_visual_language]].
- **2026-07-07 — #209 MERGED: alerts = STATE not stream (self-clearing) + witness auto-shard (zero-touch)** — alerts rebuilt (verdict + active-only + collapsed per-category cleared history; 300→18 conditions on live data); `_autoshard_witness_if_full` relocates the witness to VA·Ops itself at 6M (copy-verify-then-delete, fail-closed, 17 tests). Gemini fold-in fixed a CRITICAL recovery-gate bug ([[failures/assumptions_audit]] #98, = pre-push #11) + a regex-`\b` collapse bug ([[failures/gemini_review_patterns]] #51/#52), both tested.
- **2026-07-07 — Health-tab honesty MERGED (#206+#207) + A-2 Part 2 phase 2 (#208) + backlog audited clean** — alerts honest/layman-clear, ring no longer yellows for the experimental engine, capacity audit recommends the shard; witness-shard actuator flag-gated + safe-by-default; code-debt backlog paid down.
- **2026-07-06 — brain hygiene: B-2 · B-3 · B-6 + C-8 re-measured** — B-3 machine `tools/prepush_audit.py` (fails an output-value change with no version bump; runs in CI, #205 merged); B-2 generated `## Index` for the two case-law files (`tools/reindex_caselaw.py`); B-6 vault hygiene (0 orphans); C-8 NY re-measured (already hardened; oracle owner-gated).

## Watch items
- **Gemini Code Assist bot sunsets 2026-07-17** (consumer install blocked since 06-18; still reviewing PRs until then). Replacement bench (CodeRabbit + Qodo + Codex) already live. No action unless a gap appears after 07-17.

## What changes this page
Anything that changes "what is Tucker working on right now?" — opening/closing/merging a PR, shifting the goal, pausing/resuming a thread. Updated every session per the MOVE-only rule above; historical narrative goes to [[log]], never here.
