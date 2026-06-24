---
tags: [ny, testing, validation]
updated: 2026-06-24
status: active
---

# New York Validation Plan

## Local tests

Current fixture checks:

- `test_bill_to_record_flattens_openleg_shape`
- `test_outcome_prefers_structural_signed_boolean`
- `test_outcome_uses_structural_veto_messages_without_status_text`
- `test_unknown_chambers_and_missing_session_are_counted_not_inferred`
- `test_build_ny_bill_records_counts_completeness`

Local commands:

```bash
PYTHONPYCACHEPREFIX=/tmp/bill-tracker-pycache python3 -m py_compile ny_bill_tracker.py test_ny_bill_tracker.py
PYTHONPYCACHEPREFIX=/tmp/bill-tracker-pycache python3 - <<'PY'
import test_ny_bill_tracker as t
for name in dir(t):
    if name.startswith("test_"):
        getattr(t, name)()
        print(f"PASS {name}")
PY
```

`pytest` is not installed in the current local environment as of 2026-06-24.

## Pre-live config check

Run:

```bash
python3 ny_bill_tracker.py --check-config
```

Expected before owner secrets are set:

- `NY_OPENLEG_API_KEY` missing
- `NY_SPREADSHEET_ID` missing for writes

GitHub Actions equivalent: run `New York Bill Tracker` with mode
`check-config`. The workflow is manual-only by design and installs from pinned
`requirements-ny.txt`.

## First live dry run

Needs `NY_OPENLEG_API_KEY`.

```bash
NY_OPENLEG_API_KEY=... NY_OPENLEG_SESSION_YEAR=2025 python3 ny_bill_tracker.py --dry-run
```

Record in this page and [[ny/log]]:

| Metric | Result |
|---|---|
| GitHub Actions run | `28136128891` |
| checked_at_utc | `2026-06-24T23:25:17Z` |
| records_written | 25,314 |
| bills_seen | 25,314 |
| has_actions_rate | 1.0 |
| has_votes_rate | 0.1746 |
| patron_present / patron_missing | 25,268 / 46 |
| summary_present | 21,325 (`summary_present_rate`: 0.8424) |
| outcome_sources | `signed_boolean`: 847; `veto_messages`: 141; `unresolved_structural`: 24,326 |
| unknown_structural_outcome_rate | 0.961 |
| unknown_chamber_value | 0 |
| missing_action_text | 0 |
| source_url_missing_session | 0 |
| health.status | WARN |
| health.findings | `UNKNOWN_STRUCTURAL_OUTCOME`: 24,326 / 25,314 |
| elapsed time | 1m 56s |

Result: full-session dry run passed in GitHub Actions without malformed bill IDs,
unknown chamber values, missing action text, or missing source URLs. The only
health warning is the expected source-contract item for unresolved structural
outcomes on non-terminal/active bills.

Interpretation rule: `unknown_structural_outcome_rate` is allowed during this
first source-contract pass, but it is never silently converted to `in_progress`
from status text. A non-zero value means the next scoping pass must find a
durable OpenLeg structural field, accept an explicit unresolved product state,
or document why terminal-outcome parity is not available yet.

## First live write

Needs `NY_OPENLEG_API_KEY`, `NY_SPREADSHEET_ID`, and owner confirmation of the
target workbook.

```bash
NY_OPENLEG_API_KEY=... NY_SPREADSHEET_ID=... NY_OPENLEG_SESSION_YEAR=2025 python3 ny_bill_tracker.py
```

Pass criteria:

| Criterion | Result |
|---|---|
| GitHub Actions run | `28136320411` |
| mode / session | `write` / `2025` |
| elapsed time | 2m 25s |
| target tab | `NY_Bill_Tracker` |
| bills built | 25,314 |
| bills with sponsor | 25,268 |
| bills with action history | 25,314 |
| workflow status | passed |

Result: first live write passed in GitHub Actions. The workflow used the
explicit New York sheet configuration and completed the full 2025 OpenLeg bill
session write. The write-mode log confirms the tab build summary, while the
preceding full dry run is the canonical source for detailed health counters and
completeness JSON contents.

Pass criteria status:

- Creates or overwrites only `NY_Bill_Tracker` or the explicitly configured `NY_BILL_TRACKER_TAB`: passed by workflow configuration and successful NY write.
- `R1` contains completeness JSON: expected by writer contract; not independently read back from Google Sheets in this validation pass.
- Row count equals `records_written + 1` header row: expected 25,315 rows including header; not independently read back from Google Sheets in this validation pass.
- No Virginia tabs are touched: passed by separate `NY_SPREADSHEET_ID` and NY-only workflow invocation.

Post-write owner spot check: open the New York workbook, confirm the
`NY_Bill_Tracker` tab exists, confirm approximately 25,315 rows including the
header, and confirm `R1` contains completeness JSON.

## Scheduling gate

Do not add a scheduled workflow until:

- full dry run passes
- first write passes
- owner confirms post-write sheet spot check
- OpenLeg cadence/rate expectations are documented

The workflow `.github/workflows/ny_bill_tracker.yml` exists only as a manual
`check-config` / `dry-run` / `write` runner. No cron is allowed until the above
gates are complete.
