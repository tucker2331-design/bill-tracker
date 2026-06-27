---
tags: [workflow, brain, multi-state, organization, learning, decision]
updated: 2026-06-25
status: active
---

# The Cross-State Brain — shared learning vs per-state facts ("mega brain")

Owner raised the core tension (2026-06-25): per-state brains are smart, **BUT the whole point of the brain
is to LEARN so each new state is EASIER to build.** If every state gets a *separate* brain (the way Codex
spun up `docs/ny/` fresh), then all the hard-won VA lessons **don't carry to NY** — the brain stops
compounding, which defeats its purpose. We must resolve this. The answer is the same `core/ + states/`
shape we're applying to the code (see [[ideas/multi_state_org_structure]]), applied to the brain:

## The rule: generalizable lesson → SHARED brain; state-specific fact → per-state brain
- **SHARED brain (the "mega brain" — `docs/` root, the accumulated cross-state wisdom).** State-AGNOSTIC
  things every future state inherits on day one:
  - the **engineering standards** (CLAUDE.md's 8 standards; the 15-point pre-push audit),
  - the **failure patterns** ([[failures/assumptions_audit]], [[failures/gemini_review_patterns]] — these are
    *patterns*, not VA trivia: "displaying an API field ≠ parsing"; "`or`-on-nullable"; "verify a metric on
    a run whose headSha contains the commit"; the source-miss-visibility rule),
  - the **trust-layer philosophy** ("allowed not to know, never pretend"; provisional flags; denominators),
  - the **structural-determinism discipline** (no text parsing on the lobbyist path),
  - the **workflow** (branch+PR, bot-review fold-in, write-back mandate),
  - the **cross-state strategy + org** ([[ideas/multi_state_data_strategy]], [[ideas/multi_state_org_structure]]).
- **PER-STATE brain (`docs/<state>/` — thin overlay).** ONLY what's true for that state and nowhere else:
  - its data **sources** (VA = LIS blobs/APIs; NY = OpenLeg API; PA = hourly bulk + scrape),
  - its **quirks** (VA's "Time TBA"/`IsCancelled`/`OnCalendar`; NY's Assembly-not-in-OpenLeg gap),
  - its **source manifest**, live **status**, and state-local **assumptions register**.
  Per-state pages **link UP to the shared lessons; they never re-derive them.**

## The conflict to fix (current debt)
1. **`docs/` root currently MIXES shared wisdom with VA-specific facts** (e.g. `architecture/calendar_pipeline`,
   `knowledge/lis_api_reference`, `knowledge/tba_times`, `testing/crossover_audit` are VA-specific and should
   move under `docs/va/`; the *standards/failures/workflow/strategy* stay shared in root). Until split, "the
   VA brain" and "the shared brain" are the same pile — so a new state can't tell what to inherit.
2. **`docs/ny/` DUPLICATED structure instead of referencing shared** (Codex mirrored the folder tree). Its
   *state-specific* pages are right; but anything generalizable it learned (or should inherit) must live in
   the shared brain, not be re-written per state.

## The fix (do in the reorg, before heavy NY — owner: "sooner rather than later")
- **Extract VA-specific pages from `docs/` root into `docs/va/`**, leaving root = the shared brain.
- **Keep `docs/<state>/` thin**; convert duplicated generalizable content into links to the shared brain.
- **Two-way learning rule, codified:** finishing any state surfaces (a) state facts → its `docs/<state>/`,
  and (b) generalizable lessons → the SHARED brain (so the next state inherits them automatically). When in
  doubt: *"would this help build a DIFFERENT state?"* → yes = shared, no = per-state.
- **`scope:` frontmatter** (`shared` | `va` | `ny` | …) as the interim marker before/after the move, so the
  reuse manifest is greppable.

## Why this is the whole game
The shared brain is the **compounding asset**: VA cost enormous effort and produced deep generalizable
lessons; NY should pay a fraction because it *inherits* them; state #10 should be nearly mechanical. A pile
of separate per-state brains throws that compounding away. The mega-brain (shared core) is how "the brain
makes each state easier" actually happens. This is the brain-side of Standard #6 (scalable to 50 states).

See also [[workflow/persistent_memory]] (docs/ IS the brain), [[ideas/multi_state_org_structure]] (the code
side of the same split), [[ideas/multi_state_data_strategy]], the NY brain in `docs/ny/`.
