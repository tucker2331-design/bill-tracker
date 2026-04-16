---
tags: [workflow, protocol]
updated: 2026-04-16
status: active
---

# 3-Phase Operating Protocol

Every task follows this lifecycle. No exceptions. Referenced from CLAUDE.md as the authoritative version.

## PHASE 1: Context Routing (before writing code)

**Do NOT read all docs blindly.** Route attention:

| Task involves... | Read FIRST |
|------------------|------------|
| API calls, scraping, data parsing | [[knowledge/lis_api_reference]] — auth, quirks, schemas. Treat external sources as brittle. |
| Data flow, pipeline logic, architecture | [[architecture/calendar_pipeline]] |
| Debugging, fixing tests, investigating failures | [[failures/assumptions_audit]] + [[failures/gemini_review_patterns]] + [[testing/crossover_week_baseline]] |
| Planning next steps, new features | [[ideas/future_improvements]] |
| Current focus / what's active right now | [[state/current_status]] + [[state/open_anti_patterns]] |
| Multiple categories | Read all relevant pages. When in doubt, read `docs/failures/` — cheapest way to avoid regressions. |

Always read [[index]] first to know what pages already exist.

## PHASE 2: Pre-Push Audit

Before committing, walk this checklist:

1. **Verb Forms.** For every pattern/keyword list changed, verify ALL conjugations exist (base, past, present, plural). Example: `incorporate`, `incorporated`, `incorporates`.
2. **Function Scope.** Every function defined BEFORE all call sites. Never inside a conditional / try / loop body. A function used in two places lives at module level or in the shared parent.
3. **Doc Version Sync.** For every version number or build string changed in code, grep `docs/` for stale references.
4. **Duplicate File Check.** For every edit, check if copies exist elsewhere (`pages/` vs root). Sync ALL copies. The file Streamlit serves is in `pages/`. The backup is at repo root.
5. **Architecture Conformance.** Implementation matches [[architecture/calendar_pipeline]]. Don't invent new data paths without updating the doc.
6. **Zero-Trust Data.** No silent failures. No bare `except: pass`. No bare `continue` in parsing / API logic without a categorized alert. See [[workflow/source_miss_visibility]].
7. **Cross-List Validation.** If modifying classification lists, verify no accidental contradictions: `set(LIST_A) & set(LIST_B)` should be intentional.
8. **Import Resolution from Subpage.** If adding a top-level import touched by `pages/*.py`, run from the subpage directory: `cd pages && python -c "import <module>"`. Parse-clean is not import-clean.
9. **Source-Miss Visibility.** Before pushing, grep the diff for these patterns — each one must have a visible tag / alert / counter beside it:
   - string-literal fallbacks (`"Journal Entry"`, `"Ledger Updates"`, `"Time TBA"`, `"TBA"`)
   - bare `continue` in a filter/map loop
   - `except: pass` or `except Exception: pass`
   See [[workflow/source_miss_visibility]] for the rule.

## PHASE 3: Write-Back Mandate

**Nothing learned in a session may be lost.**

| Artifact | Lands in |
|----------|----------|
| External code review (Gemini, etc.) anti-pattern | [[failures/gemini_review_patterns]] — **extracted BEFORE writing any fix code** |
| Bug fixed | [[failures/assumptions_audit]] — numbered, append-only |
| Framework-level lesson | New page in `docs/failures/` (e.g. [[failures/pr22_post_mortem]]) — linked from [[index]] |
| API quirk | [[knowledge/lis_api_reference]] or new page in `docs/knowledge/` |
| Architecture change | [[architecture/calendar_pipeline]] (or a sibling architecture page) |
| Test result / metric delta | [[testing/crossover_week_baseline]] progress tracker table |
| Idea or trade-off | [[ideas/future_improvements]] |
| PR event (opened/merged/closed) | [[log]] — newest at top, `## [YYYY-MM-DD] pr | <title>` |
| Change in active focus | [[state/current_status]] |
| New silent-fallback anti-pattern found in code | [[state/open_anti_patterns]] |
| User feedback / preference change | New page in `docs/workflow/` or update to an existing one |

**Catch-all:** Before concluding any session, do a Knowledge Extraction. If we encountered friction and solved it, discovered ANY system constraint, made an architectural decision, or generated a future idea — write it back.
