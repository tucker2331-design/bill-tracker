---
tags: [testing, calibration, causal, confound, lobbyist]
updated: 2026-09-11
status: active
---

# The bill-mix confound — and what a lobbyist can actually do about it

## The objection (owner, 2026-09-11)

> "you notice that legislators effectiveness change out of the majority but this could be for the type of
> bills they are introducing ie it may only be 60 in the majority bc they tried a big controversial bill
> since they have chamber control and that 30% could be inflated bc all they tried was transportation code
> and other bi partisan issues to introduce."

The within-person design ([[testing/calibration_conclusion]] Layer 1) holds the **person** constant and lets
the **bill** vary. If a legislator files different kinds of bills when their party runs the chamber, then
60% majority / 34% minority is not one person meeting two worlds — it is two different portfolios, and the
gap is measuring ambition.

**It can cut either way**, which is why it had to be measured and not argued:
- harder bills in the majority → the true advantage is **bigger** than +26
- easier bills in the minority → the true advantage is **smaller** than +26

`python3 tools/calibration/bill_mix.py`

## The answer: it survives every content control, and the controls make it larger

144 legislators are observed under both statuses (9,819 majority-year bills, 7,662 minority-year bills).

| what is held constant | majority | minority | swing |
|---|---|---|---|
| person only (the number under attack) | 60% (9,819) | 34% (7,662) | **+26** |
| person **+ subject area** (1,454 cells) | 61% (6,258) | 33% (4,993) | **+28** |
| person + **the bill idea**, same chamber (891 refile groups) | 52% (1,470) | 24% (1,499) | **+28** |
| person + **the exact title**, character for character (323 groups) | 40% (396) | 9% (419) | **+31** |

**A minority patron refiling their own identical bill passes it 9% of the time.** The same person's
character-identical filing in a majority year passes 40%.

### The portfolio does not get easier

Each bill is scored by how **other** patrons' bills in the same session × subject × chamber fared — the
patron's own outcome excluded, so the score is built without reference to the thing being explained.

- mean difference in portfolio baseline, majority minus minority: **+1.97 pt (SE 1.24), p = 0.112**
- 75 legislators drew easier cells in power, 69 drew harder

There is no detectable composition shift. Total variation distance between the two subject mixes is
**0.087** — the same people file substantially the same things. The largest single shift is Crimes and
Offenses at −2.5pt.

### And the swing is identical in every difficulty stratum

| subject-matter difficulty | minority patron | majority patron | swing |
|---|---|---|---|
| hardest 20% (0–37%) | 19% | 45% | +26 |
| (37–46%) | 26% | 53% | +27 |
| middle 20% (46–54%) | 35% | 62% | +26 |
| (54–64%) | 40% | 66% | +28 |
| easiest 20% (64–100%) | 44% | 72% | +28 |

A composition story predicts the gap concentrating somewhere. It is flat to within 2 points across the
entire range. Majority standing is a **constant additive shift**, not an interaction with bill type.

## Two threats that would have survived all of the above

**Persistence.** A refile group can be "keep filing until it lands." Split on which status came first:

| | majority | minority | swing |
|---|---|---|---|
| majority filing came FIRST (349 groups) | 43% (571) | 33% (584) | **+11**, p = 2.2e-4 |
| minority filing came FIRST (542 groups) | 58% (899) | 18% (915) | **+39**, p < 1e-16 |

Persistence pushes the majority-first arm **down** — the later attempt there is the minority one. So **+11
is the floor with persistence working against the finding**, and the difference between the arms (+28) is
how much refiling itself is worth. Both arms are positive; persistence cannot flip a sign.

**Direction.** A confound that lives in the person (ambition, skill, staff, seniority) predicts the same
sign on every transition. Power predicts opposite signs.

| | transitions | change in that person's own pass rate | |
|---|---|---|---|
| gained power | 124 | **+29 pt** | 109 up, 14 down (p < 1e-16) |
| lost power | 119 | **−21 pt** | 21 up, 95 down (p = 1.2e-11) |

**The effect turns off.** No fixed trait of a legislator or of their bills can produce opposite signs on the
same person. This is the strongest causal signature observational data offers short of a randomised design.

Present in every era: +22 (2017-19), +18 (2020-21), +27 (2022-23), +31 (2024-26).

---

## The second half of the objection, which matters more

> "the difference between a legislator and lobbyists are big, the lobbyists doesnt decide this bill should
> go in now bc of control, they get the bill and have to work the best of their circumstances, if our
> advice is try a more bi partisan bill, we arent really helping them."

Correct, and the data agrees with the owner twice over.

**First: "file a more bipartisan bill" would not work even if the lobbyist could do it.** From the table
above — a majority patron on the **hardest** subject matter passes 45%; a minority patron on the **easiest**
subject matter passes 44%. Moving a bill across the entire observed range of subject difficulty does not buy
what moving it to a majority patron buys. Subject matter is not a substitute for standing.

**Second: the finding is not advice to the legislator. It is a price on the carrier**, and choosing the
carrier is a lobbyist's job.

### The handoff — identical title, a DIFFERENT person carrying it

| | majority carrier | minority carrier | swing | |
|---|---|---|---|---|
| same year (1,073 ideas) | 63% (1,173) | 49% (1,167) | +14 | this is the cross-chamber companion design |
| **a later year** (154 ideas) | 40% (205) | 17% (218) | **+24** | this is the move a lobbyist makes between sessions |

Same words, different name on it. Toscano's child-day-programs bill (2017) → Chris Head (2019). Ken Plum's
minimum wage (2017) → Jeion Ward (2025).

### The one lever a lobbyist owns outright: one co-patron from the other party

Same patron, same bill idea, same chamber — filed once **with** a cross-party co-patron and once **without**.
Nothing about the bill changes. Only the name list.

| | with | without | swing | |
|---|---|---|---|---|
| every patron (495 groups) | 56% (656) | 37% (1,009) | **+19** | p = 1.6e-14 |
| majority patron | 62% (295) | 53% (392) | +9 | p = 0.013 |
| **minority patron** | **45% (187)** | **20% (269)** | **+26** | p = 3.9e-09 |

**The lever is worth three times as much to the client who has the least power.** A minority patron with one
cross-party name on the bill reaches 45% — which is where a majority patron on the hardest subject matter
sits, and better than a minority patron on the easiest subject matter with no co-patron.

Same-party co-patrons are worth **zero** ([[testing/calibration_conclusion]]): 30% vs 33%. It is not support.
It is the *cross-party* signature specifically.

## What this means for the product

Findings sort into two tiers, and the site must not mix them:

**CONTEXT — true, causal, and not a lever.** The lobbyist cannot change these; they set the price of the
job and the expectation to set with a client.
- majority standing worth ~+26 pt, constant across subject difficulty
- the regime effect reverses on loss of power
- subject-matter difficulty (range 19%→44% for a minority patron)

**LEVERS — things a lobbyist can do on a Tuesday with a bill they did not choose.**
1. **Recruit one cross-party co-patron** — +26 pt for a minority patron, +9 for a majority one
2. **Move the bill to a majority carrier next session** — +24 pt on identical text
3. **File a cross-chamber companion** — the majority-side copy survives at 63% vs 49%
4. **Prepare for the money-committee stop** — 79% vs 99% at a second committee, −34 pt for minority patrons
5. **Know how the room kills** — clock vs vote decides whether to fight for a docket slot or for votes
6. **Work the persuadable list** — [[testing/persuadability]]; 20 members are 42% of all defections

## Limits

1. **The co-patron test is within-patron, not within-bill-text.** "Same bill idea" is the subject clause of
   the title; the operative language can differ between the two filings. The exact-title arm exists for the
   regime test (+31) but is too thin for the co-patron cut.
2. **Recruiting a co-patron is not random.** The bills where a lobbyist *can* land a cross-party name may be
   the ones already closest to the line. The within-patron/within-idea design removes the patron and the
   topic but not the lobbyist's own read on winnability. This is the one unresolved selection channel, and
   the forward-validation harness is what settles it.
3. **`passed` is Open States' `passage` classification**, not enactment. It is the same measure used in
   every other finding here, so comparisons are internally consistent.
4. Nine of eighteen sessions carry member-level votes; the co-patron and handoff cuts use bill-level data
   and are unaffected.

## Related

[[testing/calibration_conclusion]] · [[testing/persuadability]] · [[testing/venue_effect]] ·
[[testing/kill_points]] · [[testing/subject_labels]] · [[index]] · [[log]]
