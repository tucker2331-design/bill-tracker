---
tags: [testing, california, ca, replication, multi-state, calibration]
updated: 2026-11-19
status: active
---

# California — Virginia's tests re-run (2026-11-19)

Owner: "you ran the stats for cali … the same as the other sites?" — not until now. Same protocol as
[[testing/pa_replication]]: inputs known on the filing day, fit on earlier sessions, score on a later one.

## Data — collected once, from the bulk host only
`tools/calibration/ca/fetch_session_tables.py` pulls ONLY the needed tables (bills, history, versions, authors,
legislators, summary + per-member votes, committees, hearings, motions) out of Legislative Counsel's yearly zips with
HTTP range requests — the zip directory, then each table's bytes, CRC-checked — never the 1+ GB of bill text.
Sessions 2015-16 … 2025-26 (six): ~600 MB of tables in ~1 minute of requests. Public domain (Gov. Code §10248.5).
`ca_frame.py` → 27,559 bills, **3.15 M member votes** (every committee and floor roll call; 0 votes without a party).
`ca_stats.py` → `results_ca.json`. Held out: A fit 2017–21 → score 2023–24; B fit 2017–23 → score 2025–26 (floor work
ended 31 Aug 2026; settled).

**California's shape is different, and it decides how to read every number below:** Democrats held both houses in
every session here (no flip to learn from), and **the first committee is not the gate** — 86–88% of referred bills
get out of it (Virginia and Pennsylvania: roughly a third). Bills die later, mostly in Appropriations.

## Results, test by test
| test | Virginia | Pennsylvania | **California** | verdict |
|---|---|---|---|---|
| bill fate — out of the first committee (AUC) | 0.80 vs baseline 0.68 | 0.78 / 0.81 vs 0.69 / 0.67 | **0.705 / 0.763** vs baseline 0.690 / 0.755 | **weak** — 87% get out; little to predict |
| bill fate — becomes law (AUC) | — | — | **0.612 / 0.656** vs 0.581 / 0.602 (log loss 0.662 vs 0.675) | **weak but real** |
| law, updated with the first committee's roll call | — | — | 0.623 → **0.646** / 0.635 → **0.661** | small gain |
| kill points (2023–24 / 2025–26) | subcommittee is the gate | 73% die in the first committee | law **40% / 43%** · vetoed 6% / 5% · never referred 6% / 3% · first committee **13% / 12%** · origin Appropriations **14% / 15%** · second-house Appropriations **12% / 12%** · other later steps 10% / 10% | **differs** — Appropriations (the suspense file) kills as many as the policy committee |
| room memory: same subject died before → dies again | 80% vs 26% (OR 10.8) | 91% vs 37% (OR 18.2) | **30% vs 21% (OR 1.65)**, n 769 | **replicates, much weaker** |
| author effect: split-half r · session-to-session r · lift SD | 0.46–0.51 · — · 14–16 pts | 0.53 · 0.46 · 10.6 pts | **0.71–0.79 · 0.75 / 0.67 · 16.8 pts** | **replicates, stronger** — the author matters most in CA |
| committee seat (author sits on the first committee) | subcommittee seat +14 | +20 maj / +6 min; within sponsor +13.5 | **+4.8 maj / +6.7 min; within author +4.4** (407 better, 240 worse) | **replicates, smaller** |
| member votes, first committee roll call: accuracy | 85.9% vs always-yes 73.9% | 89.2% vs 87.5% | **88.2% vs 88.3%** (AUC 0.762 / 0.775) | **differs** — 88% of CA committee ballots are AYE; the threshold never flips |
| member votes, confident calls | 95%+ on 67% | 97.7% on 67% | **94.3% on 77–78%** | **replicates** |
| other-party crossover (AUC) | 0.744 | 0.822 | **0.676 / 0.675** | **weaker** |
| party position: does the minority caucus vote NO on the floor? (AUC) | — | 0.875 (0.888 with earlier votes) | filing facts only **0.61**; with the caucus's committee votes on the bill **0.966 / 0.964** | **replicates once votes are known** |
| clock | silence priced by week; crossover cliff | steady decay, no cliff | **95% of 5,524 deaths fall on 1–3 Feb** — two-year bills die by the constitution's deadline (Art. IV §10(c)) | **differs** — CA's clock is the constitution |

### What carries the bill-fate model (AUC lost when removed, 2023 / 2025, "out of first committee")
Standing (majority party / committee-authored) **−0.032 / −0.025** — the only input that clearly matters; co-authors
−0.009 / −0.004; first-committee record −0.009 / −0.005; everything else (fiscal flags, author record, tried-before,
topic, volume, tenure) within ±0.006 held out. Boosted trees: 0.734 / 0.714 — unstable, not better.

## What this means for the CA product
- **Don't show a first-committee probability in California.** It is ~87% for everyone and the model barely beats
  "party of the author". Show the author's own record instead: it is the strongest, most stable signal measured
  (split-half r 0.71–0.79, session-to-session 0.67–0.75) — a lobbyist reading "this author gets 9 of 10 bills out"
  is reading a real fact.
- **The question that matters is Appropriations.** 26–27% of all bills die there (origin + second house) — twice the
  12–13% that die in their first policy committee. The suspense file decides by fiscal cost, which the filing-day
  flags only hint at.
- **Party position is readable once the committee has voted** (0.96): after a bill clears committee, the minority's
  committee ballots predict its floor stance almost perfectly. Before any vote, it is weak (0.61).

## How to raise California's accuracy
1. **The Appropriations analysis.** `BILL_ANALYSIS_TBL` (already in the daily export; text in `.lob` files) carries
   each committee's analysis, including the fiscal estimate the suspense file runs on. A structural cost field from
   it, at the Appropriations step, is the single most likely gain for "becomes law". (Reading the analysis text is a
   Standard #3 question for the owner, as with PA titles.)
2. **Stage-by-stage, not filing-day only.** Each later step adds information (the committee roll call added +0.02–0.03
   to "law"; the caucus's committee votes took party position from 0.61 to 0.96). Re-score at each step.
3. **The author as a first-class input with shrinkage** (the record is strong descriptively but noisy per author when
   held out).
4. **Contested ballots only** for member votes (12% NOE/ABS): measure and show predictions only where a caucus
   splits, as in PA.

## Not run on California
| test | why |
|---|---|
| bill mix / majority flip | no flip: Democrats held both houses every session 2015–2026 |
| chair effects | historical chairs not in pubinfo; Open States has the current session only (could test 2025–26 alone) |
| enacting clause / venue shopping | the "amend / add" wording is in the bill text (`.lob`), not a structural field |
| money and vulnerability | campaign finance not ingested (Virginia's result was null) |
