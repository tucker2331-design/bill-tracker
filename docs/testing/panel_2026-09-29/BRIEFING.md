# Panel briefing — Virginia bill tracker "War Room": the predictive-modeling question

You are one of five experts convened by the owner, Tucker Ward. Read this briefing fully, then read the files listed in
"Required reading" (they are in the repo at /Users/tuckerward/Documents/Projects/bill-tracker). Research outside
sources where your expertise calls for it (academic literature, industry practice) and cite them with links. Never
invent numbers: every number you use must come from the files below or from a source you cite.

## The product
- A Virginia General Assembly bill tracker for **advocacy organizations staffed largely by volunteers** (not expert
  lobbyists). Data: Virginia LIS (official), Open States (public-domain copy of older records), Census, LIS legacy
  pages. A React web app reads a Google Sheet written by Python workers; a Cloudflare Worker gates everything behind
  Google sign-in plus a team list (the app is private for now).
- The **War Room** is the per-bill screen: where it stands; "who to work on" (each committee member with a guess of
  their first vote); the room's record; the team's position and contact log; "tried before" (similar bills in
  Virginia and other states). Current mockup: `scratchpad/warroom/warroom-hb1515-v11.html` (HB 1515, a data-center
  moratorium bill, continued to 2027 in House Rules, Studies Subcommittee). Published privately at
  https://claude.ai/artifact/311hd8hv1eaQpSmntDQDVE.
- Owner's standing rules: no prose written per case (templates only); grey UI, colour only for standing meanings;
  every claim labelled as sourced / derived / asserted; "bank-grade" reliability; zero routine maintenance; must scale
  to 50 states. **Commercial use is blocked** until a data arrangement with DLAS (the Virginia legislative agency)
  exists — LIS terms say "personal and non-commercial use only". Grant funding is being explored.
- Owner's modelling goals over time: "break 95%"; get the hardest third above 80% ("start with over 80%"); make it
  usable ("who they need to target where and why without writing too much text"); dig like a real statistician;
  public attention/news as a determinant (from the federal-level literature). Owner does NOT want to pay for an LLM to
  read every bill yet, and doubts paid APIs are the right long-term answer. The team contact log is a separate,
  future product item — not part of this modelling question.

## The model (as it stands)
- Target: each committee/subcommittee member's **first recorded vote** on a bill (the first vote a bill hits).
- Model: numpy gradient-boosted trees (depth 6), ~120 inputs: party and majority standing, venue, the room's record,
  the patron's record, the member's record in this room / on this patron's bills / on this subject / on similar bills,
  co-patron counts, companion bill, bill history before the vote, text-derived party lean of the summary, ideal points,
  Census district composition, room aggregates.
- Protocol: train 2019–2022 (+2024), choose settings on 2024, score ONCE on 2025; 2026 locked (never scored). 2023 was
  missing from Open States and was later added from LIS legacy files (no gain). 2017–18 excluded (committee votes
  lack names).
- **Results on 2025 (17,553 first-vote ballots):** 86.1% right overall (always-yes baseline 73.9%); other-party
  members 80.2%; party position (each party's majority) right 84%; "hardest third" (the third of ballots the model is
  least sure of) 67.8%.
- **Calibration:** calls labelled "Likely" (≥80% or ≤20%) are 70% of ballots and right 94 in 100; "Leans" (60–80%)
  20% and ~70 in 100; "Toss-up" 10% and 57 in 100. 95%+ accuracy is reached on the most-confident ~68% of ballots.
- **Ceiling measurements:**
  - If each party's position were known perfectly, member-level accuracy would be 97.3% → individual defection costs
    ~3 points; ~11 of the 14-point gap is predicting each party's position on the bill.
  - 734 near-identical bill pairs (House/Senate twins) voted separately: both parties' positions match only 75%;
    other party 80–81%; same venue and patron standing (75 pairs) 87%/91%. The model already matches this
    "identical-bill oracle" on the other party.
  - Vote SHAPES (2025 bills): everyone-for 48% (AUC 0.83), straight party line 24% (0.80), everyone-against 9%
    (0.85), **mixed split 19% (AUC 0.58 — near unpredictable)**.
- **Consensus kills** (everyone votes the bill down at its first vote): 9.8% of first votes; 73% in subcommittees;
  tabled 32%, stricken 30% (usually the patron pulling it), continued 17%, passed by indefinitely 9%. **Co-patrons:**
  in subcommittee, no co-patrons → ~20% die unanimously vs 6.9% with any co-patron, 4.3% with 5+; within the same
  patron, 20.4% vs 6.9% (112 of 143 patrons, sign test p≈6×10⁻¹²). A bill-level kill predictor (AUC 0.85) flags 10%
  of bills of which 36% die (4× base) — but even the riskiest die only ~1 in 3, so member-level guesses stay "yes".
- **Everything tried that did NOT beat the model** (all year-ahead, within ±0.6 of 86%): ~25 feature families across
  rounds 1–4; co-sponsorship relationships (plain and size-weighted); member × bill latent factors (first votes; and
  text-linked ideal points from 526k contested ballots); deeper trees (depth 8–10); regime-matched training;
  per-chamber models; logistic regression and blends; two-level (bill kill risk → member); label cleaning; adding
  2023; district × raw topic; agenda position; committee chairs 2019–2025 (validated); Cardinal News coverage;
  legislative attention (same-topic filing by party); personal profile (member's topic filing, tenure, effectiveness).
- **Descriptive finding supporting "public attention":** bills covered by Cardinal News before the vote are more
  contested (57% yes vs 74%) and the model is much worse on them (76.4% vs 86.4%) — but only 3.3% of ballots are on
  covered bills.
- Sources blocked or unavailable: Virginia Mercury, Blue Virginia, WRIC, WSLS, Virginia Business (robots.txt bars
  Anthropic); no per-bill public comments; no floor transcripts; Google Trends has no permitted API. GDELT bulk news
  data (people/places/themes/tone per article, no text) is being pulled for the 2025 session now.

## Required reading (in the repo)
1. `docs/testing/first_vote.md` — the full research log, all rounds (READ IN FULL).
2. `docs/ideas/war_room_scoping.md` — what the War Room is for and prior decisions.
3. `docs/knowledge/lis_tos_commercial_use.md` — the terms-of-service constraint.
4. `docs/state/current_status.md` — what is active and pending.
5. `docs/design/information_display.md` — display rules (P20–P25 etc.).
6. `/private/tmp/claude-501/-Users-tuckerward-Documents-Projects-bill-tracker/d2c029e9-acd9-410e-81ec-5347fd755620/scratchpad/warroom/warroom-hb1515-v11.html` — the current mockup.
Optionally skim `tools/calibration/first_vote.py` for the model and features.

## The question for the panel
What theoretical role is the predictive model filling in this product? Is the modelling effort pointed at the right
target? Assess the stats and methods, the findings, and the plateau at 86% / 67.8%. Then: how should the project move
forward to improve it — and what, if anything, should change about what is predicted, how it is measured, or how it
is shown to a volunteer lobbyist?
