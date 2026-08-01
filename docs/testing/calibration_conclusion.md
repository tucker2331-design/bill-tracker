---
tags: [testing, calibration, conclusion, war-room, product]
updated: 2026-08-01
status: active
---

# What the calibration actually found

47 stats tested. The headline for most of the exercise was *"almost nothing predicts."* **That was wrong,
and it was wrong for a specific, correctable reason: every stat was tested in isolation.**

## The finding

**The Virginia House and Senate are different machines at the committee stage, and only one of them is a
filter.**

| | got out of committee | majority patron | minority patron | gap |
|---|---|---|---|---|
| **House 2023** | 674 of 1,210 (56%) | 453/652 (**69%**) | 181/493 (**37%**) | **+33** |
| **House 2024** | 1,069 of 1,547 (69%) | 762/914 (**83%**) | 296/611 (**48%**) | **+35** |
| **Senate 2023** | 767 of 852 (90%) | 373/416 (90%) | 367/401 (92%) | −2 |
| **Senate 2024** | 727 of 737 (99%) | 388/396 (98%) | 319/321 (99%) | −1 |

**In the House, whether the patron is in the majority is worth 33–35 points.** In the Senate it is worth
nothing, because the Senate committee stage barely filters at all — it reports out 90% then 99% of
everything put in front of it.

**The strongest evidence this is structural and not partisan: the House flipped between these sessions**
(Republican 52–48 in 2023 → Democratic 51–49 in 2024) **and the gap held at the same size, +33 then +35,
with the majority party swapping.** It is about being in the majority, not about being a Republican or a
Democrat.

Per-committee in 2024, the House gaps are severe — Public Safety **93% vs 25%**, Courts of Justice
**87% vs 32%**, Privileges and Elections **86% vs 35%**, Finance **72% vs 22%**. The gap is positive in
13 of the 15 committees with 25+ bills from both sides; the two exceptions are Senate committees.

## Why isolated testing hid it

Scored alone, `patron_in_majority` is +5.4% and `committee` is +7.2%. **Together they are +16.7%** — more
than double either. Neither variable alone can express *"a minority patron in House Courts of Justice"*,
which is the situation that actually determines the outcome.

Averaging the two chambers together also washed the effect out: a stat that is decisive in one institution
and irrelevant in the other reads as mediocre in both.

## The overfitting cliff, measured

| model | better than guessing | cells | outcomes never seen in training |
|---|---|---|---|
| majority + committee | **+16.7%** | 54 | 17% |
| majority + committee + co-patron share | +14.6% | 83 | 31% |
| + patron volume | +8.5% | 80 | 63% |
| + subject | −0.1% | 6 | 99% |

**Two variables is the ceiling.** Past that the cells go empty, the model falls back to guessing, and by
five variables it is worse than knowing nothing. Recorded so nobody "improves" it by adding more.

## What this means for the product

**Do ship, because they are facts a lobbyist would act on:**
- **A House bill with a minority patron is in real trouble at the committee stage** — a 33–35 point
  disadvantage, replicated across a change of control. This is the single most useful thing in the data.
- **Majority co-patron share is the lever**, and it is the rare stat describing something an org can
  *change* rather than merely observe (+6.7% / +5.3% on its own).
- **A Senate bill getting out of committee is close to a formality** (90%→99%). The fight is elsewhere, and
  telling someone that is worth as much as any positive prediction.

**Do not ship:** any per-bill probability. Even the best model moves a 70% base rate by a limited amount,
and it is a base rate about a *class* of bills, never a claim about one. P27's ban on a composite score now
rests on measurement, not only on principle.

**Still true from the earlier rounds:** nothing about a patron's personal record, their relationships, their
district, the bill's own attributes, or its filing timing survived a clean test. See
[[testing/calibration_ledger]] for all 47.

## CORRECTION 2026-08-01 — I was too dismissive about committee rates

**Owner: *"weren't you saying committee pass rates are widely different in the House? isn't that data worth
knowing if one of our bills is in a low or high pass rate committee?"* He is right and I conflated two
different things.**

House committee rates in 2024 range **45% to 84%** — a 39-point spread:

| House committee | 2023 | 2024 |
|---|---|---|
| Finance | 46% (n=85) | **45%** (n=96) |
| Courts of Justice | 62% | 58% |
| Public Safety | 48% | 60% |
| Appropriations | 65% | 71% |
| Education | 53% | 77% |
| General Laws | 63% | **84%** |

**That spread is real and a lobbyist should absolutely see it.** A bill in House Finance is in a very
different place than one in General Laws.

**Why it still scores badly as a PREDICTOR (+1.6% alone, House-only, drift-corrected):** the rates do not
hold their positions well between sessions — **r = +0.44 (n=11)**. Almost every committee rose in 2024 with
the chamber's overall rate, and the ordering only partly persisted. Finance stayed harsh; Transportation
went 52% → 76% and General Laws 63% → 84%.

**So both are true, and I stated only one:**
- **As a FACT about last session** — "House Finance reported 43 of 96" — it is accurate, useful, and
  belongs on the panel.
- **As a GUIDE to this session** — it is shaky, because a committee's rate moves a lot year to year.

**"Weak predictor" is not "not worth showing."** A lobbyist asking *"is this committee a graveyard?"* is
asking a descriptive question about the venue, not asking us to forecast their bill. Ship the number with
its denominator and its session label; do not imply it carries forward.

## WITHIN-SESSION TEST 2026-08-01 — the owner's context hypothesis, tested

**Owner: *"it might be a valid predictor if we limit the data to sessions that match the set-up of party
control of chamber and committee."*** Correct instinct, and directly testable — but not by matching
sessions (we have exactly one session of each House control). **Split a SINGLE session instead:** learn on
the bills filed first, predict the ones filed later. Same majority, same chairs, same rules, by
construction.

| | House 2023 (R control) | House 2024 (D control) |
|---|---|---|
| **patron in majority** | **+9.8%** | **+10.1%** |
| patron matches committee majority | +7.4% | +10.1% |
| **committee identity** | **+1.9%** | **+4.3%** |
| subject | +1.8% | +1.3% |

**Two findings, and the first answers the owner's question directly.**

1. **Committee identity stays WEAK even with political context held perfectly constant** — +1.9% and
   +4.3%. The hypothesis was that year-to-year instability was hiding real committee signal. It was not:
   remove the instability entirely and the signal is still small. **Committee remains a fact worth showing,
   not a predictor.**

2. **`patron_in_majority` holds at ~10% in BOTH sessions, under BOTH parties, within a fixed context.**
   +9.8% under Republican control and +10.1% under Democratic control. This is the strongest validation the
   finding has received — it is not an artifact of the flip, of drift between sessions, or of pooling.

**Senate: still unusable at this stage.** Its within-session base rate moves 84% → 99% (2023) because
late-filed Senate bills almost all survive, which is what produced a nonsense −58% for committee. In 2024
it is 99% → 98% with almost no variance. Confirmed a third way.

## The honest caveats
- **Two sessions.** The gap replicated across one flip; that is encouraging, not conclusive.
- **"Got out of committee" is derived** from `Last_*_actid` ending in `94` ("Left in <committee>"), verified
  621/621 and 487/488 — but it is the LAST action, so a bill re-referred and killed elsewhere is attributed
  to its final committee.
- **The Senate's 99% in 2024 is suspiciously high** and worth checking against 2025 before leaning on it.
- **Untested:** interactions beyond two variables inside a single chamber, and everything in the
  blocked list (full bill text, a third session).
