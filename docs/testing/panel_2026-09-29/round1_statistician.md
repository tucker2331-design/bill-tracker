# Round 1: Statistician's position memo

Labels: **[repo]** from project files · **[audit]** from the saved audit (`stat/boot.out`; `math/bounds.out` where noted) · **[research]** cited source · **[judgment]** my statistical reading. Arithmetic is shown.

**Bottom line.** The 86.1% is real and well calibrated. The evaluation, though, cannot tell apart most of the ideas it labelled "no gain". 2025 is a validation year, not a test year. And the thing being estimated (accuracy on recorded first ballots) is not the quantity the War Room uses. Fix the measurement and change the estimand before adding any more features.

## 1. Evaluation-design audit

**The 2025 result reproduces, with bill-clustered CIs [audit].**

| metric | value | 95% CI (1,624 bills, 2,000 draws) |
|---|---|---|
| overall accuracy | 0.8609 | 0.8498–0.8717 |
| other-party | 0.8018 | 0.7838–0.8192 |
| hardest third | 0.6777 | 0.6545–0.7026 |
| Brier | 0.0993 | |
| log loss | 0.3169 | |

**Clustering is by bill.**
- The design effect is 4.6 [audit]; the mathematician gets 4.2 analytically [bounds.out].
- The effective sample is 17,553 / 4.6 ≈ 3,816 ballots. That is close to the 3,245 (bill, party) groups [bounds.out], so there is roughly one unknown per party per bill [judgment].
- The naive ±0.51-point half-width becomes ±1.1 (1.96 × 0.0056).

**What size of change the setup can detect.** Comparisons are paired (same ballots). Removing the room aggregates gives these paired SDs [audit], and the minimum detectable effect is 2.8 × SD (80% power, two-sided α = .05):

| metric | paired SD | minimum detectable effect |
|---|---|---|
| accuracy | 0.0023 | **0.64 points** |
| fixed hardest third | 0.0069 | **1.9 points** |
| log loss | 0.0017 | 0.0048 |

- The repo's "within ±0.6" band is essentially this detection limit.
- A true +0.3-point gain would be detected about 25% of the time: z = 0.30 / 0.23 = 1.30, and P(Z > 0.66) ≈ 0.25.
- So "no gain" means **"no gain ≥ ~0.65 points"**. The owner's target of +12 points on the hard third is about 6× its detection limit. **Step changes are reliably ruled out; small gains are not** [judgment].
- Model pairs that disagree on more than the 3.4% of decisions seen here have larger paired SDs [audit/judgment].

**Holdout reuse.** About 35 approaches were scored on 2025 [repo].
- If all were null, about 35 × 0.05 = 1.75 false "wins" would be expected. Bonferroni needs |z| ≥ 3.19.
- The retained room-aggregate win has z = 0.68 / 0.23 ≈ 2.96 on accuracy and 0.63 / 0.17 ≈ 3.7 on log loss [audit].
- The baseline itself was chosen on 2025: Round 3 came before the "choose on 2024" rule [repo]. The `first_vote.py` docstring still says "tune 2025" [repo].
- Reusing one holdout this way biases the chosen model upward ([Dwork et al. 2015](https://www.science.org/doi/10.1126/science.aaa9375)) [research].
- **Call 2025 validation. 2026 is the only test.**

**One year understates the uncertainty.** The year-ahead score was 84.36 in 2024 and 86.09 in 2025 [repo]. That gap (1.73 points) exceeds the within-year half-width of ±1.1, so any single-year CI understates the uncertainty on 2026 [judgment].

**The hardest third is a poor target.** It is chosen by the model's own confidence. For a calibrated model, accuracy there roughly equals mean confidence there: 0.6777 vs 0.6727 [bounds.out].
- ">80% on the hardest third" is really a demand for sharpness, not skill.
- The set changes from model to model, which is the Round 4 trap [repo].
- The "mixed-split" slice is defined by the outcome, so it can be a diagnostic, never a target [judgment].

**A possible leak to check.** Co-patrons come from Open States `_bill_sponsorships.csv` with no dates (`corpus.py`) [repo].
- If co-patrons can be added after a bill clears its first vote, only surviving bills can gain them.
- That would inflate both the feature and the 20.4% vs 6.9% contrast.
- I have not verified that late additions occur. Rebuild the co-patron list from the introduced bill [judgment].

## 2. Accuracy vs proper scores, for how the War Room uses predictions

Accuracy thresholds every prediction at 0.5. The War Room instead acts on labels and rankings. Proper scoring rules reward honest probabilities ([Gneiting & Raftery 2007](https://doi.org/10.1198/016214506000001437)), and the aim is sharpness subject to calibration ([Gneiting, Balabdaoui & Raftery 2007](https://doi.org/10.1111/j.1467-9868.2007.00587.x)) [research].

- **Skill vs always-yes:** Brier 1 − 0.0993 / 0.1931 = **0.49**; log loss 1 − 0.3169 / 0.5746 = **0.45** [audit].
- **Calibration (ECE 0.015):**

| label | right | mean confidence | 95% CI |
|---|---|---|---|
| Likely | 0.944 | 0.938 | 0.936–0.953 |
| Leans | 0.705 | 0.704 | 0.675–0.734 |
| Toss-up | 0.573 | 0.550 | 0.536–0.612 |

- Recheck calibration on 2026 and by slice (other-party × subcommittee) [judgment].
- **The trap is aggregation.** Member labels are calibrated, but ballots are strongly correlated (design effect 4.6). Multiplying member probabilities to get "clears the room" or "who is pivotal" will be overconfident. Room-level claims need their own correlated model and their own calibration check. (The room majority is currently called right in 88.4% of 1,624 rooms, against a 73.5% base [bounds.out].) [judgment]

## 3. Against the literature

On U.S. House and Senate roll calls, [Kraft et al. 2016](https://aclanthology.org/D16-1221.pdf) report 90.6% against an 84.5% always-yea baseline, and [Gerrish & Blei 2011](https://dl.acm.org/doi/10.5555/3104482.3104544) 89% on the same data [research].

| model | share of baseline error removed |
|---|---|
| Kraft et al. | (15.5 − 9.4) / 15.5 = 39% |
| Gerrish & Blei | (15.5 − 11) / 15.5 = 29% |
| **ours** | (26.1 − 13.9) / 26.1 = **47%** |

California committee votes, predicted from what legislators said *during* the hearing, reached up to 83% ([Budhwar et al. 2018](https://dl.acm.org/doi/10.1145/3209281.3209374)) [research]. The tasks, populations and holdouts differ. Still, 86% on pre-meeting first committee votes, scored a year ahead, is at least state of the art. Never market it comparatively [judgment].

## 4. Methods to insist on next

1. **Rolling-origin evaluation** (test on 2021, 2022, 2024 and 2025, each trained on earlier years only). Report the spread across years and pooled paired log-loss deltas, and accept a feature only at pooled z ≥ 3 [judgment].
2. **A hierarchical logistic model with a bill × party random effect.** The reason is not accuracy (latent factors already failed [repo]). It encodes "one unknown per party per bill" and gives correlated room-level probabilities. It also updates coherently: knowing one party-mate's position moves the others. That is the engine for the informant idea and for pooling in the contact log ([Bafumi et al. 2005](https://doi.org/10.1093/pan/mpi010)) [research/judgment].
3. **Selection.** Recorded votes are a non-random subset ([Hug 2010](https://www.cambridge.org/core/journals/british-journal-of-political-science/article/abs/selection-effects-in-roll-call-votes/0454CD5DB7FD5CDC5639116098B81A57)) [research]. Voice-vote kills and bills never heard are censored. A Heckman correction lacks an exclusion restriction. Instead, model the bill's fate directly as competing risks (not heard / stricken / voice-killed / recorded / reported) and score it with bill-level log loss [judgment].
4. **Conformal prediction** would give a {yes, no, both} set with per-class coverage ([Angelopoulos & Bates](https://arxiv.org/abs/2107.07511)). Exchangeability fails across years, so it needs weighted variants ([Barber et al.](https://arxiv.org/abs/2202.13415)) [research]. With two classes it mostly repackages the existing thresholds, adding a coverage guarantee but no accuracy [judgment].
5. **Co-patrons.** The within-patron test (112 vs 31, p ≈ 6×10⁻¹² [repo]) removes patron-level confounding, but not bill-level selection (strong bills recruit co-patrons) or the dating leak above. In Congress, cosponsorship mainly predicts whether a bill gets considered at all ([Wilson & Young 1997](https://www.jstor.org/stable/440289)) [research]. Claim "observed within-patron association", not an effect.

## 5. Ranked recommendations

1. **Pre-register the 2026 score:** log loss, Brier, accuracy, other-party accuracy, label calibration and room-majority accuracy, all with bill-clustered CIs. Freeze thresholds and slices first.
2. **Relabel 2025 as validation** in the log and the docstring.
3. **Make paired, bill-clustered log loss the acceptance rule.** Retire the hardest-third target and keep it only as a fixed-set diagnostic.
4. **Date the co-patrons** from the introduced bill, then rerun the within-patron test.
5. **Build the bill-fate competing-risks model plus a correlated room model.** Stop multiplying member probabilities.
6. **Run the informant backtest; pre-register Brier-scored contact-log pooling for 2027.**

## Agreement and disagreement

- **Lobbyist.** Agree: freeze the model and lead with the bill. Disagree on "pivotality is exact arithmetic": the number of votes needed is exact, but whether a given member is pivotal depends on correlated, uncertain votes. Co-patrons as an asymmetric bet is fine once the dating check passes.
- **Marketing officer.** Agree: spend 2026 deliberately and never quote "86%" alone. Add that "95% on the most confident 67%" must always carry the 67% alongside it.
- **Genius.** Agree on censoring and on "~2 unknowns per bill"; the design effect of 4.6 confirms the latter. Correction: the 96.4% informant figure copies a party-mate's *actual* ballot from the same roll call, so it is a ceiling for a perfectly honest informant, not an expectation. Agree the estimand should move to bill fate and room outcome.
- **Mathematician.** No memo yet. `bounds.out` independently confirms the design effect, the CIs and the hard-third arithmetic.
