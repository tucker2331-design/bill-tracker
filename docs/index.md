---
tags: [index, meta]
updated: 2026-04-16
---

# Project Brain — Index

The catalog of every page in this wiki. Open this first when looking something up. The LLM should also read this before answering any substantive question so it knows what pages already exist (don't duplicate, update in place).

Links use Obsidian `[[wikilink]]` format. Obsidian resolves by filename; path-qualified when the filename is ambiguous.

## Meta
- [[README]] — vault entry; how this brain is structured and how to maintain it
- [[index]] — this file
- [[log]] — chronological, append-only record of ingests / decisions / PRs / lint passes

## State (live trackers — read these to know what's happening NOW)
- [[state/current_status]] — active focus, open PR, current bug count, what's next
- [[state/open_anti_patterns]] — known silent fallbacks still living in the code (worker.py line debt)

## Workflow & Protocols (how we work)
- [[workflow/three_phase_protocol]] — context routing → pre-push audit → write-back mandate
- [[workflow/branching_rules]] — when to reuse vs create a branch (PR state decides)
- [[workflow/push_and_pr]] — after every commit: push, open PR, return link
- [[workflow/source_miss_visibility]] — mandatory rule: no silent fallback on a source miss
- [[workflow/persistent_memory]] — this `docs/` folder IS the brain; not global memory

## Architecture
- [[architecture/calendar_pipeline]] — LIS → worker → Sheet1 data flow + resolution priorities

## Domain Knowledge
- [[knowledge/lis_api_reference]] — VA LIS endpoints, auth, quirks
- [[knowledge/tba_times]] — Schedule API returns "Time TBA"; existence ≠ concrete time

## Testing & Metrics
- [[testing/crossover_week_baseline]] — Feb 9-13, 2026 as the benchmark; PR-by-PR bug count ledger

## Failures / Post-Mortems
- [[failures/assumptions_audit]] — every busted assumption and its fix (source of truth for "why we did that"); numbered, append-only
- [[failures/gemini_review_patterns]] — recurring mistakes caught in external code review (pre-push checklist)
- [[failures/pr22_post_mortem]] — framework-level lesson: we were measuring only the bugs we wanted to see

## Ideas / Deferred Work
- [[ideas/future_improvements]] — things on deck, priority-tagged

## Raw / Source (out of scope of this wiki)
The codebase itself (`calendar_worker.py`, `pages/ray2.py`, etc.) is the raw layer. The wiki describes it but does not duplicate it.

---

## Conventions (for the LLM maintaining this wiki)

- **Wikilinks over markdown links** where possible — Obsidian's graph view and backlinks depend on `[[name]]` syntax.
- **Frontmatter on every page:** `tags`, `updated: YYYY-MM-DD`, optional `status: active | archived | stub`.
- **One concept per page.** If a page covers two separate things, split it.
- **Cross-reference instead of duplicate.** If information belongs on page A, reference it from page B with a wikilink rather than copy-pasting.
- **Update on touch.** Whenever a page is read in service of a task, update the `updated:` field if the content needs refreshing.
- **New lessons → new pages.** Each post-mortem or framework insight gets its own page in `failures/`, then a link from the index.
