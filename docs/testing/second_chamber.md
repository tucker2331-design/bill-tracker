---
tags: [testing, calibration, second-chamber, floor-votes]
updated: 2026-09-23
status: active
---

# The second chamber — one asymmetry, and a data trap

`tools/calibration/second_chamber.py` · 2023–2026, the four sessions with member-level floor roll calls.

## The asymmetry

Bills that passed their first chamber with at least one no-vote (n = 1,885). Share of the **other** party that
voted yes in the first chamber, against passing the second:

| other party voted yes | patron's party **runs** chamber 2 | patron's party does **not** |
|---|---|---|
| 0–10% | 86% | **24%** |
| 10–50% | 89% | 34% |
| 50–90% | 86% | 62% |
| 90–100% | 87% | **80%** |

Logistic regression, year and origin chamber controlled: when the patron's party runs chamber 2 the
other-party coefficient is **+0.01, p = 0.97**; when it does not, **+2.79, p = 3×10⁻¹³**, and own-party support
is irrelevant (p = 0.53). Survives restricting to bills the other party genuinely split on (10–90% yes:
32% → 39% → 53% → 70%, p = 0.0002).

**Why it is an asymmetry and not a feature:** (1) the headline vote total already carries nearly all of it —
AUC 0.756 for the total against 0.775 for the party split, so a lobbyist reading the tally loses almost
nothing; (2) nearly the whole not-aligned sample is **2023's split control** — in 2024–26 a minority bill
essentially cannot pass the House without majority votes, leaving 2–4 bills per year below 50%. What survives
as a usable statement is the flat side: **surplus cross-party votes in chamber 1 buy nothing in a chamber your
own party runs.**

## The data trap — 997 false negatives

The member-level floor file is missing most **second-chamber** passages. Used as the outcome it reported a 49%
second-chamber pass rate; the action record says **83.6%**. HB 1595 of 2023 was enacted as Chapter 772 and the
vote file said it died. The outcome now comes from the action record (with `senate.*passed` deliberately
excluded — it matches *"Passed by indefinitely"*, which is a kill); the vote file is used only for what it is
good at, the chamber-1 party split. Coverage of that split is uneven — 77–98% of House-origin bills, 36–55% of
Senate-origin — and is carried as a caveat.
