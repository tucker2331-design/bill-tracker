# Crossover Week Audit Tools

Reproducible scripts for auditing Sheet1 vs LIS website (tier-A ground truth) for the crossover-week investigation window (Feb 9-13, 2026).

Full methodology + findings: [[testing/crossover_audit]] in the `docs/` vault.
Scraping technique: [[knowledge/lis_dom_scraping]].

## Scripts

| File | Purpose |
|---|---|
| `build_universe.py` | Enumerate all bills with Feb 9-13 activity from HISTORY.CSV. Output: `to_fetch.txt` |
| `fetch_bills.sh` | Headless Chrome fetch of LIS bill-details pages, 8x parallel, with retry for undersized dumps |
| `extract_truth.py` | Parse DOM dumps → structured JSON of {date, chamber, committee, action, refid} per bill |
| `diff_sheet1.py` | Join Sheet1 rows against LIS truth + Schedule API; emit categorized discrepancy list |

## Running the audit

```bash
# 1. Build universe from cached HISTORY.CSV
python3 tools/crossover_audit/build_universe.py

# 2. Fetch bill pages (outputs to /tmp/lis_audit/<BILL>.html)
bash tools/crossover_audit/fetch_bills.sh /tmp/lis_audit/to_fetch.txt

# 3. Extract structured LIS truth JSON
python3 tools/crossover_audit/extract_truth.py \
    --dumps /tmp/lis_audit \
    --out docs/testing/crossover_lis_truth.json

# 4. Diff against Sheet1 + HISTORY
python3 tools/crossover_audit/diff_sheet1.py \
    --sheet1 /tmp/lis_audit/sheet1.csv \
    --truth docs/testing/crossover_lis_truth.json \
    --history /tmp/lis_audit/history.csv \
    --out docs/testing/crossover_audit_findings.json
```

## Data

- **Canonical truth** — `docs/testing/crossover_lis_truth.json` (checked in; source of record).
- **Raw DOM dumps** — `/tmp/lis_audit/*.html` (not checked in; regenerate via `fetch_bills.sh` if needed).
- **Schedule API cache** — `/tmp/lis_audit/sched.json` (worker-equivalent; not checked in).
- **Findings** — `docs/testing/crossover_audit_findings.json` (checked in; input to future PR-C fix work).

## Why this exists

Crossover week is historical data — frozen, not changing. Running the audit once and persisting the truth JSON means no re-fetch needed for future verification. See [[failures/pr22_post_mortem]] for why measurement-with-denominator matters.
