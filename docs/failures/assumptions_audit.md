# Assumptions Audit Log

## Fixed Assumptions

### 1. Committee Code Map was Static (Fixed: dynamic from API)
- **What it assumed:** The 25 committee codes (H01-H24, S01-S13) never change
- **How it broke:** New committees could be created, existing ones renamed or merged between sessions
- **Fix:** Rebuilt from Committee API at runtime with static fallback + drift alerting

### 2. LOCAL_LEXICON was Hardcoded (Fixed: derived from API)
- **What it assumed:** Committee name aliases are stable across sessions
- **How it broke:** Committee names change (e.g., "Courts of Justice" was H02 in old map, is actually H08)
- **Fix:** Auto-generated from Committee API names, splitting on commas/ands

### 3. Parent Fallback Used startswith Heuristic (Fixed: ParentCommitteeID)
- **What it assumed:** Subcommittee names always start with parent committee name
- **How it broke:** Could match unrelated committees with similar name prefixes
- **Fix:** Validate against ParentCommitteeID from Committee API response

## Remaining Assumptions (Documented, Monitored)

### 4. ACTIVE_SESSION Offline Fallback = "261"
- **What it assumes:** If Session API is down, session 261 is current
- **How it breaks:** Next session will have a different code
- **Runtime check:** System alert pushed when offline mode activates
- **When to fix:** Before next session starts (Jan 2027)

### 5. scrape_start = Feb 9 (Test Value)
- **What it assumes:** We only care about crossover week forward
- **How it breaks:** Missing earlier session data
- **Runtime check:** N/A — intentional test constraint
- **When to fix:** After calendar reaches 100% accuracy, set to session start date

### 6. Noise Words Negative Filter (Fixed: positive identification)
- **What it assumed:** We know ALL noise patterns in advance
- **How it broke:** New administrative action types would pass through as events
- **Fix:** KNOWN_NOISE + KNOWN_EVENT positive classification, UNKNOWN flagged with ❓

## Bugs Caught by PR Review (Gemini PR#8)

### 7. cache_records NameError on API_Cache failure
- **What broke:** If `cache_sheet.get_all_records()` threw an exception, `cache_records` was never defined. Later code iterating `cache_records` would crash with NameError.
- **How it was caught:** Gemini PR review, static analysis
- **Fix:** Initialize `cache_records = []` before the try block

### 8. O(n) reverse lookups inside 60k-row loop
- **What broke:** `find_api_schedule_match()` and mismatch detection both did linear scans of COMMITTEE_CODE_MAP with `normalize_room_key()` per row — millions of redundant string ops.
- **How it was caught:** Gemini PR review, performance analysis
- **Fix:** Pre-calculated `NORM_TO_CODE` dict (normalized_name -> code) built once after `build_committee_maps()`. O(1) lookups replace O(n) scans.

### 9. Pattern lists allocated inside 60k-row loop
- **What broke:** `KNOWN_NOISE_PATTERNS` and `KNOWN_EVENT_PATTERNS` were defined as list literals inside the loop body, causing 60k unnecessary allocations.
- **How it was caught:** Gemini PR review
- **Fix:** Moved to module-level constants

### 11. Floor actions classified as KNOWN_NOISE (self-audit catch)
- **What broke:** `enrolled`, `signed by`, `presented`, `communicated to governor` were in KNOWN_NOISE_PATTERNS. These are real legislative milestones (also in ABSOLUTE_FLOOR_VERBS) that should appear on the calendar. The positive-ID noise filter was silently eating them because they matched KNOWN_NOISE but not KNOWN_EVENT.
- **How it was caught:** Pre-push audit comparing KNOWN_NOISE against ABSOLUTE_FLOOR_VERBS
- **Fix:** Moved all ABSOLUTE_FLOOR_VERBS entries into KNOWN_EVENT_PATTERNS. Added `enrolled`, `signed by`, `presented`, `communicated`, `received`, `engrossed` to KNOWN_EVENT.

### 10. Cache write alert lost (pushed after Sheet1 write)
- **What broke:** `push_system_alert()` appended to `alert_rows`, but `alert_rows` was already extended into `filtered_events` before the cache write. Any cache failure alert was never written to Sheet1.
- **How it was caught:** Gemini PR review, execution order analysis
- **Fix:** Cache write moved before Sheet1 write. Failure alert injected directly into `final_df` via `pd.concat`.
