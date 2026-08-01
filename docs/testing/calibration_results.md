---
tags: [testing, calibration, backtest, stats, war-room, results]
updated: 2026-08-01
status: active
---

# Calibration results — 21 candidate stats, tested

**Method:** learn each stat's rates from **2023**, predict **2024**, score against a null that just guesses
the 2023 average every time. Real bills only (HB/SB) — resolutions are a separate population (see §4).
Only facts knowable **before** the committee decides; nothing derived from the bill's own later history.

Candidates come from [[ideas/predictive_lane]]'s entity table, [[ideas/lobbyist_jtbd_ideation]] C3/C5/D2/D4,
the v8 subject profile and the M6 panel slots — not invented here.

---

## 1 · The headline: it is about being in the MAJORITY, not about party

| stat | got out of committee | passed its chamber |
|---|---|---|
| **patron is in the majority party** | **+5.4%** | **+7.9%** ← best single stat |
| patron's party (D / R) | **−7.4%** | **−2.5%** ← actively harmful |

**Raw rates, and they are large:**

| | patron in majority | patron in minority |
|---|---|---|
| 2023 | **826 of 1,068 (77%)** | 548 of 894 (61%) |
| 2024 | **1,150 of 1,310 (88%)** | 615 of 932 (66%) |

A 16-point gap in 2023 and a 22-point gap in 2024. **This is the strongest, most stable effect found.**

**Why the party label is the opposite of useful:** the House flipped between these two sessions
(2023 Republican 52–48 → 2024 Democratic 51–49). Learning *"Republican patrons do well"* from 2023 and
applying it to 2024 gets it backwards, which is exactly what the −7.4% is. **Majority standing transfers
across the flip; party identity inverts with it.** Any stat we ship must be framed as standing, never party.

## 2 · What else survived

| stat | got out of committee | passed |
|---|---|---|
| which committee it is in | +7.2% | +3.8% |
| chamber (House vs Senate) | +6.9% | +1.3% |
| **how many bills the patron carries** | **+6.4%** | +0.8% |
| this committee's record on this subject | +3.5% | +1.9% |
| subject | +2.8% | +3.9% |
| patron sits on the committee | +1.2% | +2.6% |

`patron_volume` is a **new** finding — nobody proposed it. Carrying few bills goes with a better rate than
carrying many, which is plausible as a focus/priority signal and is worth a second look.

## 3 · What died — including several the vault had planned to build

| stat | score | vault item it kills or wounds |
|---|---|---|
| patron's prior success **in this committee** | **−6.2%** | **C5 patron scouting** — the headline form |
| patron's overall prior success rate | −2.5% | C5; "patron win-rate" on the Patron profile |
| has a chief co-patron | −2.2% | co-patron structure |
| bipartisan co-patrons | −0.5% | influence/network framing (C4) |
| committee size | −0.4% | |
| number of co-patrons | +0.3% | "momentum" intuition |
| money committee (Approps/Finance) | +0.1% | |
| emergency clause | +0.1% | |
| prefiled early | 0.0% | |

**A negative score is not "weak", it is worse than knowing nothing.** Shipping
*"this patron is 3 of 4 in this committee"* would have made a reader's judgement worse than if we had shown
them nothing at all — the small-sample rate does not carry to the next session.

## 4 · The largest effect in the data is one we already shipped

Resolutions pass at **91.6%**, real bills at **54.1%**. Splitting them is worth more than every stat above
combined, and it is the ceremonial filter already live ([[state/va_todo_2026-07-30]] §0). Left pooled, it
also **manufactures fake signal**: with resolutions included, "committee" scored +27.6% — almost all of it
was really "is this a commending resolution".

## 5 · A methodology note worth keeping

An earlier run of this had the 2023 House majority **backwards**. Party was derived from voting blocs
(96% accurate per member) and 96% is not good enough to call a **52–48** chamber — it flipped it, and
`patron_in_majority` came out at −7.6%, which read as a real finding and was a bug.

**Fixed by getting the actual roster** (Open States `people`, CC0, all 350 VA legislators past and present,
cached) instead of inferring it. Both chambers in both sessions now match the historical record, and the
same stat reads +5.4%/+7.9%.

**Lesson: a derived label that is accurate per-item can still be wrong about an aggregate built from it,
and a near-tied aggregate is where it will break.** Validate the aggregate against a known truth, not the
per-item accuracy.

## 6 · What this means for the panel

- **Ship:** patron majority standing · committee record · subject · resolution split. All as *observed
  frequencies with denominators*, never as a probability for one bill.
- **Do not ship:** patron scouting rates, co-patron counts, emergency/prefiled flags, committee size.
  Leave the slot empty.
- **Nothing here justifies a per-bill prediction.** The best single stat moves a coin-flip base rate by a
  few points. P27's ban on a composite score now has an empirical basis, not just a design one.

## 7 · Not yet tested
Timing within the session · docket position (no pre-2025 docket) · vote margins · companion bills ·
fiscal impact (not published in bulk) · committee **chair** identity (no role field in the legacy roster) ·
cross-state comparison.

---

# Round 2 — the niche signals (2026-08-01)

Owner: *"the real strong signals might come from even more niche things we didn't expect."* 16 more
candidates tested — owner-named ones plus relational and behavioural signals nothing in the vault proposed.

**The hypothesis was right in principle and the surviving stat is exactly that shape.** But round 2 is
mostly a lesson in how easily this goes wrong: **four of the five apparent winners were measurement
artifacts, caught only by testing them properly.**

## Survivor

| stat | out of committee | passed |
|---|---|---|
| **share of co-patrons in the majority party** | **+6.7%** | **+5.3%** |

Not the co-patron *count* (+0.3%, dead) and not whether they are *bipartisan* (−0.5%, dead) — specifically
**how many of them are in the party that runs the chamber**. Nobody proposed it. It is structural (who
signed the bill), so there is nothing to contaminate.

## Killed by leakage — `text_versions`

Scored **+32.8%** and **+77.9%**, which was the tell. Measured:

| text versions | got out of committee | passed |
|---|---|---|
| 1 | 57% | **3%** |
| 4 | 100% | **100%** |

A bill *acquires* versions by advancing — substitute, engrossed, enrolled. It is the outcome wearing a
feature's clothes. **The leakage rule was written at the top of the file and one still got through**, which
is the argument for always asking "is this too good?" rather than trusting the rule was applied.

## Killed by same-session contamination — the three behavioural stats

These looked like the most interesting findings in the whole exercise. All three used the patron's voting
behaviour from **the same session as the outcome**, so the votes partly encoded the answer. Recomputed from
the **prior** session — which is also how it would work live, since when a session opens you know last
session's behaviour, not this one's:

| stat | same-session (wrong) | prior-session (correct) |
|---|---|---|
| patron's party loyalty | +6.5% | **−2.0%** |
| patron agrees with the deciding committee | +6.0% | **−23.3%** |
| patron's floor win rate | +5.5% | **−5.6%** |

**All three evaporate.** `patron_agrees_with_cmte` goes to −23%: committee rosters change between sessions
and the House flipped, so 2023 agreement with a committee says nothing about the 2024 committee.

## The owner's three named ideas — tested, all weak

| idea | out of committee | passed |
|---|---|---|
| chief patron and chief co-patron from different parties | −2.9% | −0.3% |
| patron's district | +1.6% | −0.0% |
| geographic spread of co-patrons | 0.0% | +0.5% |
| patron's prior success on this subject | −1.0% | +0.7% |

Cross-party pairing does not help. District does not help. **But the instinct behind them — that a
relational fact about who is backing a bill matters more than a fact about the bill — is what
`majority_copatron_share` confirms.** The right family, the wrong members of it.

## Also tested, also weak
`subject_cmte_match` (is it in the committee that usually handles this subject) +2.7%/+0.5% ·
`cmte_load` +2.7%/+1.6% · `patron_bill_rank` +2.3%/+0.2% · `patron_generosity` +1.5%/−0.9% ·
`cmte_member_copatrons` −0.2%/+0.7% · `patron_network_breadth` −0.4%/−0.1% ·
`member_id_band` +3.6%/+2.5% (a seniority proxy; too crude to ship, but the only hint that tenure matters).

## Running scoreboard — what has survived everything

| stat | out of committee | passed |
|---|---|---|
| patron in the majority party | +5.4% | **+7.9%** |
| which committee | +7.2% | +3.8% |
| **share of co-patrons in the majority** | **+6.7%** | **+5.3%** |
| how many bills the patron carries | +6.4% | +0.8% |
| chamber | +6.9% | +1.3% |
| subject | +2.8% | +3.9% |

**Everything that survives is about majority standing or venue.** Nothing about the patron's personal
record, their relationships, their district, or the bill's own attributes has survived a clean test.
