---
tags: [testing, prediction, pa, replication, calibration]
updated: 2026-11-17
status: active
open_loop: Batch 3 (member votes — first_vote, content_votes, persuadability, member_signals, member_subject, coverage, rooms, money_and_vulnerability, the exact second-chamber party split) waits on the owner pasting the five Open States PA session-CSV links (environment now allows data.openstates.org).
---

# Virginia's tests, re-run on Pennsylvania (2026-11-17)

Owner ask: *"run VA-style stats on PA ... stats-wise we've covered at least all of the things we tested in VA."*
Plan and data audit: [[testing/pa_predictive_plan]]. Code: `tools/calibration/pa/` (`pa_corpus.py` one parse of every
export · `pa_frame.py` features knowable at filing · `pa_batch1.py` export-only tests · `pa_batch2.py` roster tests).
Results: `results_batch1.json`, `results_batch2.json`.

## How it was run — collect once, test in batches by source

The efficient route (owner's question, answered): **each SOURCE is collected once** and normalised into one bill table;
**tests run in batches by the source they need**, so a missing source blocks only its own batch.

| batch | source | cost | tests |
|---|---|---|---|
| 1 | PA Bill History exports, 9 sessions 2009–2026 (palegis.us bulk ZIPs, no use restriction) | 8 downloads, 15 MB | 16 tests below |
| 2 | PA committee roster feed (current session only) | 0 new (cached 2026-11-01) | seat, chair, 3 ledger stats |
| 3 | Open States session CSVs (CC0; per-legislator votes) | 5 downloads | every member-vote test — **waiting on the owner's 5 links** |

Instead of ~2,200 roll-call page requests per session to PA's site (owner rejected as excessive), batch 3 is five
public-domain downloads that put zero load on PA.

Protocol mirrors Virginia: features use only what is known at filing; fit on earlier sessions, score on later ones;
2023–24 is the last completed session; 2025–26 is live (ends 30 Nov 2026) and is used only where the outcome is the
first committee (essentially settled).

**PA caveat that runs through three tests:** a PA title names the statute and section amended (*"…Tax Reform Code of
1971, in personal income tax, further providing for classes of income"* — 38 carriers filed that one title), not the
policy. So PA's exact-title match means *same part of the law*, coarser than Virginia's catchline. Room memory is also
reported on same-carrier refiles, the closest PA gets to "same idea" without bill text.

## Results, test by test

| Virginia test | Virginia finding | Pennsylvania, same method | verdict |
|---|---|---|---|
| [[testing/bill_fate]] | locked 2026: AUC 0.80 vs 0.68 baseline | 2023–24: **0.78 vs 0.69**; 2025–26: **0.76 vs 0.67**; log loss 0.499 vs 0.540, 0.513 vs 0.551 | **replicates** |
| [[testing/panel_audit]] | the panel adds +0.020 AUC over "patron's party" | majority only 0.667 → + room record 0.707 → + carrier record 0.714 (2025–26) | **replicates** (modest, room > carrier) |
| [[testing/calibration_ledger]] (37 stats) | 7 usable | usable: patron in majority 10.0/5.3, patron's prior record in this committee 8.2/6.4, patron's prior rate 6.3/5.3, majority co-sponsor share 6.1/4.0, patron party 4.8/6.2. Weak: bipartisan 4.8/4.4, committee 2.5/1.2, same-day batch, co-sponsor count. Noise: volume, chamber, title form, memo, second year, money committee, recency, tenure… | **mostly replicates**; differences below |
| [[testing/bill_mix_confound]] | +29 gained / −21 lost majority, within member | 2023 House flip, same members: Democrats **+33 pts**, Republicans **−34 pts** (64 / 66 members, p ≈ 1e-11); same member + same title refiled: D 4% → 15%, R 34% → 12%; Senate placebo (no flip) −0.1 / −4.0 | **replicates, stronger** |
| [[testing/carrier_effect]] | room keeps the majority member's vehicle 83% (n=208); carrier SD 14–16 pts, r 0.46–0.51 | majority carrier kept **232 of 262 (88.5%)** vs 50% expected; carrier lift SD **10.6 pts**, split-half r 0.53, session-to-session r **0.46** | **replicates** |
| [[testing/profiles]] (member) | bipartisan filing r 0.78/0.48; specialisation 0.60/0.31 | bipartisan filing r **0.72**; specialisation r **0.60** | **replicates** |
| [[testing/profiles]] (room) | partisan gap +4 to +65; rewrite 35–71%; era r: gap 0.54, rewrite 0.25 (retracted) | gap **+1 to +70**; rewrite 12–63%; era r (2009–16 vs 2017–24): rate 0.79, **gap 0.55**, **rewrite 0.73** | gap replicates; **rewrite holds in PA** |
| [[testing/room_memory]] | died before → dies again 80% vs 26% (OR 10.8); same room OR 15.2 vs other 5.5, z 2.49; new carrier OR 3.6 | **91% vs 37% (OR 18.2)**; same-carrier refile **93% vs 35% (OR 24.2)**; other room OR 5.0; z **7.0**; new carrier OR 6.9; coverage 25% of bills (VA 8–12%) | **replicates, stronger** |
| [[testing/room_memory]] (asymmetry) | after a no, moving rooms barely helps (85 → 81%) | 91% → 84% | **replicates** |
| [[testing/venue_effect]] | 272 of 1,443 companion pairs split 50/50 by chamber | **667 of 2,261** split; the House bill lived in 312 (47%, p 0.10 vs 50/50) | **replicates** |
| [[testing/venue_shopping]] | room worth +11 to +18 pts | same part of the law, higher-rate room **+4.2 pts** (185 vs 144 groups, p 0.027) | **replicates, smaller** |
| [[testing/enacting_clause]] | AMEND vs ADD: majority +18, minority +14 | "An Act amending…" vs "…providing for / establishing": majority **+4.3**, minority **+3.4** (p < 0.001) | direction replicates, **much smaller** |
| [[testing/blind_sweep]] | minority AMEND +31 vs ESTABLISH −13 | 21 nominated (swept 2009–20), 16 replicate (2021–26). Strongest: local "courtesy" bills naming a county/borough +12 minority / +8 majority; majority bills with no co-sponsors +17; joint resolutions (constitutional amendments) −11 | **replicates as a method**; PA's cells differ |
| [[testing/committee_seat]] | the 8-person SUBcommittee seat +14; full committee −2 | PA has no subcommittee gate: full committee seat **+20 (majority) / +6 (minority)**; within the same sponsor **+13.5** (115 better, 62 worse) | **replicates** (the room you sit in) |
| [[testing/influence_and_sources]] (chair co-sponsor) | chair co-patron: 92% vs 70% | majority chair co-signs: **63% vs 22%**; within sponsor **+40 pts** (123 better, 23 worse) | **replicates, stronger** |
| committee_seat (chair as sponsor) | chair adds ~3 pts over a plain seat | majority chair's own bills **80% vs 41%** for other majority members of the room | **differs** — PA chairs gatekeep |
| [[testing/kill_points]] (bill level) | subcommittee is the gate | **73% die in the first committee**; 9% reported but never pass; 7.5% die in the second chamber's committee; 7.3% become law | bill-level half only (no committee roll calls in the export) |
| [[testing/clock]] | silence priced by week; cliff before crossover | no deadline cliff: unheard at 1 month → 18% ever reported, 3 → 10%, 6 → 5%, 12 → 2% | **differs** (PA: steady decay, no crossover) |
| [[testing/continuance]] | a continuance is a soft kill (25 of 1,346 move again) | PA's parking move, re-committal, is **not** a kill: **93% move again**, median 5 days | **differs** |
| [[testing/bill_states]] | tabled bills almost never leave (13 of 1,303) | PA "laid on the table" is procedure: **92% removed**; Rule 71 / Rule 9 automatic tabling 26% | **differs** — tabled ≠ dead in PA |
| [[testing/contested_vs_routine]] | majority edge +9 consensus / +35 contested (first roll call) | measured on PA's origin passage vote (only tallies available): routine 76%; second chamber run by the patron's party: +11.5 routine / +9.7 contested | **not comparable** (different roll call) |
| [[testing/second_chamber]] | surplus cross-party votes buy nothing where your party runs chamber 2 (p 0.97) | proxy surplus (yes votes beyond own seats) **matters** both ways: 27% → 53% (p 5e-17); 22% → 39% (p 4e-4) | **differs** — re-test with exact party splits in batch 3 |
| [[testing/calibration_scope]] | committee stat strong in the House, weak in the Senate | House 1.8%, Senate 4.4% | **differs** (weak in both) |

### Where PA and VA disagree, and why it matters for the product
- **Party standing is everything in PA**, more than in VA: the ledger's best stat, the 2023 flip (±33 pts), and room
  partisan gaps up to 70 pts. A PA screen that shows nothing else still tells most of the story.
- **PA chairs gatekeep**: majority chair's own bills 80% vs 41%; chair co-signing +40 within sponsor. Virginia's chair
  effect was small because the subcommittee decides there.
- **Tabling and re-committal are procedure in PA**, not kills — already reflected in the PA subway's "parked" state
  ([[architecture/multi_state_config]]), now measured: 92% of tabled and 93% of re-committed bills move again.
- **Patron history helps in PA** (prior rate +6.3/+5.3, prior record in this committee +8.2/+6.4), where Virginia found
  it harmful or conditional. PA's two-year sessions and long careers (nine sessions here) give the record more to say.

## Not yet run (batch 3, member votes) — and not runnable

| test | needs | status |
|---|---|---|
| [[testing/first_vote]], [[testing/content_votes]], [[testing/persuadability]], [[testing/member_signals]], [[testing/member_subject]], [[testing/coverage]] | per-legislator votes | Open States CSVs — owner's 5 links |
| [[testing/rooms]], kill_points (committee half), profiles dies-on-a-record / unanimity, [[testing/venue_effect]] content-controlled kill rate | committee roll calls | check the Open States files; PA's export has none |
| [[testing/second_chamber]] exact party split, ledger vote stats (absence, loyalty, floor win rate, agrees with committee) | per-legislator votes | batch 3 |
| [[testing/money_and_vulnerability]] | votes + PA campaign finance + election margins | batch 3 + a new source, scoped after |
| [[testing/subject_labels]] | a subject vocabulary | **blocked**: PA's export has none (check Open States) |
| [[testing/redocketing]] | — | retired in VA on reasoning; not re-run |
