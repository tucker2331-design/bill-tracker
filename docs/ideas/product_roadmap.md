---
tags: [ideas, roadmap, strategy, product]
updated: 2026-06-18
status: active
---

# Product Roadmap — post-accuracy direction

The calendar's core goal is **achieved and production-verified**: X-Ray Section 9 bug count = 0,
unclassified = 0, structural coverage 100% (see [[state/current_status]]). This session added the
infrastructure on top (LIS-safety guardrails #1/#2/#4, the incremental-STM flip — flag-gated). So
the question is no longer "is the calendar right" — it's **"what is the best product for a VA
lobbyist, and how do we build it."**

**Owner decision (2026-06-18): do NOT merge the calendar subsystem back into the old
`backend_worker.py` / `v2_shadow_test`.** Retrofitting the advanced calendar engine into the old
case is counterproductive ("slipping a new item into an old case"). The forward direction is a
purpose-built product around what we've made, not a merger backward. → see [[#Closed--dropped]].

**Anti-looping rule for this roadmap:** every item below states an explicit **GOAL (what we want
out of it / done-means)**. We do not start an item — especially the open-ended UI work — until its
goal and success criteria are written down. If we ever feel like we're circling, re-read the GOAL.

---

## PHASE A — Tooling continuity (NOW; has a clock)

### A1. Replace the sunsetting code reviewer  ⏳ IN PROGRESS
- **WHAT:** Gemini Code Assist (the bot that reviewed every PR this session) is being sunset —
  consumer install blocked 2026-06-18, all review activity ceases **2026-07-17**. Codex
  (`chatgpt-codex-connector`) is unaffected and keeps running.
- **DECISION:** add **CodeRabbit** (free for public repos — this repo is public; consensus
  best-in-class AI reviewer) and keep **Codex** → two independent reviewers, restoring the
  two-bot coverage we relied on (Gemini + Codex repeatedly caught *different* real bugs).
- **GOAL / done-means:** every future PR gets an automated CodeRabbit review + the existing Codex
  review, before mid-July, with no gap. `.coderabbit.yaml` (committed) tunes it to our standards
  (no silent failures, Standard #3, LIS-safety, structural classification).
- **OWNER ACTION (2 min, only you can — it's a GitHub App permission grant):** install CodeRabbit
  on the repo → https://github.com/apps/coderabbitai → "Install" → select `tucker2331-design/bill-tracker`.
  It will then auto-review this very PR (a live end-to-end test).

---

## PHASE B — Define the product, THEN design it (collaborative; the real next chapter)

This is the "what should lobbyists see / best site" work. **Sequence is deliberate: vision →
data → UI.** Designing UI before we know the user's jobs and what data backs them is exactly the
"looping without knowing what we want" trap the owner called out.

### B1. Product vision — the lobbyist's jobs-to-be-done  ✅ LOCKED → [[ideas/product_vision]]
- **DONE (2026-06-18):** the full vision + screen spec is locked in [[ideas/product_vision]] — the
  four lenses, the global Tracking/full switch, the landing (what's-new + crossover-lane timeline +
  mini-calendar), the calendar/search tabs, the bill card (with the recovered pin + correlation
  rule), the operator bug tab, and the **trust layer** (freshness/completeness/certainty — "never
  pretend to know"). Decisions-and-why captured so we don't re-litigate. Clients/positions and the
  historical tracker are explicitly parked there.

### B2. LIS data inventory + gap analysis  ⏳ DRAFTED → [[ideas/lis_data_inventory]] (awaiting owner §7 calls)
- **WHAT:** a complete catalog of (a) what LIS actually exposes (all ~246 endpoints / blobs /
  fields), (b) what we currently ingest for the calendar, (c) what we DON'T yet collect. Then map
  candidate features (from B1) to the data each needs → which are buildable from existing data vs
  require **database expansion** (collecting things we didn't need for the calendar).
- **GOAL / done-means:** a table — feature → required LIS data → have it? / need to start collecting
  it? — so feature decisions are grounded in data feasibility, and any DB expansion is deliberate
  and scoped, not discovered mid-build. **Owner explicitly wants to discuss this alongside the UI.**
- **WHY before B3:** the UI can only show what the data supports; this bounds the design space.

### B0 (decided 2026-06-18) — stack + backend foundation
- **Front-end stack: React + Vite, hosted free on Cloudflare Pages** (owner delegated the choice).
  Static SPA, never-sleeps CDN, full control for the custom timeline; reads the worker's data from
  the Google Sheet via gviz (the X-Ray's proven, free path). $0 end-to-end. Streamlit was the
  pragmatic alternative but fights the rich interactivity our vision needs.
- **Bill-data backend: rebuild structurally, do NOT port the old text logic.** Assessment of
  `backend_worker.py` (`process_history_state_machine`/`determine_lifecycle`): it is entirely
  text-parsing (regex committee scrape + `desc.startswith("h ")` chamber hack + hardcoded English
  death/admin macro lists + `on_bad_lines='skip'` silent drop) — the exact anti-pattern the calendar
  effort replaced. **Reuse its data MODEL + lifecycle/stage CONCEPTS; rebuild the implementation on
  `calendar_worker`'s structural engine** (committee codes, refid resolution, the structural router,
  LIS status/eventcode vocabularies, safe_fetch with completeness/truncation guards). The bill
  records derive from the structural per-bill state the worker already computes — not a second
  text pass. Completeness (top trust priority) starts free: processed distinct bills vs the HISTORY
  blob's distinct bills + the truncation guard; external `AdvancedLegislationSearch` count later.

### B3. UI / information-display design  📋 NOT STARTED (I do "a lot of reading" first)
- **WHAT:** research information-display + UI/UX best practices (dashboards, dense-data tables,
  legislative/financial-terminal patterns, progressive disclosure, accessibility), then design the
  most efficient + intuitive interface for the jobs in B1, within the data envelope of B2.
- **GOAL / done-means:** a research synthesis + concrete design proposals (wireframes/mockups) the
  owner can react to — not code yet. Build only after a design is chosen.
- **DEPENDS ON:** B1 (what it's for) + B2 (what it can show).

---

## PHASE C — Deferred to the 2027 session (genuinely data-gated)

VA GA is adjourned; HISTORY is static until 2027. These need live, changing data to build/validate.

- **C1. Forward-calendar block** — surface UPCOMING meetings before they happen (Schedule API
  future-window + reconciliation against actual outcomes). Design exists (Open PR #60). GOAL:
  lobbyists see what's scheduled next, not just what happened. The "real dynamic frontier."
- **C2. Meeting-driven cadence** (was guardrail #5) — run ~4×/hour only when a real meeting is on
  the calendar. GOAL: fresh data during meetings, quiet otherwise. Gated on the flip being live +
  on actual meetings to key off. Design in [[knowledge/lis_api_safety]].
- **C3. In-season flip validation + 2027 cold-start** — turn the incremental flip to
  `=shadow` then `=1` on a busy session day; re-hydrate via the parked Backfill Burst (#56). GOAL:
  the ~180s→~6s STM win confirmed live; the system wakes cleanly for a new session.

---

## PHASE D — Closed / dropped

- **Subsystem merger into `backend_worker.py` / `v2_shadow_test` — REJECTED (owner, 2026-06-18).**
  Don't retrofit the advanced calendar into the old case. Forward-build instead (Phase B).
- **"Section 9 residual polish" (the old item-4) — MOOT.** Section 9 is already 0 in production; the
  remaining rows are honest UPSTREAM limits (LIS publishes no time / "TBA" / HISTORY-vs-LegEvent
  date drift) or are correctly surfaced/flagged — not bugs. The only live remnant is the **Part C
  reconciliation verb pre-filter migration** (the last internal spot still using a text pre-filter;
  swap to structural for Standard #3 purity) — **someday-maybe, zero user impact**, do opportunistically.

---

## Execution order (owner-set)
1. **A1 reviewer** (now) → 2. **B1 vision** + **B2 data inventory** (the discussion the owner will
open) → 3. **B3 UI design** → 4. build chosen features → 5. **Phase C** when 2027 data is live.

See also [[state/current_status]], [[knowledge/lis_api_safety]], [[ideas/future_improvements]], [[index]], [[log]].
