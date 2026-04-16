---
tags: [workflow, rule, anti-pattern]
updated: 2026-04-16
status: active
---

# Source-Miss Visibility Rule

**Every code path that handles a source miss MUST emit a visible, counted signal.** No silent default string. No bare `continue`. No rename that erases provenance. If you can't source it, tag it — don't hide it.

This rule exists because of [[failures/pr22_post_mortem]]: Section 9's bug metric was measuring only the rows the worker was honest enough to leave visible. Rows that got silently renamed, dropped, or defaulted never contributed to the metric, so they looked like "not a bug." The metric was rewarding silencing.

## Concrete checks (run before every push)

Grep the diff for:

| Pattern | Required companion |
|---------|--------------------|
| String-literal fallback: `"Journal Entry"`, `"Ledger Updates"`, `"Time TBA"`, `"TBA"`, `"Unknown"` | A visible tag and/or `push_system_alert(...)` call adjacent |
| Bare `continue` inside a filter/map over worker data | `alert_rows.append(...)` on the same branch, or an incremented counter that gets surfaced |
| `except: pass` / `except SomeError: pass` | Either log + categorize, or an explicit comment documenting why the error is known-benign-high-frequency |
| Rename of a column/field value (e.g. `"Journal Entry"` → `"📋 Ledger Updates"`) | An origin/provenance column that survives the rename so downstream can distinguish cases |

## What a compliant path looks like

```python
time_val = find_concrete_time(...)
if time_val is None:
    time_val = "⏱️ [NO_SCHEDULE_MATCH]"
    push_system_alert(
        f"No schedule match for {bill_num} on {date} — deferring to Ledger",
        category="TIMING_LAG",
        severity="WARN",
    )
    origin = "no_match"
else:
    origin = "scheduled"
master_events.append({..., "Time": time_val, "Origin": origin, ...})
```

Observable downstream:
- X-Ray can filter `Origin == "no_match"` to see the true source-miss rate.
- Bug_Logs shows the categorized alert for each miss.
- The metric has a denominator (`total rows / scheduled / no_match / dropped`).

## Every metric must have a denominator

**"459 bugs" means nothing without "out of how many rows where we knew the source vs didn't."** A metric without a denominator will always reward silencing. See [[testing/crossover_week_baseline]] — future X-Ray sections should publish:
- total rows processed
- rows with confirmed source
- rows without source (by origin)
- rows dropped (by reason)

## Reclassification is not a fix for source-miss

If the instinct is "this row is annoying the metric, let me classify it away," stop. That was PR#22's mistake. The correct instinct is "this row shouldn't be on the calendar without a visible source-miss signal — let me make the miss louder." Classification changes are for phrases whose semantics are wrong, not for phrases whose sources are missing.

## Related

- [[state/open_anti_patterns]] — the live debt tracker for this rule
- [[failures/pr22_post_mortem]] — the framework failure that produced this rule
- [[failures/gemini_review_patterns]] pattern #18 — silent `pass` in exception handlers (pre-existing)
