# Round 2: Statistician's rebuttal

Labels: **[repo]** project files · **[audit]** `stat/boot.out` · **[bounds]** mathematician's `math/bounds.out` · **[mod]** moderator's leak check (`tools/calibration/copatron_leak_check.py`) · **[research]** cited · **[judgment]** mine. Arithmetic is shown; no new model runs.

## What changed my mind

**1. The co-patron leak is resolved. I withdraw that recommendation.**
- For 2025, the co-patrons printed on each introduced bill match the undated list exactly: 0 of 1,663 bills gained any after filing [mod].
- The subcommittee kill rate using co-patrons *at filing* is 19.8% with none (n=425) vs 6.0% with some (n=517) [mod]. That is the same contrast as before.
- What remains is bill-level selection (patrons recruit co-patrons for bills they mean to push). The claim level stays "observed within-patron association". Only 2025 was checked, but the mechanism I feared does not operate there [judgment].

**2. Year-to-year noise is now measured, and it is bigger than I assumed.**

| year (scored year-ahead) | overall | hardest third |
|---|---|---|
| 2021 | 85.39 | 66.16 |
| 2022 | 84.92 | 68.85 |
| 2024 | 84.36 | 64.86 |
| 2025 | 86.09 | 67.77 |

[bounds]

- The spread across years is 1.7 points overall and 4.0 on the hardest third.
- A feature that is +0.3 on 2025 is invisible against that. The "66–68% plateau" is itself inside the year-to-year range [judgment].
- This moves rolling-origin evaluation from "nice to have" to required.

**3. The mathematician's hardest-third arithmetic.** The top two-thirds already run at (0.8609 − 0.6777/3)/(2/3) = 95.3%. So ">80% on the hardest third" equals roughly 90.2% overall [bounds, derivation]. I endorse it. It makes the owner's two goals one goal.

## Where I now agree

- **Mathematician: S/Θ/O estimand.**
  - S = does the bill reach a recorded vote; Θ = the two party positions; O = the room outcome.
  - This is the formal version of my competing-risks model plus a correlated room model. I adopt it as the headline estimand.
  - The θ<sub>b,s</sub> random effect is the right structure. The design effect (4.2–4.6 [audit, bounds]) is its empirical footprint.
- **Mathematician: labels need bill-clustered denominators.** "94 in 100" rests on about 12,355 / 4.6 ≈ 2,700 effective ballots, not 12,355 [audit arithmetic]. The bootstrap interval (0.936–0.953) already reflects that. Publish that interval, recomputed on 2026.
- **Genius: informant / value-of-information.** Once a joint Θ model exists, "which one question most reduces uncertainty about O" is a computable ranking rule (the mathematician's I(O; answer)). This is the best argument for the hierarchical model: coherent updating, not accuracy [judgment].
- **Lobbyist: triage framing.**
  - Likely is 70% of ballots at 94% right [repo], which is a legitimate "no call needed" filter.
  - I side with the mathematician against "predicting the hard third = predicting our own work": the model learns the *equilibrium* with typical lobbying already in the data. Uplift is a separate, causal quantity that only a randomised pilot identifies [judgment].
- **Marketing officer:** spend the 2026 score once, and publish calibration rather than "86%".

## Where I still disagree

- **Mathematician: the Cover–Hart interval is right in logic, but give it error bars and a sign.**
  - Sampling: with 734 pairs, R<sub>NN</sub> = 0.25 has SE √(0.25 × 0.75 / 734) ≈ 0.016, so about ±3.1 points [derivation]. With 75 pairs, the SE is about ±3.9 points [bounds]. So "87–93%" is roughly ±8 points wide once you include sampling error.
  - Dependence: if the later chamber sees the earlier vote, twins agree more than independent draws would. Observed R<sub>NN</sub> is then too low, and the whole interval moves toward *lower* Bayes accuracy. The 86.2% upper end is optimistic [judgment].
  - Net: the interval neither proves the model is at the ceiling nor shows headroom beyond a few points.
  - And estimating Bayes error from replicates (their rec. 3) is intellectually right but low product value: the replicates are a selected population (both twins reached a roll call). I rank it last.
- **Genius: "public records are exhausted".** The minimum detectable effect (0.64 points [audit]) and the year-to-year spread (1.7 [bounds]) mean small gains are *unmeasured*, not absent. The correct claim is "no public-record step change found". The conclusion (pivot to information acquisition) is still right.
- **Genius: the 96.4% informant figure** remains a ceiling. It copies a party-mate's actual same-day ballot. Stated positions in a contact log will be noisier. Score them rather than assume them (GJP-style Brier weighting, [AI Impacts summary](https://aiimpacts.org/evidence-on-good-forecasting-practices-from-the-good-judgment-project/)) [research].
- **Marketing officer: "95%+ on the most confident 67%".** Report it only as a risk–coverage curve by slice. At 95%+ the other-party coverage is 45% vs 67% overall [repo]: the confident set skews to where help matters least, as the mathematician noted.
- **Lobbyist: "pivotality is exact".** Unchanged. Only 3.9% of rooms had a margin of ≤1 vote [bounds]. Pivotality needs the joint Θ model.

## Revised top 5 (priority order)

1. **Pre-register and score 2026 once.**
   - Measures: log loss, Brier, accuracy, other-party accuracy, label calibration with bill-clustered CIs, room-outcome accuracy, and a risk–coverage curve by slice.
   - Freeze the model, thresholds and slices first. Relabel 2025 as validation [judgment].
2. **Re-pose the estimand as S/Θ/O.**
   - S: a competing-risks fate model (not heard / stricken / voice-killed / recorded / reported), preceded by the mathematician's majority roll-rate diagnostic.
   - Θ/O: a hierarchical θ<sub>b,s</sub> model.
   - Member labels are derived from these, and no room claim is built by multiplying member probabilities.
3. **New acceptance rule: rolling-origin (2021–2025), paired, bill-clustered log loss, with pooled z ≥ 3.** Retire "hardest third >80%" and "break 95" as goals.
4. **Correct the ceiling language in `first_vote.md`.**
   - Twin result as a Cover–Hart interval with sampling error and a dependence caveat.
   - The leave-one-out 96.4% in place of 97.3%.
   - Model vs oracle compared in joint-position units.
5. **Pre-register 2027: Brier-scored contact-log pooling into the Θ model, plus a randomised contact pilot for uplift.** Run the cheap informant backtest now as the precursor.

*Dropped:* co-patron dating check (resolved [mod]). The co-patron finding may go on the War Room as an observed within-patron pattern.
