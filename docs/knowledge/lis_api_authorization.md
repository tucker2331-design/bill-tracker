---
tags: [knowledge, api, compliance, lis, rule]
updated: 2026-08-01
status: active
---

# LIS API Authorization Rule (2025/2026 only)

**⚠️ WORDING CHANGED — re-read 2026-08-01. The portal now says "from 2025 onward", not "2025 and 2026
only".** Current text, verified live:

> "API usage is authorized and validated for **session data from 2025 onward**. The General Assembly has
> not authorized the usage of data from sessions prior to 2025 to be extracted with this API toolset. If
> you require data prior to the 2025 session, please use **legacylis.virginia.gov** via CSV download. Once
> the General Assembly has authorized the data for use, you will be notified."

The forward bound is now **open-ended**, which is what the A-1 auto-follow design already assumed — so the
workers were right by accident, and are now right on the record too. The pre-2025 prohibition is unchanged.
**ToS §1 lets DLAS change terms at any time, so any quote here has a shelf life; re-read before relying on
it in anything that leaves this repo.**

**PRIOR RULE (as read 2026-06-09) — superseded, kept so the change is visible:**

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

## A-1 (2026-07-05): self-extending authorization — the live workers auto-follow the active session
Previously the authorized set was a frozen `{20251, 20261}` that **halted both workers on any new session**
(e.g. `20271`), requiring a manual annual edit — a Standard #8 violation (the system would halt Jan 2027
without a human). A-1 fixes this **zero-touch and ban-safe** (PR #201, [[audits/fable_2026-07/autonomy_upgrades]] A-1):

- **Two scopes in `lis_authorization.py`:** `LIS_HISTORICAL_AUTHORIZED` = the FROZEN, human-curated set of
  known-authorized past sessions (the anti-2020–2024-replay guard; tools/replays may never exceed it). The
  **live active session** is authorized separately, passed in per call by the workers from
  `get_active_session_info()`. `is_authorized_session(code, active_session=…)` authorizes a code that's
  historical OR the current active one. `LIS_API_AUTHORIZED_SESSIONS` stays a frozen alias (tools unchanged).
- **The probe is the real ban-safety gate** (`calendar_worker.session_follow_gate`): a NEW active session is
  probe-verified ONCE with a single bills-list GET — `200 + non-empty` ⇒ follow it + one-time FYI; `401/403`
  ⇒ HALT (LIS genuinely refused the key — the only remaining halt); transient/empty ⇒ halt this cycle, retry.
  The result is cached in **`Sheet1!S2`** (`verified:20271`) so the probe fires once, shared across both workers.
- **Kill switch:** `AUTO_SESSION_FOLLOW=0` reverts to the old halt-on-new-session checkpoint (owner control).
- **One-time diligence (open):** re-review the `lis.virginia.gov/developers` wording when the 2027 session
  authorizes, and note here whether keys carry forward per session. The probe backstops us either way (a
  non-carried key `401`s and we halt), so this is a courtesy record, not a safety dependency.
- **Front-end follow-up (deferred, not halt-critical):** backend should stamp `session_code` into the
  completeness payload (kills `inferSessionCode`) and `CROSSOVER_BY_SESSION` should become derive-or-absent.

## Compliance status (2026-06-09 audit)
- **Production: COMPLIANT.** `calendar_worker.py`, `accuracy_sentinel.py`, `reconcile_votes.py`
  all operate on the **active session only** (currently `20261`); the session code is derived
  at runtime from `Session/api/GetSessionListAsync` and never hardcoded to an old session.
- **One past violation, now remediated:** `tools/edge_case_replay/schedule_replay.py` (the
  Phase-C multi-session replay) had queried the new Schedule API for **eight** **pre-2025**
  sessions (`20242, 20241, 20231, 20221, 20212, 20211, 20202, 20201`). It was a one-time,
  read-only, internal edge-case test — nothing redistributed, nothing in the pipeline — but
  it was outside this authorization. **Fixed 2026-06-09:** the tool is now pinned to
  `LIS_API_AUTHORIZED_SESSIONS = {"20261","20251"}` with a runtime `assert`, so it cannot
  re-violate; pre-2025 format-variety testing must repoint to `legacylis.virginia.gov` CSVs.

## Discovery + contact record (added 2026-08-01, so this is never re-litigated from memory)

- **The 2026-06-09 violation was SELF-DISCOVERED** in our own compliance audit. **There is no record of any
  notice, warning, or contact from LIS or DLAS** — not before, not since. Checked 2026-08-01.
- **Why it happened, kept because the cause is the reusable part:** the API does not enforce this. A valid
  key will happily serve 2020 data. The boundary is terms-of-use, not technical, so nothing fails loudly —
  the discipline has to be ours, which is exactly why the runtime `assert` now exists.

### Endpoint-scope note — `GetSessionListAsync` returns the full catalog and cannot be scoped

`Session/api/GetSessionListAsync` takes **no session parameter**. It returns every session (59 of them,
back to 1994) on every call. The production workers must call it to derive the active session, so calling
it is the documented compliant design and is unavoidable.

**Consequence to be honest about:** any caller receives the pre-2025 catalog whether or not they want it.
Reading session *metadata* from that response (which sessions exist, their names and years) is not the
same as extracting pre-2025 legislative *data* — bills, votes, history, members — which is what the
authorization governs and which we do not do. Recorded here so a future session does not mistake the
unavoidable catalog read for a breach, and equally does not use it as cover for a real one.

**Done 2026-08-01 in this project:** `GetSessionListAsync` (no param, used for the 2026 session
DisplayName), `GetLegislationEventTypeReferencesAsync?sessionCode=20261`, and blob reads under
`lisfiles/20261/`. All authorized. Pre-2025 came exclusively from
[[knowledge/legacylis_csv_route]], the channel the Developers Portal names.

## When onboarding state #2 (50-state scaling)
Every state will have its own data-use terms. Before pulling any state's data, capture its
authorization window the same way (a `*_API_AUTHORIZED_SESSIONS` allowlist + runtime assert),
and record the rule as a sibling of this page. Do not assume an API returning data implies
authorization to use it.

## Enforcement (single source of truth + every live caller gated)
The rule is enforced in code by **`lis_authorization.py`** (repo root) — the ONLY place the
authorized scope is defined. **Since A-1 (2026-07-05, see above) there are TWO scopes:**
- `LIS_HISTORICAL_AUTHORIZED = {"20251","20261"}` — the FROZEN human-curated set (anti-replay guard).
  `LIS_API_AUTHORIZED_SESSIONS` is a backward-compat alias of it (tools/replays keep frozen semantics).
- the **live active session**, followed by the workers via `is_authorized_session(code, active_session=…)`
  + `calendar_worker.session_follow_gate`'s one-time probe (`Sheet1!S2` cache; `AUTO_SESSION_FOLLOW=0` kill switch).
- `is_authorized_session(code[, active_session])` / `assert_lis_authorized(code[, active_session])` (normalizes legacy 3-digit "261").

Every code path that hits `lis.virginia.gov` or `lisfiles/*` is gated through it:
- `calendar_worker.py` + `bill_tracker.py` — after deriving the active session, `session_follow_gate`
  **auto-follows** it (probe-verified) or **HALTs + CRITICAL alert** only if LIS refuses the key / the kill
  switch is set (no data calls; Sheet1 keeps last-known-good). **2027 is now followed automatically (A-1).**
- `backend_worker.py` — `get_active_session()` now **only probes authorized-session blobs**
  (the old probe HEAD-hit `year+1` 2027 URLs in November — a ban risk), plus a main-flow gate.
- `pages/ray2.py` + `calendar_xray.py` — `load_lis_schedule()` asserts before the Schedule call.
- `tools/reconciliation/reconcile_votes.py` — asserts `--session` before any MinutesBook call.
- `tools/edge_case_replay/schedule_replay.py` — imports the shared set (no local copy).
- `tools/verification/accuracy_sentinel.py` — reads only the Google Sheet (gviz), **no LIS call** → no gate needed.

To widen for a new authorized session: edit the one set in `lis_authorization.py`. This page is
the authoritative statement; see also [[index]] and [[log]].

## API-key rotation (S-1, PR #203)
The LIS `WebAPIKey` values are a SINGLE env-first source in `lis_authorization.py`:
`LIS_API_KEY` (legacy toolset key) and `LIS_PUBLIC_API_KEY` (the SPA key the LegislationEvent/Version
endpoints require). Both are public/SPA-class (they ship in every lis.virginia.gov page), so this is
rotation resilience, not secrecy.
- **If LIS rotates a key:** set the GitHub Actions secret `LIS_API_KEY` (and/or `LIS_PUBLIC_API_KEY`) on the
  worker workflows — **no code edit**, no hunting hardcoded copies. Every runnable importer picks it up.
- **Annual diligence:** confirm the current key still authenticates (a 401/403 surfaces as an
  `API_FAILURE` alert; the workers' `auto_session_follow` probe also 401s on a dead key and halts). The
  literal fallbacks in the module keep today's behavior when the secrets are unset.
