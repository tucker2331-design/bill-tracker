---
tags: [log, meta]
updated: 2026-06-21
status: active
---

# Project Log

Append-only, reverse-chronological (newest at top). Each entry opens with `## [YYYY-MM-DD] <kind> | <title>` so `grep "^## \[" log.md | head -20` gives a parseable timeline.

## [2026-07-17] research | reading queue CLOSED — "the bill page" is the Bill object's DETAIL representation

Owner: *"what is the bill page? also finish reading before the mock up."* Both fair hits. I had been using
"the bill page" as if it were established vocabulary for something that **does not exist**, and the reading
queue still had three ⏳ items.

**The honest answer to the question.** There is no bill page. A bill's only representation today is the
**card** (inside Today/Calendar/Search); it expands in place and the drill ends there. **Verified against the
code, not assumed:** no router dependency, no `pushState`, no hash routing, no `<Route>` in `web/src` — so a
bill has **no URL** and the org cannot link one. What IS decided is
[[architecture/strategic_tools_placement]] (2026-07-15): the whip/committee tools live on "a dedicated surface
entered FROM the card, never ON it" — that decision created the need for a container but never named it or
pinned its shape ("a per-bill (or per-committee) workspace"). "Bill page" was my name for that container, and
saying "the war room is a region of the bill page" stacked an undecided container plus an unproven claim into
one phrase and presented it as a finding. Corrected.

**Then the reading answered it properly** (§1b of [[design/object_page_patterns]]). ORCA's **Round 4 —
Representation** produces "cards, details, lists, landing pages": every core object gets *several*
representations. We built the Bill's **card** and its **lists** and **never built its detail**. So the real
question is not "should we add a page?" but **"why does our core object have no detail view?"** — which is the
same reason it has no URL. The card↔page relation is settled by the same step: two representations of one
object, nothing replaced.

Two more ORCA transfers: the **Nested-Object Matrix** ("relationships pave the way for navigation paths") is
the honest tool for the tab-vs-region question instead of my reasoning-by-analogy; and the **CTA Matrix**
(object × role, actions in the intersections) **is a permission model**, independently corroborating that the
trust boundary and the Access boundary coincide. Produce both before writing a D1 route. Round 3 also says the
**MVP cut (D4, still open) should be made by downgrading/eliminating OBJECTS**, not by shortening a feature list.

**The gap that mattered most was one I hadn't ranked:** the war room is the product's **first surface anyone
types into**, and we had **zero input canon**. Now closed — [[design/information_display]] §5c:
- **P21 · affordance ≠ signifier** (Norman). *"Signifiers are of far more importance to designers than are
  affordances."* **We already paid for this lesson:** the landing-page panels were genuinely scrollable and the
  owner said *"i dont see any indication that there is more info scrollable"* — a real affordance with no
  signifier; the CSS-only shadow failed the same way; the fade+chevron (#216) was the signifier. The rule now
  has a name and applies next to the war room's editable cells.
- **P22 · form design** (Wroblewski/Penzo eye-tracking): top-aligned labels are fastest (one fixation covers
  label+field); left-aligned are slowest by fixation count but right when the user *should* deliberate over
  each input — the documented exception for the whip board; primary action gets weight, secondary is quiet;
  no decoration around inputs.

**Two corrections to my own prior claims:** (1) roster data — I said "zero ingested" in a way that implied
unavailable; precisely, we ingest none of it but it is **confirmed AVAILABLE on our LIS key**. An unbuilt
ingest, not a missing source. (2) The queue is now closed **to the limit of free primary sources** — Prater's
book/course, Wroblewski's and Norman's books are **paid and unread**, marked 🔒 rather than pretended away.

Residual (open_loop): the **roster ROW** still defeats the region-level trust partition (LIS member + our whip
mark in one row) — a mockup question. Next: the mockup.

## [2026-07-17] research | central-object page canon gap FILLED — the war room is a REGION, not a tab

Owner's instruction: *"use your existing research on design, look in the brain, then look for new research…
you're only as smart as every smart human, and every smart human wrote shit down in books"* — then, when I
offered to start drawing: *"finish reading first."* So the reading finished before any mockup.

Landed in [[design/object_page_patterns]] (+ the actionable rule distilled to [[design/information_display]]
§5b/P20, canon table row added). Five sources: OOUX/ORCA (Prater), the Salesforce record page, NN/G on tabs,
Atlassian's published Jira issue-view spec, and the provenance-in-UI literature.

Four findings that change what we build:
1. **Our "13 per-bill features" are mostly OBJECTS and relationships, not features** (OOUX). That's the real
   answer to "won't the workspace become the new junk drawer?" — structure by nouns and new capability lands
   as a new related object/attribute with an obvious home. Structure by features and it silts up.
2. **The sidebar-vs-inline question was mis-framed.** Jira/GitHub/Linear split **control vs content**, not
   attribute vs content. Our read-only LIS facts → the pinned highlights strip (Salesforce "compact layout",
   which also VALIDATES the card↔page one-source rule — the card **stays**); only our editable org attributes
   behave like Jira sidebar fields. No generic attribute sidebar needed.
3. **The provenance literature does NOT transfer** — [ProvenanceLens](https://arxiv.org/abs/2505.11784) studies
   *analytic* provenance (recency/frequency of your own clicks), not *source* provenance. Logged so nobody
   re-runs the search. The partition instead resolves from canon we already hold: **position, not colour or
   opacity** (opacity would falsely read "provisional" about the org's highest-value intel; colour is reserved
   by P10 for exceptions, and the org layer is permanent, not exceptional).
4. **The trust line and the permission line are the SAME line** — the org region is exactly what Access gates
   and what Worker+D1 writes; the LIS region is public/read-only. One boundary carries both. This answers the
   owner's open question (*"i'm not sure if it gets its own tab or stays on the home page"*): **the war room
   isn't a tab — it's the org-owned REGION of the bill page.** Prater predicted it ("CTAs settle permissions
   early"). NN/G independently forbids tabs here anyway: hearing prep needs time + roster + position at once,
   which is the comparison case tabs fail.

Honest residuals: Prater's book/course still unread in full (the ORCA method is digested from her primary
material and is what the page applies) — worth the full object-map exercise when roster data exists, and
**zero member/committee roster is ingested today**, the hard blocker under the whip board. And one genuinely
unresolved spot flagged rather than hand-waved: a **committee roster row mixes LIS fact (the member) with org
intel (our whip mark) in the same row** — spatial partition works at region level, breaks at row level. Rule
that must hold: no single cell blends the two. That's a mockup question.

Next: the mockup, per the owner's standing rule (*"once you get to the war room do a mock up before you start
writing code"*).

## [2026-07-16] pr | #226 MERGED — standards audit repaired the incident-log (owner: "are you sure everything is up to standard?")

Owner challenged whether the build wave was actually hardened. Audit found the ONE real gap: #225
(incident-log) had merged past 3 Gemini findings (1 commit, no fold-in). Real bug: the "days since a data
incident" counter required a full-width row, but Sheets trims trailing-empty cells, so an incident logged
without a summary read back short and was SKIPPED — the counter could show "safe" while an incident existed
(a silent under-report of the exact trust metric the feature exists for). #226 fixed it + folded the review
in full: len>=3 consistency; narrow WorksheetNotFound; space-separated timestamp parse; and (round-2
CodeRabbit Critical) the malformed-row skip on the trust path is now VISIBLE (empty=silent padding,
non-empty-unreadable=collected + DATA_ANOMALY alert, Standard #9). 9→15 goldens, each proving the old code
failed. Everything else in the wave (#219 live-verified, #220/#221 parity, #222 histogram, #223/#224 differ
26 goldens) held up. Process lesson reinforced: [[workflow/hardening_is_non_negotiable]] — "done" means
bot-folded + tested, and never merge before reading the review, even under "go fast".

## [2026-07-12] pr | #215 MERGED — §9 anchor ladder re-merged (exonerated) + rung telemetry actually folded into SYSTEM_METRICS

The §9 anchor ladder is live again ([PR #215](https://github.com/tucker2331-design/bill-tracker/pull/215)),
re-validated at merge: SAFETY 0/2,889 published clocks move, RESOLUTION 449/450 relative rows concrete, rung
telemetry `chamber 16 · parent 3 · sibling 1 · unresolved 1`. Closed a #211 doc/code gap (the rung counters
were documented as "folded into SYSTEM_METRICS" but no fold site existed — `anchor_unresolved` is now a real
standing drift canary, steady state 1). Gemini fold-in: exact parent-HEAD lineage match in `_committee_parent`
+ parent excluded from the sibling rung — both re-measured behavior-neutral on live data. Renumbered the new
UnboundLocalError lesson to audit #105 (#104 was already the gspread entry in the reverted docs, now restored).
`WORKER_OUTPUT_LOGIC_VERSION=2026-07-12.2`.

## [2026-07-15] session | BUILD WAVE executed — 6 PRs; ledger differ + incident mechanism proven, live-wiring honestly 2027-gated

Fable executed the build wave ([[audits/build_wave_2026-07/README]]) end to end. Shipped + merged:
- **#220/#221 — LIS endpoint-parity audit** (TASK 2 P2): `tools/parity/endpoint_audit.py` + manifest + weekly
  workflow + 9 goldens. LIS exposes ~249 API routes; we consume 8; the 51 parked ones ARE the product's
  expansion map (fiscal notes, bill text, member contacts, floor calendar, minutes oracle…). Converges to
  new=0. Fold-in: IGNORECASE + utf-8.
- **#222 — docket-drop histogram** (TASK 4a): `tools/parity/witness_histogram.py` + on-demand workflow.
  HONEST correction: the "10 PM" claim was unmeasured and CAN'T be measured now (2026 session past the
  witness's 90-day retention + sharded to VA·Ops) → measures in-season 2027; brain copy now says "late
  evening". Fold-in: or-[], exit-code-on-failure, skipped-count, kinds-mix.
- **#223/#224 — Change Ledger differ** (TASK 1 L1): `tools/change_ledger/differ.py`, pure + 26 goldens, keyed
  on structural identity so a vote-tally correction is a true history_EDITED (same refid), not remove+add;
  no-refid changes honestly surface as add+remove. Live wiring + the Changes tab are **2027-in-season-gated**
  (a change-feed can't be validated on static data; a hollow empty tab pre-launch is dishonest) — full plan
  in [[architecture/change_ledger]] (isolation-first: a workflow_run-after-worker job, worker UNTOUCHED).
  Fold-in: defensive input guards.
- **#225 — incident-counter mechanism** (TASK 2 P1): `tools/incident_log/log.py` (fail-open record_incident,
  genesis-aware days_since) + 9 goldens + [[architecture/incident_counter]]. DEFINITION + public display +
  guard-wiring are owner decisions (surfaced, not guessed) — unverifiable writes into the accuracy sentinel
  would violate verify-the-row.
- **TASK 3 (war-room memo)** → [[ideas/war_room_scoping]] (5 owner decisions, no build).

Meta-lesson reinforced: the worker was NOT touched by any of this (the accuracy path literally cannot
regress); every Sheets-writing/in-season feature was either shipped read-only, or built-proven-core +
airtight-spec with its validation gate documented, rather than shipped blind. No local creds → all Sheets
writes are CI-gated; stated honestly on each PR.

## [2026-07-13] pr | #219 MERGED — the card bundle LIVE (Next-meeting row, dashed unplaceable, grey crossover, patron, 2-step untrack)

All five owner-locked decisions shipped in one PR and verified ON PRODUCTION: HB463's list card reads
"HB463 · Cohen" and its card shows "Tue, Jul 21 · 10:00 AM · in 7 days — VA FOIA Advisory Council ·
📄 Agenda · ▶ Watch live" (a real interim meeting; real links) — the trip to the Calendar tab is gone.
Amber row fires only <48h of a CONCRETE clock (minutesUntil goldens: TBA/unresolved/past → null); the
calendar's unplaceable marker moved to the dashed border (amber = ONE meaning site-wide now); crossed-over
chip → neutral grey; two-step untrack verified incl. the multi-star capture-phase fix (Gemini caught one
confirm sticking open when clicking another bill's star). Fold-ins: parseLisDate reuse ×3, capture-phase
click-outside, patron regex hoist. Console clean, tsc clean, both bot rounds green.

**HANDOFF: the next work is specced for Opus in [[audits/build_wave_2026-07/README]]** — Change Ledger
(L1 differ → L2 Changes tab), parity sentinel + days-since-incident counter (P1–P3), war-room scoping
memo (owner-gated), witness histogram. Owner directive: Fable plans, Opus executes.

## [2026-07-13] design | Mockup regression caught by owner — the change-register pattern codified

The first Change-Ledger mockup reproduced AI-tell #1 (rainbow pastel kind-chips on routine rows) despite the
canon sitting in the vault — owner rejected it on sight. Re-read [[design/dashboard_and_visual_language]] +
[[design/information_display]], researched register archetypes (bank statements, Stripe events, GitHub audit
log, git diff, Gmail's unread boundary), codified "The change-register pattern" into the visual-language page,
and rebuilt: Ledger v2 is a monochrome register on the product's own feedrow anatomy (accent time · small-caps
grey kind column · struck-old→bold-new as the only emphasis); the card mockups were de-chipped (countdown =
muted text; urgency = the two earned amber states). Procedural rule added: mockups obey the canon — read the
design pages BEFORE drawing.

## [2026-07-13] decision | Ideation round 3 — V-series verdicts; two elevations (change ledger, LIS parity)

Owner triaged the V-series: plain-English → later+rework (coverage/fallback dependency = our own
silent-fallback doctrine applied to UX); Play-Caller → rejected as prescriptive, kernel kept as the bill-card
Now→Next section (4 mockups delivered: https://claude.ai/code/artifact/f1ef8d4e-ed6e-455a-be80-72bed4d02b44);
constituent matching → delayed (privacy + possible incumbent tool); war room → explain-then-scope; fact
sheet → data-half already IS the product; substitute diff → GO as DETERMINISTIC diff (no AI dependency);
momentum cards → parked. Two ELEVATIONS: (1) the CHANGE LEDGER — row-level "what changed since you last
looked" incl. LIS corrections (hash infra exists) + schedule deltas (witness exists); (2) the PARITY
REFRAME — goal is "everything LIS has, always": LIS-parity sentinel + public days-since-incident counter
counting accuracy AND parity incidents. Keep the 4 health rings. Full detail
[[ideas/lobbyist_jtbd_ideation]] §8b. Next: order the to-do + scope first items.

## [2026-07-13] decision | Ideation round 2 — the volunteer-advocacy-org persona (owner feedback)

Owner feedback on the zoom-out: A/C/D perfect (A's 10 PM docket claim flagged as unmeasured → witness-
histogram measurement queued), B/F explained deeper, E = single-org first (matches locked B1), G challenged
on credibility ("will the trust claim hold up?") → three pre-launch requirements logged (public days-since-
incident metric, quiet-by-default user health, hardening gate incl. 2027 cold-start). THE BIG REFRAME: the
real client is an advocacy org that writes/supports its own bills, staffed by volunteers/young people →
new V-series feature set in [[ideas/lobbyist_jtbd_ideation]] §8a (Play-Caller action windows, plain-English
mode, constituent matching, war room, verified fact sheets, momentum cards, org-as-drafter kit). Positioning:
"the experienced lobbyist they don't have" — intelligence+guidance for non-experts, a category neither
enterprise incumbents nor mass-advocacy megaphones own.

## [2026-07-13] decision | Zoom-out ideation session — the lobbyist job map + commercial moat (owner-requested)

Owner: "assume the role of an experienced lobbyist and bill writer… be expansive… we can narrow in."
Ran JTBD + year-in-the-life + Kano + working-backwards + premortem against fresh competitive research
(Quorum/FiscalNote/Plural/USLege/VPAP + bill-passage-prediction literature). Output: [[ideas/lobbyist_jtbd_ideation]]
— 4 personas, the VA annual cycle's pains, ~30 ideas in 7 buckets (session-sprint tools, text intelligence,
relationship layer, prediction, client workflow, coverage expansion, trust-as-moat), the white-space analysis
(deep-single-state + provable accuracy + contract-lobbyist segment vs enterprise incumbents), business-model
sketches, premortem, and a 6-item strawman shortlist. NEXT: owner narrows.

## [2026-07-12] pr | #218 MERGED — scroll cue made VISIBLE + pipeline legend simplified (owner UI feedback)

Owner couldn't see the #216 scroll affordance on the live site — the CSS-only scroll-shadow deployed fine but
was too subtle to read (a failed affordance is no affordance). Replaced with an obvious cue: content fades into
the panel surface + a bobbing `⌄` chevron, shown ONLY while the panel can scroll down and gone at the bottom
(`useScrollCue`: scroll + ResizeObserver + MutationObserver). Bots (Gemini + CodeRabbit, Major) caught that a
lone ResizeObserver misses content swaps in a height-constrained panel (feed paging / async load) — folded in
the MutationObserver, verified in isolation (content grew with no scroll/resize → cue recomputed on). Also cut
the confusing pipeline legend math ("all ✕ sum to 1,253 (811 died + 442 carried over)") → "✕ = a bill that
ended here (died or carried over)"; the Outcome tiles already carry the totals. **Live-verified on the deployed
site** (screenshot): fade + chevron render when the feed overflows, hidden when it fits; legend updated.

## [2026-07-12] pr | #217 MERGED — label-based agenda-FETCH target (the last VA queue item; Section-9-adjacent)

The bill-extraction FETCH no longer mines livestream/registration pages for bill numbers. `_agenda_fetch_target`
(label-based, mirrors `_extract_meeting_links`) replaces the first-href heuristic: real agenda/docket anchor →
committee homepage fallback → nothing (never a video/notice). Measured live before/after (session 20261, 3,533
rows): old heuristic on a video/registration host **298×**; new selector **retargets 82** (→ the real agenda PDF),
**drops 15** (registration/hearing-notice), **0** real committee agendas lost (the blob "drops" are budget-hearing
bulletins). `WORKER_OUTPUT_LOGIC_VERSION` → `2026-07-12.3`; 8 golden cases (29 total); prepush output-anchors +2.
Gemini fold-in: `startswith` over `re.match` on the per-anchor hot loop. Closes [[state/open_anti_patterns]] #13 —
**the VA to-do is now clear.** Also this session: [[scroll-affordance PR #216]] merged (CSS scroll cue, Gemini +
CodeRabbit folded in), and the owner's Google Drive was reorganized (4 live sheets grouped + the production sheet
renamed off "Test Mastermind" → "VA · Live").

## [2026-07-12] pr | #214 MERGED — agenda links re-shipped; the 0→66 regression ROOT-CAUSED: an UnboundLocalError wearing an API-outage costume

The three-revert mystery is solved ([[failures/assumptions_audit#105]]): the agenda-links capture block
referenced `normalized_name` 26 lines before its binding → `UnboundLocalError` on the first meeting row →
the schedule block's broad `except` alerted it as "LIS Schedule API failed" (OFFLINE) → schedule ingestion
died (skeleton rows −2,713, `timeclass_*` absent, convene anchors lost) → `meeting_unsourced=66`, breaker
trip. All three trip cycles carry the literal alert row in `Metrics_History`; §9 and cache-warmth were both
innocent; the breaker was right every time. Shipped in [#214](https://github.com/tucker2331-design/bill-tracker/pull/214):
the placement fix, the SPLIT except (a code bug now alerts CRITICAL/UNKNOWN with type+line — no more OFFLINE
costume), pre-push check 17 (pyflakes `undefined name` gate; flags the original at 5625:38; pinned 3.4.0 in
CI), `agenda_links_meetings(+_seen)` counters. Live post-merge cycle verified: `meeting_unsourced=0`, rows
61,047, `agenda_links_meetings=859/1,684`, real agenda PDFs + livestreams on Sheet1 rows, breaker clear.
Bot fold-ins: [[failures/gemini_review_patterns]] #55 (substring filter collides with sibling message wording)
+ #56 (bots re-post stale reviews). `WORKER_OUTPUT_LOGIC_VERSION=2026-07-12.1`.

## [2026-07-11] verify | Hotfix confirmed healthy — known-good FULL recompute = meeting_unsourced 0, clean write

The post-hotfix worker cycle (21:36) was a FULL recompute (shared_changed=True, 3645 recomputed) and wrote
Sheet1 cleanly at `meeting_unsourced=0`, breaker clear (W1 empty), red ring gone — only the benign blank-rows
INFO note remains. Known-good full-recompute is now 0 on BOTH the 17:05 and 21:36 cycles, so the re-ship's 66
was more likely a real effect than cache-warmth noise — the offline STM diagnosis (good-vs-new on frozen
inputs) is the way to settle it definitively before agenda-cols/§9 re-attempt. (One transient Google Sheets
503 on the first re-trigger — retried, unrelated.)

## [2026-07-11] fix | WORKER HOTFIX — revert agenda-cols worker (re-ship also tripped the breaker; §9 was NOT the cause)

The re-ship (#212, agenda cols, §9 reverted) tripped the breaker on its first full recompute at
`meeting_unsourced=66` — the SAME number the §9 merge hit. So §9 was never the cause: `build_time_graph`
was proven byte-identical to known-good (0 diffs), the agenda cols are additive + applied to `final_df`
AFTER `meeting_unsourced` is counted in `_append_event`, and the terminal-skip deletion is a no-op
(`IsTerminal` FALSE for all 3,645 bills). By elimination the worker CODE is innocent; the 0-vs-66 difference
tracks the **LegEvent cache state** (500-bill/cycle refresh cap → off-season a full recompute's
`meeting_unsourced` depends on cache warmth). Leading hypothesis: off-season cache-warmth fluctuation +
too-tight breaker `Y2=0` baseline, NOT a regression ([[failures/assumptions_audit#101]]).

Action: reverted ONLY `calendar_worker.py` to known-good (version `2026-07-07.1`, WITH the witness fix) so
cycles go incremental and reuse the healthy `meeting_unsourced=0` state — breaker stops tripping, red ring
stops, site updates. Kept the breaker-SAFE frontend (auto-refresh, Option-A, agenda card scaffold) + B-7 guard
+ witness fix — all LIVE. Removed the two worker-only tests (`test_meeting_links`, `test_clean_legevent_cell`)
whose subjects are reverted + unregistered from CI.

Deferred (safe in git, `775e074` / `7671e18`): the agenda-links WORKER columns + §9 anchor ladder. Both wait on
an OFFLINE STM diagnosis (good-vs-new on frozen identical LegEvent-cache inputs) to settle cache-warmth vs real
gap, plus a breaker off-season-baseline review. Lesson: two wrong diagnoses (§9, then agenda) — a metric moving
under a code change is not proof the code caused it; hold the inputs constant before attributing.

## [2026-07-11] pr | RE-SHIP: #211 minus §9 — agenda links + auto-refresh + witness + B-7 shipped, §9 held back

After reverting #211 for the `meeting_unsourced` 0→66 regression (entry below), reconstructed "the merge minus
the §9 resolution change" on `claude/va-reship`: brought the full merge tree, then AST-spliced the known-good
`_resolve_one_day` + `build_time_graph` back in and removed the §9 module globals (`ANCHOR_RUNG_COUNTS`,
`_SELF_REF_RE`). **Proof it's safe:** ran `build_time_graph` spliced-vs-known-good on the live Schedule API —
**0 diffs**, so the resolution path is byte-behavior-identical and `meeting_unsourced` stays 0.

Kept + re-shipped: meeting/agenda links (worker additive AgendaURL/MeetingURL cols + Calendar card, future &
past), freshness-gated auto-refresh + transient RefreshNotice, the gspread-6 witness fix, the B-7 stranded-work
guard (`tools/open_loops.py` + pre-push point 16), the READY-debt cleanups, and the Gemini/CodeRabbit fold-in
(RefreshNotice unmount + `_meeting_links` overwrite guard + others — [[failures/gemini_review_patterns]] #53/#54).
Removed `anchor_ladder_test.py` (its §9 subject is reverted) and unregistered it from CI. `WORKER_OUTPUT_LOGIC_VERSION`
bumped for the additive columns. Full test suite + web typecheck + prepush audit green.

Held back: the §9 anchor ladder (the sole regression source). The 19 unplaceables stay honestly shown as
"⚠ unplaceable". Redo scoped in [[ideas/calendar_chain_ordering]] §9 — needs an STM-level `meeting_unsourced`
gate first. See [[state/current_status]] NOW.

## [2026-07-11] pr | #211 MERGED then REVERTED — §9 change regressed `meeting_unsourced` 0→66; witness fix kept

A large PR (§9 anchor ladder + `_committee_parent` multiset fix, meeting/agenda links, auto-refresh, de-AI
polish, B-7 stranded-work guard, gspread-6 witness fix, + folded-in Gemini/CodeRabbit reviews) merged to main
(`775e074`) with all CI green. The FIRST full-recompute worker cycle on the new code tripped the circuit
breaker: **`meeting_unsourced` 0→66** (`Metrics_History`: 0 every prior cycle), `sourced_convene` −1,275,
`floor_anchor_miss` +693. The breaker refused the Sheet1 overwrite → **no bad data shipped**, live site held on
last-known-good.

Root: the §9 validation gate (`validate_relative_chains.py`) checked SCHEDULE-level resolution
(`relative_unresolved` 19→1, SAFETY 0/2,889) but NOT the BILL-ACTION-level metric `meeting_unsourced` that
actually defines §9 success — a blind spot. Resolving relative meetings to different times/committees shifted
downstream bill-action sourcing. Details: [[failures/assumptions_audit#101]].

**Action:** reverted the merge (`756ca47`) to restore known-good main, then re-applied ONLY the isolated,
unrelated **witness gspread-6 fix** (`d1fa46d`, [[failures/assumptions_audit#100]]) so the daily
"Couldn't auto-move Schedule_Witness" CRITICAL stays fixed. Triggered a clean worker run to resume writes.
The §9 + agenda + auto-refresh + frontend + B-7 work is preserved in git (merge `775e074`) for a corrected
re-merge once the `meeting_unsourced` regression is diagnosed and the gate extended to cover it. See
[[state/current_status]] NOW.

## [2026-07-07] pr | #209 MERGED — Health alerts = STATE not stream + witness auto-shard (zero-touch) + de-AI pass

**MERGED to main (squash) 2026-07-07** after Gemini fold-in: Gemini caught a CRITICAL in the auto-shard —
the recovery flag reconciled behind the same `total>=threshold` gate the move drives below the line (split-brain
if the flag write failed); fixed to reconcile from the tab's ACTUAL location, +2 regression tests ([[failures/assumptions_audit]]
#98, = pre-push audit #11). Also a real regex bug (`\b[0-9]` never matched `SB587` → per-bill alerts didn't
collapse; dropped `\b`, cleared history 300→18 on live data — [[failures/gemini_review_patterns]] #51/#52). One
Gemini finding (`useState` unimported) was a false positive — verified imported, skipped. CodeRabbit hung
"in progress" with 0 findings; merged on green functional CI (golden/prepush/structural/Cloudflare) per the
owner's "merge when reviews are done, don't stop for this again."

Owner (2026-07-07): the alerts "need real thinking and fixing… consider how a human looks at this / how other
dashboards do things"; the witness shard "shouldn't need manual input — will it always need that?"; "these
colored boxes scream AI built all over our site." Three fixes on branch `claude/health-alerts-state-not-stream`:

1. **Alerts rebuilt as state, not stream** (`web/src/views/Health.tsx`). Was a raw append-only log — nothing
   self-cleared, internal tuple dumps leaked, over-simplified labels on a wall. Now: a **verdict line**
   (all-clear by default) → only **currently-active** conditions → a **collapsed per-category** self-cleared
   history. Self-clearing derived from the latest cycle (`lastTs ≥ latestCycleTs − 6min`); conditions group by
   a normalized stem so per-bill explosions collapse; debug tails stripped. No worker change — a
   reinterpretation of the existing `Metrics_History` log. Live-verified: verdict "All clear · 1 routine
   note", 300 old alerts → 3 category lines.
2. **Witness shard is now ZERO-TOUCH** (`calendar_worker._autoshard_witness_if_full`). The worker relocates
   `Schedule_Witness` VA·Live→VA·Ops itself at 6M (copy-verify-then-delete, one-time `Sheet1!AD1` flag,
   fail-CLOSED, FYI-only). Kills the half-manual `archive.py` + `WITNESS_WORKBOOK=ops` rollout (Standard #8).
   15 unit tests (`witness_shard_test.py`). `sustainability_audit` WARN reworded → `shard-imminent`. A-2 Part 2 phase 3.
3. **De-AI visual pass** — `.hl-sev`/`.hl-breaker`/`.hl-skew`/header `.trust .pill` filled "colored boxes" +
   ●🗓✓ emoji chrome → restrained status dots + neutral text. Implements the existing [[design/reading_notes]]
   canon (Few: least-visible-means). Doctrine + offenders log: [[design/dashboard_and_visual_language]]. Bill
   outcome chips + scope toggle deliberately left (owner's aesthetic call — flagged, not silently redone).

96 pure-logic tests green (+15 new); SPA `tsc`/`eslint`/`vite build` clean.

## [2026-07-06] decision | C-8 — NY re-measured: already hardened; oracle is owner-gated

Measured `ny_bill_tracker.py` against C-8's "NY missing VA's hardening" claim (doctrine #1). NY is more
structural than the audit assumed: `_derive_outcome` reads only `signed` (bool) + `vetoMessages` (presence);
chambers ALREADY have drift canaries (`unknown_origin/action/agenda_chamber` counters → health WARN with
denominators, `chamber_raw` kept, never guessed); `UNKNOWN_STRUCTURAL_OUTCOME` already fires. `statusType`/
`statusDesc`/action-text are DISPLAY-ONLY (per docs/ny) → feed no logic, so a vocab canary on them is
low-value (can't break accuracy). **→ Did NOT add a marginal watcher (no data justification — Standard #7).**
C-8's real value is Part 2, the independent oracle (LegiScan-NY reconciliation), which needs a LegiScan API
key + terms check = **owner-gated**. Status recorded in [[audits/fable_2026-07/codebase_longevity_audit]] C-8.
**This exhausts the by-me-completable Fable queue; the remainder (A-2 Part 2 ops-workbook, C-8 oracle, CDN
inversion, PA ingestion, S-3 optional attic cleanup) needs owner infrastructure or is a multi-session build.**

## [2026-07-06] decision | B-6 — vault hygiene (measure-first: mostly moot)

Ran the B-6 checks. **0 orphans** across 78 pages (well-linked — no action; reusable orphan-check snippet
below). `next_session` already archived (B-1). The "`docs/testing/` = 1.6 MB baseline data" premise was
STALE — it's 4 small files (~38 KB), active/complete; only `crossover_week_baseline.md` lacked frontmatter →
added `status: active`. Log convention kept. B-6 marked shipped.

```python
# orphan check (docs/**/*.md with no inbound [[wikilink]]):
import os,re,glob; docs=glob.glob("docs/**/*.md",recursive=True)
names={os.path.splitext(os.path.basename(p))[0]:p for p in docs}
linked={m for p in docs for m in re.findall(r"\[\[([^\]|#]+)",open(p).read())}
print([p for s,p in names.items() if s.split("/")[-1] not in {l.split("/")[-1] for l in linked}])
```

## [2026-07-06] decision | B-2 — case-law files get a generated ## Index

`tools/reindex_caselaw.py` (stdlib, idempotent) inserts/refreshes a `## Index` (`#N — <lesson>`) at the top
of assumptions_audit.md (97 entries) + gemini_review_patterns.md (50) from the entry headers — recall drops
from a 700+-line wholesale read to ~60 lines + a grep. Re-runnable, so it's also the maintenance mechanism
(CLAUDE.md write-back rule: fix a bug → append the entry → re-run the tool). B-2 marked shipped. (Committed
to main — vault + docs-generator, no worker logic; the new prepush-audit has nothing to flag.)

## [2026-07-06] pr | #205 OPENED — machine-executable pre-push audit (B-3)

Highest rule-compliance leverage in the queue. The 15-point audit was prose (fires only when the model
thinks to apply it — #189 missed the version bump, a bot caught it a PR late, audit #96). `tools/prepush_audit.py`
(stdlib-only) now mechanically checks a diff and CI runs it every PR (`structural_tests.yml` → `prepush-audit`):
(1) an output-VALUE-affecting change with no `WORKER_OUTPUT_LOGIC_VERSION` bump FAILS — curated anchor set of
Sheet1-value-computing fns (`build_time_graph`/`_resolve_one_day`/`parse_24h_time`/`_append_event`/STM/
`classify_action`/`route_event`…), deliberately EXCLUDING gating/cadence/archive/auth so those PRs aren't
false-flagged (the exact risk I scoped for); (4) ray2↔calendar_xray divergence; (6/9) untagged
silent-fallback literals in worker files. Judgment points print as a checklist. **Measure-first validation:
the #189 diff (00c7354..bdb269c) FAILS; the import-only S-1 (#203) + archive-only A-2 (#202) diffs PASS.**
Self-test on the PR's own diff passes. B-3 marked shipped in the brain audit.

## [2026-07-06] decision | B-5 + B-4(partial) — reasoning doctrine + CLAUDE.md cadence de-drift

Brain-hygiene batch. **B-5:** wrote [[workflow/reasoning_doctrine]] — 8 imperative process moves (the actual
Fable-vs-Opus gap is process, not knowledge): measure-first, verify-the-row-not-count, fail-open,
confirm-before-advance, no-silent-fallback, structural-not-text, notify-only, write-back. Added to CLAUDE.md's
session-start reads (#4) + [[index]]. **B-4 (surgical):** CLAUDE.md's Architecture at-a-glance called the
PAUSED `backend_worker`/`v2_shadow_test` the "main product" and both workers "every 15min" — corrected to
`bill_tracker`+`web/` as the product and a "don't hardcode the cadence — see the ledger" pointer (my own
guardrail-#5 work had made both crons `*/15` self-throttled, worsening the drift). Fuller B-4 pass (row-count
softening, whole-file volatile-fact audit) left. B-4/B-5 marked in the audit page.

## [2026-07-06] decision | B-1 + S-6 — current_status restructured to a true state page

Continued the Fable queue with the brain-hygiene item (chosen over B-3, whose machine-executable audit
needs careful "output-affecting" scoping better done fresh — noted in current_status NEXT). `current_status.md`
was a 285-line append-log mixing NOW with months of history — a literal reader couldn't tell current from
past (the exact failure B-1 names). Rewrote it to **NOW / NEXT / RECENTLY LANDED** (39 lines, gate ≤60); the
full 289-line history was copied VERBATIM to [[state/status_archive_2026H1]] (status: archived) so nothing is
lost (it's also in this log + the architecture/failures docs). Added the **MOVE-only** rule to CLAUDE.md's
write-back table; repointed [[index]] "START HERE" to current_status; **archived the stale
[[state/next_session]]** (a second, three-weeks-stale "what's next" that had bitten me this session — closes
sweep **S-6**). B-1 + S-6 marked shipped in the audit pages.

## [2026-07-07] pr | #208 OPENED — A-2 Part 2 phase 2: witness relocation to VA·Ops (flag-gated)

Owner said keep going — built the A-2 Part 2 actuator now that VA·Ops exists. **Measure-first de-risked it:**
every Schedule_Witness access (append + size-canary + Part-C reconciliation read) flows through ONE point
(`_ensure_witness_tab`), so the repoint is a single-function change with no missed site (a stranded Part-C
read would've fired false "no evidence" alerts — the risk that made it look scary). **Safe-by-default:**
`WITNESS_WORKBOOK` unset = today's behavior (VA·Live), zero change; `=ops` → VA·Ops with a fail-safe fallback
to VA·Live + WARN if VA·Ops can't open. `archive.py` gains a `shard-witness` mode (copy-verify-then-delete,
reusing `_copy_tab`/`_verify_copy`; `_copy_tab` generalized with `dest_id`); the witness prune follows the
flag. Rollout when VA·Live nears 6M (~5.5M now): shard-witness → CONFIRM=delete → set WITNESS_WORKBOOK=ops.
Not output-affecting; prepush_audit passes; compile + worker-import clean. Also #206/#207 MERGED (bot
fold-ins: `step_min<=0` + within-day window guards, gap constants hoisted to module level for the test,
shard-recommend guarded to present tabs). Backlog audited clean (#8 resolved by C8 routing; only the
theoretical STM #10 remains, correctly deferred).

## [2026-07-07] pr | #206 + #207 OPENED — Health-tab honesty + A-2 Part 2 phase 1

Owner (2026-07-07): the Health tab shows more alerts than a "1 benign" claim; they want it to self-explain so
a layman can tell the site is OK without asking, and the Stability ring shouldn't yellow for an experimental
engine. Root-caused (measure-first — I'd queried current Sheet1, not the Metrics_History alert history):
three classes, all benign, now made honest — **PR #206**: (1) cycle-gap WARN was firing every morning on the
benign overnight quiet-skip — the detector's threshold ignored the quiet window (comment still said "cron 0
*/3"; it's */15 self-throttled). Now thresholds on the ACTIVE-hours gap (`_quiet_window_overlap_minutes`,
DST-correct, `health_gap_test.py` 7 cases) → nightly skip silent, real daytime outage still fires. (2) The
incremental-STM SHADOW divergence (experimental engine, output never used) was a jargon CRITICAL → now INFO +
plain English ("live calendar UNAFFECTED"), so it no longer yellows the Stability ring. (3) 6 per-row
"malformed HISTORY row" WARNs → ONE benign INFO summary ("N blank rows in VA's feed — upstream defect, not
ours"). (4) Frontend severity badges → "Action needed / Heads up / FYI" (raw on hover). WORKER_OUTPUT_LOGIC
2026-07-04.1→2026-07-07.1 (the blank-row change touches the STM — prepush_audit correctly required the bump;
harmless). **PR #207** (A-2 Part 2 phase 1): `sustainability_audit` now recommends the VA·Ops shard (config
`OPS_WORKBOOK_ID=1X7wa4b…`, `SHARD_THRESHOLD_CELLS=6M`) with concrete cells-reclaimed when VA·Live crosses 6M
(it's ~5.5M now). The auto-actuator + live witness-repoint is the gated phase-2 follow-up.

## [2026-07-06] pr | #202 + #203 + #204 ALL MERGED (squash) — A-2 verify · S-1 keys · S-2 CI

Bot-reviewed, folded in, merged. **#202** (A-2 rollover snapshot verify) fold-ins: `or []` gspread
None-guard on the header compare (both copies, Gemini), rollover FYI category `API_FAILURE`→`UNKNOWN` (a
success event shouldn't pollute failure views, CodeRabbit), test asserts EXACT helper output not just
verdict truthiness (CodeRabbit). **#203** (S-1 keys) fold-in: `LIS_KEY_SOURCE` records env-vs-fallback so a
stale-default gap is inspectable WITHOUT a per-run warning (the fallback is the intended value until the
secret is wired — Standard #8 noise-only-on-anomaly, CodeRabbit). **#204** (S-2 CI) — its golden-tests job
had failed on `session_rollover_test.py` (a #202 file not yet on main); merge-ordered #202→#203→#204 (each
reconciled with main) and the job then went green (self-validated: runs the 6 offline tests on the PR).
Combined `main` re-validated after every merge (37 cadence + 19 auth + 18 rollover pass, workers
import-clean). **Fable queue so far: A-1, A-2 Part 1, S-1, S-2 all shipped.**

## [2026-07-06] pr | #204 OPENED — run worker golden + pure-logic tests in CI (sweep S-2)

The stdlib-only `structural_tests.yml` never ran the dep-needing worker golden suites or the pure-logic unit
tests (they import calendar_worker/pandas/pytz) — regressions only caught if a session remembered to run them
locally. New paths-filtered `golden_tests.yml` installs the worker deps + runs the 6 offline tests
(compute_effective_scrape_end, pr_c3_helper_v2, refid_shape_drift, cadence, lis_authorization,
session_rollover) on PRs/pushes touching worker logic or a test file; stdlib job stays the always-on fast
lane. All 6 verified passing offline; YAML validated; the job self-validates on this PR. [[audits/fable_2026-07/sweep_findings]] S-2 shipped.

## [2026-07-06] pr | #203 OPENED — single env-first source for the LIS API keys (sweep S-1)

Next Fable-queue knock-out (owner: "don't stop"). The LIS `WebAPIKey` (`81D70A54…`) + SPA public key
(`FCE351B6…`) were hardcoded across the codebase — rotation-brittleness (not secrecy; both are public). Now
ONE env-first source in `lis_authorization.py`: `LIS_API_KEY`/`LIS_PUBLIC_API_KEY = os.environ.get(…, "<cur>")`
→ **rotation = set one GitHub secret, zero code edits.** All runnable production + tool code imports it (both
workers; the 4 active tools + backend_worker extend their existing `lis_authorization` import — `grep 81D70A54`
in running code == 1). Intentionally left: deprecated `xray.py`, frozen `backend_worker_3col_backup.py`, the
X-Ray UI-default pair (user-overridable password fields), and the dead C7 audit tools (public-key literal).
`py_compile` clean; env override verified; both workers import-clean. Rotation runbook note added to
[[knowledge/lis_api_authorization]]; [[audits/fable_2026-07/sweep_findings]] S-1 marked shipped.

## [2026-07-06] pr | #202 OPENED — verify the session snapshot before advancing the marker (A-2 part 1)

Continuing the Fable queue (owner: "best next thing… don't stop"). Picked A-2 (owner-salient: the "sheets
running out / switching to a new sheet" concern). Re-checking the code found A-2 **Part 1 (rollover hook)
was ALREADY BUILT** — same "I thought Opus had fixed this" pattern as A-1: `run_calendar_update` archives
the completed session (`_archive_completed_session` → `Session_<old>`) on `V1≠ACTIVE_SESSION` then advances
V1, fail-safe on exceptions. **The gap vs spec was verification:** it copied + advanced with NO check the
copy landed, and `copy_to`+rename has SILENT partial-failure modes → could advance V1 over a broken archive,
then next cycle's `clear()` loses the session ([[failures/assumptions_audit]] #97). Added `_verify_archived_
snapshot()` (canonical-name + grid-dims + header-row, RAISES on mismatch → existing fail-safe preserves the
live sheet), mirrored into `tools/session_archive/archive.py._verify_copy` (kept in sync), pure
`_snapshot_dim_mismatch` unit-tested (`session_rollover_test.py`, 18 cases incl. worker-vs-tool agreement),
and turned the rollover's bare `print` into an INFO SYSTEM_ALERT FYI (Slack + Health chip). `py_compile` +
worker-import clean. **A-2 Part 2 (mid-session headroom shard actuator) remains the open A-2 piece** — larger
(needs an ops workbook + C-2 shard) and not urgent (the rollover already archives each session out yearly).

## [2026-07-06] pr | #197 + #198 + #200 + #201 ALL MERGED (squash) — owner "merge if done reviewing"

The four review-folded PRs landed on main together. Merge order handled conflict risk: #197/#198 first got
`main` merged into their branches to pick up the #199 Cloudflare fix (their Workers-Build check had failed
only because they predated `wrangler.toml`); then squash-merged #197 (freshness clocks), #198 (activity-
correlated cadence + the owner's bill-worker equalization: bill cron `40 */6`→`*/15`, IN_WINDOW floor 0 to
match the calendar's 15-min track, EMPTY 6h, and its OWN `bill-tracker` concurrency lock so calendar's
in-window cycles can't starve it), #200 (F-3 Health rings), #201 (A-1 self-extending session auth). **#198 +
#201 both touch calendar_worker.py + bill_tracker.py — combined `main` re-validated after the merges:**
`py_compile` clean, 37 cadence tests + 19 auth tests pass, both workers import-clean, web `tsc` + `vite
build` clean, and both integrations confirmed coexisting (cadence gate + session-follow gate both present;
bill cron `*/15` + own lock). Cloudflare Pages deploy is green (#199 `wrangler.toml` SPA fix).

## [2026-07-06] pr | #201 OPENED — A-1 self-extending session authorization (Fable queue #1; halt-preventer)

The top Fable-audit priority ([[audits/fable_2026-07/autonomy_upgrades]] A-1) — without it the whole system
HALTS when the 2027 GA convenes (frozen `{20251,20261}` allowlist), which the owner flagged as a Standard #8
violation. Now the live workers **auto-follow the session LIS's Session API declares active**, ban-safely:
`lis_authorization.py` splits `LIS_HISTORICAL_AUTHORIZED` (frozen anti-replay set; all tools keep it via the
`LIS_API_AUTHORIZED_SESSIONS` alias) from the active session; `is_authorized_session(code, active_session=…)`
follows the active one; `calendar_worker.session_follow_gate` probe-verifies a NEW session ONCE (bills-list
GET → 200+data proceeds+FYI, 401/403 halts, transient retries) caching `Sheet1!S2`; `AUTO_SESSION_FOLLOW=0`
kill switch; both workers wired (shared S2 cache → one probe across both). 16 unit tests. Deferred (not
halt-critical): the front-end `session_code` stamp (step 6) + portal-wording re-review (step 5; the probe
backstops it). py_compile + workers/backend/tools import-clean. CodeRabbit + Qodo pending. [[knowledge/lis_api_authorization]] updated.

## [2026-07-05] pr | #200 OPENED — Health "at a glance" rings clarified (F-3, last of the 2026-07-04 batch)

Implements [[design/ui_feedback_2026-07-04]] **F-3** (owner: the rings were confusing — "1 warning" over
"Sustainability audit check", unclear top-vs-bottom, Freshness looked like it was missing its bottom line,
warning not actionable). Wiring-only over signals already on the page: **F-3a** label the two lines — live
rollup = "Status: …", outside cross-check = "Verified: …"; **F-3b** Freshness (no external oracle) shows an
explicit muted "Verified: — no outside check applies" and the others "Verified: checking…" while guards load,
so all four rings are parallel (no more "missing" line); **F-3c** the Status rollup names the offending
segment on hover and, when non-green, is a click target (↓) that smooth-scrolls to that category's detail
section (Stability→Alerts, Freshness→clocks, Accuracy/Completeness→gauges). `tsc`+`vite build` clean;
preview-verified (Stability "1 warning ↓" → scrolls to Alerts; 0 console errors). CodeRabbit + Qodo pending.
**This closes the 2026-07-04 UI feedback batch** (F-1 #197, F-2 #198, F-3 #200; F-4 = leave the lone HB923
upstream-defect alert, owner's low-stakes call).

## [2026-07-05] pr | #199 MERGED — Cloudflare Workers-Assets SPA fix (deploy was failing on _redirects loop)

The owner's Cloudflare deploy reached "Deploying" then failed: `wrangler` rejected `web/public/_redirects`
with "Line 4: Infinite loop detected in this rule." Root cause: the project deploys as **Workers Static
Assets** (log shows `wrangler` deploying a Worker `bill-tracker` from repo-root `dist/`, auto-generating a
config), and the classic-Pages SPA rule `/*  /index.html  200` is invalid there — Workers Assets
canonicalises `/index.html` → `/`, which re-matches `/*` → loop. (A classic Pages project would ACCEPT that
rule, so the error itself proves it's Workers Assets.) Fix: deleted `web/public/_redirects`, added repo-root
`wrangler.toml` with `[assets] not_found_handling = "single-page-application"` (the Workers-Assets-native SPA
fallback) + pinned `name`/`directory`. Build re-verified (root shim still emits a valid `dist/`). Runbook
[[workflow/deploy_cloudflare_pages]] gained a "#2 mistake" box. **Merged to unblock the deploy** — Cloudflare
auto-deploys `main`, so the fix only takes effect once landed. Also: bill cadence equalized to the calendar's
15-min track in-window (owner) is folded into the still-open #198.

## [2026-07-05] pr | #198 OPENED — activity-correlated cadence for both workers (LIS-safety guardrail #5)

The owner's "dynamic timing" ask ([[design/ui_feedback_2026-07-04]] F-2), and the LAST unshipped LIS-safety
guardrail. Both scheduled workers stop running blind fixed crons and instead fire FAST + self-throttle to
real legislative activity. ONE structural signal (Standard #3, no text): the calendar worker writes
last-full-run + forward **meeting windows** to `Sheet1!AC1` each successful cycle (windows from the same
concrete-time rows the site shows — `Origin ∈ {api_schedule,convene_anchor,legislation_event}`, merged);
both workers READ AC1 in their scheduled gate and skip cheaply (**Sheets-only, ZERO LIS**) unless active
enough for their tier. Tiers (calibrated to preserve today's baselines — audit #14): calendar IN_WINDOW
~15m / IDLE ~1h / EMPTY ~3h; bill IN_WINDOW/IDLE ~1h / EMPTY ~6h (bill throttles against its OWN marker
`Bill_Tracker!U1`, shared windows). Crons: calendar `0 */3`→`*/15`, bill `40 */6`→`40 *`; repo is public
so the extra runner starts are free and off-window ticks exit in seconds. New shared **`cadence.py`** (pure,
no back-import) + **`cadence_test.py`** (31 tests, all pass). Safety: BOTH failure directions non-catastrophic
(fast-but-guardrailed 24/7 vs today's baseline), gate fails OPEN, every default fails-toward-freshness; AC1/U1
writes unconditional on the success path (audit #11), empty/future markers → run not trapped (audit #15).
`py_compile` + both workers import-clean; no `pages/*.py` imports it (audit #8).
Docs updated: [[knowledge/lis_api_safety]] (guardrail #5 → 🟡, cadence ledger), [[architecture/calendar_pipeline]]
(AC1 + U1 state cells), [[design/ui_feedback_2026-07-04]] F-2, [[state/current_status]].
**Bot fold-in (2026-07-05):** 1 Gemini + 5 Qodo, all folded in — `os.environ.get` for creds (no KeyError on
local run), gate errors ROUTED (calendar→notify_slack, bill→_alert) not just printed, the U1 read narrowed
to WorksheetNotFound-vs-real-error (no silent swallow), `parse_state` gained a `malformed` flag so a parse
failure is distinguishable from a legit empty state (audit #15) + surfaced in the decide() log, and
`build_windows` now COUNTS every skip (skipped / dropped_past / dropped_horizon — no untagged `continue`).
Qodo's 6th (AC1 undocumented) was already satisfied on main (calendar_pipeline). Tests 31→36, all pass.
CodeRabbit summary-only (no actionable inline). Bots re-reviewing the fold-in commit.

## [2026-07-04] pr | #197 OPENED — unify both freshness clocks in the top trust header (F-1 display fix)

Implements [[design/ui_feedback_2026-07-04]] **F-1**: the top "data as of" showed only the bill backend's
clock (~6h) while the Calendar tab showed the calendar subsystem's fresher clock (~3h) — two honest
timestamps that read as a contradiction because they lived in different places. Fix is display-only:
`TrustHeader` (components/common.tsx) now renders BOTH clocks side by side — "● Bills as of …" +
"🗓 Calendar as of …"; App.tsx loads the calendar freshness (Sheet1!AA1) non-blocking via a new
promise-cached `loadCalendarFreshness()` (data/calendar.ts); the now-redundant in-view pill + its unused
`relativeTime` import are removed from views/Calendar.tsx (moved up, not duplicated). NO cron/cadence change
— that's the separate guardrail-#5 work (F-2). `tsc --noEmit` + `vite build` clean; verified in preview
(one "Calendar as of", both clocks in the header, 3645/3645). Also removed a stray untracked `package 2.json`
(a macOS " 2" duplicate of the #196 root build shim — never committed).
**Bot fold-in (2026-07-05):** 2 Qodo findings folded in — dropped the redundant second `Sheet1!AA1` fetch
(removed `fetchFreshness()` from `loadCalendar`'s `Promise.all` + the now-unused `CalendarData.dataAsOf`;
`loadCalendarFreshness()` is the single AA1 read), and made the App-level freshness `.catch()` observable
(log before falling back to "unknown", Standard #4). `tsc`+`vite build` clean. **Cloudflare Pages now builds
green** (the #196 root shim worked — deploy comments are posting on the PRs).

## [2026-07-04] decision | Cloudflare build failed (root-dir) FIXED in runbook + owner UI/cadence notes captured

Owner's Cloudflare Pages build failed: `npm error enoent … /opt/buildhome/repo/package.json`. Diagnosed:
the app is in `web/` but **Root directory wasn't set to `web`**, so Cloudflare ran `npm run build` at the
repo root (no package.json there) AND auto-installed the workers' root `requirements.txt` Python deps. One-
setting fix (Root directory = `web`); [[workflow/deploy_cloudflare_pages]] rewritten with a prominent "#1
mistake" section + fix-the-existing-project steps. Owner UI/cadence notes for later banked to
[[design/ui_feedback_2026-07-04]]: (F-1) the two freshness clocks disagree because bills=6h / calendar=3h
FIXED crons — a display-honesty fix (show the oldest + a breakdown), NOT a cron-sync; the real unification
is the CDN-inversion manifest. (F-2) cadence is FIXED, not activity-correlated — guardrail #5 (meeting-
driven cadence) is documented-but-UNBUILT and now unblocked; strong next-VA-backend candidate. (F-3) Health
rings: label the two lines (Status vs Verified), explain Freshness's absent badge, make "1 warning"
descriptive + click-to-scroll to the alert. (F-4) the lone live alert = LIS's own blank HISTORY row for
HB923/03-09 (verified content-less, nothing lost) — an honest upstream-defect flag, not a bug; leave it.

**Kinds:** `ingest` (new source/doc processed), `pr` (PR opened/merged/closed), `decision` (architectural or workflow), `lint` (wiki health-check pass), `session` (notable multi-hour working block), `post-mortem` (failure analysis), `milestone` (project-goal threshold crossed).

## [2026-07-04] pr | #194 + #195 MERGED — Cloudflare Pages deploy prep + chief-patron FULL name (VA data follow-ups closed)

#194: repo turnkey for the decided host (React+Vite→Cloudflare Pages) — `web/public/_redirects` SPA
fallback, `web/.node-version=22` (Vite-8 floor), clean-checkout build verified, connect runbook
[[workflow/deploy_cloudflare_pages]]; the ~5-min dashboard Git-connect is owner-only (account/OAuth) and
gives per-PR preview URLs (the flaky-local-preview cure). #195: chief-patron FULL name from the
bill-universe payload (free — the `Patrons` list we already fetch carries `MemberDisplayName` "Jeion A.
Ward" + `MemberNumber`; 3645/3645 coverage), with a Qodo fold-in round: crash-safe Patrons parse (isinstance
guards so a non-list/non-dict drift can't abort the whole cycle — Standard #6), 3-part heuristic doc, rate
companion, and `MemberNumber` used deliberately as the BILLS.CSV-format-consistent id (no numeric-MemberID
fallback = no format corruption). Bill worker dispatched for production proof. **All VA data follow-ups now
resolved:** chief patron ✅ (#195), co-patrons scoped-deferred ([[ideas/copatrons_backfill]] — needs
DOM-discovered endpoint + cadence), subject deferred (no bulk source). Remaining VA: the owner's dashboard
connect + owner-triggered `/code-review ultra`. NEXT chapter = the Fable-audit queue
[[audits/fable_2026-07/README]].

## [2026-07-04] decision | Cloudflare Pages deploy PREPPED (the flaky-local-preview fix) → [[workflow/deploy_cloudflare_pages]]

Owner: "actually set up the new host for the site so I don't have to keep looking at a preview that fails."
Host was already DECIDED (2026-06-18: React+Vite on Cloudflare Pages, over Streamlit). Prepped the repo so
the connect is turnkey: `web/public/_redirects` (SPA fallback), `web/.node-version=22` (Vite 8's Node
floor, so Cloudflare's build env can't drift), clean-checkout build verified (`npm ci && npm run build` →
dist ~80KB gz). The remaining step is account-bound (create/connect Cloudflare + GitHub OAuth) — a ~5-min
dashboard Git-connect only the owner can do; exact build settings (root `web`, build `npm run build`,
output `dist`) documented. Dashboard route recommended because it gives a real per-PR preview URL — the
direct cure for the failing-local-preview complaint. gviz stays the data path (link-readable sheet);
CDN-inversion removes that dependency later. Health tab visible pre-launch (gate before public launch).

## [2026-07-04] decision | 50-state scaling blueprints banked (CDN inversion / Omni-Schema / Fleet)

Final Gemini-prompted deliverable before audit close, with Fable's assessments on record: (1) **CDN
inversion** = the real new build and keystone — worker publishes versioned static JSON (bills/calendar/
health + an atomic manifest, per state) to R2/edge; gviz demoted to migration fallback then deleted;
dual-publish diff soak as the gate; sequenced with A-1/A-2 BEFORE any new state. (2) **Omni-Schema** =
formalization, not invention — NY already emits the VA shape by design; freeze types.ts reality as JSON
Schema v1, add per-state CAPABILITY FLAGS (honest-absent features for thin states), CI-validate every
payload. (3) **Fleet** = premise corrected — no monolithic 50-state cron exists; per-state workflows
already run independently. The real problems: Actions concurrency/scheduler throttling at ~15+ states →
generated (not hand-copied) per-state workflows, hash-staggered crons, session-aware cadence per state,
shared-nothing storage, national manifest rollup (one state red ≠ national alert), and a NAMED graduation
path off Actions (~12-15 active states trigger). Explicitly deferred: databases, queues, k8s. Execution
order per owner: A-1 → A-2 → CDN inversion → fleet generator at the 3rd state.
[[audits/fable_2026-07/50_state_scaling_architecture]].

## [2026-07-04] ingest | CA + FL researched against the 10-15 min freshness target → [[audits/fable_2026-07/multistate_ingestion_ca_fl]]

Owner: repeat the PA treatment for California and Florida. **CA (verified from the official pubinfo
Readme):** the batch layer is a LITERAL RELATIONAL DATABASE export — per-legislator vote tables
(BILL_DETAIL_VOTE_TBL), COMMITTEE_HEARING/AGENDA_TBL, DAILY_FILE_TBL, CODES_TBL, shipped MySQL DDL,
sessions to 1989 — the most structural state yet (zero prose routing at batch). But cadence is DAILY
(per-weekday incremental zips), so the 10-15 min target requires a speed layer: Assembly/Senate Daily
File web apps + leginfo's own pages, gated on a Phase-0 MEASURED-LAG experiment (poll moving bills on
session days; build a per-event-class publication-lag table; only surfaces that measure ≤ target join
the speed layer — honest "as of" labeling otherwise). **FL:** no official bulk dump — a "site-API state":
flsenate.gov (clean ID-keyed URL grammar; thin official RSS = daily calendar + video) + flhouse.gov with
a LIVE `/api/document/...?sessionid=` endpoint observed in the public index (a family to enumerate in
Phase 0). FL's structural gift: House and Senate run two INDEPENDENT first-party systems covering the
same legislature = a built-in dual-pipeline verification oracle, no third parties. 10-15 min PROBABLE
for FL across all critical classes, contingent on endpoint enumeration. Emerging 4-tier state taxonomy
(API / relational-export / bulk+feeds / site-API) all binding to the SAME lambda contract — confirms
[[ideas/multi_state_data_strategy]].

## [2026-07-04] decision | PA text-dictionary REJECTED → structural-JOIN router (live-feed evidence)

Owner (via Gemini review) rejected the 57-year phrase corpus: a historical dictionary is still a text
dictionary — a clerk's novel Tuesday phrase defeats it and pings a human. Fable retracted it and answered
the three architectural challenges EMPIRICALLY by inspecting PA's live feeds: (1) **hidden structural
codes FOUND** — the committee-schedule RSS carries a full custom `parss:` namespace
(MeetingDate/MeetingTime/Committee/**Bills**/Location/InCapitol — meetings are 100% structural, agenda
included, richer than VA's Schedule API); roll-call RSS links carry canonical DB keys
(`sessYr/sessInd/rcNum`) with machine-serialized titles (`HB 2154 PN 2787`) and fixed-format tallies;
printer's numbers = PA's version primary key. (2) **Prove-to-Hide fail-safe**: route by JOIN — every event
class has a structural witness artifact (roll-call item ⇒ vote; parss:Bills ⇒ meeting; PN transition ⇒
version event); prose is display-only, exactly VA's refid→VOTE.CSV pattern. (3) **The unseen row**: the
router is a TOTAL function — no artifact ⇒ event_class=UNPROVEN by construction → the visible
Suspense/Unconfirmed lane ([[ideas/self_healing_classification]] Prove-to-Hide), rate-anomaly canary (not
per-row), auto-upgrade when the artifact trails in. Zero regex, zero human. The corpus is demoted to a
one-time MEASUREMENT instrument (join-rate forecast + router validation set). Part 3 + Phase gates of
[[audits/fable_2026-07/multistate_ingestion_pa]] rewritten accordingly.

## [2026-07-04] decision | Owner correction: ZERO-TOUCH rollover/capacity + first-party PA freshness ladder

Owner pushed back on the Fable audit's C-1/C-2 designs ("why were your solutions pinging me… I explicitly
stated my sustainability goals") and asked: were session auto-switch + sheet rotation ever built?
**Verified:** session DETECTION is built (Session API every cycle, Standard #5); the authorization
allowlist halt was a DELIBERATE compliance checkpoint (LIS portal authorizes per-session), not a gap.
Capacity: headroom-aware tab creation + prunes + monthly compaction ARE built; the **auto rollover hook is
documented in archive.py as an unbuilt follow-up** ("a worker rollover hook will call snapshot-session
automatically on session change (follow-up)") — the owner's memory was right. New page
[[audits/fable_2026-07/autonomy_upgrades]]: **A-1** self-extending session authorization (auto-follow the
Session API's active session, probe-verify 401→halt, kill switch, FYI-only alert; historical sessions stay
frozen) + **A-2** automated workbook lifecycle (finish the rollover hook: snapshot→verify→reset; headroom-
triggered ops-shard actuator). C-1/C-2 superseded; "notify-only test" codified into
[[workflow/zero_routine_maintenance]]. ALSO: PA fresher-than-hourly, NO third parties (owner: "we are
building a superior competitor") — Part 5 added to [[audits/fable_2026-07/multistate_ingestion_pa]]:
first-party freshness ladder (RSS 2–5-min polling = the minutes-matter classes: votes/meetings/calendars;
palegis.us XHR/JSON investigation = the VA SPA-key playbook; WebSub push check; hourly XML stays the
authoritative reconciler — admin history lines need no freshness, VA doctrine). Freshness rides ON
accuracy: provisional-stamped, XML-confirmed-or-quarantined, first-party cross-channel verification.

## [2026-07-04] session | FABLE AUDIT — four execution-ready deliverables banked to [[audits/fable_2026-07/README]]

Owner directive at the stopping point: use the time-limited Fable access for (1) a brain audit — what to
change so Opus performs closer to Fable (verdict: make the written thing exactly true, small, and
executable — B-1 status-page restructure, B-2 case-law indexes, B-3 EXECUTABLE pre-push audit script,
B-4 CLAUDE.md de-drift, B-5 reasoning doctrine); (2) a VA+NY longevity audit (C-1 the Jan-2027
authorization HALT + horizon canary; C-2 the Sheets 10M-cell ceiling — witness ≈232k rows measured; C-3
gviz/Actions coupling → static-JSON inversion; C-5 BILLS.CSV oracle canary; C-8 NY hardening gap —
canaries + LegiScan oracle; C-10 multi-session product design); (3) the PA/non-API-state question —
RESEARCHED: PA publishes hourly Bill History XML (1969+) + per-publication RSS incl. roll calls and
committee schedules (palegis.us/data) — structured transport, NO scraping; semantic layer = controlled
vocabulary handled by the enumerate-the-57-year-corpus registry doctrine; lambda architecture (batch
authoritative / speed provisional / reconciler / LegiScan verification oracle) fully specified with a
4-phase build plan; (4) sweep S-1…S-6 (plaintext LIS key ×10 files, CI golden-test blind spot, root
cruft). ALL document-only per the owner: "leave the grunt work to Opus." Hub README carries the priority
queue.

## [2026-07-04] milestone | Production proof: Section 9 = 0 held through #189+#193; TimeClass live

Manually-dispatched worker run (28710792692, success): `meeting_unsourced=0`, `invariant_violations=0`,
TimeClass column live in Sheet1 (7,249 concrete / 3,728 relative_resolved / 370 relative_unresolved rows;
per-meeting counters 1,667 total / 19 unresolved in-window). The 2026-01-14 Senate P&E meetings — the owner's
original unplaceable example — now carry `relative_unresolved` and top-surface with the ⚠ badge. Bill worker
proof landed earlier the same day (floor reconcile 1157/1157, rate 0.0). The owner's full to-do list is DONE
with production proof on both workers.

## [2026-07-04] pr | #193 MERGED — §7.2 TimeClass (unplaceable meetings surface first) + subcommittee lineage cue

Closes calendar_chain_ordering §7.2 + the same-time-family grouping. Worker: structural `TimeClass` column
(concrete | relative_resolved | relative_unresolved | "") via the ScheduleClass keyed-map pattern; counters +
`timeclass_total` denominator in SYSTEM_METRICS (steady ≈ 22 unresolved / 3480). Front end: unresolved
meetings sort to the TOP of their day + caution tint + "⚠ unplaceable" badge (whole-surface tint, never a
side strip); "Parent - Sub" committee names render as muted parent + "↳ Sub" so interleaved same-time
families stay readable. Qodo fold-in caught a REAL miss: #189 changed Sheet1 output without bumping
`WORKER_OUTPUT_LOGIC_VERSION` → Stage-2/incremental signature reuse could serve pre-change rows; bumped to
2026-07-04.1 (covers #189 + TimeClass), and TimeClass joined `_STM_EVENT_KEY_FIELDS` so the incremental-STM
oracle can see TimeClass-only divergences. One merge-conflict resolution vs #191/#192 (took main's
Health.tsx). Both workers manually dispatched post-merge for same-day production proof: bill worker ✅
(House Floor: 2345 passed + 5 defeated; Senate: 2007 + 6; reconcile 1157/1157, rate 0.0 — the Timeline's
Floor stages lit live, including the 11 real floor defeats answering the owner's "did nothing really get
voted down on the floor?").

## [2026-07-04] pr | #191 MERGED — Timeline FLOOR stages (passed/defeated per chamber) + landing reorder + grouped drill-down

The owner's "you had prefiled committee floor crossover committee end point" pipeline, done structurally.
Backend: `_derive_floor` emits per-chamber **House Floor / Senate Floor** columns (appended Q,R; completeness
R1→T1) valued `passed|defeated|""` from LIS's controlled action vocabulary ("(Read third time and)
passed/defeated by House/Senate" + voice-vote "Agreed to by X"). **Defeat is first-class** — a bill voted
down on a floor REACHED it (✕ at Floor, not Committee); ~29 true floor defeats in 2026 vs 834+ passages;
procedural "substitute rejected by X" excluded; passage WINS over defeat (HB55: defeated → reconsidered →
signed). Self-calibrating reconcile (validated **1157/1157** fully-passed HB/SB show both floors, 0 false
positives) now ALERTS >1% (Standard #4). Front-end: 6-column spine (Prefiled→Committee→Floor→CROSSOVER→
Committee·2nd→Floor·2nd→Outcome); `furthestStage()` shared between live placement and died-✕; new
`stageSide()` derives the lane from the STAGE + origin (Qodo: b.chamber keyed impossible cells for
crossed-then-returned bills). Also: legend states the ✕ math ("all ✕ sum to 1,253 = 811 died + 442 carried"
— the owner's confusion), Timeline moved ABOVE "Where the bills stand", drill-down grouped by
chamber→committee→sub with per-group counts, off-season note on the What's-new feed. Two bot fold-in rounds.
Floor columns light up on the bill worker's next run (dispatched).

## [2026-07-04] pr | #192 MERGED — verify badges name their check (no "confirmed with a warning" contradiction)

Owner: "how can stability be independently confirmed with a warning?" The ring segments are LIVE internal
signals; the badge is the named OUTSIDE cross-check — the generic "✓ independently confirmed" hid that. Badges
now name their check ("✓ Sustainability audit check passed"); a NON-pass badge names only the guard(s)
actually in the worst state (Qodo: two guards on a dial must not smear each other); hover title states a live
warning and a passing outside check can coexist.

## [2026-07-04] pr | #190 MERGED — Health alert-flood fix (routine deferrals stop paging the operator)

Owner: "the health tab looked concerning with a lot of concerning notifications." Root causes, both false
alarms: (a) ~499 distinct `WARN:TIMING_LAG` "No schedule match … deferred to Ledger" alerts — one PER BILL
ACTION, re-emitted every cycle; routine dispositions, not anomalies (`meeting_unsourced`=0), the exact
Standard-#8 violation the sibling admin_default path already avoided (Gemini #66); (b) the Completeness
trust badge stuck on "✕ FAILED" from the 2026-06-29 tripwire run — the S10 gap #184 fixed on 06-30, but the
WEEKLY guard hadn't re-run. Fix: the `journal_default` block no longer emits a per-row SYSTEM_ALERT (row
stays visible via [NO_SCHEDULE_MATCH] + diagnostic_hint + the `unsourced_journal` counter); the Health alert
history COLLAPSES any >8-distinct-message category into one expandable summary (handles the historical
backlog too); re-ran `completeness_tripwire` (workflow_dispatch) → **PASSED**, validating #184's production
proof. Preview-verified: Completeness 4/4 "independently confirmed", 499-alert flood → one collapsed line.
One Qodo fold-in round (stable React keys on the reorderable list; stale doc/comment refresh).

## [2026-07-03] pr | #189 MERGED — date-aware relative-time resolver (chains sort by real per-day time)

Implemented the re-scoped fix (the day after the premise was falsified below). `build_time_graph` now
resolves each DAY independently and outputs `{(date, name): "HH:MM"}`; the caller looks up
`(date_str, owner_lower)`. Honors every published clock exactly (concrete `ScheduleTime` always wins);
`_committee_parent` anchors a committee reference to that committee's node, not the chamber floor,
reserving the floor-adjourned clock for bare-chamber refs; +1-min chain epsilon keeps a transitive
A→B→C chain strictly ordered; fixed `_parse_relative_offset_minutes("1/2 hour")`=120→30 (+ mixed
"1 1/2"/unicode "½"). Offline-validated (`tools/edge_case_replay/validate_relative_chains.py`, live
Schedule API): SAFETY 0/2,877 published-clock keys move, RESOLUTION 198→428 relative rows concrete,
date-awareness proven (senate adjourned = 69 distinct per-date times), chains order parent→children.
THREE bot fold-in rounds — the standout: replaced a hand-curated UI-caption denylist (Standard-#1 rot
risk) with a structural `day_vocab` intersection (drift-proof; also resolved 10 more rows). Worker
golden tests pass; front-end unchanged (`toMinutes` already sorts by `SortTime`). Production proof =
Section 9 = 0 + X-Ray ordering next worker cycle. Residual ~32/450 (root unresolvable) → §7.2 follow-up.
Lesson [[failures/assumptions_audit#95]] closed; plan [[ideas/calendar_chain_ordering]] §8 → implemented.

## [2026-07-02] decision | Relative-time chain fix RE-SCOPED — plan premise falsified by measurement

Picked up the queued relative-time chain ordering ([[ideas/calendar_chain_ordering]]) as the next intensive
worker task. Built an offline validator (`tools/edge_case_replay/validate_relative_chains.py`, sibling of
`schedule_replay.py`) that AST-extracts `build_time_graph` old-vs-new and diffs the resolved map against ONE
live Schedule API pull. The planned §3 fix (broadened detection + normalized committee parent-match, strictly
additive) came back **`changed=0` — a no-op on real data.** Instrumenting 3,521 rows / 443 dates falsified the
plan's premise: `build_time_graph` is **DATE-BLIND** (name-only key; `house appropriations` = 27 dated meetings
→ 1 SortTime), and the chains are **mis-anchored** (subcommittee → floor-adjourned), not stranded at 23:59.
Reverted the inert code (did NOT ship a no-op); kept the validator as a reusable diagnostic + additive-only
gate. Re-scoped to a date-aware time-engine refactor with a re-framed safety gate ("0 PUBLISHED-clock rows
move"). Lesson → [[failures/assumptions_audit#95]] (measure current behavior before coding the fix; "no vibe
coding" applies to PLANS, not just code). Plan §8 documents the corrected approach.

## [2026-07-02] pr | #188 MERGED — color swap (dead=pale red, carried=yellow, referral=grey)

Owner: the outcome palette had confusing hue overlaps (referral tan ≈ carried amber; grey `--o-dead`
overloaded onto "unknown" health states). Swapped dead→pale red `#b85b56` (distinct from veto's bright
`#d2403a`), carried→yellow `#96820c` (= WARN hue), referral→grey (new `--neutral` token that also unforks the
"unknown" breaker/severity states from red). tsc/vite clean; preview-verified 5 distinct outcome colors, 0
console errors. **Qodo fold-in (1 finding):** `HealthVitals.tsx` still colored the `unknown` vital tone with
`--o-dead` — now pale red, which would read unknown-as-failure ("unknown ≠ bad", §7); repointed to `--neutral`
grey (the overload class I cleared in CSS but missed in the component). Qodo re-review 0 bugs; CodeRabbit +
structural-tests green; merged.

## [2026-06-30] pr | #185 MERGED — Calendar week-view relayout (work-week columns + month selector)

Owner relayout ([[design/ui_redesign_spec]] item 3): the 7-day week is now the PRIMARY module as COLUMNS
(Mon–Fri visible together), empty weekend days shrink to 0.4fr ("pushed aside") + expand when they have
meetings, meetings are compact (time + 2-line committee; bills behind a click dropdown), and a compact month
grid alongside is a dual-cue selector — a 7-cell week band shows the displayed week + a ring marks the focused
day; clicking a day jumps+focuses. One state (focusedDay) drives all three. Incorporated mid-build owner
feedback ("I'm only seeing one day at a time — let me see the 5 work days, push the 2 weekend ones aside, bills
in a dropdown"). TWO bot fold-in rounds (Gemini + CodeRabbit + Qodo): no-op-button a11y, stale stepMonth,
out-of-range focus trap, busiest-WEEK default anchor, focus/cross + band/cross CSS-channel collisions, stable
keys. Removed the now-dead month-grid CSS (kept .daycol* for the landing sliver). tsc/vite clean;
preview-verified with live data (columns, weekend-aside, dropdown, week paging, mini jump+focus, crossover cues
coexisting, 0 console errors).

## [2026-06-30] pr | #184 MERGED — surface off-season interim meetings (lift the session-end window pin)

The new dial badge (#183) caught a real `completeness_tripwire` failure (2026-06-29 S10 interim committee
meeting absent from Sheet1) → root-caused to `compute_effective_scrape_end` pinning the worker's write-window
at the session end off-season (treated the adjourned session as historical) — the SAME bug as "Calendar shows
nothing past May." Owner chose: surface interim meetings, bounded. Fix (calendar_worker.py): new live
OFF-SEASON branch extends the window to `today + INTERIM_FORWARD_WINDOW` (45d, bounded — can't reach a
far-future session); `live_run=False` keeps pinned replays reproducible. The Schedule-loop meeting filter +
the agenda-fetch gate now bound on `effective_scrape_end` (no-op in-season). One bot fold-in round (CodeRabbit
+ Qodo): the window drop is now non-silent — a COMMITTEE meeting BEYOND the horizon increments
`schedule_beyond_window` + raises a WARN, the runtime validation that the 45d horizon isn't too short
(Standard #1, audit #9). New `test_compute_effective_scrape_end.py` (6 golden cases). Production proof: the
completeness tripwire goes green next run + the Calendar renders interim/future meetings. See
[[failures/assumptions_audit]] (the window/completeness-mismatch lesson).

## [2026-06-29] pr | #183 MERGED — merge "Are we right?" verification onto the dials

Owner: the standalone "Are we right?" panel read as a second data readout next to the gauges ("isn't it just
repeating info?") and its value (it's an INDEPENDENT cross-check vs LIS calendar / MinutesBook) didn't land.
Removed the panel; each at-a-glance donut now carries a small "independently confirmed" trust line from the
same guards (Accuracy ← sentinel+reconcile, Completeness ← completeness_tripwire, Stability ← sustainability,
Freshness ← none). Source/cadence/last-run moved to the hover title + an aria-label (so the bare freshness
stops reading as "stale"). One bot fold-in round (unverifiable-on-load-fail badge, a11y, Record<GuardState>
typing). **Real signal surfaced:** the live Completeness badge shows ✕ FAILED — the 2026-06-29
completeness_tripwire genuinely failed (a 2026-06-29 S10 interim committee meeting on LIS's calendar is absent
from Sheet1). Root-caused to [[state/health_gauge_calibration_plan|the off-season window pin]] (see
current_status / task) — same root as "Calendar shows nothing past May." Owner chose: surface interim
meetings (bounded forward window) — that fix is next.

## [2026-06-29] pr | #182 MERGED — Health gauge calibration (cadence-aware feed-skew + session-aware source-feed)

Folded the `/code-review` findings on #181 into fixes (P3 deferred). P1: the feed-skew chip's flat 3h/8h
bands false-warned ~half of every normal cycle (bill backend 6h cron vs calendar ~15min) → bands now derive
from `BILL_CADENCE_H` (ok ≤7h / warn ≤13h). P2: the source-feed (HISTORY.CSV blob age) gauge would
false-danger the whole adjourned period (off-season the blob legitimately doesn't change) → `health.ts` reads
`Sheet1!S1`, the gauge redlines only when ACTIVE, and **hides** when session state is unknown (BulletGraph has
no neutral tone → an all-good band on unknown is a false-green; all 3 bots — CodeRabbit/Qodo/Gemini — flagged
it). Both new heuristics documented with the assumes/breaks/fix triad (Standard #1). Plan was persisted at
[[state/health_gauge_calibration_plan]] (now archived). One bot fold-in round; tsc/vite clean; preview-verified.

## [2026-06-29] pr | #181 MERGED — Health observability long-tail (canary green-state, alert/metric history, trends, source-feed freshness)

**MERGED to main (squash) 2026-06-29** after TWO bot fold-in rounds (7 findings total; CodeRabbit's round-2
re-scan hung in "pending" — the known intermittent behavior — so merged on the verified state per the owner's
standing merge-on-loop-complete authorization). Combined-main validated: worker parses, `structural_router`
imports from `pages/`, all 5 structural golden tests pass. New `metrics_history_retention.yml` workflow + the
canary/Metrics_History/source-feed signals go live on the next worker cycle. Below is the build record.

Closed the five deferred Health-observability gaps on `claude/health-observability`, after a plan AUDIT the
owner requested ("could it be better? did you assume?") that corrected 3 wrong assumptions
([[failures/assumptions_audit#91]] per-bill-freshness moot in a bulk-re-derive pipeline → reframed to
SOURCE-FEED freshness; #92 a green-state that flips clean on empty upstream is a false-green; #93 an alert
emitted after its channel is finalized is silent). Worker: drift-canary green-state in `SYSTEM_METRICS`
(-1/0/N sentinel); `Metrics_History` append-only tab + `tools/metrics_history/prune.py` (45d, shares the
calendar-worker lock, registered in `sustainability_audit` RETENTION_DAYS); HISTORY.CSV blob-age
(`history_blob_age_min`). Front-end: "Upstream watchers" panel, aggregated alert-history view, sparklines
(`data/history.ts` + `Sparkline.tsx`), feed-skew chip, source-feed clock. Bot fold-in round done (4 findings:
canary false-green guards, history-alert relocation so failures reach Sheet1, pct-sparkline, workflow perms).
Structural tests pass; tsc/vite clean; preview-verified (honest empty-states on live data). Awaiting final bot
pass → merge. Owner queued 3 UI follow-ups ([[design/ui_redesign_spec]]): "Are we right?" cadence-legibility,
Calendar past-May cap, Calendar weekly-primary relayout.

## [2026-06-29] decision | Self-healing classification design — 3 owner corrections locked + PARKED

Owner (cross-checking with Gemini) refined the self-healing/auto-classify design and PARKED it as the
50-state scale unlock (after VA). Three corrections locked into [[ideas/self_healing_classification]]:
**(1) Prove-to-HIDE** — my "no proof → admin" was a regression (hides a clerk's timeless meeting for ~10h);
corrected: meeting-vs-admin is the ACTION TYPE (EventCode), confirmed-vs-not is the PROOF; a row enters the
hidden Ledger only with POSITIVE admin-proof (clerical EventCode / batch-notice law / Docket class), else it
SURFACES — meeting-kind + timeless → visible Suspense lane, never hidden. Beats Gemini's "surface all unproven"
(owner's flooding fear): only candidates/ambiguous surface, proven-clerical → Ledger. **(2) Canonical-only
learning** — the Learned Store keys ONLY on canonical IDs (EventCode/StatusID/RefidClass), never free text;
no-canonical-ID events are unlearnable (typo-immune). **(3) Structural-integrity breaker, NOT quantity** —
owner rejected Gemini's delta-on-correction-COUNT (quantity ≠ accuracy: high volume = loop working, low volume
can be catastrophic; audit #53). Breaker watches foundations: every correction ground-truth-confirmed; trip on
proof-rate collapse / vocab-drift / ground-truth self-contradiction. Then back to VA Health-observability long-tail.

## [2026-06-24] pr | Health/operator tab (Task #4) BUILT — Few bullet-graphs with danger bands (`claude/health-tab`)

Owner queue **Task #4**. Rebuilt the Health view from flat stat-cards into the operator trust surface (vision §3f / PL-8 / owner's "RPM redline"), per the scope in [[design/health_operator_tab]]. **`BulletGraph.tsx`** (new): a reusable Few bullet graph — qualitative good/warn/**DANGER** bands behind a thin measure bar + a target tick; the value's color follows its band so a danger reading pops red (Munzner popout); direction-agnostic. **`data/health.ts`** (new): LIGHTWEIGHT loader — a gviz **`tq WHERE Origin='system_metrics' or 'system_alert'`** grabs only the two SYSTEM rows (**~2 KB, not the ~5 MB sheet** — rec #1) + `range=` reads for `AA1` freshness + `W1` breaker; optional reads warn-not-silent (Standard #4). **`Health.tsx`**: **9 prioritized gauges** (critical first — Section-9 accuracy=0, completeness=100%, anomalies; then **two distinct freshness clocks** — bill backend vs calendar subsystem, different workers — rec #2; then invariant violations, outcome-drift, unclassified share, patron coverage) + a **breaker chip**, the severity-coded **`SYSTEM_ALERT` feed**, the **structural router distribution** (meeting 48.4% / admin 34.2% / executive 0.8% / blank 5.7%), and collapsible raw counters. Bands calibrated from the worker's breaker thresholds + steady state, **not magic numbers** (Standard #1); every gauge carries its denominator (PL-7); leads with the critical few (Few "emphasize by de-emphasizing" — rec #3). **Kept its `{completeness, dataAsOf}` props → App.tsx unchanged.** **VERIFIED LIVE** against the production sheet: 9 gauges on real data (Section-9 0, completeness 100%, 1 invariant violation = honest amber warn, calendar fresh 0.9h vs bill 2.7h), the `WARN/TIMING_LAG` HB30 alert renders, distribution + raw counters render; build clean, **0 console errors**. One fold-in: the column-select gviz CSV has NO header row → fixed the alert loop to iterate from row 0 (was dropping the alert). **REMAINING: the ACCESS-GATING infra** (Cloudflare Access on an operator deploy, §4 of the scope) — harmless visible now (pre-launch, no lobbyists; metrics are operational not secret); must gate before public launch. **Branch `claude/health-tab` (stacked on `claude/calendar-feature` so the PR diff is Health-only); PR base = the calendar branch, retarget to main once #166 merges.**

## [2026-06-24] session | New York sibling brain + first OpenLeg bill-engine scaffold

Owner directed the New York retune to stay clearly separated from Virginia for clarity, with scope/plan/test gates before any long-term route structure. Added a dedicated `docs/ny/` brain branch (`README`, project standards, current status, architecture, data inventory, source-scoping protocol, validation plan, owner setup, assumptions register, log) and linked it from the root index/README/CLAUDE.md. Added `ny_bill_tracker.py`, a separate OpenLeg bill-record engine that writes the Virginia product tab shape to a `NY_Bill_Tracker` tab only when `NY_SPREADSHEET_ID` is explicitly set; no fallback to the Virginia workbook. Added fixture tests and a manual-only `New York Bill Tracker` workflow (`check-config`, `dry-run`, `write`) with no schedule until full-session dry-run/write metrics are reviewed. NY-local details live in [[ny/log]].

## [2026-06-23] decision | Calendar "Time TBA" resolved structurally — IsCancelled + Description display; text-parse reverted; chain-ordering queued

Owner caught the calendar surfacing many "Time TBA" meetings and pushed hard (rightly): *"we had a time for everything except administrative actions… never hide information,"* then *"everything needs to be structural so we can trust it long-term WITHOUT intervention"* (Standard #3/#8). Deep investigation vs the **live LIS Schedule API** (session 261, one authorized verification call) resolved it **entirely structurally**: **(1)** `IsCancelled` → the worker's `Status=CANCELLED` (`calendar_worker.py:4936`) — **459/482** of the apparent "TBA" rows were **cancelled placeholders** (every Feb-17 crossover-day House committee in the screenshot was `IsCancelled=true`); front end drops them at the MEETING level (`cancelled && !held`, keeping a cancelled slot that recorded a real vote). **(2)** the **20 remaining** were active House subcommittee chains LIS publishes with a **dynamic relative-time `Description`** ("Immediately after the Transportation and Public Safety Subcommittee"); the worker already copies that `Description` verbatim into Sheet1's `Bill` column for skeleton rows (`:5082`), so the front end just **DISPLAYS** it. **KEY LESSON (owner, sharp):** *displaying the value of an API-returned field verbatim is structural; EXTRACTING/classifying from prose (keyword-marker matching) is the forbidden text-parsing.* I first tried to broaden the worker's `dynamic_markers` keyword list to catch these — **owner stopped me; reverted, worker untouched.** Also discovered the structural visibility flag **`OnCalendar`** (all 20 are `OnCalendar=False` — LIS hides them from its public calendar; the 4 genuinely-bare "to be determined" retreats are `OnCalendar=False` AND out of our date window). Result (live): Feb 17 29→13 meetings 0 TBA, ~1,613 total, **0 bare "Time TBA"**, build clean, 0 console errors. **QUEUED with a full plan (owner: "really plan it out… before you start"):** ordering the "after committee X" chains — no structural field encodes the dependency (`SortTime`=23:59; `ScheduleID`/`VersionSequence` don't match the chain), so it's a careful **Section-9-sensitive `build_time_graph`** fix (structural relative-time resolution, not front-end parsing). Plan: [[architecture/relative_time_chain_resolution]]. **Timeline owner feedback captured** (terminal stages should BRANCH — failed/died as a pipeline end-state, not a side box: [[design/ui_redesign_spec]]). Pushed to PR #166 (`33311f2`); bots re-review.

## [2026-06-23] pr | Calendar feature — integrate the calendar subsystem (Sheet1) into web/ (PR #166 OPEN)

Owner queue **Task #3**. The full "by time" lens (vision §3c): the `web/` Calendar tab now reads the perfected calendar subsystem's `Sheet1` output **read-only via gviz** — the same auth-free path the X-Ray uses, and `Sheet1` is in the SAME workbook as `Bill_Tracker`, so the existing `SPREADSHEET_ID` + a `tq` **column projection** (`select A,B,C,E,F,G,J`, ~5 MB vs ~9 MB) is all it took. **No new credentials, no worker change.** This is the long-planned calendar↔product integration, done read-only (the subsystem stays the single source of truth for times). **Grounded in the Task-#2 reading** ([[design/reading_notes]] "Calendar UI patterns", [[design/information_display]] PL-9): a **month grid = small multiples of days** (one `DayCell` ×42, Tufte) for the macro shape + a **day-agenda column** for the micro read (one geometry); **time = vertical position** (Munzner #1 channel — sorts by the displayed clock time, falls back to `SortTime` for relative/TBA); **today + the crossover guillotine (2026-02-17) the only loud cells** (Few attention / Munzner popout), weekends + out-of-month the quietest tint; chamber by quiet hue + label (never color-alone). New `web/src/data/calendar.ts` (`loadCalendar()`, lazy + **session-cached**, in-flight dedupe) groups rows into `(day, committee, time)` meetings; **excludes** the `📋 Ledger Updates` collapse + `🏛️ Governor` + meta rows; **keeps "Time TBA" meetings marked honestly** rather than silently dropping a real meeting (vision §1/§7 — caught + fixed mid-build when the first cut dropped 73 TBA meetings). The global **Tracking↔full** switch scopes it (Tracking filters meetings AND their agenda to tracked bills, so a floor session doesn't dump its ~300-bill docket); **"+N more"** expands big agendas; bill chips open the full card; honest empty/off-season + a denominator-bearing legend; calendar-specific freshness from `Sheet1!AA1`. **Verified live** against the production Sheet (715 Feb-2026 meetings, crossover marked + auto-selected, Tracking filter via starring HB1432, expand, card-open all work; `npm run build` clean; **0 console errors**; desktop two-column + mobile stacked; 37 ms cached re-open). **Architecture note added to [[architecture/calendar_pipeline]]** (front-end integration section). **Follow-up (in-code + [[state/next_session]]):** the worker should stamp the session's crossover date so the marker is structural, not the front-end `CROSSOVER_BY_SESSION` constant. **AWAITING CodeRabbit + Qodo → fold in → squash-merge.**

## [2026-06-23] ingest | Design deep-reads — Tufte VDQI (small multiples), Munzner (channels), Hearst (faceted nav) → Calendar build rules

Owner queue **Task #2** (read the remaining design books before the Calendar build; "digest full-length books… so the brain keeps growing"). Three genuine deep-reads banked to [[design/reading_notes]], focused on the calendar/encoding material the Task #3 build leans on. **Tufte (VDQI 2nd ed + *Envisioning Information*), deeper:** small multiples ("at the heart of quantitative reasoning is a single question: *Compared to what?*" — same scale/axes, vary one variable) → **a month grid IS small multiples of days** (one `DayCell` ×31); data density / shrink principle (trust the reader; show the whole day, not "+N more"); micro/macro readings (overview + detail in one geometry = the landing sliver ↔ Calendar-tab relationship); smallest effective difference (quiet cues, reserve the one loud mark for the crossover guillotine). **Munzner (*Visualization Analysis & Design*, Ch5 Marks & Channels):** the channel-effectiveness ranking — magnitude (position-common-scale > position-unaligned > length > tilt > area > depth > luminance > saturation > curvature > volume) and identity (spatial region > color hue > motion > shape); expressiveness + effectiveness principles; separable channels + preattentive popout. **Justifies our encodings rigorously:** timeline position-for-progress = the #1 channel; chamber-by-position (Senate above / House below) = the #1 *identity* channel, so the blue/red hue is redundant and can stay quiet (independently confirms PL-4); calendar **time = vertical position, never color/size**; popout needs ONE strong channel (the mechanism under Few's "saturation = attention"). **Hearst (*Search User Interfaces*, Ch1 + Ch8 Flamenco):** the 7 SUI guidelines (informative feedback, user control, reduce memory load via faceted metadata = recognition>recall, shortcuts, **avoid empty result sets**, small details, aesthetics); faceted nav specifics — **facet counts = information scent**, zero-count facets visibly disabled, **per-facet removable chips** (not one mixed breadcrumb), keyword→facet bridge, fixed categories > clusters for trust; the 32-user study (≈88–91% preferred faceted; grouping reduces the anxiety of hidden results = the lobbyist's deepest fear, vision §1). **Write-back:** new deep-read sections + a cross-source **Calendar UI patterns synthesis** in [[design/reading_notes]]; [[design/information_display]] canon table updated (Few full / Tufte+Munzner+Hearst deep-read), **new punch-list PL-9** (Calendar = month grid small-multiples + day column, time=position, hairline grid, today+crossover the only loud cells). Task #2 complete; Task #3 (build the Calendar feature) is unblocked.

## [2026-06-23] pr | UI redesign MERGED (#165, dcba4d2) — visual system + Today/Timeline; Timeline tab dropped

Owner-feedback redesign of the front end, grounded in the deep reading ([[design/reading_notes]]: Few read in full + Refactoring UI). **Visual system** (fixes the "screams-AI/stale" verdict): a real TINTED cool canvas (not white/cream — owner pref, cuts fatigue) with elevated cards; muted natural palette + saturation reserved for attention; Refactoring-UI spacing+type scales, weight+color hierarchy, shadows-over-borders. **Today relayout:** "Next up" → a **calendar sliver** (today's paper-planner day column + designed empty state); the **timeline moved onto the landing** below what's-new + a clean outcome strip. **Timeline:** redrawn from boxy columns to a **smooth integrated spine**, **crossover shrunk** to a thin seam; the **standalone Timeline tab dropped** (owner: redundant — nav is now Today·Calendar·Search·Health). Robust local date parsing (`web/src/data/dates.ts` — Date.parse drift fixed + part validation), a11y (Space/Enter, aria, focus, keyboard DiedStat, nested-Star bubble), sticky-header restructure. Reviews clean (CodeRabbit + Qodo) over two fold-in rounds (Gemini+CodeRabbit+Qodo). **Floor stage deferred** (needs a backend floor/passed-chamber signal; empty node would mislead). **Owner queue (2026-06-23, after this):** read the remaining books → build the **Calendar feature** (integrate the calendar subsystem); then the **Health/bugs tab + master site** — NB the **Health page will be access-gated** to the owner + a few (operator view; plan auth-gating for the static-SPA/gviz setup). Tasks #2–#4.

## [2026-06-22] ingest | Design reference created — information-display canon → actionable rules for `web/`

Owner queued a standing research thread: read the literature on displaying quantitative information + UI/layout (owner's #1 = Tufte, *The Visual Display of Quantitative Information*, 2nd ed.) and **log everything relevant so the brain keeps growing.** First pass synthesized into a NEW design space: [[design/information_display]] (linked from [[index]] under a new "Design" section). Grounded in the canon (Tufte VDQI 2nd ed + *Envisioning Information*; Few *Show Me the Numbers* / *Information Dashboard Design*; Hearst *Search User Interfaces* / Flamenco; Gestalt + WCAG) via web research of authoritative summaries. **19 principles, each written as an ACTIONABLE rule mapped to a specific screen** (data-ink → counts dominate the lanes; chartjunk → the crossover hatch is OK because it ENCODES danger; lie factor → honest scaling/equal stage spacing; small multiples → the §3b committee board; layering "1+1=3" → card hierarchy by weight not boxes; smallest effective difference → quiet the chamber hues since position already encodes side; Few "remove non-data pixels, reserve red for attention"; Hearst faceted nav → **add per-facet counts + avoid empty result sets** in Search; tables-vs-graphs → history is a table, timeline is a graph; never color-alone/WCAG). Produced a **7-item punch-list (PL-1…PL-7)** for the next front-end polish PR (lighten lane chrome, facet counts + disable zero-count facets, re-layer the card, audit red usage, build the committee board as small multiples, tabular figures + colorblind check, always show denominators). The page is LIVING — reading log table tracks sources done/queued (Norman, Wroblewski, Munzner next). Task #2 (the queued research) — first deliverable shipped; continues as more books are fed.

## [2026-06-22] pr | B3 FRONT-END FOUNDATION — React/Vite SPA built toward the locked vision (in `web/`)

The first real cut of the lobbyist front end (Phase B3), a $0 static SPA (React + Vite + TypeScript, zero runtime deps beyond React) that reads the worker's `Bill_Tracker` tab **client-side via gviz** — the same auth-free path the X-Ray uses (verified gviz reflects the request `Origin` in `Access-Control-Allow-Origin`, so a browser `fetch` works cross-origin from the Pages domain; the sheet must stay link-readable; completeness payload read from cell R1). **Built toward [[ideas/product_vision]]:** the global **Tracking↔full-GA switch** (localStorage star set — clients/positions still parked), the **trust header** ("data as of X ago" + "N/N bills" completeness), and the four lenses + bill card: **Today** (what's-new feed, full-day paged + outcome summary + next-up), **Timeline** (the centerpiece — crossover lanes: Senate ABOVE the centerline, House BELOW, the ✦CROSSOVER✦ divider, counts per side per stage, drill-down to bill boxes; floor stages folded into the committee flow for v1), **Calendar** (DOCKET upcoming; full calendar integrates from the calendar subsystem later), **Search** (faceted — bar + stacking filter chips, the one reused bill-box component), **Health** (the operator trust signals from the completeness payload), and the **bill card** (every fact tied to its source — vote WITH location, committee, patron — + the recovered pin + the deterministic LIS link). **VALIDATED:** `npm run build` clean (tsc + vite, 67 KB gzipped); the data layer parses the live sheet end-to-end (3645 bills, completeness extracted, HB1 correct); rendered + screenshotted every view + the card against live data — outcome counts match the backend exactly (1132 signed / 1216 to-gov / 811 dead / 443 carried / 31 vetoed / 12 in-progress), 1416 crossed-over, the timeline lanes + card provenance all correct. Co-patron sourcing investigated (no bulk blob; `LegislationByMember` ~148 bounded calls = a future throttled backfill); bonus: the bill-universe `Patrons` field carries the chief patron's FULL name + MemberID (a planned upgrade over BILLS.CSV's surname). Deploy: Cloudflare Pages, root `web/`, build `npm run build`, output `dist/`. **MERGED to main 2026-06-22 (#164, squash `7f90917`).** Reviews: CodeRabbit final CLEAN, Qodo resolved; one fold-in round — Timeline `LaneCol` children-array crash → explicit props (Gemini HIGH); localStorage throw-guards + Set char-split guard; gviz CSV header validation + fetch timeout + freshest-timestamp; chamber falls back to the bill prefix; ErrorBoundary; a11y (Space-key, aria-pressed, `:focus-visible`); LIS link prefers an authoritative `completeness.session_code` (backend-stamp = a follow-up). Re-validated: build clean, zero console errors across all tabs.

## [2026-06-22] pr | bill_tracker SCHEDULED (ban-safe) + legacy backend_worker PAUSED (ban-risk)

Owner asked to schedule `bill_tracker` and "ensure we aren't risking getting banned." **Scheduled it ban-safely**, mirroring the calendar worker's proven pattern: `bill_tracker.yml` cron `40 */6 * * *` (every 6h at :40 UTC — off the congested top-of-hour AND off the calendar worker's :00), and a new `_scheduled_gate()` in `bill_tracker.py` that, for SCHEDULED runs only (`GITHUB_EVENT_NAME==schedule`), skips 11pm–6am ET quiet hours + jitters 0–180s (guardrail #2); manual dispatch bypasses both. The job **inherits guardrails 1/3/4** (it reuses `get_armored_session()` + `safe_fetch_csv` — conditional blob fetch incl. BILLS.CSV, the retrying adapter, the per-cycle request cap) and **shares the `calendar-worker` concurrency lock** so it never overlaps a calendar cycle's LIS use. Conservative cadence because the job is light (~5 reads, mostly 304s) and bill data regenerates ~daily (bump to ~2h in 2027). **The real ban risk — legacy `backend_worker` (`update_database.yml`) — PAUSED (owner decision, same session):** it ran **every 15 min (96×/day)** with raw, UNCONDITIONAL `pd.read_csv` of HISTORY (~4.7 MB) + DOCKET + the bill-list API — no ETag/304, no jitter, no cap, no quiet hours — a blind metronome re-downloading multi-MB blobs 96×/day, the project's single biggest LIS exposure. It feeds the OLD front end being replaced by `bill_tracker` + B3. Owner: "just pause it for now" → `schedule:` commented out in the workflow (manual `workflow_dispatch` retained; trivially resumable). **NOTE: GitHub Actions schedules run only from the DEFAULT branch, so the pause takes effect when this PR merges to main.** Recorded in [[knowledge/lis_api_safety]] (new per-job cadence ledger). **MERGED to main 2026-06-22 (#163, squash `7f6d093`)** — both the bill_tracker schedule and the backend_worker pause are now live on the default branch (the 15-min worker no longer fires). Reviews: CodeRabbit final CLEAN, Qodo 0 bugs/0 violations; two fold-in rounds — gate→bool (Gemini; no sys.exit in a helper), explicit `pytz` in the workflow + requirements (Qodo BUG — was surviving only on pandas' transitive pytz), malformed-jitter WARN alert (CodeRabbit+Qodo), least-privilege `permissions` on both workflows, `calendar-worker` concurrency on the paused update_database (CodeRabbit). Validated: gate returns bool (manual→True; scheduled non-quiet→True; malformed jitter→WARN+True), compile/import clean.

## [2026-06-22] pr | bill_tracker PR3 — patron (BULK) + structural-first outcome + status-drift; subject deferred

PR3 of the forward-build backend. **Investigation first (ban-safe):** confirmed `BILLS.CSV` is a fourth bulk blob (`lisfiles/{session}/BILLS.CSV`, 3,646 rows, one fetch) carrying `Patron_id`/`Patron_name` + structural outcome fields (`Vetoed`/`Approved`/`Chapter_id`/`Carried_over`/`Failed`/`Passed`) + committee ids + full-text doc refs. **Probed for a subject blob — none exists** (clean 404 on SUBINDEX/SUBJECT/etc.; only BILLS/HISTORY/DOCKET/VOTE) and the `LegislationSubject` MVC endpoint is per-bill (a 3,645-call ban risk). **Built:** (1) chief **PATRON** in bulk (`patron`/`patron_id`, 0 per-bill calls — powers "by patron"); (2) **structural-first `outcome`** from BILLS.CSV's own fields (Standard #3), keyword path only as fallback — **fixes "Continued"→carried_over** (442 bills the PR1 keyword wrongly read in_progress) AND chaptered joint resolutions (`Chapter_id` present = enacted even when `Approved=N`, because resolutions chapter without a Governor's signature → `signed`, not awaiting_governor); (3) a **SELF-CALIBRATING outcome check, NOT a status vocabulary** — owner pushed on long-term sustainability: a status-name allow-list (hardcoded OR fetched) would need maintenance AND would false-flag forever, since LIS is internally inconsistent (its bill feed emits bare "Continued", absent from its OWN `GetLegislationStatusListAsync` reference). Instead the keyword fallback is validated each run against LIS's OWN structural flags (the oracle) → a mismatch RATE; **zero hardcoded vocabulary, zero maintenance (Standard #1/#8), zero extra LIS calls.** **SUBJECT deferred** (no bulk source; documented in [[lis_data_inventory]] §6). New trust counters: `bills_meta_rows`, `outcome_structural`/`outcome_keyword_fallback`, `patron_present`/`patron_missing`, `outcome_keyword_mismatches`+`_rate`. **Offline-validated on real 2026 data: 3645/3645, patron 3645/3645, outcome 3633 structural / 12 keyword-fallback (all status "Introduced" resolutions → in_progress); keyword-vs-structural mismatch 1 bill (HB30, benign In-House+Carried_over), rate 0.03%; outcome dist now 1:1 with the raw status counts — signed 1132 / awaiting_governor 1216 / dead 811 (=725 Failed+86 Incorporated) / carried_over 443 / vetoed 31 / in_progress 12.** The reconciliation EARNED ITS KEEP: it surfaced the 8 joint-resolution mislabels, which drove the `Chapter_id` fix. **MERGED to main 2026-06-22 (#162, squash `0023c47`) + VALIDATED LIVE** (run 27963083941, success): `✅ 3645 bills; Completeness 3645/3645; 0 anomalies; 1416 crossed over; 3645 with patron; Outcome 3633 structural / 12 keyword-fallback; keyword-vs-structural mismatch 0.03%` — matches the offline build exactly. **Reviews:** the redesign resolved Qodo's two structural concerns (the `_KNOWN_BILL_STATUSES` runtime-validation gap — which Qodo independently flagged, confirming the owner's sustainability instinct — and the untagged `continue`); the fold-in addressed Gemini (`series()` header-variant robustness), Qodo (the "Passed House" single-chamber mislabel), and CodeRabbit (BILLS.CSV skip counter + an explicit `bills_meta_rows==0` total-failure alert); CodeRabbit final review CLEAN, Qodo 0 bugs / 0 violations; Codex rate-limited. New LIS quirk recorded in [[knowledge/lis_api_reference]] (bill-feed `LegislationStatus` ≠ `GetLegislationStatusListAsync`). Manual-dispatch only (not scheduled yet).

## [2026-06-21] decision | Vote meeting-TIME is the calendar subsystem's domain — sourced at integration, never re-derived in bill_tracker

Qodo (PR #161) flagged that the bill card's `latest_vote` carries `{tally, location, date}` but no meeting TIME, applying the calendar's "every meeting action needs a time" rule (CLAUDE.md Current Goal / X-Ray Section 9). Owner steer: **"do what's most sustainable and accurate long-term."** Decision: **the calendar subsystem is the single source of truth for meeting times** (convene-time graph, Schedule-API matching, time-resolution priority — hardened to 100% over many PRs). Building a SECOND time-resolution path inside `bill_tracker` would create drift between two engines computing the same fact (anti-patterns [[gemini_review_patterns]] #14/#27 — divergent sibling logic) and would be a hasty re-derivation, not the proven times — i.e. the *least* sustainable + accurate option. **Contract: the bill card's vote TIME is SOURCED FROM the calendar subsystem at the calendar↔product integration (roadmap B/C) — never re-derived in bill_tracker.** For now `latest_vote` carries date+location+tally (complete + honest for the card's lens — it shows what it knows, the date being the right granularity for a PAST vote; it does not pretend to a time it hasn't sourced). The Section-9 meeting-time rule is scoped to the CALENDAR output (the time lens), not every artifact. This is recorded so no future change adds a duplicate time-resolution path. Qodo #1 left open by design (documented decision, not an oversight); CodeRabbit full-review CLEAN; Codex rate-limited.

## [2026-06-21] pr | bill_tracker PR2 — structural position + vote-with-location + upcoming (DOCKET)

The intricate structural layer on the PR1 spine, all derived from refids (Standard #3 — no text classification, no probabilistic guess). Reuses `calendar_worker`'s `build_committee_maps` (populates the global `COMMITTEE_CODE_MAP`) + `resolve_committee_from_refid` (which reports whether a refid is a direct committee referral vs a committee vote). New per-bill fields: **chamber** + **crossed_over** (a CERTAIN structural fact — the bill had a committee action in the chamber opposite its origin) + **last_committee** + **referral_count** (distinct sequential committees it was referred to — the 1st/2nd/3rd-referral badge); **latest_vote** = `{tally, location, date}` where the tally is a DISPLAY of LIS's own published tally and the location is structural (committee from the vote refid, else Floor); **upcoming** = future committee meetings from DOCKET.CSV (empty off-season, correctly). Key stance: **LIS's own `status` stays the authoritative "where it is"** — these are certain facts layered on top, never a re-guessed location state machine. Committee-map build and DOCKET are enrichment (fail soft to the static map / empty, never hard-fail the spine). New trust counter `docket_unparseable_dates`. Unit-tested the derivations offline (House→Senate crossover, subcommittee-vote refid `H14003V…`→parent H14, floor-vs-committee vote location, date parsing) — all pass. Deferred to PR3: patron + subject ingests (need a bulk endpoint — per-bill over 3,645 bills is a ban risk) and the true status-drift check (reuse `validate_status_grouping`).

**MERGED to main 2026-06-22 (#161, squash `db38981`) + VALIDATED LIVE** (run 27958608279, success): `✅ 3645 bills written; Completeness 3645/3645; 0 in-history-not-in-universe; 0 skipped; 0 prefiled-no-history; **1416 crossed over**` — the new structural position derivation works on real data (~39% crossover, plausible: most bills die in committee). Committee maps rebuilt from the live API (25 codes); `upcoming` empty (correct — session adjourned). Reviews: **CodeRabbit full-review CLEAN**; Gemini + Qodo findings folded in (ET-vs-UTC date bug, refid upper-casing, heuristic docs, metric denominator+rate, broad-except diagnostics, continue tagging, frontmatter); **Qodo's vote-meeting-time item resolved by the 2026-06-21 decision above** (calendar subsystem owns meeting-time, sourced at integration); Codex rate-limited. Captured review pattern [[gemini_review_patterns]] #47 (`date.today()` for ET-domain comparison). Manual-dispatch only (not scheduled yet).

## [2026-06-18] decision | Stack = React+Vite/Cloudflare Pages; bill backend = structural rebuild, NOT port the old text logic

Owner: "use the old logic but it had a lot of problems, be careful" + "if the alternatives are better than Streamlit, choose the best and go." **Stack DECIDED: React + Vite, free on Cloudflare Pages** (never-sleeps CDN, full UI control for the crossover timeline; reads the Sheet via gviz like the X-Ray — $0 end-to-end). Streamlit's case (free Community Cloud, Python-native, we know it) lost to the rich-interactivity need. **Backend assessment (the "be careful" diligence): the old `backend_worker.py` bill logic is ENTIRELY text-parsing** — regex committee scrape, `desc.startswith("h ")` chamber hack, hardcoded English death/admin macro lists, `on_bad_lines='skip'` silent drop — i.e. every anti-pattern the calendar accuracy effort eliminated. **Decision: reuse its data MODEL + lifecycle/stage CONCEPTS, but REBUILD the implementation on `calendar_worker`'s structural engine** (committee codes, refid resolution, structural router, LIS vocabularies, completeness-guarded fetch); derive bill records from the structural per-bill state the worker already computes, not a second text pass. Completeness check starts free (processed bills vs HISTORY distinct bills). Details in [[ideas/product_roadmap]] §B0. Next: build the structural bill-record pipeline.

## [2026-06-21] pr | #159 MERGED + VALIDATED LIVE — bill_tracker PR1 (the new product backend spine)

The first real piece of the forward-build lobbyist-product backend (`bill_tracker.py`), structural not text-driven, reusing `calendar_worker`'s guarded machinery (auth gate, request-capped session, truncation-guarded fetch) + dynamic session derivation. Emits the `Bill_Tracker` tab (universe + title + raw status + outcome label + action/date history + trust fields) the React/Vite front end will read via gviz. **Live validation (manual dispatch, run 27910495183): `✅ Bill_Tracker written: 3645 bills; Completeness 3645/3645; 0 in-history-not-in-universe; 0 skipped`** — the `getlegislationsessionlistasync` 5-digit contract works, the free completeness trust signal is perfect, the grid-resize + batched Sheets write work. Hardened through ~15 findings across FOUR reviewers: Gemini (correctness — None/NA leak, iterrows/NA crash, CRITICAL gspread grid-limit, empty/missing-data fail-safes), CodeRabbit (security + observability — categorized alerting, source-miss counter, persist-credentials), Codex (a real logic bug — unrecognized-status noise), and **Qodo** (caught a precedence-confusing universe parse the other three missed — validating the reviewer-bench rebuild). Manual-dispatch only (not scheduled yet). **PR2 = the intricate structural part (position via the STM: chamber lane/crossover side/committee/referral; vote-with-location via VOTE refid; upcoming via DOCKET; patron+subject ingests; the real status-drift check).**

## [2026-06-21] decision | Reviewer bench rebuilt for the Gemini sunset — CodeRabbit (tuned) + Qodo + Codex

Gemini Code Assist review ceases ~2026-07-17. Evidence from #159 (first real code): the bots split by LENS — Gemini = correctness/runtime bugs, CodeRabbit = security/observability, Codex = targeted logic; CodeRabbit caught ZERO of the correctness bugs, so losing Gemini would lose that lens. Actions: (1) **tuned CodeRabbit** (#160) with a `**/*.py` directive to prioritize correctness/runtime/data-integrity classes (NA handling, pandas pitfalls, API/grid limits, fail-safes) + trimmed its walkthrough for speed (it ran ~6 min and re-raised already-fixed items — noisy + slow); (2) **owner added Qodo Merge** (qodo-merge-pro GitHub App, 14-day unlimited trial then free tier ~75 PRs/mo) — the reliable correctness primary, independent of Codex's fast rate-limits, and it immediately earned it (the parse catch). Bench now: CodeRabbit + Qodo + Codex (+ Gemini till July) — no single point of failure.

## [2026-06-18] decision | B1 product vision LOCKED → [[ideas/product_vision]]

Multi-session design stew converged into the locked front-end spec. Highlights: **one dataset, four lenses** (urgency/stage/time/name) + a single global `Tracking ↔ full GA` switch every view obeys. **Landing** = full-day "what's new" feed (no per-user read-state; Slack on-demand digest) + the **crossover-lane timeline** as hero + mini-calendar. **Timeline:** Senate permanently above the centerline, House below, so a bill *literally crosses the line at crossover* (crossover = a single session deadline/guillotine, also marked on the calendar; bills that never cross are stranded-left = visibly dead). Overview = counts per side; committee drill-down = a board (committees as columns, money-committees last, subcommittee subheaders, expandable bill boxes), House/Senate committees never melded (distinct H/S codes). **Bill card:** recovered model + the recovered **pin** (`shadow_v2.py:420` — status feed ahead of history → provisional row on top) + the **correlation rule** (every fact carries its source location; next-meeting names its committee, vote names where it happened; never a false link). **Search:** bar + filter buttons (chamber = buttons, not a switch). **Bug/health tab** = operator view of existing diagnostics. **The trust layer (first-class):** freshness/completeness/certainty — "the product may not know something but never pretends to" — with six tracking gaps to close (bill-count completeness, per-bill freshness, generalized feed-skew, universal provenance flag, scope disclosure, surface upstream changes), several of which are B2 questions. Parked: clients/positions (single-org now, leave a position column), the historical tracker (separate state-level analytics pass). **Next: B2 — the LIS data inventory.** Full spec + decisions-and-why in [[ideas/product_vision]].

## [2026-06-18] decision | Direction shift — NO subsystem merger; forward-build the product; reviewer swap to CodeRabbit

Owner decisions after the speed/safety/flip work landed: (1) **Do NOT merge the calendar subsystem back into the old `backend_worker.py`/`v2_shadow_test`** — retrofitting the advanced engine into the old case is counterproductive; forward-build a purpose-built product instead. (2) The next chapter is the **product/UI**: define the lobbyist's jobs-to-be-done (vision) → inventory what LIS data we have vs. don't (gap analysis, may require DB expansion for non-calendar features) → design the most efficient/intuitive UI (owner wants me to do "a lot of reading" on information display first). Sequence is deliberate (vision → data → UI) to avoid designing without a defined goal. (3) **Replace the sunsetting Gemini reviewer** (review ceases ~2026-07-17) with **CodeRabbit** (free for this PUBLIC repo, best-in-class) + keep Codex → two-reviewer coverage. `.coderabbit.yaml` committed (tuned to no-silent-failures / Standard #3 / LIS-safety). Owner installs the GitHub App. Comprehensive plan with explicit per-item GOALs (anti-looping) → [[ideas/product_roadmap]]. The old "Section 9 residual polish" is moot (Section 9 already 0); only the Part C verb-prefilter migration remains as a someday-maybe internal tidy. **`current_status` active focus updated to point at the roadmap.**

## [2026-06-17] pr | #157 MERGED — the incremental-STM flip (subset-STM + cache reuse), flag-gated & dormant

The in-season time lever, built to a 100% bar over ~9 review rounds (several REAL bugs caught — the high-risk change earned the scrutiny). `STM_INCREMENTAL_PRIMARY`: `""` off (default, full STM, **no production change on merge**) | `shadow` (full STM drives Sheet1+telemetry; the EXACT incremental path runs in isolation and must prove events + breaker counters identical) | `1` (incremental drives Sheet1). Mechanics: subset-STM on changed bills (fresh per-bill state) + reconstruct unchanged bills' events from `STM_Bill_Cache` THROUGH `_append_event`.

**Correctness pillars (what makes it 100% on what matters):** (1) CALENDAR identical — proven by order-invariance + cache shadow + day-by-day replay, and re-proven each `shadow` cycle. (2) BREAKER exact — every counter it reads (`invariant_violations`/`rows_appended` rate, `meeting_unsourced` Y2, `_unconfirmed` Y3-from-final-events) is event-derived, so `_append_event` reproduces them. (3) TYPE FIDELITY — `_stm_event_key` str-coerces, so the cache stores `AgendaOrder` (only int field, −100..999) as a string; `_reconstruct_stm_event` restores the int (the shadow CAN'T see this — it str-coerces — so it's locked by `test_incremental_flip.py`). (4) `_compute_stm_shared_sig` extracted (one definition, shared with the cache shadow, can't drift).

**Real bugs the review caught + fixed:** shadow restore was inside the try → a shadow exception would write CORRUPTED `master_events` to Sheet1 (→ `try/finally`, always restore); PHANTOM events for a bill that leaves HISTORY (→ skip cached bills not in `legevent_history_hashes`); `_floor_miss_dates` side-effect leak in the shadow; corrupt-cache iteration crashes (`isinstance` guards). Primary mode is FAIL-SAFE: any incremental failure discards the partial + runs the full STM (accuracy > speed).

**Telemetry — reasoned, not a gap:** process-observability counters (`dropped_noise`, `total_processed`, `legevent_cache_*`, `*_recovered`, `sourced_*`, `_floor_hit/_floor_miss`) are NOT in the events and can't be honestly mirrored; they correctly report only the changed bills processed and feed nothing downstream (`_floor_hit/_floor_miss` are STM-internal). A partial mirror would be *wrong*, not complete. The shadow surfaces these deltas (observe-only) so they're visible, never alarmed.

**ROLLOUT (owner): set repo var `STM_INCREMENTAL_PRIMARY=shadow` → watch for `✅ INCREMENTAL-PRIMARY SHADOW MATCH` (and zero `🚨 DIVERGENCE`) over a window incl. a crossover-style busy day → then `=1` for the ~180s→~6s STM win (8min→~5min in-season).** Unset to revert instantly. See [[ideas/future_improvements]] Step 6.

## [2026-06-17] session | LIS-safety guardrails #1/#2/#4 all SHIPPED; the flip is the remaining lever (with a telemetry risk found)

Autonomous run through the post-replay TODO list. **Merged:** #153 (guardrail #1 conditional fetch, HISTORY+DOCKET), #154 (guardrail #1 extended to VOTE.CSV — all three blobs), #155 (guardrail #2 jitter on scheduled runs), and #156 (guardrail #4 hard per-cycle request ceiling — `_CountingHTTPAdapter`, counts in `send()` before retries per Codex P1, resets at cycle start per Gemini). So **3 of the 5 charter guardrails are now in code** (#3 backoff was already present); only #5 (meeting-driven cadence) remains, and it is gated on the flip. See [[knowledge/lis_api_safety]].

**FLIP RISK FOUND (why it's not a rush job).** Confirmed the flip is *mechanically* tractable: every `master_events` event has EXACTLY the 14 `_STM_EVENT_KEY_FIELDS` (verified: `_REQUIRED_KEYS` = 11 base + `_append_event` adds `LegEventRoute`/`RefidClass`/`ScheduleClass`), so the `STM_Bill_Cache` keys reconstruct full events losslessly via `dict(zip(_STM_EVENT_KEY_FIELDS, key))` — no cache-format change needed. **BUT** the incremental-PRIMARY path (subset-STM on changed bills + reconstruct unchanged from cache) has **telemetry/breaker side-effect coupling the existing event-only shadow does NOT validate**: `source_miss_counts` like `meeting_unsourced` (feeds the **Y2 Section-9-regression breaker**) and `scheduleclass_*` are produced per-bill inside `_append_event`/the STM; reconstructing unchanged bills' events does not reproduce their per-bill telemetry contributions, so the breaker inputs would differ between full and incremental. The `shadow` validation mode (run full for Sheet1 + telemetry, compute incremental observe-only) is safe, but the PRIMARY mode needs the telemetry/breaker handled (cache per-bill telemetry, or recompute the affected counters) BEFORE it can drive the lobbyist surface. Owner-facing decision — not shipped autonomously. Detail in [[ideas/future_improvements]] Step 6.

First guardrail off the [[knowledge/lis_api_safety]] charter. `safe_fetch_csv` now sends `If-None-Match` with the cached ETag; on **304** (Azure-verified: the 4.7 MB HISTORY.CSV returns 304/0-bytes when unchanged) it reuses bytes from `.lis_blob_cache/` — persisted across runs via a new `actions/cache` step (unique key + `lis-blob-cache-` restore-keys) — and **skips the multi-MB transfer**. Accuracy-safe BY DESIGN: a 304 is Azure guaranteeing byte-identity, the reused bytes still pass the SAME completeness/marker checks as a fresh download, and ANY fault (length mismatch, junk bytes, unreadable, disabled) drops the cache and falls back to a full unconditional GET → the parsed DataFrame is identical either way. Kill switch `LIS_BLOB_CACHE=0`. 5 unit tests (200-write / 304-reuse-identical-DataFrame / corrupt-cache-fallback / kill-switch / length-guard). Cuts upstream **bytes** (the prereq for raising cadence safely); request count unchanged. VOTE.CSV (separate ragged-CSV path) still re-downloads — TODO. Helpers: `_blob_cache_paths`/`_read_blob_cache`/`_write_blob_cache`, `blob_cache_stats`.

## [2026-06-17] decision | LIS API Safety charter created — meeting-driven cadence; shadow proven on real reuse path

Owner asked (1) to write the LIS-safety policy *centrally* and (2) whether 4×/hour during business hours is sustainable / should be triggered by actual meetings. New page [[knowledge/lis_api_safety]] (sibling of [[knowledge/lis_api_authorization]]): the standing rule = our load must correlate with genuine legislative activity, never be a blind metronome. **Five guardrails** (status today): #1 conditional fetch ⚠️ partial (agenda/LegEvent/STM cached but blobs still re-downloaded — ETag layer unshipped), #2 jitter ❌, #3 backoff+breaker ✅ (`urllib3 Retry backoff_factor=2 status_forcelist=[429,500,502,503,504]` + W1/X1 data breaker), #4 hard daily cap ❌, #5 activity-correlated cadence ❌. **Cadence policy = meeting-driven** (owner's proposal, endorsed): 4×/hour ONLY in real Schedule-API meeting windows (structural, not admin actions), hourly/3h otherwise — dissolves the off-season interim-meeting objection because it keys off actual meetings not the session flag. **Assessment:** 4×/hour *in meeting windows* is sustainable once guardrails #1/#2/#4 ship; 24/7 4×/hour is NOT the proposal. The current conservative 3h/no-jitter cadence is safe precisely because it compensates for the missing guardrails — **do not raise cadence until #1/#2/#4 land.** Sequenced in [[ideas/future_improvements]].

**Shadow VALIDATED on the real reuse path (2026-06-17):** owner set `STM_INCREMENTAL_SHADOW=1`. Cycle 1 trivially recomputed all (cold cache, `shared_changed=True`); the next cycle logged `✅ INCREMENTAL SHADOW MATCH — 3645 bills reused, 0 recomputed (shared_changed=False)` — first proof the pure-reuse path reproduces the full output exactly.

## [2026-06-17] pr | #152 MERGED — incremental-STM replay sim (day-by-day 2026 validation, LIS-free, passive)

The strongest pre-2027 validation: runs ONE normal cycle, then replays the 2026 session at session-day checkpoints **entirely in memory** (the STM is cache-lookup-only → ZERO network), proving `incremental==full` at each checkpoint on real in-season deltas; CRITICAL alert on any divergence; snapshot/restore-protected so it never perturbs the cycle. Gemini #152 (high) caught the per-day `groupby`+`iterrows` on the growing slice → fixed with one-pass incremental hashing + `STM_REPLAY_STRIDE` (default 5 → ~18 checkpoints, ~30 min; =1 for exhaustive); also corrected Gemini's misattribution (the ~90 full-STM re-runs dominate, not the hashing). Lesson → [[failures/gemini_review_patterns]] #46. Workflow `stm_replay_sim.yml` (manual, shares the worker lock, 350-min ceiling). **VERDICT (2026-06-17): `🎬✅ REPLAY SIM PASSED — 28 checkpoints across the session, incremental==full at EVERY one` (133 session-days, stride 5, 311s).** Combined with order-invariance + the real-cycle shadow (3,645 reused / 0 recomputed / match), the incremental engine is now validated on real in-season deltas — **the flip (3c) is green-lit** (no longer must wait for the 2027 session).

## [2026-06-17] pr | #150 + #151 MERGED — INCREMENTAL-STM ENGINE BUILT (shadow mode); flip awaits real-cycle validation

The engine, complete in safe SHADOW mode. **#150 (engine core, 3 Gemini rounds incl. a real `Counter(unhashable list)` crash):** `_stm_incremental_shadow(full_events, current_hashes, shared_changed, prev_cache)` — reuses a bill's cached events when its HISTORY hash is unchanged AND shared inputs didn't move, else recomputes; DIFFs incremental vs full. Pure, 6+ unit tests (reuse/recompute/divergence-caught/None-safe/JSON-list-safe). **#151 (cache + every-cycle shadow, 2 Gemini rounds incl. 2 real shared-input-completeness catches):** `STM_Bill_Cache` tab `{bill->(HistoryHash,EventsJSON)}` + `__SHARED_SIG__` row (fail-safe load/persist, agenda-cache pattern, chunked); shared-input signature = canonical hash of docket+vote+schedule+convene(**incl Name→Committee**)+session; shadow hook (`STM_INCREMENTAL_SHADOW=1`, flag-gated) builds incremental from last cycle's cache + this cycle's full contribution (`master_events[_pre_stm_len:]`), logs MATCH or CRITICAL-alerts divergence, **never changes production output**. Wired into the production worker via repo var `vars.STM_INCREMENTAL_SHADOW` (no extra cycle → **no extra LIS load**; `STM_Bill_Cache` registered overwrite-BOUNDED in the audit). Gemini's two #151 catches (malformed-cache silent-loss; convene `Name` missing from the sig) were exactly the shared-input-completeness risks the shadow exists to surface. **REMAINING = the flip (3c)**, gated on the shadow proving `✅ INCREMENTAL SHADOW MATCH` (zero divergence) over many real cycles — inherently time-gated, not collapsible into a session. **To start validation: set repo VARIABLE `STM_INCREMENTAL_SHADOW=1`.** Design: [[ideas/future_improvements]] Step 6.

## [2026-06-16] milestone | ✅ STM ORDER-INVARIANCE PROVEN ON REAL DATA — incremental engine GREENLIT (+ #149 oracle fix)

The gate for the incremental STM. **First oracle run (27660470113) flagged `only-date=2493` — but it was a BUG IN THE ORACLE, not the STM:** the variant events were all `Source=API_Skeleton` phase-1 schedule rows (board/commission meetings) already in `master_events` before the STM ran; the oracle compared the WHOLE `master_events` while the re-run's reset dropped that phase-1 prefix. Caught only by investigating the red instead of trusting it. **#149 fix:** capture `_pre_stm_len` before the STM call, compare only `master_events[_pre_stm_len:]` (the STM's own contribution); reset/restore via `del master_events[_pre_stm_len:]`. **Re-run (27661570960) verdict: ✅ ORDER-INVARIANCE HOLDS — 58,294 events byte-identical under date-order vs bill-grouped order.** Per-bill decomposition is PROVEN output-safe on the real 2026 session → the incremental engine (PR3) is greenlit. Methodology fully vindicated: the static code-read had a hole (the `+=` accumulators, #147), and even the oracle had a bug — only the layered, prove-don't-assume discipline (extract → oracle → investigate red → fix → re-prove) got to a trustworthy result. **Next: PR3 incremental engine** — per-bill event cache (reuse unchanged bills' events), shared-input-split signature (full recompute when schedule/docket/convene move, else reprocess only HISTORY-changed bills), SHADOW-validated against the full run via `_stm_outputs_equivalent` before the flip-to-primary. Design: [[ideas/future_improvements]] Step 6.

## [2026-06-16] pr | #148 MERGED — incremental-STM step 2: cross-bill order-invariance ORACLE (flag-gated)

The differential proof the incremental engine rests on: re-run the full STM in CleanBill-grouped order on the SAME inputs and assert the OUTPUT MULTISET equals the date-order run — if a bill's events are independent of cross-bill interleaving, per-bill decomposition is output-safe. OFF in production (`STM_ORDER_INVARIANCE_CHECK=1` gate; doubles STM time); dedicated workflow `stm_order_invariance.yml` (manual + weekly) runs it on real 2026 data. **4 Gemini rounds, each caught a real isolation bug in the oracle** (the careful-build discipline working): no-op closure-silencing → resolved by snapshot+restore of `alert_rows`+`_alert_dedup_keys`; unstable same-(bill,date) tie order → `sort_values('CleanBill', kind='stable')` preserves within-bill production order; + restore `master_events`/`source_miss_counts` so the re-run NEVER perturbs the cycle. Comparison via `_stm_outputs_equivalent` (multiset, order-independent, diff-surfacing). **Oracle dispatched (run 27660470113) for the real-2026 verdict — the gate for PR3 (the incremental engine).** If it HOLDS → greenlit; if VARIANCE → a hidden cross-bill dependency to root-cause before any incremental code ships.

## [2026-06-16] pr | #147 MERGED — incremental-STM step 1: extract the STM into run_sequential_turing_machine (behavior-preserving)

Foundation for the incremental engine (the real in-season lever) + the differential oracle: lifted the 660-code-line per-row STM loop out of the 6,000-line `run_calendar_update` into a module-level `run_sequential_turing_machine(df_past, **inputs)` so it's callable in isolation. **Pure verified MOVE, no logic change** — script-generated with three static proofs (line-for-line identical body, AST-proven self-contained, compiles). **Gemini caught a CRITICAL my proof MISSED:** `_floor_hit`/`_floor_miss` are `+=` accumulators, and my `loaded-minus-stored` free-var analysis silently drops them (a `+=` both loads AND stores) → `UnboundLocalError`. Fixed (thread in + return; caller unpacks) + re-verified with a corrected augassign-aware analysis (zero remaining). **Lesson → [[gemini_review_patterns]] #45** (and the textbook case for why the runtime differential oracle is non-negotiable — a clean static proof can still have a hole). **Deferred (out-of-scope for a pure move):** Gemini also flagged `or`-on-nullable-pandas patterns + stale line-number comments in the moved body — pre-existing, production-validated code; a behavior-preserving move must not touch the body, so these go to a separate follow-up. **Next:** PR2 = differential-replay harness (full-STM oracle + in-season measurement); PR3 = incremental engine (ships only when `incremental == full` across the whole 2026 session).

## [2026-06-16] pr | #145 MERGED — worker speed stage 1: prefetch HISTORY.CSV (download hidden, 0.0s) — but win is noise-floor

Stage 1 of the warm-8m speedup (owner chose "both, staged"). Prefetch DOCKET+HISTORY Azure blobs concurrently (`ThreadPoolExecutor`, 2 workers) at the top of the fetch section so the 4.7 MB HISTORY.CSV download overlaps phase 1. `safe_fetch_csv` uses its own `requests.get` (not the shared `http_session`) → thread-safe; same bytes, same #68 completeness guards, empty-frame-on-failure preserved. **Verified live: the new `⏱️ PHASE HISTORY.CSV download` mark = 0.0s** (fully hidden). Clean Gemini review (0 findings).
**HONEST RESULT — small win, swamped by variance:** this verification run was 9m26s vs the prior warm 8m15s. The Sheets writes alone varied ~2× run-to-run (LegEvent persist 23→38s, Sheet1 12→23s) and the STM 181→215s — all environmental (GitHub runner + Google Sheets API jitter), not the change. So the ~20-40s download-hide is **inside the ±30-60s single-run noise floor**. Lesson: the worker's wall-time is NOISY (Sheets jitter on top of GitHub's queue delay), so trimming a fixed 8m can't make cycles *reliably* fast — only **skipping the heavy work when inputs are unchanged (stage 2)** can. **Azure blobs DO return ETag/Last-Modified** (enabler for stage 2's download-skip), but off-season DOCKET+VOTE are regenerated DAILY (fresh ETag at 16:00 GMT) while HISTORY is stable through the day → stage 2 must CONTENT-hash, not trust ETag (ETag-304 = fast-path skip; ETag-changed → download + content-hash → still skip recompute if content identical). Stage 2 design (signature + 3 backstops + Sheet1-integrity) in [[ideas/future_improvements]] worker-speed.

## [2026-06-16] pr | #143 MERGED — Slack ops alerts (CRITICAL worker + sentinel FAIL → webhook)

Owner ask: wire bug notifications to Slack (the old product versions used `slack_sdk` to broadcast bill updates to subscribers — a different use case; this is ops/bug alerting from the worker). Added `notify_slack()` (worker, requests) + `_notify_slack()` (sentinel, stdlib urllib so it stays dependency-free), both **dormant until the `SLACK_WEBHOOK_URL` repo secret is set** (no-op → worker/sentinel run byte-identically pre-wiring). **CRITICAL-only by design** to keep the channel high-signal: hooked into `push_system_alert` (severity==CRITICAL → covers breaker trip, LIS auth failure, I1–I3 data anomalies), the breaker STUCK escalation (explicit synchronous ping before `sys.exit(1)`), and the accuracy-sentinel FAIL (names the breached invariant). Both workflows pass the secret. Never raises / 8s cap so a Slack outage can't fail or slow a cycle. New [[architecture/alerting]] documents all three channels (in-sheet `SYSTEM_ALERT` / GitHub failure email / Slack) + every tripwire + the one-time webhook setup. **Owner action to activate: create a Slack Incoming Webhook, add it as repo secret `SLACK_WEBHOOK_URL`.**

## [2026-06-16] pr | #142 MERGED — public data-freshness marker Sheet1!AA1 (site "data refreshed X ago")

Owner ask: persist the time of the last SUCCESSFUL calendar run (distinct from the GitHub dispatch time, which precedes a variable queue delay) so the site can show lobbyists how recent the data is — and surface a major GitHub delay. Added `Sheet1!AA1`, written on every successful cycle with `_cycle_end_utc_iso` (the same real-UTC value as the `Y1` backfill cursor, but a SEPARATE stable public contract decoupled from Y1's internal semantics). Only a fully successful cycle reaches the write, so a failed/delayed/halted run leaves the last-good time and the site correctly shows staleness. Site reads `gviz…&sheet=Sheet1&range=AA1&headers=0`. State-cell map updated in [[architecture/calendar_pipeline]].

## [2026-06-16] pr | #141 MERGED — sentinel staleness false-fire fix (S1=ACTIVE outlived the session)

Caught during #140's live verification: the accuracy sentinel went **red** at 21:28 on 2026-06-15 (first cycle after #138's staleness gate deployed) — `[FAIL] STALENESS: newest action 2026-05-05 is 29 business days old during an ACTIVE session`. Root cause: `_session_active` trusted LIS `IsActive` alone, but `IsActive` stays True through the post-sine-die interim, so `S1=ACTIVE` mislabeled an adjourned session and the freshness gate expected data that legitimately wasn't coming. **NOT** caused by the agenda cache (orthogonal). Fix: `_session_active = is_active AND now <= session_end` (schedule-gated; `_session_active` has exactly one consumer, the S1 write). S1 must stay schedule-derived, never data-derived, or the gate it feeds could never catch a real freeze ([[failures/assumptions_audit]] #90). Speedup also confirmed this run: **#1399 cache-cold 20m44s → #1400 cache-warm 8m8s** (actual compute ~2m; rest is GitHub queue delay). Truth-table tested. Prereq for the Slack ops channel (a cycle-stable false-fire would spam it on cycle 1).

## [2026-06-15] pr | #140 MERGED — worker speed: agenda PDF-parse cache + pdfminer flood silenced

Speed audit ([[ideas/future_improvements]] worker-speed). Owner screenshot showed the worker step at **11m40s, still running**, the Actions log flooded with `pdfminer` `Could not get FontBBox` warnings — i.e. **agenda/docket PDF parsing**, not the Sheet1 write the #139 hypothesis had guessed (buffered stdout had swallowed the `⏱️ PHASE` lines). `extract_rogue_agenda` re-fetched + re-PDF-parsed **every** agenda in the scrape window **every cycle, uncached**; off-season it re-parsed the whole immutable adjourned-session set each run. Fix: **`Agenda_Cache`** tab (`url -> bills`) reused only for **settled (>2d-old)** meetings (immutable dockets skip fetch+parse; recent/future always re-parse). Pure speedup + fail-safe (any cache failure → parse fresh, no accuracy loss). New `fetch_ok` return on `extract_rogue_agenda` gates caching so a transient-empty is never frozen as a real "0 bills" ([[failures/assumptions_audit]] #89 — sentinel-collision class of pre-push audit #15). Date-keyed col A + 540d prune-on-load keeps the tab bounded (registered in `sustainability_audit` `RETENTION_DAYS`). `pdfminer` logger silenced to ERROR. 8 cache-logic unit tests pass.

**Gemini fold-in (3 rounds, merge commit 218a0de):** **r1 CRITICAL** — a transient `get_all_values()` failure returned an empty cache with a valid ws handle, so the end-of-cycle `clear()`+rewrite would have **wiped the whole tab** with one new row; fixed with an explicit `load_ok` boolean (declined Gemini's magic-string sentinel — that's the very anti-pattern this PR teaches; [[gemini_review_patterns]] #42). **r2 MEDIUM** — `delete=False` temp PDF leaked on the parse-exception early-return; moved cleanup to `finally` ([[gemini_review_patterns]] #43). **r3 HIGH — DISMISSED as a false positive (misapplied to the wrong worksheet):** Gemini flagged `ws.clear()` wiping state cells (the real #133 lesson) — but state cells (S1/T1/U1/V1/W1/X1/Y1/Z1) live on **Sheet1** (re-written every cycle at L6033/6083/6095); `_persist_agenda_cache`'s `ws` is the isolated 3-col `Agenda_Cache` tab with NO state cells. Dismissal documented on the PR with evidence. **Next: live re-measure** (1st post-merge cycle populates the cache; 2nd should drop sharply) + confirm green + accuracy unchanged via the chained sentinel.

## [2026-06-15] pr | #138 + #139 MERGED — SRE guard hardening + worker phase profiling

**#138 (SRE guards, from a senior-SRE review of the 5-layer matrix):** (A) **consecutive-trip escalation** — a single breaker trip stays green (in-sheet only); now T1 counts trips-in-a-row (survives the trip cycle, reset on a healthy write) and the 3rd consecutive trip does sys.exit(1) so the run FAILS → GitHub emails (escalates past in-sheet). (C) **staleness gate** — guards checked data SHAPE not FLOW; worker now writes Sheet1!S1=ACTIVE/ADJOURNED (LIS IsActive) and the sentinel, only while ACTIVE, FAILs if the newest action Date is >2 business days old (weekend-aware, ET-correct). (chain) accuracy_sentinel.yml now also runs on workflow_run AFTER the worker, so a regression is caught on the data that just landed, not up to a day later. (B "suspense overflow" needed no change — the sentinel already caps unconfirmed at 150.) State cells verified non-colliding: data is 14 cols (A-N); S1(19)/T1(20) sit in the empty gap before V1(22)/Y(25).

**#139 (speed-audit step 1):** the worker runs **~20-26 min EVERY cycle even off-season** (no new session data) — re-processing + re-writing unchanged data. GitHub buffers stdout so log timestamps can't profile it; added a `_phase()` helper (time.perf_counter deltas) splitting setup+fetch / STM+hydration+classify / LegEvent-cache write / final_df+API_Cache write / Sheet1 write. Profiling run dispatched to find whether the ~20 min is PROCESSING or WRITING — decides incremental-compute vs incremental-write (the owner-confirmed optimization: "with history it makes the least sense to full rewrite … be thorough, don't lose accuracy"). See [[ideas/future_improvements]] (speed audit).

## [2026-06-15] pr | #135 MERGED — 10-year hardening (action bumps + 401-halt + archive monitor)

Knocked out the actionable items from the future-proofing assessment + an issue-hunt pass. All 11 remaining workflows (incl. production calendar_worker.yml + update_database.yml) bumped checkout@v3/setup-python@v4 -> @v4/@v5 (Node 24, ahead of the 2026-09-16 deadline). get_active_session_info distinguishes a 401/403 (key rotated — permanent) from a transient outage -> distinct CRITICAL `lis_api_auth_failure` instead of every-cycle OFFLINE noise. Harness now watches the SEPARATE archive workbook's cap (archive-cells; live 14.5%) so "archive filled" (~decade out) is a long-lead WARN. Issue hunt: fixed the only bare `except:` on the live path (2371) + a stale "L3b (TODO)" comment (the prune shipped in #126); confirmed no other bare excepts / stray secrets / mutable-default-args. Stress-test residual ledger slimmed: Y1/Y4/Y5 closed; standing-open list now only inherent (LIS redesign) + process (Gemini sunset 2026-07-17) + optional (archive auto-create needs Drive scope) items. Workbook 54.8%, archive 14.5%, harness 0 FAIL.

## [2026-06-15] pr | #133 + #134 MERGED — auto-rollover hook + API_Cache capacity

**#133 (worker auto-rollover):** the live Sheet1 must correspond to the active session (the 3rd of: LIS session code, API-call session, sheet's V1 marker). On a V1!=ACTIVE mismatch the worker archives the completed session's Sheet1 to the archive workbook. The archive is a PRECONDITION for the overwrite: read-fail / archive-fail / V1-advance-fail all RAISE so Sheet1 is never overwritten before the old session is safely archived (Gemini caught two subtle archive-corruption paths across 7 rounds; the naive retry would copy NEW data into Session_<old>). Live-verified: V1 initialised to 20261, no spurious rollover, cycle success. Fires first at the 2027 rollover.

**#134 (API_Cache capacity):** investigation showed API_Cache had only ~1,632 DATA rows in a 353,811-row ALLOCATED grid — a stale allocation (row analogue of the trim_api_cache_cols column padding), not unbounded data. `tools/cell_count_audit/trim_api_cache_rows.py` (dry-run + full-width emptiness scan + resize) reclaimed 2,062,866 cells -> **workbook 75.3% -> 54.8%**. Added a harness `wasted-grid` check (allocated >> populated) so this class is caught automatically going forward — it immediately flagged `C7_1b_FV_BillEvents` (40k/13k).

## [2026-06-14] pr | #131 MERGED — Session Archive (capacity finding resolved by separation)

The sustainability audit's capacity finding (workbook 79.7% of the 10M cap) met the owner's requirement to keep every session's data for long-term trend analysis. Resolution: SEPARATE, don't delete. `tools/session_archive/archive.py` + a separate owner-created "Mastermind Archive" workbook (its own 10M budget). Ran live: `verify` ✅ → `snapshot-session 20261` (2026 calendar → `Session_20261`, 37,542 rows) → `migrate-c7` (the C7_1a audit corpus → archive, 75,374 rows PRESERVED) → `migrate-c7 CONFIRM=delete` (removed from live). **Cap 79.7% → 75.3%.** 6 Gemini rounds (copy-before-delete, int sheetId, version-robust copied-sheet lookup → atomic batch rename, json guard). `API_Cache` row-retention PARKED (owner's bigger conversation). Next: the worker auto-rollover hook (fires 2027). Design: [[architecture/session_archive]]. Earlier reversal worth noting: a pure-delete tool for C7_1a (#130) was OPENED then CLOSED when the owner said preserve-don't-lose — became this archive-then-clean flow instead; nothing was ever deleted without first being archived + verified present.

## [2026-06-14] session | Sustainability campaign — the audit, made executable (PRs #125/#126/#127)

Owner asked to prove the system can sustain itself unattended ("find the hidden unsustainable issues; I don't know what to look for anymore") and to be conscious that the DB will grow. Reframed latent failure as a **time bomb** with one of five *enumerable* triggers (temporal / capacity / upstream-schema / state-wedge / determinism) and swept all five conclusively. Findings: temporal SAFE (session/window runtime-derived, verified); state-wedge SAFE (per-cycle self-clearing); determinism LATENT (0 live collisions but no dedup tiebreaker); upstream GAP (`LegislationEventID` consumed but uncovered by the canary); capacity FAIL (Witness append-only, prune never built). Meta-finding: [[architecture/stress_test_failure_modes]] had silently rotted (S5 false-safe — the very claim the text bug hid behind; Y2 false-open), so the audit was a claims-ledger, not verdicts.

- **#125 MERGED — `sustainability_audit.py` + weekly workflow.** The stress test made EXECUTABLE: 5 trigger classes, PASS/WARN/FAIL/SKIP, **convention-driven** (walks live tabs + code field-reads, so DB additions auto-surface). 8 Gemini rounds (the loop caught two silent-skip bugs in the audit tool itself). **First live run caught an unknown real finding: workbook at 79.7% of the 10M cell cap** (API_Cache 353,811 rows; stale C7_1a_RawCorpus 65,447) → [[ideas/future_improvements]], owner decision pending.
- **#126 MERGED — Witness retention prune (L3b).** The prune the worker expected but that was never built; shares the worker concurrency group for exclusive tab access. Closes the Witness unbounded-growth path. 4 Gemini rounds (off-by-one precision, empty/null/invalid-date edges).
- **#127 MERGED — worker expansion-safety.** `LegislationEventID` → Y2 canary; deterministic dedup tiebreaker (`_dedup_order`, output-neutral — 0 live collisions). Flips the last two harness WARNs → PASS.
- **Docs reconciled (this PR):** stress-test S3/S5/Y2/Y5 + standing-open corrected; `verification_durability` classify_action mechanism + #1r WARN fixed; harness added as durability **Layer 5**; assumptions_audit **#88** (audits-as-claims-rot). **Open for owner:** the API_Cache/79.7%-cap remediation (destructive — needs go-ahead).

## [2026-06-13] pr | Part C OPENED — last worker text dependency gone (verb gap-check → recorded-vote RefidClass)

The Part C gap-recovery reconciliation selected HISTORY rows by `MEETING_VERB_TOKENS` to find
"meetings" on gap dates. Migrated to a STRUCTURAL recorded-vote signal (`classify_refid` →
`VOTE_COMMITTEE`/`VOTE_FLOOR`), cache-independent (this block runs before LegEvent hydration, so
route_event is out — uses History_refid + the VOTE.CSV id set, both in scope). Owner chose RefidClass
(structural, 50-state-clean) over keeping the verb OR-fallback. Measured MORE precise: of 51
verb-flagged dates, 45 caught; the 6 misses are all benign (4 non-session Sunday false-positives +
2 witnessed floor days). Removed the now-dead `MEETING_VERB_TOKENS` constant — **the worker is now
fully text-free on the meeting path.** Offline triage/audit tools keep their own verb copies
(standalone). Awaiting Gemini.

## [2026-06-13] pr | #124 MERGED — PR-C8.4c: residual unconfirmed 31 -> 1; STRUCTURAL COVERAGE 100.00%

The 31 unconfirmed were clerical document rows: ~29 "Governor's substitute printed" + 1 "Veto
Received" (\d+[A-Z] document-version refids) + 1 HB26 referral. New REFID_DOCUMENT class
(\d+[A-Z], 0% VOTE.CSV join) -> administrative. SAFE only via classify_action's route-first guard:
the action-required DECISIONS (4 vetoes + 312 recommendations also carry digits+D refids!) route
'executive' and never reach the DOCUMENT tier; only BLANK-route clerical document rows land there.
Verified: 0 meeting->admin surprises (risk-set empty), 180 executive rows protected, unconfirmed
31 -> 1 (just HB26). Reverses the C8.4a digits+D caution, now that C8.4b surfaces the decisions via
their G-codes (the original risk is gone). [[failures/assumptions_audit#87]]. golden: classify_refid
35, classify_action 32. **VERIFIED LIVE (worker run, headSha contains the merge):** unconfirmed 31->1 (the 1 = HB26, VOTE_COMMITTEE, no LIS-published timed meeting); STRUCTURAL COVERAGE 99.92%->**100.00%**; Section 9 still 0; 'Vetoed by Governor' 7/7 still executive (0 buried — route-first guard held); refidclass_document=8739 stamped; completeness 180/180. Gemini r1 HIGH tightened the regex to ^\d+[A-Z]+$ (no trailing digits -> surface). main @ 0028b0a.

## [2026-06-13] milestone | POST-C8.4 HARDENING VERIFIED LIVE — all 3 solutions complete

#118/#119/#120/#121 + the #122 follow-up (count-population fix) all merged. Final worker run
confirmed end-to-end: worker read Y3=46, counted unconfirmed=31 over the WRITTEN rows, ratcheted
Y3 46→31 (rolling baseline self-calibrated), no spurious spike alert (delta 0 on an improvement),
unconfirmed_rows correctly NOT in the published metrics JSON (it's a local); meeting_unsourced=0
(route-based), 0 G-code drift alerts; sentinel all-green (Section 9=0, unconfirmed=31, executive=324),
completeness 180/180. main @ 661f2bc. assumptions_audit #85 (G-code drift) + #86 (count population).

## [2026-06-12] pr | PR-hardening1b-1 OPENED — count unconfirmed_rows over the WRITTEN rows (not pre-filter)

The hardening1b verification run exposed a count-population mismatch: the worker counted
unconfirmed_rows in _append_event (PRE the ephemeral-filter + (Date,Committee,Bill) dedup) = 46,
but the sentinel/X-Ray (written sheet) see 31. Fix: count over final_df (== sheet_data, post-filter)
excluding SYSTEM, via the canonical classify_action. Now 31 == the budget population the Y3 rolling
baseline tracks. Verified on the live written rows (31). [[failures/assumptions_audit#86]]. Caught by
the post-merge run (audit #74), not the unit sim (which measured the sheet, not the count site).

## [2026-06-12] milestone | POST-C8.4 HARDENING COMPLETE — all 3 deferred items merged

#118 (G-code drift alert), #119 (structural meeting_unsourced), #120 (centralize classify_action),
#121 (unconfirmed rolling baseline) all MERGED. Each grounded in an existing precedent
(validate_status_grouping / LegEventRoute / the Y2 breaker), each through the Gemini re-audit loop
— which caught: a dtype/NA leading-zero hazard, the floor-path convene-gap counter, a pd.NA crash,
and confirmed the route-based meeting_unsourced premise (0, not 150). main @ db1189c. Final
verification worker run dispatched. Designs: [[architecture/post_c8_hardening]].

## [2026-06-12] pr | PR-hardening1b OPENED — unconfirmed rolling baseline (Y3 spike alert)

The sentinel gated `unconfirmed` against an ABSOLUTE --unconfirmed-max (150) — audit #53's
calibration-bug shape. Now a rolling baseline, mirroring the Y2 meeting_unsourced breaker: the
worker counts `unconfirmed_rows` (canonical classify_action over finalized columns, ex-SYSTEM),
reads last-known-good from a NEW state cell Y3 (separate presence flag, audit #15),
delta=max(0,current-Y3), and on `present and delta>25` raises a DATA_ANOMALY/WARN spike alert;
ratchets Y3=current on success. DECISION (as-built): it ALERTS, not trips — `unconfirmed` rows are
SAFE-surfaced (visible+flagged), not bad data, so halting the whole sheet would be disproportionate
(contrast meeting_unsourced = a real meeting-without-time = correctly trips). Keeps the breaker
trip logic untouched (Hard Rule 10). Sentinel keeps --unconfirmed-max as the absolute backstop (it's
stateless → can't do rolling). Verified: worker unconfirmed_rows count == sentinel's (31, no drift);
delta truth table correct. Solution 1b (final) in [[architecture/post_c8_hardening]]. Awaiting Gemini.

## [2026-06-12] pr | PR-hardening1a OPENED — centralize classify_action (single source of truth)

Moved `classify_action` from pages/ray2.py into structural_router.py (it's pure string-ops, fits
the dependency-free module). ray2.py + calendar_xray.py now IMPORT it (diff-identical preserved);
the accuracy sentinel imports it instead of AST-extracting it; the worker can now import it too
(the foundation for hardening1b's unconfirmed rolling baseline). Removes the triplicate
definition + the AST-extraction drift risk (the "no duplicated copy that can drift" the
structural_router header warns against). Behavior-preserving: new test_classify_action.py (23
golden) + zero-diff gate = 0 diffs across 37,531 live rows; sentinel green; diff-identical held.
Solution 1a of (1a+1b) in [[architecture/post_c8_hardening]]. Awaiting Gemini.

## [2026-06-12] pr | PR-hardening2 OPENED — structural meeting_unsourced (drop MEETING_VERB_TOKENS from I4)

I4 (the write-time chokepoint) computed the circuit breaker's `meeting_unsourced` regression signal
from a VA-English verb list. Now STRUCTURAL: count when `LegEventRoute == "meeting"` AND
`origin in {journal_default, floor_miss}` — the router's own verdict that a row is a meeting the
worker couldn't time (the true Section-9-bug shape). Standard #3/#6 (no prose, 50-state-clean) and
a STRICTER detector. Behavior-preserving: verb-based and route-based both = 0 at steady state
(Section 9 = 0), so no breaker recalibration (Y2 already ratcheted to 0). MEETING_VERB_TOKENS stays
(still used by the Part C reconciliation candidate pre-filter ~L4159 — df_past has no route column,
a separate harder migration tracked in ideas — and the offline crossover_audit mirror). Solution 2
of 3 in [[architecture/post_c8_hardening]]. Awaiting Gemini.

## [2026-06-12] pr | PR-hardening3 OPENED — G-code drift alert (closes the executive prefix rule's fail-unsafe gap)

`validate_governor_eventcodes` (structural_router, mirrors `validate_status_grouping`) + a once-per-
cycle worker check over the hydrated LegEvent cache: any G-prefix EventCode LIS publishes that is
NOT in `KNOWN_GOVERNOR_EVENTCODES` raises a CRITICAL/DATA_ANOMALY drift alert. Closes the one
fail-UNSAFE gap in C8.4b's executive PREFIX rule (a new action-required family outside G72/G73/G79
would silently route admin→Ledger = a buried veto). Golden suite (9) + live verification: reference
G-codes == classified set, drift []. Zero behavior change (additive observability).
[[failures/assumptions_audit#85]]. Solution 3 of 3 in [[architecture/post_c8_hardening]]. Awaiting Gemini.

## [2026-06-12] pr | #117 MERGED — PR-C8.4b-1: floor-path executive carve-out (route/placement consistency)

Post-merge worker run for C8.4b verified the fix LIVE (331 executive rows on the calendar, 7
"Vetoed by Governor" moved Ledger→🏛️ Governor with 0 left in Ledger, Section 9=0, completeness
180/180, drift 0) but exposed a route/placement inconsistency: 7 rows had `route=="executive"` yet
sat in the Ledger (`origin=floor_miss`) — the worker's FLOOR path (a separate, earlier consumer of
the route) tagged floor-verb-matched "Governor's Veto Received"/"substitute printed" rows as
floor misses. Fix: an `elif _floor_route == "executive"` carve-out mirroring the main executive
branch (executive_default + 🏛️ Governor + legevent_executive_placed bucket), mutually exclusive with
the main resolver (gated `origin=="journal_default"`). 2 Gemini rounds: round-1 HIGH (back out the
convene-gap counters `_floor_miss`/`_floor_miss_dates` — these aren't floor misses) folded in;
round-2 re-emission verified-redundant (suggestion == committed code). [[failures/assumptions_audit#84]].
main @ b07e87e. Live effect on the next worker run (moves the 7 floor-routed veto rows → calendar).

## [2026-06-11] pr | #116 MERGED — PR-C8.4b: the veto-blindspot fix (new "executive" route/class on the calendar)

Governor vetoes/recommendations were routing `admin` → buried in the Ledger (the live Veto
Blindspot). `route_event` now returns a new `"executive"` route for action-required governor
EventCode families — VETO `G79xx` + RECOMMENDATION `G72xx`/`G73xx` (measured from real bill events;
`G7320` caught my initial G72-only guess) — checked BEFORE `ministerial_codes` (a veto is
ministerial-shaped, so the order is load-bearing) and after VoteTally (so a chamber vote ON a
recommendation stays a meeting). `classify_action` maps `executive` → a new `executive` class that
surfaces ON THE CALENDAR (worker `executive_default` origin + "🏛️ Governor" committee label, kept
OUT of the Ledger collapse mask), time-less and EXCLUDED from Section 9 (route is the guard — no
real meeting can reach it). MILESTONE governor codes (approved/chapter/deadline, ~4,700 rows) stay
admin; only action-required (~808) surface. Worker integration: `executive_default` in
`_VALID_ORIGINS` (auto I3/I4-exempt), route counter + metrics line. X-Ray: Classification Matrix
row + "🏛️ Executive Actions" drill-down. New `test_route_event.py` (20 golden, incl. the
veto-before-ministerial ordering); sentinel reports `executive=`; ray2/calendar_xray diff-identical.
[[failures/assumptions_audit#84]]. **MERGED** (2 Gemini rounds; round-1 HIGH caught a PRE-EXISTING
denominator-drift false-alarm of 3,034 — admin_default + derived_standing were omitted from the
X-Ray `_bucket_sum`; fixed + verified drift 3,034→0; round-2 re-emission verified-redundant).
main @ c39a914. **Live effect realizes on the next worker run** (moves matched veto/rec rows
Ledger→Governor calendar) — verify on a run whose headSha contains c39a914 (audit #74).

## [2026-06-11] pr | #115 MERGED — PR-C8.4a: SINGLETON_DOC ("Placed on Agenda") → admin; refid length law

Closes 44 of the 75 unconfirmed structurally + corrects 6 false-meetings (all `SINGLETON_DOC`
"Placed on Agenda/Calendar" / "Assigned sub" docket placements → administrative, consistent with
the existing `BATCH_NOTICE` treatment). `structural_router`: numeric-refid LENGTH LAW (measured —
len≤6 = 0% vote-join = document; len≥7 = 100% = vote-id) + new `VOTE_UNMATCHED` class (len≥7
not-in-VOTE.CSV → SURFACE, fail-safe guard). Worker counter pre-init fixed (KeyError guard).
unconfirmed 75→31; structural coverage 99.8%→99.92%; Section 9 still 0; sentinel all-green;
ray2/calendar_xray diff-identical. Discovery: a refid names the DOCUMENT, not the action — SB764's
veto-received carries a `digits+D` doc refid (same shape as admin "substitute printed"), so
`digits+D → admin` is FORBIDDEN (would bury a veto); those surface, vetoes handled in C8.4b
(route_event G-family split). [[failures/assumptions_audit#83]]. **Gemini round 1: clean. Round 2
(confirming re-audit): caught a real defensive gap** — HISTORY read via `pd.read_csv` with no
`dtype` could float-infer refids, dropping leading zeros and truncating a len≥7 vote-id into the
len≤6 document bucket (hidden meeting; ~0 VA risk, real 50-state hazard). Folded in: `dtype=str`
at the read (zero regression, 65,367 rows). The mandated confirming re-audit earned its keep.
Round 3 documented the leading-zero CALLER CONTRACT + golden tests; round 4 accepted
`keep_default_na=False` (strict string posture, verified zero-regression). Rounds 5: only the
redundant leading-zero re-emission (can't be fixed in-function — addressed at the read). **MERGED**
after the redundant stop-condition; main @ 70039c0. Next: C8.4b (route_event G-family → executive).

## [2026-06-10] pr | #114 MERGED — PR-C8.3 completeness tripwire + 99.8% structural-coverage metric

Layer 4 (no-hidden-meeting): completeness_tripwire.py joins LIS Schedule committee meetings vs
Sheet1 by committee CODE (subcommittees roll to parent) — 180/180 (100%); EXTERNAL SOURCE
CHANGE / CANNOT VERIFY guards; auth-gated; weekly workflow. Sentinel now reports STRUCTURAL
COVERAGE (1-unconfirmed/rows = 99.80%) as the honest headline (old 83.8% relabeled ROUTER
RESOLUTION, kept as the mass-degradation floor). 3 Gemini rounds folded. Next: C8.4 — close the
5 structural gaps in the unconfirmed 0.2%.

## [2026-06-10] milestone | PR-C8.2 MERGED — THE FLIP: text patterns deleted, classification 100% structural

The hand-built verb dictionaries (MEETING_ACTION_PATTERNS / ADMINISTRATIVE_PATTERNS /
ADMIN_OVERRIDE_PATTERNS) are DELETED from ray2.py + calendar_xray.py. classify_action now reads
NO prose — decides on LegEventRoute -> RefidClass -> ScheduleClass, else 'unconfirmed'
(surfaced, never hidden). The UUID litmus test passes. Live: Section 9 = 0, unclassified = 0,
unconfirmed = 75 (<=150), resolution 83.8%; 967 scheduled hearings surfaced to the calendar
(owner decision). Zero-diff gate caught + fixed the VOTE-refid referral bug (audit #81) and a
splice that deleted 9 fns (audit #82). Standard #3 satisfied on the lobbyist path. Next: C8.3
guards (completeness tripwire + unconfirmed error-budget).

## [2026-06-10] pr | #112 MERGED — PR-C8.1b ScheduleType companion (ScheduleClass), shadow

Closes the api_schedule tail of the 16%. classify_schedule_type (pure, golden-tested) keys on
LIS's integer ScheduleTypeID; in-memory (date_committee)->ScheduleTypeID index from raw
`schedules` (NO API_Cache migration); _append_event stamps ScheduleClass centrally. Both open
items resolved by measurement (agenda rows NOT dup: 0% overlap; 'Scheduled' rows NOT leakage:
99% in-session). Coverage 100% (1814/1814 api_schedule text rows non-OTHER), sentinel green.
4 Gemini rounds folded: KeyError crash (.get), str(None) guard, readability, float-proof, and
the normalize_room_key BOTH-sides join fix; final HIGH was a verified-stale re-emission
(code already implemented the suggestion + coverage held). Structural evidence layer COMPLETE
(RefidClass + ScheduleClass). Next: C8.2 — the FLIP (delete the text patterns).

## [2026-06-10] pr | #111 MERGED — PR-C8.1 structural evidence layer (RefidClass), shadow

All 3 gates green: worker success (VOTE.CSV=1606, refidclass stable), Gemini clean (3 rounds:
ragged-VOTE.CSV, float64 coercion, pandas-NA reprs — all folded), sentinel green. The
batch-notice law (text-free) solves the journal_default 16% at 98.3%, 0 counterexamples, K=2.
Shadow = zero behavior change. Next: C8.1b (ScheduleTypeID for 964 api_schedule-text rows).

## [2026-06-10] pr | #111 opened — PR-C8.1 structural evidence layer (RefidClass), shadow

Text-free `classify_refid` (by History_refid identity) stamped as shadow telemetry. Native
measurement: journal_default blank rows 98.3% BATCH_NOTICE, 0 counterexamples, K=2; the
"Placed on Agenda" 16% structurally solved. Found+fixed 2 telemetry bugs (ragged VOTE.CSV via
pandas; empty-refid NaN→UNKNOWN). Scope boundary: 964 api_schedule-text rows need ScheduleTypeID
→ C8.1b. Sentinel green (shadow = no behavior change). [[knowledge/history_refid_namespace]],
assumptions_audit #80.

## [2026-06-09] decision | PR-C8 execution spec written for handoff to a lighter model

Deep-reasoning session (owner: "lay out the plan and hard guidelines... so a less strenuous
model can carry out your hardwork"). Produced [[architecture/pr_c8_structural_classification]]:
12 hard rules (no prose on the decision path with a UUID litmus test, fail-safe direction,
review/worker gates, never tune-to-pass), the structural decision chain (route → vote-join →
batch-notice law → surface), 3-PR sequence with per-PR merge gates + golden tests + open
items (V-refid↔VOTE.CSV correspondence must be MEASURED, K chosen empirically), and a
stop-and-escalate protocol. Foundation discovery logged at [[knowledge/history_refid_namespace]].

## [2026-06-09] pr | #110 merged: LIS 2025/2026-only rule enforced in code (shared guard, every live caller)

`lis_authorization.py` = single source of truth ({20251,20261} + assert). Gated: calendar_worker
(halt + alert direct to Sheet1!X1 — Gemini caught the buffered-alert-loss as a RECURRENCE of
pattern #39), backend_worker (probe only authorized blobs; old probe HEAD-hit 2027 URLs each
November), ray2/calendar_xray (assert + clean st.error), reconcile_votes, schedule_replay.
2 Gemini rounds folded; final CRITICAL verified stale (code already writes X1 directly).
Branch worker run: success, processed=65366, sentinel all-green — gate is a 2026 no-op.

## [2026-06-09] decision | LIS API authorization rule captured + one past violation remediated

Owner spotted the LIS Developers Portal banner: the API toolset is authorized for **2025/2026
session data ONLY**; pre-2025 must come from `legacylis.virginia.gov` CSV. Audit result:
production is COMPLIANT (active session `20261` only). One internal tool —
`tools/edge_case_replay/schedule_replay.py` — had queried the new API for seven pre-2025
sessions (one-time, read-only, internal); now pinned to `{20261,20251}` with a runtime assert.
Rule recorded as [[knowledge/lis_api_authorization]] (linked from [[index]]); enforce per-state
when scaling. Also discovered (for later): the portal lists `Calendar` and
`CommitteeLegislationReferral` APIs we don't use yet — candidate structural sources for the
House "Placed on Agenda" routing.

## [2026-06-07] session | Post-Section-9 audit + independent verification + proactive future-proofing (PRs #100-104)

Owner: "thorough audit vs our brain's sustainability demands, then full verification, then future-proofing — who's to say that's all the bugs?" Three phases:
- **A — standards audit** ([[architecture/scalability_audit]], PR #101): 8-standard re-run; 4 gaps — G2/G4 fixed (PR #104), G1 deferred, G3 logged (YAGNI).
- **B — reconciliation tripwire** ([[tools/reconciliation]], PR #103, Standard #2): diff vs the independent official MinutesBook. **99.67% of committee reports confirmed**, 0.33% known residual → PASS. The continuous answer to unknown bugs. Vote-tally diffing found unreliable (minutes' VoteTally often empty) → verifies meeting/attribution existence ±2d.
- **C — multi-session edge replay** ([[testing/edge_case_registry]], PR #102): pure functions vs every session LIS serves. Found **B1** (real `parse_24h_time` "8am"/"8:30AM" → 23:59 sort bug, FIXED PR #104), the LIS rolling-window limit, and text-fallback coverage gaps (veto/rename) that `route_event` handles structurally. 2027 cold-start dry-run PASSED.

Also the **discipline correction** the owner caught: I'd been merging before bot review. PR #100 (the derived-standing fold-in) was then held for review and Gemini caught **4 rounds** of real separator edge cases in my own regex (hyphen → formal chamber names → comma → trailing punct); folded all in (final: alpha-words extraction). Lesson: wait for the audit before merging. PRs #100-104 all merged after a CLEAN bot review. See [[failures/assumptions_audit#77]].

## [2026-06-06] milestone | 🎯 Section 9 = 0 — EVERY meeting action now has a time (SJ209 closed via flagged standing-schedule derivation)

Owner pushed past "SJ209 is irreducible" a third time: *"you tell me the last few are unfixable then you find a way — is there another source? We know the committee; fill the time and flag it as assumed, but check every endpoint first."* Both instincts correct.

**The hunt (PR #96 / PR-C7.1w / audit #76):** enumerated all **246 LIS `/api/` endpoints**. Found the committee **MinutesBook** API — it *confirms* P&E's 3/10 meeting officially (published book #3853, "Closed"), though its content blobs 404. DOCKET.CSV has no time column; Calendar API is floor-only. The concrete time is derivable from the committee's OWN published data: P&E's modal standing pattern "15 minutes after the Senate adjourns" (6/6 regular-session meetings) + the published 3/10 "Senate adjourned 5:19 PM" = **5:34 PM**.

**The fix:** `_build_standing_schedule_maps()` + `_derive_standing_committee_time()` — a FLAGGED last-resort wired AFTER every real source (HB438 still keeps its real 8:00 AM; SJ209 gets 5:34 PM derived). Tagged `Origin="derived_standing"`; the X-Ray surfaces a "DERIVED / ASSUMED times" block so an assumed time is flagged, never hidden. Owner-approved narrow relaxation of Standard #3.

**Verified in production** (run 27075505625): `derived_standing=1`, Section-9 missing-times = **0**, SJ209 row = `5:34 PM / derived_standing`, no duplicates (the 3/13 6:00 PM row is the separate House P&E report). Trajectory 1,072 → 0 (100%). See [[state/current_status]], [[failures/assumptions_audit#76]].

## [2026-06-05] milestone | Section 9 = 1 MEASURED & DURABLE — the residual is one irreducible LIS data gap (SJ209)

Cold-start re-verification after the prior block exposed that **#72's "Section 9 = 1" was a projection, never measured** — the verifying burst ran a commit from before #87 merged (audit #74). The first REAL measurement was 6. Closed to a measured, durable **1** through three structural fixes (each verified on the produced rows, not just the count):

- **#90 (PR-C7.1t / audit #74):** unify the "real meeting time" definition on ONE `[07:00,23:00]` window shared by `structural_router._has_meeting_time` and `_plausible_meeting_time`. The `{00:00,04:00}` blocklist missed the **05:00** doc-batch artifact, so `H0840` Rule-22 continuances looked "timed" → dodged the ministerial law → routed meeting. Validated against a 117-bill / 300-EventCode sample (only clerical codes newly captured; every voted action vote-protected).
- **#91 (PR-C7.1u):** terminal-only schema back-fill — a NO-OP (the run proved every bill is `IsTerminal=FALSE`), corrected by ↓.
- **#92 (PR-C7.1v / audit #75):** the real blocker. The recovery was proven CORRECT on fresh API data (HB438→8 AM, HB246→12 PM, HB447→10 AM) but in production reads the cache, where **500 bills / 12,793 events still had `CommitteeName="?"`** (pre-column hydration) — which the recovery refuses — and they were skipped as "fresh" because persist bumps `FetchedAtUTC` without re-fetching. Fix: detect `"?"` directly and re-queue before the terminal/TTL skips. One migration cycle (`schema_backfill=500`) → cache 100% migrated (0 `"?"`) → the 3 rows timed → Section 9 = **1**, 0 mis-timed.

The remaining **SJ209** is honestly irreducible: P&E voted 13-Y on 3/10, but LIS published no 3/10 P&E meeting. Trajectory 1,072 → 1 (~99.9%). See [[state/current_status]], [[failures/assumptions_audit#74]], [[failures/assumptions_audit#75]].

## [2026-06-04] pr | #79/#80/#81/#82 — "look harder at the timeless 7" → relative-time sort fix, LegEvent structural-join recovery (+ a caught regression), forward-calendar producer

Owner pushed past "the 7 are upstream-limited" — "look at all the data across all the endpoints; find a standardized solution like the published LIS guide; don't guess." Four shipments:
- **#79 (PR-C7.1o):** the "15 min after adjournment" committee times were resolved to convene+1min (~2-7h too early). LIS publishes the basis (a "Senate/House adjourned" marker with the real clock time + the literal offset); fixed `build_time_graph`/`parse_24h_time` to anchor on the adjourned marker + parsed offset. ~168 committees re-sorted to their real slot. Honest scope: this corrects the SORT time; the displayed time stays LIS's published relative string (LIS-parity). [[failures/assumptions_audit#70]].
- **#81 (PR-C7.1p):** the standardized join the owner asked for — a timeless meeting row recovers its time from the matched LegEvent's OWN `CommitteeName` (→ committee schedule time; the committee it actually met in, e.g. HB438 rereferral → Senate Courts of Justice 8:00 AM) or, for a floor action (no committee, chamber actor), the chamber convene time (HB642/HB246 → 12:00 PM). Replaces the verb list (`ABSOLUTE_FLOOR_VERBS`) with a structural signal. [[failures/assumptions_audit#71]].
- **#82 (PR-C7.1p.1):** caught + fixed a regression #81 shipped — the cache never persisted `CommitteeName`, so committee reports were timed as floor actions (SJ209 → wrong 10:00 AM). Caught by verifying the ROW, not the count. Fixed with a persisted 3-state sentinel (name → committee / "" → floor / "?" → unknown-refuse). SJ209 back to honestly timeless; 0 mis-timed committee reports.
- **#80 (PR-FC1b):** forward-calendar producer (Step 1b) — future Schedule meetings tagged `scheduled_future`. Verified no-op on the adjourned session; activates 2027. Remaining: Step 2 X-Ray "Upcoming meetings" section, Step 3 reconciliation, Step 4 synthetic test.

Section 9: 7 → 6, converging to ~4 as `CommitteeName` back-fills (HB642 already recovered). SJ209 is the one genuinely irreducible row (P&E voted 3/10 but LIS published no 3/10 meeting). See [[state/current_status]].

## [2026-06-03] pr | PR-C7.1n (#77) — EventType-reference admin recovery (Section 9 10 → 7, the upstream floor)

Owner: "keep going until you reduce it as far as possible… with this api guide what else can you improve and standardize… look into why they are lacking times." Traced all 10 residue rows across EVERY source (HISTORY date, LegEvent date+timestamp, Schedule API, DOCKET, EventType reference). Two commonalities: **DATE DRIFT** (governor/conference/reconvene actions where HISTORY date ≠ authoritative LegEvent date by 1-9 days → exact-date route match blanks → text reads "recommendation" as meeting) and **GENUINE no-time** (relative-time committees, LIS-published `Time TBA`, midnight, not-in-DOCKET).

Fixed the date-drift class dictionary-free using LIS's OWN EventType reference (`GetLegislationEventTypeReferencesAsync` — 3,912 EventCode↔description entries, newly discovered; corrected the stale "404'd" note in [[knowledge/lis_api_reference]]). When the date-match is blank, recover the route by looking the outcome up in LIS's published descriptions and routing admin iff every mapped EventCode is admin (G-prefix/ministerial). "Governor's Recommendation" → {G7210,G7220} → admin. Asserts admin only on a blank route → never manufactures a false meeting. The standardization step the owner asked for: blank rows route via LIS vocabulary, not hand patterns. Sim: 10→7, 0 regressions. The remaining 7 GENUINELY lack a concrete time in any LIS source (e.g. Senate P&E meets "15 minutes after adjournment" — a relative time, no clock value) → the honest irreducible floor; reducing further = inventing data (Standard #3 forbids). Documented further standardization opportunities (EventCode drift monitor; LegEvent-date re-anchoring) in the API reference. See [[failures/assumptions_audit#69]].

## [2026-06-03] milestone | Section 9 = 10 — MEASURED on the FULL sheet (1,072 → 10, a 99.1% reduction) after #74 + #75

Worker run `26914210038` (success, **65,180 rows processed → 35,491 written** = full window restored) measured route-aware Section 9 = **10** on the complete live Sheet1, matching the #74 simulation exactly. Trajectory: 1,072 (cache-starvation peak) → 210 (post-hydration) → 25 (#71+#72) → **10** (#74 ministerial). The 10 residue (all named, none ballooning): 3 governor date-drift, 2 LIS-Time-TBA, 1 rereferred (#71 non-guess), 4 other (HB447 Continued-Rule-22/TBA, HB642 conferees, SJ209 not-in-DOCKET, +1). ~5-6 are upstream-limited (no time in any LIS source). Two corroborating sources agree (X-Ray route-aware count + worker SYSTEM_METRICS). See [[state/current_status]].

## [2026-06-03] post-mortem | A flaky Session-API window silently dropped crossover week (#75) — found while verifying #74

The first #74 verification run reported "Section 9 = 0" — but on a **277-row sheet that had silently lost the entire early session including crossover week (Feb 9-13)**. Taking 0 as a red flag rather than a win exposed a real silent-data-loss bug: `df_past` is filtered to `[test_start_date, test_end_date]` = min/max of the active session's SessionEvents (a sparse ~5-event summary), and the Session API intermittently returns a subset whose min jumps forward — **65,180 vs 310 processed rows on byte-identical HISTORY/config** — while `df_past.empty` stayed False so no alert fired. Fix (#75 / PR-C7.1m): clamp the window so the API can only EXTEND it, never shrink it below the pinned investigation floor (`min(test_start, INVESTIGATION_START)` / `max(test_end, INVESTIGATION_END)`); hardened `safe_fetch_csv` with retries + 60s timeout + Content-Length completeness (a truncated body can't silently parse as partial — the #62 class). Verified flaky/full/offline bounds all cover Feb 9-13. Lesson: partial/looks-valid data is more dangerous than outright failure; a collapsing row count must itself be an alert condition, not just `.empty`. See [[failures/assumptions_audit#68]].

## [2026-06-03] pr | PR-C7.1l (#74) — ministerial event-type routing (Section 9 25 → 10, dictionary-free)

(Detail consolidated below; measured outcome confirmed = 10 on the full sheet.) Owner pushed back on accepting 25 as a floor: "we can't have 25 wrong per session and gamble there's an influx next session." Probing showed the empty-status admin class is **412 timeless signings (404 on sine die)**, recurring/growing. Resolved with a structural LAW not a dictionary: *a deliberative action leaves a vote OR a timestamp; a ministerial record leaves neither.* `compute_ministerial_eventcodes()` derives from each session's own data the EventCodes that never (≥20 occ) carry a vote or a real time → Ledger. Per-TYPE aggregation is the safety guarantee (a midnight "Read third time" stays meeting; a genuine meeting can never enter the set). 33-code set, 0 deliberative types, 590 admin rows moved meeting→Ledger, 0 meetings swept. Self-calibrating to any state, zero maintenance (Standard #3+#5+#6+#8). See [[failures/assumptions_audit#67]].

## [2026-06-03] milestone | Section 9 = 25 — MEASURED (1,072 → 25, a 97.7% reduction) after #71 + #72 merged + a worker cycle

The crossover-week Section-9 bug count, route-aware against live Sheet1 (read with the production raw reader, NOT pandas), measured **25** after both fixes merged to main and worker run `26907047082` (completed/success) applied them. Trajectory this session: **1,072** (cache-starvation peak) → **210** (post-hydration, pre-merge) → **25** (measured). Per-class before→after: Governor **114→3** (#72 null-cell fix; 111 now route admin→Ledger), Rereferred **69→1** (#71 sibling-inheritance), empty-status admin **~20→15**, schedule-gap ~4→3, LIS-TBA 3→3.

The 25 residue, fully named: **14 signed-by** + **1 placed-on** (the proven no-dictionary floor — LIS encodes ceremonial/admin actions identically to floor reads: empty Status, no vote, midnight date; only EventCode/EventTypeID separates them); **3 governor date-drift** (Sheet1 row dated from HISTORY.CSV 1–2 days off the authoritative LegEvent date → exact-date route match misses → blank → text reads "recommendation" as meeting); **1 rereferred** (#71 correctly declined — no unambiguous sibling); **3 schedule-gap** (SJ209 P&E vote = a real DOCKET-join miss, + conferees/passed-by); **2 LIS-TBA** (upstream publishes no time). Irreducible floor ≈ 15–17; the other ~8 are fixable with care (date-tolerant Governor-actor match, DOCKET coverage) but carry diminishing returns / Standard-#3 false-match risk. Architecture validated: zero dictionary, zero per-state config, scales to 50 states. Full map in [[state/current_status]].

---

## [2026-06-03] pr | PR-C7.1k — LegEvent null-cell normalization (the 114-row Governor blank-route bug)

Post-hydration Section 9 = 210, of which **114 were Governor rows** carrying a BLANK `LegEventRoute` despite the router unambiguously routing `ActorType=Governor → admin`. A local repro insisted they should route admin; production blanked them — they disagreed for weeks. Root cause (raw-bytes probe): the API returns JSON-null `ChamberCode` for Governor events; the persist path's `str(e.get("ChamberCode",""))` wrote the literal string **`"None"`** (the `""` default only applies to a missing *key*, not a None *value*). Fresh-API events keep real `None` (falsy → filter collapses to `""` → route fine); cache-RELOADED events carry truthy `"None"` → chamber filter computes `ev_chamber="NONE" != "S"` → **excludes the event → no candidate → blank route**. Invisible until a bill is evicted+reloaded — i.e. the steady state after full hydration. This **corrects PR-C7.1j's prediction below** that the governor rows would "self-resolve against the full cache" — they did not; the null-cell sentinel was a real persisted-data bug, not hydration lag. **Why the repro lied:** it read the sheet with `pandas` (auto-NaN's `"None"` → `""`) while production reads `gspread.get_all_values` (raw `"None"`) — the test parser healed the corruption the prod parser chokes on (same family as #62/#63). Fix: one `_clean_legevent_cell()` helper collapsing `None`/`"none"`/`"null"`/`"nan"` → `""` on BOTH persist and load, applied to every nullable structural field. Heals existing rows on the next cycle (no re-persist wait). Governor rows now route admin → Ledger Updates (executive action, not a legislative meeting → correctly exits Section 9). Projected: 210 → ~96 (then ~27 after PR-C7.1j clears the rereferred). Merged together. See [[failures/assumptions_audit#66]].

---

## [2026-06-03] pr | PR-C7.1j — sibling-time inheritance (structural fix for the genuine Section-9 residue, NO dictionary)

After hydration, Section 9 = 190. Owner flagged the risk that fixing it would mean building a per-state admin-word dictionary (the anti-pattern the whole structural pivot eliminated). Probing the LIS LegislationEvent API (owner's "structural join first" call) proved the dictionary was never the answer: the largest genuine residue — "Rereferred to Finance" rows with no time — are NOT misclassified admin words. LIS treats "Reported from X **and rereferred to Y** (vote)" as ONE committee event; HISTORY.CSV splits it into a primary row (with refid) + a secondary "Rereferred to Y" row (EMPTY refid). The worker attributes the secondary row to the destination Y, which didn't meet, so it goes timeless → Ledger. Every such row has a same-(Bill,Date) sibling "Reported from X" that resolved the real committee time. See [[failures/assumptions_audit#65]].

Fix (`Origin=sibling_meeting`): a timeless, MEETING-routed `journal_default`/`floor_miss` row inherits the Time/SortTime/Committee of a same-`(Bill,Date)` resolved committee/floor sibling — only when that meeting time is UNAMBIGUOUS (single distinct resolved time that day; else no guess, Standard #3). Pure structural rule, zero vocabulary, scales to 50 states. New origin registered in `_VALID_ORIGINS` + I3 concrete set (carries a real time) + architecture doc; does NOT collapse to Ledger; new `sibling_inherited` counter (printed in its own log line — it's computed after the SYSTEM_METRICS row is serialized). 4-case unit test (inherits / ambiguous-skip / admin_default-skip / no-sibling-skip). Parse-clean; 15-point audit walked.

Expected: drops the genuine "rereferred/secondary split" chunk of Section 9 after a worker run. (NOTE: the governor/signed rows mentioned here as "self-resolving" did NOT self-resolve — see PR-C7.1k above for the real fix.)

## [2026-06-03] pr | PR-C7.1i — route matcher 0-overlap guard (the dominant remaining Section-9 false positive)

Post-hydration (97.8%) Section 9 was 266, not ~3. The residue was ~106 ADMIN rows ("Placed on X Agenda", "Rereferred to Finance") that the structural router routed to MEETING. Root cause (confirmed on SB41): `_route_for_row` matched a row to the best same-`(date,chamber)` cached event via `max(cands, key=token_overlap)` but returned its route EVEN AT ZERO OVERLAP — so "Rereferred to Finance" inherited the route of that day's coincident "Reported from Transportation (14-Y 0-N)" committee vote. The sibling TIME matcher `_find_legevent_time_in_cache` already had the guard (`best_score==0 -> None`); the ROUTE matcher was the only one missing it. Fix: `if _overlap(best)==0: return ""` -> the row falls back to text classification (admin). 4-case unit test. See [[failures/assumptions_audit#64]].

Expected: after merge + one worker run re-writes `LegEventRoute`, Section 9 drops 266 -> ~160 (the ~106 admin false-positives become admin). Remaining ~160 = ~143 blank-route genuine meeting-verbs without a cached-event match + 14 floor_miss (floor_recovered=0) — the next diagnosis.

---

## [2026-06-03] pr | hotfix — Backfill Burst died on `gh workflow view --json` (no such flag)

The owner stopped the 15-min cron and dispatched the ⏩ Backfill Burst; it **failed in 21s** at the "Snapshot cron state + pause if currently active" step with `unknown flag: --json`. Root cause: the PR #56 Codex-P2 fold-in snapshotted the cron's prior state with `gh workflow view calendar_worker.yml --json state` — but **`gh workflow view` has no `--json` flag** (that's a `gh run`/`gh pr` flag). The step exited 1 and the burst aborted before running a single cycle.

Why it slipped past pre-merge: I "verified" the snapshot idea with `gh workflow view ... --json ... 2>/dev/null || <fallback>` in my own shell — the `2>/dev/null || fallback` silently swallowed the `unknown flag` error, so the broken command looked like it worked. **Lesson: a `2>/dev/null || fallback` while spot-checking a CLI invocation can mask the exact error you're checking for; verify the command's exit code/output WITHOUT the swallow before baking it into a workflow.** And: GitHub CLI `--json` support is per-subcommand — `gh run`/`gh pr`/`gh workflow list` have it; `gh workflow view` does not.

Fix: use the REST API — `gh api "repos/${{ github.repository }}/actions/workflows/calendar_worker.yml" --jq '.state'` returns `active` / `disabled_manually` / `disabled_inactivity`. Verified live (returns `active`). Defaults to `"active"` on API hiccup so a transient blip can't strand the cron disabled. The Codex-P2 behavior (only re-enable if WE disabled it) is preserved. YAML validated.

After merge: re-dispatch the burst — it'll snapshot `active` → disable the cron → run N cycles (now hydrating correctly thanks to PR-C7.1h) → re-enable.

## [2026-06-03] pr | PR-FC1 — forward-calendar date-window foundation (Step 1a)

First increment of the forward calendar (the future-proofing feature). Ships ONLY the date-window foundation — the part Gemini found two real bugs in (#60 review) — fully unit-tested and a verified no-op on the current adjourned session, so it can't perturb the just-stabilized pipeline.

- `FORWARD_WINDOW = timedelta(days=14)` + pure `compute_effective_scrape_end(scrape_end, test_end_date, today)`. Pinned/historical runs (today's real state: `scrape_end=2026-05-01` < today) return `scrape_end` UNCHANGED (Gemini #2 reproducibility); a LIVE run extends the upper bound +14d, capped at `test_end_date` (no spurious next-session dates). All-datetime operands (Gemini #1 tz-safety — no `date`/`datetime` TypeError).
- Wired into the viewport slice (`scrape_end_str = effective_scrape_end.strftime(...)`) so future-dated rows will survive to Sheet1 once generated (Gemini #4 fetch/slice-bound parity). No-op now.
- `scheduled_future` registered in `_VALID_ORIGINS` (I2) + architecture-doc origin enum. **No producer yet** — registration only.

5-case date-logic unit test passes (pinned-no-extend / live-extend / cap-at-session-end / within-window-behind / no-TypeError). Parse-clean.

**Next: Step 1b** — the row-generation (Schedule-API meetings with `meeting_date > today` → `scheduled_future` rows). That's the riskier increment (touches the Schedule-API→rows path); deliberately split out so this foundation lands clean. Full plan in [[ideas/future_improvements#Forward-calendar block]].

---

## [2026-06-03] pr | PR-C7.1h — Tier A = "no cached events" (fixes the hydration starvation that kept the cache at 29%)

**The cache fix (PR-C7.1e) merged but the cache stayed pinned at exactly 1,063/3,645 bills (29.2%) across 8 hours of cron cycles.** Diagnosed live: PR-C7.1e was correct but DORMANT — the tab only grows when the in-memory events cache exceeds 25k rows, and that cache wasn't growing because the hydration queue never fetched the uncached bills. Root cause: `_build_legevent_refresh_queue` defined Tier A ("uncached, drains FIRST") as **no `bills_meta` row**, but a truncation victim keeps its metadata row (`FetchedAtUTC` set) with ZERO events — so all 2,582 victims were misclassified Tier B/C and mostly skipped as "fresh," while the 1,063 already-cached early-alphabet bills perpetually TTL-expired (6h TTL vs ~3h cron) and re-consumed the 500/cycle budget. Same ~500 HB bills re-fetched every cycle; SB/SR/HJ never reached. Full lesson in [[failures/assumptions_audit#63]] (proxy-vs-actual: "has metadata" ≠ "has events").

**Fix:** Tier A is now `cached is None OR not events_cache.get((bill, session))`. Pass the reloaded events cache into the queue builder (BEFORE the negative-`[]` seeding, so absent/empty == genuinely eventless). Truncation victims + the genuine 2027 cold-start + any future re-truncation now drain in Tier A FIRST and self-heal via the ordinary cron — the Backfill Burst (#56, now merged) is no longer *required*, just faster. Still 500/cycle capped (no fetch storm).

**Validates the owner's original mandate** ("uncached drains FIRST") which the old metadata-based test silently defeated. Unit test: truncation victim with 'fresh' metadata but no events → Tier A (not skipped); genuine cold-start (no metadata) → Tier A; all-cached-fresh → tier_a=0 (regression unchanged); omitted events_cache → safe default. Parse-clean; 15-point audit walked.

**Post-merge:** the next active-hours cron cycle will drain ~500 Tier-A bills, persist them (PR-C7.1e grows the tab), and coverage climbs ~500 bills/cycle → full in ~5-6 active cycles (or one burst). Re-verify with `tools/c7_section9_verify`.

---

## [2026-06-02] pr | PR-C7.1g — admin-route gate on the journal_default resolver (deferred follow-up, done)

Closes the item deferred from PR-C7.1c's scope. The journal_default LegEvent recovery path computes `_row_route` and, when `route=="meeting"`, recovers via the cache-direct helper; on any miss it fell through to `_resolve_via_legislation_event_api`. That fallback ran for `route=="admin"` rows too — so an administrative action (e.g. a "Governor's Recommendation" / "Bill text as passed" event) could be "recovered" with its ~4 AM document-batch timestamp, putting a structurally-WRONG time on an admin row (Standard #3 violation on the lobbyist surface).

Fix: `if _le_result is None and _row_route == "admin": skip` (increment new `legevent_admin_skipped` counter, surfaced in SYSTEM_METRICS) `elif _le_result is None:` run the resolver as before. Admin rows drop to NO_SCHEDULE_MATCH → Ledger Updates (timeless, correct); blank/meeting/unknown-future routes keep today's behavior unchanged.

**Re-hydration-safe + well-timed:** while the LegEvent cache is still re-filling (PR-C7.1e), routes are mostly `""` (blank), not `"admin"`, so this gate doesn't bite — blank rows still hit the resolver. It only activates once a bill's events are cached AND structurally admin, so shipping it BEFORE re-hydration means the freshly-filled cache produces correct output from the first hydrated cycle. 5-case unit test (admin→skip, meeting+hit→cache-direct, meeting+miss→resolver, blank→resolver, unknown-future→resolver).

**Review fold-in (#66):** the initial commit only skipped the resolver, leaving `origin=="journal_default"` — which (Gemini HIGH) flowed the admin row into the downstream journal_default source-miss block (a per-row TIMING_LAG WARN + `unsourced_journal++` → Bug_Logs flood once hundreds of admin rows hydrate) and (Codex P2) left the top-of-block `legislation_event_attempted++` standing, so X-Ray Section 0's `attempted − recovered` source-gap signal would overstate gaps. Fix: introduced a dedicated terminal origin **`admin_default`** — the admin-skip branch sets `origin="admin_default"`, `time_val="⏱️ [NO_SCHEDULE_MATCH]"`, backs out the attempted increment; the new origin is registered in `_VALID_ORIGINS` (I2) + the Ledger-collapse mask (still lands in 📋 Ledger Updates) and is deliberately excluded from the concrete-source set (I3) and unsourced-meeting set (I4). End-to-end flow test confirms admin→admin_default (no WARN, no unsourced_journal, attempted backed out, collapses) / meeting→honest attempted-recovered / blank→journal_default+WARN unchanged. X-Ray is origin-agnostic on these values. Architecture doc Origin enum + I2 table updated. Parse-clean; 15-point audit walked.

---

## [2026-06-02] pr | PR #61 + #62 + #63 merged — cache-capacity fix (the real blocker), cron/quiet-hours, legacy post-mortem

Three PRs merged after live verification disproved the earlier "Section 9 closed" claim (see the correction milestone below + [[failures/assumptions_audit#62]]).

- **PR #61** (PR-C7.1e) merged at `b837d17` — **the actual fix.** `LegEvent_Events` cache tab 25k→120k rows + `_ensure_row_capacity` (grow-before-write, workbook-cell-budget guarded, CRITICAL-alert on overflow) + one-step lift of the existing 25k tab + a shared `_workbook_cell_headroom` helper. Review fold-in: **Gemini HIGH** (budget guard was gating the CRITICAL alert on the buffered target, not the minimum need → false CRITICALs; now gates on `needed_rows`) + **Codex P2** (tab *creation*/grow at 120k bypassed the budget guard → could fail `add_worksheet` on a near-cap workbook and disable the cache; now both create and grow clamp to the budget). 3-branch capacity unit test + create-clamp test passing.
- **PR #62** (PR-C7.1f) merged at `83d0e96` — worker cadence 15min→3h + overnight quiet-hours gate (11pm-6am ET, DST-correct, scheduled-runs-only; manual dispatch + Backfill Burst bypass). Review fold-in: **Codex P2** (gap thresholds `GAP_CRITICAL=60` were 15-min-calibrated → every 3h run + overnight skip would false-`outage` + trigger wasteful Part-C reconciliation; recalibrated to cadence-derived `WARN=cadence*2=360`, `CRITICAL=quiet+cadence*2=780` so the ~12h healthy overnight gap doesn't reconcile — Point-14 calibration) + **Gemini medium** (quiet-window logic now handles non-midnight-spanning windows).
- **PR #63** merged at `cd7f009` — [[failures/legacy_calendar_versions]] post-mortem (why app.py/shadow_v2/v2_shadow_test/backend_worker/xray are relative failures: text-driven, hardcoded `20261`, 15 silent excepts, `st_autorefresh` per-tab). Gemini fold-in (terminology/grammar). Linked from [[index]].

**STATE: cache fix is MERGED but NOT YET VALIDATED in production.** The next worker run grows the tab and starts persisting all bills' events, but full re-hydration takes several cycles (or one ⏩ LegEvent Backfill Burst, PR #56). **Only after re-hydration + a fresh live cross-tab is the Section 9 drop real** — do NOT re-declare victory before measuring (the #62-assumptions_audit trap). Re-hydration involves ~4k LIS calls (burst) or several cron cycles; owner drives the trigger (API-exposure call).

---

## [2026-06-02] milestone | PR #57 + #58 merged — Section 9 pipeline closed (1,049 → ~3 expected steady state)

Both end-of-session PRs merged sequentially per the user's "safest sequence so we can finally see this Section 9 bug count drop" directive.

- **PR #57** (X-Ray UI) merged at `486faa2` — `pages/ray2.py` + `calendar_xray.py` `classify_action()` now consumes `LegEventRoute`. Streamlit auto-deploys against `main`; next page load on the X-Ray reflects the new bug count using existing route data the worker has been writing since PR-C7.1b-1.
- **PR #58** (worker time recovery + journal_default regression fix) merged at `07c4a17` — floor_miss → LegEvent recovery via the new `_find_legevent_time_in_cache` helper, gated `route == "meeting"`. Same helper applied to the journal_default path closes the silent regression that's been failing recovery for every fresh/terminal bill since PR-C7. Next cron cycle (~15 min after merge) is the first run with the recovery active.

**Merge order chosen for diagnostic clarity:** #57 first (UI shows the 90% classification collapse immediately based on data already in Sheet1); #58 second (next cron cycle then adds the time-recovery delta). If anything had regressed at either step, the visible signal would have isolated it cleanly. Both PRs were `MERGEABLE / CLEAN` pre-merge; #58 hit a `docs/log.md` conflict after #57 landed (both branches added entries at the top), resolved by keeping all four HEAD entries and inserting the origin/main entry chronologically.

**Verification cues over the next ~30 min:**
- Streamlit X-Ray: bug count drops 1,049 → ~106 immediately; drops again to ~3 after the next worker cron writes the recovered times to Sheet1.
- Worker SYSTEM_METRICS line: new counter `legevent_floor_recovered=N` climbs toward ~103; `legislation_event_recovered` increments more than it had pre-merge (the previously-silent journal_default rows).
- Section 9 proof block on the X-Ray: `admin ≈ 943, meeting ≈ 103, blank ≈ 3` against the flagged subset.

**The objective is done structurally.** The ~3 clerical no_event residue is below the noise floor and intentionally not addressed — overfitting to static data per the owner's design-for-dynamic mandate (Standard #6 / #8). The structural router architecture is training-free and survives next session's vocabulary changes by construction.

**PR #56** (`⏩ LegEvent Backfill Burst`) remains open as parked infrastructure for the 2027 cold-start; its fold-in (shared concurrency group + state-aware re-enable) is pushed and ready to merge whenever owner decides.

---

## [2026-06-02] pr | PR-C7.1c fold-in pushed — Codex P1 (cache-direct) + P2 / Gemini medium (Counter multiplicity) + journal_default extension

Three changes to `claude/pr-c7-1c-floor-miss-legevent-recovery` after the initial bot reviews on `5199810`:

1. **Codex P1 (cache-direct recovery):** new module-level helper `_find_legevent_time_in_cache(events, ...)` does the resolver's date+chamber filter / real-time filter / token-overlap score / EventDate parse / 12-hour render on an already-cached events list. Bypasses `_resolve_via_legislation_event_api()`'s `if not legislation_id` short-circuit. The route="meeting" verdict is itself proof the event cache is populated, so no LegislationID is needed. Closes the regression where fresh/terminal bills (loaded from `LegEvent_Events` tab, not rehydrated this cycle) silently failed recovery on both floor and journal_default paths.
2. **Codex P2 + Gemini medium (multiplicity):** `_floor_miss_dates` switched from `set` to `collections.Counter`. `set.discard()` removed combos entirely on recovery even when other unrecovered misses remained on the same date/chamber; Counter preserves per-combo unrecovered count via `[combo] -= 1; if <= 0: del`. Report set-difference wraps the Counter with `set(...)` (Counter's `-` is element-wise, not set-difference).
3. **Journal_default extension (proactive):** the same negative-cache regression Codex flagged on the floor path silently affected the pre-existing journal_default LegEvent recovery, and has since PR-C7 merged. Applied the cache-direct helper there too, gated identically on `route == "meeting"`. Behavior preservation: no path regresses; the regression case (cached events + negative-cached id + route="meeting") now recovers. Admin-route gating on the fallback is deferred to a separate PR. Net effect: potential additional Section 9 bug-count reduction beyond C7.1c's headline ~106 → ~3 (every fresh/terminal bill with cached meeting events that was silently failing recovery now succeeds).

Three new entries in [[failures/assumptions_audit]] (#59 pandas NaN→"nan" literal, #60 two linked caches must be seeded together, #61 set.discard loses multiplicity) capture the framework-level lessons.

---

## [2026-06-02] pr | PR-C7.1b-2 fold-in pushed — Gemini critical NaN + Gemini medium perf + Codex P2 full-column drift scope

Three changes to `claude/pr-c7-1b-2-xray-consumes-route` after the initial bot reviews on `30a3443`:

1. **Gemini critical × 2 + Codex P2 (NaN handling):** pandas reads blank Sheet1 cells as float `NaN`; `.astype(str)` turns those into the literal six-char string `"nan"`, which falls outside the documented `{"admin", "meeting", "blank"}` set and would falsely trip the CRITICAL drift banner in production for every TTL-backfill row (most rows today). Fix: `.fillna("")` before `.astype(str)` in BOTH the flagged-subset `route_series` and the new full-column drift scan. Verified the bug directly — old code produced `{'meeting': 1, 'admin': 1, 'judicial': 1, 'nan': 1, 'blank': 1}` on a mock sheet; new code produces `{'meeting': 1, 'admin': 1, 'judicial': 1, 'blank': 2}`.
2. **Gemini medium × 2 (perf):** `DataFrame.apply(axis=1)` constructs a Series per row, ~1-3s on ~58k Sheet1 rows for what is effectively a two-column zipped function call. Switched the route-aware classifier callsite from `apply(lambda r: ..., axis=1)` to a list comprehension over `zip(Outcome.fillna(""), LegEventRoute.fillna(""))` — runs in milliseconds, also handles NaN cleanly.
3. **Codex P2 (drift scope):** drift check was scoped to the flagged subset only — a new `LegEventRoute` value on timed rows / admin rows / cycles with `text_bug_count == 0` would go silent (exactly the scenario where a structural-router schema change is most likely). Added a full-column drift scan that runs whenever `LegEventRoute` exists, regardless of `text_bug_count`. Removed the redundant flagged-subset drift banner since full-column scan is strictly more thorough.

Lesson [[failures/assumptions_audit#59]] captures the NaN-ghost class for future review.

---

## [2026-06-02] pr | PR #56 review fold-in pushed — Codex P1 (concurrency lock) + P2 (preserve prior cron state)

Two changes to `claude/legevent-backfill-burst`:

1. **P1 (concurrency lock):** changed `concurrency.group` from `legevent-backfill-burst` → `calendar-worker` so the burst shares the cron worker's queue. GitHub queues the burst behind any in-flight cron at the queue layer (the `gh workflow disable` only stops *future* triggers, not in-progress runs); the disable step then runs once the burst actually starts to prevent future cron triggers from queueing during it. Belt + suspenders.
2. **P2 (preserve prior state):** `gh workflow view --json state -q .state` snapshots the cron's enabled/disabled state as a step output; the burst only disables if `state == active`; cleanup only re-enables if `prior_state == 'active'`. A new "Note prior-disabled cron was left in place" step makes the decision visible in the run log. An owner-disabled cron (maintenance window) is no longer silently un-paused.

PR #56 retains its OWNER-DECISION status (not needed for the current backfill — handoff measured the cold-start completed organically). Kept as infrastructure for 2027 session start / schema migrations.

---

## [2026-06-02] pr | PR-C7.1c opened — worker floor_miss → LegEvent time recovery (the time half)

Branch `claude/pr-c7-1c-floor-miss-legevent-recovery`. Closes the ~103 genuine-meeting residue PR-C7.1d measured: real floor votes (`conference report agreed`, `read third time`, `rules suspended`, etc.) whose convene anchor was missing and which the journal_default LegEvent block at `calendar_worker.py:~3508` SKIPS because that gate is `origin == "journal_default"` and origin has already become `floor_miss`.

**Safety gate (the key design constraint):** route MUST equal `"meeting"` (not just `!= "admin"`). The danger this defends against — already flagged in the 2026-05-31 sequencing correction in [[state/current_status]] — is `H5601`/`S5601` "Bill text as passed Senate (HB###ER)" rows text-matching `ABSOLUTE_FLOOR_VERBS` ("passed senate") → forced to Floor → convene miss → would land in this block. Their LegislationEvent has a 4 AM document-batch timestamp, not a meeting time. The structural router routes those to `"admin"` via LIS's own `ReferenceType` (`LegislationText`) — cache-lookup, no network. Requiring `route == "meeting"` (not just `!= "admin"`) also handles the blank-route case: a row whose LegEvent cache hasn't backfilled yet stays unrecovered (route unknown → safer to leave NO_CONVENE_ANCHOR than to recover with a possibly-wrong time). Next cycle, TTL backfill populates the cache, the route becomes `"meeting"`, and the row recovers. **Designed for new sessions as much as the static 2026 corpus:** the gate consumes LIS's own structural verdict — no per-state pattern list to maintain (Standard #6/#8).

**Hang safety:** cache-lookup-only — the PR-C7 pre-iteration hydration seeds the LegEvent cache (real events OR negative cache via the Codex P1 fix) for every candidate bill in `legevent_candidate_bills`, which includes floor_miss bills. The resolver short-circuits via the existing PR-C3.1 negative-cache check; the row loop never fetches. The PR-C3 hang root cause cannot recur.

**Telemetry:** new `legevent_floor_recovered` counter in `source_miss_counts`, surfaced in the SYSTEM_METRICS print line. The CONVENE GAP report (line ~3699) now prefixes with `⏪ LegEvent floor recovery rescued N row(s) (route==meeting); residue below.` when nonzero, so the gap report reflects "what's left after route-gated recovery." `_floor_miss` is decremented inline for each rescued row and `_floor_miss_dates.discard(...)` is called, so the existing report's count is the post-recovery residue (no double-counting).

**Local sanity:** parse-clean; 5-branch simulation of the gate's decision logic passed (route=meeting+success → recover, route=meeting+None → safe fallback, route=admin → skip, route=blank → skip, route=unknown-future-value → skip). 15-point audit walked.

**Sequence:** ships in parallel with **PR-C7.1b-2** (the X-Ray UI consumes `LegEventRoute`, branch `claude/pr-c7-1b-2-xray-consumes-route`). The two are CODE-independent (worker vs X-Ray) and together close Section 9: C7.1b-2 takes 1,049 → ~106 (misclassification collapse), C7.1c takes ~106 → ~3 (time recovery on the genuine residue). A row-level fallback for the final ~3 clerical no_event rows is a tiny follow-up.

---

## [2026-06-02] pr | PR-C7.1b-2 opened — X-Ray consumes LegEventRoute (the UI win)

Branch `claude/pr-c7-1b-2-xray-consumes-route`. Wires the X-Ray (`pages/ray2.py` + diff-identical `calendar_xray.py`) to consume the additive `LegEventRoute` column the worker has been writing since PR-C7.1b-1. The validated dictionary-free structural router (LIS's own `ReferenceType`/`VoteTally`/`Status`, full-scale-validated at 1,046/1,049 = 99.7% coverage) now drives X-Ray Section 9 classification, taking the visible bug count from ~1,049 → ~106 (the ~942 misclassification collapse). The ~103 genuine-meeting residue still need TIMES — that's PR-C7.1c (floor_miss → LegEvent fallthrough, the next push).

**Implementation (dynamic-data safe — designed for new sessions and schema drift, not just the static 2026 corpus):**
- `classify_action(outcome_text, legevent_route="")` — route wins when present; text patterns fall back. Default arg keeps any external caller working. Routes normalized via `.strip().lower()` with exact match on `"meeting"`/`"admin"` only — an unseen future route value (LIS adds a category, a code path emits something else) falls through to text instead of silent mis-route (Standard #1 / #8).
- Callsite switched from `.map(classify_action)` to `.apply(axis=1)` with `("LegEventRoute" in df.columns)` guard. Old Sheet1 read or schema regression → text-only fallback + visible `st.warning` (zero-trust, Point 9). Never silent.
- Parallel `_action_class_text` column preserved so Section 9 can self-prove the route's effect on the FLAGGED subset (the correct denominator the handoff flagged — current counters count all ~58k rows). New Section-9 "LegEventRoute effect on the flagged subset (the proof)" block: text-flagged-as-meeting + missing-time → router verdict distribution table. Shows admin-recovered (the win), meeting-residue (genuine, time-recovery pending), blank (TTL backfill / no LegEvent).
- Unseen-route surfacing: if the router emits a value other than the documented `meeting`/`admin`/`""`, the X-Ray throws a CRITICAL `st.error` banner with the unknown values + counts. Standard #1 runtime drift validation.
- Architecture doc updated (`docs/architecture/calendar_pipeline.md`) — the C7.1b-2 deferred block now reads "resolved."
- `XRAY_VERSION` bumped to `2026-06-02.1`.

**Tests:** 15-case unit suite of `classify_action` (route wins both directions, unseen route falls through, whitespace/casing/None safe, NaN-resilient under pandas `.apply`). All pass. Parse-clean from `pages/` with `sys.path = ..` (Point 8). `diff pages/ray2.py calendar_xray.py` = clean (Point 4).

**Verification post-merge:** Section 9's new proof block should show `admin ≈ 943, meeting ≈ 103, blank ≈ 3` against the current flagged subset (matches `C7_1b_FV_Summary` 943/103/3). Bug count above drops 1,049 → ~106. Then PR-C7.1c (floor_miss → LegEvent fallthrough, gated on `LegEventRoute != "admin"` to prevent recovering H5601/S5601 with 4 AM document-batch times) closes the genuine residue.

---

## [2026-06-02] post-mortem | C7.1b-1 was stranded on a merged branch — #40 recurrence; re-landed via cherry-pick

**What happened:** "check what things look like" — I pulled the worker logs (6 clean runs on `1cf2289`) and noticed the C7.1b-1 status-grouping `✅` line was absent. Initial (wrong) diagnosis: the worker's status-list fetch was failing. The REAL cause, found by grepping the deployed worker: **`1cf2289` (main) has ZERO C7.1b-1 markers — no `_route_for_row`, no 11-col header, no drift check.** PR #54 merged at `c563498`; I then pushed `bdbd902` (validation writeback) and `5ae3237` (the whole C7.1b-1 worker change) to the SAME branch AFTER it had merged. Both stranded on the dead `claude/pr-c7-1b-eventcode-namespace` branch; never reached main. The worker had been running pre-C7.1b-1 code the entire time.

**This is [[failures/assumptions_audit#40]] AGAIN** (pushed follow-up to an already-merged PR branch — the rule "closed/merged PRs have dead branches; branch from main for any follow-up"). Third occurrence. Root cause this time: I treated the long-lived `eventcode-namespace` branch as still-open and kept committing across the validation→greenlight→build arc, not noticing PR #54 merged mid-stream at `c563498`.

**Recovery:** fresh branch from `origin/main`, `git cherry-pick bdbd902 5ae3237` (clean — linear children of `c563498`, which IS in main). Verified all C7.1b-1 markers restored + parse-clean. Then folded in the observability layer (below).

**Process tightening (the rule already exists; I failed to apply it):** before pushing ANY commit, check whether the target branch's PR is still open (`gh pr view <n> --json state`). Merged PR = dead branch = new branch from main. And: when a result looks wrong in prod (a missing log line), FIRST verify the code is deployed (`git merge-base --is-ancestor <commit> origin/main`) before diagnosing runtime causes — I burned a cycle assuming a fetch failure when the code simply wasn't there.

---

## [2026-06-01] pr | PR-C7.1b-1 — worker persists structural fields + writes additive LegEventRoute (no UI change)

Owner greenlit the wiring as a two-PR split, safest path: build the backend first, prove the data populates in the sheet before touching the X-Ray/UI, secure the 90% classification win (Section 9 1,049 → ~106), handle time-recovery separately later.

**C7.1b-1 is additive + observability-only — does NOT change `Origin`, `Committee`, row placement, or `meeting_unsourced`.** So the circuit breaker, the calendar, and the lobbyist UI are all unchanged this PR. What it does:
- Promotes `structural_router.py` to the repo root (single source of truth; worker + tools import it; tool-dir dupe deleted) — kills the worker-vs-X-Ray drift class before it can start.
- Worker persists `ReferenceType`/`VoteTally`/`ActorType`/`Status` per event to `LegEvent_Events`, appended after EventCode (→11 cols, #56 append-don't-insert, tab auto-widened). Optional on read; backfills over ~7 TTL cycles.
- Worker writes an additive Sheet1 `LegEventRoute` column (`meeting`/`admin`/`""`) via `_route_for_row()` (cache-lookup-only, mirrors the validated full_validate matcher), defaulted via `setdefault` in `_append_event` so it's not a `_REQUIRED_KEY` (no I1 violation).
- Startup drift check: fetches `GetLegislationStatusListAsync`, CRITICAL-alerts on unclassified statuses (Standard #1), INFO-degrades on fetch failure.

15-point audit walked; key checks: Point 8 (no `pages/` file imports worker/router — verified), Point 14 (breaker inputs unchanged — `meeting_unsourced` untouched), Point 56 (all new cols appended), Point 2 (`_route_for_row` module-level before call site). `_route_for_row` unit-tested on a mock multi-event cache (bill-text→admin, floor-vote→meeting, no-event→""). Validate after merge: `LegEvent_Events` 4 new cols + Sheet1 `LegEventRoute` matching the 943/103 split. Then PR-C7.1b-2 (X-Ray consumes `LegEventRoute`).

---

## [2026-06-01] milestone | Structural router PASSES full-scale validation — 90% of the bug count is misclassification, provably

Ran `full_validate.py` against ALL 1,049 flagged X-Ray Section-9 rows (run on `c563498`, sheet+log-captured — numbers from `C7_1b_FV_Summary`, not transcribed). The dictionary-free structural router (routes on LIS's own `VoteTally`/`ReferenceType`/`Status`/Governor, [[failures/assumptions_audit#58]]):

- **943 (89.9%) → admin** — false positives collapsed (document 843: H5601/S5601 "Bill text as passed" family + conference-report docs; executive 100: G7210 "Governor's Recommendation").
- **103 (9.8%) → meeting** — genuine residue (committee/subcommittee *offered* 85 + committee reports *with vote tallies* 18). The "committee offered → meeting" routing independently agrees with the owner's PR#22 ground-truth ruling ([[failures/pr22_post_mortem]]).
- **3 no_event** (clerical, no LegEvent match), **0 FAILED**, **status-grouping drift NONE at full scale** (covers LIS's complete 52-status published list).

Near-exact match to the C7.1d prediction (~942/~100). The router is validated at full scale. **Metric impact:** wiring it in drops Section 9 from 1,049 → ~106. **Caveat preserved:** "routes to meeting" ≠ "has a time" — the ~103 residue still need time recovery (the separate floor_miss→LegEvent fix); the router resolves the *classification* 90%, time-recovery closes the rest.

The weeks-long "what are these bugs / how do we handle them without a brittle dictionary" question is now answered with full-scale data and a defensive, source-consuming, zero-maintenance router. **Next: PR-C7.1b proper (wire into X-Ray + worker) — gated on owner greenlight (the promised design-review checkpoint); plan in [[state/current_status]].**

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

**Codex P2 fold-in (2026-05-31):** the initial commit inserted `EventCode` at index 4 (mid-schema). Codex caught that this breaks the write-then-clear-trailing partial-write recoverability: a transient mid-persist failure leaves new-7-col header + stale-old-6-col rows, and the name-indexed reader then reads stale rows as `EventCode=<old ChamberCode>`, `ChamberCode=<old Description>` — silent corruption. Fix: APPEND `EventCode` last; stale old rows keep legacy fields at fixed indices and the trailing EventCode degrades to `""`. Lesson in [[failures/assumptions_audit#56]] (append-don't-insert for partial-write-tolerant schemas — same family as protobuf field-numbering). Gemini had no comments.

---

## [2026-05-31] decision | NO DICTIONARY — route on LIS's own structural fields (ReferenceType/VoteTally)

Owner cut to the core: *"why does LIS know what the code means and not ours? why do we need a dictionary in the first place... LIS knows what it means and it's correct on their site why can't ours be if we have access to that source of truth."*

Answer: LIS doesn't decode a dictionary — `Description` IS the plain-English meaning, served directly, and it's in every API response we pull. We never needed a dictionary for DISPLAY. The only internal need was calendar-vs-admin routing, and **LIS classifies that itself** via `ReferenceType`/`VoteTally`/`IsPassed` — documented at [[knowledge/lis_api_reference]]:142 since PR-C3, unused.

Live probe (`tools/c7_1b_eventcode_namespace/probe_referencetype.py`, 37 bills / **1,068** events, file-captured). **⚠️ first numbers I posted were wrong** (read off garbled shell output: "Communication 456", "Vote 392/392", "G7210=Communication" — none real); corrected after re-running to a file. Authoritative `ReferenceType` distribution: `Vote` (473), `<blank>` (291), `LegislationText` (115), `LegislationFile` (86), `Committee` (61), `Subcommittee` (41).

Honest finding: `ReferenceType` is NOT a clean binary. `Vote` includes non-votes (readings, referrals; only 262/473 have a `VoteTally`); `<blank>` mixes floor meetings with admin. **Clean:** `VoteTally`→meeting (266, narrow); `LegislationText`+`LegislationFile`→docs/admin (201); `Committee`/`Subcommittee`→referral/admin. **Hard middle** (`<blank>` + Vote-without-tally) needs full-dataset measurement. False positives confirmed: H5601/S5601=`LegislationText`, G7210=`<blank>`. DISPLAY solved (`Description`); ROUTING dictionary-free but not yet fully closed. **Double lesson in [[failures/assumptions_audit#57]]:** consume the source's labels (not text/dictionary) AND capture tool output to a file when the terminal is corrupting it — I committed wrong numbers to the brain by transcribing noise.

Decisions: EventCode→category dictionary ABANDONED. PR #54 (its premise) to be closed/superseded. Brain lesson captured as [[failures/assumptions_audit#57]]: we reached for text/dictionary 4× while the source's own classification sat documented in our brain — the meta-lesson on reading the brain (and the upstream's full API) thoroughly. `lis_api_reference` updated with a prominent classification-fields callout so it's never buried again.

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
