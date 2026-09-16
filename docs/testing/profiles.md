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
| **partisan gap** (majority-patron pass rate minus minority-patron) | **+12 to +65 pts** | +34 | whether this room is survivable for your side at all |
| **dies on a record** (share of deaths with a recorded fatal vote) | **42% to 100%** | 75% | whether you are fighting a vote or a clock |
| ~~rewrite rate~~ | ~~35% to 71%~~ | ~~55%~~ | **RETRACTED — does not persist across eras (r = 0.25). See [[testing/panel_audit]].** |
| **unanimity** (share of roll calls with no dissent) | **34% to 79%** | 61% | whether this room argues or rubber-stamps |

The partisan gap is the headline. **S07 is 12 points apart; H18 is 65** (79% vs 14%). Those two rooms are
different countries, and nothing published anywhere says so.

> **Corrected 2026-09-16.** The first version of this table read S07 at +4 and listed `S4V`/`S5V` as
> separate rooms. They are not rooms — **in 2026 the Senate began writing vote ids as `S1V…` where earlier
> sessions wrote `S01…`**, and keying on `vote_id[:3]` split every Senate committee in two: the numeric
> room lost its 2026 bills while the V-form appeared as a brand-new room with no history. Verified by
> roster overlap (S5V/S05 **100%**, S8V/S08 94%, S1V/S01 88%). `CV.room_code()` now normalises it. Same
> class as the five padding bugs in [[failures/assumptions_audit]]: two spellings of one structural
> identifier, joining to nothing, failing silently.

| room | bills | passes | maj | min | gap | dies on a record | rewrites | unanimous |
|---|---|---|---|---|---|---|---|---|
| H18 | 185 | 51% | 79% | 14% | **+65** | 86% | 43% | 34% |
| H15 | 235 | 64% | 88% | 25% | +63 | 80% | 51% | 34% |
| S08 | 125 | 54% | 75% | 20% | +55 | 76% | 46% | 33% |
| H10 | 268 | 46% | 65% | 19% | +46 | 75% | 53% | 48% |
| H02 | 220 | 54% | 66% | 28% | +39 | **95%** | 47% | **79%** |
| S05 | 368 | 54% | 69% | 31% | +38 | 94% | 56% | 64% |
| S11 | 169 | 75% | 81% | 68% | +13 | 42% | 48% | 66% |
| S07 | 163 | 69% | 75% | 63% | **+12** | 72% | 35% | 55% |

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

## Backtested — and one dimension removed

[[testing/panel_audit]] re-measured every number on held-out years. **Dies-on-a-record (r = 0.79) and
unanimity (r = 0.77) hold. The partisan gap holds directionally (r = 0.54) but moves a median of 11 points
between eras — recompute it per session, never quote it from history. The rewrite rate does NOT hold
(r = 0.25) and is retracted.**

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
