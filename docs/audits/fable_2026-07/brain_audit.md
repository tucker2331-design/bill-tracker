---
tags: [audit, fable, brain, workflow, meta]
updated: 2026-07-04
status: active
---

# FABLE 1 — Brain audit: what works, what to change so Opus performs closer to Fable

Auditor's basis: I (Fable) ran an entire multi-PR session (#188–#193) on this brain cold — routed by
[[index]] → [[state/current_status]] → task pages — plus the full vault inventory below. This page is
half retrospective, half prescription. The prescriptions are ordered by leverage-per-hour.

**Vault inventory (2026-07-04):** 65 pages, 2.8 MB. architecture 9 / design 4 / failures 4 (284 KB!) /
ideas 8 / knowledge 7 / ny 13 / state 4 / testing 4 (1.6 MB — data, not prose) / workflow 9.
Hot files: log.md 1,638 lines · assumptions_audit.md 732 lines · current_status.md 266 lines ·
CLAUDE.md 168 lines.

## What is genuinely working (keep, do not "improve")

- **The routing table + 3-phase protocol.** Cold-start to productive took one read of index +
  current_status. The task-routing table in CLAUDE.md is the single most valuable block in the repo.
- **assumptions_audit as numbered case-law.** It is the project's institutional memory of HOW failures
  happen, not just what failed. #95 (measure-before-fix) directly prevented me shipping a plausible no-op
  this session. The numbered, append-only, cross-referenced format is exactly right.
- **Write-back discipline.** Every PR event logged; every lesson filed. The brain never lied to me about
  project state — rare, and worth protecting at any cost.
- **The pre-push audit points 10–15 pattern**: each rule cites the failure that created it. Rules with
  provenance get followed; rules without get rationalized away.
- **Source-miss visibility doctrine** (every metric has a denominator; every silent path has a counter).
  This is the reason Section 9 = 0 is a *trustworthy* zero.

## Why Opus underperforms Fable here — the honest diagnosis

It is mostly NOT raw capability. It is that the brain currently rewards synthesis (reading 266 lines of
stale-mixed-with-fresh status and inferring what matters) and punishes literalism (CLAUDE.md contains
false facts; prose rules don't fire at the moment of action). Fable compensates by re-deriving context;
Opus anchors on what's written. **Therefore: make the written thing exactly true, small, and executable,
and the gap closes substantially.** The six changes below do that.

---

### B-1 — Restructure `state/current_status.md` from an append-log into a true state page
> **STATUS 2026-07-06: SHIPPED.** current_status rewritten to NOW / NEXT / RECENTLY LANDED (39 lines, gate
> ≤60); the 289-line history moved verbatim to [[state/status_archive_2026H1]] (no loss). MOVE-only rule
> added to CLAUDE.md's write-back table; index "START HERE" repointed to current_status; the stale
> [[state/next_session]] archived (this also closes sweep **S-6**).
- **What:** "Active focus" holds 10+ ▶️ entries dating to June, plus a "NEXT SESSION" pointer from
  2026-06-23 that is long-obsolete. A literal reader cannot tell NOW from HISTORY. 266 lines and growing.
- **Risk:** Opus anchors on stale directives (e.g. resurrects a completed queue), or burns context
  re-reading history every session.
- **Fix (detail):** Rewrite to a hard 3-section template, cap ~50 lines total:
  1. `## NOW` — at most 3 bullets: the active task(s), each one line + a wikilink to its plan page.
  2. `## NEXT` — the owner-ordered queue, one line each (link, don't describe).
  3. `## RECENTLY LANDED` — max 5 one-liners, newest first, each linking its log entry; older entries are
     DELETED from this page (they already live in [[log]]).
  Add to the write-back table in CLAUDE.md: *"current_status is MOVE-only: finishing a task moves its
  line from NOW to RECENTLY LANDED and evicts the oldest; nothing is ever appended below."*
  Migrate: move every existing ▶️ block verbatim into log.md (dated) if not already there (most are).
- **Validation:** `wc -l docs/state/current_status.md` ≤ 60 after every session; a fresh session can
  answer "what am I doing right now?" from the first screen.
- **Effort:** ~1 h once; enforced by rule after.

### B-2 — Add one-line indexes at the TOP of the two case-law files
> **STATUS 2026-07-06: SHIPPED.** `tools/reindex_caselaw.py` (stdlib-only, idempotent) generates the `## Index`
> block (`#N — <lesson>`) at the top of assumptions_audit.md (97) + gemini_review_patterns.md (50) from the
> entry headers themselves — recall is now a ~60-line read + a grep. Re-runnable = the maintenance rule (added
> to CLAUDE.md write-back: fix a bug → append the entry → re-run the tool).
- **What:** assumptions_audit (732 lines, 96 entries) and gemini_review_patterns are read wholesale when
  a model wants recall; that's ~25k tokens for what should be a 60-line skim.
- **Fix (detail):** At the top of each file, maintain a `## Index` block: `#N — <one-sentence lesson>`
  per line, grouped by theme (sentinels/caching/scope/process). The write-back rule already appends the
  full entry; extend it: *"and add the one-liner to the Index block."* Backfill the 96 existing entries
  (mechanical; the ### headings are already one-line summaries — copy them).
- **Validation:** recalling "have we seen this failure class?" costs one 60-line read; grep by keyword
  still works for depth.
- **Effort:** ~45 min backfill + rule.

### B-3 — Convert the pre-push audit from prose into an executable script
> **STATUS 2026-07-06: SHIPPED (PR #205).** `tools/prepush_audit.py` (stdlib-only) enforces the mechanical
> subset on a diff: (1) output-VALUE-affecting change → requires a `WORKER_OUTPUT_LOGIC_VERSION` bump —
> curated anchor set of Sheet1-value-computing fns, deliberately excluding gating/cadence/archive/auth so
> those aren't false-flagged; (4) ray2↔calendar_xray diff-identical; (6/9) untagged silent-fallback literals
> FAIL; (2/5) WARN reminders; judgment points print as a checklist. Wired as the `prepush-audit` job in
> structural_tests.yml (every PR). **Validated (measure-first): the #189 diff FAILS on the missing bump; the
> import-only S-1 and archive-only A-2 diffs PASS — no false-positives.** CLAUDE.md notes the tool.
- **What:** The 15-point audit is prose. Prose rules fire only when the model *thinks to* apply them.
  Evidence: PR #189 (Fable!) missed the logic-version bump; Qodo caught it a PR later
  ([[failures/assumptions_audit#96]]). If Fable misses prose rules, Opus will too.
- **Fix (detail):** Create `tools/prepush_audit.py` (stdlib-only so it can run in structural_tests.yml)
  that takes the staged diff (`git diff --cached` or a base ref) and mechanically checks what is
  mechanically checkable:
  1. Diff touches `_append_event` / Sheet1 column construction / `_STM_EVENT_KEY_FIELDS` ⇒ REQUIRE
     `WORKER_OUTPUT_LOGIC_VERSION` changed in the same diff (audit #96).
  2. New key added to a `master_events`/`_append_event` dict ⇒ REQUIRE it appears in
     `_STM_EVENT_KEY_FIELDS` (audit #96) and in the architecture schema table (grep docs).
  3. `pages/ray2.py` touched ⇒ REQUIRE `diff pages/ray2.py calendar_xray.py` empty (audit point 4).
  4. Diff adds `except: pass`, bare `continue` in worker files, `"Time TBA"`, `"Journal Entry"` ⇒ FAIL
     unless the line carries a `# audited:` tag (audit points 6/9).
  5. Diff touches a `_..._RE` pattern list ⇒ WARN with a checklist reminder for verb forms (point 1 is
     judgment; the script only reminds).
  6. Print a rendered copy of the judgment-only points (2, 5, 7, 11–15) as a checklist.
  Wire it: a `prepush-audit` job in structural_tests.yml (runs on every PR), and mention in CLAUDE.md
  ("run `python3 tools/prepush_audit.py` before commit; CI enforces the mechanical half").
- **Validation:** replay the #189 diff (`git diff 00c7354..bdb269c -- calendar_worker.py`) through the
  script → it must fail on the missing version bump.
- **Effort:** ~3 h. Highest rule-compliance leverage available.

### B-4 — CLAUDE.md is drifting; make it small and stable, push volatile facts to state pages
> **STATUS 2026-07-06: PARTIAL (surgical).** Fixed the actively-misleading + freshly-drifted facts: the
> Architecture at-a-glance no longer calls the PAUSED `backend_worker`/`v2_shadow_test` the "main product"
> (it's `bill_tracker` + `web/`), and the "every 15min" cadence claims are replaced with a "don't hardcode
> the interval — see the cadence ledger" pointer (guardrail #5 made both crons `*/15` self-throttled). The
> fuller pass (soften the illustrative row-counts, audit the whole file for volatile facts) remains.
- **What (verified drift):** CLAUDE.md says workers run "every 15min" (calendar is 3h since PR-C7.1f;
  bills 6h); the architecture summary predates the product backend split; Sheet1 is described via an
  11-column schema note elsewhere while reality is 15 columns (LegEventRoute, RefidClass, ScheduleClass,
  TimeClass). A literal model inherits false priors *before it reads anything else*.
- **Fix (detail):** One pass: delete every volatile number/cadence/schema fact from CLAUDE.md and replace
  with a pointer ("cadences: see [[knowledge/lis_api_safety]] ledger; schema: see
  [[architecture/calendar_pipeline]] §Sheet1"). Add a write-back rule: *"if a PR changes a cadence,
  schema, or file role, grep CLAUDE.md for the stale fact in the same PR"* — and add that grep to
  `tools/prepush_audit.py` (mechanical: cron strings in workflows vs CLAUDE.md text).
- **Effort:** ~1 h.

### B-5 — Distill the meta-lessons into a short `workflow/reasoning_doctrine.md` and put it in the session-start reads
> **STATUS 2026-07-06: SHIPPED.** [[workflow/reasoning_doctrine]] written (8 imperative moves: measure-first,
> verify-the-row, fail-open, confirm-before-advance, no silent fallback, structural-not-text, notify-only,
> write-back). Added to CLAUDE.md's session-start read list (#4) and [[index]] workflow section.
- **What:** The actual Fable-vs-Opus difference this session was PROCESS, not knowledge: (a) instrument
  current behavior before implementing a planned fix (#95); (b) build the validator BEFORE the change and
  let it arbitrate; (c) find the oracle + denominator first; (d) be willing to falsify the plan you were
  handed; (e) ask "which map key / axis am I not looking at?" (#91, #95). These live scattered inside
  700-line case-law files where they won't shape behavior at decision time.
- **Fix (detail):** Write `docs/workflow/reasoning_doctrine.md`, ≤40 lines, imperative voice, exactly
  five rules above each with its one-sentence case citation. Add it as read #4 in CLAUDE.md's
  session-start list. Then add one line to the PR-template/plan habit: every task plan must name its
  **oracle** (what independent thing proves it right), its **denominator**, and its **validator command**
  before code is written. That triplet is what made #189 and #191 land clean.
- **Effort:** ~30 min. Disproportionate payoff.

### B-6 — Vault hygiene (small items)
- `docs/testing/` is 1.6 MB of baseline data; mark those pages `status: archive-data` in frontmatter and
  note in [[index]] "do not read wholesale — grep only." Consider moving raw baselines to repo
  `artifacts/` and leaving summary pages.
- `docs/state/next_session.md` is superseded by current_status NOW/NEXT after B-1 — archive it (it
  already carries stale queues; two sources of "next" is one too many).
- The log's `## [date] kind | title` convention is excellent — keep; but log entries have grown to
  15–20 lines each. Cap new entries at ~8 lines; depth belongs in the linked page.
- Wikilink hygiene: run a quarterly orphan check (grep every `[[name]]` against files; list orphans in
  the lint log entry — the convention already exists, automate it in `tools/prepush_audit.py --vault`).

## What NOT to change

Do not split the vault into more folders; do not adopt heavier tooling (databases, embeddings) for 65
pages; do not rewrite history in log/audit files (append-only is the point); do not move the brain out of
the repo (same-commit atomicity of code+docs is a quiet superpower — e.g. #193's fold-in updated code and
architecture doc in one diff).
