# Project Standards — Virginia Legislative Bill Tracker

## Owner
Tucker Ward — building an enterprise legislative intelligence platform for lobbyists tracking Virginia General Assembly bills.

## Non-Negotiable Engineering Standards

These standards apply to ALL code in this repository. Any AI working on this project MUST follow these without exception.

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

## Architecture

### Current State
1. **v2_shadow_test** (pages/v2_shadow_test.py + backend_worker.py) — Main product. Backend worker runs every 15min via GitHub Actions ("Mastermind Ghost Worker"), writes to Google Sheets "Mastermind DB".
2. **calendar_worker.py + test_auto_calender.py** — Calendar subsystem being perfected separately. Runs as "Mastermind Ghost Worker 2" every 15min. Will be merged into v2 once 100% accurate.
3. **calendar_xray.py** — Diagnostic tool for Sheet1 ↔ LIS schedule parity checks.

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
- **resolve_committee_from_refid()** — Structural primary key lookup from History_refid column.
- **find_api_schedule_match()** — Fuzzy matching between HISTORY.CSV events and Schedule API. Uses PARENT_COMMITTEE_MAP for validated subcommittee->parent fallback.
- **Bill state machine** — `bill_locations` dict tracking each bill's current committee.
- **Convene time graph** — Resolution of relative times ("upon adjournment", "15 min after").
- **Mismatch categorization** — PARENT_CHILD (INFO), TIMING_LAG (INFO), COMMITTEE_DRIFT (WARN).
- **Noise positive ID** — KNOWN_NOISE filtered, KNOWN_EVENT passes, UNKNOWN flagged for review.

## Current Goal (as of 2026-04-04)
Calendar 100% accuracy vs LIS website. Every committee event that happened at a real time must show that time. Ledger updates (administrative entries) must be collapsed into a single "Ledger Updates" block per day. Currently testing against crossover week (Feb 9-13) as the hardest edge case concentration.

## Project Knowledge Base

### MANDATORY: Read Before Write
**Before writing ANY code in this repository, you MUST read the relevant `docs/` files first.** This is not optional. The docs contain hard-won knowledge about bugs we've already fixed, API quirks that will bite you, and architecture decisions that exist for specific reasons. Skipping this step leads to regressions.

### MANDATORY: Document As You Go
When you fix a bug, discover an API quirk, or learn something new about the system:
1. **Bugs fixed** → Add to `docs/failures/` (what broke, why, how it was fixed, what to watch for)
2. **API quirks discovered** → Add to `docs/knowledge/` (endpoint, quirk, workaround)
3. **Architecture changes** → Update `docs/architecture/` (what changed, why, how data flows now)
4. **Test results** → Update `docs/testing/` (before/after metrics, new baselines)
5. **Ideas or trade-offs** → Add to `docs/ideas/` (what, why, priority, blockers)

This is how project memory persists between sessions. If you don't document it, the next session will repeat your mistakes.

### Directory Structure
- `docs/architecture/` — System design, data flow, integration plans
- `docs/testing/` — Test plans, baselines, regression metrics
- `docs/failures/` — Post-mortems, assumption audits, things that broke
- `docs/ideas/` — Future improvements, trade-offs, optimization candidates
- `docs/knowledge/` — LIS domain knowledge, API quirks, legislative process

## Future Integration Plan
1. Calendar subsystem merges into v2_shadow_test
2. Bug dashboard integration (Bug_Logs sheet already exists in v2)
3. Nightly session/committee discovery bot (Session API + Committee API)
4. Expand to additional states
