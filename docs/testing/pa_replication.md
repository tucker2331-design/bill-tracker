---
tags: [testing, prediction, pa, replication, calibration]
updated: 2026-11-18
status: active
open_loop: Batch 3 DONE 2026-11-18. Not runnable on PA data — money_and_vulnerability (needs PA campaign finance + election results) and subject_labels (Open States PA bills carry no subjects); vote-model boosts listed under 'Member votes — PA vs Virginia'.
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

## Does each design element mean anything? (held-out element value, 2026-11-17)
`pa_element_value.py` → `results_element_value.json`. Each element added to a baseline that already knows party
standing × chamber × session year; fit on earlier sessions, scored on one never seen.

| element | AUC gain 2023–24 / 2025–26 | bills it speaks to | verdict |
|---|---|---|---|
| tried before (same law, same/other room) | +0.061 / +0.097 | 37% / 41% | strongest |
| the room's record for this standing | +0.031 / +0.045 | ~95% | keep |
| sponsor sits on the committee (2025–26, odd→even) | +0.044 | 35% | keep |
| sponsor is the majority chair | +0.037 | 7% | keep |
| carrier's own record | +0.030 / +0.030 (log loss barely moves) | 82–94% | small |
| majority chair co-signs | +0.062 | 13% | **timing unverified** (co-sponsors undated) |
| co-sponsor count / other-party co-sponsor | +0.017–0.057 | all | timing unverified |
| majority co-sponsor share | −0.025 / −0.004 | all | drop |
| title form (amend vs new act) | +0.002 / +0.005, log loss worse | all | drop |

Baselines: AUC 0.692 (2023–24), 0.665 (2025–26). Everything together: +0.101 / +0.139.

## Drafting-room tests (pre-introduction levers, 2026-11-18)
Ten tests of what a drafter can still change — the law amended (→ room), Appropriations, filing time, new members,
twins, district make-up, memo, bandwidth. Results and verdicts: [[ideas/drafting_war_room]] §0.2; code
`pa_drafting.py` → `results_drafting.json`; district data [[knowledge/district_profiles]].

## Bill fate, round 2 — PA vs Virginia (2026-11-18)
`pa_fate_v2.py` → `results_fate_v2.json`. Every input knowable on the filing day (counts to date, a twin only if filed
first); co-sponsor inputs are a separate arm because PA's co-sponsor list is final and undated.

| | 2023–24 (fit 2009–21) | 2025–26 (fit 2009–23) | Virginia, locked 2026 |
|---|---|---|---|
| baseline: standing × chamber × year | 0.692 | 0.665 | 0.68 |
| logistic, clean inputs | **0.775** (log loss 0.495) | **0.807** (0.474) | **0.80** |
| boosted trees, clean inputs | 0.772 | 0.805 | — |
| + co-sponsor arm (timing unverified) | 0.810 | 0.828 | — |

- **PA now matches Virginia** on the same protocol. Trees add nothing over logistic — the signal is a few strong
  facts, not interactions.
- What carries it (AUC lost when removed): **tried before** −0.015 / −0.036, standing −0.009 / −0.006, filing time
  −0.008 / −0.008; room, carrier and usual-room records ≈ 0 once tried-before is in.
- Calibration: 2023–24 runs low in the middle (predicted 11% → actual 18%) — the 2023 House flip put a new majority
  in charge that the training years had never seen; 2025–26 is close (deciles within ±0.06 except one).
- **To raise it:** (1) date the co-sponsors — the +0.02–0.04 arm is worth having only if signatures predate the
  committee; the PA co-sponsorship memo (circulated before filing) is the clean source; (2) recalibrate on the most
  recent session after a majority change; (3) historical committee seats from batch 3's committee roll calls (seat
  and chair added +0.044 / +0.037 on 2025–26); (4) member votes for the later gates (batch 3).

## Batch 3 — member votes (2026-11-18)
Source: Open States PA session CSVs 2017–2026 (CC0; links from the owner; `MANIFEST.json`, zips not committed).
22,885 roll calls, 2.1 M ballots; 0.19% of ballots unresolved (counted, kept out of party statistics). PA's committee
roll calls are in the files (11,440), recorded in the motion text ("Committee vote (Health): …"). The 2017–18 file
ships without organizations.csv — chamber ids are stable across sessions, so they are taken from the other files.
Code: `pa_batch3.py` (first-vote model + roll rate, defection, pivotality, member stats, rooms) and `pa_batch3b.py`
(Virginia's exact definitions: second chamber, persuadability, denominator, member × law, rooms, kill points).

| Virginia test | Virginia finding | Pennsylvania | verdict |
|---|---|---|---|
| [[testing/first_vote]] | locked 2026: **85.9%** vs always-yes 73.9% (+12); ceiling 97.3% | 2025–26: **89.2%** vs always-yes 87.5% (+1.7); 2023–24: 87.6% vs 87.6% (+0); ceiling 98.4% | **differs** — PA's recorded first votes are 88% yes; the gain lives on contested ballots |
| first_vote, contested ballots | the hardest third 66–68% | contested (≥10% no): 70.6% (2025–26, cutoff from 2023) to 79.1% (cutoff 0.5) vs 60.6% always-yes; 2023–24: 64.2% vs 61.3% | **replicates in 2025–26**; broken by the 2023 House flip |
| first_vote, confident calls | 95%+ on 67% of ballots | 2025–26: **97.7% on the most confident 67%** (99.3% on 30%); 2023–24: 92.5% | **replicates** (2025–26) |
| [[testing/content_votes]] (who in the other party crosses) | AUC 0.744 | 2025–26: **0.822** (basics 0.712); 2023–24: 0.616 (basics 0.751) | **replicates in 2025–26**; the flip again |
| [[testing/persuadability]] | z year→year r 0.68; top third defects ~4× | r **0.84, 0.78, 0.50 (flip), 0.84**; top third next session 4.0% vs 1.3%, 7.5% vs 0.4% | **replicates, stronger** — except across the majority flip |
| [[testing/member_signals]] denominator | 21% of committee roll calls have a caucus split | committees **16%**; floor 39% | **replicates** |
| member_signals attendance | split-half 0.98, across eras 0.36 | absence is near zero in PA (median 0.06% of ballots); session r 0.15 / 0.05 / 0.59 / 0.03 | **differs** — no attendance signal in PA |
| [[testing/member_subject]] | residual member × subject r 0.487 across eras | member × law residual r **0.135** (1,844 cells); same-law r ≈ general record r every session | **does not replicate** — a member's law-specific record adds nothing beyond their general record |
| ledger: majority roll rate | majority rolled 1.4–5.6%, minority 20–43% | House majority 0.3–1.6%, minority 15–48%; Senate majority 0–1%, minority 14–28% | **replicates, sharper** |
| ledger: loyalty, floor win rate | — | loyalty median 97.5%, session r 0.71/0.79/0.08/0.93; floor win median 94%, r ≥0.95 except −0.69 across the flip | stable traits **within** a majority, reset by a flip |
| [[testing/second_chamber]] exact split | other party's chamber-1 support: buys nothing if your party runs chamber 2 (86–89% flat); 24% → 80% if not | not running: **14% → 50%**; running: 20% → 45%; slope weaker when running (interaction −1.11, p 0.004) | **asymmetry replicates**; in PA support helps either way |
| [[testing/rooms]] | the room is a subcommittee of 8; favourable recs 62% unanimous | full committee: median **24** members recorded; 69% unanimous; 157 of 11,440 committee roll calls failed | **differs** — no subcommittee gate |
| [[testing/kill_points]] committee half | subcommittee votes kill | **0 of 2,773** bills that died in their first committee (2023–24) ever got a committee roll call | **differs** — PA kills by never voting |
| pivotality | — | 437 of 19,360 roll calls decided by one vote; 415 members ever on the winning side of one | descriptive |
| [[testing/coverage]] | member × subject flags rarely apply | moot: the member × law signal does not hold (above) | — |
| [[testing/venue_effect]] content-controlled kill rate | — | not applicable: PA committees do not vote bills down | — |

### Member votes — PA vs Virginia, and how to raise PA's
- **Overall accuracy is the wrong yardstick in PA.** Committees vote only on bills they report, so "everyone votes
  yes" is 87.5%. The useful targets are contested roll calls and other-party crossovers, where the 2025–26 model
  clearly works (AUC 0.82 on who crosses; 97.7% on the most confident two thirds).
- **The 2023 House flip breaks member records** (defection r 0.07, floor-win r −0.69, model at baseline) — and Open
  States began recording far more House committee votes in 2023 (1,428 → 3,836 committee roll calls). Records keyed
  to party letter break; records keyed to majority/minority role were added; training on post-flip sessions fixed it
  for 2025–26.
- **Party position tested:** [[testing/pa_party_position]].
- **To raise it:** (1) a party-position reader for bill content (PA ceiling 98.4% if party positions were known —
  the same gap Virginia hit); full bill text links are in PA's XML since Feb 2026, or an LLM read of each bill
  (Virginia costed ~$4–8 per 11.6k summaries); (2) show vote predictions only on bills likely to be contested
  (16% of committee roll calls split a caucus); (3) recalibrate after every change of majority; (4) in PA the
  bigger lever is the bill-fate model — PA kills by never voting, so whether the chair brings a bill up is the
  decision that matters.

## Not runnable on PA data
| test | why |
|---|---|
| [[testing/money_and_vulnerability]] | needs PA campaign finance and election results — not ingested (Virginia's result was null) |
| [[testing/subject_labels]] | Open States PA bills carry no subjects (0 of 26,138); the statute named in the title is the structural stand-in used above |
| [[testing/redocketing]] | retired in Virginia on reasoning |

