---
tags: [audit, fable, autonomy, rollover, capacity, zero-maintenance]
updated: 2026-07-04
status: active
---

# FABLE addendum — Autonomy upgrades A-1/A-2 (owner correction: zero-touch, not ping-the-human)

**Owner (2026-07-04):** *"Opus was meant to have built fixes so the code would check which session we are
in and automatically switch… same for the sheets running out… I'm not sure why your solutions were
pinging me to fix it when I explicitly stated my sustainability goals."*

The owner is right, and this page supersedes the human-in-the-loop parts of
[[audits/fable_2026-07/codebase_longevity_audit]] C-1 and C-2. Standard #8 is the law here: **alerts are
FYI; automation is the actuator.** A designed-in annual human step IS routine maintenance no matter what
the comment calls it.

## Verification: what exists today vs what was believed built

| Capability | Status | Evidence |
|---|---|---|
| Detect the current session automatically | ✅ BUILT | `get_active_session_info()` derives `ACTIVE_SESSION` from LIS's Session API every cycle (both workers). No hardcoded session on the data path. |
| Auto-EXTEND the authorization allowlist to the new session | ❌ NOT BUILT (deliberate) | `lis_authorization.py` docstring: portal authorizes "2025 and 2026 sessions ONLY… you will be notified"; the frozen set was designed as a "deliberate, ban-safe annual checkpoint." It halts-and-alerts on 20271. |
| Headroom-aware tab creation/growth vs the 10M-cell cap | ✅ BUILT | `_workbook_cell_headroom()` clamps every `add_worksheet`/grow (calendar_worker ~L1900–1930, Codex P2 #61). |
| Automated retention (witness 90d, metrics 45d) + monthly archive compaction | ✅ BUILT | `witness_retention.yml` + `metrics_history_retention.yml` daily, green; `compact_archive.yml` monthly auto-apply. |
| Capacity watch "years ahead" | ✅ BUILT | `sustainability_audit` CAPACITY checks incl. `archive-cells`. |
| **Automatic session-change workbook rollover** | ❌ NOT BUILT — **designed but left as a follow-up** | `tools/session_archive/archive.py` header: *"a worker rollover hook will call `snapshot-session` automatically on session change (follow-up). For now it is run via workflow_dispatch."* The hook never landed. |
| Mid-session automatic capacity relief | ❌ NOT BUILT | Growth is clamped + alerted, but nothing *moves* data automatically when headroom runs low. |

So: session *detection* and capacity *awareness* were built; session *authorization-follow* and workbook
*lifecycle actuation* were not. A-1 and A-2 below are the zero-touch completions.

---

## A-1 · Self-extending session authorization (auto-follow the legislature)

**Owner decision recorded:** the system follows LIS's own declaration of the active session
automatically. The human is informed, never required.

**The one honest constraint to respect:** the frozen list exists because LIS's *developer-portal terms*
authorize per-session, and querying UNAUTHORIZED sessions risks the ban (the 2020–2024 replay incident).
The design below stays ban-safe by (a) only ever following sessions **LIS's own Session API declares**,
(b) probe-verifying before full traffic, and (c) keeping HISTORICAL sessions frozen exactly as today.

**Design (Opus implements):**
1. In `lis_authorization.py`, split the concept:
   - `LIS_HISTORICAL_AUTHORIZED = frozenset({"20251", "20261"})` — unchanged semantics; tools/replays may
     never exceed it without an explicit owner edit (this is the anti-2020–2024 guard, keep frozen).
   - `is_authorized_session(code, active_info=None)` returns True when `code ∈ HISTORICAL` **or** `code ==
     the Session API's current active session** (passed in by the caller from
     `get_active_session_info()` — no new fetch; both workers already hold it).
2. **Probe-verify on first encounter of a NEW code** (once, cached in a state cell e.g. `Sheet1!S2 =
   "verified:20271"`): one Bills-list request for the new session; HTTP 200 + non-empty ⇒ verified,
   proceed; 401/403 ⇒ HALT exactly as today with a CRITICAL alert (this is the only remaining halt, and
   it fires only if LIS actively refuses the key — a genuine anomaly, Standard #8-legitimate).
3. **FYI alert, not action-required:** on first auto-follow:
   `INFO/DATA_ANOMALY "Auto-followed LIS into session 20271 (Session API active; probe verified). No
   action needed. Portal terms last reviewed <date> — see session_rollover notes."` Slack + Health chip.
4. **Kill switch:** env `AUTO_SESSION_FOLLOW=0` reverts to halt-and-alert (owner control preserved).
5. **One-time diligence step for Opus (build-time, not annual):** fetch the current
   lis.virginia.gov/developers wording; record in [[knowledge/lis_api_authorization]] whether it says
   key-holders are notified/carried forward per session. If the wording requires affirmative per-session
   registration, note it — the probe (step 2) still keeps us safe either way, because a non-carried key
   401s and we halt.
6. Front-end adjacents become automatic: backend stamps `session_code` into the completeness payload
   (kills `inferSessionCode`); `CROSSOVER_BY_SESSION` becomes *derive-or-absent* — show the crossover
   marker only when the new session's date is known (backend stamp or config), never a stale year's date
   (honest-absent beats wrong, §7).

**Validation gate:** integration test faking the Session API returning 20271: worker proceeds, probe
fires once, S2 records it, FYI alert emitted, second cycle silent. Then fake a 401 probe: worker halts
with CRITICAL. `AUTO_SESSION_FOLLOW=0` halts without probing.
**Effort:** ~3–4 h including tests. **Do this before Nov 2026.**

## A-2 · Automated workbook lifecycle (finish the designed-but-unbuilt rollover hook + add relief)

**Design (Opus implements):**
1. **The rollover hook (the missing piece archive.py already promises):** in `run_calendar_update`, the
   worker knows last cycle's session (state cell, e.g. `Sheet1!S3 = last_session_code`) and this cycle's
   derived one. On change:
   a. call `session_archive.snapshot-session` for the OLD session (idempotent, already built);
   b. verify the snapshot tab exists + row-count matches (the tool's own confirm-before-delete ethic);
   c. reset the live session-scoped tabs for the new session (Sheet1 viewport naturally re-derives; the
      caches: clear `API_Cache`/`Agenda_Cache` rows tagged to the old session — they're dead weight);
   d. write `S3 = new code`; emit ONE FYI alert "Rolled over 20261 → 20271; snapshot Session_20261
      archived (N rows verified); caches reset." No human step anywhere.
   Failure at any sub-step: keep the old-session data untouched, CRITICAL alert (a genuine anomaly).
2. **Mid-session relief (headroom actuator):** extend the existing weekly `sustainability_audit` CAPACITY
   check: when live-workbook cells > 6M, automatically run the (to-be-built) `ops-shard` move — relocate
   `Schedule_Witness` + `Metrics_History` to the ops workbook (C-2's design, now as an automated actuator
   with the same copy-verify-then-delete protocol archive.py uses). > 8M after shard = CRITICAL alert
   (that would be genuinely unprecedented and warrants eyes — Standard #8's real threshold).
3. **Pointer stability for readers:** the front end must never chase workbook IDs. Cleanest path: C-3's
   static-JSON publishing makes the worker the only thing that knows workbook IDs; until then the ops
   shard keeps ALL lobbyist-facing tabs in the current workbook (IDs unchanged), so no front-end change
   is needed for A-2.
**Validation gate:** dry-run rollover on a copy workbook (fake S3=20251): snapshot lands, verify passes,
caches reset, one alert. Cell-count actuator test with a threshold temporarily set at current size.
**Effort:** hook ~4 h (the hard parts — snapshot, verify, compaction — already exist); relief actuator
~1 day with the C-2 shard work it absorbs.

## Write-back of the standing lesson
Added to [[workflow/zero_routine_maintenance]] doctrine by this correction: **"Notify-only" is the test:
if an alert's remediation is a foreseeable, mechanizable edit (add a code, move a tab, rotate a file),
the system performs it and informs; a human is interrupted only when the world did something
unprecedented (upstream refuses the key, data fails integrity, terms change).** My original C-1/C-2
designs failed this test; A-1/A-2 pass it.
