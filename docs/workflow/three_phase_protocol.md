---
tags: [workflow, protocol]
updated: 2026-05-11
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

Before committing, walk this checklist. **Points 1-9** are the original audit; **Points 10-15** were codified in PR-C7.0.5 after the PR-C7 work block surfaced six distinct bug classes during cold-start validation. Each new point cross-references the [[failures/assumptions_audit]] entry that justified codifying it — the entry is the historical record and contains the full reasoning + the worked example.

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
10. **Function-Scope Shadow Check.** For any function with a local `from X import Y` or `Y = ...` assignment where `Y` is also imported at module level, grep the function body for ALL references to `Y` and confirm every reference appears textually AFTER the local binding. Preferred fix: delete redundant local imports — Python's local-binding rule makes EVERY reference to `Y` in the function local-scoped, so an early reference (textually before the local binding) raises `UnboundLocalError`. This bug is invisible to `python -m py_compile` (parse-clean) and only surfaces at runtime when the function is actually invoked. See [[failures/assumptions_audit#50]].
11. **Side-Effect Gating Check.** For any state-carrying side effect (cache persist, state cell write, idempotent re-publication) inside an `if`/`else`/`try`/`finally`, ask: *can this gate ever be permanently true?* If yes AND the side effect is required to RECOVER from that state, the side effect must hoist OUT of the gate to run unconditionally. Grep EVERY enclosing `if` above the call site, not just the immediately surrounding one. Worked example: PR-C7 cold-start where persist gated on `_breaker_tripped` (and later on `if not final_df.empty:`) created a Groundhog Day deadlock — the breaker tripped, persist was skipped, next cycle reloaded zero, same trip, repeat forever. See [[failures/assumptions_audit#51]] (and the Gemini fold-in noting that "every enclosing `if`" matters, not just the most obvious one).
12. **Fallback Liveness Check.** For any `try X, fallback Y` pattern, periodically verify X is still the right primary. A WARN log line that fires every cycle for >24 hours is a bug signal, not a transient — cycle-stable WARNs are not transient by definition. Either delete the dead path (preferred) or invert the order so the working URL is primary. Worked example: `blob.lis.virginia.gov` was a dead CNAME alias that the worker had been falling back from for at least 36 hours, masking a state-wide LIS infrastructure change. See [[failures/assumptions_audit#52]].
13. **Dead-Path Resurrection Check.** When dropping a fallback or simplifying a defensive pattern, grep EVERY function-scope variable that was bound only on the path being removed. Confirm each is either re-bound unconditionally on the surviving path or no longer referenced downstream. Removing dead code can resurrect previously-dead error paths — a code path that was unreachable becomes reachable, and any variable that was only bound on the now-removed path raises `UnboundLocalError` on the resurrected path. See [[failures/assumptions_audit#52]] (Codex fold-in).
14. **Threshold Calibration Check.** Whenever a PR's diff is architecturally significant (changes the worker's row processing pipeline, classifier, recovery surface, or breaker inputs), grep every existing absolute threshold against the new steady-state and flag any that would now trip on healthy operation. **Treat any cycle-stable breaker trip as a CRITICAL calibration bug, not a transient.** Prefer delta-vs-rolling-baseline thresholds for metrics whose floor depends on system behavior; reserve absolute thresholds for genuine catastrophes (cardinality-bounded floors, hard memory limits, etc.). Worked example: PR-C1's `meeting_unsourced >= 50` (set against a pre-PR-C7 baseline of ~9) froze Sheet1 for 3+ days after PR-C7 shipped because the steady-state floor moved to ~150. See [[failures/assumptions_audit#53]].
15. **Sentinel-Value Collision Check.** For any state cell read or persisted-value load with a default-on-failure path, ask: *"is the default ever a legitimate runtime value?"* If yes, track presence as a separate boolean flag (not encoded by the value being zero / empty / etc.). Same root class as `Optional` / `Maybe`-type-confusion bugs in any language — the explicit-presence pattern is the universal answer. Worked example: PR-C7.0.4's initial fix keyed delta-check activation on `last_known_good_meeting_unsourced > 0`, which collided with the legitimate post-PR-C7.1 scenario where the classifier fix drives `meeting_unsourced` to 0 (Y2 = "0" is a valid baseline, not "baseline absent"). See [[failures/assumptions_audit#53]] (Codex P2 fold-in).

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
