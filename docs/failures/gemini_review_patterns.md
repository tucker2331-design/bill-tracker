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
