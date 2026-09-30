---
tags: [testing, calibration, prediction, members, war-room]
updated: 2026-09-28
status: active
open_loop: Modelling exhausted (six rounds, see Verdict). Remaining: score the locked 2026 test once; carried-over bills lack a summary-wording score (HB 1515) — fix before member cards ship; the bill-level consensus-kill warning and co-patron pattern are ready to design into the War Room (owner decision).
---

# Predicting every legislator's FIRST vote on a bill

Owner, 2026-09-25: *"focus on the first committee vote score or sub or what ever the first vote a bill hits bc
after that we know its a lot easier… becareful not to build something thats accurate when its least useful…
make sure your testing is dynamic… lets try to break 95."*

`tools/calibration/first_vote.py` (+ `gbm.py`, `text_party.py`, `text_features.py`, `stats.py`)

## Protocol — the way model builders evaluate
- **Train** 2020, 2021, 2022, 2024 · **tune** 2025 only · **2026 locked**, scored once after every choice is frozen.
- Every feature is computed by **replaying the legislature day by day**: a first vote sees only what happened on
  earlier days (earlier years, or earlier dates in the same session).
- Always reported by slice — **other-party legislators** and **whole-party position** — so a gain on the easy
  ballots cannot hide where it matters.

## The right baseline
On first votes "always guess yes" is **73.9%**, not the 84–85% of all votes. And the ceiling: if each party's
position were known perfectly, individual accuracy would be **97.3%** (other-party 96.5%). **Breaking 95% means
calling party positions ~97% right.**

## Progress on 2025 (tuning year)

| model | all | other-party | party position |
|---|---|---|---|
| basics (party, standing, venue) | 76.8% | 64.5% | 72.3% |
| + committee, patron, legislator-in-room, content, co-patrons, bill history, room memory, duplicates | 85.6% | 79.8% | 83.0% |
| + summary-word party classifier | 85.8% | 80.4% | 83.6% |
| **tuned: one-stage GBM, depth 6** | **86.2%** | **80.7%** | **84.0%** |
| two-stage (party → member) | 85.3% | 80.2% | 83.2% — not better |
| *always guess the common answer* | *73.9%* | *57.4%* | |

## Subject labels — no gain (tested 2026-09-25)
Coarse subjects cover 85% of bills (vs 20–32% for similar-bill content), added as party-on-subject and
legislator-on-subject records: 85.9% vs 86.2%, within noise. Bill-level signals have plateaued near 86%.

## Breaking 95 the way a product can — confident calls (2025, tuning year)

| call only the most confident… | all legislators | other-party |
|---|---|---|
| 30% | **99.2%** | 96.8% |
| 50% | 97.8% | 93.9% |
| 60% | 96.4% | 91.1% |
| 80% | 91.8% | 84.9% |
| 100% | 85.9% | 79.9% |

**95%+ accuracy on 67% of all first-vote ballots and 45% of other-party ballots**, with the rest flagged "too
close to call". The confidence cutoff is fixed on 2025 and carried unchanged into the 2026 test — choosing it on
2026 would be tuning on the answer.

## The plateau — tested from every direction (2026-09-25/26)

Owner: *"look into more to close this gap… consider things like district location composition… see if you
can 2x it."* Every attempt, same protocol (tune 2025, 2026 locked):

| added | all | other-party | party position | hardest third |
|---|---|---|---|---|
| (tuned model) | **86.2%** | 80.7% | 84.0% | — |
| subject labels (85% coverage) | 85.9% | 79.9% | 83.2% | — |
| actual subcommittee, this-session room, legislator×patron, companion's vote | 85.8% | 80.1% | 83.3% | 66.8% |
| full-text structural flags (2025 layer) | 84.9% | 78.7% | 82.8% | 66.8% |
| full-text similar bills (47% coverage) | 85.1% | 79.2% | 82.6% | 67.5% |
| ideal points, per chamber (district proxy) | 85.6% | 79.4% | 83.5% | 66.3% |
| + 2019 training year | 85.6% | 79.6% | 83.4% | 67.2% |
| training on fewer years | 84.6–85.1% | — | — | — |

**Every idea lands within ±0.6 of 86%.** The remaining error is almost entirely *which way a party goes on this
bill in this room* (ceiling with perfect party positions 97.3%). That is decided in caucus and is not in any public
record we hold. **The hardest third sits at 66–68% — inside the owner's 60–70% target.**

**Ideal points, face validity:** per chamber (a combined fit let the House swamp the Senate and made every
"moderate" a senator near zero). Dimension 1 separates the parties 100%; the most moderate include the 2024
swing-seat senators (Perry, Pekarsky, VanValkenburg) and, historically, Petersen/Lewis (D) and Vogel/Hanger (R).

**2017–18 excluded from training:** their committee roll calls carry counts but no names, so each bill's first
NAMED vote is its floor vote — 166,000 floor ballots that would have been over half the training set.

**What could still move party positions (each needs the owner):** an LLM reading each bill for its political
charge (~10k API calls, cost); Census district composition (a free key only the owner can register); the org's
own positions and contact notes (caucus-level information the public record lacks).

## Round 3 (2026-09-28) — aimed at the hardest third, owner target >80%

| added | all | hardest third |
|---|---|---|
| Census district composition (2022 maps, joined via 2023 ELECT filings) | 85.5% | 67.0% |
| "by request" bills (read from the printed bill) | — | hypothesis false: own party backed them 95% |
| attribute scan for consensus kills (companion ahead, duplicates, fiscal, co-patrons…) | — | nothing separates; best "no co-patrons" 18% vs 8% |
| **the room's seated members as a group** (each side's record on patron / subject / similar bills / map / districts) | **86.1%** | **67.8%** — best so far, rank 0.914 |
| what this room did EARLIER THE SAME DAY (LIS vote-id order) | 86.4% | 68.7% — live-hearing only, not pre-meeting |

**Verdict:** ~20 ingredients tested; the hardest third moves inside 66–69%. It is the bills whose party position is
set in caucus, which no public record carries. What could still move it needs the owner: an LLM reading each bill
for its political charge (API spend), and the org's own positions/contact notes.

**District join, done right.** The people file mixes old- and new-map district numbers for SITTING members
(Sickles listed at old 43; he holds 17) — joining on it put about half the legislature in the wrong place (the
sanity check had Mark Sickles among the least college-educated districts). Districts now come from the Nov 2023
ELECT candidate filings (2022 maps) via `finance.join_members`: Sickles 17, Kilgore 45, Shin 8, Tran 18.
Filings whose office reads "0.00" are excluded — Barry Knight's said 81 (old map) and joined him to a
Black-majority Chesapeake district.

## Traps caught, all before any number was reported
1. **Direction bug — 1,262 roll calls (2.7%) read backwards.** "Failed to report (defeated)" was treated as a kill
   motion. Fixing it moved every number up.
2. **Carryover vote copies** in the next session's file (1,816) — the same vote in training and test.
3. **The integer-mask scoring bug**, twice.
4. **Stacking trap** — word-model scores for training years came from cross-fitted models that had seen later
   years; 2025's did not. The tree over-trusted them (85.6 → 82.7). Fixed with an expanding window everywhere.
5. **Where the misses are:** unanimous tablings of ordinary bills (the patron's own party votes to table — not
   explained by duplicates, tested) and party-line splits on majority bills. Those are the targets for text.

## How sure, in words a volunteer can use (2026-09-28)

Accuracy by how far the model leans, 2025 first votes (17,553 ballots, held out of training; 2025 was also the
tuning year, so read these as slightly optimistic until the locked 2026 check runs):

| label | how far it leans | share of calls | right |
|---|---|---|---|
| Likely | 80%+ either way | 70% | 94 of 100 |
| Leans | 60–80% | 20% | about 70 of 100 |
| Toss-up | 40–60% | 10% | 57 of 100 |

The War Room shows only the label; the "How sure is this?" sheet shows this table. No per-member percentages.

## Why a member gets their guess — `why_member.py` (2026-09-28)

Owner: the two raw counts on the member card were odd to an amateur and "not enough evidence." Each reason now
carries a direction and a size, measured by swapping that reason's inputs for 300 real same-party ballots
(method and the failed first attempt are in the script's docstring). HB 1515, first vote assumed Jan 2027:

- **The bill's own situation dominates for everyone.** No co-patrons / no Senate companion: −6 to −10 points per
  member. Sitting in a subcommittee, carried over: −10 to −16 (depends on the assumed vote date). The first is the
  one factor an org can change.
- Personal factors are small: Kilgore's overall record −3; the four Democrats: committee record −1 to −5, similar
  bills +4, overall record up to +6, patron record +2. District: 0 for all five.
- **Data gap found:** HB 1515 has no summary-wording score (`txt_has = 0`), and the missing score moves the
  Democrats' guesses by +10 to +17 — an artifact, not a reason. It is kept off the card and disclosed in the
  "How sure" sheet. Fix: score carried-over bills' summaries (open loop below).

## Round 4 (2026-09-28) — owner: "getting that 67 number up"

Protocol: choices fixed on 2024 (model trained 2019–2022), applied unchanged to 2025. 2026 stays locked.

| tried | 2025 all | 2025 hardest third | verdict |
|---|---|---|---|
| baseline | 86.1% | 67.8% | — |
| **missing inputs** — do ballots lacking a wording score / content / districts go wrong more? | — | with 67.5% vs without 68.1% (wording) | **no**: missing data is not where the misses are, so filling gaps won't lift it |
| party consistency — blend each member's guess toward party-mates' on the same vote (a=0.2) | 86.2% | 68.0% | noise (+0.1 / +0.2) |
| per-slice thresholds (other-party × subcommittee) | 85.4% | 70.5% | **rejected — a metric trap.** Moving thresholds changes WHICH ballots count as "hardest"; the headline rose while overall accuracy fell 0.7 points |

**Where the hard third lives:** 72% are other-party ballots (vs 48% overall) and 69% are subcommittee votes (vs 42%).

**The one untested lever — an LLM reading each bill for its political charge.** Cost, checked 2026-09-28
(Anthropic price list; Batch API is half price): ~11,600 summaries × ~400 input + ~60 output tokens ≈ **$4 on
Haiku 4.5, $8 on Sonnet 5.5, roughly $40–60 on Opus 5.5** (its thinking is always on). **Leakage risk that must be
designed out:** a model trained on public data may remember how a 2019–2025 bill actually fared, which would make
backtests look better than reality. Mitigate by sending only the summary text (no bill number, year, patron) and
asking about content, not outcome; the only fully clean test is the 2027 session. Needs the owner's go-ahead (spend
+ an API key).

## Round 5 (2026-09-28) — owner: "exhaust the options ... complicated statistics a statistician would"

**Where the misses are (2025, error analysis):** by motion — "strike from the docket" is called right only 39% of
the time (522 ballots) and unanimous kills 54%; they are 22% of the hardest-third misses. Patron-requested
withdrawals are rare (~30 bills/session in LIS history), so they are not the main story.

| tried | 2025 all | hardest third | verdict |
|---|---|---|---|
| baseline GBM | 86.09% | 67.77% | — |
| **co-sponsorship relationships** (member↔patron co-sponsorship in earlier years, reciprocity, ties to this bill's coalition, co-sponsors seated in the room) | 85.95% | 66.91% | no gain |
| same, **size-weighted ties** (a shared 3-sponsor bill counts far more than a 60-sponsor one, Fowler-style) | 86.11% | 67.87% | noise |
| **member × bill latent factors** stacked on the GBM (supervised ideal points: member position = personal + district/party projection; bill location from summary words, subject, committee, patron) | 84.65% | 64.66% | **hurts** — overfits to training bills. Learning curve on 2024 with stronger regularisation: never above the GBM at any step (84.36% → flat or down) |

**Reading:** the GBM already searches combinations of up to six inputs; the question the owner raised — identity ×
content combinations ("this member × this kind of bill") — was tested directly by the factor model and does not
generalise from first votes alone (too few ballots per member). Next: the same axes learned from ALL contested
roll calls (floor + committee, earlier years) as a single feature — `text_ideal.py`.

| tried | 2025 all | hardest third (fixed set) | verdict |
|---|---|---|---|
| **text-linked ideal points from ALL contested roll calls** (15,763 roll calls, 526k ballots, earlier years only; bill placed by its content) as a GBM feature | 85.94% | 67.30% | no gain (2024: 84.33 vs 84.36) |
| **deeper combinations** — trees combining 8–10 inputs instead of 6, slower learning, more rounds (4 settings) | 85.76–86.00% | 66.76–67.49% | no gain; every deeper setting ties or loses on 2024 AND 2025 |

**Round-5 verdict (broad tests, each rules out a family):** relationship data, member×content interactions (from
first votes or from every vote), and deeper feature combinations all leave the hardest third at 67–68%. The
information that decides those votes — how each party will line up on this bill in this room — is not in the
public voting record, however it is combined. What can still move it is NEW information, not new maths:
the team's own contact log and positions (now being built), and (owner's call, later) reading bill content.

## Consensus kills — what they are and whether we can see them coming (2026-09-29)

Owner: "22% of the hard misses are unanimous kills or strike from the dockets ... dig more into that, how does that
happen in what scenario and could we predict it?" Scripts: `consensus_kills.py` (diagnosis), `consensus_kill_model.py`
(prediction). Data: first votes 2019–2025 (2023 excluded as elsewhere).

**What they are.** 918 of 9,344 first votes (9.8%) end with every member against the bill. 73% are in subcommittees;
none are full-committee first votes (full-committee kills are voice votes, no roll call). How they die: tabled 32%,
stricken from the docket 30% (almost always the patron pulling it), continued 17%, passed by indefinitely 9%;
"sent to study with a letter" only 3%; "incorporated into another bill" ~0%.

**Theory rejected:** "killed because a twin carried the idea" is FALSE — bills whose near-twin had already advanced
were killed LESS (5.7% vs 8.9%, 2025).

**The pattern — co-patrons, not party.** In a subcommittee:

| bill | consensus-kill rate |
|---|---|
| no co-patrons, minority patron | 21.2% (1,169 bills) |
| no co-patrons, majority patron | 19.6% (1,211) |
| at least one co-patron | 6.9% (2,691) |
| 5+ co-patrons | 4.3% (1,074) |
| co-patrons from both parties | 5.3% (495) |

81% of strikes and 69–82% of every kill type are bills with no co-patrons. **Correlation, not proof:** bills without
co-patrons may be weaker or placeholder bills; the same-patron check (a patron's bills with vs without co-patrons) is
the next test before telling anyone "add co-patrons."

**Predictable in advance, from inputs we already have.** Bill-level model, trained ≤2024, tested on 2025 (1,624 bills,
142 kills): AUC 0.85; the 10% of bills it flags most are consensus kills 36% of the time (4× the 8.7% base rate) and
catch 41% of all of them. New traces (twin advanced, patron's past kill rate, filing order, day of session) add nothing.

**Why the member model still misses them — and why that is correct.** Even the riskiest bills die only about 1 in 3,
so each member's single most likely vote is still yes. The miss is genuine uncertainty (the patron's private decision),
not a modelling gap. The value is a **bill-level warning** ("bills like this die quietly about 1 in 3 times"), not a
different member guess.

## Round 6 (2026-09-29) — the remaining broad families

**Co-patrons, same-patron test** (`copatron_same_patron.py`). 167 patrons had subcommittee bills both with and without
co-patrons. Their bills WITHOUT co-patrons died unanimously 20.4% (2,374 bills) vs 6.9% WITH (2,673); within-patron
difference +13.6 points; 112 patrons worse off without, 31 better, 24 tied — sign test p ≈ 6×10⁻¹². "Weaker
patrons" is ruled out as the explanation. Still not proof that ADDING a co-patron causes survival (patrons may
recruit co-patrons for their strongest bills), but strong enough to show lobbyists as an observed pattern.

| tried (settings fixed on 2024) | 2024 all / hard | 2025 all / hard (fixed set) | verdict |
|---|---|---|---|
| baseline GBM | 84.36 / 64.86 | 86.09 / 67.77 | — |
| regime-matched training (years with the same House majority counted twice) | 84.36 / 64.85 | 85.57 / 66.19 | worse |
| separate House and Senate models | 84.20 / 64.56 | 85.21 / 65.24 | worse |
| logistic regression alone | 82.72 / 61.31 | 84.28 / 63.75 | worse |
| GBM + logistic blend | 84.04 / 63.90 | 85.66 / 66.50 | worse |
| two-level: bill consensus-kill risk (expanding window) fed to the member model | +0.11 / +0.34 | −0.02 / −0.07 | noise |
| cleaner labels: train without strike-from-docket votes (scored on ALL votes) | +0.24 / +0.72 | −0.39 / −1.18 | does not replicate |

**Verdict after rounds 1–6:** every reasonable modelling and feature family has now been tested against the same
protocol. None moves the hardest third outside 66–68% on 2025. The only untried lever inside our own data is MORE
data: 2023 is missing from training (Open States has no 2023 committee record), but LIS's own 2023 files are cached
(`va/231/Vote.csv`: 8,071 roll calls with member-level ballots, committee votes included). Adding it needs a
refid→bill/date/motion join through History.csv and a member-ID→name join; by the earlier "+2019" test, one extra
year is worth about a point on the hardest third, not a step change.

**2023 added from LIS legacy files** (`add_2023.py`): 5,679 roll calls on 1,719 bills joined (Vote.csv → History.csv
refid → bill/date/motion, same direction and venue rules as every other year, 2022 carryover lines dropped); 136 of 141
members resolved through a suffix/nickname/first-last/unique-surname cascade (5 counted as unresolved, never guessed);
2023 co-patrons from LIS Sponsors.csv (971 bills) so 2023 does not masquerade as a no-co-patron year. Result:

| | 2024 all / hard | 2025 all / hard (fixed set) |
|---|---|---|
| original pipeline (no 2023) | 84.36 / 64.86 | 86.09 / 67.77 |
| 2023 in the features' history only | 84.36 / 64.85 | 86.08 / 67.71 |
| 2023 in history AND trained on | 84.36 / 64.86 | 86.14 / 67.90 |

Noise-level (+0.05 / +0.13 on 2025, nothing on 2024). **One more year of data does not move it either.**

## Verdict after six rounds (2026-09-29)

Every reasonable option inside our own data has been tested under one protocol (choose on 2024, score once on 2025,
2026 locked): new features (~25), relationship networks, member × content latent factors (first votes and all
526k contested ballots), deeper combinations, alternative model classes and blends, regime weighting, per-chamber
models, two-level structure, label cleaning, and an additional year of data. The hardest third stays 66–68%; overall
86%. The remaining error is how each party lines up on a specific bill in a specific room — decided privately, not
recorded in any public vote. What can still move it is NEW information: the team's own contact log and positions,
and (owner's call, later) reading bill content. Meanwhile two findings ARE usable now: the per-member labels are well
calibrated (Likely 94 / Leans ~70 / Toss-up 57 in 100), and consensus kills can be flagged at the bill level (4× base
rate in the top 10%), with the co-patron pattern holding within patrons (p ≈ 6×10⁻¹²).

## The ceiling, measured — and the hard third reverse-engineered (2026-09-29)

Owner: "would a statistician stop here? ... if we know what composes that final 30% can we reasonably predict when
a bill will end up in it?"

**1. Natural-experiment ceiling** (`twin_ceiling.py`). 734 pairs of near-identical bills (summary Jaccard ≥ 0.8) voted
separately — almost all House/Senate twins in the same session. Using one twin's ACTUAL first vote to call the other's
party positions (a cheat no forecast has):

| pairs | both parties match | patron's party | other party |
|---|---|---|---|
| all 734 | 75% | 88% | 80% |
| opposite chambers (697) | 76% | 90% | 81% |
| same venue AND same patron standing (75) | 87% | 91% | 91% |

Our model calls other-party members right 80% of the time on 2025 — **at the level of the identical-bill oracle.**
Bill content cannot say more than this; the rest depends on the particular room, people and day.

**2. The hard third by vote SHAPE** (`vote_shapes.py`, bill-level, train ≤2024, test 2025, 1,624 bills):

| shape | share | AUC | top-10% flagged are this shape |
|---|---|---|---|
| everyone for | 48% | 0.83 | 93% |
| straight party line | 24% | 0.80 | 64% |
| everyone against (consensus kill) | 9% | 0.85 | 33% |
| **mixed split** (members break from their party) | 19% | **0.58** | 30% |

Shape guessed right 59% overall (48% by always guessing "everyone for"); 83% on the quarter of bills it is surest
about. **Mixed splits are the irreducible core** — near-unpredictable before the meeting, and 28% of the hard-third
misses. Consensus kills are detectable but top out at 1-in-3, so they belong on the bill as a risk, not in a guess.

**Verdict:** stopping is now justified by measurement, not by exhaustion. The model is at the identical-bill ceiling;
the residual is mixed splits (unknowable from public data) plus consensus kills (a bill-level risk). New information —
the team's contact notes — is the only lever left, and it targets exactly the mixed-split members.

## Last two families (2026-09-29) and the bounded claim

| tried | 2025 all | hard (fixed) | mixed-split votes | verdict |
|---|---|---|---|---|
| baseline | 86.09 | 67.77 | 76.14 | — |
| **district × topic** — raw subject one-hots so trees can form (district profile × topic) combinations; aimed at mixed splits (`topic_x_district.py`) | 85.85 | 67.05 | 76.01 | no gain, even on mixed splits |
| **agenda position / docket length** (2025 DOCKET + SUBDOCKET; only 638 of 1,663 first votes match a listing) | — | — | — | last third of agenda 5.1% consensus kills vs 2.4% first third = ~6 bills; noise |

**The bounded claim (what the measurements support — and what they do not).** Not "no breakthrough is possible" —
that is a claim about every idea, not a measurement. What IS measured:
1. Individual defection from one's own party costs ~3 points (perfect party positions → 97.3%). The rest of the
   86 → 97 gap is predicting each party's position.
2. Our party-position accuracy (84%) already exceeds the concordance of near-identical bills voted in the other
   chamber (75% both parties; 734 pairs) — i.e. it beats a forecast that has the answer for an identical bill.
3. Of the four vote shapes, three are predictable (AUC 0.80–0.85); mixed splits (19% of bills) sit at AUC 0.58 and
   did not move under any member, district, topic, network or latent-factor representation tried.
4. ~35 approaches across seven rounds, one protocol, all inside ±0.6 of 86% overall.
Remaining room for a breakthrough is therefore confined to information NOT in the public record about how each party
will line up on a specific bill — which is what the team's contact log captures.

## Who sets the party lineup — and the one public trace we hold (2026-09-29)

Owner: "how do you know its about party line up ... who are the party decision makers behind the scenes what other
sources". **How we know:** with each party's position known, member accuracy is 97.3% — individual defection costs ~3
points, so ~11 of the 14-point gap is the party's position on the bill. **Who sets it (roles):** caucus leadership
(Speaker / majority leaders / president pro tem / minority leaders, in private caucus), committee and subcommittee
chairs (what is heard and when; money-committee chairs most of all), the Governor's office, state agencies (fiscal
impact statements) and local-government associations (VACo, VML), and stakeholder deals.

**Committee chairs as co-sponsors** (`chairs_as_sponsors.py`; roles exist only in the authorized 2025–26 rosters, so
the test is 5-fold by bill WITHIN 2025 — weaker than year-ahead). Descriptive: bills with a chair among the sponsors
get 82% yes (69% without); other party 64% (54%); and the model is WORSE on the other party there (75.7% vs 82.3%).
Predictive: base 87.68% → +chairs 87.65%; other-party 83.50% → 83.11%. **No gain** — the model already carries it
through patron standing and co-patron counts.

**Sources that could reveal lineups before a vote, not yet collected:** interest-group support/oppose lists, the
Governor's legislative agenda, agency positions in fiscal impact statements (full text), news coverage; and the
team's own contact notes (being built — the most direct).

## Round 8 (2026-09-29) — chairs 2019–2025, public attention, personal profile

| tried (year-ahead: choose 2024, score 2025) | 2024 all / hard | 2025 all / hard (fixed) | verdict |
|---|---|---|---|
| baseline | 84.36 / 64.86 | 86.09 / 67.77 | — |
| **committee chairs 2019–2025** from LIS legacy session pages (`legacy_chairs.py`; 25 committees × 7 sessions; validated vs the 2025 API roster: 20/23 exact, the 3 differences are real mid-year personnel changes); inputs: hearing chair is a sponsor, chairs among sponsors, voting member chairs/vice-chairs | 84.19 / 64.36 | 86.04 / 67.61 | no gain — confirms the within-2025 result with the stronger test |
| **news coverage, Cardinal News** mentions before the vote (`news_mentions.py`; 80–194 bills/session, 3.3% of 2025 ballots) | 84.29 / 64.65 | 86.19 / 68.06 | noise-level; too few covered bills |
| **legislative attention** — same-topic bills filed this session, by party, bipartisan filing, near-twins by other patrons (`legislative_attention.py`) | 84.47 / 65.18 | 85.97 / 67.41 | does not replicate |
| **personal profile** — member's own filing and co-sponsoring on the topic (earlier sessions and now), topic specialisation, tenure, own bill pass rate (`personal_profile.py`) | 84.31 / 64.71 | 86.14 / 67.92 | noise |

**Descriptive finding that supports the public-attention hypothesis:** 2025 bills covered by Cardinal News before the
vote are more contested (57% yes vs 74%; other party 42% vs 58%) and the model is much worse on them (76.4% vs 86.4%).
Attention marks exactly the bills the model struggles with — but one outlet covers too few bills to help the totals.

**Public-attention sources checked:** Virginia Mercury, Blue Virginia, WRIC, WSLS, Virginia Business — robots.txt blocks
Anthropic crawlers (respected). Bearing Drift, WTVR, WHRO, WTKR, NBC29, The Richmonder — allowed but no article API.
Virginia Scope — allowed, API, small archive (not yet used). GDELT DOC API — works back to 2017 but rate-limited us
twice even at 8 s spacing; GDELT asks heavy users to use its bulk "web ngrams" dataset instead (a large download —
needs the owner's go-ahead). Google Trends — no permitted automated access. Per-bill public comments — not published.
Speaking on bills — no floor transcripts; committee minutes only in the 2025–26 data (within-year only).

## Corrections from the five-perspective panel (2026-09-29) — see [[testing/panel_2026-09-29]]

- **The twin "ceiling" is an interval, not a ceiling** (Cover–Hart): content-only accuracy on joint party positions
  lies between 75% and ~86% (other party 80–89%). Earlier lines above saying "bill content cannot say more" and
  "stopping is justified by measurement" are withdrawn.
- **Use the leave-one-out 96.4%** (copy one party-mate's actual ballot) in place of the 97.3% party-position figure.
- **2025 is a validation year** (≈35 approaches scored on it); only the locked 2026 score is a clean test.
- **"No gain" = no gain ≥ ~0.65 points** (80% power); the hardest third's year-to-year spread (64.9–68.9) is wider than
  the "plateau" band. Acceptance from now on: paired, bill-clustered log loss pooled over rolling-origin years, z ≥ 3.
- **The co-patron finding survives a leak check** (`copatron_leak_check.py`): 0 of 1,663 2025 bills gained co-patrons
  after filing; 19.8% vs 6.0% using co-patrons at filing.

## The locked 2026 test — scored once (2026-09-29)

Rules frozen and committed first (`frozen/prereg_2026.json`, sha 7895dc13, commit e487e5b), then scored once
(`prereg_2026.py --score` → `frozen/score_2026.json`). Model trained on 2019–2022, 2024, 2025. 22,163 ballots on
1,989 bills; 95% intervals by bill-clustered bootstrap.

| measure | 2026 | 95% | pre-registered expectation |
|---|---|---|---|
| accuracy | **85.9%** | 84.9–86.8 | 84.4–86.1 across 2021–2025 — **held** |
| other-party accuracy | 78.9% | 77.3–80.6 | |
| party position right | 82.6% | 81.7–83.5 | |
| room outcome right | **91.5%** | 90.5–92.4 | 88.4% on 2025 |
| log loss (logit baseline 0.426) | 0.312 | 0.298–0.326 | |
| hardest third (diagnostic) | 65.9% | 63.7–68.2 | |
| always "yes" | 73.5% | | |

**The labels, as a volunteer reads them (2026):**

| label | share of calls | right | 2025 validation |
|---|---|---|---|
| Likely | 72% | **95 in 100** (94.2–95.6) | 93.6–95.3 — held |
| Leans | 20% | **66 in 100** (63.2–68.4) | 67.5–73.4 — **came in lower** |
| Toss-up | 8% | **54 in 100** (50.5–57.9) | 53.6–61.2 — held |

Any wording that says Leans is right "about 70 in 100" should say **about 2 in 3**. (Checked: the app shows no
label percentages today.) By chamber: House 82.5%, Senate 89.2%; subcommittee votes 81.3%.

## Party positions first — rejected (2026-09-29, `theta.py`)

The panel's Θ: predict each party's position per bill directly (one row per bill × side), derive members as
q(1−d) + (1−q)d. Rolling origin 2021/2022/2024/2025 against the one-stage model:

| | party position right (one-stage → Θ) | member log loss (one-stage → Θ) |
|---|---|---|
| 2021 | 83.7 → 83.7 | 0.328 → 0.330 |
| 2022 | 82.4 → 82.3 | 0.354 → 0.365 |
| 2024 | 81.2 → 80.8 | 0.345 → 0.355 |
| 2025 | 83.9 → 82.6 | 0.317 → 0.334 |

Pooled per-bill log-loss: **z = −7.6 (worse)**; averaging the two: z = −2.0. Larger trees chosen on 2024 (80.5–80.8%)
do not close it. **The member model already calls party positions as well as a model built only for them**, and
deriving members from the party loses the member-level cues. Kept as a negative result.

## GDELT news attention — no gain; bulk download stopped (2026-09-29, `gdelt_effect.py`)

2025 pilot (GKG bulk, 74 session days, 26,621 Virginia-legislature articles after dropping 1,503 West Virginia
articles — audit #141). Articles name people and themes, not bills (22 bill numbers in URLs). Inputs dated before
the decision: patron mentions, member mentions, topic-word volume (all-time and last 14 days). Stacked on the
existing models, 5 folds by bill: **ballots z = 0.9, fate z = 1.1 — no gain.** Rule written before running: more
years (~40 GB each) only if z ≥ 3 — so **no further download.**

## How this compares to anyone else's published number (2026-09-29)

No product publishes member-level accuracy. FiscalNote and Skopos claim 93–99% on whether a BILL passes, which is
mostly the base rate (most bills die); Plural and Quorum make no accuracy claim ([[testing/panel_2026-09-29]],
marketing memo). The closest published research:

| study | what it predicts | tested on | accuracy | "always yes" | errors removed |
|---|---|---|---|---|---|
| **this model** | VA committee/subcommittee **first votes** | a later, locked year (2026) | **85.9%** | 73.5% | **47%** |
| [Kornilova et al. 2018](https://aclanthology.org/P18-2081/) | US Congress roll calls | later session 2013-14 / 2015-16 | 83.6% / 71.9% | 65.9% / 61.1% | 52% / 28% |
| [Budhwar 2018](https://digitalcommons.calpoly.edu/theses/1818/) | California legislators, from floor speech | same session | up to 83% | not reported | — |
| [Political Actor Agent, AAAI-25](https://ojs.aaai.org/index.php/AAAI/article/download/32017/34172) | US House floor votes | random split of the same sessions | 91.8% | not comparable | — |

Different tasks, so no clean ranking: same class as the best forward-tested research, not provably ahead. Floor votes
and same-session splits are easier than a first committee vote scored on a later year.

**How sure, by confidence rank (2026 locked test; deciles are arithmetic on the pre-registered risk–coverage curve):**
most-sure 10% of calls right 99.5 in 100 · 2nd 98.8 · 3rd 98.4 · 4th 96.0 · 5th 95.4 · 6th 91.8 · 7th 86.3 ·
8th 74.5 · 9th 63.7 · least-sure 10% 54.3. The cut points were drawn within 2026 itself; for live use they must be
fixed from earlier years, then checked on the next session.

## Stakeholder lineups — association positions and House written testimony (2026-09-29, `stakeholder_effect.py`)

Owner cleared both. Tested with the new acceptance rule (`accept.py`: fitted on earlier years' out-of-sample
predictions, scored on the next year, pooled 2022/2024/2025, per bill, accept at z ≥ 3). Neither was tested on bill
fate: testimony exists only once a bill is on an agenda, and scorecards pick bills after the session.

| source | coverage | effect on covered ballots | pooled |
|---|---|---|---|
| **VALCV scorecard positions** (Support/Oppose, 2019–2025; `va_positions.py`) | 26–29 bills a year, ~1.7% of ballots | accuracy 77.3→82.4 (2022), 84.9→87.5 (2024), 84.4→84.8 (2025) | z = 1.3 — **not proven** (too few bills; direction positive) |
| **HODSpeak written testimony** (counts only; `hodspeak_comments.py`; 2021/22/24/25: 1,336–2,828 bills with comments a year, 7,420–34,789 comments) | ~50% of ballots (bills on a House agenda) | accuracy 78.7→77.9, 79.1→78.9, 80.1→80.0 | z = −2.9 — **rejected** (slightly worse) |

Public comment volume and its support/oppose wording say nothing the model does not already know about how members
vote. One organization's stated position points the right way on the bills it covers, but a single scorecard is too
thin to prove it; many organizations' lists together might be — none other found in machine-readable form that
allows automated access (Family Foundation blocks Anthropic crawlers; VPAP and NFIB refuse automated requests).
