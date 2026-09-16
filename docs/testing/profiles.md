---
tags: [testing, calibration, war-room, committee, members, profile]
updated: 2026-09-16
status: active
---

# The two War Room panels — what goes on them

**Owner, 2026-09-16:** *"we have info on the committee and info on the committee members. but not much on
either. find more for both of those. you know what doesnt work so find what does."*

What does not work is settled: ten member-level "who can be moved" hypotheses are null or collapse
([[testing/member_signals]], [[testing/money_and_vulnerability]]). 86% of subcommittee kills have nobody
crossing party lines, so there is little persuasion in this data to detect. **Everything on this page is
therefore descriptive** — a property of a room or a person that a lobbyist reads, never a prediction that
someone can be moved.

`python3 tools/calibration/profiles.py`

## The room panel — four dimensions, all with real spread

24 committees with ≥120 bills as the first stop.

| | range | median | what it tells a lobbyist |
|---|---|---|---|
| **partisan gap** (majority-patron pass rate minus minority-patron) | **+4 to +65 pts** | +34 | whether this room is survivable for your side at all |
| **dies on a record** (share of deaths with a recorded fatal vote) | **42% to 100%** | 75% | whether you are fighting a vote or a clock |
| **rewrite rate** (share of reported bills carrying a substitute or amendment) | **35% to 71%** | 55% | whether to bring finished text or expect a rewrite |
| **unanimity** (share of roll calls with no dissent) | **34% to 79%** | 61% | whether this room argues or rubber-stamps |

The partisan gap is the headline. **S07 treats minority patrons within 4 points of majority ones. H18 is
65 points apart** (79% vs 14%). Those two rooms are different countries, and nothing published anywhere
says so.

| room | bills | passes | maj | min | gap | dies on a record | rewrites | unanimous |
|---|---|---|---|---|---|---|---|---|
| H18 | 185 | 51% | 79% | 14% | **+65** | 86% | 43% | 34% |
| H15 | 235 | 64% | 88% | 25% | +63 | 80% | 51% | 34% |
| H10 | 268 | 46% | 65% | 19% | +46 | 75% | 53% | 48% |
| H02 | 220 | 54% | 66% | 28% | +39 | **95%** | 47% | **79%** |
| S02 | 214 | 67% | 73% | 53% | +20 | 77% | **71%** | 54% |
| S11 | 169 | 75% | 81% | 68% | +13 | 42% | 48% | 66% |
| S07 | 121 | 67% | 70% | 66% | **+4** | 70% | 36% | 56% |

## A verb-form bug found writing this — audit point #1

The fatal-action matcher said **"passing by indefinitely"**. Virginia writes **"passed by indefinitely"** —
639 Senate actions. The consequence: **every Senate room reported 0% of its kills happening on a recorded
vote**, which read as a fact about the Senate and was a fact about my tuple. Senate also uses "continued
to" (488) and "failed to report" (98), neither matched.

Corrected, the chamber medians converge — House 75%, Senate 70%. The pre-push audit's point #1 is
literally *"For every pattern/keyword list changed, verify ALL conjugations."*

## The member panel — three traits, each validated before being shown

171 legislators with ≥40 bills and a difficulty benchmark.

### Carrier lift — the one that matters for choosing who carries your bill

Their actual pass rate minus what their **own** bills should have scored, where "should" is how other
patrons' bills in the same session × subject × chamber fared.

- split-half **r = 0.75** (n=141) · across eras **r = 0.48** (n=76) · **6.1× the binomial noise floor**
- **drift check: r = −0.01** against the member's last active year — so it is not era, it is the person.
  [[testing/calibration_corrections]] Correction 1 caught base-rate drift masquerading as skill once; this
  is the guard against repeating it.

**Range −42 to +31 points; median +1.** Ben Chafin +31, Barry Knight +28, Katrina Callsen +26 at one end;
Thomas Garrett −42, Eric Zehr −39, Amanda Chase −36 at the other. A 73-point spread in what the same bill
is worth depending on whose name is on it.

### Bipartisan filing — split-half r = 0.78, across eras r = 0.48

Share of their own co-patroned bills carrying a cross-party name. **0% to 100%, median 30%.** Morrissey
100%, Coyner 78%, Stanley 77%; several Democrats at 0–4%.

### Specialisation — split-half r = 0.60, across eras r = 0.31

The share of their filing sitting in one subject. **Median 18%**, but Joe McNamara is 55% Taxation and
Terry Austin 43% Motor Vehicles. Tells a lobbyist who already owns their subject.

## Limits

1. All three member traits describe **filing and outcomes**, not persuadability. Nothing here says a member
   will vote your way.
2. Carrier lift is measured against our own coarse subject labels ([[testing/subject_labels]]).
3. Room figures cover 2023–2026, the span of the committee-vote corpus; the partisan gap needs ≥20 bills
   per side and rooms below that show a dash rather than a guess.
4. The partisan gap is a property of the bills a room receives as well as of the room. [[testing/venue_effect]]
   and [[testing/venue_shopping]] hold content constant and still find room differences, which is the
   corroboration — but the gap itself is not content-controlled.

## Related

[[testing/rooms]] · [[testing/venue_shopping]] · [[testing/committee_seat]] · [[testing/member_signals]] ·
[[testing/carrier_effect]] · [[index]] · [[log]]
