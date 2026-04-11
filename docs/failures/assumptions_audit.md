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

### 10. Cache write alert lost (pushed after Sheet1 write)
- **What broke:** `push_system_alert()` appended to `alert_rows`, but `alert_rows` was already extended into `filtered_events` before the cache write. Any cache failure alert was never written to Sheet1.
- **How it was caught:** Gemini PR review, execution order analysis
- **Fix:** Cache write moved before Sheet1 write. Failure alert injected directly into `final_df` via `pd.concat`.

### 11. Floor actions classified as KNOWN_NOISE (self-audit catch)
- **What broke:** `enrolled`, `signed by`, `presented`, `communicated to governor` were in KNOWN_NOISE_PATTERNS. These are real legislative milestones (also in ABSOLUTE_FLOOR_VERBS) that should appear on the calendar. The positive-ID noise filter was silently eating them because they matched KNOWN_NOISE but not KNOWN_EVENT.
- **How it was caught:** Pre-push audit comparing KNOWN_NOISE against ABSOLUTE_FLOOR_VERBS
- **Fix:** Moved all ABSOLUTE_FLOOR_VERBS entries into KNOWN_EVENT_PATTERNS. Added `enrolled`, `signed by`, `presented`, `communicated`, `received`, `engrossed` to KNOWN_EVENT.

## Bugs Caught by PR Review (Gemini PR#9)

### 12. Redundant tag count recalculation in X-Ray
- **What broke:** Section 5 recalculated `str.contains().sum()` for every tag when `tag_counts` was already computed in Section 3.
- **How it was caught:** Gemini PR review
- **Fix:** Iterate over pre-calculated `tag_counts` dict, only compute `str.contains()` mask for the row sample display.

### 13. `dir()` used to check variable existence
- **What broke:** `gap_counts` and `issues` were only defined inside conditional blocks. Download payload used `"gap_counts" in dir()` as a guard — fragile and hard to reason about.
- **How it was caught:** Gemini PR review
- **Fix:** Initialize `gap_counts` and `issues` as empty DataFrames before the conditional blocks.

### 14. Redundant `.empty` check on DataFrame length
- **What broke:** `int(len(missing_df)) if not missing_df.empty else 0` — `len()` already returns 0 for empty DataFrames.
- **How it was caught:** Gemini PR review
- **Fix:** Simplified to `int(len(missing_df))`.

## Bugs Caught by Self-Audit (2026-04-04)

### 15. X-Ray Streamlit serving stale file (pages/ray2.py)
- **What broke:** All X-Ray upgrades went to `calendar_xray.py` at repo root, but Streamlit serves from `pages/ray2.py` (auto-discovered by Streamlit's pages/ directory convention). User saw build "2026-04-03.3" despite code being at "2026-04-04.1".
- **How it was caught:** User reported X-Ray not updating after PR merge
- **Fix:** Synced `pages/ray2.py` with `calendar_xray.py` content. Both files now at build "2026-04-05.2". Going forward, `pages/ray2.py` is the authoritative Streamlit page.

### 16. UNKNOWN_ACTION patterns not classified
- **What broke:** "rules suspended", "offered" (amendment actions), and "incorporates" were not in KNOWN_EVENT_PATTERNS. These are real legislative actions being flagged as ❓ UNKNOWN_ACTION.
- **How it was caught:** X-Ray data analysis showing recurring UNKNOWN_ACTION tags
- **Fix:** Added "rules suspended", "offered", "incorporates" to KNOWN_EVENT_PATTERNS. Note: "incorporated" was already there but doesn't substring-match "incorporates".

### 17. "0 missing" gold metric was misleading — only measured matched committees
- **What broke:** X-Ray Section 7 reported "0 rows missing time that LIS has" but this metric ONLY counted rows where the committee name matched between Sheet1 and LIS Schedule. The 4,228 `no_lis_committee_match` rows — including Ledger Updates, Floor actions, and potentially real committee actions — were excluded entirely from the metric. We were celebrating 100% accuracy on a subset while ignoring a massive unexamined population.
- **How it was caught:** User pushed back asking "how close are we really?" during data review
- **Fix:** Added X-Ray Section 9 "Action Classification Audit" which classifies EVERY row as meeting action or administrative based on the Outcome text. The true accuracy metric is: **meeting actions without times = bugs**. Also added Ledger Health Check to find meeting actions buried in Ledger Updates (votes/reports that fell through to Journal Entry because calendar_worker couldn't match them to a schedule entry). This is the real bug count.
- **Lesson:** Never trust a metric that excludes the hard cases. The denominator matters as much as the numerator.

### 18. Convene time capture too narrow — only "House Convenes" / "House Chamber"
- **What broke:** LIS Schedule API may list floor sessions under names like "House Session", "House Floor Period", or "House of Delegates" — not just "House Convenes". The convene_times dict only populated on exact matches for "house convenes" and "house chamber", missing alternative names. Similarly, the cache reader only matched "Convenes" (capital C substring).
- **How it was caught:** X-Ray Section 9 showed 408 "passed" + 169 "agreed to" + 149 "read first" actions buried in Ledger — all floor actions that should have had convene times.
- **Fix:** Expanded both live API and cache readers to match broader floor session patterns: "house session", "house floor", "house of delegates", "senate session", "senate floor", "senate of virginia". Added "first match wins" guard so canonical names aren't overwritten by fallback matches.
- **Runtime check:** Convene time gap diagnostic now logs hit/miss counts and missing date/chamber combos after each run.

### 19. Parent-to-child schedule lookup missing — only child-to-parent existed
- **What broke:** `find_api_schedule_match()` had child→parent fallback (subcommittee inherits parent time) but NOT parent→child. When a parent committee like "House Appropriations" had "Time TBA" in the Schedule API but its subcommittees had concrete times, the parent's actions got TBA instead of inheriting a child time.
- **How it was caught:** X-Ray showed 147 House Appropriations meeting actions without times despite subcommittees having concrete times on the same dates.
- **Fix:** Added Direction 2 lookup: when exact match exists but has non-concrete time, search PARENT_COMMITTEE_MAP for child committees and check if any have concrete times for the same date.

### 20. 3,150 unclassified actions — missing pattern coverage
- **What broke:** X-Ray action classification didn't recognize: "Governor's Action Deadline" (1,145), "Scheduled" (454), "Left in [committee]" (231), "requested conference committee" (167), "acceded to request" (84), "Blank Action" (29).
- **How it was caught:** X-Ray Section 9 unclassified warning.
- **Fix:** Added all patterns to appropriate lists. "Governor's Action Deadline", "Scheduled", "Left in", "Blank Action" → ADMINISTRATIVE. "Requested conference committee", "acceded to request" → MEETING. Also added to calendar_worker.py KNOWN_EVENT/KNOWN_NOISE accordingly.

### 21. REVERTED — "passed" is NOT missing from floor verbs
- **Original assumption:** Bare "passed" needed to be added to ABSOLUTE_FLOOR_VERBS because 408 Ledger bugs showed "passed" as #1 meeting action.
- **Data disproved it:** HISTORY.CSV analysis shows "passed" ALWAYS appears as "Passed House" or "Passed Senate" — never bare. "passed house" and "passed senate" already match. The 408 bugs are floor actions that matched correctly but missed convene times.
- **Lesson:** Check the actual data before changing classification lists. The bug was convene time coverage, not verb matching.

### 22. REVERTED — Executive/Conference are NOT chamber-time actions
- **Original assumption:** Governor approval and conferee actions needed chamber session times.
- **Data disproved it:** "Approved by Governor-Chapter 7 (effective...)" has a DATE but no time — governor acts on her own schedule. "Conferees appointed by House" is an administrative listing. Conference MEETINGS happen separately from chamber sessions.
- **Lesson:** "Happened in the legislative process" ≠ "happened during a chamber session at a specific time."
- **Correct fix:** Reclassified governor actions, conferee appointments as ADMINISTRATIVE in X-Ray. Only "conference report agreed" (floor vote) stays as MEETING. Removed "signed by", "enrolled", "communicated", "presented", "received", "engrossed" from ABSOLUTE_FLOOR_VERBS — these are clerk/paperwork actions.

### 23. Schedule API has 545 entries (16.5%) with empty ScheduleTime
- **What broke:** 545 of 3,310 Schedule API entries have no time. House Courts of Justice has ZERO times across all 98 entries. Earlier validation checked entry existence ("3,310 entries confirmed 1:1"), not time completeness.
- **How it was caught:** Direct analysis of Schedule API response data.
- **Status:** Not code-fixable. These committees genuinely don't publish times to the Schedule API. May need alternative time sources (Description HTML, committee agenda pages). Deferred pending code-fixable bug resolution.

### 24. Administrative actions misclassified as meeting actions inflated bug count
- **What broke:** ABSOLUTE_FLOOR_VERBS contained "signed by" (24), "enrolled" (33), "engrossed" (54), "communicated" (16), "presented" (0), "received" (0), "conferees:" — these are clerk/paperwork actions that do NOT require people in a room at a specific time. Forcing them to "Floor" → missing convene time → Journal Entry → Ledger → counted as bugs. Similarly, X-Ray MEETING_ACTION_PATTERNS included governor actions and conferee appointments.
- **How it was caught:** User challenged whether these were truly floor actions. Gemini caught "engrossed" inconsistency (admin in X-Ray but floor in worker). HISTORY.CSV data analysis confirmed all are clerk actions.
- **Fix:** Removed admin actions from ABSOLUTE_FLOOR_VERBS. Reclassified in X-Ray: governor actions → ADMINISTRATIVE, conferee appointments → ADMINISTRATIVE. Only "conference report agreed" (floor vote) stays as MEETING. Reordered priority: absolute_floor checked BEFORE conference.
- **Impact:** Reduces X-Ray bug count by reclassifying ~170+ phantom bugs as correctly-untimed administrative actions.

### 25. API_Cache hit Google Sheets 10M cell limit — cache writes silently failing
- **What broke:** API_Cache sheet accumulated rows across many runs (3,310 Schedule entries × 5 columns per run). Despite dedup logic preventing exact duplicates, the sheet grew past Google Sheets' 10,000,000 cell limit. All subsequent `append_rows` calls failed with `APIError: [400]`, meaning schedule data was no longer being cached for offline fallback.
- **How it was caught:** Worker log analysis showed CRITICAL alert: "Failed to update API_Cache: APIError: [400]: This action would increase the number of cells in the workbook above the limit of 10000000 cells."
- **Fix:** Added cache compaction: when `append_rows` fails due to cell limit, merge all existing + new entries into a deduplicated dict (keyed by Date+Committee), clear the sheet, and write the compacted data. New data overwrites stale entries.
- **Lesson:** Any append-only cache in Google Sheets needs a compaction strategy. The cell limit is 10M across ALL sheets in the workbook.

### 26. Bare `except: pass` blocks hid failures in Session API, CSV fetch, and date parsing
- **What broke:** Three bare `except: pass` blocks silently swallowed all exceptions: Session API parsing (line 484), CSV fetch (line 496), and date parsing in session events (line 470). Any failure in these paths produced no log output, making debugging impossible.
- **How it was caught:** Code audit against zero-trust data standards.
- **Fix:** Replaced with specific exception types (`ValueError`, `TypeError`) for date parsing and `Exception` with `print()` logging for Session API and CSV fetch.

### 27. 574 unclassified actions — missing pattern coverage (session 261 data analysis)
- **What broke:** HISTORY.CSV data analysis showed 574 out of 61,841 actions didn't match any KNOWN_EVENT or KNOWN_NOISE pattern. These were flagged as ❓ UNKNOWN_ACTION in the worker and counted as "unclassified" in X-Ray Section 9. Key missing patterns: "insisted" (126), "taken up" (144), "moved from uncontested calendar" (137), "reading waived" (17+), "withdrawn" (various, ~17), "budget amendments" (12), "elected/election by" (7), "concurred" (8), "emergency clause" (3), "recommitted" (3).
- **How it was caught:** X-Ray Section 9 showing 749 unclassified actions. Direct HISTORY.CSV analysis confirmed 574 in raw data (difference due to diagnostic tag prepending in Sheet1).
- **Fix:** Added 19 new MEETING patterns and 6 new ADMINISTRATIVE patterns to both worker (KNOWN_EVENT/KNOWN_NOISE) and X-Ray (MEETING_ACTION/ADMINISTRATIVE). Remaining ~25 unclassified are data fragments ("S", "Floor") and "[Committee Name] Substitute/Amendment" entries that can't be caught without false positives.
