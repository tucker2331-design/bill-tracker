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
articles — audit #144). Articles name people and themes, not bills (22 bill numbers in URLs). Inputs dated before
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

## Do members vote for bills like the ones they sponsor? (2026-09-30, `similar_sponsor.py`)

Owner: *"are members votes at all correlated to wether they have introduced similar language or introduce in the same
topic?"* 2021/2022/2024/2025 first votes, dated before each vote; model predictions are year-ahead (`accept.py`).

| member … | patron's party: yes rate (n) | other party: yes rate (n) | model's miss | adds to forecasts? |
|---|---|---|---|---|
| sponsored a near-identical bill (summary match ≥ 0.30) | 90.8% (422) vs 87.3% | 61.0% (82) vs 57.9% | ≈ 0 | no, z = −0.8 |
| filed a bill on the same topic before | 87.4% (18,517) vs 87.3% | 57.1% (16,756) vs 58.9% | ≈ 0 | no, z = −4.1 |

Sponsoring near-identical wording goes with ~3 points more yes, but it is rare (0.8% of votes) and the model already
gets those votes right. Filing on the same topic tells nothing. (Round 8's personal-profile test agrees.)

## Member-card reasons: what each one really rests on (2026-09-30, `why_member.py`)

Owner: strength words unclear ("idk what you have some of"); "not clear why those specifically matter". `why_member.py`
now reports, per reason, every input's own swap effect plus the member's value and the typical peer value.
Findings that changed the card:
- **Two HB 1515 reasons were absences, not findings.** "Similar earlier bills" (+3.5 to +4.0) and "wording" (+10 to
  +18) came only from HB 1515 HAVING NO similar bills with votes / no wording score — the swap measured "peers had
  data". Both now flagged `absent` and moved to Checked. **Method lesson: a swap-based reason must check the no-data
  flags before it is shown.**
- "Overall voting record" was three different things: Tran/Helmer = length of record (~3,500 contested votes vs ~370);
  Kilgore = how Republicans in THIS subcommittee voted this year (a room fact). Retitled to what it is.
- At ±2 the evidence sometimes pointed the other way (Sullivan: backed 91 of 93 of Shin's bills, below the typical 97,
  yet +2.3 toward yes) — interactions. Display threshold raised to 3 in 100.
- **Resolved:** Kilgore's `ses_rate` (0.262) is keyed by (session, room, same-side) with NO party, so it pools BOTH
  parties' votes on the other party's bills in the Studies Subcommittee: 17 of 76 in 2026 (R on D bills 17/44 + D on R
  bills 0/32), smoothed (17+5.5)/(76+10) = 0.262. Likewise `subroom_rate` (0.439) = own-party support there, 94 of 233
  across 2024 and 2026. The card's evidence lines now describe the room ("crosses party lines", "own party's bills"),
  not one party — the first draft said "Republicans backed 17 of 44", which was not what the model uses.

**How a "determinant" is measured here:** a reason counts only if (1) it moves the guess when swapped for real peers'
values, (2) the member actually has data for it, and (3) as a new input it improves year-ahead forecasts across
2022/2024/2025 (z ≥ 3). Descriptive gaps without (3) are "the model already knows".

## Which reasons may appear on a member card — the three-check gate (2026-09-30, `reason_gate.py`)

Owner: a "Leans yes" card showed only reasons for no — because the party starting point had been removed (owner
2026-09-28: "what does a republican on a dem bill like idk why im being shown that"). Fix: the card now opens with
**"Where the guess starts"** (Democrats on a Democrat's bill: 87 in 100 vote yes; Republicans: 62 in 100; first votes
2019–2025), and every reason is a push away from that. Owner then asked for more reasons meeting the three checks.

Check 3 was run two ways over 2021/2022/2024/2025 (year-ahead, per-bill paired log loss, pooled z ≥ 3):
**leave-one-out** (what a group adds that nothing else carries) and **add-to-base** (party & standing + venue, plus
the group — does it carry information at all).

| reason group | leave-one-out z | add-to-base z | card |
|---|---|---|---|
| where the vote happens (sub vs full committee) | 23.2 | (base) | shown |
| co-patrons & companion | 7.7 | 11.0 | shown |
| how members voted on similar earlier bills | 3.1 | 8.6 | shown when data exists |
| the companion bill's earlier vote | 1.2 | 7.3 | shown |
| similar bills in this room (room memory) | 0.2 | 4.9 | shown |
| the room's members as a group | 2.1 | 3.1 | shown (marginal; negative in 2021–22) |
| party & standing | −1.4 (carried by room records) | (base) | the starting point |
| 16 others — incl. waiting time, committee/subcommittee records, own voting record, patron's record, district, subject, ideal points, summary words | < 3 both ways | | never shown as a reason |

**HB 1515 cards after the gate:** Democrats start at 87 → subcommittee vote −8 to −13, no co-patrons −7 to −9 →
Leans yes. Kilgore starts at 62 → subcommittee −12, no co-patrons −5, only Republican voting there +7 (lone
Republicans in a subcommittee backed Democrats' bills 39 of 71 times vs 51 in 100 with other Republicans; thin) →
Toss-up. Dropped from cards: "carried over, waiting", "this subcommittee's record", "long voting record".

## The hardest third, attacked directly (2026-10-15)

Owner: "keep digging on the hard 1/3 ... use the 85% we have in the training ... predict it will be party line ...
categorize that hard 1/3 ... try more than one or two hypotheses." Every test: year-ahead (fit on earlier years, score
2022/2024/2025, pooled per bill, z ≥ 3), the FIXED hardest third reported (`accept.py` now prints it).

**What the hardest third is made of** (2021/2022/2024/2025 pooled; `shape_first.py`, `hard_third_more.py diag`):

| cut | share of the hard third | model right there |
|---|---|---|
| actual vote shape: everyone yes / party line / mixed split / everyone no | 36.5% / 25.2% / 23.9% / 14.4% | 72.8% / 73.7% / 60.2% / 51.5% |
| voter: other party / patron's party | 70.2% / 29.8% | 66.4% / 68.3% |
| venue: subcommittee / committee / floor | 62.9% / 23.6% / 13.6% | 66.0% / 70.0% / 66.3% |
| **the room's outcome was still called right / missed** | **80.1% / 19.9%** | 71.8% / 47.3% |

Half the hard third ends unanimous: the model hedged on bills the room agreed on. And 80% of the hard third sits in rooms
whose OUTCOME we called right — those member misses do not change the result.

| hypothesis | result |
|---|---|
| H1 bill viability (fate model) × side | reject, z −2.4 |
| H2 the chair (co-sponsors; record on this patron) × side | reject, z −2.0 |
| H3 fiscal cost × side (fit 2025 → score 2026) | reject, z −2.3 |
| H4 domain scores (VALCV) | not run — built from the same roll calls the model already uses |
| H5 what members said on the topic in earlier committee debates (2026, time-forward) | reject, z −5.0 — captions show who was called on, not their side |
| H6 this session's party lines on the topic × side | reject, z 1.4 |
| shape forecast (party line / mixed / unanimous) × side | reject, z −0.8; shape model 52–61% vs 45–49% base; "vote with your party" on predicted party-line hard ballots 71.7% vs model 74.2% |
| P5/P6 this session: patron's bills, member on this patron's bills | reject, z 0.4 |
| P9 recalibration by side × venue | reject, z −2.5 |
| P10 the room's habit of unanimity | reject, z −1.6 |
| P8b words that go with the other party voting yes | reject, z 0.8 |
| **P8 consensus words** — per-word log-odds of unanimous-yes / unanimous-no first votes, learned from earlier years, on the summary AS INTRODUCED + title | **ACCEPT, z 4.2**; hardest third 68.9→69.5 (2022), 65.1→67.0 (2024), 67.9→68.8 (2025) |
| **P8 replicated on 2026** (never used to choose it) | **accuracy 85.99 → 86.24; hardest third 66.29 → 67.04; z 4.0** |

P8 is text-derived (summary words): internal research until the owner's Standard #3 call.
| **P8 built INTO the member model** (`gbm_words.py`; word scores as two more inputs, each year from earlier years only) | **ACCEPT, z 5.6**; accuracy 84.92→85.01 / 84.36→85.09 / 86.09→86.38; hardest third 68.85→69.13 / 64.86→67.06 / 67.77→68.62 (2022/2024/2025) |
| P8c with two-word phrases, in the model | z 6.8 on log loss, but hardest third 68.85→68.82 / 64.86→67.07 / 67.77→67.58 — less consistent than single words |
| R1 mixed-split words × member's defection rate | reject, z −2.1 |
| **P8 in the model, scored on 2026** (trained 2019–2025, never used to choose it) | **does NOT replicate:** accuracy 85.86→85.42; hardest third 65.90→64.56; other party 78.94→77.79; z −0.2 |

**Verdict on the consensus words:** two ways of using the same signal disagree on the fresh year. As a simple stacked
adjustment on top of the model it replicated on 2026 (hardest third 66.29→67.04, z 4.0); as raw inputs inside the
trees it did not (64.56 vs 65.90). The trees overfit the word scores to the earlier years; a one-coefficient-per-input
linear layer generalised. If the signal is used at all, it is the stacked form — and it is still a small lift
(+0.75 points on the hardest third) that needs the owner's Standard #3 call (text-derived). The hardest third remains
what it was: half of it consensus votes the model hedges on, the other half party positions decided privately.

## New techniques for member votes and the room result (2026-10-16, `levers.py`)

Owner: "try things in ways you dont normally ... to make a llm accurate they use thousands of tuned levers." Only numpy
is installed (no downloads without the owner's OK), so every technique is written in numpy. One frame for all:
CHOOSE (learn 2019–2022, score 2024), CONFIRM (learn to 2024, score 2025), REPEAT (learn to 2025, score 2026, the
already-scored test year). Measures: member accuracy, FIXED hardest third, room result (most members yes).

| technique (2024 choose unless noted) | member | hardest third | room |
|---|---|---|---|
| base (locked model) 2024 / 2025 / 2026 | 84.36 / 86.09 / 85.86 | 64.86 / 67.77 / 65.90 | 87.38 / 88.36 / 91.45 |
| **bagging: 8 trees, each on 50% of rows and 50% of inputs** — 2024 / 2025 / 2026 | **84.75 / 86.26 / 86.29** | **66.02 / 68.26 / 67.17** | 87.60 / 88.30 / **91.86** |
| bagging: 5 trees, 70% rows / 60% inputs — 2024 / 2025 / 2026 | 84.62 / 86.07 / 86.22 | 65.64 / 67.70 / 66.97 | 87.65 / 88.79 / 91.75 |
| bagging: 10 trees, 70% / 60% | 84.61 | 65.60 | 87.81 |
| direct room model (bill-level "most vote yes"), members shifted 30% toward it — 2024 / 2025 / 2026 | 84.67 / 85.03 / 85.24 | 65.81 / 64.57 / 64.04 | 87.92 / 89.53 / 91.40 |
| direct room model + bagging — 2024 / 2025 / 2026 | 84.81 / 85.27 / 85.76 | 66.20 / 65.36 / 65.60 | 88.36 / 89.35 / 91.50 |
| joint room model (second stage reads the other members' first-stage predictions) | 84.42 | 65.05 | 87.10 |
| larger trees, tighter limits / deeper / slower+longer / more weight on uncertain votes | 83.85–84.23 | 63.32–64.47 | 86.89–87.81 |
| neural network with learned member / patron / committee codes (after fixing a scaling fault) | 81.85 (blend 30%: 84.40) | 59.80 (64.99) | 84.43 (86.67) |

**Result:** bagging with 50% rows and 50% inputs improves member votes AND the hardest third in all three years
(+0.39 / +0.17 / +0.43 member; +1.16 / +0.49 / +1.27 hardest third), and the room result in two of three (2026 91.45 →
91.86). Per-year z +1.5 / +0.5 / +3.8 (combined ≈ 3.3). It changes HOW the model is trained, not what it reads — no new
data, no text. Because 2026 has now been used, the next clean test is a frozen forward test on 2027.
The direct room model helps the room result in 2024 and 2025 but hurts member votes and adds nothing in 2026 — not adopted.

## Public traces of private decisions (2026-10-16, `private_traces.py`)

Owner: "we need to learn how to derive the private decisions from public data." A private decision often leaves a
public trace before the vote. Six traces, each a stacked layer on the locked member model (fit on earlier years,
score 2022/2024/2025, pooled per bill, accept at z ≥ 3, fixed hardest third shown).

| trace (the private decision → its public mark) | result |
|---|---|
| A. Leaders back the bill → Rules committee members / Rules chair sign as co-patrons | reject, z −2.1 |
| B. The bill was planned early → rank of the draft request number in its session | reject, z 0.0 |
| C. Bargaining before the vote → passed by for the day, substitute, earlier hearing | **not testable:** under 0.5% of ballots carry any such action before the FIRST vote; the fit did not converge on so few |
| D. The governor's agenda → governor's party vs voter and patron | reject, z −10.3 |
| E. Close seats get a pass to break from the party → voter's last general-election margin (Wikipedia election boxes, 94–98% of ballots matched) | reject, z −1.9; hardest third 68.85→68.69 / 65.05→64.64 / 67.92→67.89 |
| F. Leaders give easy bills to members in close seats → PATRON's last margin | reject, z 0.8; hardest third +0.08 / +0.47 / +0.09 |

**Result:** none of the six traces adds to what the model already reads. The model already carries the patron, the
co-patrons, the member's history, the district and the room; these traces repeat that information. The one change
that helps (bagging, above) changes how the model learns, not what it reads.
Source note: election margins come from the Wikipedia API (`tools/historical_cache/election_margins.py`, 6 requests,
robots.txt has no rule against this agent; numbers cite the Department of Elections).

## A second model family in the blend (2026-10-17, `levers.py linear` / `blend`)

The trees cut each input into steps. A penalised logistic model draws smooth slopes instead: every input standardised,
3 bends per input (hinges at training quantiles), products of the 8 strongest inputs, and every term crossed with the
voter's side (own party / other party). Same inputs as the locked model — no new data, no new text. It fits in
seconds, so its settings were searched on CHOOSE (2024) only; 2025 and 2026 were scored once per finalist.
Blends are averaged in log-odds, 80% trees / 20% linear (weight chosen on 2024; 0.2–0.3 is flat).

| model (2024 / 2025 / 2026) | member | hardest third | room | z (log loss, per bill) |
|---|---|---|---|---|
| locked trees (base) | 84.36 / 86.09 / 85.86 | 64.86 / 67.77 / 65.90 | 87.38 / 88.36 / 91.45 | — |
| linear model alone (3 bends, 8 products) | 84.24 / 86.04 / 86.47 | 65.41 / 67.68 / 67.75 | 88.03 / 89.04 / 91.96 | −2.0 / −3.8 / −0.2 |
| base trees + 20% linear (no products) | 84.80 / 86.13 / 86.24 | 66.17 / 67.89 / 67.04 | 87.27 / 88.85 / 91.86 | **+7.0 / +3.2 / +4.9** |
| base trees + 20% linear (8 products) | 84.97 / 86.06 / 86.33 | 66.69 / 67.66 / 67.31 | 87.54 / 88.92 / 91.80 | **+6.9 / +5.2 / +7.2** |
| **bagged trees + 20% linear (8 products)** | **85.12 / 86.33 / 86.50** | **67.12 / 68.47 / 67.82** | **87.92 / 88.85 / 92.11** | +5.0 / +2.5 / +6.2 |
| … plus one shift per member × side and per committee in the linear model | 85.14 (2024) | 67.19 | 87.81 | +4.9 — no gain, not kept |

**Result:** the best candidate is bagged trees + 20% linear model. It improves member votes, the hardest third AND the
room result in every one of the three years: +0.76 / +0.24 / +0.64 member, +2.26 / +0.70 / +1.92 hardest third, +0.54
/ +0.49 / +0.66 room. The 2025 log-loss z (2.5) is under 3; the base-trees blend passes z ≥ 3 in all three years but
lifts accuracy less. Several finalists were scored on 2025/2026, so those years are no longer clean — a frozen 2027
forward test is the only clean confirmation left.

Also tested and not kept (2024 choose): 16 bags (z 1.5, no better than 8); 400 rounds per bag (z 2.2); 30% of inputs per
tree (z −4.0); 30% of rows (z 1.1); depth 5 (z 0.6); recent years weighted more, 0.85 or 0.7 per year back (z 0.7 /
0.3). A per-member correction layer on the base predictions (own shift per side and own confidence, ridge 3–100)
lifted 2026 accuracy a little but worsened 2026 log loss at every penalty (z −2.4 to −2.9): not kept (`member_layer.py`).

## Owner approved the blend (2026-10-19) — frozen copy, gains counted, and the session learning itself

**Approved:** bagged trees + 20% linear model. Frozen as `tools/calibration/blend_2027.py` (copy of the research code;
verified identical to the research predictions on 2026, max difference 0.0, accuracy 86.50%).

**What the gain is in votes and bills (`gains.py`, adopted blend vs the old locked model):**

| year | votes fixed / broken / net | bill results fixed / broken / net |
|---|---|---|
| 2024 | 390 / 241 / +149 of 19,689 | 24 / 14 / +10 of 1,830 |
| 2025 | 269 / 228 / +41 of 17,553 | 17 / 9 / +8 of 1,624 |
| 2026 | 378 / 236 / +142 of 22,163 | 23 / 10 / +13 of 1,989 |

Every changed vote is in the hardest third (changes happen only near 50/50).

**What we can and cannot predict (misses left, 2026; same pattern 2024/2025):**

| actual vote shape | patron's own party | other party |
|---|---|---|
| unanimous yes | 99.8% right | 91.2% right (12% of misses) |
| party line | 97.6% | 69.1% (24% of misses) |
| mixed split | 88.7% | 64.7% (24% of misses) |
| unanimous no | **36.1%** (22% of misses) | 89.9% |

"Unanimous no" first votes are mostly NOT defeats: the motion text is "subcommittee recommends striking from the docket"
(61–73 bills a year), "laying on the table" (47–86) or "continued to next session" — mostly the patron's own choice.
Public traces of that choice (near-copy voted first, the patron's past withdrawals, the patron's bill count) were
tested (`withdraw_probe.py`): too rare or too weak, z −2.8, rejected.

**The session learning itself (`online_layer.py`, `online_relinear.py`).** The model learns from earlier years only;
but every vote cast earlier in the same session is public before the next one. Before each session week, the linear
half of the blend is refit on earlier years + this session's earlier votes (weight 3), and blended 70/30 with the
bagged trees. Below 3,000 session votes it uses earlier years only (without that gate, 2024's second week was refit on
11 easy week-one bills and broke 21 room calls). Settings chosen on 2024:

| year | member | hardest third | room | z |
|---|---|---|---|---|
| 2024 | 85.12 → 85.31 | 67.12 → 67.71 | 87.92 → 88.25 | +6.7 |
| 2025 | 86.33 → 86.85 | 68.47 → 70.02 | 88.85 → 89.41 | +9.2 |
| 2026 | 86.50 → 87.09 | 67.82 → 69.58 | 92.11 → 92.66 | +9.8 |

Against the old locked model on 2026: member 85.86 → 87.09, hardest third 65.90 → 69.58, room 91.45 → 92.66.
A lighter version (one shift and slope per party × side, refit daily on the base predictions) also helps every year
but less (pooled z 5.2). No leak: each week uses only votes from earlier weeks, and a bill has one first vote.
2025/2026 have been seen many times; the 2027 forward test is the clean check. Not yet approved by the owner.

Also tested on top of the weekly refit (2026-10-19), chosen on 2024, not adopted:
- larger linear share (0.4 / 0.5): 2024 member 85.13 / 85.11 vs 85.31 at 0.3 — worse on the choose year.
- per-party session shift stacked on top (`ONLINE_BASE=... online_layer.py party`, ridge 30): room +0.44 / +0.49 /
  +0.85 (2024/2025/2026) but member +0.15 / +0.04 / +0.01 and pooled z +0.9 — a candidate for the room result only.
- bagged trees refit once at mid-session on the first half (`midsession_trees.py`, second half scored): member
  −0.35 / +1.12 / +0.69 — hurts the choose year, rejected (the session-learning gain shows again in 2025/2026).
- bagged trees depth 4 (400 rounds) / depth 8 (min leaf 60), 2024: z +0.4 / +1.7 — no better than depth 6.

## Locked 2027 forward test + can we see a bill being dropped? (2026-10-20)

**Owner approved arm B** ("if they are going to consistently improve accuracy then yes" — it did, all three years).
`frozen/prereg_2027.json` (sha256 baff9d0a…) locks two arms in `blend_2027.py`: A = bagged trees + 20% linear; B = A
with the weekly session refit. Both verified identical to the research predictions on 2026 (difference 0.0). Reference
= the old locked model. Training years 2019–2026 (a first freeze wrongly listed 2017–18, which have no member names;
caught before any score, deleted and re-frozen the same day). `--score` refuses until 2027 rows exist.

**Can we predict that a bill will be struck, tabled or continued at its first vote?** (`drop_model.py`; bill-level
trees, each year learned from earlier years only; target = unanimous-no first vote)

| year | drops | ranking AUC | top 10% riskiest bills: share dropped / drops held | top 20%: drops held |
|---|---|---|---|---|
| 2022 | 179 of 1,650 | 0.81 | 34% / 56 | 92 (51%) |
| 2024 | 214 of 1,830 | 0.84 | 43% / 79 | 124 (58%) |
| 2025 | 142 of 1,624 | 0.85 | 33% / 54 | 82 (58%) |
| 2026 | 207 of 1,989 | 0.92 | 60% / 118 | 162 (78%) |

**Result:** partly. The risk can be RANKED — the riskiest tenth of bills is dropped 3–6 times as often as the base rate
(9–12%) — but it can rarely be CALLED: only 7–48 bills a year reach P ≥ 0.5. "Continued to next session" (long
sessions only) is the most visible; "struck at the patron's request" the least (the private decision). The new
inputs (even-year session, committee and patron drop history, bill counts) add almost nothing over the member model's
own inputs (AUC +0.00 to +0.01), and P(drop) as an input to member votes does not help (stacked, z −0.1, rejected).
Use: a watch list for volunteers ("high risk of being dropped at first hearing"), not a change to vote calls.

## On top of arm B: more session learning (2026-10-20) — big gains in 2025/2026, a small loss in 2024

| method (on arm B) | 2024 member / hardest third | 2025 | 2026 | verdict |
|---|---|---|---|---|
| session booster: 15–100 shallow trees fit each week on this session's earlier votes, starting from B (`session_booster.py`) | −0.02 to −0.34 / −0.1 to −1.0 | +0.4 to +0.8 / +1.1 to +2.4 | +0.0 to +0.6 / +0.1 to +1.7 | not adopted: loses on 2024 in every version |
| best of those (15 trees, depth 2, lr .05) | 85.31→85.28 / 67.71→67.62 | 86.85→87.31 / 70.02→71.41 | 87.09→87.38 / 69.58→70.46 | pooled z +8.7; 2024 z −1.1 |
| member × side and committee offsets inside the weekly refit | 85.17–85.20 (vs 85.31) | = | — | worse on 2024, stopped |
| per-side × venue × chamber session shift (`online_layer.py vch`) | 85.29 / 67.64 at best | ≈ 0 | +0.04 / +0.12 | no gain |

**Why 2024 differs:** the booster only starts after 3,000 session votes. In 2024 that is the week of 29 January, and its
lesson from the first three weeks did not carry into the next one (net −14 votes that week; +0 in crossover week). In
2025 (+103 votes) and 2026 (+91) the drift held through the session. The method helps when a session's mood is
steady and does nothing or slightly harms when it turns. Recorded as a candidate; not adopted (rule: choose year
must not lose).

## Two more gains that never lose a year (2026-10-21)

**1. Room result: count the members called yes.** A bill was called "passes" when the members' chances summed past
half the room. Counting the members whose own call is yes is better for arm B in every year — 88.25→88.36 (2024),
89.41→90.27 (2025), 92.66→92.91 (2026) — and it matches what a volunteer sees on the member cards. (Old model and arm A:
better in 4 of 6, the two losses 1 bill each.)

**2. Self-checked session booster (arm C, `booster_2027.py`).** The booster that lost on 2024 now checks itself first:
each week it learns from the session before LAST week and is scored on last week; only if that helped does it touch
this week. It switched on in 1 of 6 weeks (2024), 2 of 4 (2025), 3 of 8 (2026). Chosen on 2024 (30 trees, depth 2):

| year | member (B → C) | hardest third | room | z |
|---|---|---|---|---|
| 2024 | 85.31 → 85.32 | 67.71 → 67.73 | 88.25 → 88.25 | +2.0 |
| 2025 | 86.85 → 87.25 | 70.02 → 71.15 | 89.41 → 89.59 | +6.2 |
| 2026 | 87.09 → 87.22 | 69.58 → 69.97 | 92.66 → 93.16 | +5.7 |

Never worse in any year — the owner's condition ("if they are going to consistently improve accuracy then yes").
Frozen as an addendum before any 2027 data: `frozen/prereg_2027_addendum.json` (arm C + the count rule; the original
A/B spec is untouched and its hash is paired in). The frozen copy reproduces the research predictions exactly (0.0).
Against the old locked model on 2026: member 85.86 → 87.22, hardest third 65.90 → 69.97, room 91.45 → 93.16.

## Tested 2026-10-21, not kept

- **Train on later committee votes too** (`fv_all.py` builds 270,145 later sub/committee ballots with the same inputs;
  first-vote rows verified identical, 0 differences; `later_votes.py`). Single locked trees, later votes weighted 0.3:
  member 84.36→84.55 (2024) but 86.09→85.49 (2025) and 85.86→85.55 (2026). Later votes behave differently. Rejected.
  The linear half on the same rows: 2024 +0.2, 2025 −0.1 vs the linear model alone — rejected.
- **Adaptive weekly blend share** (pick the linear share that did best on earlier weeks): 2024 member −0.2 / −0.16. Rejected.
- **Who surprises the model this session** (`session_resid.py`: running errors per member, committee and patron, per
  side, self-checked): the self-check switched it on in 1 of 18 weeks; no change. Rejected.
- **Prune an input group** (linear model, each of 16 groups dropped in turn): no group helps when dropped in all three
  years. Largest losses when dropped: summary words (−0.6 / −1.3 / −2.2 member), venue, co-patrons, the room's members.
  Without the summary-word inputs the linear model falls 86.47→84.32 on 2026 — they stay (Standard #3 call pending).
- **Committee docket position**: DOCKET.CSV lists bills in bill-number order, not agenda order — not measurable.
- **Campaign money**: parked by the owner 2026-09-24 (money moves access, not votes) — not re-tested.
- **Position scores updated during the session** (`online_ip.py`; SVD recomputed weekly with this session's contested
  roll calls, so new members — 25% of 2024's votes, 9% of 2026's — get a position): member −0.08 / −0.03 / −0.03
  vs arm B. The trees already lean on other inputs when a member has no position. Rejected.
- **Separate linear slopes by chamber or by venue** (`levers.py linear cross`): chamber −0.33 / +0.03 / +0.42 member
  vs the plain linear model; venue −0.08 / −0.52 / +0.22. Lose on 2024. Rejected.

**Where we stand (old locked model → arm C, room by the count rule):**

| year | member | hardest third | room |
|---|---|---|---|
| 2024 | 84.36 → 85.32 | 64.86 → 67.73 | 87.38 → 88.36 |
| 2025 | 86.09 → 87.25 | 67.77 → 71.15 | 88.36 → 91.01 |
| 2026 | 85.86 → 87.22 | 65.90 → 69.97 | 91.45 → 93.16 |

## Know when we will be wrong — "can't call" (2026-10-21, `abstain.py`)

Owner: *"limiting the scenarios we guess wrong is supremely important so if there is a 30% we cant guess right we
should try to then predict that we cant predict it instead of allowing our model to knowingly fail."*

**Rule:** call a member's vote only when arm C's chance of yes is ≤ 20% or ≥ 80% (the existing "Likely" label);
otherwise show "can't call". Cutoff fixed on EARLIER years (for a 95% target), then applied unchanged:

| year | votes called | calls right | "can't call" | those would have been right |
|---|---|---|---|---|
| 2025 (cutoff from 2024) | 71.3% | 95.1% | 28.7% | 67.7% |
| 2026 (cutoff from 2024–25) | 73.1% | 95.6% | 26.9% | 64.6% |

A second model that predicts "arm C will be wrong" (confidence, disagreement between the two halves, booster shift,
drop risk, all inputs) is NO better than arm C's own confidence (2025: 67.4% called at 95.5%; 2026: 74.2% at 95.4%) —
the blend is already honest about its own doubt.

**Who is "can't call" (2026):** 46% of other-party votes vs 12% of the patron's party; 39% of subcommittee votes vs
17% committee / floor. By actual outcome: 35% unanimous yes, 25% party line, 23% mixed, 16% unanimous no. It is a
**party-block** statement: on 94% of (bill × party) blocks either every member is called or none is.

**Bill result:** calling the most confident 80% of bills → 98.2% right; 90% → 96.6%; all → 93.2%.

**Progress in these terms (votes called at ≥ 80% / ≤ 20%, and how often those calls are right):**

| year | old model | arm C |
|---|---|---|
| 2024 | 64.0% called, 94.77% right | 65.9%, 95.09% |
| 2025 | 70.4%, 94.44% | 71.0%, 95.16% |
| 2026 | 72.0%, 94.90% | 72.6%, 95.68% |

**Where the confident WRONG calls are (arm C, calls outside 20–80%):** 637 / 603 / 695 wrong calls (2024 / 2025 / 2026,
vs ~813 for the old model on 2026), on 251 / 219 / 267 bills; 42–54 bills carry 5+ each and hold 38–46% of them —
whole rooms that surprise. Largest groups: the patron's own party called yes on a bill then struck / tabled
unanimously (215 / 170 / 123), and mixed splits (both sides called yes, part voted no).

Tried to move those into "can't call", none kept:
- **Specialist model trained only on earlier years' uncertain votes** (`specialist.py`, re-scores 20–80% votes):
  calls more votes but MORE wrong calls (2026: 695 → 817; member 87.22 → 87.29, hardest third up, 2024/2025 down). Rejected.
- **Drop-risk flag** (own-party yes calls on the riskiest 10% of bills → can't call): removes 21 / 5 / 8 wrong calls vs
  10 / 7 / 4 for removing the same number of least-confident calls. Too few votes affected, not consistent. Rejected.
- **Error model** (above): no better than confidence.
- **Three-part blend** (+ depth-8 bagged trees): member −0.02 / +0.01 / +0.09 vs arm A. Not worth its cost.

## Fewer wrong calls — 2026-10-22

- **Co-sponsorship ties** (`cosponsor_ties.py`: bills the voter signed with this bill's patron / sponsors, earlier
  sessions + this session before the vote, × side): z −4.0, rejected — the member's record on this patron's bills
  (mpat) already carries it.
- **A separate cutoff per group** (side × venue, each fixed on earlier years): at the SAME number of calls it makes
  MORE wrong calls (95% target: 452 vs 448 in 2025, 501 vs 475 in 2026; 97%: 210 vs 162, 279 vs 261). The model's
  confidence is honest in every group; one cutoff is right.
- **Conclusion so far:** the ranking by confidence is already near the best possible abstention for what the model
  knows. Fewer wrong calls now needs NEW information, not a better cutoff.

**What the worst wrong calls are (2026, the 25 bills with most):** (1) Senate committee votes that split on party lines
9–6 on Democratic bills (landlord–tenant, Human Rights Act, casinos, procurement) where every Republican was called
yes; (2) House subcommittees tabling or striking Democratic bills without dissent — most with a fiscal impact
statement, several adding health-insurance coverage requirements; (3) Republican criminal-penalty bills that passed
without dissent where Democrats were called no. In each case the bill's SUBJECT decides; the model reads subject
through coarse labels and summary-word scores (its strongest input group). The largest lever left is a better reading
of what the bill does — text-derived, so it needs the owner's Standard #3 call.
- **Fine subject labels** (`fine_subjects.py`; 458 fine LIS-style subjects vs the 43 coarse ones; party and member
  support by fine subject from earlier years, × side): z 0.6, rejected (coverage 49–100% of ballots; the coarse labels
  plus the summary-word scores already carry it).
- **Calibration of confident calls is sound** (2024–2026, calls ≥ 80% yes, by chamber × side): actual yes rate meets
  or beats the predicted rate in 11 of 12 cells (exception: Senate other party 2026, 91.9% predicted vs 90.3%). Wrong
  calls are missing information, not over-confidence.

**Every structural (non-text) source tried for the wrong calls has now failed.** Left: a better reading of what each bill
does (text-derived — owner's Standard #3 call), or information not public before the vote.

## House subcommittees — the accuracy gap (2026-10-22)

Every subcommittee first vote is in the House; most full-committee first votes are in the Senate (84–89%). 11–13% of
subcommittee first votes are unanimous no (patron drops: strike / table / continue); full committees have none.

| year | subcommittee (all) | subcommittee without unanimous-no bills | full committee | sub wrong calls on unanimous-no bills |
|---|---|---|---|---|
| 2024 | 77.8% | 83.5% | 93.4% | 224 of 351 |
| 2025 | 81.1% | 86.4% | 92.4% | 175 of 327 |
| 2026 | 84.4% | 88.2% | 89.6% | 106 of 261 |

Patron drops are about half the gap. Tested, none kept:
- drop risk on subcommittee votes only (`sub_probe.py drop`): z −1.2
- the member's own record inside THIS subcommittee (`sub_probe.py memsub`): z 0.4
- a model trained on subcommittee votes only (`sub_model.py only`): member +0.03 / −0.23 / +0.17, wrong calls UP
  329→403 / 320→349 / 293→369
- subcommittee votes weighted ×3 in training (`sub_model.py weight 3`): member +0.21 / −0.10 / +0.39, wrong calls
  329→337 / 320→350 / 293→299

## The owner's strategic-calculation traces (2026-10-23, `strategy_traces.py`)

Owner: *"most bills are shot down … bc of a strategic calculation balancing polarities"* — budget amendment on the same
idea, a study announced, a near-copy by another member, the patron on the record, the general fund already packed,
election years, a big fight on one issue holding up related bills, leadership priorities filed first (HB1 = minimum wage).

| trace | measure (all before the vote) | result |
|---|---|---|
| leadership bills first | bill number ≤ 25 × majority patron × side | z −0.2. Low numbers exist only in EVEN years (odd sessions continue the numbering); 37–42 bills; already called well (2024 94.0%, 2026 86.4%) |
| a big fight holds up related bills | party-line share of this session's earlier first votes on the same subject × side / minority | z +1.3, reject |
| the general fund is packed | fiscal-impact bills already passed this session in this chamber × this bill has a cost × side; + even (budget) year | z −4.1, reject |
| election years | House, odd years × side × close seat | z −5.7 — but only 2021 and 2025 are election years in the frame; too few to learn from |
| a veto comes back | exact title of a bill vetoed in the two previous sessions | see below |
| near-copy by another member | tested before (`withdraw_probe.py`, `dup_*` inputs) | rare at first votes |
| study announced | joint "study" resolutions are not in the corpus (HB/SB only); "passed by with letter" in 2–40 bills a year | not testable yet |
| budget amendment | members' budget amendments are not ingested (a separate LIS budget system) | needs a source check first |

**A vetoed bill comes back (2026):** 78 bills carried exactly the title of a bill vetoed in 2024–25 (70 with a first
vote; 69 Democratic — the governor changed party). Half split on party lines; Republicans voted yes 32% vs 48%
predicted, called right only 63%. Earlier years have few such refiles (7 in 2024), so the weight can only be learned
inside the session: being tested as an input to the weekly refit (`veto_refile.py`).
- **Veto refile as an input to the weekly refit** (`veto_refile.py`, exact title of a bill vetoed in the two previous
  sessions, arm B with one extra input): on the refile votes 85.5→74.2% (2024, 62 votes), 84.6→85.9% (2025, 234),
  86.2→87.8% (2026, 788); overall member −0.03 / −0.02 / +0.01, wrong calls 637→638 / 604→603 / 747→743; z −0.1 /
  +0.5 / +2.1. Too small and not consistent — not adopted. The signal is real in 2026 but the linear half (30% of the
  blend) moves too little to fix it.

**Next: the bill-reading test** (Claude rates each bill's likely reception by each party from title + summary only,
no bill number / patron / year). Owner approved spending the Claude API credit ($100) and an internal-only text test
(2026-10-23). Waiting on: the `anthropic` package install OK, the owner's API key set in his terminal, the model choice
(pilot of 100 bills on Opus 5.5 and Haiku 5.5 first). Leak risk: model training data runs to mid-2026; mitigated by
stripping identifiers; only the 2027 forward test is fully clean.

### AI bill-reading test — ON HOLD until every non-AI option is used (owner 2026-10-23)

Budget: the $100 is Claude Code cloud-session credit; ~$10 regular API credit would cover a ~$1 pilot. Leak plan,
written before any run (owner: *"minimize this possible statistically as much as possible"*):
1. **Blind input.** Title + summary only — no bill number, patron, co-patrons, year, dates, committee, or votes.
2. **Ask about content, never outcome.** "How would most Democrats / Republicans on a committee view this bill?",
   not "did it pass".
3. **Memorization probe.** Separately ask the model to state each bill's outcome. If it beats what the text alone
   predicts (the locked model's own text-only score), it remembers — measure that rate, and drop the bills it
   "knows" from the evaluation.
4. **Exposure split.** Compare the gain on low-exposure bills (subcommittee votes, no news mentions in our GDELT
   counts, unanimous) with high-exposure bills (floor fights, news coverage). A gain that lives only on famous bills
   is memory, not reading.
5. **Era split.** Compare gains on 2019–2021 with 2024–2026; a much larger gain on the years nearest the model's
   training cut-off is a warning.
6. **Clean test.** Freeze the ratings recipe before the 2027 session; only 2027 is fully free of memory.

**More non-AI tests (2026-10-23), none kept:**
- **Code of Virginia chapter** a bill amends (`code_sections.py`; enacting clause of the 2025–26 introduced text, 69% of
  bills parsed; this side's and this member's earlier support on the same chapter, self-checked weekly layer on arm C):
  switched on in 0 of 4 weeks (2025) and 2 of 8 (2026); 2026 member 87.22→87.19, wrong calls 695→692. No gain.
- **Issue-adjusted ideal points** (`issue_points.py`; each member's own slope on 20 summary topics, learned on the
  locked model's residual from earlier years): z −0.9 (K = 20); K = 10 did not converge. Rejected.
- **Study announced**: the LIS subject index lists only 20 study resolutions (HJ/SJ) across 2025–26 — too rare to
  explain the drops. Not pursued.

## Negative z values — are they "reverse" signals? (2026-10-23, `rerun_no2021.py`)

Owner: *"is there anyway you can use these negative z values like maybe for reverse stats since they are strong in
the other direction"*. A negative z does NOT mean "strong the other way": the stacked test learns each signal's
direction from the earlier years, so a signal that is reliably reversed gets a negative weight and a POSITIVE z.
Negative z = the direction learned from earlier years did not hold the next year. Checking why (per-year fits):

| signal | 2021 | 2022 | 2024 | 2025 |
|---|---|---|---|---|
| co-sponsor tie with patron (other party) | −0.16 | +0.05 | +0.30 | +0.04 |
| fund load × cost (other party) | −0.18 | 0.00 | +0.03 | +0.08 |
| voter in the governor's party | −0.68 | +0.35 | +0.09 | +0.40 |

**2021 — the COVID session (House met virtually) — runs backwards on almost everything**, and every stacked test
learned its first weights from 2021. Rule fixed BEFORE re-running, applied to every rejected signal alike: learn from
2022 onward only; score 2024 + 2025 (accept at z ≥ 3); 2026 as replication.

Result: **none passes.** Pooled z (2024+2025) / 2026 replication: governor × trifecta +0.6 / +4.5 (but 2026 accuracy
down — the trifecta weight cannot be learned: the only earlier trifecta year in the frame is 2021); co-sponsor ties
−0.2 / +0.2; fund load −1.5 / +0.5; big fight +0.9 / +0.5 (2024 alone +4.6); election +0.8 / −6.0; low numbers 0.0 /
−2.3; fine subjects −0.8 / +1.9; subcommittee drop risk +2.2 / +3.5 (closest); member-in-subcommittee +1.3 / +2.6;
patron drops −2.3 / +1.2; drop model +0.7 / −4.0; **patron chairs the committee** (new, `chair_patron.py`) −1.7 /
+5.9. Removing 2021 changed directions but not the verdicts: the signals are unstable year to year, not reversed.
Also re-run without 2021: draft order −1.4 / +0.5; governor's party −0.3 / +1.7; election margin −1.1 / +1.0;
**docket load** (new, `docket_load.py`: bills on that day's docket, earlier dockets without a vote; 2025–26 only)
+0.4 / −4.0. Leaders (Rules members as co-patrons) cannot be fitted — one input nearly separates the votes and
stats.logit's Newton steps (penalty in the Hessian, not the gradient) do not settle; recorded, not forced.

## Members' budget amendments (2026-10-23, `historical_cache/budget_amendments.py`, `budget_signal.py`)

Policy check first ([[knowledge/budget_portal]]): DLAS site, no robots.txt, LIS rules applied (2025/2026 only;
personal research use per the owner's 2026-09-24 ToS decision); 4 page requests with all five guardrails (cached,
jittered 4–9 s, backoff + stop, cap 12, one-off off-session). 3,693 member requests parsed; **1,001 name a bill**
("Placeholder Amendment for HB 551", "(SB 283)"). Used only for votes on/after the day each chamber's requests became
public (House 2025-01-17 / 2026-01-22; Senate 2025-01-15 / 2026-01-21, LIS "Budget amendments available").

| year | named bills: passed / unanimous no / arm C right | not named: passed / unanimous no / arm C right |
|---|---|---|
| 2025 | 81% / 7% / 89.3% | 72% / 9% / 86.8% |
| 2026 | 75% / 11% / 86.9% | 77% / 10% / 87.3% |

Named bills are NOT dropped more often — members file budget amendments for bills they keep pushing, not instead of
them — and the model already calls them as well as the rest. Stacked (learned on 2025): 2026 z −0.8. Rejected.

**Carried-over bills** (in a 2025 first vote, first action before Nov 2024): only 6 bills — too few. Not pursued.

**Non-AI list, closed out (2026-10-23).** Owner's ideas: budget amendment ✗, study announced (20 resolutions) ✗,
near-copy ✗, patron on record (no pre-vote source), general fund ✗, election years ✗, big fight ✗, leadership
numbers ✗. Mine: co-sponsor ties ✗, fine subjects ✗, Code chapters ✗, issue-adjusted ideal points ✗, session
mood per member / committee / venue ✗, subcommittee-only models ✗, specialist ✗, error model ✗, deeper / more trees ✗,
later committee votes ✗, online position scores ✗, chair-patron ✗, docket load ✗, carried-over ✗, veto refile ✗;
and every rejected signal re-tested without 2021 ✗. What remains is the AI bill-reading test (leak plan above).

## Statistical determination — calls with a guarantee (2026-10-23, `guaranteed_calls.py`)

From the selective-prediction literature (risk–coverage, El-Yaniv & Wiener; conformal risk control / Learn-then-Test,
Angelopoulos & Bates): choose the loosest cutoff whose error among calls is ≤ 5% with 95% confidence on the
calibration years (exact binomial upper bound), then apply it unchanged.

| year (calibrated on) | rule | called | right | wrong calls |
|---|---|---|---|---|
| 2025 (2024) | "Likely" band (≥ 80% / ≤ 20%) | 71.0% | 95.2% | 603 |
| 2025 (2024) | guaranteed cutoff (|p − .5| ≥ .31) | 69.6% | 95.5% | 555 |
| 2026 (2024–25) | "Likely" band | 72.6% | 95.7% | 695 |
| 2026 (2024–25) | guaranteed cutoff (≥ .31) | 71.5% | 95.9% | 649 |

The target held in both later years; ~7% fewer wrong calls for ~1 point fewer calls.

**Per group, the 95% is an average.** Under one cutoff, calls are right: full committee own party 98–99%; full
committee other party 91–95%; subcommittee own party 92–97%; **subcommittee other party 91–92%**. A per-group
guarantee (Mondrian; Bonferroni scan) finds NO cutoff that guarantees 95% for other-party subcommittee votes or floor
votes — even the most confident calls there include patron drops and surprises. For volunteers, a call's reliability
depends on where the vote happens.

**Combination of every weak signal** (`mega_stack.py`, 14 signal families, no-2021 rule): one ridge layer — 2024
−0.03, 2025 −0.45 member, pooled z −3.5; reject (the ridge-100 fit did not converge). Residual trees over all signals
+ member inputs: see below.

Literature consulted: [Gerrish & Blei — issue-adjusted ideal points](https://www.cs.columbia.edu/~blei/papers/GerrishBlei2011.pdf);
[Kraft et al. — embedding model for roll calls](https://mirror.aclweb.org/emnlp2016/program/979.html);
[Eidelman et al. 2018 — state floor action, text + context +18%](https://ar5iv.labs.arxiv.org/html/1806.05284);
[Selective conformal risk control](https://arxiv.org/pdf/2512.12844).
Residual trees over all signals + member inputs (60 rounds, depth 3): member 84.36→84.08 / 86.09→86.03 /
85.86→86.81, wrong calls 658→797 / 687→737 / 814→1,029 (it calls more and errs more); pooled z −1.8, 2026 +5.9.
Rejected — combining the weak signals adds noise, not signal, on the years that choose.

## External signals — round 1 (2026-10-24)

Owner: *"weve gone real deep on the internals but not the externals ... 30 tests just isnt enough to call it quits on."*

**Member background** (`historical_cache/member_bio.py` via the Wikipedia API, ~25 requests; `member_bio_signal.py`):
224 members elected 2019–2025, 219 with a page; lawyers 36, military service 30, women 31, birth year 161; only 67
pages list an occupation field (health 5, farmer 5, educator 8 — too few). 93–99% of 2020–2026 votes matched.
Inputs: lawyer × Courts of Justice room, lawyer, military, woman, age, educator / health / farmer × their committee,
each × side. No-2021 rule: 2024 z −4.0, 2025 +1.5 → pooled −2.5; 2026 −1.1. Rejected.

**District make-up, extended** (`historical_cache/districts_ext.py`): both maps (ACS 2021 for sessions 2020–23,
ACS 2023 for 2024+) and new measures (industry: farming/mining, manufacturing, public administration; armed forces,
veterans, foreign born, unemployed, transit, renters; land area for density). Variable codes checked identical in
2021 and 2023. **Blocked on a key:** the Census API now redirects keyless requests to missing_key.html (2026-10-24);
the script reads CENSUS_API_KEY from the owner's own terminal (never stored).

**Geography** (`geo_signal.py`; Census Gazetteer national files, Virginia rows; 4 downloads, public domain, no key):
district interior points + land area, previous maps for 2020–23 and 2022 maps for 2024+; members placed by the
election that seated them (92–98% of votes; patron distance 81–93%). Inputs: within 40 km of the patron, log
distance, log land area (rural), × side. Weights are steady — other-party members near the patron lean yes (+0.35 /
+0.31 / +0.06) — but the gain is small: pooled z +0.5, 2026 −0.2. Rejected (the model already places members through
ideal points and district make-up).

**District make-up × bill subject** (`district_subject.py`; 6 district measures × the 10 commonest subject groups ×
side, 2024+): 2025 z −1.0, 2026 −3.3. Rejected. (`rerun_no2021.py` gained a properly penalised fallback fit, used
only when stats.logit fails — marked in the output.)

**Not usable:** Census Reporter's data API (robots.txt `Disallow: /`); the Census API without the owner's key.

**District make-up, extended — fetched and tested (2026-10-24).** Owner saved the Census key in ~/.zshrc; the fetch ran
in the owner's terminal tab (8 Census requests; key never seen). 17 measures on both maps (ACS 2021 → sessions
2020–23, ACS 2023 → 2024+), 92–98% of votes placed. (a) As a stacked layer × side (`district_ext_signal.py`): 2024 z
−4.6, 2025 +1.3, pooled −3.7; 2026 −2.9 — rejected. (b) Inside the linear half of arm A (`district_ext_model.py`):
member +0.02 / +0.06 / 0.00, wrong calls +3 / +1 / −1 — no gain.
(c) **The voter's district resembles the patron's** (`district_pair.py pair_mode`; similarity over the 17 measures,
× side): on the locked model **passes** — 2024 z +5.1, 2025 +1.1, pooled +3.2; member +0.11 / +0.08, hardest third
+0.33 / +0.22 — but 2026 replication z −0.3. On top of arm C (layer learned on earlier years' arm C predictions):
member +0.01 / +0.19, but WRONG CALLS UP 670→686 (2025) and 742→783 (2026), z +0.6 / −1.7. Not adopted — the owner's
first rule is fewer wrong calls. (d) District × subject, all years: pooled z −6.3, rejected.

## Combinations — what the model misses in a cell (2026-10-24, `combo_cells.py`)

Owner: *"if the district is all rich white people and its in northern virginia do we think they are for or against
data centers ... brain storm deeper then your singular tests and run in parallel."*
Method (residual target encoding, year-ahead): district TYPES (k-means on the 17 measures, both maps pooled; 6 or 10
types) and REGIONS (k-means on district location, 7); for a cell — e.g. district type × subject × side — the locked
model's average miss (actual − predicted) in that cell from EARLIER years only (2021 excluded), shrunk toward 0;
that miss is the input. Tested with the no-2021 frame. NOTE: 2024 learns from 2022 only, whose inputs are empty
(nothing before 2022 in the tables), so the 2024 line never moves — the real tests are 2025 and 2026.

| cell | 2025 z | 2026 z |
|---|---|---|
| district type (6) × subject × side | +0.5 | +1.0 |
| district type (10) × subject × side | +0.1 | +1.3 |
| region × subject × side | +0.3 | +1.3 |
| district type × summary topic × side | −3.9 | +2.4 |
| district type × committee × side | −0.7 | −1.2 |
| voter's region × patron's region × subject × side | +1.2 | +1.3 |
| district type × voter party × patron party × subject | +1.1 | +1.2 |
| **member × subject × side** (shrink 30 / 10 / 100) | **+1.7 / +2.2 / +1.0** | **+2.4 / +2.6 / +2.2** |
| member × patron | +1.6 | +1.7 |
| member × committee × side | +0.1 | +1.8 |
| **patron × subject × side** | **+2.7** | +0.9 |
| **committee × subject × side** | **+2.0** | +0.6 |
| patron × committee × side | +1.8 | +1.5 |
| all positive families together (shrink 30 / 10) | −0.2 / +0.7 | +1.5 / +2.1 |

**Reading:** the identity cells (member / patron / committee × subject) point the same way in BOTH years — real
signal, but each is short of z 3 with only 2022 + 2024 as history. Next: 2023 rebuilt from LIS legacy files
(`build_2023.py`) as one more history and learning year (FIT2023=1), which also gives 2024 a real test.

**With 2023 rebuilt** (`build_2023.py`: LIS legacy 2023, 17,255 ballots on 1,569 bills, locked model 86.5%) as a further
history + learning year (FIT2023=1): the identity families together (member / patron / committee × subject, member ×
patron, member × committee, patron × committee; shrink 10) lift accuracy in ALL three years — member +0.14 / +0.26 /
+0.18, hardest third +0.47 / +0.77 / +0.54 (2024 / 2025 / 2026), z +0.3 / +2.9 / +2.0, pooled 2.3. **But on top of
arm C** they add nothing and raise wrong calls (670→733, 742→784); member × subject alone +0.05 / +0.03 member, wrong
calls 670→684 / 742→744; patron × subject +0.04 / +0.13, 670→670 / 742→757. Arm C's weekly session learning already
holds most of it. Not adopted.

**Third model family — "who with whom on what"** (`cell_rates.py`; shrunk yes-rates in 9 identity cells from strictly
earlier days, ridge logistic): alone 74.4 / 77.0 / 77.3%; blended into arm A it lowers accuracy (2024 −0.04 to −0.6) and
log loss (z −2.5 to −10); fewer wrong calls only because it makes fewer confident calls. Rejected.

**Adaptive "can't call" cutoff** (`adaptive_calls.py`, adaptive conformal inference, daily updates toward ≤4.5% wrong):
at the SAME number of calls it makes MORE wrong calls than the fixed cutoff in every setting (e.g. 2025: 596 vs 546).
**Block-coherence rule** (also require the party block's average to be confident): 593 / 557 / 655 vs 584 / 555 / 649
wrong at equal calls. Both rejected — the member's own confidence is the best abstention signal we have.

## Is a third model the best use of time? Theory check (2026-10-24)

Owner: *"spend time thinking and researching studies our history etc staticians and their theories as well as
political ones to decide if the 3rd model is the best of your time."*

1. **Ensemble theory** (Krogh–Vedelsby ambiguity decomposition and its classification analogues): a blend beats its
   members only when a member is BOTH reasonably accurate AND makes different mistakes; correlated errors cancel the
   benefit. Our record fits exactly: the linear half (84% alone, a different functional form) helped; the "who with
   whom" cell-rate model (74–77%, built from the same identity information the trees already read) did not. **Another
   family on the same inputs is not worth the time; a third family must bring NEW information.**
2. **Roll-call ceilings**: DW-NOMINATE classifies ~83–85% of US House votes (secondary source; Poole & Rosenthal);
   Snyder & Groseclose show classification understates hidden party pressure. Our 87% (first votes, committees
   included) is at or above the usual ceiling for vote-history methods.
3. **Political science — negative agenda control** (Cox & McCubbins; state tests by Cox, Kousser & McCubbins; Shor &
   Kistner): majority parties mostly act by BLOCKING bills before a vote (not heard, struck, tabled); interest-group
   pressure can sometimes override the gate (Kistner & Shor). That is our hardest residual — patron drops and
   party-line kills decided in private — and it matches our testimony-lineup result (helped 2022–25 bill fate, not 2026).
4. **Decision:** stop building models on the same inputs. The largest untried lever is new information about the bill
   itself — text-based models gain most in the literature (Gerrish & Blei; Kraft et al.; Eidelman et al. 2018 for
   state floor action) — i.e. the AI bill-reading pilot, with the written leak controls.

Sources: [Kistner & Shor slides](https://uh.edu/hobby/cpp/events/eitm/papers/slides-for-cantu-conference-kistner.pdf),
[Shor & Kistner](https://priceschool.usc.edu/wp-content/uploads/2008/08/Shor-and-Kistner.pdf),
[Stanford: institutional foundations of majority party power](https://purl.stanford.edu/dy798kq4055),
[Cox, Kousser & McCubbins notes](https://adambrown.info/p/notes/cox_kousser_and_mccubbins_party_power_or_preferences_quasi_experimental_evidence_from_american_state_legislatures),
[Partition decomposition for roll calls](https://arxiv.org/pdf/1108.2805), [Bowdoin DW-NOMINATE report](https://www.bowdoin.edu/student-fellowships/recent-winners/_pdf/peterson-lierin.pdf),
[Diversity and degrees of freedom in regression ensembles](https://arxiv.org/pdf/1803.00314), [Ensemble diversity & bias-variance](https://metricgate.com/blogs/ensemble-diversity-bias-variance/).

**AI pilot prepared, not run** (`llm_pilot.py build`): 100 bills from 2024 (50 hardest-third, 50 random; subcommittee
votes), blinded title + summary (checked: 0 of 200 model-visible texts contain a bill number or year), a content
rating request + a separate memorization probe per bill, structured JSON output, Batch API. Estimate (not measured):
~64k input / ~60k output tokens → Opus 5.5 ≈ $0.73, Haiku 5.5 ≈ $0.02 with Batch. `submit` deliberately not wired
until the owner OKs the `anthropic` install, the API key in his terminal, and the model.

**Refit cadence for arm B** (`online_relinear.py`, ONLINE_STEP_DAYS): weekly (adopted) 85.31 / 86.85 / 87.09 member;
every 3 days 85.29 / 86.89 / 87.02; daily 85.28 / 86.83 / 87.08 (2024 / 2025 / 2026). Equal within noise; weekly
stays (best on the choose year).

## AI bill-reading pilot — RUN (2026-10-24, `llm_pilot.py`, `llm_pilot_eval.py`)

Owner: *"lets run the 1 dollar test first comparing haiku and opus, or even sonnet ... dont use more then 5 dollars."*
No API key was available (the owner's $10 is subscription extra usage, not API credit), so the ratings were made by
Claude Code helper agents on the chosen model (subscription usage; ~82k tokens per model run, ~330k in all), each
allowed to read only the blinded bill file (2 tool calls each). 100 bills from 2024 (choose year), neutral ids
B001–B100, no bill number / year / name in any text (checked 0 of 100). Evaluation on those bills' 2024 first votes
(812 member votes; party blocks), the rating's weight fit leave-one-bill-out:

| model | rank corr. with party's actual yes share (arm A: +0.51) | party majority right (arm A 74.0%) | member votes right (arm A 77.2%) | wrong calls at arm A's 344 calls (arm A 23) |
|---|---|---|---|---|
| Haiku 5.5 | +0.24 | 73.0% | 77.1% | — |
| Sonnet 5.5 | +0.32 | 73.0% | 76.4% | — |
| **Opus 5.5** | **+0.38** | **77.0%** | **80.0%** | **22** |

Opus: +2.8 points on member votes on these mostly hardest-third bills, log loss 0.521 → 0.500 at the party-block
level, and no more wrong calls at the same number of calls (22 vs 23; hardest bills 18 vs 20). **Memorization probe
(separate Opus run): recognized 0 of 100 bills** — a self-report, so weak evidence; the exposure split (famous vs
obscure bills) and a year-ahead fit are the next checks. Haiku and Sonnet add nothing.
**Status: promising pilot on 100 bills, NOT established.** Text-derived — internal only (Standard #3).

**AI reading — year-ahead check (2026-10-24, `llm_ahead.py`).** Opus rated 150 + 150 "can't call"-heavy bills from 2025 /
2026 (same blinding, 0 numbers / years visible); memory probe: 4 of 300 recognized (B176, B282, B283, B391 — excluded).
Protocol notes: one probe agent ran one shell command (printed a template; no reads / network) against instructions;
rating agents used 3 tool calls (a second read of the long file). Weights learned on the 2024 ratings, on top of ARM C:
- Both party ratings: 2025 member 74.6→74.2%, 2026 73.0→71.2%; calls at equal wrong calls +8 / +14 votes. Fails.
- Why: the Democratic weight flips sign by year (+0.92 / −0.88 / −0.48 within 2024 / 2025 / 2026); the Republican weight is
  stable (+1.25 / +1.13 / +0.87).
- **Republican rating only** (2024 weight +1.25): 2025 member 74.5→76.7%, Republican votes 69.8→75.9%, calls at equal
  wrong calls 553→586 (38→41%); 2026 72.8→72.5%, Republican votes 66.3→65.1%, 560→570. Helps 2025, not 2026 (first
  trifecta year: the 2024 weight overshoots — within 2026 it is +0.87).
**Verdict: a real but unstable signal; not adopted.** A stable weight needs ratings for many more bills per year
(~5,000 bills for 2024–26 ≈ $37 in Opus batch API by the earlier estimate — over the owner's $5 cap; or ~50 helper-agent
runs on the subscription). Text-derived: internal only.

**Hard third only (owner 2026-10-25: "exclusively targeting the last 1/3 ... llms should be able to predict outcomes with
a accuracy over 80% in that final 1/3").** On "can't call" votes of the rated bills, arm C is right 64.5% (2025, 891
votes) / 61.2% (2026, 950); with Opus's Republican rating 68.0% / 60.5%. Next: give the model the context a lobbyist
uses (patron party and majority status, committee, governor's party, this committee's votes on similar bills this
session — all public before the vote), ask it directly how each party block votes, score on can't-call votes only,
year-ahead, same memory probe; 100 can't-call blocks from 2025 first — after the owner's 5-hour usage window resets.

**Hard third, member-centric (2026-10-25, owner: "idk that its abt the lobbyist as much as the rep").**
`tools/calibration/llm_member.py` builds one blinded packet per bill (296 bills, 1,841 "can't call" votes, the same
pilot bills): the bill, the room, and one anonymous card per unsure member (party, district, record, and the member's
OWN votes on the 6 most similar earlier bills, with the whole-room and own-party tallies; all strictly before the vote).
- **Opus trial, 30 bills of 2025 (180 votes):** arm C 60.6%, AI alone 55.6%, AI + arm C 65.0% (too few votes to trust).
  The AI's misses come in whole blocks: rooms that killed a bill unanimously, which it read as yes.
- **Where the hard third really is (`can't call` votes, all bills):** knowing only the member's PARTY-BLOCK majority on
  the bill would be right 95.5% (2025) / 94.3% (2026). Knowing the room majority: 69.8% / 70.8%. So the hard third is a
  question about how each party block in the room votes on the bill (two answers per bill), not about the member.
  14–16% of these votes are on rooms that voted unanimously NO; arm C is right on 46% of them.
- **Non-AI bar, `knn_own.py`:** own votes on similar bills (share, departure from party, share of those bills the room
  killed) on top of arm C. Fit 2025 → test 2026: 62.4 → 64.8%. Fit 2026 → test 2025: 67.8 → 66.3%. Killed-share alone:
  +2.5 / −0.5 points. **Unstable; not adopted.**
Next: ask at the block level (does each party in the room vote mostly yes?) with the room's own history on similar bills,
and use the research survey (`docs/research/legislator_vote_prediction_survey.md`) to set the criteria.

**Block-level AI trial (2026-10-25, `llm_block.py`, Opus helper agents, instructions `.cache/llm_block/instructions_v1.md`).**
Packet = blinded bill + room facts + THIS room's tallies on the 8 most similar earlier bills + the 4 most similar bills
voted earlier this session + the room's kill count so far; asked: chance each party block mostly votes yes.
2025, 59 clean bills (B139 dropped: its own result was visible in a batch-mate's packet), 344 can't-call votes:
arm C 64.8%, AI alone 60.8%, **equal average of AI and arm C 69.2% (+4.4; 90% range −1.1 to +10.4)**. Same pattern as the
member-level trial (+4.4 on 180 votes). The AI alone is worse; its errors differ from the model's, so the average helps.
**FROZEN before the 2026 run (written before any 2026 answer exists):** instructions v1 unchanged; member chance =
equal log-odds average of arm C and the AI's block chance; scored on every 2026 can't-call vote of the 147 pilot bills;
recognized bills dropped; batches built so that no packet shows the tally of a batch-mate. Pass = gain > 0 with the
90% bill-resampled range above 0, and no more wrong calls at arm C's own number of calls.
**2026 RESULT (frozen rule, 147 bills, 950 can't-call votes, 0 recognized):** arm C 61.2%, AI block chance alone 65.1%,
equal average 63.4% — gain +2.2, 90% range −2.4 to +6.8 (21.6% of resamples no gain). **FAIL; not adopted.**
New calls made by the average: 36 of 950 (35 right); 2025 15 (12 right). By the room's real result (2026): unanimous NO
304 votes — arm C 38%, AI 48%, average 46%; unanimous YES 186 — 75 / 69 / 66%; split 460 — 70 / 75 / 74%.
Reading: the AI, given the room's history, reads split votes and kills a little better than the model, but it is not
stable across years, and unanimous kills stay below 50% for every method. Research survey
([[research/legislator_vote_prediction_survey]], ~70 sources) finds no published method near 80% on a hard subset; its
top ideas (outcome-type first, patron kill history, even-year continuation, by-request, co-patron ties, election margins,
chair cues, own-vote retrieval) were already tested here and add nothing or are unstable.

**Coverage test (2026-10-25, `llm_cover.py`) — FROZEN before the last 89 2025 answers arrived.** Why: ranked by
confidence, arm C + AI got the top 100 of 950 hard 2026 votes 92% right (arm C's own ranking: 70%), weight taken from
2025; reverse direction 2026 → 2025 newly calls 68 of 344 at 85.3%. 2025 had too few votes (344) to set a guaranteed
cutoff, so the AI rates the other 89 pilot bills of 2025. Rule: weight AND cutoff (95% Clopper-Pearson bound, ≥81 right
in 100 — the same rule as all calls) learned on 2025 only; applied unchanged to 2026; PASS if calls > 0 and ≥81% right.
**COVERAGE RESULT (frozen rule):** 2025 now 148 bills / 884 can't-call votes; weight +0.44 (2026 alone would pick
+0.46 — stable). **No cutoff on 2025 passes the 81-in-100 guarantee → 0 calls on 2026 → FAIL.** Diagnosis only (not a
new verdict): ranked by confidence, arm C + AI beats arm C's own ranking in both years — 2025 top 50/100/150 82/80/77%
(arm C 72/71/69%), 2026 98/90/82% (74/70/71%). The signal is consistent; 884 votes are too few to certify it.
Open: rate ALL 1,147 can't-call bills of 2025 (~115 helper-agent batches ≈ 1.6 five-hour windows, no money) so the
cutoff can be certified on 2025, then re-score 2026 unchanged. Packet defect to fix first: some Senate committee votes
are labelled "floor" (venue flags), noticed by three agents; it does not change the frozen 2026 answers.
Also rejected today (non-AI, year-ahead both ways): summary set-phrases (commission recommendation and "identical to"
bills are never killed unanimously but are rare; overall +0.9 / −1.0), this-session patron / room kill traces
(−0.5 / −1.6).

**2026-10-26 round.**
- **Pooled coverage arm (`llm_pool.py`):** weight and cutoff learned on 2025 + 2026 rated bills (1,834 can't-call
  votes): weight +0.45, cutoff |p−.5| ≥ .34 passes the 81-in-100 guarantee → 179 new calls (9.8% of hard votes), 87.2%
  right (2025 81%, 2026 93%). **Frozen for 2027** in `frozen/prereg_2027_ai.json` (instructions, packet builder and
  scorer pinned by sha256). Not a gain on any scored year yet — the 2027 session is the test.
- **Where the AI fails (`llm_block_errors.py`, 425 blocks):** the patron's own party when it holds the majority voted
  yes on only 38% of these hard bills (84 blocks) — the majority killing its own members' bills, mostly unanimously;
  AI and arm C both ~50% there. Unanimous kills are 31% of blocks; AI 52% right on them.
- **Packets v2 (`llm_block2.py`):** + committee / subcommittee names, the bill's own record before the vote, session
  type, Virginia-practice notes. 2025, 129 clean bills: block accuracy 61.1% (v1) → 61.7% (v2); answers correlate 0.91
  with v1; "killed" chance 36 on killed bills vs 30 otherwise. **No better; not run on 2026.**
- **Same-meeting twins (`sameday_twin.py`):** near-identical bill heard in the same room the same day — no signal
  (year-ahead 62.4 → 62.4 / 67.8 → 67.6). Rejected.
- **Data bug found:** ~940 first votes 2019–2026 (mostly Senate committees, 10–14 ballots, "Passed by indefinitely in
  …") are labelled "floor" in the roll-call venue. Fixed in v2 packets only; a separate task will fix the source and
  re-measure the member model.
- **Leak control:** an agent reading two pack files can see a batch-mate's tally across files — 19 2025 bills dropped
  from the v1/v2 comparison for that reason. Packing rule: keep linked bills apart per AGENT, not per file.
- **Next (running):** AI as a measuring tool — a fixed checklist (party support, consensus, set-aside risk, cost,
  mandates, study, crime, technical, local, topic) for all 3,613 first-voted 2025–26 bills from the official
  introduced summaries (LIS `Summaries.csv`, now cached), learned on one year and scored on the other (`rubric_eval.py`).

**AI as a measuring tool — checklist (2026-10-26, `llm_rubric.py` + `rubric_eval.py`). FIRST AI RESULT THAT HOLDS
BOTH WAYS.** Opus helper agents read only the blinded official summary as introduced (LIS `Summaries.csv`, cached) for
every first-voted 2025–26 bill and fill a fixed checklist (party support D / R, consensus, set-aside risk, cost,
program, business / locality / insurance mandate, study, crime, technical, local, topic). A ridge logistic on top of
arm C learns, from ONE year, how each item × voter party / same-party-as-patron / majority moves the vote; scored on
the OTHER year. Left out: 8 bills the AI recognized; 6 summaries that name the bill that absorbed them (LIS appends
"incorporated into …" to some introduced summaries — found by an agent; `leak_ids.json`).
| interim, 2,516 of 3,613 bills rated (~70% of votes) | all votes | hard third | calls at equal wrong calls |
|---|---|---|---|
| learn 2025 → score 2026 | 87.22 → **88.42%** | 65.4 → **69.3%** | 15,850 → **16,460** |
| learn 2026 → score 2025 | 87.25 → **88.22%** | 68.4 → **71.6%** | 12,224 → **12,648** |
Log loss 0.288 → 0.272 / 0.299 → 0.282. **Control:** checklists shuffled between bills → −0.11 to +0.02 (no gain), so
the gain is the content. Stable carriers: own-party support (+0.80 / +0.68), consensus (+0.58 / +0.73), consensus ×
same-party (−0.41 / −0.38), own support × majority (+0.36 / +0.36). **Memory check (partial):** gain on bills with no
co-patrons (low profile) +1.4 / +1.5 both years; larger outside House subcommittees (+2.0 to +2.6 vs +0.5 to +0.7) —
content or memory, not separable here; the 2027 session is the clean test. Remaining 1,000 bills to rate next window.
Text-derived: INTERNAL ONLY until the owner's Standard #3 call.

**"Pulled off the block" (Gemini suggestion; `block_vote.py`, 2026-10-27). REJECTED.** LIS records "Block Vote" only
on Senate FLOOR actions; no committee action carries it and committee report votes never share a vote id across
bills, so the committee version Gemini described is not observable in any source we may use. The floor version is
forward-looking (second reading comes on an earlier day than the passage roll call) and was tested on 2025–26:
- LIS labels Senate second-reading blocks only from 2026 (2025: none) — a recording change, so it cannot be learned
  year-ahead.
- 2026: bills read in the block were contested MORE often (241 of 481) than bills read on their own (65 of 246) —
  second reading is a formality the Senate blocks wholesale.
- Committee report unanimous: 14 of 246 (block) vs 8 of 180 (own) contested; report had a No: 227 of 235 vs 54 of 57.
  The committee tally already carries the signal; block status adds nothing.

**Venue label fixed — and the member-model headline drops (`venue_fix.py`, 2026-10-27; case law #146).** The roll-call
venue was read from the motion text, so 2,086 Senate committee kill motions ("Passed by indefinitely in …",
"Continued to … in …") were labelled "floor" — a label that told the model a kill motion had been made. Ballot count
instead (committee ≤ 22, floor ≥ 30, none between), same reference model (depth 6, lr .03, 260 rounds), year-ahead:
| | old (leaky) venue | fixed venue |
|---|---|---|
| 2025 (learn 2019–24) | 86.09% · hard third 67.77% · 12,133 calls, 642 wrong | **81.25% · 64.38% · 9,002 calls, 657 wrong** |
| 2026 (learn 2019–25) | 85.86% · 65.90% · 15,712 calls, 771 wrong | **83.41% · 64.02% · 14,000 calls, 857 wrong** |
First votes labelled "floor" by the old rule: 1,895 ballots in 2025 (29% for the bill) and 2,234 in 2026 (20%), vs
90% / 86% on "committee". **Every member-model figure in this file before this entry used the leaky venue**, including
arms A/B/C, the hard-third work and the AI checklist gain (measured on top of arm C). The frozen 2027 arms use it too —
their 2027 scores will be inflated the same way, because 2027 rows are built after the fact from the same motion text.
War Room replay redone with the fixed venue (reference model, learned 2019–2025; Senate Education and Health, 2–8 Feb
2026, 48 bills): 14 bills short of a majority in called yes — 6 of them failed; 34 with enough — 1 failed. The leaky
version had put exactly the 6 failures at the top; now they sit inside the top 14 (the top two, SB 721 and SB 740,
passed). Mockup v9 corrected.

**Honest baseline + addendum (2026-10-27, owner: "if you think its best then your clear to proceed").** Arm C's frozen
code (`booster_2027.predict_boosted`) on the fixed-venue rows (`venue_fix.py armc`), year-ahead; "can't call" = |p−.5| < .31:
| | member | can't-call third | calls (wrong) |
|---|---|---|---|
| 2025 (learn 2019–24) | **83.68%** | 69.18% | 10,295 (628) |
| 2026 (learn 2019–25) | **84.91%** | 67.35% | 14,096 (710) |
AI checklist on top of the honest arm C (`venue_fix.py rubric`, 2,695 checklists, ~74% of votes), learned on one year:
| | all votes | hard third | calls at equal wrong |
|---|---|---|---|
| learn 2025 → score 2026 | 84.91 → **86.03%** | 67.35 → **70.39%** | 14,096 → **15,035** |
| learn 2026 → score 2025 | 83.68 → **85.07%** | 69.18 → **72.57%** | 10,295 → **11,247** |
The checklist gain holds (slightly larger) once the leak is gone. **Frozen:** `frozen/prereg_2027_venuefix.json`
(sha256 0467645…), pairing with the three earlier 2027 files; arms C_fixed and reference_fixed on VENUE_FIX rows. The
original arms stay as registered and will be reported with the leak caveat.
