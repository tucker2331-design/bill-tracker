# Reconciliation Tripwire (Standard #2)

`reconcile_votes.py` diffs our calendar output (Sheet1) against an **independent**
LIS source the worker pipeline never touches — the official committee
**MinutesBook** API. This is the continuous answer to *"who's to say that's all
the bugs?"*: it catches **unknown** output drift in production (mis-attribution,
fabricated meetings, gross date errors), not just bugs we can enumerate.

## What it checks (and what it doesn't)
The official minutes reliably record that a committee **met** and **acted on a
bill**, but their structured `VoteTally` field is frequently **empty** (the tally
lives in the LegislationEvent — our own source — so a vote-to-minutes diff is
unreliable *and* partly circular). So the tripwire verifies the durable,
independent signal: **every committee report we publish corresponds to a real
official meeting of that committee that acted on that bill**, within ±2 days
(absorbing the known HISTORY-vs-LegEvent date drift).

Per row: `MATCH_SAMEDAY` · `MATCH_NEARBY` (date-drift, informational) ·
`MISATTRIB` (committee has minutes near the date but the bill is absent — **drift**) ·
`NO_BOOK` (no book near the date — coverage gap, not our error).

## Baseline (2026-06-07, session 20261)
3338 committee reports · **99.67% confirmed** · date-drift 1 · coverage gap 0 ·
**mis-attribution 0.33% (11)** → PASS. The 11 are concentrated on opening-day
joint resolutions (1/14) and 2/24 crossover-day boundaries — stable known
residual, not systematic drift.

## Run
```
python3 tools/reconciliation/reconcile_votes.py --max-drift 1.0   # exit!=0 if drift exceeds
```
No secrets — reads the live Sheet via the public gviz CSV. Also wired as the
`🔎 Reconciliation Tripwire` GitHub workflow (manual `workflow_dispatch`;
`schedule` is ready to enable once the baseline is confirmed stable).

## External-source brittleness (Gemini review)
This tripwire's independent reference is the LIS **MinutesBook JSON API**
(`getpublishedminutesbooklistasync` + `getminutesbookasync`) — **not** HTML/PDF
scraping, so it is more stable than a scraper, but it is still an external
government API that can change shape or be retired. Guard: if the fetch throws or
the published-book count falls below `MIN_EXPECTED_BOOKS` (50; a real session
publishes hundreds), the tool raises a distinct **`EXTERNAL SOURCE CHANGE`**
failure (exit code **2**, vs **1** for a real drift breach) — an empty/broken
independent source verifies nothing and must never be reported as "0 drift / PASS."
If you see exit 2, investigate the MinutesBook API contract before trusting any
subsequent reconciliation.
