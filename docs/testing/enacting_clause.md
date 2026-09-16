---
tags: [testing, calibration, structural, drafting, lever, war-room]
updated: 2026-09-16
status: active
---

# The enacting clause — the structural "what kind of ask is this?"

[[testing/blind_sweep]] found, blind, that a bill whose **title** says *amend* outperforms one that says
*establish*, and most for a minority patron. That was a regex over a title, which Standard #3 forbids on any
lobbyist surface. **This is the structural replacement, and it replicates.**

`python3 tools/calibration/enacting.py`

## The source

Open States ships each bill's **enacting clause** as the abstract noted `title`:

> *"A BILL to amend and reenact § 58.1-402 of the Code of Virginia, relating to corporate income tax."*
> *"A BILL to amend the Code of Virginia by adding in Chapter 14 of Title 10.1 an article numbered 3.8."*

That is the bill's own formal legal statement of what it does, in a fixed grammar, naming exact Code
sections. It gives three structural facts at once: **what kind of act** it is, **how many sections** it
touches, and **which Code Title** — which turns out to decide the committee.

## ⚠ The outcome leak that nearly shipped

**A bill that passes has its title rewritten from "A BILL to…" to "An Act to…".** Matching only `A BILL`
therefore selects bills that *did not pass*: the matched subset showed an **18%** pass rate against **100%**
for the unmatched, and every downstream number was fiction.

Both verb forms must be matched. With both, the subset passes **53%** against a 2025–26 corpus rate of
**53%** — and that comparison is the check that caught it. **Any subset whose base rate does not match the
population it is drawn from is a selection bug until proven otherwise.**

## It replicates structurally

| act type | bills | passes | majority patron | minority patron |
|---|---|---|---|---|
| **AMEND** | 2,569 | 56% | **72%** (1,475) | **35%** (1,094) |
| AMEND+ADD | 637 | 49% | 59% (475) | 23% (162) |
| **ADD** | 940 | 44% | **55%** (642) | **20%** (298) |
| DIRECTIVE | 398 | 59% | 67% (289) | 37% (109) |

- **majority patron: AMEND 72% vs ADD 55% — +18 points, p = 8.9e-16**
- **minority patron: AMEND 35% vs ADD 20% — +14 points, p = 2.1e-06**

**`AMEND+ADD` sits between the two in both groups.** A dose response, which is exactly what the mechanism
predicts: the more *new* law a bill makes, the worse it does.

This was discovered on 2017–2022 **titles** and confirmed on 2025–2026 **enacting clauses** — held out on
both the measurement and the period.

## Scope is a NULL — and that sharpens it

| sections named | bills | passes |
|---|---|---|
| 1 | 3,461 | 52% |
| 3 or more | 932 | 52% |

**+0 points, p = 0.97.** It is not *how much* you change. It is whether the thing already exists.

## The Code Title decides the room

| chamber | Code Titles (≥25 bills) | median top-committee share | Titles routing ≥80% to one room |
|---|---|---|---|
| **House** | 23 | **79%** | **10 of 23 (43%)** |
| Senate | 19 | 47% | 3 of 19 (16%) |

House examples: Title **58.1** (Taxation) → **H10, 84%**. Title **46.2** (Motor Vehicles) → **H19, 89%**.
Title **32.1** (Health) → **H24, 88%**. Title **22.1** (Education) → **H09, 81%**.

**In the House, the Code Title a bill amends largely decides its committee.** That is the drafting lever
from [[testing/venue_shopping]], sourced from the bill's own clause rather than inferred. The Senate routes
far more loosely, so the lever is chamber-specific.

Where one Title does route to several rooms, the spread for a minority patron is a **median of 15 points**.

## Limits

1. **Coverage is 2025 forward only** — Open States carries no clause for 2017–2024 (0%), 61% for 2025, 51%
   for 2026. Everything here rests on 4,608 bills across two sessions.
2. Still a parse. Reading structural identifiers out of a fixed-grammar legal clause is much closer to
   structural than keyword-matching a title, but it is not LIS telling us directly. **Sourcing the
   amend/create distinction and the Code sections from LIS is the remaining work** before this reaches a
   lobbyist surface.
3. The Code-Title→committee mapping is descriptive. Whether a drafter can *move* a bill between Titles
   without changing its substance is not measured, and is the question that decides how big this lever is.

## Related

[[testing/blind_sweep]] · [[testing/venue_shopping]] · [[testing/panel_audit]] · [[testing/profiles]] ·
[[index]] · [[log]]
