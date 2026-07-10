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
- **PR [#211](https://github.com/tucker2331-design/bill-tracker/pull/211) OPEN** (`claude/calendar-landing-polish`, 6 commits) — §9 anchor ladder + `_committee_parent` multiset/lineage fix + READY debts + Option-A calendar/landing polish + B-7 stranded-work guard. Gates: SAFETY 0/2,889 clocks move · `relative_unresolved` 19→1 (survivor is a correct refusal) · full pure-logic suite + open_loops green. **Next: fold in bot reviews on the commits** per [[workflow/bot_review_fold_in]], then merge.
- **Meeting + agenda links (owner 2026-07-08: GO) — MEASURED + SCOPED, not built: [[ideas/meeting_agenda_links]].** Deliberately not half-built at the tail of a long session: it needs a Sheet1 **migration** (29→31 cols — an off-grid write is what caused [[failures/assumptions_audit#99]]) and it changes which URLs the worker fetches. Measured on live data: the current `agenda_url` takes the *first* `href` whenever the description says `agenda|docket|info`, which is correct 1,028× , correct-by-design 194× (rogue-nav into committee sites), and **points at a registration/video page 89×** — those get fetched and bill-regexed. LIS's own data contains the typo `'Subommittee Info'` ×17, so the label vocabulary **must** ship with a drift alert (Standard #1); its Description HTML is malformed, so parse anchors with BeautifulSoup, not regex.

## NEXT (needs owner infra / a decision — then I execute)
1. ~~Enable A-2 Part 2 manually~~ **NO LONGER OWNER-GATED — the worker auto-shards the witness itself at 6M** (`_autoshard_witness_if_full`, zero-touch, fail-closed). Nothing for the owner to run. `archive.py shard-witness` + `WITNESS_WORKBOOK=ops` remain as manual overrides only. [[audits/fable_2026-07/autonomy_upgrades]].
2. **C-8 Part 2** — NY independent oracle (reconciliation) ([[audits/fable_2026-07/codebase_longevity_audit]]). Needs a **LegiScan API key** + terms check. (C-8's vocab-canary gap is already largely closed — re-measured.)
3. **Multi-state — ONE STATE AT A TIME (owner directive 2026-07-07; notes preserved, do NOT lose):** tackle each new state as its own scoped project. Notes are banked and safe:
   - PA ingestion plan → [[audits/fable_2026-07/multistate_ingestion_pa]]
   - CA + FL research → [[audits/fable_2026-07/multistate_ingestion_ca_fl]]
   - 50-state decoupling (CDN inversion + Omni-Schema + Fleet) → [[audits/fable_2026-07/50_state_scaling_architecture]]
   - NY is the live 2nd state (its own brain: [[ny/state/current_status]]); C-8 Part 2 (LegiScan oracle) is its next step.
4. Optional/low-value: **S-3** (attic-move deprecated repo-root files — cosmetic, **but it breaks the paused worker's manual dispatch**, so it needs an explicit owner "yes, break it"; not done on blanket authority). ~~B-4 finish~~ **DONE 2026-07-10** (CLAUDE.md volatile-facts audit — all file/doc/function refs verified; fixed two real drifts: deploy target said "Cloudflare Pages", is Workers static-assets per `wrangler.toml`; stale page-count).
- Also open (owner-triggered): `/code-review ultra`; co-patrons backfill (scoped, deferred — [[ideas/copatrons_backfill]]).

## READY (unblocked — no owner input needed; I can execute any of these)
*The lane that did not exist until 2026-07-10. Every `open_loop:` page in the vault must appear here (or in
NOW/NEXT), or `tools/open_loops.py` fails the pre-push audit.*
- **Empty (2026-07-10).** All READY debts cleared this session — see RECENTLY LANDED. The B-7 guard also
  flagged the Floor stage as a lingering `open_loop`; investigation found it was **already shipped**
  (`bill_tracker.py` floor signal → Timeline `floor1`/`floor2`; live House-passed=2,345 / Senate=2,007), so
  its stale open-loop was closed. That is the guard working: it forces a look, and a look resolves it either way.

## RECENTLY LANDED (newest first; full detail in [[log]])
- **2026-07-10 — READY debts cleared: dead terminal-skip deleted · silent-heal counter added · date-drift measured away** — `TERMINAL_DESCRIPTION_PATTERNS`/`_is_terminal_legevent_description` DELETED (text-based, fail-unsafe, never fired since PR-C7; [[failures/assumptions_audit#103]]); `_clean_legevent_cell` now counts stringified-null heals + alerts on a flood ([[state/open_anti_patterns]] #12); HISTORY-vs-LegEvent date-drift **measured to 0 live rows** on the full 37,826-row sheet (0 meeting rows empty-time or NO_SCHEDULE_MATCH) — NOT built, it's a Section-9-critical time-engine change with no failing row to justify it ([[architecture/scalability_audit]]). Two new pure tests wired into CI.
- **2026-07-10 — §9 anchor ladder + two live mis-anchors fixed (pushed, PR pending)** — `relative_unresolved` 19→1 (survivor is a *correct* refusal: a 2025 row anchored to a prior session's recess). Found + fixed two pre-existing `_committee_parent` defects: token **sets** collapsed LIS's repeated-word subcommittee naming into its own parent, and the "deterministic" **alphabetical tie-break** was a coin flip that resolved correctly only because `"labor" < "public"`. Measured 209 matches → 207 identical, 2 corrected, 0 lost. [[failures/assumptions_audit#100]] / [[#101]] / [[#102]], [[ideas/calendar_chain_ordering]] §9d.
- **2026-07-10 — de-AI visual pass COMPLETE + reserved-colour doctrine** — finality is the fill (solid = final verdict, tint = still in play, grey = routine); dots removed site-wide; Option-A calendar (time is the accent); masthead top bar; Search rebuilt (origin-vs-now chamber, pagination, no 400-row cut); landing sized to 2/3 with the timeline peeking. Doctrine: [[design/dashboard_and_visual_language]].
- **2026-07-07 — #209 MERGED: alerts = STATE not stream (self-clearing) + witness auto-shard (zero-touch)** — alerts rebuilt (verdict + active-only + collapsed per-category cleared history; 300→18 conditions on live data); `_autoshard_witness_if_full` relocates the witness to VA·Ops itself at 6M (copy-verify-then-delete, fail-closed, 17 tests). Gemini fold-in fixed a CRITICAL recovery-gate bug ([[failures/assumptions_audit]] #98, = pre-push #11) + a regex-`\b` collapse bug ([[failures/gemini_review_patterns]] #51/#52), both tested.
- **2026-07-07 — Health-tab honesty MERGED (#206+#207) + A-2 Part 2 phase 2 (#208) + backlog audited clean** — alerts honest/layman-clear, ring no longer yellows for the experimental engine, capacity audit recommends the shard; witness-shard actuator flag-gated + safe-by-default; code-debt backlog paid down.

## Watch items
- **Gemini Code Assist bot sunsets 2026-07-17** (consumer install blocked since 06-18; still reviewing PRs until then). Replacement bench (CodeRabbit + Qodo + Codex) already live. No action unless a gap appears after 07-17.

## What changes this page
Anything that changes "what is Tucker working on right now?" — opening/closing/merging a PR, shifting the goal, pausing/resuming a thread. Updated every session per the MOVE-only rule above; historical narrative goes to [[log]], never here.
