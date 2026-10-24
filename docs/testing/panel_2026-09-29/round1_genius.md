# Round 1 — the Genius: stop predicting ballots, start routing information

Labels: **[R]** from the repo · **[W]** from research (linked) · **[M]** my own computation on repo data (method stated) · **[C]** conjecture.

## 1. The premise I distrust most: the ballot as the unit of prediction

- **The sample is censored.** When the minority-patron copy of a twin bill dies, it dies "on the clock 69% of the time and on a vote 31%" (n=125) [R, `what_we_left_off.md`]. Of 1,346 continued bills, 25 ever moved again, and 0 of 333 continued out of 2024 got any 2025 action [R, `continuance.md`]. A first-vote model only covers bills that reached a roll call, which are the minority of deaths.
- **Ballots are not independent.** With each party's position known, accuracy is 97.3% [R]. So ~11 of the 14 missing points are one unknown per (bill, party): 17,553 ballots, but only ~2 × 1,624 real unknowns [R]. Intervals should be clustered by bill.
- **Individual accuracy barely moves outcomes.** For "will our bill pass?", the member panel adds **+0.020 AUC** over patron party alone. Pivotal members: 5.2% observed vs a 6.9% party-line null. A flippable target exists in **0.4%** of rooms [R, `what_we_left_off.md`].

HB 1515 shows the effect. The bill is continued (12 of 1,348 continued bills later reached a floor vote), yet the top of its War Room is five per-member Toss-up/Leans labels [R, v11 mockup]. The screen is precise about the stage least likely to decide the bill.

## 2. What the plateau numbers say

- **97.3% ceiling:** the gap is about two bits per bill, not 17,000 small facts [R].
- **75% twin concordance, and the model is already at the identical-bill oracle on the other party** [R]: past the bill content, what's left is the room, the people and the day. That is social information.
- **Hardest third at 67.8%:** 72% of it is other-party ballots, 69% subcommittee; mixed splits have AUC 0.58 [R]. The residual is small rooms where a caucus hasn't shown its hand.

**The key number [M].** I took each bill's first non-floor roll call from `content_votes_cache.pkl` and guessed every member's vote by copying **one randomly chosen party-mate** (exact expectation over all pairs). Result: **96.4% on 2025** (1,530 first votes, 16,117 ballots), **95.8% on 2024**. The party-majority ceiling on the same rows is 97.4% / 97.2%. My row set is a little smaller than the model's 17,553, so the figure is approximate. The point holds anyway: **one true answer per party per bill would beat all ~35 modelling approaches.** The signal is in what people say, not in records. The step change is **information acquisition**, and the model's new job is to route it and fuse what comes back.

## 3. Non-obvious ideas, each testable

**A. "Who to ask," not "who to work on" (value-of-information routing).** For each bill, name the party whose position is most uncertain. Then name the member whose answer best reveals that caucus: the patron, or the party-mate in the room with the lowest defection (defection is a stable trait, r = 0.68 year to year [R, `persuadability.md`]).
*Test now, with data on hand:* rerun the informant backtest with a *chosen* informant against a random one (96.4%), on 2024 then 2025, and on the hardest third.
*Caveat [C]:* what an office says is not how it votes. 96% is the ceiling for an honest informant.

**B. The contact log as scored forecasts, pooled with the model.** "Dana R., 28 Aug · Lean no" [R] is already a forecast. Formalise it, Brier-score each volunteer, weight by track record, and pool with the model's log-odds as the prior. In the Good Judgment Project, skill persisted (r = 0.65 year to year) and aggregation improved Brier scores (0.166 individual → 0.146 aggregated for superforecasters) [W, [AI Impacts on GJP](https://aiimpacts.org/evidence-on-good-forecasting-practices-from-the-good-judgment-project/)].
*Test:* pre-register for 2027; score model vs model+team on the hardest third.

**C. Predict the bill's fate tree; show levers, not ballots.** A competing-risks model: never heard / stricken by the patron / voice-killed / recorded vote / reported. Score it by bill-level log loss against patron party alone. On top, show levers already validated by within-unit designs [R]:
- co-patrons, within the same patron: 20.4% vs 6.9% unanimous death (p≈6×10⁻¹²)
- same idea in a different room: +18 points
- patron sitting on the subcommittee: +11 points
- a minority patron's bill refiled by a majority patron: 41% vs 6%

Each renders as a template with k of n (P25/P26). That makes the model an instrument, not an oracle.

**D. Detect two-sided fights to crack mixed splits.** Butler and Miller used position disclosures in Colorado, Nebraska and Wisconsin (26,000+ bills). One-sided lobbying *for* a bill went with **+11 points** of enactment and lobbying *against* with **−26**; two-sided lobbying lowered enactment. Lobbying predicted **agenda progress, not committee votes** [W, [Butler & Miller](https://www.davidryanmiller.com/files/LobbyingImpact.pdf)]. That is consistent with "bills die on the clock." I conjecture mixed splits (AUC 0.58) are mostly bills with organized interests on both sides [C]. Virginia disclosure covers expenditures, not bill positions [W, [Va. Code §2.2-426](https://law.lis.virginia.gov/vacode/title2.2/chapter4/section2.2-426/)]. A Virginia test must therefore use position lists that associations publish *during* the session. End-of-session scorecards pick contested votes after the fact, so they leak the outcome.
*Test:* 2025 mixed-split AUC with and without a "positions on both sides" flag.
*For the 50-state plan:* Wisconsin publishes every bill each principal lobbied, back to 2003–04 [W, [WI Ethics Commission](https://ethics.wi.gov/Pages/Lobbying/LobbyingOverview.aspx)]. Illinois witness slips record per-bill support and opposition [W, [Kistner & Pomirchy 2026](https://onlinelibrary.wiley.com/doi/10.1111/lsq.70057)]. **Weigh structural position disclosure when choosing the next state**; its ceiling may exceed Virginia's [C].

**E. Uplift, not likelihood.** "Likely yes" points volunteers at *sure things*. Uplift modelling targets only *persuadables* [W, [uplift modelling](https://en.wikipedia.org/wiki/Uplift_modelling)]. In a randomized Michigan experiment, constituent contact raised support ~**12 points** [W, [Bergan & Cole 2015](https://link.springer.com/article/10.1007/s11109-014-9277-1)], echoing New Hampshire [W, [Bergan 2009](https://journals.sagepub.com/doi/abs/10.1177/1532673X08326967)]. The product already collects volunteers' districts [R]. Rank members by persuadability × org constituents in the district, and aim at the members who shape the caucus position, since individual flips are rarely pivotal [R].
*Test:* only a randomized 2027 contact pilot, with the org's consent, can measure uplift. That is also the impact evidence grant funders want [C].

## 4. Ranked recommendations

1. **Freeze feature hunting.** Score the locked 2026 test once. The ceiling is measured [R].
2. **Change the scoreboard.** Use bill-clustered intervals and bill-level fate log loss. Add **surprise precision**: accuracy where the model *disagrees* with the "vote with your party; majority bills pass" rule a volunteer already applies. Retire "95%" as a goal: 95%+ is already reached on the most confident ~67% [R].
3. **Run the informant backtest (A) now.** It is cheap and decides the member module.
4. **Restructure the War Room.** Fate and levers on top (C); members become "who to ask / who you can reach," keeping the calibrated labels.
5. **Pre-register 2027:** scored forecasts (B) plus a randomized contact pilot (E).
6. **Pilot interest-position data (D)** and factor it into next-state choice. The ~$4 Haiku read [R] can come later, as a party-position feature.

## 5. Where the others will be too conventional

- **Lobbyist:** will keep the member as the unit. The pivotal and flippable numbers say caucus and calendar decide; the lobbyist's real asset is *asking*.
- **Mathematician:** will propose a better model (hierarchical IRT). Member×bill factors on 526k ballots already failed [R]. The ceiling is informational.
- **Statistician:** will fix clustering and leakage but keep recorded-roll-call accuracy as the estimand. The bigger bias is censoring.
- **Marketing officer:** will want "95% accurate." That is the confident-subset twin of the per-slice-threshold trap already rejected [R]. Funders buy *votes moved per volunteer hour*, and only E measures it.

**Bottom line [C]:** public records are exhausted. The next step is a system that gathers and scores the two missing facts per bill from the people who hold them.
