# Round 1 — Chief Lobbyist: position memo

Labels: **[repo]** = from the project files · **[research]** = cited source · **[judgment]** = my professional read.

**Bottom line.** The model is good and finished. Stop tuning it. What's wrong is the question it answers and how the War Room shows it. A volunteer on Tuesday morning doesn't need to know "how will Delegate X vote?" to 86% accuracy. They need three things: is this bill alive, where is the majority, and which one or two offices can we still move. Point the product at those.

## 1. What job the model is actually doing

- **Triage, not forecasting.** "Likely" calls are 70% of ballots and right 94 in 100. "Toss-up" calls are 10% and right 57 in 100 [repo]. For a volunteer, that is a way to rule out 70% of the room: no calls needed there. That job is valuable, and the model already does it. [judgment]
- **Member-level accuracy is mostly party arithmetic.** Known party positions give 97.3%; ~11 of the 14 missing points are the party's position [repo]. A pro gets that from caucus and leadership, not individual modelling. [judgment]
- **The model predicts the vote before anyone lobbies, which is the vote we are trying to change.** In Bergan's randomized experiment with Michigan legislators, being targeted by constituent emails raised support by about 12 points ([Bergan 2009](https://journals.sagepub.com/doi/abs/10.1177/1532673X08326967)). Congressional staff say in-person constituent visits sway undecided members more than any other tactic ([CMF, *Citizen-Centric Advocacy*](https://rollcall.com/2017/02/13/report-shows-untapped-power-of-constituent-advocacy/)). So the right target is **persuadable × pivotal**, not "correct." A 95%-likely yes isn't worth a call. Neither is a vote that can't change the result. [judgment]
- **The model can't see how most bills actually die.** Full-committee kills are voice votes with no roll call [repo]. HB 1515 was continued on a voice vote, and 23% of bills in its room were never acted on at all [repo, mockup]. "Will the chair docket it at all?" comes before any member question. [judgment]

## 2. Which findings matter in the field

**Most valuable:**
1. **Co-patrons.** Within the same patron, no co-patrons meant a 20.4% unanimous-death rate vs 6.9% with one (112 of 143 patrons; p≈6×10⁻¹²); bipartisan co-patrons 5.3% [repo]. The persona is an org that *writes* bills [repo, `lobbyist_jtbd_ideation` §8a], so this is the most actionable finding in the log: it can be acted on before filing. The card's "why" agrees: no co-patrons costs −6 to −10 points per member, "the one factor an org can change" [repo].
2. **Consensus-kill warning.** In the top 10% flagged, 36% die, 4× the base rate [repo]. 30% of these kills are the bill being "stricken," almost always because the patron pulled it [repo]. In the field that means the biggest risk is often your own patron. What to do: confirm before the docket that the patron will present the bill. [judgment]
3. **Room base rates.** "12 of 1,348 continued bills later reached a floor vote" and "33% of majority-party bills reported" in Rules [repo, mockup]. For HB 1515, these are the most honest numbers on the screen and should be the headline. [judgment]
4. **Mixed splits.** They are 19% of bills and near-unpredictable (AUC 0.58) [repo]. That tells a volunteer where the whip work is.
5. **Attention = fight.** Bills covered by Cardinal News got 57% yes votes vs 74% for others, and the model was right 76.4% of the time on them vs 86.4% [repo]. It works as a flag, not as a feature.

**Interesting to researchers, useless to a volunteer:** the twin-bill oracle, ideal points, latent factors, the "hardest third" as a goal (a moving selection that Round 4 showed can be gamed [repo]), and the mockup's "Tested and left off" sheet of 14 r-values and AUC deltas [repo, mockup]. Move those to a methods page. [judgment]

## 3. What practitioners know that the data can't see

The log correctly names who sets lineups: caucus leadership, chairs, the Governor's office, agencies via fiscal impact statements, VACo/VML, stakeholder deals [repo]. I'd add: the patron's real intent (placeholder, message bill, "study it"), whether the chair has promised a hearing, and which locality or industry is in the room. On a data-center bill, counties are the swing stakeholder; the mockup's example note says as much ("wants to hear from county officials"). [judgment]

How to surface this within the owner's rules (templates only, structural data, no paid LLM, three-class labelling):
- **Make the contact log the whip count.** Each outcome gets a fixed field (committed yes / lean yes / undecided / lean no / no / won't say). Show it next to the model's label in the OURS zone (P20), never blended. A disagreement between model and team becomes a structural flag: no prose, just two cells that differ. [judgment]
- **Org-asserted "patron check" fields:** will present, seeking co-patrons, Senate companion planned. [judgment]
- **A public trace worth probing.** House committee pages say written comments received four hours before a meeting "will be available to the public from the meeting agendas" ([House committee page, via search index](https://virginiageneralassembly.gov/house/members/members.php?committee=H09); [HODSpeak](https://hodspeak.house.virginia.gov/)). The log says per-bill comments are "not published" [repo], so this needs a probe. If testimony can be counted per bill, it is the best public proxy for the stakeholder lineup. Owner's OK needed on load and terms. [research + judgment]
- There is field evidence that simply giving legislators information about their constituents changes their votes ([Butler & Nickerson 2011](https://isps.yale.edu/research/publications/isps11-016)). That supports the V3 idea: match each volunteer to their own legislators on the deciding committee. [research]

## 4. Ranked recommendations

1. **Freeze the member model.** Score the locked 2026 test once; fix the missing wording score on carried-over bills (it moves HB 1515's Democrats by +10 to +17 points) [repo]. The plateau is measured: the model matches the identical-bill oracle on other-party members [repo]. More rounds cost product time. [judgment]
2. **Make the bill the headline, not the member.** Top of the War Room: (a) room base rates, including whether bills in this room get acted on at all; (b) the vote-shape call where it is reliable: everyone-for, party-line and consensus-kill all score AUC 0.80–0.85 [repo]; (c) the consensus-kill warning. Members come second. [judgment]
3. **Re-sort "Who to work on" by what to do, not by prediction.** Three groups, using the existing labels plus exact arithmetic: *locked* (no call), *worth a call*, *unknown: find out*. Add pivotality, which is deterministic math and needs no amber flag under P20b [repo]: votes needed (3 of 5) against the current lean. On HB 1515, four Democrats lean yes [repo, mockup], so Kilgore's toss-up is not the pivot. The real question is whether Rules leadership wants the bill heard at all. [judgment]
4. **A "what you can change" checklist, built from the bill-level findings:** co-patron count, a bipartisan co-patron, Senate companion, patron committed. These are templated and structural, and they are the only levers the data says an org controls. [repo + judgment]
5. **Add a structured commitment field to the contact log, then measure what matters in 2027:** did Toss-up/Leans members who were contacted move, and did the org's bills win more? That is the metric I'd fund. [judgment]
6. **Probe the House written-testimony trace** (owner OK required). [judgment]
7. **LLM bill reading last.** About $4 on Haiku [repo]: cheap, but it has leakage risk and can only be tested cleanly in 2027 [repo]. One test, not a strategy. [judgment]

## 5. Where the statistician will disagree, and why I hold

- **"Co-patrons are correlation; patrons recruit them for their strongest bills."** True, and the log says so [repo]. But a co-patron costs almost nothing and the same-patron gap is 13.6 points [repo]. Label it an observed pattern and act on it anyway: an asymmetric bet. [judgment]
- **"Persuadability and pivotality aren't validated; accuracy is the only honest metric."** Pivotality is exact arithmetic. For persuadability, the honest move is to measure it next session with the contact log, not to keep optimizing a number that ignores intervention. [judgment]
- **"Lift the hardest third with GDELT or an LLM."** The hardest third is 72% other-party ballots and 69% subcommittee votes [repo]. That is exactly where lobbying happens. Predicting it perfectly would mean predicting the outcome of our own work. Hand those members to the whip count and show them as unknown. "Unknown" is useful information: it tells the volunteer where to spend Tuesday morning. [judgment]
- **"Keep the member model as the centrepiece; it's the most rigorous piece."** Rigorous isn't the same as useful. Lobbying mostly subsidises allies rather than converting opponents ([Hall & Deardorff 2006](https://www.cambridge.org/core/journals/american-political-science-review/article/abs/lobbying-as-legislative-subsidy/AE4B5D8AB9C2487BB78C2A51BB53E03F)). The War Room should show who our allies are and what they need, with the model underneath as triage. FiscalNote itself shows bill-level floor scores, not member guesses ([FiscalNote](https://fiscalnote.com/blog/bill-forecasts-policynote-feature)). Calibrated member triage plus the org's own whip count would be new. [research + judgment]
