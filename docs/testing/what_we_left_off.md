---
tags: [testing, war-room, design, trust, nulls]
updated: 2026-09-22
status: active
---

# The drawer — what we checked and left off, and the stat that proves why

Owner, 2026-09-22:
> *"its also worth noting weve disproved a lot more then we proved which is useful in its own right. im
> imagining maybe a little drop down or pop up that says everything statistically validated and something
> about what we are intentionally not showing and the stat proving why. a drop down of course bc its not
> relevent unless a lobbyist thinks one of those stats might be and is looking for it."*

**This turns the null results into the product's best trust asset.** A lobbyist who wonders *"shouldn't you
be showing me donor money?"* opens the drawer, reads `+3.9 points`, and stops wondering. Closed by default,
because the question only exists for the person who has it.

## The framing fact that explains the whole list

Same bill text filed in both chambers, one majority patron and one minority. When the minority copy dies,
**it dies on the clock 69% of the time and on a vote 31%** (n=125, [[failures/assumptions_audit|#136]]).

**Bills mostly die by never being heard.** That is why measure after measure aimed at the roll call came back
empty — we were counting votes in a process that is decided by the calendar. It belongs at the top of the
drawer because it is the reason the list below is as long as it is.

## On the page, and what earned it

| element | the test | result |
|---|---|---|
| Patron's party | identical text, both chambers, one patron each side | majority won 257 of 317 discordant pairs — **OR 4.3** |
| Which room | same idea, same chamber, **same year**, different committee | **+18 pts**, p = 2.7e-04 |
| The bill's recorded state | every state counted, ever-in-state | continued 12 of 1,367; tabled 13 of 1,303 |
| How often the room votes no | 25 rooms, committee + subcommittee roll calls, 2026 | **4.0% → 34.7%** |
| Patron on the subcommittee | within patron × subject | **+11 pts** (full committee alone −2, p = 0.33) |

## Tested, and not on the page

| the question a lobbyist would ask | the answer |
|---|---|
| Is a member in a close district easier to move? | **r = +0.00** (n = 46) |
| Do donors move votes on the donor's own issue? | **+3.9 pts** within-member |
| Does getting the chair on side help? | **−1.4 pts** vs a rank member *of the chair's own party*, p = 0.98 — **we published the opposite and withdrew it** ([[failures/assumptions_audit|#135]]) |
| Do members trade votes? | **−4 pts**, wrong direction, p = 2.9e-05 |
| Are there blocs that move together? | 132 significant pairs → **1** once chance used FOLLOW rates |
| Is any member pivotal? | observed **5.2%** vs a party-line null's **6.9%** |
| Are there undecided members? | collapses into plain defection rate, **r = 0.92** |
| Do busy legislators do worse? | **r = +0.02** |
| Will our bill pass? | the whole panel adds **+0.020 AUC** over patron party alone, and the top decile does not move |
| Does a member who strays on a subject keep straying? | yes, 76% vs a 41% null — but a flippable target exists in **0.4%** of rooms |
| Does a substitute mean a rewrite? | **withdrawn**, replicates at r = 0.25 |
| Are some subjects more partisan? | **withdrawn**, p = 0.690 |
| Is being re-docketed a signal? | **retired** — surviving the first meeting is the news, and the history already shows it ([[testing/redocketing]]) |

**Withdrawn items stay listed.** A page that silently deletes its retractions is worth less than one that
shows them, and the two we withdrew are both cases where a wrong control group produced a large, exciting,
false number — which is exactly what a reader should know we are capable of and now check for.

## Design

Collapsed `<details>`, grey, **no colour at all** — see the correction in [[testing/bill_states]] for why this
surface spends none. Two tables, one template per row: *question → measured answer*. No prose per case (P25).

**Open:** the drawer is currently hand-maintained HTML. It should render from one data file so a retraction
in the vault cannot disagree with what the page says — the same failure mode as
[[testing/calibration_ledger]] drifting from the pages it indexes.
