---
tags: [audit, fable, longevity, sustainability, va, ny]
updated: 2026-07-04
status: active
---

# FABLE 2 — Codebase longevity audit (VA + NY running code)

**Scope (the live system only):** `calendar_worker.py` (7,780 LOC, 3h cron) · `bill_tracker.py` (640,
6h cron) · `ny_bill_tracker.py` (835, daily) · `ny_calendar_probe.py` (731, manual) ·
`lis_authorization.py` · the scheduled workflows (accuracy_sentinel daily; completeness_tripwire,
legevent_reconcile, sustainability_audit, stm_order_invariance weekly; metrics_history + witness
retention daily; compact_archive monthly) · `web/src/` data layer (~2.2k LOC). Excluded: deprecated
`backend_worker.py`/`update_database.yml` (paused), `xray.py`, tests, one-shot tools.

**Audit lens (the owner's directive):** *"longevity and sustainability in my accuracy and extent of
data… ensure I don't have to come back and fix these for years."* Every finding is therefore rated by
**time horizon** (when it bites) and carries a validation gate.

**Overall verdict:** the VA engine is in genuinely strong shape — the guardrail charter
([[knowledge/lis_api_safety]]), the canary layer, write-time invariants, witness/reconciliation loops,
and the denominator discipline are exactly what decade-scale unattended operation needs. The real
longevity threats are *around* the engine, not in it: *dated rollover events nobody will remember,
storage growth against a hard platform ceiling, single-platform coupling, and NY lagging VA's hardening.*

---

## C-1 · Session rollover Jan 2027 — the system HALTS by design without a human (CRITICAL, dated)
> **SUPERSEDED 2026-07-04 (owner correction):** the runbook+canary design below made a human the
> actuator — Standard #8 violation. Implement **A-1 in [[audits/fable_2026-07/autonomy_upgrades]]**
> (auto-follow + probe-verify + kill switch + FYI alert) instead. The evidence below stands.
- **Evidence:** `lis_authorization.py:18` `LIS_API_AUTHORIZED_SESSIONS = frozenset({"20251","20261"})`;
  `run_bill_tracker()` and the calendar worker both hard-halt on an unauthorized session ("🛑 LIS
  authorization halt"). Front end: `web/src/data/calendar.ts` `CROSSOVER_BY_SESSION` has only `"20261"`;
  `web/src/data/gviz.ts inferSessionCode()` fallback. When LIS's Session API flips to 20271 (bills
  prefile ~Nov–Dec 2026; session convenes 2nd Wed of Jan 2027), **both workers stop producing new-session
  data until a human adds one string.**
- **Why it's built this way (keep it):** the gate is the deliberate ban-safety control — LIS access per
  session is owner-authorized. The fix is NOT auto-authorization; it's making the event **impossible to
  miss and 5 minutes to execute.**
- **Fix (detail):**
  1. Write `docs/workflow/session_rollover_runbook.md`: the exact checklist — add `"20271"` to
     `LIS_API_AUTHORIZED_SESSIONS`; add the 2027 crossover date to `CROSSOVER_BY_SESSION` (from the
     published 2027 session calendar); confirm `S1` flips to ACTIVE; confirm `test_start/end_date`
     derivation picked up the new session; run the completeness tripwire against 20271; archive-check the
     2026 Sheet1 story (see C-10). Each step with its verification command.
  2. **Horizon canary (zero-maintenance prompt):** the worker already calls the Session API every cycle.
     Add ~10 lines: if the Session API lists a session whose code is NOT in
     `LIS_API_AUTHORIZED_SESSIONS` and whose start date is within 45 days → `push_system_alert(WARN,
     DATA_ANOMALY, "Session 20271 begins <date> and is not authorized — run the rollover runbook")`,
     dedup-keyed per session code. Also surface on the Health tab as an amber chip. The runbook then has
     a built-in reminder; Standard #8 satisfied (the human is notified for a genuine one-per-year event,
     not a routine).
  3. Backend stamps `session_code` into the bill completeness payload (the gviz.ts fallback already
     prefers it — TODO noted in code) and, once known, `crossover_date` — killing both front-end
     hardcodes permanently (see C-9).
- **Validation:** simulate by temporarily removing "20261" locally → both workers halt with the alert;
  the canary fires when pointed at a mock session list. Runbook dry-run before Dec 2026.
- **Effort:** runbook 1 h; canary ~2 h; completeness stamp ~1 h.

## C-2 · Google Sheets cell ceiling — the witness tab is the whale (HIGH, ~12–24 mo)
> **PARTIALLY SUPERSEDED 2026-07-04:** stage (1) measure stays; stages (2)-(3) become the AUTOMATED
> actuators of **A-2 in [[audits/fable_2026-07/autonomy_upgrades]]** (rollover hook + headroom-triggered
> shard — zero-touch). Note: more automation existed than this audit first credited (headroom-aware tab
> creation, retention prunes, monthly compaction); the missing piece is the actuation hook archive.py
> itself documents as an unbuilt follow-up.
- **Evidence (measured 2026-07-04 via gviz counts):** Schedule_Witness ≈ **232,570 rows** (13 cols ≈
  3.0M cells) *with the 90-day prune green*; Metrics_History ≈ 72,181 rows (flood-era backlog; shrinks
  after #190 + 45-day prune); Sheet1 ≈ 37,810 × 15; LegEvent cache tabs; Bill_Tracker 3,645 × 18. The
  workbook is plausibly at 4–5M of Google's hard **10M cells per spreadsheet**. A second VA session's
  witness volume + NY (if ever co-located) + new columns ⇒ the wall is reachable within one to two
  sessions. Hitting it = **every write fails** = the worst possible failure mode.
- **Fix (detail), three stages:**
  1. **Measure continuously (this month):** extend `sustainability_audit.yml` (tools/cell_count_audit
     exists, manual) to compute total workbook cells weekly and alert at 6M (warn) / 8M (critical). A
     ceiling you watch is a plan; one you don't is an outage.
  2. **Shard by concern (this quarter):** machine-only tabs do not need to live in the lobbyist workbook.
     Move `Schedule_Witness` + `Metrics_History` to a separate "ops" spreadsheet (new
     `OPS_SPREADSHEET_ID` secret; the writers already isolate these code paths — small diffs in
     `calendar_worker.py` witness/metrics writers + `tools/witness_retention/prune.py`,
     `tools/metrics_history/prune.py`, `web/src/data/history.ts` URL). This alone removes ~3.3M cells and
     decouples ops-data growth from product data forever.
  3. **Long term (design note, not now):** machine-only history belongs in artifacts, not Sheets —
     e.g. append Parquet/SQLite to GitHub Releases per month. Sheets remain for: lobbyist-facing tabs +
     small state cells. Do this only when (2) proves insufficient.
- **Validation:** cell gauge on Health; after the shard, workbook total drops below 2M and the witness
  writer's first cycle against the ops workbook passes reconciliation.
- **Effort:** gauge 2 h; shard ~1 day incl. migration + front-end history URL.

## C-3 · Platform coupling: gviz + link-readable + GitHub Actions (MEDIUM, undated but real)
- **Evidence:** the entire front end reads via the **undocumented** `gviz/tq` CSV endpoint of a
  link-readable sheet (web/src/data/*.ts); the entire compute layer is GitHub Actions cron (observed
  queue delays of ~12 min already; scheduled-run deprioritization is documented GitHub behavior).
- **Risk:** Google can change/limit gviz semantics without notice (it has broken before historically);
  "anyone with link" is also a quiet data-governance decision that must hold for years; Actions outages
  stop the product silently between guard runs.
- **Fix (detail):**
  1. **Static snapshot publishing:** at the end of each worker cycle, ALSO write the exact JSON the front
     end needs (`bills.json`, `calendar.json`, `health.json`) to a static host (Cloudflare Pages/R2 — the
     deploy target the roadmap already names — or a `gh-pages` branch). Front end: try static JSON first,
     fall back to gviz. This inverts the dependency: the undocumented endpoint becomes the fallback.
     Bonus: removes the ~5 MB Sheet1 fetch on calendar loads (speed win) and the link-readable
     requirement for readers.
  2. **Actions liveness watch:** the freshness clocks on Health already catch a stalled scheduler; add
     the missing notifier — if `AA1` age > 3× cadence, the accuracy_sentinel (which runs on a different
     trigger) should Slack-alert. Verify accuracy_sentinel currently checks freshness; if not, add it.
- **Validation:** unplug gviz locally (block the domain) → app fully functional from static JSON.
- **Effort:** ~1–2 days; can ride the planned Cloudflare Pages deploy task.

## C-4 · The worker monolith (LOW urgency, HIGH care) — refactor only behind the golden harness
- **Evidence:** 7,780 lines, one file; recurring bug class from function-scope shadowing and gate
  hoisting (audit #50–#53); AST-extraction is how tests/tools already borrow pure functions — evidence
  the pure core wants to be modules.
- **Fix (sequenced, NOT now):** after the 2027 rollover proves out, extract in this order, one PR each,
  with the existing golden tests + `stm_order_invariance` + a full before/after Sheet1 diff as the gate:
  (1) time engine (`parse_24h_time`, `_resolve_one_day`, `build_time_graph`, offsets) → `engine/time.py`;
  (2) classifiers (`classify_*`, `_is_relative_time_text`, routing) → `engine/classify.py`;
  (3) blob/cache IO. The tools that AST-extract (schedule_replay, validate_relative_chains) then import
  normally — deleting their `exec` machinery. **Do not** extract stateful cycle code; the risk/benefit is
  wrong.
- **Validation per PR:** byte-identical Sheet1 output on a pinned replay (`live_run=False` path) + all
  golden tests + Section 9 = 0 on the next live cycle.

## C-5 · LIS source-contract coverage — one canary gap (MEDIUM)
- **Evidence:** 5 vocabulary canaries + refid-shape drift + ScheduleTypeID first-fire + Location alias
  chain = excellent coverage of HISTORY/Schedule surfaces. **Gap:** `bill_tracker.py`'s outcome oracle is
  BILLS.CSV's flag columns (Vetoed/Approved/Chapter_id/Carried_over/Failed/Passed). If LIS renames a
  column or changes Y/N encoding, `_outcome_from_flags` returns None for every bill → the keyword
  fallback silently takes over 100% of outcomes (visible only as `outcome_structural` dropping — which
  nothing alerts on).
- **Fix:** in `build_bill_records`, after the BILLS.CSV join: (a) assert the expected flag columns exist,
  alert `DATA_ANOMALY/CRITICAL` listing missing ones; (b) alert if `outcome_structural /
  records_written < 0.9` (steady ≈ 0.997) — the "oracle went dark" tripwire; (c) add the flag-column
  presence to the weekly sustainability audit. Mirror the same idea for VOTE.CSV (`vote_csv_thin` alert
  already exists — good).
- **Validation:** unit-test with a BILLS.CSV missing `Approved` → CRITICAL alert fires, outcomes fall
  back with the drop-rate alert.
- **Effort:** ~2 h.

## C-6 · Caches: integrity is solid; add self-sizing awareness (LOW)
- **Evidence:** blob cache (ETag/304, marker-validated, fail-safe re-download), Agenda_Cache (settled-only,
  load_ok guard), LegEvent cache (tiered TTL, hash-change detection) — all carry the lessons of audits
  #89/#153. Remaining risk is only growth (`Agenda_Cache` 491 rows now, but each session adds; LegEvent
  cache scales with bills×events).
- **Fix:** fold cache row/cell counts into the C-2 weekly gauge; define per-cache retention (e.g. agenda
  cache rows for sessions older than the authorized set are dead weight — prune on session archive).
- **Effort:** 1 h inside the C-2 work.

## C-7 · `bill_tracker.py` — smallest, healthiest; two notes
- Floor vocabulary (`_PASS_/_DEFEAT_*_RE`) now alerts on reconcile drift >1% (shipped #191) ✓.
- Patron is surname-only (BILLS.CSV); the full-name upgrade from the universe `Patrons` field is a
  pending product item — fold into a normal PR, no longevity risk.
- `checked_at_utc` / completeness self-describes ✓. Add `session_code` stamp (C-1.3).

## C-8 · New York — functional but missing VA's hardening layer (HIGH for NY accuracy)
> **STATUS 2026-07-06 — RE-MEASURED; more hardened than this audit assumed.** Reading `ny_bill_tracker.py`
> against the spec below (doctrine #1: measure before building):
> - **(a) vocab canaries — mostly ALREADY PRESENT / low-value.** Chamber codes ALREADY have the drift
>   canary: `unknown_origin_chamber` / `unknown_action_chamber` / `unknown_agenda_chamber` counters →
>   surfaced as health WARN findings WITH denominators, and an unnormalizable chamber is kept as `chamber_raw`
>   (never guessed). `status.statusType`/`statusDesc` are **DISPLAY/PROVENANCE ONLY** (per docs/ny
>   bill_pipeline + quality_audit + assumptions_register) — they feed NO logic, so a statusType-drift canary
>   is low-value: a new statusType can't break accuracy. Action text is display-only too (`_history` keeps
>   it, never classifies it). NY's accuracy path is already STRUCTURAL: `_derive_outcome` reads only `signed`
>   (bool) + `vetoMessages` (presence), and an unmapped outcome ALREADY fires `UNKNOWN_STRUCTURAL_OUTCOME`
>   WARN with a denominator. **→ No new canary added: it would be a marginal watcher on a display-only field,
>   i.e. a change with no data justification (Standard #7).**
> - **(b) independent oracle — the REAL remaining value, and it's OWNER-GATED.** NY has nothing outside
>   OpenLeg. The valuable port is LegiScan-NY (or Assembly/Senate public-site) reconciliation — needs a
>   **LegiScan API key + a terms check** (owner infra), same class as the other owner-gated items.
> - **(c) session-year rollover:** fold NY into the rollover runbook alongside VA — a doc task, bundle with
>   the next NY session.
> **Net:** C-8's high-value work is Part 2 (oracle, owner-gated); the canary gap it names is largely already
> closed. Do the oracle when the owner provisions a LegiScan key.
- **Evidence (read of `ny_bill_tracker.py` + docs/ny/):** clean source contract (OpenLeg API v3, paged,
  retry/backoff, fail-safe keep-last-known-good, machine-readable completeness with named gaps —
  Assembly calendar/committee absence is documented honestly). **Missing vs VA:** (a) no drift canaries
  on OpenLeg vocabularies (`status.statusType`, action-text families, chamber codes) — the NY analog of
  the watchers that caught real drift in VA; (b) no independent verification guard (VA has MinutesBook
  reconciliation + LIS-calendar tripwire; NY has nothing outside OpenLeg itself); (c) session-year
  rollover is `NY_OPENLEG_SESSION_YEAR` env or derived? (env-first — same class as C-1: put NY in the
  rollover runbook + horizon canary via OpenLeg's session listing); (d) API-key dependency
  (`NY_OPENLEG_API_KEY` — document rotation; OpenLeg keys are free but revocable).
- **Fix (port the proven patterns, in order):**
  1. NY vocab canaries: on each run, diff observed `status.statusType` values + chamber codes against a
     committed registry; unknown → WARN + quarantine row handling (never guess). ~2 h.
  2. NY independent oracle: **LegiScan's NY dataset** (weekly bulk JSON) as the reconciliation source —
     count bills, compare last-action dates on a sample; divergence rate with denominator, weekly
     workflow like legevent_reconcile. (Check LegiScan terms for this use; free tier exists. Alternative:
     NY Assembly/Senate public site spot-checks like the VA completeness tripwire.) ~1 day.
  3. Add NY to the rollover runbook (odd-year sessions; 2027–28 session starts Jan 2027 too).
- **Validation:** canary catches a synthetic unknown statusType; reconciliation baseline established and
  tracked like VA's 0.33%.

## C-9 · Front-end hardcodes that belong to the backend (LOW, rides C-1)
- `CROSSOVER_BY_SESSION` pinned date and `inferSessionCode` year-inference — both erased by C-1.3
  (backend stamps). The TODO comments already point this way; finish it.

## C-10 · Multi-session data story — decide before 2027 (MEDIUM)
- **Question the code doesn't answer yet:** when 20271 becomes active, Sheet1's viewport moves to the new
  session; what does the product show for 2026 bills (carried-over bills re-file; lobbyists will want
  last-session history)? `session_archive` tooling + `compact_archive.yml` exist for archival, but the
  product-level answer (a session picker? archive workbooks read-only?) is undesigned.
- **Fix:** a design page (`docs/ideas/multi_session_product.md`) BEFORE the rollover: per-session
  workbook naming, what the front end offers for past sessions, and how carried-over bills link their
  2026 history to their 2027 record (LIS re-numbers; BILLS.CSV `Carried_over` flag + same-catchline join
  is the structural candidate — needs validation against real 2025→2026 carryovers).
- **Effort:** design 2–3 h now; saves an emergency in January.

## Priorities recap (also mirrored in the hub README)
C-1 (dated, cheap) → C-2 (whale) → C-5 + C-8.1/8.2 (accuracy oracles) → C-3 (platform inversion) →
C-9/C-10 (rollover adjacents) → C-4 (only when calm, behind the harness).
