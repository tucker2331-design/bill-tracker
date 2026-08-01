---
tags: [testing, calibration, backtest, stats, war-room, method]
updated: 2026-08-01
status: active
---

# Calibration — scope, method, and the challenges to it

**What this decides:** which stats on the War Room panel ([[design/information_display]] P27) are worth
showing, and which are arithmetic dressed up as insight. The vault has had this backwards for a while — stat
infrastructure was built while the backtest sat "recorded, not queued", when *the backtest decides which
stats are worth building*.

**Now unblocked:** [[knowledge/legacylis_csv_route]] gives 2023 and 2024 complete, cached locally
(`tools/historical_cache`). With 2025 and 2026 that is **four sessions**.

---

## 0 · The measurement that should govern the whole exercise

Before designing anything, I ran the single most important test — **does a committee's pass rate in one
session predict the next one?** If it does not, the headline stat on the panel is noise.

**Measured 2026-08-01, cached 2023 → 2024, committees with n ≥ 20 in both:**

| | committees | correlation | error using the committee's own rate | error using only the base rate | improvement |
|---|---|---|---|---|---|
| **House** | 11 | r = **+0.77** | 0.066 | 0.109 | **+40%** |
| **Senate** | 10 | r = **+0.49** | 0.111 | 0.126 | **+12%** |

**Read that carefully, because it is not the happy answer.**

- **The House stat is real.** Knowing a committee's own history cuts prediction error by 40% against
  "just use the session base rate".
- **The Senate stat is close to worthless.** 12% improvement, r = +0.49, over **ten** committees. That is
  well inside what noise produces at that sample size.
- **Individual committees swing enormously.** `S01` went 61% → 21%; `H10` went 44% → 21%. A lobbyist shown
  "reports 27 of 44" for S01 in 2023 would have been badly misled about 2024.

**Consequence: one number for both chambers would have shipped a House-grade claim on Senate-grade
evidence.** That is exactly the failure this exercise exists to catch, and it took one measurement.

**Base rates for reference** (the null every stat must beat):

| | 2023 | 2024 |
|---|---|---|
| House bills passing the House | 1,191 of 1,865 (64%) | 1,565 of 2,427 (64%) |
| Senate bills passing the Senate | 810 of 1,164 (70%) | 870 of 1,168 (74%) |
| Became law | 812 of 3,029 (27%) | 845 of 3,595 (24%) |

---

## 1 · Method

**Forward-chaining only. Never pooled, never in-sample.**

```
fit on 2023            → test on 2024
fit on 2023+2024       → test on 2025
fit on 2023+2024+2025  → test on 2026   (only when 2026 is complete — see §2.3)
```

Every stat is scored on a session it was not fitted on. Pooling all four and reporting fit would make
everything look excellent and mean nothing.

**Every stat is scored against a stated null.** Default null = **the session base rate**. A stat that cannot
beat "assume this bill behaves like the average bill" does not ship. The comparison is reported as it is
above — two error numbers and the gap — never as a single quality score.

**Kill criterion, decided before looking:** a stat ships only if it beats the null on **held-out** data in
**both chambers separately**. Chamber-specific shipping is allowed and expected; a stat that works only in
the House ships only in the House, labelled.

---

## 2 · Challenges to this design — the reasons it could produce confident nonsense

### 2.1 Four sessions are not four independent samples
2023 and 2024 share a General Assembly; the 2023 election changed the House between them. So the one
transition I measured above **crosses an election** — some of that House r = +0.77 may be a committee
keeping its character despite new members, or may be the two years being more alike than 2024→2025 will be.
**Do not extrapolate the +40% to future transitions.** Re-run it at each new session and watch whether it
holds; a stat whose value collapses at every election is a stat with a six-month shelf life, which is worth
knowing before it goes on a panel.

### 2.2 `Last_house_committee_id` is not "referred to", it is "ended at"
The field names the LAST committee a bill touched. A bill referred to Commerce, re-referred to
Appropriations, and killed there counts **only** against Appropriations. So my §0 measurement is really
*"of bills that ENDED here, how many passed"* — subtly but importantly different from *"of bills SENT here,
how many got out"*, which is the question a lobbyist is actually asking.
**This is a measurement-validity problem, not a precision one, and it must be fixed before any of this
ships:** the true referral→outcome path needs `History.csv` refids, which we have cached. Until then, treat
§0 as evidence that *committee identity carries signal*, not as the final rate for any committee.

### 2.3 Right-censoring — the active session will lie
2026 is live; its bills have not finished. Including it in outcome statistics counts unresolved bills as
"not passed" and depresses every rate. **Outcome calibration uses COMPLETED sessions only.** 2026 enters the
scheme when it adjourns, not before.

### 2.4 The special session is a different animal
`242` is 290 bills, budget-dominated. Pooling it with a 3,595-bill regular session would let ~8% of the data
distort the whole. **Report special sessions separately or exclude them** — and note that the *current* live
session (20262) is also special, so the panel's own numbers today are drawn from an unusual population.

### 2.5 "n ≥ 20" is a threshold I invented, and that is the exact sin already ruled on
I used it above to get a readable table, and it is doing real work — it selected 11 of ~25 House committees.
The owner's objection to invented thresholds stands. **The fix is not a better constant:** report every
committee with its denominator (P26 — `12 of 19` shows its own thinness), and separately measure *whether
error actually shrinks as n grows*. If it does, size is informative and the reader can see it; if it does
not, the stat is noise at every size and no threshold rescues it.

### 2.6 The null model may be too easy
"Session base rate" is a weak opponent. A stat can beat it and still be useless next to something obvious —
e.g. **bill type** (a commending resolution passes near-100%; [[state/va_todo_2026-07-30]] §0 measured 295 of
300 ceremonial in the special session). **Add a second null: base rate stratified by bill class.** If the
committee stat cannot beat *that*, it is re-discovering "resolutions pass".

### 2.7 We cannot see the thing that actually decides outcomes
Caucus decisions, the Speaker's priorities, budget context, a patron's standing — none are in the data. A
stat can be genuinely predictive and still not be *causal*, and a lobbyist may read a rate as a lever when it
is a symptom. **This bounds what the panel may claim:** report observed frequencies, never "your bill has an
X% chance". That is already law here (P27, no composite score) and this is the empirical reason for it.

### 2.8 No pre-2025 docket
`Docket.csv` is header-only for every legacy session. **Anything docket-derived — was it on the agenda, how
many meetings before a vote — can only be tested on 2025/2026, i.e. two sessions, one of them incomplete.**
Those stats start life on much weaker evidence than the outcome stats, and should be labelled or held.

---

## 3 · What gets tested, in priority order

Each is scored the same way: forward-chained, against both nulls, per chamber, with denominators.

1. **Committee pass rate** — §0 done in preliminary form; redo via referral path (§2.2).
2. **Committee rate under the current chair** — the M6 panel's default. Tests whether splitting by
   composition (the [[state/va_build_queue]] E2 break detection) actually improves prediction or just
   halves the sample.
3. **Patron success rate** — does "this patron gets 3 of 4 bills out" carry over? `Bills.csv` has
   `Patron_id` for every session.
4. **Bill class** — the stratified null of §2.6, and a candidate stat in its own right.
5. **Subject-area pass rate** — needs the bill→subject link (`CiBillSubjects.csv` exists on the legacy route
   and is **not yet cached**; add it if this reaches the queue).
6. **Co-patron count as a signal** — `Sponsors.csv` IS cached and is 1.2 MB/session, which suggests it
   carries the full patron list. **If so it also answers E6 (co-patrons) for historical sessions for free** —
   worth a look independent of calibration.

---

## 4 · What this cannot answer
- Anything before 2023 (the route 404s; [[knowledge/legacylis_csv_route]]).
- Anything docket-derived before 2025 (§2.8).
- Causation (§2.7).
- Individual-bill prediction — still Tier 3, still owner-gated ([[ideas/predictive_lane]]), and §0 is a
  reason for caution, not a green light.
