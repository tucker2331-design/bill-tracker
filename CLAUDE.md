# Project Standards — Virginia Legislative Bill Tracker

## Owner
Tucker Ward — building an enterprise legislative intelligence platform for lobbyists tracking Virginia General Assembly bills.

## Current Goal (as of 2026-04-05)
Calendar 100% accuracy vs LIS website. The accuracy metric is in X-Ray Section 9: **meeting actions without times = bugs**. Every action that happened in a meeting (vote, report, reading, recommendation) must show the time of that meeting. Administrative actions (referrals, printing, filing) belong in Ledger Updates with no time expectation. When the bug count hits **0** and unclassified hits **0**, we're done. Testing against crossover week (Feb 9-13) as the hardest edge case concentration.

---

## 3-Phase Operating Protocol

Every task follows this lifecycle. No exceptions.

### PHASE 1: Context Routing (Before Writing Code)

**Do NOT blindly read all docs.** Assess the task, then route attention to what's needed:

| If the task involves... | Read FIRST |
|------------------------|------------|
| API calls, scraping, data parsing | `docs/knowledge/` — API quirks, schemas, auth. CRITICAL: treat all external sources as brittle. Verify expected schemas before writing extraction logic. |
| Data flow, pipeline logic, architecture | `docs/architecture/` — How data flows, what connects to what. |
| Debugging, fixing tests, investigating failures | `docs/failures/` AND `docs/testing/` — What already broke and why. Anti-patterns to avoid. |
| Planning next steps, new features | `docs/ideas/` — What's been considered, priorities, blockers. |
| Multiple categories | Read all relevant folders. When in doubt, read `docs/failures/` — it's the cheapest way to avoid regressions. |

### PHASE 2: Execution & Pre-Push Audit (Before Every Push)

Write your code. Then before committing, run through this checklist:

1. **Verb Forms**: For every pattern/keyword list changed, verify ALL conjugations exist (base, past, present, plural). Example: `incorporate`, `incorporated`, `incorporates`.
2. **Function Scope**: Every function must be defined BEFORE all call sites. Never inside conditional blocks (`if`, `for`, `with`). A function used in two places must be at module level or in the shared parent scope.
3. **Doc Version Sync**: For every version number or build string changed in code, grep `docs/` for stale references to the old value.
4. **Duplicate File Check**: For every file edited, check if copies exist elsewhere (e.g., `pages/` vs root). Sync ALL copies. The file Streamlit/runtime actually loads is in `pages/`.
5. **Architecture Conformance**: Verify implementation matches the data flow in `docs/architecture/`. Do not invent new data paths without updating the doc.
6. **Zero-Trust Data**: Verify no silent failures or bare `except: pass` anywhere in parsing or API logic. All brittle endpoints must fail gracefully with categorized alerts (severity + category). No unhandled exceptions.
7. **Cross-List Validation**: If modifying classification lists (KNOWN_EVENT, KNOWN_NOISE, MEETING_ACTION, ADMINISTRATIVE, ABSOLUTE_FLOOR_VERBS, DYNAMIC_VERBS), verify no contradictions between lists. `set(LIST_A) & set(LIST_B)` should be intentional, not accidental.
8. **Trace the Code Path**: For EVERY item added to ANY list, trace what the runtime does with it. Read the consuming code. KNOWN_NOISE items are **silently deleted** — only truly disposable content belongs there. KNOWN_EVENT items are **preserved**. If you can't state with certainty what happens to an item at runtime, you haven't done your job. Never assume a list name describes its behavior — read the code that consumes it.
9. **100% Confidence Gate**: Do not commit unless you are 100% confident every change is correct. If any doubt exists, investigate it first. "Probably works" is not acceptable — prove it works with data. Run the cross-list validation script against HISTORY.CSV before every push that touches classification lists.

### PHASE 3: Write-Back Mandate (After Every Task)

**Nothing learned in a session may be lost.**

- **External Audits (Gemini, etc.)**: When an external code review is pasted, the VERY FIRST action — before writing any fix code — is to extract the anti-patterns and log them to `docs/failures/gemini_review_patterns.md`. Then fix.
- **Bugs Fixed**: Add to `docs/failures/assumptions_audit.md` — what broke, why, how fixed, what to watch for.
- **API Quirks Discovered**: Add to `docs/knowledge/lis_api_reference.md`.
- **Architecture Changes**: Update `docs/architecture/calendar_pipeline.md`.
- **Test Results**: Update `docs/testing/crossover_week_baseline.md` with before/after metrics.
- **Ideas or Trade-offs**: Add to `docs/ideas/future_improvements.md`.
- **Catch-All**: Before concluding any session, perform a Knowledge Extraction. If we encountered friction and solved it, discovered ANY system constraint, made an architectural decision, or generated a future idea — write it back to the appropriate `docs/` folder.

---

## Non-Negotiable Engineering Standards

### 1. ZERO ASSUMPTIONS
- Never hardcode values that can be derived from an authoritative data source at runtime.
- If a value must be static, it must have runtime validation that alerts when it drifts.
- Every heuristic must be documented with: what assumption it makes, how it could break, and what runtime check validates it.
- If you're not sure something is always true, it isn't. Flag it.

### 2. BANK-GRADE RELIABILITY
- The system must run autonomously for years without manual intervention.
- No silent failures. Every exception must produce a visible alert in Bug_Logs or the system status dashboard.
- Self-monitoring: the system should detect when its own data is stale, incomplete, or anomalous.
- Circuit breakers: if data looks wrong (e.g., zero events on a weekday during session), stop processing and alert — don't write bad data.
- Reconciliation: periodically compare output against source (LIS) to catch drift.

### 3. DATA-DRIVEN, NOT TEXT-DRIVEN
- Use structural identifiers (API codes, primary keys, refids) over text parsing wherever possible.
- Text parsing is a fallback, never the primary method.
- When text parsing must be used, it must be validated against structural data.

### 4. SELF-DESCRIBING ERRORS
- Never suppress a warning. Categorize it (severity + category) and route it to the appropriate dashboard.
- Categories: `TIMING_LAG`, `PARENT_CHILD`, `COMMITTEE_DRIFT`, `API_FAILURE`, `DATA_ANOMALY`, `UNKNOWN`
- Severities: `INFO` (expected edge case), `WARN` (unexpected but non-breaking), `CRITICAL` (data integrity at risk)
- Anything categorized as `UNKNOWN` must be surfaced for human review.

### 5. DYNAMIC CONFIGURATION
- Session codes, committee maps, date ranges — all must be derived from LIS APIs at runtime.
- Committee API: `https://lis.virginia.gov/Committee/api/getcommitteelistasync?sessionCode=X`
- Session API: `https://lis.virginia.gov/Session/api/GetSessionListAsync`
- Schedule API: `https://lis.virginia.gov/Schedule/api/getschedulelistasync?sessionCode=X`
- Static config is only acceptable for API keys and Google Sheet IDs.

### 6. SCALABILITY TO 50 STATES
- Every Virginia-specific pattern must be isolated and swappable.
- No logic that assumes Virginia's committee structure, naming conventions, or legislative calendar.
- The goal is to replicate this system for all 50 states by swapping configuration, not rewriting code.

### 7. NO VIBE CODING
- Every change must be justified by data, not intuition.
- "It probably works" is not acceptable. Prove it works with numbers.
- Match rates, edge case counts, and before/after metrics for every change.
- If you can't measure it, you can't ship it.

---

## Architecture

### Current State
1. **v2_shadow_test** (pages/v2_shadow_test.py + backend_worker.py) — Main product. Backend worker runs every 15min via GitHub Actions ("Mastermind Ghost Worker"), writes to Google Sheets "Mastermind DB".
2. **calendar_worker.py + test_auto_calender.py** — Calendar subsystem being perfected separately. Runs as "Mastermind Ghost Worker 2" every 15min. Will be merged into v2 once 100% accurate.
3. **pages/ray2.py** (+ calendar_xray.py backup) — X-Ray diagnostic tool. Streamlit serves `pages/ray2.py`. The root-level `calendar_xray.py` is kept in sync as a backup. The old `xray.py` is deprecated.

### Data Sources (Gold Standard: LIS)
- **LIS Schedule API** — Authoritative source for meeting times. 3,310 entries for session 261.
- **HISTORY.CSV** — 60,694 rows of bill action history from Azure blob storage.
- **DOCKET.CSV** — Committee meeting bill assignments (Senate committees S01-S13).
- **Committee API** — Authoritative committee list with codes (H01-H24, S01-S13).
- **Session API** — Session lifecycle (IsActive, start/end dates, crossover).

### Persistent Storage
- Google Sheets: Mastermind DB (Sheet1), Bug_Logs, API_Cache
- GitHub Actions: scheduled runners every 15 minutes

### Key Code Concepts
- **build_committee_maps()** — Rebuilds COMMITTEE_CODE_MAP, LOCAL_LEXICON, and PARENT_COMMITTEE_MAP from Committee API at runtime. Static fallback with drift alerting if API fails.
- **COMMITTEE_CODE_MAP** — Rebuilt from Committee API each run. Static fallback validated against session 261.
- **LOCAL_LEXICON** — Auto-derived from Committee API names (comma/and splitting). Not hardcoded.
- **PARENT_COMMITTEE_MAP** — Maps subcommittee codes to parent codes via ParentCommitteeID.
- **NORM_TO_CODE** — Pre-calculated reverse lookup dict (normalized_name -> code) for O(1) lookups.
- **resolve_committee_from_refid()** — Structural primary key lookup from History_refid column.
- **find_api_schedule_match()** — Fuzzy matching between HISTORY.CSV events and Schedule API. Uses PARENT_COMMITTEE_MAP for validated subcommittee->parent fallback.
- **Bill state machine** — `bill_locations` dict tracking each bill's current committee.
- **Convene time graph** — Resolution of relative times ("upon adjournment", "15 min after").
- **Location resolution priority**: ABSOLUTE_FLOOR_VERBS (always floor) → DYNAMIC_VERBS (contextual, resolved by refid/lexicon/Memory Anchor) → committee lookup.
- **Noise filter**: KNOWN_NOISE (silently filtered) → KNOWN_EVENT (passes through) → UNKNOWN (flagged with ❓).
- **Action classification** (X-Ray): MEETING_ACTION_PATTERNS (must have times) vs ADMINISTRATIVE_PATTERNS (Ledger is OK) vs unclassified (needs human review).

### File Map (What Streamlit Actually Serves)
- `test_auto_calender.py` — Main Streamlit app entry point
- `pages/ray2.py` — X-Ray diagnostic (sidebar page). **This is the file to edit for X-Ray changes.**
- `pages/v2_shadow_test.py` — v2 shadow test page
- `calendar_xray.py` — Kept in sync with `pages/ray2.py` as backup. NOT served by Streamlit.
- `xray.py` — DEPRECATED. Do not edit.

## Project Knowledge Base (docs/)
- `docs/architecture/` — System design, data flow, integration plans
- `docs/testing/` — Test plans, baselines, regression metrics
- `docs/failures/` — Post-mortems, assumption audits, Gemini review patterns
- `docs/ideas/` — Future improvements, trade-offs, optimization candidates
- `docs/knowledge/` — LIS domain knowledge, API quirks, legislative process

## Future Integration Plan
1. Calendar subsystem merges into v2_shadow_test
2. Bug dashboard integration (Bug_Logs sheet already exists in v2)
3. Nightly session/committee discovery bot (Session API + Committee API)
4. Expand to additional states
