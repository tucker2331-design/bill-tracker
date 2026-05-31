---
tags: [log, meta]
updated: 2026-05-04
---

# Project Log

Append-only, reverse-chronological (newest at top). Each entry opens with `## [YYYY-MM-DD] <kind> | <title>` so `grep "^## \[" log.md | head -20` gives a parseable timeline.

**Kinds:** `ingest` (new source/doc processed), `pr` (PR opened/merged/closed), `decision` (architectural or workflow), `lint` (wiki health-check pass), `session` (notable multi-hour working block), `post-mortem` (failure analysis), `milestone` (project-goal threshold crossed).

---

## [2026-05-31] pr | PR-C7.0.6 — persist EventCode per event + fix EventID typo (prerequisite for PR-C7.1b)

Worker-only schema add to `LegEvent_Events`: new `EventCode` column (the structural action code `H4020`/`S5100`/`G7050` that PR-C7.1b's classifier will consume instead of substring text matching). Shipped as a small safe prerequisite ahead of the big classifier PR, so the persistent cache is already warm with EventCode by the time C7.1b lands.

Three defensive details (fragile-government-data mandate):
1. **EventCode OPTIONAL on read.** Old persisted rows predate the column; the load reads it via a separate `ei_eventcode = eh.index("EventCode") if "EventCode" in eh else -1` index, guarded by `0 <= ei_eventcode < row_len`, defaulting `""`. Adding it to the STRICT required-column set would raise `ValueError` on the one-cycle header transition and wipe the whole events cache. Split `LEGEVENT_EVENTS_REQUIRED_COLS` (the original 6) from `LEGEVENT_EVENTS_HEADER` (now 7).
2. **Grid widened before write.** The tab was created with 6 cols; persist now writes 7-wide rows. `_get_or_create_legevent_tabs` widens an existing narrow tab via `add_cols` (additive, idempotent, alert-wrapped) before persist, so `update` can't raise "exceeds grid limits".
3. **EventID typo fixed (closes [[state/open_anti_patterns#9]]).** Persist read `e.get("EventID")`, but raw API events (from hydration) carry `LegislationEventID`; reloaded events carry `EventID`. Now reads `LegislationEventID or EventID` to handle both dict shapes.

**Sequencing correction caught while scoping:** I almost shipped the floor_miss→LegEvent fallthrough alone. Caught the interaction first: `H5601`/`S5601` "Bill text as passed" rows match `"passed house"` → forced Floor → floor_miss; a standalone fallthrough would "recover" them with their 4 AM document-batch timestamp — a wrong time on a non-meeting row. The two PR-C7.1b parts are NOT independent (my earlier writeback was wrong about that): the floor fix is only safe AFTER EventCode classification pulls document/admin codes off the floor path. Hence C7.0.6 (this) → C7.1b (classification + floor fix together).

Hang-safety for the eventual floor_miss fallthrough verified ahead of time: floor_miss bills are in `legevent_candidate_bills` (line ~2905) and negative-cache-seeded (line ~2978), so the row loop never fetches regardless of origin — the PR-C3 hang vector (assumptions_audit #42/#47) stays closed. PR-C7's Codex P1 seeding covers all origins, not just journal_default.

Diff `+52/-4`, worker-only. Branch `claude/pr-c7-0-6-persist-eventcode`. Brain: arch doc schema table updated, open_anti_patterns #9 marked resolved, current_status sequencing section added.

---

## [2026-05-31] milestone | PR-C7.1d audit RAN — the months-old "what are the bugs" question is answered

The PR-C7.1d structural audit ran against 1049 flagged Section 9 rows (full window). **The count is two distinct populations, not one homogeneous pile** — the framing that had stalled every prior strategy discussion was wrong.

- **~942 (90%) false positives:** `H5601`/`S5601` "Bill text as passed House and Senate (HB####ER)" (842) + `G7210` "Governor's recommendation received" (100). Engrossed-text document records + executive receipts, NOT meetings. X-Ray's substring matcher flagged `"passed"`/`"recommendation"`. Confirmed via EventCode, not estimated.
- **~100 genuine meetings:** real floor votes + committee actions that legitimately lack a shown time.
- **LIS data quality:** 13,259 events, 0 null EventCodes / 0 null EventDates / 0 malformed / 0 failed. Clean for session 20261. The fragile-data concern is real for robustness-over-years but the structural fields are present and well-formed today.

**Diagnosis (owner directive: "stop with the menus, write the script, run it, tell me the exact mechanical reason"):** wrote `tools/c7_1d_structural_audit/diagnose_floor_gate.py`, ran it on live LIS. **105 of 299 real-timed events in a 12-bill sample are `ABSOLUTE_FLOOR_VERBS` floor votes AT RISK of the dead-end.** The chain: floor action → forced `event_location="Floor"` (line 3072) → convene-anchor path (3239) → convene **miss** → `origin="floor_miss"` (3259) → LegEvent block at 3289 gated on `journal_default` SKIPS it. LegEvent has the minute-precision time (e.g. `S6015` conference-report-agreed at `17:05:14`); the worker never asks. **Codex P2 fold-in:** the 105/299 is the *at-risk* population (floor votes that COULD dead-end), NOT the dropped count — the worker only drops the subset whose convene anchor is also missing. The authoritative dropped count is the audit's ~100 flagged genuine-meeting rows. The diagnostic proves the mechanism; the flagged set counts the drops. (My initial writeback conflated the two — a Standard #7 wrong-denominator error, now corrected.)

Full measurement + both lessons (audit-design: discriminating signal must be IN the class definition; the bug: recovery gated on one origin value excludes rows that need recovery) in [[failures/assumptions_audit#55]].

**PR-C7.1b is now scoped against data, not inference:** (1) X-Ray classifies by EventCode → 942 false positives reclassify administrative; (2) worker floor_miss → LegEvent fallthrough → recovers the genuine floor-vote residue. See [[state/current_status#Next: PR-C7.1b (data-backed, ready to scope)]].

Diagnostic + this writeback shipped on branch `claude/pr-c7-1d-floor-gate-diagnosis` (the PR-C7.1d audit branch #51 already merged; fresh branch from main per [[workflow/branching_rules]]).

---

## [2026-05-12] pr | PR-C7.1d — structural audit of Section 9 flagged rows (read-only) + Standard #3 sharpening

Owner directive: *"Fetch the LegEvent data for the flagged rows and categorize them into Class A, B, C, and D. Stop guessing and show me the actual measured breakdown."* Plus the fragile-data constraint: *"Government data is fragile. LIS frequently drops columns, changes headers, leaves fields null. Your structural logic must be highly defensive."*

**The reframe that unblocked this:** reading [[failures/pr22_post_mortem]] + the PR-C6.3 verb-dump back showed the ~150 "bugs" aren't 150 unresolved time gaps — they're 150 rows the **current X-Ray text-classifier flags**, ~80%+ false positives. We had never MEASURED the breakdown by structural cause. The whole "what do we do with the residue" debate was happening without data.

**The tool** (`tools/c7_1d_structural_audit/`):
- `categorize.py` — pure, testable. Classes by structural fact: **B** (matched meeting event WITH real time → recoverable, worker missed it), **C** (matched, no real time → genuine LIS gap), **D** (no LegEvent event for bill+date → likely clerical annotation), **E** (matched but EventCode null → FRAGILE DATA), **F** (bill fetch failed → indeterminate, retry — NOT conflated with D), **X** (malformed flagged row). Class A (false positive) read off the EventCode histogram, not hardcoded (no EventCode→category mapping exists yet; that's PR-C7.1b).
- `audit.py` — orchestrator. Replicates the X-Ray's exact flagging logic (same patterns as [[meeting_bug_triage|the triage tool]]); fetches LegEvent per distinct flagged bill (reuses PR-C7.1a's `FetchResult` enum + exponential backoff + 25-bill checkpoint); writes `C7_1d_RowVerdicts` / `C7_1d_DataQuality` / `C7_1d_Summary`.
- The `C7_1d_DataQuality` tab measures LIS structural fragility directly (null-EventCode %, null/malformed EventDate %, failed-bill count) — the evidence base for how defensive the eventual architecture must be.

**Self-caught defect before push:** initial version set `events_by_bill[failed_bill] = []`, which would have categorized failed-fetch rows as Class D (no event). That conflates "fetch failed" with "LIS has no event" — exactly the PR-C7.1a Codex P1 lesson (FAILED≠EMPTY). Fixed by tracking `failed_bills` as a separate set and assigning Class F. This is also Point 15 (Sentinel-Value Collision) — presence-of-failure tracked separately, not encoded by an empty list.

**Standard #3 sharpening folded in** (greenlit decision): *"Text parsing is forbidden on the lobbyist-facing path. Structural determinism is required, not preferred."* Plus the owner's hard guardrails captured in [[state/current_status]]: no LLM runtime dependency; no OpenStates fallback (their VA classifier is regex-on-text — the brittleness we're escaping); **no hiding rows from lobbyists, no probabilistic guesses** (owner rejected my hide-from-UI idea — the surface must be complete AND correct).

**Open question still open:** the residue-handling architecture (PR-C7.1b) is gated on this audit's measured class breakdown. We stopped guessing. The audit runs, returns the B/C/D/E/F split, and the architecture follows from the data.

**Bot review fold-in (Codex P2 + 4 Gemini, 2026-05-13):**
- **Codex P2 (high-impact, fixed):** matcher used `(bill, date)` only — same-day cross-chamber events would have classified the row as Class B (recoverable) when the production resolver correctly abstains. Fixed by mirroring `calendar_worker.py`'s resolver: chamber filter (from outcome's `H `/`S ` prefix, fallback to bill prefix) + token overlap (3+ letter alphabetic tokens, same as `_legislation_event_token_set`). Class B now means "production resolver would have recovered," Class C means "production resolver would refuse" (no real time OR zero overlap). Smoke test confirms: HB1 row with only Senate event correctly classifies as Class D, not Class B.
- **Gemini HIGH / Codex P2 (date validation, fixed):** `event_date_only("not-a-date")` returned `"not-a-dat"` (truthy), bypassing the malformed-counter and allowing prefix-based date-match. Added `_DATE_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}$")` validator. Now strict.
- **Gemini medium (midnight normalization, fixed):** `eventdate_has_real_time("2026-02-12T00:00:00.000Z")` would have returned True (exact-string compare missed fractional seconds + timezone). Switched to regex extraction of the `HH:MM:SS` prefix before midnight check.
- **Gemini medium (versions list check, fixed):** `versions[0]` on a non-list truthy value could TypeError. Added `isinstance(versions, list)` check.
- **Gemini medium (final-retry sleep, fixed):** the prior version slept after the last attempt before returning FAILED. Now skips sleep on the final attempt; wasted latency removed.

**Lesson codified:** [[workflow/bot_review_fold_in]] — the bot review process was implicit across the session's ~10 PRs but never written down. Owner flagged: *"we should have established process you know to follow in the brain that includes reviewing these implementing good and necessary changes and then re-auditing yourself because the reviewers will not review your response to their initial reviews."* New workflow page documents the loop. Linked from [[index]] and [[CLAUDE.md]] write-back routing table.

---

## [2026-05-11] pr | PR-C7.1a — derived-classifier math-proof audit (read-only)

Owner mandate: *"I do not trust 'good ideas' without mathematical proof... Define a strict mathematical threshold for 'Trust' (e.g., minimum Support Count to ignore typos, and maximum Entropy to avoid chaotic words). ... Give me the exact percentage of historical rows that pass the Trust Threshold versus the percentage that fail and route to the DLQ. If the DLQ rate is too high, this architecture is not sustainable. ... Consider processing power and don't lose progress on hourly/weekly limits."*

Strategic agreement landed in the prior message:
1. PR-D (static `lexicons/va.py`) is retired. The classifier becomes a **derived artifact** built from observed structural data, not a checked-in dictionary.
2. Audit-first sequencing: PR-C7.1a proves the math BEFORE PR-C7.0.6 (schema migration) and PR-C7.1b (the rewrite).
3. Alert semantics: novel **EventCode** appearing in LIS = CRITICAL alert (structural vocabulary expansion). Novel narrative phrase in HISTORY = silently absorbed by the classifier. Structural novelty alerts; narrative novelty absorbs.

**Structural finding while scoping PR-C7.1a:** the LIS LegislationEvent API returns **`EventCode`** per event (verified live 2026-05-11 against HB1: 30 events, every one has `EventCode` plus `LegislationEventTypeID`, `IsPassed`, `IsMapped`, `Sequence`). The worker NEVER extracts these — only takes `EventDate`, `ChamberCode`, `Description`. The persist code at `calendar_worker.py:1272` also has a wrong-field-name bug (reads `e.get("EventID", "")` but the API field is `LegislationEventID`); every persisted event row has an empty EventID column. Both findings logged: the structural ones inform PR-C7.0.6's schema; the EventID typo is parked in [[state/open_anti_patterns#9]].

**Audit method:**
1. Deterministic sample of 100 bills from HISTORY.CSV (seed 20260511 for reproducibility).
2. Two-step LIS fetch per bill (~200 API calls total). Checkpoints every 10 bills to `Sheet1!C7_1a_RawCorpus` so a mid-process interruption loses at most one batch.
3. Build training corpus of (Description, EventCode) pairs. Bill-level 80/20 split (training/validation) to prevent leakage.
4. **Token trust math:** `TRUSTED(t) ⟺ support(t) ≥ MIN_SUPPORT ∧ H(EventCode | t) ≤ MAX_ENTROPY` where `H` is the per-token entropy of the EventCode distribution in bits. Headline: `MIN_SUPPORT = 10`, `MAX_ENTROPY = 1.0 bits`.
5. **Row trust math:** `ROW_TRUSTED ⟺ trusted_tokens_count ≥ 2 ∧ top_votes ≥ 2 ∧ margin ≥ 1` (votes are token-level argmax-EventCode majority).
6. Score the FULL HISTORY.CSV corpus (~65,169 rows). Report exact PASS / DLQ percentages.
7. Validate on the held-out 20%: precision on rows the classifier was willing to classify.
8. Sweep over a 4×4 grid of (MIN_SUPPORT ∈ {5, 10, 20, 50}, MAX_ENTROPY ∈ {0.5, 1.0, 1.5, 2.0}) for the Pareto frontier.
9. Write four tabs: `C7_1a_RawCorpus` (checkpoint), `C7_1a_TokenStats` (per-token signal table), `C7_1a_DLQ_Samples` (50 examples for human inspection), `C7_1a_Summary` (headline numbers + sweep JSON).

**Processing-power minimization:**
- LIS calls: ~200 total (2 per bill × 100 bills). Well under any rate limit; retries with exponential backoff for transient 429s.
- Sheets API: 1 read for checkpoint + 4 writes (one per output tab) + N append_rows for the checkpoint batches. Well under 60 reads/min, 60 writes/min limits.
- CPU: tokenize + dict-build + score. Total wall-clock ~5 min on the first run, <30s on a checkpoint-resume run.
- Workflow timeout: 30 min (generous; allows recovery if a single run goes long).
- **Idempotent:** re-running with the same seed picks the same sample; the checkpoint tab skips already-fetched bills; the math phases are pure and reproducible.

**Path forward (gate on audit results):**
- If headline PASS rate ≥ ~95% AND validation precision ≥ ~95%: proceed to PR-C7.0.6 (schema migration to persist `EventCode` per event) + PR-C7.1b (the rewrite). Static MEETING_ACTION_PATTERNS / ADMINISTRATIVE_PATTERNS / ADMIN_OVERRIDE_PATTERNS deleted.
- If headline numbers are weaker: revisit thresholds, possibly add bigrams to the tokenizer, or escalate the sweep. Document the decision in [[failures/assumptions_audit]] regardless of outcome.

**Pre-push audit walk (the 15-point version is now canonical via PR #46):** module docstring `tools/c7_1a_audit/audit.py` walks all 15 points explicitly. Point 14 (Threshold Calibration) called out: MIN_SUPPORT / MAX_ENTROPY are audit-internal parameters with a published sweep grid, NOT production breaker thresholds. Point 15 (Sentinel-Value Collision) called out: DLQ reasons are explicit string constants from `trust_math.py`, not encoded by sentinel values.

**Bot review fold-in + owner correction on sample size (commit `69c9015`):**
- **Owner P0 — sample size correction:** the original `SAMPLE_BILLS=100` was a grave mistake. At `MIN_SUPPORT=10`, ~3k events (100 bills × ~30 events) doesn't cover the EventCode alphabet — many real codes get filtered as "rare" and the math doesn't prove anything. Raised to 10,000 (effectively "all" — bounded by the distinct-bill universe of ~3,645). Workflow timeout bumped 30 min → 360 min (GH Actions max) for the ~60-120 min wall-clock first run. Checkpointing every 25 bills keeps any restart cost bounded. **Lesson:** when designing a statistical proof, the corpus must exceed the support threshold by enough margin that the proof is meaningful. A sample whose expected per-class support is below the trust threshold is, by construction, a proof that the threshold filters everything out.
- **Codex P1 — failed fetches were silently checkpointed:** `fetch_legislation_events_for_bill` returned `[]` for BOTH transient API failures AND confirmed-empty bills. The checkpoint treated both as "fetched empty" and skipped them permanently on rerun, biasing the corpus + PASS/DLQ percentages. Fix: `FetchResult` enum (`OK` / `EMPTY` / `FAILED`). Failed bills are NOT checkpointed (natural retry on next workflow run); confirmed-empty bills get a sentinel row with `EventCode = "_CONFIRMED_EMPTY_"` so resume doesn't refetch them. Failed bills surfaced in summary + stdout. **Same root class as [[failures/assumptions_audit#53]]'s Codex P2 fold-in (sentinel-value collision):** encoding "transient failure" with the same shape as "confirmed result" silently merges two distinct states. Track outcome explicitly via enum, not by absence-of-data.
- **Gemini HIGH (×2) — strict `bill_id` column lookup:** production HISTORY.CSV uses `BillNumber`. Substring match (`"bill" in c.lower()`) at both sites, with explicit `RuntimeError` if absent. Mirrors `calendar_worker.py:2669` pattern.
- **Gemini MEDIUM — whitespace in CSV column names:** added `df.columns = df.columns.str.strip()` after `pd.read_csv`. Mirrors `calendar_worker.py:1340`.
- **Gemini MEDIUM — backoff was linear, comment said exponential:** changed `LIS_RETRY_BACKOFF_S * (attempt + 1)` (linear) to `LIS_RETRY_BACKOFF_S * (2 ** attempt)` (true exponential). Comment and code now agree.

- **Post-merge first-run failure (2026-05-11 17:44Z) — hotfix PR #48:** the workflow crashed at `client.open_by_key(GSHEET_ID)` with `gspread.exceptions.SpreadsheetNotFound: 404`. Root cause: I had fabricated `GSHEET_ID = "1msUW9wq6OavWmw_..."` instead of grep'ing for the canonical value used everywhere else. Production `SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_..."` lives in `calendar_worker.py:25` and in every sibling audit tool's source. Fix: rename `GSHEET_ID` → `SPREADSHEET_ID` (matches sibling-tool convention), use the correct literal. **Lesson:** when adding a tool that mirrors an existing tool's auth pattern, copy the constants from the sibling, don't re-derive them. This is the config-level analogue of the function-scope rule (a single value used in multiple places lives at one source of truth, not multiple). Did not warrant a new assumptions_audit entry — the practice is already covered by Standard #5 (Dynamic Configuration) and Standard #7 (No Vibe Coding); my mistake was the failure mode, not a novel pattern.
- **Gemini MEDIUM fold-in on the hotfix PR:** the post-mortem note was a paragraph; surrounding entries are bullet points. Reformatted for consistency. **Self-audit reflection:** Point 3 (Doc Version Sync) of the 15-point audit covers "stale version references" but doesn't explicitly cover "formatting consistency within the same section." The lesson is the next layer of Point 3: when adding a new entry to a structured doc, walk up one line and check it matches the surrounding format. Could be Point 16 if another instance surfaces, but a single formatting nit doesn't justify a new canonical audit point.
- **Post-merge second-run buffering blindness (2026-05-11 ~17:55Z) — hotfix PR #49:** the audit workflow ran for 3+ minutes producing zero stdout in the Actions log past the env block. Symptom looked like a hang; actual cause was Python block-buffering stdout when piped to GitHub Actions' log capture (no TTY). With our ~100-byte log lines a 4KB buffer hides 5+ minutes of progress. Fix in the workflow's `env:` block: `PYTHONUNBUFFERED: "1"` (YAML mapping syntax) + `python -u` flag on the `run:` invocation (belt + suspenders). **Broader observation (not yet canonized):** every other audit workflow in `.github/workflows/*.yml` has the same latent issue (none use `-u` or `PYTHONUNBUFFERED`). They work fine TODAY because they're short (<60 sec) — the buffer never fills before the process exits. PR-C7.1a is the first long-running audit; that's why this surfaced now. **Decision:** scope the fix to `c7_1a_audit.yml` only (one-PR-one-purpose). The broader fix is a tiny bulk-PR for a future date OR opportunistically when another long-running tool gets added. **Why not canonize as Point 16:** the buffering issue is a CI-runner-specific runtime observability concern, not a code/data integrity issue. Adding "always use python -u in workflows" would inflate the audit with platform-specific hygiene. Belongs in `docs/workflow/` as a per-tool checklist if it recurs.
- **Gemini MEDIUM fold-in on the buffering PR (#49):** the prior bullet wrote `PYTHONUNBUFFERED=1` (shell syntax). The actual workflow YAML uses `PYTHONUNBUFFERED: "1"` (mapping syntax with quoted string value). A future maintainer copy-pasting from the log entry into a YAML file would write the wrong format. Doc now matches implementation exactly. **Self-audit reflection:** this is the third Gemini-medium consistency catch in a row (paragraph-vs-bullet, then shell-vs-yaml-syntax). Pattern: when the brain documents a fix, the description must be precisely copy-paste compatible with the implementation, including syntax-environment markers (shell vs YAML vs Python). Point 3 (Doc Version Sync) covers this implicitly — the "version reference" doesn't have to be a numeric version; it can be any technical literal whose exact form matters. **Process tightening:** when writing fix-description bullets, paste the exact code form, then narrate around it. Don't translate code shape into prose shape.

---

## [2026-05-11] decision | Codify Points 10-15 of the pre-push audit (PR-C7.0.5)

Owner directive: *"we must formalize our operational learnings before writing new code. Technical debt in our prompt instructions (CLAUDE.md) is just as dangerous as technical debt in our Python scripts."*

The PR-C7 work block surfaced six distinct bug classes that the existing 9-point pre-push audit could not have caught — none of them were diff-shaped failures (where the new code is wrong). All six were **interaction failures** between new code and pre-existing code paths / variables / thresholds. Each had been logged as a forward-looking "Audit upgrade: add Point X" note in the corresponding [[failures/assumptions_audit]] entry. The lessons were written down, but the practice had not formally changed. PR-C7.0.5 closes that loop.

**Audit-point backlog → canonical:**

| # | Point | Source | Bug class |
|---|---|---|---|
| 10 | Function-Scope Shadow Check | [[failures/assumptions_audit#50]] | Local `from X import Y` shadows module-level `Y` for the entire function (Python local-binding rule). Surface symptom: `UnboundLocalError` at runtime, invisible to `py_compile`. |
| 11 | Side-Effect Gating Check | [[failures/assumptions_audit#51]] | State-carrying side effect gated on a check that can be permanently true → Groundhog Day deadlock. Gemini fold-in: applies to *every* enclosing `if`, not just the most-obvious one. |
| 12 | Fallback Liveness Check | [[failures/assumptions_audit#52]] | `try X, fallback Y` where X has been dead for >24h. Cycle-stable WARN is not a transient. |
| 13 | Dead-Path Resurrection Check | [[failures/assumptions_audit#52]] (Codex fold-in) | Removing dead code resurrects previously-dead error paths. Variables bound only on the removed path become unbound on the survivor. |
| 14 | Threshold Calibration Check | [[failures/assumptions_audit#53]] | Absolute thresholds anchored to a current-state baseline silently go stale when an architectural change shifts the metric's floor. Prefer delta-vs-rolling-baseline. |
| 15 | Sentinel-Value Collision Check | [[failures/assumptions_audit#53]] (Codex P2 fold-in) | Encoding "absent" by a sentinel value that's also a legitimate runtime value. Track presence separately (boolean flag, `Optional[T]`, etc.). |

**Locations updated:**
- [[CLAUDE.md]] (project root): header `(9 points)` → `(15 points)`; appended 6 new one-line entries with cross-references.
- [[workflow/three_phase_protocol]] (authoritative full version): Phase 2 section updated with 6 new entries including worked examples and cross-references.
- `assumptions_audit.md` entries #50-#53 unchanged — the historical forward-looking notes ("Audit upgrade: add Point X") stand as the justification record. The cross-reference now flows in both directions (audit point → entry, entry → audit point).

**What this is NOT:** the audit-point codification does NOT replace per-PR code review or bot review. It's a checklist for the *push author* to walk before commit, in the same role as the original 9 points. Bot review (Codex P1/P2, Gemini critical/high/medium) continues to be treated as a real signal — most of the entries #50-#53 were caught by bot review, which is itself the strongest evidence that even a 15-point self-audit is insufficient without independent eyes.

**Process note for the next active block (PR-C7.1):** these 6 new points are now active. Any PR opened post-codification is expected to walk all 15. The X-Ray classifier rewrite (PR-C7.1) is the immediate test case — it touches the row pipeline (Point 5), introduces a new Sheet1 column (Point 14: threshold-watched metrics will move), modifies `pages/ray2.py` (Point 4: keep `calendar_xray.py` in sync), and changes the metric definition (Point 14 explicitly).

**Codex P2 fold-in on PR #46:** Codex caught that [[README|docs/README.md]] (the vault entry page that maintainers see first) still said *"Phase 2 — Pre-push audit: run the 9-point checklist before every commit."* This is exactly the Doc Version Sync failure (Point 3) the audit itself is supposed to prevent — and it's a CRITICAL drift point for a vault-entry page because a new agent reading the vault gets stale instructions before ever reaching the authoritative `three_phase_protocol`. Fix: flip to *"the 15-point checklist ... originally 9 points; expanded to 15 in PR-C7.0.5"* with a wikilink to the canonical list. Other matches for the grep `9-point|9 points` (8 hits in `log.md`, 1 in `state/current_status.md`) are intentionally past-tense historical citations inside dated log entries — they correctly describe the audit AS IT WAS at the time of the entry, and stand as historical record. **Lesson:** when codifying anything that's referenced from a "first-page-opened" doc (README, CLAUDE.md, etc.), grep for ALL references — the entry point matters more than internal pages because it's the only one guaranteed to be read on every session start.

---

## [2026-05-08] pr | PR-C7.0.4 breaker recalibration — Sheet1 frozen 3+ days, owner directive to unfreeze

Owner directive: *"stale data is unacceptable in a live tracking environment."*

**Symptom:** Sheet1 has been frozen at `2026-05-04T23:47:03Z` for ~3+ days. Worker process is healthy every cycle, but the PR-C1 mass-violation circuit breaker has been tripping on `meeting_unsourced >= 50` every cycle since the cold-start completed. Latest cycle (run `25531131454` on `9214010`, 2026-05-08T01:32:22Z) shows the architecture is fully steady-state: `loaded=3645 bills`, `tiers A/B/C=0/6/1641`, all bills cached. But `meeting_unsourced=150` is the steady-state floor (X-Ray classifier false positives — `Governor's Recommendation` matching the `recommend` substring, etc.), and the threshold of 50 was set against a pre-PR-C7 baseline of ~9.

**The breaker was technically working as specified.** The specification was wrong because the threshold was anchored to a transient value, not a structural property. PR-C7 changed the input distribution (every `journal_default` row gets a LegEvent attempt; recoverable rows drop out, non-recoverable rows stay) and revealed that the PR-C1 absolute threshold encoded an implicit baseline that PR-C7 invalidated.

**Decision:** since stale UI is unacceptable AND the structural fix for the 150 floor (PR-C7.1's classifier rewrite) is days away, recalibrate the breaker now. Replace `CIRCUIT_MAX_MEETING_UNSOURCED = 50` (absolute) with **`CIRCUIT_MAX_MEETING_UNSOURCED_DELTA = 25`** (regression vs `Sheet1!Y2` rolling baseline) plus **`CIRCUIT_MAX_MEETING_UNSOURCED_ABS = 500`** (catastrophic absolute floor). New state cell `Y2` stores last-known-good `meeting_unsourced`, written on every successful Sheet1 overwrite. Delta = `max(0, current - prior)` — improvements never trip; PR-C7.1 ratchets Y2 down automatically when it lands.

**Behavior matrix:**
- Steady state at 150: delta=0 → breaker passes → Sheet1 unfreezes
- Real regression spike (e.g., 150 → 200): delta=50 > 25 → breaker trips
- PR-C7.1 lands, drops to 30: passes, Y2 ratchets to 30, new floor tracked
- Catastrophic (e.g., 600): absolute floor 500 still trips
- First cycle post-deploy with Y2 empty: delta-check inactive, floor handles edge cases

**Brain writeback:** [[failures/assumptions_audit#53]] captures the lesson — *threshold values that anchor to a current-state baseline are time-bombs* — with proposed **Point 14 audit upgrade** (*Threshold Calibration Check*: when a PR's diff is architecturally significant, grep every existing threshold against the new steady-state and flag any that would now trip on healthy operation). Cross-references #48 (the diagnostic shape: "metric definition silently changed") and inverts it into the action shape ("threshold definition silently went stale").

**PR #45:** https://github.com/tucker2331-design/bill-tracker/pull/45. Initial diff `+104/-15`. Awaiting owner merge. Once merged: next cycle establishes Y2 baseline at ~150, Sheet1 unfreezes, gap_minutes drops from ~4400 back toward steady state. Then the next active block is PR-C7.1.

**Codex P2 fold-in (commit `af4aa7e`):** the initial activation logic keyed delta-check active on `last_known_good_meeting_unsourced > 0`. Codex caught that this silently conflates "Y2 absent / unreadable / malformed" with "Y2 = 0 (a legitimate post-PR-C7.1 baseline once the classifier fix drives meeting_unsourced to 0)." Future regression vector: when PR-C7.1 ships, Y2 = "0" gets written; next cycle reads Y2=0 and turns OFF the delta-check; a regression from 0 → 26..500 then bypasses the >25 delta threshold AND the 500 absolute floor (because 26..500 < 500), gets accepted, and Y2 ratchets up to that regressed value. The breaker would adapt to a regression instead of catching it. **Fix:** track baseline **presence** as a separate `y2_baseline_present` boolean (default False, True ONLY on successful read + non-empty value + successful int parse). Activation keys on the presence flag, not the value. **Lesson generalization** added to [[failures/assumptions_audit#53]]: **never encode "absence of a value" by a sentinel value of that same type.** Proposed **Point 15 audit upgrade** — *Sentinel-Value Collision Check.* Same root class as the Optional/Maybe-type-confusion bugs that bite many languages. Total PR diff: `+129/-24` across 2 code commits.

---

## [2026-05-06] pr | PR-C7.0.3 dead-alias hotfix — `blob.lis.virginia.gov` NXDOMAIN diagnostic

Owner asked whether the persistent `⚠️ CSV fetch failed for https://blob.lis.virginia.gov/lisfiles/20261/HISTORY.CSV: ... NameResolutionError ... Errno -2` warning (firing every cycle since at least 2026-05-04) was state-wide LIS infrastructure failure or LIS punishing us for the high-volume PR-C7 cold-start testing.

**Diagnostic:** `nslookup` from a different ISP than the GitHub Actions runners returned NXDOMAIN for `blob.lis.virginia.gov` — universal, not GHA-specific, not rate-limit-shaped. Meanwhile `lis.virginia.gov` resolved normally (`20.110.235.203`) and canonical `lis.blob.core.windows.net` served HTTP 200 with 4.7 MB / 65,170 lines of HISTORY.CSV — matching exactly the worker's `processed=65169` per cycle, confirming the silent-fallback at `calendar_worker.py:2569-2570` had been masking the dead alias by always succeeding on the canonical retry. Other LIS endpoints we hammer much harder (Session API, LegislationEvent at 500 fetches/cycle for hydration, DOCKET.CSV from `lis.blob.core.windows.net`) all healthy.

**Conclusion:** dead CNAME alias, not targeted blocking. LIS removed the `blob.lis.virginia.gov` CNAME at some unknown date; the worker's WARN log line had been the only externally-visible signal but its structure made it look like a transient fetch failure rather than a permanent dead URL.

**Fix (PR-C7.0.3, branch `claude/pr-c7-0-3-drop-dead-blob-alias`):** drop the dead alias from the worker entirely, use canonical `lis.blob.core.windows.net` only. Replace silent-empty-DataFrame fallback with a CRITICAL `push_system_alert` if HISTORY.CSV ever returns empty — aligns with [[workflow/source_miss_visibility]] (no silent failure on a source miss).

**[[failures/assumptions_audit#52]]** captures the lesson: a `try-then-fallback` pattern that succeeds on the fallback every time is observability debt, not resilience. Audit upgrade proposed: Point 12 — *Fallback Liveness Check.* Process upgrade: a WARN appearing in N consecutive cycles is a CRITICAL pending investigation; cycle-stable WARNs are not transient by definition.

**Brain updates:** [[knowledge/lis_api_reference]] flipped to mark `blob.lis.virginia.gov` as ⚠️ DEAD (Do Not Use); HISTORY.CSV row count updated from 60,694 baseline to current 65,169 + 1 header.

**Codex P1 fold-in (post-push):** dropping the dead-alias fallback newly exposed a dormant `UnboundLocalError` — `legevent_bills_meta / legevent_bills_ws / legevent_events_ws` were initialized inside `if not df_past.empty:`, so a real empty df_past would crash the unconditional persist call (PR-C7.0.2 placement) before the new CRITICAL alert could land in Sheet1. Same bug class as [[failures/assumptions_audit#50]] but a different root cause: **conditional binding on a previously-unreachable path** rather than Python's local-binding rule. Before PR-C7.0.3, the silent fallback to canonical always succeeded, so the never-bound path was effectively dead code. **Removing dead code can resurrect previously-dead error paths.** Fix folded into the same PR: hoist the LegEvent INIT block (load + counters, df_past-independent) to function-scope before the `if not df_past.empty:` check. Hydration stays inside the block. **[[failures/assumptions_audit#52]]** updated with the fold-in subsection and a new audit upgrade — **Point 13: Dead-Path Resurrection Check.** When dropping a fallback or simplifying a defensive pattern, grep every function-scope variable that was bound only on the path being removed; confirm each is either re-bound unconditionally or no longer referenced downstream.

---

## [2026-05-06] milestone | PR-C7 architecture validated — out of Groundhog Day, cold-start draining

Cycle 2 of post-PR#43 confirmed the persistent LegEvent cache works as designed.

| Metric | Cycle 1 (post-#43) | Cycle 2 | Δ |
|---|---|---|---|
| `loaded` from persistent cache | 0 | 500 | +500 ← **persist round-tripped** |
| Tier A (uncached) | 3,645 | 3,145 | −500 |
| `skipped(terminal/fresh)` | 0/0 | 0/500 | The 500 loaded are within TTL → treated as fresh, no re-fetch |
| `queued_overflow` | 3,145 | 2,645 | −500 |
| `unsourced_journal` | 6,235 | 6,158 | −77 |
| `meeting_unsourced` | 150 | 144 | −6 |

Drain projection: ~7 more cycles to fully drain Tier A. Breaker clears when `meeting_unsourced < 50` — currently ~6/cycle drop, likely accelerates as the 500/cycle hydration hits the bills that actually have unsourced meeting actions. Once breaker clears, Sheet1 overwrite resumes, Y1 advances, gap closes from 1039 min back to ~15 min steady state. Post-drain quantification of the X-Ray Section 9 real-bug residue (vs the ~80% classifier-false-positive mass) lands when `meeting_unsourced` stabilizes.

Two things deferred until queue=0: (1) sizing-variance audit entry — PR-C6.4 sized the cold-start at 2,002 bills, reality is 3,645 (~82% larger); will be assumptions_audit #53 with real cycle counts; (2) post-PR-C7 baseline capture in [[testing/crossover_week_baseline]].

---

## [2026-05-05] pr | PR-C7.0.1 merged → 12 cycles of Groundhog Day → PR-C7.0.2 hotfix (PR #43)

PR #42 (PR-C7.0.1) merged at `2512a96` 2026-05-05T00:16:15Z. Cycle 1 worked structurally — queue identified 3,645 uncached bills (vs PR-C6.4's 2,002 estimate; ~82% larger surface, sizing-variance entry deferred until queue drains), 500 hydrated, 3,145 negative-cache seeded, row loop strictly cache-lookup-only (the Codex P1 / Gemini critical fix held). But the breaker tripped at `meeting_unsourced=150` (the 3,145 unhydrated bills had unsourced meeting actions). Sheet1 overwrite refused, state cell Y1 frozen at pre-PR-C7 `2026-05-04T23:47:03Z`.

**Then 12 cycles ran identically over ~16 hours.** Same gap (877.8 min), same tier counts (A/B/C=3,645/0/0), same overflow (3,145), same hydration (500 — same 500 bills every cycle), same breaker trip. Each cycle's GitHub Actions run was green. The worker was achieving 0% structural progress while reporting 100% individual-cycle success.

**Root cause:** `_persist_legevent_cache(...)` lived inside the `else` branch of `if _breaker_tripped:` at `calendar_worker.py:3597`. Breaker trips → persist skipped → next cycle reloads zero → re-hydrate same 500 → re-trip → loop. Same bug class as PR #41's Codex P1 / Gemini critical row-loop finding ("side effect on the wrong side of a check that doesn't fire on the test path") — caught on the row-loop face, missed on the persist face.

**Fix:** PR #43 hoists `_persist_legevent_cache(...)` to before the `if _breaker_tripped:` check. Persist runs unconditionally; Sheet1 overwrite remains gated on the breaker. Branch `claude/pr-c7-0-2-persist-before-breaker` commit `7493d45`. Diff: `+18/-13`.

**[[failures/assumptions_audit#51|assumptions_audit #51]]** captures the lesson: idempotent state-carrying side effects must not be gated on a check that can permanently prevent them. Audit upgrades proposed: Point 11 (Side-Effect Gating Check) + dry-run with breaker artificially tripped + monitor-as-bug-signal for counters that should be moving but aren't.

**PR #43:** https://github.com/tucker2331-design/bill-tracker/pull/43 — Gemini medium review (commit `b0f3998`) caught that the initial fix at `7493d45` hoisted persist out of the `else: _breaker_tripped` branch but **left it inside two enclosing `if not final_df.empty:` checks** AND after `sheet_data` was finalized. Two real issues: (1) empty `final_df` would recreate the deadlock with a different gate (same bug class as #51, different precondition); (2) persist-failure alerts wouldn't reach this cycle's Sheet1 because they'd land in `alert_rows` after the fold into `filtered_events`. Final placement is function-scope at ~line 3340, just before the source-miss metrics block. **Lesson generalization** added to [[failures/assumptions_audit#51]]: "must not be gated on a check that can permanently prevent them" applies to **every** enclosing check, not just the most-obvious one. Treating bot review as a real signal paid off again. Awaiting owner merge.

---

## [2026-05-05] pr | PR-C7 merged → first cold-start cycle bricked → PR-C7.0.1 hotfix opened (PR #42)

PR #41 (PR-C7) merged at `c917d6de` 2026-05-05T00:01:55Z. The very next scheduled cycle (run [25350329090](https://github.com/tucker2331-design/bill-tracker/actions/runs/25350329090), `workflow_dispatch` at 00:02:24Z, ~30s after merge) failed with:

```
UnboundLocalError: local variable 'timezone' referenced before assignment
File "calendar_worker.py", line 1893, in run_calendar_update
    _cycle_start_utc = datetime.now(timezone.utc)
```

**Root cause:** PR-C7 added a redundant `from datetime import timezone` at `calendar_worker.py:2793` inside the LegEvent recovery block of `run_calendar_update()`. Python's scoping rule made `timezone` local-to-function for the entire body — references at lines 1893 and 1906 (which had previously resolved to the module-level import at line 12) raised `UnboundLocalError` before the local import had executed.

**Fix:** one-line deletion at `calendar_worker.py:2793`. Branch `claude/quizzical-euler-b32824` commit `efe1a90`. Worktree-isolated branch (per [[workflow/branching_rules]] — PR #41 is closed/merged so its branch is dead; new work branches from main).

**[[failures/assumptions_audit#50|assumptions_audit #50]]** captures the lesson: function-scope import shadowing bypasses parse-clean checks and the 9-point pre-push audit. Process upgrade proposed: add Point 10 (Function-Scope Shadow Check) and a 60-second `IS_DRY_RUN=true` pre-merge dry-run for any diff that touches `calendar_worker.py:run_calendar_update`.

**PR #42:** https://github.com/tucker2331-design/bill-tracker/pull/42 — awaiting bot review + owner merge. Once merged, the next 15-min cycle becomes cold-start cycle 1 (the cold-start clock the handoff anticipated effectively *did not start* at 00:01:55Z; it starts when PR #42 lands).

---

## [2026-05-04] pr | PR-C7 review fixes — Codex P1 + Gemini critical/high/medium/medium

Branch `claude/pr-c7-legevent-persistent-cache` commit `45c72b5`. Four findings on the PR-C7 initial commit, all real, all addressed:

1. **Codex P1 + Gemini CRITICAL (same issue, both bots agreed):** the row loop called `_resolve_via_legislation_event_api` unconditionally on every `journal_default` row. For Tier A overflow bills (cold-start cycles 1-4, ~1,500 bills/cycle queued for next cycle), the cache key was absent → resolver fell into its network-fetch path, bypassing `LEGEVENT_FETCHES_PER_CYCLE` and recreating the [[failures/assumptions_audit#42|PR-C3 hang vector]]. Fix: seed both `_legislation_id_cache[(bill, session)] = ""` and `_legislation_event_cache[(bill, session)] = []` for every candidate bill that did NOT make the queue. The resolver short-circuits cleanly via existing PR-C3.1 cache checks. Row loop is now strictly cache-lookup-only regardless of which tier a bill is in. New telemetry `legevent_overflow_no_fetch` tracks the seed count.
2. **Gemini HIGH:** initial worksheet rows undersized (1,000 vs 2,002 cold-start surface). `update(range_name="A{N}")` raises when N > allocated rows. Fix: 3,000 rows for `LegEvent_Bills`, 25,000 for `LegEvent_Events`. ~170k cells total — small fraction of post-PR-C6.2 ~7M-cell workbook headroom.
3. **Gemini MEDIUM:** `_persist_legevent_cache` did `clear() then update()`, leaving the sheet temporarily empty during chunked writes. Mid-write crash → cache destroyed. Fix: write-then-clear-trailing pattern. Old rows are preserved during the write phase; trailing clear at the end removes stale rows beyond the new tail. Mid-write crash now leaves OLD data intact for unwritten rows.
4. **Gemini MEDIUM:** `_is_terminal_legevent_description` substring match assumed pre-lowercased patterns. Fix: lowercase patterns at check time (`p.lower() in lower`). Forward-looking — constant is currently empty `()`, but a future maintainer can populate with natural casing without silent match failures.

New entries appended to [[failures/assumptions_audit]]: #47 (queue-with-cap requires explicit overflow handling), #48 (when a metric jumps at scale, sample-verify the metric's definition before scoping a fix), #49 (gspread default 26-col grid → silent over-allocation; check dimensions before persist).

Awaiting bot re-review on `45c72b5`. Once clean → merge → first cold-start cycle.

---

## [2026-05-03] decision | Owner rejects New-Verb Canary; mandates structural classifier pivot for PR-C7

After PR-C6.3's verb-dump returned 994 "meeting bugs" with the dominant mass being **X-Ray classifier false positives** (admin actions like `Governor's Recommendation` matching the substring `"recommend"` in `MEETING_ACTION_PATTERNS`), I proposed two paths:
- **Strategic prevention idea (rejected):** "New-Verb Canary" — startup scan for unknown verbs, alert per new verb. Owner rejected as a band-aid: even with cycle-1 visibility, the response is a human writing code to add the verb to a hardcoded list. Doesn't scale to 50 states or to vocabulary drift within VA.
- **Structural pivot (approved):** drop the `MEETING_VERB_TOKENS` gate at `calendar_worker.py:2593` and use the LIS LegislationEvent API as the source of truth. With a cross-cycle persistent cache, every `journal_default` row gets a chance at recovery. The 50-state plan: each new state plugs in a structural-event adapter normalized to `(bill, date, chamber, action_type)`.

Owner mandates locked:
- **TTL safety net: 6 hours** (`LEGEVENT_TTL_SECONDS = 21600`)
- **Per-cycle fetch cap: 500** (`LEGEVENT_FETCHES_PER_CYCLE = 500`)
- **Cold-start strategy: EXPLICIT** (rejected my "organic" recommendation): Tier A (uncached) drains FIRST before Tier B (hash-changed) and Tier C (TTL-expired). User reasoning: "An 'Organic' blend risks exhausting the WAF budget on TTL-expirations while bills with zero cached data are starved."
- Live-readiness signal: SHA256 of sorted `(date, outcome, refid)` HISTORY rows per bill. Clerk edit → hash changes → cache refresh in next cycle.
- Terminal short-circuit infrastructure: `TERMINAL_DESCRIPTION_PATTERNS` — empty initially pending real API observation.

`docs/ideas/future_improvements.md` updated to mark "New-Verb Canary" REJECTED with rationale preserved (audit trail) and add "Structural classifier as source of truth" with full implementation plan.

---

## [2026-05-03] pr | PR-C7 opened (PR #41) — drop verb gate + cross-cycle persistent LegEvent cache

Branch `claude/pr-c7-legevent-persistent-cache` commit `70f14f8`. Implementation:

- New constants: `LEGEVENT_BILLS_TAB`, `LEGEVENT_EVENTS_TAB`, `LEGEVENT_TTL_SECONDS = 21600`, `LEGEVENT_FETCHES_PER_CYCLE = 500`, `TERMINAL_DESCRIPTION_PATTERNS = ()`.
- New helpers: `_hash_history_rows_for_bill`, `_is_terminal_legevent_description`, `_get_or_create_legevent_tabs`, `_load_legevent_cache`, `_build_legevent_refresh_queue` (Tier A → B → C with cap), `_hydrate_legevent_cache`, `_persist_legevent_cache`.
- Worker integration: pre-iteration cache load + hash compute + tier + hydrate; row loop drops verb gate; pre-Sheet1-write persists cache.
- 11 new telemetry counters in `source_miss_counts` (orthogonal to bucket math): `legevent_cache_loaded_bills/events`, `legevent_tier_a/b/c`, `legevent_skipped_terminal/fresh`, `legevent_fetched_this_cycle`, `legevent_hydration_queued`, `legevent_cache_hits/misses`.
- Diff: 558 ins / 15 del to `calendar_worker.py`.
- Local sanity: hash determinism + order-independence, terminal pattern empty/populated paths, Tier A→B→C order with terminal/fresh skip, cap enforcement + overflow telemetry. All passing.

Why dropping the verb gate is safe: PR-C7 inverts the timing. ALL fetches happen in pre-iteration hydration under hard 500 cap. Row loop is network-free (cache lookup only). PR-C3 hang root cause cannot recur. (Caveat: bot review caught a Tier A overflow path that DID fetch — fixed in `45c72b5`.)

---

## [2026-05-01] pr | PR #40 merged — PR-C6.4 LegEvent sizing audit

Merged at `3039123`. Read-only diagnostic returned the data PR-C7 ships against:
- **Cold-start surface: 2,002 unique bills** in `journal_default` rows
- **Today's `MEETING_VERB_TOKENS` gate fires on 3 rows / 3 bills (0.1%)** — the gate is essentially turned off in production
- **Top 20 bills:** flat distribution, max 10 rows per bill (HB569), median 7
- **Cycles to full hydration at 500/cycle: 4** (~60 min wall-clock)
- **Steady-state warm cycle:** 50-200 fetches at 2/5/10% bill-churn scenarios — comfortably under 840 budget
- **Recommendation:** Phased rollout required (cold-start exceeds 840 single-cycle budget)

Gemini high review folded in pre-merge: `pd.to_datetime` for date parsing + `pandas` install in workflow YAML.

---

## [2026-05-01] pr | PR #39 merged — PR-C6.3.1 hotfix (get_all_values for duplicate-empty header)

Merged at `1941ec7`. PR-C6.3 (PR #38) shipped clean against local sanity tests but **crashed on its first production run**:
```
gspread.exceptions.GSpreadException: the header row in the worksheet contains
duplicates: ['']
```
Root cause: Sheet1's worksheet has 26 allocated cols but only ~12 schema cols. Row 1 = `[Date, Time, ..., DiagnosticHint, "", "", ...]` — the 14+ trailing empty cells parsed as identical `''` keys. **Same root class as the API_Cache 92% problem PR-C6.2 fixed:** over-allocated grid columns. Fix: `get_all_values()` + `list.index()` for column lookup. `list.index()` returns the first match, sidestepping the duplicate-key issue. Defensive `_cell()` helper for short-row tolerance.

Gemini medium follow-up review folded in: pre-calc column indices in locals + drop the `_cell()` helper inline. Matches the existing strptime pre-parse hygiene (Gemini's earlier fix in the dump tool).

---

## [2026-05-01] pr | PR #38 merged — PR-C6.3 verb-dump triage tool

Merged at `1941ec7` (alongside PR-C6.3.1 hotfix). Read-only triage that revealed the misclassification finding: top "meeting bug" rows are **`Governor's Recommendation` (76+41+5)**, **`[Memory Anchor] X Failed to Pass from conference` (14)**, **`Bill text as passed Senate (SRxxxER)` family (~46 unique outcomes)** — all administrative actions misclassified as meetings because the X-Ray's `MEETING_ACTION_PATTERNS` substring list matches them (`recommend`, `passed`, `failed`, `concurred`).

Reframed mid-PR (commit `f0890cb`) from "scope verb-list edits" to "verify PR-C7 structural pivot's coverage." Owner rejected the verb-list-extension fix as a band-aid (see [[#2026-05-03 decision | Owner rejects New-Verb Canary; mandates structural classifier pivot for PR-C7]]).

Codex P1 + Gemini medium reviews folded in:
- `TARGET_COMMITTEE = "📋 Ledger Updates"` (matches `calendar_worker.py:2772` worker write — exact match against unprefixed `"Ledger Updates"` would silently match 0 rows)
- Pre-parse window dates at module load (saves ~70k strptime calls)
- `DIAGNOSTIC_TAG_PATTERN` regex strips leading emoji + bracketed tags so verb counts don't fragment across `⚠️ [COMMITTEE_DRIFT: ...] H Reported` vs `H Reported`. Caught a self-audit bug in the regex (greedy symbol class ate `[`); fixed by excluding `[` and `]` from the symbol class.

---

## [2026-04-28] pr | PR #37 merged — PR-C6.2 trim API_Cache from 26 → 6 cols

Merged at `18134b5`. **Reclaimed 7,076,220 cells = 70.8% of the 10M cap.** Workbook total 9,996,623 → 2,920,403 cells (99.97% → 29.2% of cap). Headroom 3,377 → 7,079,597 cells.

`API_Cache` had 26 allocated cols but only 6 schema cols (`Date, Committee, Time, SortTime, Status, Location` — canonical at `calendar_worker.py:2819`). Cols 7-26 were empty padding inherited from the worksheet's default grid size. The worker writes 6-col rows and reads by header — cols 7-26 were unreachable from any code path.

Three-layer safety on the resize: (1) header schema match check, (2) all-empty G:Z check across all 353,811 rows in 50k-row chunks (Gemini high — single 7M-cell read would exceed Sheets API payload limit), (3) workflow_dispatch dry-run gate default true.

Codex P2 + Gemini medium folded in: drop `rows=` from `worksheet.resize()` so a concurrent worker cycle's appends aren't truncated.

Operator runbook executed cleanly: dry-run cycle (run #1) → live-write cycle (run #2) → cell-count audit re-verification.

---

## [2026-04-28] pr | PR #36 merged — PR-C6.1 cell-count audit

Merged at `18134b5` (alongside PR-C6.2). Read-only audit returned the unambiguous diagnosis:

| # | rows | cols | cells | % wb | % cap | title |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 353,811 | 26 | **9,199,086** | **92.0%** | **92.0%** | **API_Cache** |
| 2 | 28,909 | 26 | 751,634 | 7.5% | 7.5% | Sheet1 |
| 3 | 1,000 | 26 | 26,000 | 0.3% | 0.3% | Bug_Logs |
| 4 | 1,531 | 13 | 19,903 | 0.2% | 0.2% | Schedule_Witness |

API_Cache dominated by 12×. Codex P2 review folded in: recommendation must reference `biggest['title']` dynamically, not hardcode `"Sheet1"`.

---

## [2026-04-28] pr | PR #35 merged — PR-C6 / Move 3a (full-session stress test)

Merged at `214104b`. Widened `investigation_config.py` from `2026-02-09 → 2026-02-13` to `2026-01-14 → 2026-05-01` (full 2026 VA GA session window). First worker run on the wider window crashed at `calendar_worker.py:2972`:
```
gspread.exceptions.APIError: APIError: [400]: This action would increase the
number of cells in the workbook above the limit of 10000000 cells.
```

The architecture held — pipeline ran cleanly through 64,891 HISTORY rows, source-miss bucket math clean, classification ran, reconciliation ran, API_Cache write succeeded. **Only the final `worksheet.update()` for Sheet1 hit the cap.** "Suffering from success" — diagnosed as workbook capacity ceiling, not code defect. Triggered the PR-C6.1 → PR-C6.2 cell-cap remediation arc.

Updated [[failures/assumptions_audit]] #5 (scrape_start) status to CLOSED — gate satisfied. Gemini medium review fixes folded in (broken wikilink anchor → `[[log]]` reference, triage naming `PR-D.1/D.2` → `PR-C6.1/C6.2`, ambiguous `(this commit)` → `PR-C6`, stale "When to fix" line restructured).

---

## [2026-04-27] milestone | BOTH halves of CLAUDE.md "done" criterion HIT for crossover week

Worker run on PR-C5 code (PR #33 merged at `313e9a3`) reports X-Ray Section 9 = `0 meeting actions without times` AND `0 unclassified`. Both halves of the CLAUDE.md project goal — `meeting bug count → 0` AND `unclassified → 0` — are simultaneously satisfied for the Feb 9-13 benchmark window. **Crossover week is mathematically verified clean.**

**The math, which is the proof.** Comparing post-PR-C3.1 → post-PR-C5:

| Section 9 row | Before PR-C5 | After PR-C5 | Δ |
|---|---:|---:|---:|
| Meeting (with / without / total) | 2,715 / 0 / 2,715 ✓ | 2,715 / 0 / 2,715 ✓ | 0 / 0 / 0 |
| Administrative (with / without / total) | 1,176 / 431 / 1,607 | 1,312 / 452 / 1,764 | +136 / +21 / +157 |
| Unclassified (with / without / total) | 136 / 21 / 157 | 0 / 0 / 0 ✓ | −136 / −21 / −157 |

**Exactly** the 157 unclassified rows moved into administrative. Zero misrouted to meeting (no false positives). Zero remain unclassified. The 5 substring patterns (`(view meeting)`, `no agenda listed`, `subcommittee info`, `speaker's conference room`, `[memory anchor: admin]`) plus the empty-outcome guard (`if not lower or lower in ("none", "nan")`) fully covered the bucket — no PR-C5.1 pattern triage needed for the 156 schedule-skeleton rows.

**Other green signals:** Section 7 (Sheet vs LIS time parity) = 0 missing; Section 8 (system alerts) = 0; Ledger Health Check = 428 admin / 0 meeting bugs / 0 unclassified; bucket math holds with no drift warning.

**One residual flagged for PR-C5.1 (this branch):** Section 5's worker-side `UNKNOWN_ACTION (1 row)` counter still ticks. That row is SB584 on 2026-02-10 — **a malformed HISTORY.CSV row** with description `"S "` (chamber prefix + space, no verb) and empty refid. It's an upstream LIS data anomaly, not a missing pattern. PR-C5.1 adds a structural malformed-row guard. See entry below.

**What this milestone unlocks.** The investigation window can now widen from the Feb 9-13 test value to the full session (Jan 14 → May 1) per [[failures/assumptions_audit]] #5's "When to fix: After calendar reaches 100% accuracy". That's the next move (PR-D series). [[architecture/calendar_pipeline]] is proven on the hardest week; the stress-test will prove (or disprove) it at session scale.

---

## [2026-04-27] pr | PR-C5.1 — malformed HISTORY-row guard (SB584 outlier)

Branch `claude/pr-c5.1-sb584-outlier-and-writeback`. One surgical addition to `calendar_worker.py` plus the writeback for the meeting-bug=0 milestone.

**Why this exists.** After PR-C5 (PR #33) cleared Section 9 unclassified to 0, Section 5's worker-side `UNKNOWN_ACTION` counter still showed 1 row. Investigation: the row was SB584 / 2026-02-10 / Senate P&E. Direct fetch of LIS LegislationEvent API showed **two** real events for SB584 that day (`S8122` "Senate committee offered" 11:30, `S0808` "Failed to report from Privileges and Elections with substitute (7-Y 7-N 1-A)" 00:00) — both verbs already match `KNOWN_EVENT_PATTERNS` (`"offered"` and `"failed"`). So the verbs themselves were not the issue. Direct fetch of HISTORY.CSV showed **three** rows for SB584 that day — the two real ones plus a third with description literally `"S "` (chamber prefix + space, no verb) and empty `History_refid`. That malformed row is what the worker tags `UNKNOWN_ACTION`.

**Why a pattern addition would have been wrong.** Adding `"s "` to `KNOWN_NOISE_PATTERNS` would substring-match every "S Foo" Senate row — Zero-Trust violation by means of false-positive noise filtering. The verb-list approach assumes there IS a verb to classify; here there isn't.

**Fix — structural guard at `calendar_worker.py:2316`.** After `outcome_text` is set and chamber prefix detected, strip the leading `H ` / `S ` and check if the remainder is empty. If yes: emit categorized `push_system_alert` (`category="DATA_ANOMALY"`, `severity="WARN"`, `dedup_key=f"history_empty_desc::{bill_num}::{date_str}"` — flooding-safe per CLAUDE.md Standard #4), increment `source_miss_counts["dropped_noise"]` to keep denominator math intact (one bucket added to total_processed), and `continue`. The DATA_ANOMALY alert (not the bucket label) carries the diagnostic distinction; future PR can promote to a dedicated `dropped_malformed` counter if the volume warrants.

**Expected next worker run:** Section 5 `UNKNOWN_ACTION` 1 → 0; Section 9 metrics unchanged; Section 8 may show a one-time WARN row for the SB584 anomaly with the dedup_key. Bucket math still holds: dropped_noise +1, all other buckets identical.

**New page:** [[failures/assumptions_audit]] #45 — captures the lesson that "missing pattern" and "malformed upstream row" are different failure modes and the gate that distinguishes them.

---

## [2026-04-27] pr | PR #33 merged — PR-C5 unclassified pattern triage

Merged into `main` at `313e9a3`. Five substrings added to `ADMINISTRATIVE_PATTERNS` (`(view meeting)`, `no agenda listed`, `subcommittee info`, `speaker's conference room`, `[memory anchor: admin]`); `classify_action()` empty-outcome guard added (`if not lower or lower in ("none", "nan")`). Files mirrored via `cp` to preserve diff-identical contract. Gemini PR review caught one issue mid-flight: the original guard was `lower == "none"` and missed pandas NaN values — fixed by extending to `lower in ("none", "nan")` with comment block documenting why exact-match is the right place (substring `"nan"` would sweep "finance"/"Tennessee"). 14/14 logic spot-check + Gemini review fix. See [[log#2026-04-27-milestone--both-halves-of-claudemd-done-criterion-hit-for-crossover-week]] above for the milestone details and bucket math.

---

## [2026-04-26] pr | PR #32 merged — docs sync recovery + Codex/Gemini review fixes

Merged into `main` at `1b9bfc7` then follow-up `c7838c1`. Recovered the stranded PR-C3.1 writeback commit (`57dfc63`) that was pushed to a now-dead branch after PR #31 merged. Cherry-picked cleanly as `8950c0b` onto a fresh branch from main, then pushed Codex P2 fix (PR #31 row moved out of Open PRs table) and Gemini renumbering (added missing `#41` PR#22 line-level lesson, renumbered my entries to `#42/#43/#44`, updated 4 back-references in lockstep). Net effect: the brain on main is fully synced with the meeting-bug=0 milestone state.

---

## [2026-04-26] milestone | Meeting actions without times = 0 (first half of CLAUDE.md "done" hit)

Worker run on the PR-C3.1 code (PR #31 head `a2bb618`) reports X-Ray Section 9 = `0 meeting actions without times`. Crossover-week bug count: **9 → 0** in a single PR. The CLAUDE.md "Current Goal" — "every action that happened in a meeting must show the time of that meeting" — is satisfied for the benchmark window.

Bucket math holds with no drift warning: `sourced_api(12,324) + sourced_convene(32,429) + sourced_legislation_event(182) + unsourced_journal(6,553) + floor_anchor_miss(6,571) + dropped_noise(6,696) = 64,755 = total_processed`. LegEvent telemetry: 185 attempted / 182 recovered / 3 abstained (the abstain-on-zero-overlap and wrong-chamber safety nets working as designed). Worker completed normally (~2 min cycle), no recurrence of the Apr 25 hang. Section 7 (Sheet vs LIS time parity): 0 rows missing time in Sheet but with time in LIS. Section 8: 0 system alerts. Ledger Health Check: 428 admin / 0 meeting bugs / 0 unclassified.

**Class-2 collapse — unexpected bonus.** The PR was scoped to fix 4 × Class-1 (parent-committee Schedule API gap on HB111/505/972/609). All 5 × Class-2 subcommittee-attribution bugs (HB24/1266/1372/SB494/SB555) collapsed too — confirmed by inspection of `MEETING_VERB_TOKENS` (`calendar_worker.py:362`): `"subcommittee offered"` and `"recommends continuing"` are in the canonical allowlist, so all Class-2 outcomes pass the PR-C3.1 gate. The LegislationEvent endpoint is keyed by **bill + date + chamber** (not committee), so subcommittee-vs-parent attribution doesn't gate time recovery. PR-C4 (originally scoped for Class-2) is provisionally retired — see [[state/current_status#class-2-collapse-via-legislationevent-pr-c31-side-effect]]. Re-open only if Sheet1 `Committee` column accuracy is later promoted from "informational" to a tracked metric.

**Half remaining.** The other half of the "done" criterion — `unclassified → 0` — is still open. Section 9 reports 157 unclassified actions (REVIEW). Sample inspection: predominantly meta rows (agenda links, "House Convenes", "Immediately upon adjournment of …"). PR-C5 will categorize each into NOISE/ADMIN pattern lists.

---

## [2026-04-26] pr | PR-C3.1 opened as PR #31 — response cache + meeting-verb gate

Branch `claude/pr-c3.1-legislation-event-cached`. Two surgical fixes on the PR-C3 base, both born from the Apr 25 incident post-mortem (entry below):

1. **`_legislation_event_cache`** per-cycle, mirroring the existing `_legislation_id_cache` pattern. Keys are `(bill_num, session_code_5d)`. The endpoint returns the bill's whole event history in one shot, so a single fetch covers every action_date for that bill — eliminates the N+1 fetch that hit the LIS WAF rate-limiter on Apr 25. Negative cache: any failure path stores `[]` so a same-cycle retry storm cannot stack the urllib3 `Retry(total=4, backoff_factor=2)` on top of the rate-limiter. Categorized `push_alert` with `dedup_key` still fires on miss so the failure remains visible.
2. **Meeting-verb gate** — call site changed from `if origin == "journal_default":` to `if origin == "journal_default" and any(v in outcome_lower for v in MEETING_VERB_TOKENS):`. Reuses the existing canonical allowlist at `calendar_worker.py:362` (already used by the convene-times index and HISTORY-vs-witness reconciliation — single source of truth, NOT a parallel list). Collapses the candidate set from "every journal_default row in the full session window" (thousands of admin actions like Prefiled / Referred / Printed) to actual meeting-verb candidates (the Class-1 + Class-2 patterns).

Codex P1 outcome_text matcher, Codex P2 X-Ray denominator (`sourced_legislation_event` bucket + `legislation_event_attempted/recovered` orthogonal counters), Gemini `isinstance(..., dict)` type-safety guards, and the session-code 3-digit limitation docstring are all preserved unchanged from PR-C3 round-2.

Diff scope: `calendar_worker.py` only. `calendar_xray.py` and `pages/ray2.py` unchanged from PR-C3 round-2 (still diff-identical per CLAUDE.md pre-push #4).

**Tests (13/13 passing on Python 3.9 via `python3 test_pr_c3_helper_v2.py`):** all 11 from PR-C3 round-2 still green (matcher behavior unchanged); two new regression tests prove the cache (`test_pr_c31_event_cache_prevents_refetch`: 2 calls for same bill on different dates → exactly 1 LegislationEvent HTTP request; `test_pr_c31_negative_cache_suppresses_retry_on_failure`: HTTP 500 on first call → second call hits `[]` cache, total fetch attempts = 1).

**Branch ancestry note — revert-of-merge resolved via `-s ours` merge.** PR-C3.1 was branched from the PR-C3 tip (`f5745c4`) to preserve a single review surface. After main reverted PR #30 (commit `246cba5`), the merge-base of branch and main was `f5745c4` and the branch's diff-vs-base diverged opposite-direction from main's diff-vs-base — the canonical revert-of-merge three-way conflict. Two attempts were tried before landing the right one: `git revert 246cba5` was a zero-diff no-op (HEAD already had everything the revert removed) and would not have cleared GitHub's conflict block; `git merge -X ours origin/main` silently un-applied module-level constants (`LEGISLATION_EVENT_HEADERS`) on non-conflict lines and broke the resolver with a NameError. Final fix: `git merge -s ours --no-ff origin/main` (commit `a2bb618`) — the strategy form discards theirs tree entirely while still recording main as a merge parent, shifting the merge-base to `246cba5` and clearing the conflict without force-push. Full mechanical analysis: [[failures/assumptions_audit]] #44.

---

## [2026-04-26] post-mortem | Apr 25 PR#30 worker hang — N+1 fetch + over-broad gate

PR #30 merged 2026-04-25; on the next 15-min worker cycle the GitHub Actions run hung 11+ min vs normal ~2 min and was manually canceled. Reverted on main as commit `246cba5` (the bleed-stop) the same day.

**Root cause #1 — N+1 fetch (dominant cost).** The original `_resolve_via_legislation_event_api` cached `LegislationID` per (bill, session) but NOT the `LegislationEvent` history fetch. The endpoint returns the bill's whole history in one shot, so a single fetch covers every action_date — yet every `journal_default` row in HISTORY.CSV triggered a fresh fetch. With ~3,000 unique bills and likely ~10,000+ journal_default rows across the full session window, the worker issued thousands of redundant HTTP calls. Combined with `urllib3.Retry(total=4, backoff_factor=2)` on 429s, LIS WAF rate-limiting cascaded into 40s+ stalls per affected request.

**Root cause #2 — gate too loose.** `if origin == "journal_default":` fired across the FULL session window (Jan 14 → May 1, NOT the Feb 9-13 investigation window — see `calendar_worker.py:2080`) for thousands of administrative rows ("Prefiled", "Referred to Committee", "Printed") with zero chance of recovering a meeting time. The Class-1 bug pattern is specifically *committee meeting verbs* with no Schedule API entry — orders of magnitude smaller.

**What had been tested and what hadn't.** Standalone unit tests (13/13 pre-merge) covered matcher correctness on the 4 Class-1 + HB1 multi-event cases and the abstain safety nets. They did NOT exercise the gate's selectivity at session scale or the per-cycle HTTP-call count. The reviewer playbook for new fallback paths needs a "candidate-set sizing" check before merge — see [[failures/assumptions_audit]] #42 / #43.

**Remediation.** Both root causes fixed surgically in PR-C3.1 (PR #31 — entry above). Validated by two new regression tests; no force-push, no history rewrite. Audit trail preserved: PR#30 merge → main revert → PR-C3.1 → `-s ours` merge of main → meeting-bug=0 milestone, all visible in linear log.

---

## [2026-04-25] pr | PR-C3 round-2 + PR #30 merged (and reverted same day)

Pushed Codex P1/P2 + Gemini round-1 review fixes on `claude/pr-c3-legislation-event-fallback` (commit `f5745c4`): outcome_text token-overlap matcher with score=0 abstain (Codex P1); `sourced_legislation_event` added to mutually-exclusive `_bucket_sum` plus orthogonal `legislation_event_attempted/recovered` counters in `calendar_xray.py` + `pages/ray2.py` (Codex P2, files diff-identical per CLAUDE.md pre-push #4); `isinstance(raw_json, dict)` guards on both `r.json()` parses (Gemini); LIMITATION docstring on `_normalize_session_code_5d` documenting the 21st-century "20" prefix assumption with upgrade path (Gemini). 11/11 standalone tests passing. Pre-push audit caught a stale `calendar_worker.py:942` line ref in the LIMITATION docstring (actual line was 1233, now 1259); replaced with a search-string anchor that won't rot.

PR #30 merged at `4d398ac`. The very next worker cycle hung 11+ min and was manually canceled — see [post-mortem](#2026-04-26-post-mortem--apr-25-pr30-worker-hang--n1-fetch--over-broad-gate) above. Reverted on main as `246cba5`. Net same-day status: PR-C3 round-2 code returned to a feature branch, awaiting the surgical fix that became PR-C3.1.

---

## [2026-04-25] ingest | LIS API surface fully inventoried (developer portal + LegislationEvent verified)

PR-C2.1 was reverted yesterday after headless verification proved the "historical web scraper" premise wrong (no public web source has 2026 data the Schedule API doesn't). Today's deeper investigation surfaced the actual recovery path: the **LegislationEvent API** publishes minute-precision `EventDate` timestamps for every bill action, including the 4 Class-1 bug actions (HB111/505/972/609 on Feb 12) where the Schedule API has zero entries for the parent committee.

**Verification results (read-only probes, single cycle):**
- HB111 (P&E Feb 12) → `EventDate: 2026-02-12T21:02:00`
- HB505 (P&E Feb 12) → `EventDate: 2026-02-12T21:02:00`
- HB972 (P&E Feb 12) → `EventDate: 2026-02-12T21:03:00`
- HB609 (Finance Feb 12) → `EventDate: 2026-02-12T09:24:00`

All four have recoverable times via `https://lis.virginia.gov/LegislationEvent/api/GetPublicLegislationEventHistoryListAsync?legislationID={id}&sessionCode=20261`.

**Owner correction (mid-investigation): the LIS dev portal at `lis.virginia.gov/developers` lists ALL 31 public API services**. LegislationEvent is not new or hidden. The brain previously documented only 3 (Session/Committee/Schedule), so this knowledge was effectively lost. [[knowledge/lis_api_reference]] now contains the full inventory plus the LegislationEvent + LegislationVersion contracts.

**Three integration gotchas captured in the brain:**

1. **Two distinct public WebAPIKeys.** The legacy worker key (`81D70A54-...`) covers Session/Committee/Schedule but returns 401 on the new MVC endpoints. The SPA's public key from `handleTitle.js` (`FCE351B6-...`) covers everything. Neither alone covers the full API surface.
2. **Two session-code formats.** Legacy 3-digit `261` works on Schedule/Committee/Session; new MVC endpoints (LegislationEvent, LegislationVersion, AdvancedLegislationSearch, ...) require 5-digit `20261` and reject the legacy form with `"Provided Session Code is invalid"`.
3. **Two-step bill→ID→events lookup.** `LegislationEvent` requires `legislationID` (not `billNumber`). One extra hop through `LegislationVersion/api/GetLegislationVersionbyBillNumberAsync` resolves it. LegislationID is stable per session — cacheable.

**Next:** PR-C3 — surgical 80-120 line addition in `calendar_worker.py`: `_resolve_via_legislation_event_api(bill_num, action_date)` as fallback in the time-resolution chain (after API_Schedule, before `journal_default`). Targets exactly the 4 Class-1 bugs. Class-2 (subcommittee attribution) remains a separate problem; LegislationEvent's `CommitteeNumber/CommitteeName` are `None` on vote-style events so this API doesn't help that class directly.

## [2026-04-24] pr | PR#29 merged — PR-C2 (gap detection + Schedule_Witness + reconciliation)

Merged into `main` at 17:17 UTC after three rounds of Gemini review (round-1 inline at PR open, round-2 Location/prune/canary patches, round-3 `col_values()` scale-cliff fix). Merge commit `fddfea6`. Final shipped scope: Y1 gap-detection with 7 `gap_cause` classes + WARN/CRITICAL thresholds; `Schedule_Witness` change-feed tab (13 cols, ADDED+CHANGED only, whitelist-iterated `WITNESS_DELTA_FIELDS = (Time, SortTime, Status, Location)`, migration burst guard, retention deferred to L3b Nightly Audit); HISTORY-vs-witness reconciliation with 7-day cap. Zero bug-count delta as expected — observability + data-recovery infrastructure. Counters added to `source_miss_counts`: `gap_minutes`, `gap_cause`, `witness_rows`, `witness_location_backfills`, `reconciliation_blind_dates`, `reconciliation_checked_dates`. Three follow-ups still flagged in [[ideas/future_improvements]]: L3b Nightly Audit (witness retention owner), PR-C2.1 Playwright historical scraper (data-recovery), Notification Routing for `y1_stale` / `gap_reconciliation_oversized` / `gap_critical` CRITICALs. Next: PR-C3 (LegislationEvent API as secondary time source) — first fix-pass that collapses Class 1 bugs.

## [2026-04-24] pr | PR-C2 round-3 patch — col_values() for reconciliation witness-date index

Single-point fix in response to Gemini round-3 HIGH review of PR #29. Part C reconciliation was reading the `Schedule_Witness` tab via `get_all_values()` to build the prior-cycle `witness_dates` index. Given the 90-day retention target and high cycle frequency, the change-feed can approach Sheets' 10M-cell ceiling, and pulling the entire sheet into memory every cycle is a latent scale cliff that eventually breaks the worker via timeout or memory pressure. Only `meeting_date` is needed for the index. Switched to `col_values(WITNESS_HEADER.index("meeting_date") + 1)` which fetches only that column. Header cell is sliced off via `[1:]`. The existing try/except fallback-to-deltas-only semantics is unchanged, so a col-read failure still degrades gracefully.

Adversarial audit: WITNESS_HEADER is the canonical schema we write at tab creation (inside `_ensure_witness_tab`), so index lookup against the constant is stable and matches what's on the tab. No schema drift risk unless someone hand-edits the tab header — and in that case the col fetch still returns the data, just potentially from a different column; the fallback semantics would give weaker reconciliation for one cycle until detected. Acceptable. No other `witness_tab.get_all_values/get_all_records` call sites in the worker (grep-verified). AST parse clean.

Docs updated: architecture/calendar_pipeline Part C bullet 2 now documents the `col_values()` path + the memory-cliff rationale.

---

## [2026-04-24] pr | PR-C2 round-2 patches — Location delta, prune moved to L3b, size canary

Pushed three patches on the open PR-C2 branch in response to Gemini round-2 review. Owner greenlit Concerns 1 + 2 for the current branch; Concern 3 (Playwright scraper) deferred to PR-C2.1.

**Concern 1 — Location/Room missing from witness (round-1 junk-delta whitelist + round-2 "Missing Room Update"):** `WITNESS_DELTA_FIELDS = ("Time", "SortTime", "Status", "Location")` constant introduced with DO-NOT-ADD-METADATA warning. Delta comparison rewritten to iterate the whitelist — never iterate `_wval.items()` or any future metadata key becomes a delta trigger. `_extract_meeting_location(meeting)` uses a `Location → Room → RoomDescription` fallback chain (the field is not documented in [[knowledge/lis_api_reference]]) and logs which key fired. Location threaded through `api_schedule_map`, `new_cache_entries`, API_Cache header + compaction. `WITNESS_HEADER` grew from 11 → 13 cols (`location`, `prev_location` appended to both the current-state and prev-state halves). **Migration burst guard:** on first cycle(s) after deploy, API_Cache-seeded entries have Location="" while live entries are populated — without suppression every meeting would emit a bogus CHANGED delta. Suppress ONLY when the delta is {"Location"} and it went empty→populated; count in `witness_location_backfills` so the one-time burst is visible but quiet. Real room moves (both sides non-empty) still emit. One-time header migration in the cache-read path writes `F1="Location"` if missing, so subsequent cycles can actually read the column back (without this, the burst guard would fire forever).

**Concern 2 — Pruning race (round-1 "Pruning Race Condition"):** removed the in-cycle `append_rows` + `col_values(1)` + `delete_rows` block entirely. Same-cycle append-then-delete on a Google Sheets tab is a documented eventual-consistency race that can silently delete rows we just wrote. Retention is now owned by an L3b Nightly Audit (TODO, see [[ideas/future_improvements#L3b Nightly Audit — Schedule_Witness retention owner (flagged 2026-04-24, PR-C2 round-2)]]) running outside the 15-min hot path. Cycle still does a cheap `col_values(1)` read as a size canary: exposes `witness_rows` in `source_miss_counts` and fires `witness_canary_over_threshold` WARN at > 500,000 rows so L3b lag is visible.

**Concern 3 — Playwright scraper deferred to PR-C2.1.** Will use `wait_for_selector()` tied to the actual schedule-table DOM element (NOT `wait_for_load_state("networkidle")` which hangs on bloated gov sites) and ≥ 15s per-date timeout (5s was too aggressive for LIS at peak session). Flagged in [[ideas/future_improvements#PR-C2.1 — Playwright historical scraper (deferred from PR-C2)]].

**Adversarial audit (embedded at commit time):** Caught a NameError bug during audit — `WITNESS_DELTA_FIELDS` was originally defined after the live loop but referenced inside it; hoisted the constants block above the pre-live snapshot so closure order matches execution order. API_Cache schema migration is idempotent; compaction + rollback blocks both padded to 6 cols so writes stay rectangular. No new silent fallbacks: every new except path has a categorized alert with a unique dedup_key. Whitelist iteration means we cannot accidentally add a new field without explicitly opting in. AST parse clean.

---

## [2026-04-24] pr | PR-C2 opened — gap detection + witness log + reconciliation

Second PR in the PR-C series, on branch `claude/pr-c2-gap-detection-witness-log`. Three-part scope, all landing together so data-recovery infrastructure is cohesive:

**Part A — Y1 gap detection.** Parses `Sheet1!Y1` (written by PR-C1), computes `gap_minutes = now_utc − Y1`, classifies `gap_cause` as one of `first_run`, `future_cursor`, `stale_cursor` (>30 d), `malformed_cursor`, `breaker_carryforward` (W1 populated), `outage`, `normal`. Emits WARN at >20 min gap, CRITICAL at >60 min, CRITICAL on stale_cursor. `gap_cause` and `gap_minutes` land in `source_miss_counts` for SYSTEM_METRICS. `_gap_window_start_utc` becomes the usable bound for Part C — set ONLY when Y1 parses cleanly and is neither future nor stale. All comparisons use `datetime.now(timezone.utc)` (PR-C1 Codex P1 fix already made the UTC import available).

**Part B — `Schedule_Witness` change-feed tab.** Append-only log of ADDED + CHANGED LIS Schedule API deltas, one row per delta (11 cols: `seen_at_utc | run_id | event_type | meeting_date | committee | time | sort_time | status | prev_time | prev_sort_time | prev_status`). Pre-live deep-copy snapshot of `api_schedule_map` is diffed against post-live state BEFORE the `best_times` post-pass so the witness captures raw LIS signal. REMOVED deferred — can't reliably distinguish "LIS dropped it" from "LIS did not return it this poll" given cross-session cache staleness. Data-loss detection for that case is Part C's job. Tab auto-created on first delta. 90-day rolling prune via lexical sort of ISO timestamps + single `delete_rows(2, N)`. Write NOT gated by the circuit breaker — witness rows have to survive breaker trips, since the entire point is reconciliation on the next healthy cycle. Volume math: steady-state well under 10M-cell Sheets limit (change-feed, not snapshot); cold-start ~3.3k ADDED burst then normalizes.

**Part C — HISTORY-vs-witness reconciliation.** Runs ONLY when `gap_cause in {outage, breaker_carryforward}` AND `gap_minutes >= 60`. Hard cap `GAP_RECONCILIATION_MAX_DAYS = 7`: over cap, CRITICAL `DATA_ANOMALY` alert + skip (manual review required). Within cap, builds gap date range in ET, builds witness date index (this cycle's deltas + all prior Schedule_Witness rows), filters `df_past` (HISTORY.CSV) to meeting-verb rows in gap window, and for each date with HISTORY meeting-verb rows but zero witness evidence emits a WARN `DATA_ANOMALY` labeled "CONFIRMED BLIND-WINDOW LOSS". Date-granularity (not committee-granularity) because HISTORY doesn't carry committee directly — resolving committee would force reconciliation to run AFTER the Sequential Turing Machine, which defeats the "cheap and independent" goal. `reconciliation_blind_dates` / `reconciliation_checked_dates` added to `source_miss_counts`.

**Future-consideration flag.** Owner flagged during scoping that the CRITICAL alerts here (`y1_stale`, `gap_reconciliation_oversized`, `gap_critical`) may eventually want a dedicated dashboard or push channel rather than routing through `SYSTEM_ALERT` rows. Tagged in code comments on both alert sites, in [[architecture/calendar_pipeline#Future-consideration flag]], and in a new section in [[ideas/future_improvements#Notification Routing (flagged 2026-04-24, PR-C2)]].

Adversarial audit (because Codex/Gemini don't re-review mid-stream): 9-point pre-push checklist clean; boundary conditions verified — Y1 parse handles None + ValueError + future + stale + malformed; delta computation survives api_is_online=False (empty deltas, no write); prune handles all-old / all-new / empty-tab / single-row / multi-row cases; breaker interaction confirmed (trip leaves Y1 untouched → next cycle detects as `breaker_carryforward`); source_miss_counts mixed int/string values serialize cleanly via `json.dumps`; no new silent fallbacks (every except has a categorized alert).

Zero bug-count delta expected. This is observability + data-recovery infrastructure; PR-C3 (LegislationEvent API) is the first fix-pass that collapses Class 1 bugs.

---

## [2026-04-21] pr | PR-C1 review fixes — Codex P1/P2 + Gemini denominator

Three review findings on PR #28 addressed in one follow-up commit on `claude/pr-c1-append-event-chokepoint`. All three are real issues; all three surface anti-patterns worth extracting so future PRs don't repeat them. New entries #38, #39, #40 in [[failures/gemini_review_patterns]].

**Codex P1 — Y1 stored as ET mislabeled UTC:** `now = datetime.now(America/New_York).replace(tzinfo=None)` at L722. My Y1 write used `now.strftime("%Y-%m-%dT%H:%M:%SZ")` — the `Z` suffix is a lie, it's actually local ET wall-clock time. A PR-C2 consumer treating Y1 as UTC would shift the gap-backfill window by 4–5 hours across DST, either missing or double-processing intervals. Fix: added `timezone` to the datetime import, compute `_cycle_end_utc = datetime.now(timezone.utc)` at breaker evaluation time, use `_cycle_end_utc.strftime(...)` for Y1 and the breaker message. All other uses of `now` (alert rows' human-readable timestamp, date keys) stay ET because those are ET-facing fields. Anti-pattern #38.

**Codex P2 — breaker alert not durable:** `push_system_alert` appends to `alert_rows`, which is a function-local list persisted to Sheet1 ONLY as part of the main `worksheet.update(...)` call. The breaker path deliberately skips that update — so the alert died with the process. My architecture doc's claim "goes to `alert_rows` (so the next healthy cycle surfaces it)" was flat wrong — `alert_rows` resets each cycle. Fix: added a durable JSON trip record at `Sheet1!W1` (compact banner stays at X1), plus a carry-forward READ at the top of the next cycle that converts the W1 record into a proper `DATA_ANOMALY / CRITICAL` SYSTEM_ALERT row. W1 is cleared on successful overwrite so the carry-forward doesn't double-report. SYSTEM_ALERT monitors now see breaker trips one cycle delayed instead of never. Anti-pattern #39.

**Gemini high — denominator semantics:** `_violation_rate = invariant_violations / total_processed` used a denominator that counted pipeline entries including rows dropped before `_append_event` (noise filter, state-machine drops). Numerator can only fire INSIDE `_append_event`. Rate was silently diluted. Gemini's suggestion was to move `total_processed` increment into `_append_event` — I took a variation that preserves existing denominator-bucket math: added a new orthogonal counter `rows_appended` inside `_append_event`, used as the breaker's rate denominator. `total_processed` stays as the mutually-exclusive-bucket sum it's always been (Section 0 denominator). Anti-pattern #40.

**Also updated:** [[architecture/calendar_pipeline]] breaker section corrected re: in-memory alert durability; added W1 subsection; flagged real-UTC requirement on Y1.

**Phase-2 re-audit after fixes:** AST parse pass, `_append_event` still defined exactly once, diff visibility grep still empty. Ready to push.

## [2026-04-21] pr | PR-C1 opened — write-time chokepoint + circuit breaker + state cell + concurrency

First PR in the PR-C series. Pure scaffolding — lands the infrastructure that PR-C2+ (the actual bug fixes) depend on. Zero bug-count delta expected from C1 alone; this is a prerequisite for auditable fix-passes. Branch: `claude/pr-c1-append-event-chokepoint`.

**Five pieces shipped (diff: +265 / -9 across 2 files + 3 doc files):**

1. **Write-time chokepoint `_append_event()`** — nested closure inside `run_calendar_update()`, defined once, used at all 5 bill-row append sites (API chamber event, DOCKET row, API_Skeleton DLQ row, API_Skeleton agenda row, main CSV loop row). Enforces four invariants:
   - **I1** — schema completeness (all 11 columns). Missing keys fill with `""`, push `DATA_ANOMALY / CRITICAL` alert.
   - **I2** — `Origin` in the enumerated set `{api_schedule, convene_anchor, journal_default, floor_miss, system_alert, system_metrics}`. Out-of-enum pushes alert; row is NOT dropped (visibility beats silence).
   - **I3** — concrete-source Origins (`api_schedule` / `convene_anchor`) cannot carry a `⏱️ [NO_*]` Time string. Parity violation pushes alert.
   - **I4** — telemetry counter (no invariant): meeting-verb outcome AND Origin in `{journal_default, floor_miss}` increments `meeting_unsourced`. Feeds the circuit breaker.

2. **Mass-violation circuit breaker** — just before `worksheet.clear() + worksheet.update()`, evaluates three thresholds:
   - `violation_rate > 10%` (invariant_violations / total_processed)
   - OR `invariant_violations >= 50` absolute
   - OR `meeting_unsourced >= 50` (baseline today for crossover week: ~9)

   On trip, the worker REFUSES the Sheet1 overwrite — leaves the previous cycle's data intact as last-known-good. Banner written to `Sheet1!X1`, `DATA_ANOMALY / CRITICAL` alert pushed. Y1 is NOT advanced, so PR-C2's gap-backfill naturally covers the skipped cycle. Thresholds are intentionally generous — a safety net for regressions, not a gate on normal operation.

3. **State cell `Sheet1!Y1`** — `last_successful_cycle_end_utc`. Written with the ISO UTC timestamp after every successful overwrite. Read at cycle top (logged only in C1; C2 will consume it as the "since" cursor). Empty on first post-C1 deploy is expected and does not alert. Read/write errors emit categorized `API_FAILURE` alerts.

4. **GitHub Actions `concurrency`** on `calendar_worker.yml`: `{ group: calendar-worker, cancel-in-progress: false }`. If cycle N's runtime slips past 15 min, cycle N+1 queues rather than running in parallel. Never cancels mid-flight — half-written Sheet1 is worse than a delayed cycle.

5. **Counter schema additions** in `source_miss_counts`: `invariant_violations` (rows that failed I1/I2/I3 at append time) and `meeting_unsourced` (meeting-verb outcome + unsourced Origin). Both overlap the existing denominator buckets by design — orthogonal-tag pattern, same as `unsourced_anchor` and `dropped_ephemeral` (see [[failures/gemini_review_patterns]] #31).

**Module-level constant added:** `MEETING_VERB_TOKENS` (high-recall list mirroring `tools/crossover_audit/diff_sheet1.py` MEETING_VERBS — the two lists should stay in sync). False positives only elevate the telemetry counter, never drop or reclassify rows.

**Self-audit against 9-point pre-push checklist:** pass.
- (1) Verb forms — MEETING_VERB_TOKENS covers base/past/present as the crossover-audit pair does; no new conjugation lists.
- (2) Function scope — `_append_event` defined once, nested in `run_calendar_update`, before all call sites.
- (3) Doc version sync — architecture doc updated in same PR.
- (4) Duplicate file check — no `pages/ray2.py` / `calendar_xray.py` drift (PR doesn't touch X-Ray).
- (5) Architecture conformance — [[architecture/calendar_pipeline]] now has "Write-Time Safety Rails (PR-C1)" section.
- (6) Zero-trust data — all four invariants emit categorized alerts; no silent paths introduced.
- (7) Cross-list validation — MEETING_VERB_TOKENS overlaps with ABSOLUTE_FLOOR_VERBS, DYNAMIC_VERBS, KNOWN_EVENT_PATTERNS by design (orthogonal tagging, not classification).
- (8) Import resolution — no new top-level imports touched.
- (9) Source-miss visibility — grep on diff is empty; no new `continue` / `except: pass` / `"Time TBA"` sites.

**Writing back to:** [[architecture/calendar_pipeline]] (Write-Time Safety Rails section), [[state/current_status]] (PR-C1 added to Open PRs, Active focus updated), this entry.

**After Gemini review:** merge → PR-C2 (gap-backfill consuming Y1) → PR-C3 (LegislationEvent secondary time source, collapses Class 1) → PR-C4 (subcommittee attribution, collapses Class 2).

## [2026-04-20] pr | PR #27 review fixes — encoding, portability, phantom_row coverage

Six review comments from Gemini + Codex on the crossover-audit tooling addressed in one commit on branch `claude/crossover-audit`.

**Medium (Gemini):**
- `build_universe.py`, `diff_sheet1.py`: open HISTORY.CSV as `iso-8859-1` (per [[knowledge/lis_api_reference]]). Defensive — current snapshot happens to be pure ASCII, but that won't hold forever.
- `extract_truth.py`: `html.unescape()` added to `strip_tags` so LIS-emitted `&amp;` / `&nbsp;` / numeric refs don't desync downstream string compares against API-sourced text.
- `fetch_bills.sh`: `CHROME` path via env-var override with executable-bit check, so the script runs on Linux/CI without editing.

**Codex:**
- `fetch_bills.sh` (P2): capture Chrome exit status; report `FAIL` distinctly from `UNDERSIZED`. Previous version masked non-zero rc by redirecting stderr.
- `diff_sheet1.py` (P1): iterate `universe | sheet_bills` (union, not intersection) so phantom-row checks also cover the 19 bills in Sheet1 with no Feb 9-13 HISTORY activity. Re-ran: `phantom_row: 0` still holds — all 19 are correctly-classified `Outcome: Scheduled` placeholders (non-action).

**Extra fix caught during verification:**
- `diff_sheet1.py`: `sorted(all_dates)` before iteration so `crossover_audit_findings.json` is deterministic across runs. Python set iteration is hash-randomized; findings.json was churning on every re-run and cluttering diffs.

**Findings summary unchanged:** `meeting_in_ledger: 9`, `phantom_row: 0`, `subcommittee_miss: 0`. See [[testing/crossover_audit]].

**PR-C direction (decided this session, not yet coded):** LegislationEvent API (`GET /LegislationEvent/api/GetLegislationEventByLegislationIDAsync?legislationID=<int>`) is the bank-grade source. Per-bill event dump carries ISO `EventDate`, `CommitteeName`, `ParentCommitteeName`, `EventCode`, `VoteTally`. Requires a pre-built bill→integer-ID map (AdvLegSearch + sequential sweep covers all 3,634 session 20261 bills; the published `GetLegislationIdsListAsync` returns only 2,831). Coverage on the 9 known bugs: 6 fully rescued; 3 are LIS-side data holes (HB24 has no meeting-verb event; SB494 Feb 12 and SB555 Feb 12 × 2 carry `00:00` midnight-stub timestamps). New quirk logged to [[knowledge/lis_api_reference]] as follow-up.

**Fallback chain order** (to be implemented in PR-C):
1. `LegislationEvent` API, join-by-(bill, date) so fields merge across multiple events on the same day
2. `Schedule` API by (committee, date) for bills where LegislationEvent is committee-only or blank
3. `HISTORY.CSV` refid parsing (H18001 → parent H18) as last-resort committee attribution
4. `SOURCE_GAP` alert — never silent-fallback to `Time TBA` or `12:00`

## [2026-04-19] session | Crossover Week full-universe audit completed — X-Ray Section 9 bug count confirmed at 9

Ran tier-A ground-truth audit: 1,544 bills × 6,885 LIS actions vs 4,473 Sheet1 rows, Feb 9-13 2026 window. Pipeline: `tools/crossover_audit/{build_universe.py, fetch_bills.sh, extract_truth.py, diff_sheet1.py}`. Raw DOM via headless Chrome (see [[knowledge/lis_dom_scraping]]).

**Headline:** the X-Ray Section 9 bug count of **9 is the actual, full-window crossover-week bug count.** Confirmed zero hidden meeting-misrouted rows, zero phantom rows, zero silent bill-drops. The 51 bills in HISTORY-but-not-in-Sheet1 are all Fiscal-Impact-Statement-only entries correctly filtered as noise. See [[testing/crossover_audit]] for full findings table, 9-bug exemplars with LIS committee attributions, and class distribution.

**Class distribution:**
- **Class 1 (Schedule API gap at full committee):** 4 bugs — HB111/HB505/HB972 (Feb 12 H-P&E meeting), HB609 (Feb 12 H-Finance). Two upstream API gaps = 4 of 9 bugs. Fixing the secondary time source collapses Class 1 entirely.
- **Class 2 (Subcommittee attribution miss):** 5 bugs — HB24, HB1266, HB1372, SB494, SB555. State-machine / attribution bugs in worker's subcommittee resolution path.

**Instrumentation observation (not a bug, but worth noting):** 423 admin-verb rows are tagged `⏱️ [NO_SCHEDULE_MATCH]` because the worker runs the schedule lookup on every row regardless of verb class. Consider narrowing the tag to rows whose verb class implied a meeting was expected. Logged to [[state/open_anti_patterns]] as item #8.

**Artifacts checked in:**
- `docs/testing/crossover_lis_truth.json` — 1.3 MB, 6,885 actions structured per-bill
- `docs/testing/crossover_audit_findings.json` — 180 KB, categorized discrepancies
- `tools/crossover_audit/` — reproducible pipeline

**Lesson learned (scraping):** LIS bill-details DOM uses nested `<span>` tags in descriptions. A naive regex over the history-event-row block over-captures across row boundaries. The fix (row-split BEFORE parsing) is now documented in [[knowledge/lis_dom_scraping]] so the next scraping task doesn't repeat the mistake. Caught during audit dry-run by noticing empty LIS truth on bills that clearly had HISTORY activity — investigating revealed the regex bug rather than accepting "LIS is missing rows."

Next: PR-C scoping. Two-track fix — secondary time source for Class 1 (4 bugs) + subcommittee resolution fix for Class 2 (5 bugs). No code written until audit is reviewed.

## [2026-04-16] pr | PR-B opened — metrics visibility + source-miss diagnostic hint

Branch: `claude/pr-b-metrics-visibility-diagnostic` from `origin/main` post-PR#25-merge. Two focused fixes cashing in on real-world behavior of PR-A:

1. **Viewport slice was filtering out the `SYSTEM_METRICS` row.** PR-A stamped the metrics row with `Date=today` (run timestamp) so it'd write on every cycle. The end-of-pipeline viewport slice then filtered `final_df` to `scrape_start <= Date <= scrape_end` (= Feb 9-13, 2026), silently dropping the `Date=2026-04-16` metrics row before Sheet1. X-Ray Section 0 rendered blank even though upstream counters were correct. Fix: exempt `Origin in {system_alert, system_metrics}` from the window mask (`final_df = final_df[in_window | is_system]`). Logged as [[failures/gemini_review_patterns]] #36.
2. **NO_SCHEDULE_MATCH rows now carry a `DiagnosticHint` column.** New pre-loop dict `api_schedule_by_date` indexes `api_schedule_map` by date. `_build_diagnostic_hint()` produces `loc='<bill_locations[bill]>'; api_<date>=[<committee>@<time>; ...]` (nearest-3 same-chamber candidates). Populated in both `journal_default` and `floor_miss` branches; empty string for sourced rows. Added to all 9 `master_events.append` sites (4 API-sourced = `""`, 1 CSV branch = populated, plus push_system_alert / SYSTEM_METRICS / cache_alert meta sites). X-Ray Sections 4d, 9 sample rows, and the Ledger Health Check "meeting actions in Ledger" expander now surface the column when present. Sheet1 schema: 10 → 11 columns. Logged as [[failures/gemini_review_patterns]] #37.

Also re-synced `calendar_xray.py` with `pages/ray2.py` and updated [[architecture/calendar_pipeline]] schema section.

## [2026-04-16] pr | PR#25 merged — worker source-miss visibility instrumentation (PR-A)

Merged into `main` after Gemini review follow-up commits. Worker ran successfully with the new counters (mutual-exclusive denominator = 63,081). The `SYSTEM_METRICS` row never reached Sheet1 because of the viewport-slice bug documented in PR-B's entry above.

## [2026-04-16] pr | PR#25 updated — Gemini review follow-up for PR-A

Five issues from Gemini review of PR#25, logged as [[failures/gemini_review_patterns]] #31-#35:

1. **#31 Counter double-counting.** `source_miss_counts` split into mutually-exclusive denominator buckets (`sourced_api`, `sourced_convene`, `unsourced_journal`, `floor_anchor_miss`, `dropped_noise` — sum to `total_processed`) and orthogonal tag counters (`unsourced_anchor`, `dropped_ephemeral` — overlap intentional). `unsourced_anchor` now fires on every Memory-Anchor row regardless of time resolution.
2. **#32 Origin/metric parity.** Floor transitions from `api_schedule` to `convene_anchor` now decrement `sourced_api` and increment `sourced_convene`, so row Origin matches the counter.
3. **#33 Dedup-key scope.** `no_match` alert key now includes `bill_num` per [[workflow/source_miss_visibility]].
4. **#34 Redundant import.** Removed local `import json as _json`; use module-level `json`.
5. **#35 Origin field parity.** Added `Origin="api_schedule"` to 4 `master_events.append` sites in the Schedule API branch.

X-Ray Section 0 rewritten to visually separate denominator buckets (with sum-check warning on drift) from orthogonal tag counters.

## [2026-04-16] pr | PR-A opened — worker source-miss visibility instrumentation

Branch: `claude/worker-source-miss-visibility`. Instrumentation-only PR that cashes in all five items from [[state/open_anti_patterns]]:

1. `calendar_worker.py` L756 — `except: print` cache fallback now also calls `push_system_alert(..., category="API_FAILURE", severity="WARN")`.
2. L~1201 Memory Anchor path now tags both admin and dynamic verbs (`📝 [Memory Anchor: admin]` vs `⚙️ [Memory Anchor]`).
3. L~1181 silent `"Journal Entry"` default replaced with `"⏱️ [NO_SCHEDULE_MATCH]"` tag + deduped `push_system_alert` (category `TIMING_LAG`, severity `WARN`).
4. L~1340 ephemeral-filter silent `continue` replaced with counter + deduped alert (category `DATA_ANOMALY`, severity `INFO`).
5. Ledger-Updates rename (L~1363) now gates off a new `Origin` column (`journal_default` / `floor_miss` / `api_schedule` / `convene_anchor` / `system_alert`) instead of the renamed Time string, so provenance survives.

Also: `push_system_alert` extended to accept `category`, `severity`, and `dedup_key`; a JSON-encoded `SYSTEM_METRICS` row is written to Sheet1 per run. X-Ray `pages/ray2.py` gains Section 0 rendering the denominator (total / sourced / unsourced / dropped). `calendar_xray.py` re-synced.

Expected effect: bug count goes *up* short-term because previously-silent rows now surface with visible tags. That is the point — per [[failures/pr22_post_mortem]], the old metric was rewarding silencing.

## [2026-04-16] pr | PR#24 opened — Gemini review follow-up for the brain PR

Four doc fixes flagged by Gemini on PR#23: (1) removed placeholder `[LLM-Wiki](https://github.com/)` link in `docs/README.md`; (2) aligned severity labels in `docs/state/open_anti_patterns.md` to CLAUDE.md Standard #4 (`INFO`/`WARN`/`CRITICAL`); (3) `<mod>` → `<module>` in CLAUDE.md pre-push audit point 8 for consistency with [[workflow/three_phase_protocol]]; (4) corrected the log entry below to cite the actual migrated files (`feedback_always_push.md`, `project_tba_discovery.md`) instead of just the `MEMORY.md` index. Also untangled stale "PR#23" references in [[state/current_status]] and [[state/open_anti_patterns]] that referred to the instrumentation PR before PR#23 was assigned to the brain PR.

## [2026-04-16] pr | PR#23 merged — Obsidian brain consolidation

Vault is live on `main`. Primary checkout now carries `docs/` as the project brain. Follow-up fixes in PR#24 address Gemini review.

## [2026-04-16] decision | Consolidated brain into Obsidian-compatible wiki

Restructured `docs/` as an Obsidian vault. Created `index.md`, `log.md`, `state/`, and `workflow/` subtrees. Migrated the two entries from global `~/.claude/.../memory/` (`feedback_always_push.md` and `project_tba_discovery.md`, both indexed by `MEMORY.md`) into `[[workflow/push_and_pr]]` and `[[knowledge/tba_times]]`. Updated [[README]] as the vault entry point. CLAUDE.md now routes all persistent memory writes here, not to global memory.

Trigger: user reported scattered knowledge between `docs/` and hidden `~/.claude/` memory folder; adopting the LLM-Wiki pattern with Obsidian as visual interface.

## [2026-04-16] post-mortem | PR#22 framework failure — "only measuring the bugs we wanted"

See [[failures/pr22_post_mortem]] and [[state/open_anti_patterns]]. User invalidated PR#22's reclassification premise (members really do offer amendments in committee). Audit of `calendar_worker.py` found the anti-pattern PR#22 inherited is still live in four places: line ~1181 (silent "Journal Entry" default), lines ~1248-1261 (ephemeral `continue`), lines ~1158-1167 (selective Memory Anchor tag), lines ~1269-1275 (Journal → Ledger rename without provenance). Section 9 bug metric was measuring symptoms, not source-miss rate.

New workflow rule created: [[workflow/source_miss_visibility]]. PR#22 to be closed unmerged by user.

## [2026-04-15] pr | PR#22 opened — `[chamber] (sub)committee offered` as admin override

Reclassified 8 crossover-week "offered" rows as administrative via `ADMIN_OVERRIDE_PATTERNS`. Premise later invalidated by user pushback. Logged as [[failures/assumptions_audit]] entry #41. To be closed.

## [2026-04-14] pr | PR#21 merged — `_REPO_ROOT` file-probe replaces dir-name check

Gemini PR#20 review flagged brittle `_HERE.name == "pages"` check. Replaced with `(_HERE / "investigation_config.py").exists()` probe. Logged as [[failures/gemini_review_patterns]] pattern #30.

## [2026-04-13] pr | PR#20 merged — sys.path prelude fix for `pages/ray2.py`

Streamlit subpage threw `ModuleNotFoundError: investigation_config` on deploy after PR#19. Added sys.path prelude. Logged as [[failures/assumptions_audit]] #39.

## [2026-04-12] pr | PR#19 merged — window alignment via `investigation_config.py`

Rolling `scrape_end = now + timedelta(days=7)` was expanding the bug count mechanically every run. PR#14-18 metrics were polluted. Pinned to `INVESTIGATION_START/END = Feb 9-13` in a single module, imported by worker + X-Ray. Logged as [[failures/assumptions_audit]] #38.

## [2026-04-11] pr | PR#18 merged — "prefiled and ordered printed" → admin override

2,042 prefiled rows were misclassifying as meetings due to substring "offered". Added to `ADMIN_OVERRIDE_PATTERNS`. Logged as [[failures/assumptions_audit]] #37. (Note: #37's call about bare "committee offered" being a meeting was later invalidated by #41.)

## [2026-04-10] pr | PR#17 merged — subcommittee vote refid regex fix

`resolve_committee_from_refid()` regex missed H14003V... format (parent + 3-digit subcommittee + V + vote ID). 1,637 subcommittee refids were unlocked. Logged as [[failures/assumptions_audit]] #36.

## [2026-04-09] pr | PR#16 merged — sub-panel schedule matching + overwrite protection

Added Strategy B in `find_api_schedule_match` for hyphen-suffixed sub-panels (HCJ-Civil, etc.) that aren't in Committee API. Added map overwrite protection so "Time TBA" can't clobber concrete times. Logged as [[failures/assumptions_audit]] #34, #35.

## [2026-04-08] pr | PR#15 merged — whitespace normalization + session marker fallback

Session marker fallback now overwrites non-concrete placeholder times. `_is_non_concrete_time` hoisted to module level. Logged as [[failures/assumptions_audit]] #32, #33.

## Earlier entries

Pre-2026-04-08 PR history is captured in the [[testing/crossover_week_baseline]] progress tracker table and in numbered entries in [[failures/assumptions_audit]]. This log was backfilled starting 2026-04-16 and is append-only from that date forward.
