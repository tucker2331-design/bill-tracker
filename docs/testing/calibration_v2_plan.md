---
tags: [testing, calibration, method, plan, war-room]
updated: 2026-08-02
status: active
---

# The instrument: same words, opposite fates

## Why the previous drafts were wrong

Draft 1 was a methodology. Draft 2 was ten questions, most of them descriptive ("where do bills die") —
true, obvious, and not worth 20 sessions to establish.

**What survived review was one question — "what gets a minority bill through?" — and the reason it is the
right shape generalises:** it fixes a population that is alike in one important way, then asks what
separates the winners inside it. It can be run forever, against any pool, and it ends in an action.

**This draft is built on that shape, and on the strongest version of it available.**

---

## The core idea

Bills differ in a thousand ways at once, so any comparison is confounded by content. A parking-fee bill and
an abortion bill have different fates for reasons no feature list will capture.

**Unless the words are the same.**

When two bills carry the same text and one passes while the other dies, **content is held constant and
whatever differs is what mattered.** That is as close to a controlled experiment as this domain allows.

**MEASURED, all 11 regular sessions 2017–2027:**

| | |
|---|---|
| companion pairs (same session, both chambers, same title) | **3,139** |
| of those, both chambers passed it | 1,820 |
| both chambers killed it | 815 |
| **DIVERGED — one lived, one died** | **504 (16%)** |

**504 natural experiments.** Same text, same session, same political weather, same week — and opposite
outcomes. Every one of those pairs is a direct question: *what was different about the room?*

Per session it runs 27–70 divergent pairs, so this supports cutting by chamber, by committee, by patron
standing, and still leaves something to count.

---

## What this instrument answers that nothing else can

Each of these is the same question asked of a different slice. None has a fixed answer; all are re-runnable
against every new session.

**Direction of failure**
- When a pair diverges, which chamber kills it more often? Is that stable across control regimes, or does
  it follow whoever is in the majority?

**Venue**
- Which committee pairs reliably diverge — where the House committee passes what the Senate committee kills,
  or the reverse? **That is a map of where to file a bill**, and it is derived from cases where the bill
  itself was identical.

**Patron**
- In a divergent pair, is the surviving side more often the majority-standing patron? **This tests the
  majority-standing finding with content perfectly controlled** — the strongest available check on the one
  result that has survived every correction so far.
- Does the more senior patron survive? The one who files fewer bills? The one on the deciding committee?

**Sequence**
- Does the chamber that acts FIRST do better or worse? Does a bill that has already passed one chamber fare
  better in the second than an identical bill starting fresh?

**The negative space**
- Are there committees that never kill a bill their counterpart passed? Or that always do?

---

## The other pools, and what each holds constant

| pool | holds constant | isolates | status |
|---|---|---|---|
| **Companions** | text, session, climate, timing | chamber, committee, patron | **3,139 pairs — measured, viable** |
| **Reintroductions** | text, roughly | regime, patron, timing, Governor | needs cross-session matching (see limits) |
| **Incorporations** — LIS says so explicitly (*"Incorporated by Public Safety (HB158-McClure)"*) | subject and intent | **whose version survives** | not yet counted; a direct test of patron influence |
| **Copycats** (same session, unrelated patrons) | subject | venue vs sponsor | not yet counted |

**Reintroduction must match on TEXT, not patron.** Owner: *"patrons will leave or give up on a bill and
someone else will pick it up with minor adjustments."* Matching on patron would discard exactly the cases
where the handoff IS the variable — and a bill that changes hands and then passes is one of the most
informative rows in the dataset.

---

## Limits found while checking whether this was feasible at all

**1. There is no full bill text for history.** Open States `bill_versions.csv` is metadata; the actual text
lives behind `bill_version_links.csv` URLs pointing at legacylis CGI pages. Fetching 20 sessions of those
would be scraping at scale — not acceptable, and not necessary.

**2. Abstracts are unusable as a spine.** Coverage measured per session: 100% for 2020, 2022, 2024–2027;
**31–35% for 2017–2019; ZERO for 2023.** Median length also drops from ~480 to ~185 characters after 2024,
so the field changed. Usable as a supplement where present, never as the matching key.

**3. Titles are the only universal key — 100% coverage in every session**, median ~60 characters, and
Virginia's convention makes them substantive: *"Elections; early voting."* / *"Imprisonment; consecutive
terms."* The existing companion detector already treats identical title as its structural signal
([[architecture/text_similarity]]), and the 3,139 figure above is built on it.

**4. The comparer's threshold is NOT validated for this use.** `tools/text_corpus/companions.py` calibrated
`NEAR_IDENTICAL = 0.80` on **n=12, one session, full text**, and its own docstring says to re-measure before
reusing it. Cross-session reintroductions are edited more heavily than same-session companions. **That
recalibration is a prerequisite for the reintroduction pool, not for companions.**

**5. A defect in the source, found by checking.** The `VA_2023S1` archive contains **3,082 bills — an exact
duplicate of the 2023 regular session's identifier set**, relabelled. Treating it as a separate session
would silently double-count an entire session. **Every archive's identifier set must be checked for overlap
against its neighbours before use.**

---

## On pooling — correcting a guard I got wrong

A previous draft said a finding *"must hold in a majority of independent regimes."* **That is backwards.**
Context is not noise to be generalised over; **the context is frequently the finding.** "Minority bills die
in House Courts and survive in House Transportation" is not a failure to generalise, it is the answer.

**The rule instead: every finding carries its pool, and the pool is part of the claim.** Never "minority
bills pass 30% of the time" — always "minority-patron House bills, divided control, passed 30% (n = …)".
A number without its pool is not weaker, it is a different and false claim.

**The real risk is slicing until something looks interesting.** Two honest guards:
1. **Pools are defined by something structural** — chamber, regime, committee, text-match — and defined
   before the outcome is looked at. Never "the bills that did well".
2. **Report counts, and report how many pools were examined.** Five of forty committees showing an effect is
   a different claim from five of five.

---

## What to do first

1. **Verify no other archive is a duplicate** (limit 5). One pass over 20 identifier sets. Cheap, and
   everything downstream is wrong without it.
2. **The 504 divergent pairs, by patron standing.** The tightest available test of the only finding that
   has survived every correction, with content controlled.
3. **The 504 by committee pair** — the where-to-file map.
4. **Count the incorporation pool**, which is a second natural experiment nobody has looked at.

**Still open to you:** other Virginia situations where the words stay put and the circumstances move —
budget amendments, a bill appearing in both a regular and a special session, carry-overs that get
re-referred. Each is another pool, and you will know ones I do not.
