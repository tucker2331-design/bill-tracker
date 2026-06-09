---
tags: [knowledge, api, compliance, lis, rule]
updated: 2026-06-09
status: active
---

# LIS API Authorization Rule (2025/2026 only)

**RULE (from the LIS Developers Portal, `lis.virginia.gov/developers`, read 2026-06-09):**

> "API usage is authorized and validated for **2025 and 2026 session data only**. The
> General Assembly has **not** authorized the usage of data from sessions **prior to
> 2025** to be extracted with this API toolset. If you require data prior to the 2025
> session, please use **`legacylis.virginia.gov`** via CSV download. Once the General
> Assembly has authorized the data for use, you will be notified."

## What this means for us (hard constraint)
- The `lis.virginia.gov/*/api/*` endpoints **and** the `lis.blob.core.windows.net/lisfiles/*`
  CSVs may be used **only for session codes `20251` (2025) and `20261` (2026)** until LIS
  notifies otherwise.
- **Pre-2025 data MUST come from `legacylis.virginia.gov` (CSV download)** — never the new
  API toolset.
- This is an **authorization / terms-of-use** rule, not a technical access control: the new
  API will still *return* old-session data if asked, so the discipline is on us. Using a
  registered API key does not extend the authorization to older sessions.

## Compliance status (2026-06-09 audit)
- **Production: COMPLIANT.** `calendar_worker.py`, `accuracy_sentinel.py`, `reconcile_votes.py`
  all operate on the **active session only** (currently `20261`); the session code is derived
  at runtime from `Session/api/GetSessionListAsync` and never hardcoded to an old session.
- **One past violation, now remediated:** `tools/edge_case_replay/schedule_replay.py` (the
  Phase-C multi-session replay) had queried the new Schedule API for seven **pre-2025**
  sessions (`20242, 20241, 20231, 20221, 20212, 20211, 20202, 20201`). It was a one-time,
  read-only, internal edge-case test — nothing redistributed, nothing in the pipeline — but
  it was outside this authorization. **Fixed 2026-06-09:** the tool is now pinned to
  `LIS_API_AUTHORIZED_SESSIONS = {"20261","20251"}` with a runtime `assert`, so it cannot
  re-violate; pre-2025 format-variety testing must repoint to `legacylis.virginia.gov` CSVs.

## When onboarding state #2 (50-state scaling)
Every state will have its own data-use terms. Before pulling any state's data, capture its
authorization window the same way (a `*_API_AUTHORIZED_SESSIONS` allowlist + runtime assert),
and record the rule as a sibling of this page. Do not assume an API returning data implies
authorization to use it.

## Enforcement points (where this rule lives in code)
- `tools/edge_case_replay/schedule_replay.py` — `LIS_API_AUTHORIZED_SESSIONS` allowlist + assert.
- `calendar_worker.py` — session code derived from the live Session API (active session only).
- This page is the authoritative statement; see also [[index]] and [[log]].
