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
| records_written | TBD |
| bills_seen | TBD |
| has_actions_rate | TBD |
| has_votes_rate | TBD |
| patron_present / patron_missing | TBD |
| summary_present | TBD |
| outcome_sources | TBD |
| unknown_structural_outcome_rate | TBD |
| unknown_chamber_value | TBD |
| source_url_missing_session | TBD |
| health.status | TBD |
| health.findings | TBD |
| elapsed time | TBD |

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

- Creates or overwrites only `NY_Bill_Tracker` or the explicitly configured `NY_BILL_TRACKER_TAB`.
- `R1` contains completeness JSON.
- Row count equals `records_written + 1` header row.
- No Virginia tabs are touched.

## Scheduling gate

Do not add a scheduled workflow until:

- full dry run passes
- first write passes
- owner chooses workbook strategy
- OpenLeg cadence/rate expectations are documented

The workflow `.github/workflows/ny_bill_tracker.yml` exists only as a manual
`check-config` / `dry-run` / `write` runner. No cron is allowed until the above
gates are complete.
