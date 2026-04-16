# Project Standards — Virginia Legislative Bill Tracker

## Owner
Tucker Ward — building an enterprise legislative intelligence platform for lobbyists tracking Virginia General Assembly bills.

## Current Goal
Calendar 100% accuracy vs LIS website. The accuracy metric is in X-Ray Section 9: **meeting actions without times = bugs**. Every action that happened in a meeting (vote, report, reading, recommendation) must show the time of that meeting. Administrative actions (referrals, printing, filing) belong in Ledger Updates with no time expectation. When the bug count hits **0** and unclassified hits **0**, we're done. Testing against crossover week (Feb 9-13, 2026) as the hardest edge case concentration.

**Current active focus and bug count:** see `docs/state/current_status.md`. Do not restate here — that file is the live source.

---

## Persistent Memory — Read `docs/` First

The `docs/` folder is the project **brain**. It is an Obsidian vault of markdown files. **All persistent memory (failure lessons, API quirks, workflow rules, architecture notes, live state) lives there, not in global `~/.claude/` memory.**

### At the start of every session (read these first)
1. `docs/index.md` — catalog of every page in the vault. Know what exists before you answer.
2. `docs/state/current_status.md` — what's active right now.
3. `docs/state/open_anti_patterns.md` — known silent-fallback debt in the code.

### Route by task (read on demand)
| Task involves... | Read FIRST |
|------------------|------------|
| API calls, scraping, data parsing | `docs/knowledge/` |
| Data flow, architecture | `docs/architecture/` |
| Debugging, investigating failures | `docs/failures/` + `docs/testing/` |
| Planning next steps | `docs/ideas/` + `docs/state/current_status.md` |
| Workflow / process / branching / PR rules | `docs/workflow/` |

Full routing and the 3-phase protocol: `docs/workflow/three_phase_protocol.md`. That page is authoritative; this file summarizes.

### Write-back: every session ends with knowledge extraction
Nothing learned in a session may be lost. Route every artifact to the right page in `docs/`:

| Artifact | Lands in |
|----------|----------|
| External code review anti-pattern (Gemini, etc.) | `docs/failures/gemini_review_patterns.md` — **extract BEFORE writing any fix** |
| Bug fixed | `docs/failures/assumptions_audit.md` — numbered, append-only |
| Framework-level lesson | New page in `docs/failures/`, linked from `docs/index.md` |
| API quirk | `docs/knowledge/` |
| Architecture change | `docs/architecture/` |
| Test result / metric delta | `docs/testing/crossover_week_baseline.md` |
| Idea or trade-off | `docs/ideas/future_improvements.md` |
| PR event (opened/merged/closed) | `docs/log.md` — `## [YYYY-MM-DD] pr \| <title>`, newest at top |
| Change in active focus | `docs/state/current_status.md` |
| New silent-fallback found in code | `docs/state/open_anti_patterns.md` |
| User feedback / preference | New page in `docs/workflow/` or update existing |

**Do NOT write persistent memory to `~/.claude/.../memory/`.** If the auto-memory system writes there, treat it as drift and migrate to `docs/` on the next session. See `docs/workflow/persistent_memory.md`.

### Obsidian conventions when writing vault pages
- **Wikilinks:** `[[page_name]]` or `[[folder/page_name]]`. Not markdown links (except for external URLs).
- **Frontmatter on every page:**
  ```yaml
  ---
  tags: [category, subcategory]
  updated: YYYY-MM-DD
  status: active | archived | stub
  ---
  ```
- **Update [[index]] whenever a new page is created.** Orphan pages (no inbound link) are a maintenance smell.
- **Append to [[log]]** for every structural vault change, PR event, or decision.

---

## Pre-Push Audit (9 points)

Before every commit. Full version in `docs/workflow/three_phase_protocol.md`.

1. **Verb Forms.** For every pattern/keyword list changed, verify ALL conjugations (base, past, present, plural).
2. **Function Scope.** Functions defined BEFORE all call sites. Never inside a conditional / try / loop body.
3. **Doc Version Sync.** Grep `docs/` for any stale version references.
4. **Duplicate File Check.** `pages/ray2.py` and `calendar_xray.py` must stay diff-identical. Streamlit serves `pages/`.
5. **Architecture Conformance.** Matches `docs/architecture/calendar_pipeline.md`. Update the doc if the flow changes.
6. **Zero-Trust Data.** No silent failures. No bare `except: pass`. No bare `continue` without a categorized alert.
7. **Cross-List Validation.** Classification lists — no accidental overlap between NOISE/EVENT/MEETING/ADMIN/FLOOR lists.
8. **Import Resolution from Subpage.** Any new top-level import touched by `pages/*.py` must be validated with `cd pages && python -c "import <module>"`. Parse-clean ≠ import-clean.
9. **Source-Miss Visibility.** Grep the diff for `"Journal Entry"`, `"Ledger Updates"`, `"Time TBA"`, `"TBA"`, bare `continue`, `except: pass`. Each one must have a visible tag / alert / counter beside it. Rule: `docs/workflow/source_miss_visibility.md`.

---

## Non-Negotiable Engineering Standards

### 1. ZERO ASSUMPTIONS
- Never hardcode values derivable from an authoritative source at runtime.
- Static values must have runtime validation that alerts when they drift.
- Every heuristic documented: what it assumes, how it breaks, what runtime check validates it.

### 2. BANK-GRADE RELIABILITY
- Must run autonomously for years without manual intervention.
- No silent failures. Every exception produces a visible alert in Bug_Logs or the status dashboard.
- Circuit breakers: on anomalous data, stop and alert — don't write bad data.
- Reconciliation: periodically diff output against LIS to catch drift.

### 3. DATA-DRIVEN, NOT TEXT-DRIVEN
- Structural identifiers (API codes, primary keys, refids) over text parsing.
- Text parsing is a fallback; must be validated against structural data.

### 4. SELF-DESCRIBING ERRORS
- No suppressed warnings. Categorize + route.
- Categories: `TIMING_LAG`, `PARENT_CHILD`, `COMMITTEE_DRIFT`, `API_FAILURE`, `DATA_ANOMALY`, `UNKNOWN`.
- Severities: `INFO`, `WARN`, `CRITICAL`.
- `UNKNOWN` → human review.

### 5. DYNAMIC CONFIGURATION
- Session codes, committee maps, date ranges — derived from LIS APIs at runtime.
- Static config only for API keys and Google Sheet IDs.

### 6. SCALABILITY TO 50 STATES
- Every VA-specific pattern must be isolated and swappable.
- No logic assuming VA committee structure, naming, or calendar.

### 7. NO VIBE CODING
- Every change justified by data, not intuition.
- Match rates, edge case counts, before/after metrics.
- If you can't measure it, you can't ship it. **And your metric must have a denominator** — see `docs/workflow/source_miss_visibility.md`.

---

## Architecture (at-a-glance)

Full version: `docs/architecture/calendar_pipeline.md`.

1. **v2_shadow_test** (`pages/v2_shadow_test.py` + `backend_worker.py`) — main product. Worker "Mastermind Ghost Worker" every 15min via GitHub Actions → Google Sheets "Mastermind DB".
2. **calendar_worker.py + test_auto_calender.py** — calendar subsystem, perfected separately. "Mastermind Ghost Worker 2" every 15min. Merges into v2 once at 100% accuracy.
3. **pages/ray2.py** (+ `calendar_xray.py` backup) — X-Ray diagnostic. Streamlit serves `pages/ray2.py`. Root `calendar_xray.py` is diff-identical backup. `xray.py` is deprecated.

**File map (what Streamlit serves):**
- `test_auto_calender.py` — Streamlit entry
- `pages/ray2.py` — X-Ray (edit here for X-Ray changes)
- `pages/v2_shadow_test.py` — v2 shadow test
- `calendar_xray.py` — backup of `pages/ray2.py` (NOT served)
- `xray.py` — DEPRECATED

**Data sources (gold standard: LIS):**
- Schedule API — 3,310 entries for session 261, authoritative for meeting times
- HISTORY.CSV — 60,694 rows, Azure blob
- DOCKET.CSV — committee meeting bill assignments (Senate committees confirmed)
- Committee API — authoritative committee list (H01-H24, S01-S13)
- Session API — session lifecycle

**Key code concepts:** `build_committee_maps()`, `COMMITTEE_CODE_MAP`, `LOCAL_LEXICON`, `PARENT_COMMITTEE_MAP`, `NORM_TO_CODE`, `resolve_committee_from_refid()`, `find_api_schedule_match()`, bill state machine (`bill_locations`), convene time graph, location resolution priority, noise filter, action classification.

Resolution priorities, full signatures, and history are in `docs/architecture/calendar_pipeline.md`.
