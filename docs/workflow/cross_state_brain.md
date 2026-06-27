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

## What actually carries over — the NUANCE (owner pushed: "more than that, more nuance")
It is NOT whole *files* copying over. It's **assets at different grains** — and it includes **code, design,
and methodology**, not just docs (the thin-list mistake). Four tiers:

- **Tier 1 — pure shared (inherit wholesale):** the 8 standards + the 15-point pre-push audit; the trust-layer
  PHILOSOPHY ("never pretend," provisional flags, denominators); structural-determinism (no text parsing on
  the lobbyist path; *displaying an API field ≠ parsing*); the workflow protocols (branch+PR, bot-review
  fold-in, write-back, the 3-phase protocol); **the PRODUCT VISION** (four lenses, crossover-lane timeline,
  bill card, trust layer); **the DESIGN SYSTEM** ([[design/reading_notes]] → [[design/information_display]]
  rules, the visual system, the bullet-graph Health, the calendar UI patterns, the reusable components). *A
  new state's product is the SAME product, restyled — same components, same lenses.*
- **Tier 2 — shared as PATTERNS, with VA instances as EVIDENCE (the key nuance).** [[failures/assumptions_audit]]
  and [[failures/gemini_review_patterns]] are NOT VA trivia: each entry is a *(generalizable pattern, VA
  instance)* pair. The PATTERN generalizes ("or-on-nullable-pandas," "verify a metric on a run whose headSha
  contains the commit," "the sentinel that outlived the session," "side-effect gating," "sentinel-value
  collision," "displaying ≠ parsing"); the instance is the proof. → a new state inherits the PATTERNS as a
  pre-flight checklist; the VA specifics stay as the evidence trail. **These files split at the LESSON level,
  not the file level** — the reorg should distill a generalized "engineering lessons / pre-flight checklist"
  from them into the shared layer, leaving the instances in place.
- **Tier 3 — the reusable ENGINE CODE (carries as CODE, not docs).** `structural_router` (meeting/admin
  framework), the reconciliation framework, the time-resolution machinery, the breaker / sentinel /
  sustainability-audit machinery, the trust/completeness primitives. The per-state **source adapters** (LIS
  blobs vs OpenLeg vs PA bulk) are written fresh against this shared `core/` (see [[ideas/multi_state_org_structure]]).
- **Tier 4 — pure per-state (don't carry):** the endpoints + source maps; the quirks (VA "Time TBA"/
  `IsCancelled`/`OnCalendar`; NY Assembly-not-in-OpenLeg); committee structure, session calendar, crossover
  date; the live status + the per-state assumptions register.

**The single most valuable transferable asset is the METHODOLOGY** (Tier 1): *how* we scope-before-build,
probe a source, validate against structural data, run the bot-review loop, and write back. That discipline —
not any VA fact — is what makes state #10 nearly mechanical.

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
