---
tags: [knowledge, session, rollover, multi-state, watch]
updated: 2026-11-20
status: active
---

# Session rollovers, Dec 2026 – Jan 2027: what each state's job does, and what to watch

Checked 2026-11-20 (owner priority: session-critical bill tracking first). Dates follow each state's constitutional
rule [asserted: CA Art. IV §3(a) — sine die Nov 30 of even years, convenes the first Monday in December; PA Art. II
§4 — convenes the first Tuesday of January; VA Art. IV §6 — the second Wednesday of January; NY — the first
Wednesday after the first Monday of January]. Verify against each legislature's own calendar before relying on a day.

| state | old session ends | new session starts | how our job finds the session | at the edge |
|---|---|---|---|---|
| **CA** | Nov 30, 2026 | **Dec 7, 2026** (2027-28) | newest `SESSION_YEAR` in the daily pubinfo export (`ca_adapter.current_session`, 2026-11-20). Every export measured holds ONE session (2019/21/23/25 files) | an export with no regular-session bill **stops plainly** ("between sessions… the last published data stands"); nothing is written, so the site keeps 2025-26's final state until the new bills appear |
| **PA** | Nov 30, 2026 | **Jan 5, 2027** (2027_0) | newest REGULAR export listed on the data page (`pa_adapter.current_regular_session`) | a listed 2027_0 export with 0 bills passes the partial-universe check (0 = 0) and publishes the new session with 0 bills (honest on day one). Co-sponsorship memos for 2027-28 circulate in December |
| **NY** | — | Jan 6, 2027 | its own brain: [[ny/state/current_status]] | — |
| **VA** | (2026 sessions done) | **Jan 13, 2027** (20271) | the LIS Session API's active session; a NEW session is probe-verified once (`calendar_worker.session_follow_gate`, cached in `Sheet1!S2`) | LIS authorizes "session data from 2025 onward" (re-read 2026-08-01, [[knowledge/lis_api_authorization]]), so 20271 is in scope. The finished session is archived before the overwrite, with a capacity check first ([[architecture/session_archive]]) |

## What to look at, on the day
- **CA, Dec 1–8:** the CA job's run log either stops with "no regular-session bills" (expected until bills exist) or
  shows `session_display` "2027-2028 Regular Session". If two `SESSION_YEAR` values ever appear in one file, the newer
  wins; that has never been observed, so note it here.
- **PA, Jan 5–7:** the PA site's trust line should read the 2027-28 session; Bill count starts near 0. War Room
  positions are keyed by session, so 2025-26 stances stay with that session (PA bills die at session end).
- **VA, Jan 13–14:** the probe's one-time FYI ("following 20271"); `Session_<code>` archive tab written; the
  `20261 → 20262` lesson applies — young-session counts are small, ratios are what to judge
  ([[architecture/incident_counter]] "a chronic alert").
- **All states:** the tick gate ([[knowledge/lis_api_safety]]) keeps working across the rollover. A young session
  usually has few meetings, so the cadence stays slow until the calendar fills.
