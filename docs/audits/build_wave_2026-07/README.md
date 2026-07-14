---
tags: [audit, plan, execution-spec, product, frontend, worker]
updated: 2026-07-13
status: active
---

# BUILD WAVE 2026-07 — the priority-ordered execution queue for Opus

> **What this is (read first):** the owner ran a multi-round product-ideation + design cycle with Fable
> (2026-07-13, [[ideas/lobbyist_jtbd_ideation]] §8–8d) and asked Fable to bank a meticulous execution spec
> so Opus can do the build work. **Decisions here are OWNER-LOCKED unless marked `OWNER-GATED`** — do not
> re-litigate them; do not "improve" a locked design. Where this spec says measure/verify, that step is as
> mandatory as the code. Follow CLAUDE.md session-start reads + the pre-push audit + the bot fold-in loop
> ([[workflow/bot_review_fold_in]]) on every PR, and MERGE when green (the owner's standing workflow) —
> then verify the produced row/pixel, never just the projection ([[failures/assumptions_audit]] #74/#101).

## Standing process rules for this wave (violations here burned us this month)

1. **A recommendation is NOT a decision.** Any design/UX change to a live surface not already locked below
   needs explicit owner sign-off BEFORE it enters code ([[ideas/lobbyist_jtbd_ideation]] §8c process
   correction). When in doubt, present options + a recommendation and STOP.
2. **Mockups and UI obey the design canon** — read [[design/dashboard_and_visual_language]] (esp. "The
   change-register pattern" + the AI-tells list) and [[design/information_display]] BEFORE drawing or
   styling anything. Registers are monochrome; color is earned; routine is grey.
3. **pyflakes gate**: `python3 tools/prepush_audit.py --base main` before every push (check 17 catches the
   use-before-assignment class that caused the 0→66 saga, audit #105).
4. **Worker output changes** (anything altering Sheet1 values/columns) require a
   `WORKER_OUTPUT_LOGIC_VERSION` bump (audit #96). New TABS are additive and need no bump — but say so in
   the PR body so reviewers see it was considered.
5. **LIS safety**: no new unconditional fetch loops; anything hitting LIS respects
   [[knowledge/lis_api_safety]] (budgets, jitter, ETag reuse).
6. **Verify in the browser** with the dev server (`.claude/launch.json` → `web`) before pushing frontend
   work; verify the DEPLOYED bundle after merging (grep the live JS/CSS for a distinctive token, then
   exercise the surface).
7. **Write back to the brain** every session: [[log]] entry per PR, [[state/current_status]] MOVE-only,
   lessons → [[failures/assumptions_audit]] / [[failures/gemini_review_patterns]] (+ rerun
   `python3 tools/reindex_caselaw.py` after either).

---

## TASK 0 — finish PR #219 if not already merged (may already be done)

State when this spec was written: #219 (the card bundle) was green after one bot fold-in round.
If it is still open: check for NEW inline bot comments since the last commit, fold in real ones, merge
(`gh pr merge 219 --merge --delete-branch`), then **deploy-verify on production**:
- `curl` the live site, find the JS bundle, confirm it contains `nextMeetingFor` and `star-confirm`;
- open https://bill-tracker.tucker2331.workers.dev, search HB463 (or any bill on a future interim docket —
  find one via the calendar data if HB463's meeting has passed), confirm the enriched Next-meeting row +
  working Agenda/Watch links; confirm patron "· Surname" on list cards; star → lit-star click → confirm
  popover (Keep tracking autofocused) → Untrack works.
- Brain write-back: [[log]] `## [date] pr | #219 MERGED …`; [[state/current_status]] RECENTLY LANDED MOVE;
  mark §8c/§8d items "BUILT" in [[ideas/lobbyist_jtbd_ideation]].

---

## TASK 1 — THE CHANGE LEDGER (the wave's centerpiece; owner-approved design)

**What it is:** a new user-facing **"Changes" tab** answering *"what's different since I last looked?"*
with exact before → after per delta. Visual spec is LOCKED: the v2 register mockup
(https://claude.ai/code/artifact/17b5817d-247c-4007-9da8-45eeb093ab56) + the codified register pattern in
[[design/dashboard_and_visual_language]]. Owner concerns already answered in [[ideas/lobbyist_jtbd_ideation]]
§8d — re-read it; the three constraints below fall out of it.

**The three load-bearing constraints (owner-verified):**
- **C1 — bounded vocabulary:** the ledger never paraphrases LIS prose. Kinds are OUR differ's closed set;
  payloads are QUOTED raw values (old → new verbatim). One sentence template per kind, ~6 total. Any delta
  the differ can't classify renders a generic-but-true row ("record changed — view the bill card") AND
  fires a categorized drift alert (mirror the agenda-label canary pattern, `calendar_worker.py` ~L7397).
- **C2 — detection-time honesty:** the time shown is when OUR cycle saw it, never presented as when LIS
  acted. Label/tooltip it. Styling: detection times render MUTED grey, not accent (accent time = a real
  meeting clock in What's-new; do not overload it). This muted-vs-accent choice is my recommendation
  applied as default — note it in the PR for the owner to veto cheaply.
- **C3 — per-browser "last visit":** a localStorage timestamp marker (same mechanism as stars). Label
  honestly ("since you last looked on this device"). Per-person comes later with the watchlist identity
  work (TASK 3) — do NOT build accounts here.

### Phase L1 — the worker-side differ + the `Change_Ledger` tab (no UI yet)

**Investigate first (½ session, write findings into this page):**
- `WITNESS_DELTA_FIELDS` in `calendar_worker.py` — exactly which schedule fields the witness already
  diffs (time/status/location/…?) and its row schema. The witness IS the schedule-delta source; do not
  build a second schedule differ. Determine whether per-meeting BILL-LIST changes (docketed / off-docket)
  are visible in witness deltas or need a new diff over `docket_memory`/agenda bills vs the prior cycle.
- The per-bill history hash machinery: `_hash_history_rows_for_bill`, `legevent_history_hashes`, and the
  `LegEvent_Bills.LastHistoryHash` column — the worker already knows WHICH BILLS changed each cycle.
  Row-level diff needs the prior rows, not just the hash: decide between (a) persisting a compact per-bill
  rows-hash LIST (hash per history row, ordered) in a new column/tab and diffing hash lists, or (b) diffing
  against the previous cycle's HISTORY.CSV cached bytes (`.lis_blob_cache/` keeps the last blob — verify
  whether the PREVIOUS version survives a cycle or is overwritten; if overwritten, (a) is the design).
  (a) is my recommendation: deterministic, small, no second blob retained.
- Measure expected volume: on the static off-season corpus, deltas/day ≈ 0; simulate in-session volume by
  replaying two HISTORY snapshots a day apart (the day-by-day replay harness exists —
  `stm_replay_sim.yml` / the incremental-STM tooling). Numbers from prior measurement: 324 changed
  bills/typical day, 1,236 busiest (future_improvements Step 6) — row-level deltas will be of that order.

**Build:**
- New append-only tab `Change_Ledger` (in **VA·Ops** — user-readable via a gviz… ⚠ VA·Ops is auth-walled;
  the FRONTEND reads via gviz, so the tab must live in **VA·Live**. Put it in VA·Live; register it in the
  sustainability harness (`RETENTION_DAYS`) + add a retention prune mirroring `tools/witness_retention/`
  (90d), sharing the worker concurrency group.)
- Schema (13 cols max, mirror witness discipline):
  `DetectedAtUTC | Kind | Bill | Committee | DateKey | OldValue | NewValue | ContextAction | AgendaURL | RunID | Session | Spare1 | Spare2`
- Kinds (closed set, C1): `history_added` | `history_edited` | `schedule_time_moved` |
  `schedule_cancelled` | `docket_added` | `docket_removed` | `unclassified_change` (the fallback+canary).
- Emit sites: history differ (new) for the first two; witness-delta fold (existing signals) for the
  schedule two; docket differ for the docket two. Every emit ALSO increments a
  `ledger_deltas_<kind>` counter into SYSTEM_METRICS (denominator: `ledger_deltas_total`) — Standard #7.
- Golden tests: a pure differ function over two synthetic history snapshots (added / edited / removed /
  reordered / unchanged / malformed) — `test_change_ledger_differ.py`, added to `golden_tests.yml`.
- **No Sheet1 output change → no version bump** (state this in the PR body). Fail-open: any ledger-write
  error is a categorized WARN, never blocks the cycle (the ledger is additive telemetry, not the product's
  accuracy path).

### Phase L2 — the "Changes" tab (frontend)

- New nav tab **Changes** (`web/src/views/Changes.tsx` + `web/src/data/ledger.ts` reading the tab via the
  existing gviz helper pattern — copy `health.ts`/`calendar.ts` fetch discipline, timeout + parse guards).
- Render EXACTLY the v2 register: product feedrow anatomy (time · small-caps grey kind column · sentence),
  `drill-grouphdr` day headers, struck-old → bold-new, quiet italic "LIS revised this record", the
  "seen on your last visit" hairline (localStorage marker, C3), filter pills
  (All / Tracked bills / Record edits / Schedule) with counts (Hearst facet-count rule). Zero colored fills.
- Bill numbers open the card (reuse the App-level open handler); meeting rows link to the Calendar tab.
- Kind→sentence templates live in ONE map with a `default` branch rendering the generic row (C1).
- Empty state (off-season): "No changes since <marker> — the legislature is quiet." honest + designed.
- Browser-verify each state (rows, filters, marker divider, empty) before push; deploy-verify after merge.

### Phase L3 — polish (separate PR, after owner sees L2 live)
- "LIS revised this record" filter deep-link from Health; per-row "what changed" affordance on the bill
  card's history (the row that was edited gets a quiet marker). OWNER-GATED: show mockups first.

---

## TASK 2 — LIS-PARITY SENTINEL + THE DAYS-SINCE-INCIDENT COUNTER

**The owner's goal, verbatim anchor:** *"ensure my lobbyists see everything they could see on the state
legislative website"* — a flagged gap costs nearly as much as an unflagged error ([[ideas/lobbyist_jtbd_ideation]]
§8b). The claim expands from "never wrong" to **"never less than LIS."**

### Phase P1 — define + instrument the incident counter (do this first; small)
- **Incident definition (STRICT, owner-approved wording needed before anything public — OWNER-GATED for
  the public display, NOT for the instrumentation):** an incident is any of
  (i) wrong data visible on the product (accuracy sentinel failure / breaker bypass),
  (ii) a parity gap: content on LIS not visible here for > 1 worker cycle,
  (iii) a user-visible degraded state (stale banner / missing panel) lasting > 60 min.
- New small tab `Incident_Log` (VA·Live; append-only; columns: `StartUTC | EndUTC | Class | Summary |
  DetectedBy`). Writers: the accuracy sentinel, the completeness tripwire, the reconciliation job, and a
  manual entry path (documented) for owner-declared incidents.
- Health tab: a quiet "**N days since a data incident**" line derived from the log (and "—" until the
  owner blesses the definition; ship it Health-only first, trust-header later on owner sign-off).

### Phase P2 — the endpoint-inventory audit (closes the "what if it's on the site but not in our API" hole)
- Key fact: the LIS website is a SPA rendering from the same public API we consume (we sourced the key
  from their bundle — [[knowledge/lis_api_reference]] / [[knowledge/lis_dom_scraping]]).
- New tool `tools/parity/endpoint_audit.py` + weekly workflow: fetch the LIS SPA's JS bundle(s), extract
  API route strings (regex over quoted `/api/` paths + the service-base constants), diff against a
  DECLARED manifest of endpoints we consume (write the manifest as `tools/parity/consumed_endpoints.json`
  — enumerate from `calendar_worker.py`/`bill_tracker.py` fetch sites), and alert `DATA_ANOMALY/WARN` on
  any LIS endpoint not in the manifest and not in an acknowledged-ignore list (with reasons, e.g.
  member-photos). Bundle hash unchanged → skip (cheap). This converts unknown-unknowns into a list.
- Gates: runs read-only against static JS; zero LIS data-API load. Alert wording must tell a human exactly
  what appeared and where to triage.

### Phase P3 — sampled DOM parity checks (the catch-all)
- Weekly job renders N=10 random tracked-bill LIS pages + the schedule page headlessly
  ([[knowledge/lis_dom_scraping]] has the working approach), extracts visible history-row counts + meeting
  counts, and diffs against our data. Mismatch → `DATA_ANOMALY/CRITICAL` with the exact bill/page.
  LIS-safety: 11 fetches/week is negligible; still jitter them.
- P2+P3 findings feed the `Incident_Log` (class ii) automatically once stable.

---

## TASK 3 — WAR ROOM + SHARED WATCHLIST (scoping memo ONLY — owner decisions required)

Do NOT build. Produce a one-page decision memo (new page `docs/ideas/war_room_scoping.md`, linked from
[[state/current_status]] NEXT) covering, with a recommendation each:
1. **IA:** a new top-level "Ours" tab (recommended — it answers a question no current page does: *what is
   OUR org doing?*) vs a section inside Today. Cite the page-purpose analysis in [[ideas/lobbyist_jtbd_ideation]].
2. **Write path:** the site is static-assets on Cloudflare Workers — the natural write path is a tiny
   Worker API route + **D1** (or KV) for org state (watchlist, positions, whip marks). Alternative: a
   Google-Sheet write via Apps Script webhook (keeps everything in Sheets, weaker auth). Enumerate cost/
   auth/complexity for both; recommend Worker+D1.
3. **Identity:** none (per-browser, shared board unauthenticated-but-unlisted) vs name-pick (a dropdown
   "who are you" per device) vs real auth (Cloudflare Access for the org). Recommend name-pick MVP.
4. **MVP cut:** shared watchlist + per-bill org position (support/oppose/watch/amend) ONLY; whip board
   second; assignments third. The star UI's "for everyone" confirm copy (already shipped) anticipates this.
5. Open UX question the owner flagged: how position/involvement marking coexists with the star.

---

## TASK 4 — SMALL, INDEPENDENT ITEMS (each ≤ ½ session, any order)

- **4a. Witness docket-drop histogram** (the "10 PM" measurement debt, §8): `tools/parity/witness_histogram.py`
  reading `Schedule_Witness` (it lives in VA·Ops after auto-shard — gspread with the service account, like
  other tools/), bucket ADDED/CHANGED rows by ET hour-of-day for the Jan–Mar 2026 window, print the
  distribution + write it into [[ideas/lobbyist_jtbd_ideation]] §8 (replacing the flagged unmeasured claim).
- **4b. Crossed-over chip on Search filter labels** — verify no other senate-purple statuses exist
  (`grep -n "chip senate" web/src`) beyond the chamber chip itself; fix any stragglers (owner-locked rule).
- **4c. Ledger name check**: user-facing label is **Changes** everywhere; "ledger" is internal only.
- **4d. Artifacts hygiene**: the two mockup artifacts are the visual spec of record — do not redesign them;
  update only on owner request (same URLs).

## Priority order (owner can reorder)
1. TASK 0 (finish #219) → 2. TASK 1 L1 → 3. TASK 1 L2 → 4. TASK 2 P1 → 5. TASK 4a →
6. TASK 2 P2 → 7. TASK 3 memo → 8. TASK 2 P3 → 9. TASK 1 L3 (owner-gated).

See also: [[ideas/lobbyist_jtbd_ideation]] (the full ideation record), [[design/dashboard_and_visual_language]]
(the register pattern), [[state/current_status]].
