---
tags: [testing, calibration, content, members, war-room, prediction]
updated: 2026-09-24
status: active
open_loop: Research result, NOT a feature. Before anything reaches the War Room — (1) owner's go/no-go on member-level prediction (predictive_lane Tier 3; owner previously rejected a yes/no/maybe sort), (2) show RANK not probability (low end is overconfident), (3) re-run on full bill text once fetched (summaries are the proxy), (4) widen coverage — content history exists for only ~13% of votes.
---

# Controversy measured from content — per bill, per party, per legislator

> ## ROUND 2 (2026-09-25) — accuracy, and every ingredient added and removed
> Owner: *"whats the accuracy? is the info you are inputing the important info? how does the accuracy
> changing adding and removing."* Three new ingredients (co-patrons from the legislator's party; the
> legislator IS a patron; **earlier roll calls on this same bill**). `content_votes_ablate.py`. Held out on
> 2025–26, threshold chosen on training data only.
>
> **Two leaks fixed first:** (1) 1,816 roll calls re-carried into the next session's file with the prior
> year's DATE — the same vote sat in 2024 training and 2025 test; (2) the integer-mask scoring bug, a second
> time (it printed "0% support" on first votes; true 57%).
>
> | population | ranking (0.5 = guess) | balanced accuracy | accuracy | "always guess the common answer" |
> |---|---|---|---|---|
> | all votes (n = 372,940) | 0.907 | 83.6% | 90.3% | 84.6% |
> | other-party legislators | 0.889 | 83.6% | 83.6% | 71.1% |
> | **other-party, FIRST vote on the bill** (n = 18,197) | **0.716** | **65.3%** | 61.4% | 56.8% |
>
> **Remove one ingredient (other-party all / other-party first vote):** earlier votes on this bill **0.889 →
> 0.699** / 0.716 → 0.642 · venue 0.905 / **→ 0.575** · co-patrons 0.885 / 0.699 · bill controversy 0.886 /
> 0.699 · legislator on content 0.888 / 0.709 · party on content 0.888 / 0.713 · **general defection rate: no
> change (0.888 / 0.718)**.
>
> **Read plainly:** most of the headline accuracy is *how they already voted on this same bill* — useful
> (stage tracking) but visible in the vote record. **The valuable prediction — the first vote, before anyone
> has voted — is 0.72 ranking / 65% balanced.** Venue matters most there; each content ingredient adds
> ~0.01–0.02; a legislator's general habit of crossing adds nothing.

Owner, 2026-09-24: *"one of the biggest confounds is simply text at all… if there was a way to know just how
controversial something is historically and relative to individual politicans it would be the golden ticket…
its based on more then one stat."*

`tools/calibration/content_votes.py` · plan written into the docstring **before** any result was seen.

## The test

**Unit:** one legislator's vote on one substantive roll call (subcommittee, committee or floor) on an HB/SB,
2020–2026 except 2023 (no summaries in the source). **1,333,713 votes.** Direction read from the motion text —
a *yes* on "laying on the table" counts as a vote **against** the bill.

**Predict before the vote**, from four layers, each only from **earlier years**:

| layer | what it measures |
|---|---|
| A — what we already knew | same party as the patron · majority/minority · the legislator's general rate of breaking with their party · venue |
| B — bill controversy | how opposed the 10 most similar earlier bills were (official summaries, title stripped) |
| C — the party on this content | how the legislator's **party** voted on those similar bills |
| D — the legislator on this content | how **this legislator** voted on them, relative to their party |

Fit on 2021/2022/2024, **scored on 2025/2026, which the fit never saw.**

## Result

**Where it matters — legislators of the OTHER party, on contested bills, with a record on similar content
(n = 7,040):**

| model | AUC |
|---|---|
| A — everything we knew | **0.508** — a coin flip |
| + B bill controversy | 0.614 |
| + C party on this content | 0.679 |
| + D this legislator on this content | **0.699** |

**Ranked before the vote, no outcome filter** (opposite-party legislators with a content record, n = 17,467):

| fifth | content model: backed the bill | baseline: backed the bill |
|---|---|---|
| lowest | **12%** | 55% |
| 2 | 34% | 53% |
| 3 | 82% | 40% |
| 4 | 75% | 63% |
| highest | **90%** | 81% |

**Everything we knew before cannot tell you WHICH opposite-party legislator will cross. How that party and that
person voted on similar content can.** Most of the lift is content-and-party (B, C); the individual adds a
smaller, real increment (D: +0.020 AUC; coefficient z = +13.3 — the strongest single term in the model).

## What it is not, stated in front

- **A ranking, not a probability.** The low end is overconfident: the bottom fifth is predicted ~39% and backs
  the bill 12%. Display must never print a percentage chance (P20b; [[ideas/predictive_lane]] Tier 3 gate).
- **Coverage is thin: content history exists for ~13% of votes** — similar earlier bills often died on voice
  votes with no recorded roll call.
- **Summaries, not full text.** Full text is the next step (keyless LIS blob; owner's OK needed for the fetch).
- **Owner's standing objection applies:** a yes/no/maybe sort was rejected on 2026-09-14. This is research; how
  (or whether) it surfaces is his call.

## Traps caught on the way

1. **Open States' vote labels are unusable** — every 2024 roll call is classified `passage` (including
   subcommittee recommendations), every 2025 one `[]`. Venue and direction come from motion text.
2. **Open States DOES carry committee and subcommittee roll calls** for these years (16,708 committee, 7,958
   subcommittee), correcting the vault's earlier "0 committee roll calls" note for this corpus.
3. **A scoring bug that looked like a finding:** an integer used as a mask index scored rows 0 and 1 ten
   thousand times and printed "0% support". Masks are now explicit booleans.
4. **`party_map.json` lists three Republicans as Democrats** (Les Adams, Tim Anderson, John McGuire). Nothing
   read it; quarantined. The files that ARE used verified 135/135 and 137/137.
5. **2.6% of votes dropped** — six legislators absent from both party sources (Hashmi, Guzman, Morrissey,
   Brewer, Campbell, Jay Jones). Counted, not guessed.
