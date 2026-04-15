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

## 17. Non-Atomic Clear+Write on External Storage
**Pattern:** Using `sheet.clear()` followed by `sheet.update()` to replace data. If the update fails after the clear, data is lost.
**Examples:**
- API_Cache compaction: `cache_sheet.clear()` then `cache_sheet.update(values=compacted)` — if update threw, cache was gone (PR#13)

**Self-check:** Any clear-then-write on external storage needs a rollback path. Either: (1) write new data first, then delete old, or (2) keep original data in memory and restore on failure. Also chunk large writes to stay under API payload limits.

## 18. Silent `pass` in Exception Handlers
**Pattern:** Using `except: pass` or `except SomeError: pass` without logging. The error is swallowed and invisible in logs, making debugging impossible.
**Examples:**
- Date parsing in Session API events used `except (ValueError, TypeError): pass` with no log (PR#13)
- Three bare `except: pass` blocks in session/CSV parsing (PR#13, initial fix)

**Self-check:** Every `except` block must either log or re-raise. `pass` alone is only acceptable for truly expected, high-frequency noise (e.g., expected parse failures on known-bad data) and even then should be documented with a comment explaining why.

## 19. KNOWN_NOISE vs KNOWN_EVENT Misplacement
**Pattern:** Adding administrative milestones to KNOWN_NOISE instead of KNOWN_EVENT. The worker silently deletes noise-only items (`if is_known_noise and not is_known_event: continue`). Milestones like "recommitted", "no further action taken", "budget amendments available" should be preserved in Ledger, not deleted.
**Examples:**
- "recommitted", "unanimous consent to introduce", "no further action taken" placed in KNOWN_NOISE would be silently deleted instead of preserved in Ledger (PR#14)

**Self-check:** KNOWN_NOISE = truly disposable (fiscal statements, reprints, blank actions). KNOWN_EVENT = everything else that should appear in output, even if classified as ADMINISTRATIVE in X-Ray. When in doubt, use KNOWN_EVENT — an extra Ledger row is better than a missing legislative milestone.

## 20. Overly Broad Substring Patterns
**Pattern:** Adding short/common substrings to pattern lists that use `any(p in lower for p in PATTERNS)`. "moved from" matches "removed from the table", "moved from committee to floor", etc.
**Examples:**
- Bare "moved from" added to KNOWN_NOISE — would also match "removed from" (PR#14)
- Bare "substitute" or "amendment" considered but rejected — would catch "substitute printed" (PR#14)

**Self-check:** Before adding any pattern shorter than 10 characters, grep HISTORY.CSV for all lines containing it and verify every match should be classified the same way. Prefer the most specific pattern that covers the intended cases.

## 21. Fallback Logic Skips Non-Concrete Placeholders
**Pattern:** A fallback/override path checks "does an entry exist?" but not "is the existing entry useful?" Non-concrete placeholder values ("Time TBA", "", "TBA") occupy the slot and prevent better data from replacing them.
**Examples:**
- Session marker fallback checked `chamber not in convene_times[date]` — but the entry might contain "Time TBA". A real derived time from adjourned/recessed events should overwrite it (PR#15)

**Self-check:** When guarding a fallback with "already exists", also check whether the existing value is concrete/useful. Use `_is_non_concrete_time()` or equivalent.

## 22. Inconsistent Source Filter Patterns
**Pattern:** One code path uses `Source != "API"` while sibling paths use `.startswith("API")`. The latter catches both "API" and "API_Skeleton" sources, the former misses API_Skeleton.
**Examples:**
- Session marker fallback used `!= "API"` while time promotion (lines 857, 873) used `.startswith("API")` (PR#15)

**Self-check:** Use `.startswith("API")` consistently for all API source checks. Never use `== "API"` or `!= "API"` — it's fragile if new API sub-types are added.

## 23. Helper Functions Defined Inside Conditional/Try Blocks
**Pattern:** A utility function defined inside a `try` or `if` block is only accessible within that scope. Other code paths that need the same logic can't call it.
**Examples:**
- `_is_non_concrete_time()` defined inside Schedule API `try` block (line 851), needed by session marker fallback outside that scope (line 917) (PR#15)

**Self-check:** Pure utility functions (no closures over local variables) must be at module level or at the top of the enclosing function, never inside conditional blocks.

## 24. Using Only First Element of a Multi-Match List
**Pattern:** A list of matches is collected (e.g., `exact_matches`) but downstream logic only reads `[0]`. If the list contains multiple entries with different raw representations that all normalize to the same value, the first element may not be the one needed by subsequent matching logic.
**Examples:**
- Strategy B sub-panel matching used `exact_matches[0].split("_", 1)[1]` as the prefix to check against. If multiple exact matches exist with different raw names (e.g., "House Courts of Justice" vs "House Committee on Courts of Justice"), only the first was tried (PR#16).

**Self-check:** When a collected list could contain multiple entries with different raw representations, iterate all entries rather than indexing `[0]`. Especially when downstream logic depends on string-level properties (prefix, suffix) of the raw representation.

## 25. Greedy Regex Quantifiers on Compound ID Fields
**Pattern:** Using greedy `\d{1,2}` to capture a variable-length component of a compound ID when the next component is also digits. The greedy quantifier consumes digits that belong to the next field, producing wrong captures.
**Examples:**
- `r'^([HS])(\d{1,2})\d{0,3}V\d+'` on `S2001V1234`: greedy `\d{1,2}` captures "20" (parent = S20) instead of "2" (parent = S2). The "0" from the subcommittee suffix `001` gets eaten by the parent group (PR#17).

**Self-check:** When a regex captures a variable-length numeric field followed by another numeric field, use non-greedy quantifiers (`?`) combined with fixed-width groups for the subsequent field. Alternatively, anchor on a known-width component. Always test with the minimum-length variant of each field.

## 26. Override-Only Classification (Bypassing Base List)
**Pattern:** Adding a phrase to `ADMIN_OVERRIDE_PATTERNS` without also adding it to `ADMINISTRATIVE_PATTERNS`. The override layer catches it today, but the base list is the documented source of truth for "what counts as administrative". If the override mechanism is ever refactored or removed, the phrase silently falls back to `unclassified` or worse, back to `meeting`.
**Examples:**
- PR#18 added `"prefiled and ordered printed"` to `ADMIN_OVERRIDE_PATTERNS` only, not to `ADMINISTRATIVE_PATTERNS`. Gemini flagged inconsistency with standard from assumptions_audit #27.

**Self-check:** Every entry in `ADMIN_OVERRIDE_PATTERNS` must also exist in `ADMINISTRATIVE_PATTERNS`. The override is a priority tiebreaker, not a replacement. Base lists are the durable classification record.

## 27. Duplicated Configuration Across Files
**Pattern:** The same config value (date, threshold, constant) hardcoded in multiple files that must stay in sync. "Sync by convention" means it will drift.
**Examples:**
- PR#19 put `INVESTIGATION_START`/`INVESTIGATION_END` in `calendar_worker.py`, `pages/ray2.py`, AND `calendar_xray.py`. Shifting the window requires three edits and any miss silently breaks alignment.

**Self-check:** If a constant must appear in two or more files, promote it to a single module (`investigation_config.py`, `constants.py`) or data file (JSON/YAML) and import. Never duplicate.

## 28. String-Casting a Date Column for Comparison
**Pattern:** Using `df["Date"].astype(str)` to build a string mask against ISO date bounds. Works for clean `YYYY-MM-DD` but silently breaks if pandas loads the column as `datetime64` — `astype(str)` then produces `"2026-02-13 00:00:00"`, which compares lexicographically greater than `"2026-02-13"` and excludes the last day.
**Examples:**
- PR#19 window filter in `pages/ray2.py` / `calendar_xray.py` used `sheet_df["Date"].astype(str)` for the window comparison.

**Self-check:** For date-bounded filters, normalize the column via `pd.to_datetime(col).dt.strftime("%Y-%m-%d")` (or compare as datetime objects directly). Never assume the source dtype is string.
