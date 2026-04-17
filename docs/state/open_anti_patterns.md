---
tags: [state, live, debt, anti-pattern]
updated: 2026-04-16
status: active
---

# Open Anti-Patterns in Code

Live debt tracker for the "silent source-miss" anti-pattern surfaced in [[failures/pr22_post_mortem]]. Each entry is code that swallows a missing source signal into an invisible default. The governing rule is [[workflow/source_miss_visibility]].

This page is the counterpart to [[failures/gemini_review_patterns]] but for debt that is known-live-in-code, not just caught-in-review.

**Severity labels** use CLAUDE.md Standard #4 (`INFO` / `WARN` / `CRITICAL`):
- `CRITICAL` — data integrity at risk (silent data loss, a metric that is structurally wrong).
- `WARN` — unexpected but non-breaking (provenance loss, alert not routed to the right place).
- `INFO` — expected edge case.

---

## 1. `calendar_worker.py` ~line 1181 — silent `"Journal Entry"` default

**Status:** resolved-in-PR#25 (branch `claude/worker-source-miss-visibility`). Tag + alert + Origin column landed.

**Severity:** `CRITICAL` — data integrity at risk; root disease of the Section 9 metric illusion.

```python
time_val = "Journal Entry"
sort_time_24h = "23:59"
matched_api_key = find_api_schedule_match(...)
if matched_api_key:
    time_val = api_schedule_map[matched_api_key]["Time"]
# else: row silently keeps "Journal Entry"
```

**Problem:** When the Schedule API lookup misses, the row's time silently becomes `"Journal Entry"`. No tag, no alert, no provenance column. Later (~line 1269) the string gets renamed to `"📋 Ledger Updates"`, making source-miss rows indistinguishable from real admin entries. Every Section 9 bug flows through this path.

**Fix plan:** Replace with visible `"⏱️ [NO_SCHEDULE_MATCH]"` tag + `Bug_Logs` row (`TIMING_LAG`, severity `WARN`). Preserve provenance via an origin column.

**Blocked on:** User approval for the worker-instrumentation PR (see [[state/current_status#Next PR (proposed, not yet approved)|Next PR]]).

---

## 2. `calendar_worker.py` ~lines 1248-1261 — ephemeral filter silent drop

**Status:** resolved-in-PR#25. Counter + deduped `push_system_alert` added on the drop branch; `dropped_ephemeral` now surfaces in X-Ray Section 0.

**Severity:** `CRITICAL` — silent row loss on source miss.

```python
for ev in master_events:
    if bool(ephemeral_pattern.search(ev["Outcome"])) and ev["Time"] == "Journal Entry":
        ...
        if not was_scheduled:
            continue  # silently drops row
```

**Problem:** Rows with ephemeral language and no Schedule API match get `continue`-dropped with no counter, no log, no categorized alert. Pure data loss on source miss.

**Fix plan:** Replace `continue` with `alert_rows.append({...})` + increment a `dropped_ephemeral` counter displayed in X-Ray Section 0.

---

## 3. `calendar_worker.py` ~lines 1158-1167 — selective Memory Anchor tag

**Status:** resolved-in-PR#25. Admin-verb path now emits `📝 [Memory Anchor: admin]`; dynamic-verb path keeps `⚙️ [Memory Anchor]`. Both increment `unsourced_anchor`.

**Severity:** `WARN` — provenance loss on admin-verb Memory Anchor fallbacks.

```python
else:
    # Dynamic Nameless (Memory Anchor)
    event_location = bill_locations[bill_num]
    is_dynamic_verb = any(v in outcome_lower for v in DYNAMIC_VERBS)
    if is_dynamic_verb and "Floor" not in event_location:
        outcome_text = f"⚙️ [Memory Anchor] " + outcome_text
```

**Problem:** Memory Anchor fallback is only tagged when the action is a dynamic verb. For admin verbs resolved via Memory Anchor, the row silently inherits `bill_locations[bill_num]` with no tag. Can't distinguish Memory-Anchor-derived rows from structurally-resolved rows downstream.

**Fix plan:** Tag every Memory-Anchor-derived row regardless of verb class (different tag variants if needed: `[Memory Anchor — dynamic]` vs `[Memory Anchor — admin]`).

---

## 4. `calendar_worker.py` ~lines 1269-1275 — Journal → Ledger rename erases provenance

**Status:** resolved-in-PR#25. `Origin` column added to every `master_events` append; Ledger-Updates collapse now gates off `Origin.isin(['journal_default', 'floor_miss'])` instead of the renamed Time string, so provenance survives the rename.

**Severity:** `WARN` — provenance loss; enabler for #1's invisibility (borderline `CRITICAL` because without it #1 would already be surfaced).

```python
journal_mask = final_df['Time'] == 'Journal Entry'
if journal_mask.any():
    final_df.loc[journal_mask, 'Committee'] = '📋 Ledger Updates'
```

**Problem:** Traceability lost at this rename. Downstream X-Ray cannot distinguish "we couldn't time this meeting action" from "this is a legitimate admin entry." Both look identical.

**Fix plan:** Add an `Origin` column (values: `scheduled`, `no_match`, `ephemeral_drop`, `memory_anchor`, `admin_intended`) that survives the rename. X-Ray Section 9 filters on `Origin == "no_match"` instead of fuzzy text matching.

---

## 5. `calendar_worker.py` ~line 756 — `except Exception as e: print(...)` cache fallback

**Status:** resolved-in-PR#25. `print` retained for logs; categorized `push_system_alert(..., category="API_FAILURE", severity="WARN", dedup_key="cache_read_failure")` added alongside.

**Severity:** `WARN` — alert not routed to Bug_Logs (still visible in stdout, so not silent, but not categorized either). Same family as #1-4.

**Problem:** `print()` is not a categorized alert. If the cache sheet read fails in GitHub Actions, the failure appears only in stdout, not in `Bug_Logs`. Violates CLAUDE.md Standard #4 (self-describing errors).

**Fix plan:** Replace `print` with `push_system_alert(..., category="API_FAILURE", severity="WARN")`.

---

## 6. `calendar_worker.py` viewport slice silently dropped `SYSTEM_METRICS` row

**Status:** resolved-in-PR-B (branch `claude/pr-b-metrics-visibility-diagnostic`).

**Severity:** `CRITICAL` — the entire denominator was invisible in production despite the counters running correctly.

```python
# BEFORE PR-B
scrape_start_str = scrape_start.strftime('%Y-%m-%d')
scrape_end_str = scrape_end.strftime('%Y-%m-%d')
final_df = final_df[(final_df['Date'] >= scrape_start_str) & (final_df['Date'] <= scrape_end_str)]
```

**Problem:** PR-A stamped the `SYSTEM_METRICS` row with `Date=today` so it'd land in Sheet1 on every run. The viewport slice then filtered to the investigation window (Feb 9-13, 2026). The metrics row's date (2026-04-16) fell outside the window and was silently dropped before Sheet1 was written. X-Ray Section 0 rendered blank even though upstream instrumentation was correct. Classic "meta rows are not business rows" injection bug.

**Fix (PR-B):** Exempt `Origin in {system_alert, system_metrics}` from the window mask: `final_df = final_df[in_window | is_system]`. Also logged as [[failures/gemini_review_patterns]] #36.

---

## 7. Source-miss rows carried no diagnostic trail

**Status:** resolved-in-PR-B.

**Severity:** `WARN` — triage friction, not data loss.

**Problem:** PR-A tagged NO_SCHEDULE_MATCH rows visibly but stored nothing about what the matcher was looking for or what LIS *did* schedule that day. Every investigation of the 9 in-window bugs would have started with "add a print and re-run the worker."

**Fix (PR-B):** New column `DiagnosticHint` populated only on `journal_default` / `floor_miss` rows with `loc='<bill_locations[bill]>'; api_<date>=[<committee>@<time>; ...]` (nearest-3 same-chamber candidates). X-Ray Sections 4d, 9 sample rows, and the Ledger Health Check expander surface the column. Also logged as [[failures/gemini_review_patterns]] #37.

---

## How this page is kept current

- Every new silent-fallback discovered: add here with location + fix plan + severity.
- Every remediation PR that lands: **do not delete the entry** — mark it `status: resolved-in-<PR#>` and keep for history. This page's value is partly the ledger of debt paid down.
- Link every entry to: the commit that introduced it (if known), the commit that fixes it (when landed), and the [[log]] entry for the fix PR.
