# Patterns Caught by Gemini Reviews

Recurring mistakes to self-check BEFORE pushing code. Each pattern has been caught at least once across PR reviews. This list should be consulted as a pre-push checklist.

## 1. Redundant Computation
**Pattern:** Calculating the same value twice in different sections of code.
**Examples:**
- Tag counts computed in Executive Summary, then recomputed in Deep Dive (PR#9)
- `str.contains().sum()` called again when dict already had the answer

**Self-check:** Before writing a computation, search the file for whether the result already exists in a variable. If it does, reuse it.

## 2. Variables Undefined on Exception Paths
**Pattern:** A variable is assigned inside a `try` block but referenced later outside it. If the `try` fails, the variable is never defined → `NameError`.
**Examples:**
- `cache_records` assigned inside try, used in cache write logic (PR#8)

**Self-check:** Any variable assigned inside a `try` block that's used after the `except` must be initialized before the `try`.

## 3. Constants Defined Inside Loops
**Pattern:** List/dict literals defined inside a loop body that runs thousands of times. Each iteration allocates a new object unnecessarily.
**Examples:**
- `KNOWN_NOISE_PATTERNS` and `KNOWN_EVENT_PATTERNS` defined inside 60k-row loop (PR#8)

**Self-check:** If a value doesn't change between iterations, it belongs at module level or above the loop.

## 4. O(n) Lookups Inside O(n) Loops = O(n^2)
**Pattern:** Linear search through a dict/list to find a reverse mapping, called once per row in a large dataset.
**Examples:**
- `next((c for c, n in COMMITTEE_CODE_MAP.items() if normalize(n) == target))` inside 60k-row loop (PR#8)
- Same pattern in mismatch detection (PR#8)

**Self-check:** If you need a reverse lookup, pre-build a reverse dict once. Never do `O(n)` inside `O(n)`.

## 5. Execution Order of Alerts/Side Effects
**Pattern:** Pushing an alert or side effect after the data it should appear in has already been consumed/written.
**Examples:**
- Cache write alert pushed via `push_system_alert()` after `alert_rows` was already merged into `filtered_events` (PR#8)

**Self-check:** Trace the lifecycle of alert/event data. If something appends to a list, verify the list hasn't already been consumed.

## 6. `dir()` for Variable Existence
**Pattern:** Using `"varname" in dir()` to check if a variable was defined. This is fragile, hard to grep for, and breaks under refactoring.
**Examples:**
- `gap_counts.to_dict() if "gap_counts" in dir() else []` (PR#9)

**Self-check:** Initialize all variables that might be conditionally assigned. Never use `dir()` as a guard.

## 7. Redundant Conditional Guards
**Pattern:** Wrapping a call in a condition that's already handled by the call itself.
**Examples:**
- `len(df) if not df.empty else 0` — `len()` returns 0 for empty DataFrames (PR#9)

**Self-check:** Check whether the function already handles the edge case before adding a guard.

## 8. Numbering/Ordering Consistency
**Pattern:** Adding new numbered sections out of order in documentation.
**Examples:**
- Section 11 placed before Section 10 in assumptions_audit.md (PR#9)

**Self-check:** When appending to a numbered list, add at the END. Verify sequential order.

## 9. Cross-List Contradictions
**Pattern:** The same value appearing in two lists that have opposing semantics (e.g., noise vs event).
**Examples:**
- `enrolled`, `signed by`, `presented` in both KNOWN_NOISE and ABSOLUTE_FLOOR_VERBS (self-audit catch)

**Self-check:** When creating classification lists, verify no item appears in a contradicting list. Automated: `set(NOISE) & set(EVENTS)` should be empty.

## 10. Editing the Wrong File (Stale Copies)
**Pattern:** Multiple copies of the same file exist (e.g., `xray.py`, `calendar_xray.py`, `pages/ray2.py`). Edits go to the wrong copy and never reach the user.
**Examples:**
- X-Ray upgrades applied to `calendar_xray.py` but Streamlit served `pages/ray2.py` (2026-04-04)

**Self-check:** Before editing, verify which file the runtime actually loads. For Streamlit: check `pages/` directory. For imports: grep for the import statement.

## 11. Substring Match Misses (Verb Tense/Form)
**Pattern:** Using `"word" in text` for classification but the text contains a different form of the word (e.g., "incorporates" vs "incorporated").
**Examples:**
- `"incorporated"` in KNOWN_EVENT didn't match `"incorporates hb912"` — different verb form

**Self-check:** When adding a word to a classification list, also add common conjugations (past/present/plural). Or use stemming.

## 12. O(n) Scan Inside Hot Loop (Pre-calculate Reverse Maps)
**Pattern:** Linear scan of a map to find reverse relationships inside a function called 60k+ times.
**Examples:**
- `[c for c, p in PARENT_COMMITTEE_MAP.items() if p == event_code]` inside `find_api_schedule_match()` (PR#11)
- Same pattern as PR#8 Finding 2 (O(n) reverse lookup of COMMITTEE_CODE_MAP)

**Self-check:** Any dict comprehension/list comprehension inside a function called in a loop must be pre-calculated at init time.

## 13. Cache Blocking Live Data
**Pattern:** Cache loaded first into a dict, then live API guarded by `if key not in dict` — stale cache blocks fresh data.
**Examples:**
- `if "House" not in convene_times[date_str]` prevented live API from overwriting cached convene times (PR#11)

**Self-check:** Live API data should always overwrite cache. Use `if key not in dict` only when cache is the FALLBACK, not the primary.

## 14. Inconsistent Pattern Lists Between Code Paths
**Pattern:** Two code paths doing the same job use different keyword lists.
**Examples:**
- Cache reader missing "house of delegates"/"senate of virginia" that live API reader had (PR#11)

**Self-check:** When adding patterns to one code path, grep for sibling paths doing the same job and sync them.

## 15. Overly-Specific Patterns Miss General Cases
**Pattern:** Classification list has "passed senate" and "passed house" but not bare "passed". When data contains just "Passed (40-Y 0-N)" without the chamber qualifier, it doesn't match.
**Examples:**
- ABSOLUTE_FLOOR_VERBS had "passed senate"/"passed house" but not "passed" — 408 floor actions misclassified
- Fix: use the general form with an explicit exclusion for the false positive ("passed by" = tabling)

**Self-check:** When adding verb+qualifier patterns, ask: "Can this verb appear WITHOUT the qualifier?" If yes, use the general form with guards for false positives.

**UPDATE: Pattern #15 itself was wrong.** Data analysis showed "passed" ALWAYS appears with "House"/"Senate" in Virginia HISTORY.CSV — the original "passed senate"/"passed house" patterns were correct. The real bug was convene time coverage, not verb matching. **Always check the actual data before changing classification lists.**

## 16. Assuming All Legislative Actions Need Times
**Pattern:** Classifying actions as "meeting" (needs a time) when they're really administrative. Not every action in the legislative process happens in a room at a specific time.
**Examples:**
- "Approved by Governor" — governor acts on her own schedule, no chamber session
- "Conferees appointed by House" — leadership designates members, administrative listing
- "Enrolled Bill communicated to Governor" — clerk transmission, paperwork
- "Signed by Speaker" — ceremonial paperwork, not a timed floor event
- "Engrossed by House as amended" — clerk preparing official text, not a timed event

**Self-check:** Before classifying an action as "meeting", ask: "Does this require people to be physically present in a room at a specific time?" If not, it's administrative.
