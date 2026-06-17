---
tags: [knowledge, api, lis, rule, sustainability, cadence]
updated: 2026-06-17
status: active
---

# LIS API Safety & Sustainable Cadence (standing charter)

Sibling of [[knowledge/lis_api_authorization]]: that page governs **what** we may hit
(2025/2026 sessions only); **this** page governs **how hard and how often** — the rule
that keeps us a welcome, invisible API consumer for years of unattended operation, with
nothing to explain to LIS and no path to a ban.

## The standing rule (non-negotiable)
> **Every interaction with LIS — or any upstream source, for any of the 50 states — must
> be provably sustainable for unattended multi-year operation. Our request load must
> correlate with genuine legislative activity, never be a blind metronome. When in doubt,
> fetch less, cache more, and back off harder.**

This is Standard #2 (bank-grade reliability) and Standard #8 (zero routine maintenance)
applied to the *upstream* side: a year-round bot is judged on its pattern, not a single
day. The cadence *number* is downstream of the guardrails below — the number is never the
risk; the **pattern** (predictable metronome) and **unconditional re-downloads** are.

## The five guardrails (the actual safety; cadence rides on these)
| # | Guardrail | What it means | Status (2026-06-17) |
|---|-----------|---------------|---------------------|
| 1 | **Conditional fetch** | Never re-download unchanged data. Use ETag/`If-None-Match` / `Last-Modified` (→ 304) for blobs; content-hash to confirm; skip the download when unchanged. | ✅ **Shipped for HISTORY + DOCKET** (2026-06-17). `safe_fetch_csv` sends `If-None-Match` with the cached ETag; a 304 reuses bytes from `.lis_blob_cache/` (persisted across runs via the GitHub Actions cache) and skips the multi-MB transfer (HISTORY is 4.7 MB; Azure returns 304/0-bytes — verified). Accuracy-identical (304 = Azure byte-identity guarantee); any cache fault falls back to a full GET; kill switch `LIS_BLOB_CACHE=0`. **All three Azure blobs covered** (HISTORY + DOCKET via `safe_fetch_csv`; VOTE.CSV via the same helpers on its ragged-CSV path). Agenda PDFs already cached; LegEvent hydration already incremental; STM events already cached. Cuts upstream **bytes**; request count unchanged (still 1 conditional GET/blob). |
| 2 | **Jitter** | Never hit exactly :00/:15/:30/:45 forever — randomize within the window so we don't look like a bot and aren't trivially rate-limited. | ✅ **Shipped** (2026-06-17). `__main__` delays a SCHEDULED run (`GITHUB_EVENT_NAME==schedule`) by a random `0..JITTER_MAX_SECONDS` (default 180s) before the cycle — manual dispatch / Backfill Burst stay immediate. Decorrelates arrival from the cron tick; tiny vs the 3h interval, and the concurrency lock still serializes cycles at higher cadence. `JITTER_MAX_SECONDS=0` disables. |
| 3 | **Backoff + circuit breaker** | Respect 429/503/`Retry-After`; exponential backoff; halt + alert on sustained upstream errors. Never hammer a struggling source. | ✅ **Present.** `urllib3 Retry(total=4, backoff_factor=2, status_forcelist=[429,500,502,503,504])` on the session adapter; plus the data circuit breaker (W1/X1) halts on anomalous data. (Backoff covers transient throttling; it does **not** replace not-asking via guardrail #1.) |
| 4 | **Hard ceiling** | An absolute per-cycle request cap as a runaway guard, independent of the cadence logic — a bug can never spike us into a ban. | ✅ **Shipped** (2026-06-17). A counting HTTP adapter (`_CountingHTTPAdapter`) tallies every request in `send()` — *before* urllib3's retry loop, so a call that exhausts retries and raises is still counted (a response hook would miss it). If a single cycle exceeds `LIS_REQUEST_CAP` (default 15000, well above the worst healthy cold-start) it raises `LisRequestCapExceeded` (a `BaseException`, so it bypasses inner `except Exception` and aborts to `__main__`) → Slack CRITICAL + non-zero exit; Sheet1 keeps last-known-good. Counter resets per cycle (at the top of `run_calendar_update`, not in the session factory, so multiple sessions in one cycle accumulate). Scope: gspread/Sheets use their own session (uncounted); blob fetches are bare-requests + bounded. `LIS_REQUEST_CAP=0` disables. Per-cycle count logged for calibration. |
| 5 | **Activity-correlated cadence** | Fast **only** when there is genuine activity (a real meeting on the calendar). Slow otherwise. Load tracks the legislature, not the clock. | ❌ **Not present** (fixed 3h). This is the meeting-driven cadence policy below. |

The current **3-hour, no-jitter** cadence is safe today precisely *because it is so
conservative* — it compensates for the missing guardrails (1, 2, 4, 5). **Do not raise
cadence until guardrails 1, 2, and 4 are shipped.**

## Cadence policy: meeting-driven, not clock-driven (owner proposal, 2026-06-17)
The right design is **not** "fast during business hours" — it's **fast only when a real
meeting is on the calendar**:

- **Trigger = a structural meeting**, from the Schedule API — an entry with a concrete
  time (a committee/floor meeting), **not** an administrative HISTORY action (referral,
  printing, filing). Structural only (Standard #3 — no text parsing to decide cadence).
- **In a meeting window** (the meeting time + a tail afterward, since votes/reports post
  during and shortly after): bump to **4×/hour (~15 min)** to catch actions within ~15 min
  of posting — a real freshness need for lobbyists, not an arbitrary number.
- **No meeting scheduled** (most of the year, and quiet in-session stretches): drop to
  hourly or the 3h baseline.
- **Nothing on the forward calendar**: slowest tier.

Why this is the *most* defensible pattern: our load **rises exactly when LIS is already
serving that meeting's data and activity is real, and falls silent otherwise** — the
opposite of a blind metronome. It also dissolves the off-season objection from
[[ideas/future_improvements]] Step 5: interim committee meetings still appear on the
calendar off-season, so keying off *actual meetings* (not the session-lifecycle flag)
makes us go fast for those too, automatically, and stay quiet when there's truly nothing.

### Is 4×/hour sustainable? (honest assessment)
**Yes — in a meeting window, paired with guardrails 1–4.** Absolute volume is *low*: a
cycle is ~7 small API GETs + a few Azure-blob reads; 4×/hour is trivial for a government
API and Azure storage (a single analyst refreshing pages generates comparable load). The
two things that would make even a *lower* cadence riskier than necessary, and that we must
fix first:
1. **Re-downloading unchanged blobs** (the 4.7 MB HISTORY 48×/day when it changed maybe
   3×) — guardrail #1 collapses this to download-on-change.
2. **Metronome pattern** — guardrail #2 (jitter).
Backoff (#3, present) and a hard ceiling (#4, to add) are the seatbelts. With 1+2+4 in
place, 4×/hour *inside genuine meeting windows* is comfortably sustainable; **24/7** 4×/hour
is **not** the proposal and should never be the default.

### Compute side is already cheap (so cadence is purely an LIS-politeness question)
The incremental STM (shadow-validated 2026-06-17: 3,645 bills reused, 0 recomputed, exact
match) + the Stage-2 short-circuit make an unchanged cycle ~seconds of our compute. So
raising cadence costs *us* almost nothing — the only constraint is upstream politeness,
which is exactly what this charter governs.

## Sequence before flipping cadence up
1. Ship guardrail #1 (ETag/`Last-Modified` conditional blob fetch — Stage 2).
2. Ship guardrail #2 (jitter) + guardrail #4 (per-source daily cap + alert).
3. Ship the incremental-STM flip (in flight) so cycles are cheap.
4. *Then* ship guardrail #5 (meeting-driven cadence) — fast only in real meeting windows.

## 50-state scaling
This charter is **per-source**. Every new state's source gets the same five guardrails and
its own activity-correlated cadence, recorded as a sibling of this page. Never assume an
API that *tolerates* a cadence *welcomes* it for years.

See also [[knowledge/lis_api_authorization]], [[knowledge/lis_api_reference]],
[[ideas/future_improvements]] (Steps 4–6), [[architecture/alerting]], [[index]], [[log]].
