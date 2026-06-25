---
tags: [ny, testing, validation]
updated: 2026-06-25
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
- `test_health_status_uses_standard_info_token_when_clean`
- `test_sheet_readback_verifies_payload_and_completeness`
- `test_sheet_readback_rejects_stale_tail_cells`
- `test_sheet_readback_rejects_completeness_mismatch`
- `test_sheet_readback_rejects_non_object_completeness_json`
- `test_parse_sources_rejects_unknown_source_names`
- `test_env_int_reports_invalid_detail_limit_cleanly`
- `test_clean_label_preserves_falsy_source_values`
- `test_result_items_ignores_malformed_result_payload`
- `test_parse_openleg_meetings_builds_canonical_senate_rows`
- `test_parse_openleg_meetings_counts_missing_time_explicitly`
- `test_parse_assembly_agenda_index_uses_structural_detail_links`
- `test_parse_assembly_agenda_detail_preserves_relative_time_label`
- `test_parse_assembly_floor_index_and_detail_mark_timeless_rows`
- `test_probe_report_keeps_time_denominator_balanced`
- `test_probe_report_flags_unknown_time_bucket_drift`
- `test_probe_report_flags_per_source_gap_not_no_events`
- `test_probe_report_flags_empty_probe_as_source_gap_not_no_events`
- `test_record_source_error_logs_context`
- `test_run_probe_samples_assembly_detail_pages_without_writes`

Local commands:

```bash
PYTHONPYCACHEPREFIX=/tmp/bill-tracker-pycache python3 -m py_compile ny_bill_tracker.py test_ny_bill_tracker.py
PYTHONPYCACHEPREFIX=/tmp/bill-tracker-pycache python3 -m py_compile ny_calendar_probe.py test_ny_calendar_probe.py
PYTHONPYCACHEPREFIX=/tmp/bill-tracker-pycache python3 - <<'PY'
import test_ny_bill_tracker as t
for name in dir(t):
    if name.startswith("test_"):
        getattr(t, name)()
        print(f"PASS {name}")
PY
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import test_ny_calendar_probe as t
for name in dir(t):
    if name.startswith("test_"):
        getattr(t, name)()
        print(f"PASS {name}")
PY
```

`pytest` is not installed in the current local environment as of 2026-06-24.

## Calendar source probe

The first NY calendar implementation is a read-only source probe:
`ny_calendar_probe.py`.

It must not write Google Sheets and must not populate `Upcoming JSON`. Its job
is to prove or reject source shapes before calendar promotion:

- OpenLeg Senate agenda meeting JSON via
  `/api/3/agendas/meetings/{fromDateTime}/{toDateTime}`
- official Assembly committee agenda index/detail links
- official Assembly floor calendar index/detail links
- explicit time buckets: `exact_clock`, `relative_time`, `no_clock_source`,
  `terminal_or_timeless`, and `source_gap`
- visible health findings for empty probes and denominator drift

Local validation on 2026-06-25:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m py_compile ny_calendar_probe.py test_ny_calendar_probe.py
PYTHONDONTWRITEBYTECODE=1 python3 -c "import test_ny_calendar_probe as t; [getattr(t, name)() for name in sorted(dir(t)) if name.startswith('test_')]; print('test_ny_calendar_probe direct tests passed')"
PYTHONDONTWRITEBYTECODE=1 python3 ny_calendar_probe.py --check-config --sources assembly
```

Result: passed. Local `pytest` is still unavailable, so calendar tests were run
by direct function invocation.

Live Assembly validation on 2026-06-25:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 ny_calendar_probe.py --sources assembly --detail-limit 3
```

| Metric | Result |
|---|---|
| checked_at_utc | `2026-06-25T15:00:12Z` |
| status | `INFO` |
| production_write | `false` |
| total rows | 365 |
| sources audited | 4 |
| sources_with_errors | 0 |
| health_findings | none |
| assembly_agenda_index rows | 17 |
| assembly_floor_index rows | 5 |
| assembly_agenda_detail_sample rows | 154 |
| assembly_floor_detail_sample rows | 189 |
| exact_clock | 0 |
| relative_time | 154 |
| no_clock_source | 17 |
| terminal_or_timeless | 194 |
| source_gap | 0 |
| unknown_time_bucket | 0 |
| time_bucket_denominator_drift | 0 |

Interpretation: the official Assembly agenda/floor pages expose durable
structural links for agenda and floor-calendar rows. The sample detail pass
found agenda bill links with explicit `OFF_THE_FLOOR` relative timing and floor
calendar bill links that are structurally release-only, not clocked events.
This proves enough source shape for a later calendar worker design, but it does
not yet promote rows into `Upcoming JSON`.

Live OpenLeg agenda validation still needed:

```bash
NY_OPENLEG_API_KEY=... python3 ny_calendar_probe.py --from-date 2026-01-01 --to-date 2026-02-01
```

The OpenLeg live report should be recorded here and in [[ny/log]] before any
Senate calendar worker or non-empty `Upcoming JSON` values are built.

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

Owner spot check cleared on 2026-06-24: the `NY_Bill_Tracker` tab loaded and the
expected data was present.

## Automated read-back verification

Purpose: verify the actual Google Sheet artifact produced by write mode.

The writer must fail the workflow after a write if any of these read-back checks
fail:

- row 1, columns A:P match the expected product header
- `R1` is parseable JSON and matches the just-built completeness object for
  state, source, session year, records written, bills seen, checked-at timestamp,
  and health status
- column A from row 2 through the active payload matches the bill IDs just built
- the bounded tail range immediately below the active payload has no stale cells

This check is intentionally after-write. It is not a substitute for the source
health counters; it confirms that the production artifact in Google Sheets
matches the run that just completed.

Branch validation:

| Metric | Result |
|---|---|
| PR | `#169` |
| GitHub Actions run | `28137572349` |
| commit | `bc9b691` |
| mode / session | `write` / `2025` |
| elapsed time | 2m 38s |
| bills built | 25,314 |
| rows verified | 25,315 |
| bills verified | 25,314 |
| tail verified through row | 25,365 |
| health status | WARN |
| workflow status | passed |

Earlier branch validation on commit `61636dc` also passed in run `28137147423`.
Run `28137572349` is the post-bot-fold-in live validation.

Post-merge validation:

| Metric | Result |
|---|---|
| GitHub Actions run | `28137876638` |
| commit | `5cfd215` |
| branch | `main` |
| mode / session | `write` / `2025` |
| elapsed time | 2m 33s |
| bills built | 25,314 |
| rows verified | 25,315 |
| bills verified | 25,314 |
| tail verified through row | 25,365 |
| health status | WARN |
| workflow status | passed |

## Scheduling gate

The schedule gate passed on 2026-06-24 after:

- full dry run passes
- first write passes
- owner confirms post-write sheet spot check
- automated read-back verification passes on GitHub Actions
- owner approves a once-daily cadence while the frontend is not yet live

Daily cadence:

| Field | Value |
|---|---|
| Workflow | `.github/workflows/ny_bill_tracker.yml` |
| Cron | `40 17 * * *` |
| Mode | scheduled `write` |
| Session default | `2025` |
| Manual modes retained | `check-config`, `dry-run`, `write` |
| Production write ref | `refs/heads/main` only |
| Production concurrency | scheduled and manual writes serialize; branch probes do not block writes |
| Merge PR | `#170` |
| Merge commit | `7cd08c8` |
| Post-merge check-config | GitHub Actions run `28139043035`, passed |

This is a conservative production heartbeat. Increase frequency only after a
fresh OpenLeg source/rate review and an incremental-update plan.
