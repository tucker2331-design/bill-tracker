---
tags: [testing, calibration, war-room, committee, history, lever]
updated: 2026-09-23
status: active
open_loop: CONTENT VERSION SUPERSEDES TITLES (2026-09-24, tools/calibration/summary_memory.py). Before the War Room, (1) re-measure on FULL bill text once fetched (summaries are a proxy), (2) calibrate display thresholds on the summary-similarity scale (not the VA-companion text scale).
---

# Committees remember ideas

> **SUPERSEDED ON CONTENT, 2026-09-24.** Owner: *"the titles mean nothing they are performative and often hide
> the real controversial text."* Re-tested on the official LIS **summary as introduced** (already in the cached
> Open States zips, title text stripped out), each bill against its most similar earlier summary,
> `tools/calibration/summary_memory.py`. Same first committee, patron standing held fixed:
>
> | summary similarity | room killed it before → dies again | room cleared it before → dies | OR | …with titles DIFFERENT |
> |---|---|---|---|---|
> | 0.80+ | 94.5% | 42.9% | 20.4 | 93% vs 30%, OR 23.6 |
> | 0.50–0.80 | 90.1% | 29.2% | 20.2 | 91% vs 33%, OR 16.9 |
> | 0.30–0.50 | 91.2% | 45.9% | 11.5 | 92% vs 46%, OR 12.7 |
> | 0.15–0.30 | 82.6% | 29.0% | 11.2 | 80% vs 31%, OR 8.8 |
> | 0.05–0.15 | 78.0% | 46.0% | 4.1 | 76% vs 47%, OR 3.6 |
>
> **It holds when the titles differ, so it is the content.** The room effect is far clearer than on titles:
> similarity ≥ 0.15, **same committee OR 14.9 [9.3–23.9] vs different committee 3.2 [2.1–5.0], z = +4.71,
> p = 2.5e-06** (titles gave p = 0.013). Stable across eras: 16.7 (2021–22), 16.2 (2024–26). **The War Room
> tag becomes `Same committee · ~5×`, not 3×.**
>
> **An artefact caught on the way:** the first run read **99.0%** at ≥ 0.80 — carryover twins (a bill continued
> 2024 → 2025 appears in both files with the same summary, and Open States never updates the second copy).
> Excluded; the band drops to 94.5% on n = 73. Same artefact as [[testing/continuance]], second time.
> 2023 has no summaries in the source and is excluded both as a matched and as an earlier bill.

## The title version (kept for the record; not the product basis)

Owner, 2026-09-23: *"so your big finding is longer sessions means bills have more time to get heard? please
be serious."* Fair — the clock result was mostly the crossover deadline restated ([[testing/clock]]). This is
what serious work turned up instead, and it passes the test he set on 2026-09-22: **a finding has to tell you
something the bill's own action list does not already say.**

A bill's history starts at its own filing. This is the history **before** that — what this committee did with
this idea the last time it saw it. A veteran carries it in their head; a volunteer cannot see it anywhere.

`python3 tools/calibration/room_memory.py` · scope 2020–2026 ([[failures/openstates_committee_gap]])

## The finding

Same idea, **same first committee**, patron's party held fixed:

| match rule | died there before → dies again | cleared before → dies | odds ratio |
|---|---|---|---|
| exact title | **80%** (n = 227) | 26% (n = 148) | **10.8** [6.7–17.6] |
| subject clause | 58% (n = 1,033) | 35% (n = 1,342) | 2.6 [2.2–3.0] |
| subject clause, 2025–26 only | 59% | 31% | 3.2 |

**And a different legislator of the same party still meets it:** OR **3.6** [1.5–8.2], p = 0.003 (n = 106).

## The confound that had to be beaten — bad ideas are bad everywhere

If this were only idea quality, the room would not matter. It does. Exact title, same standing:

| | odds ratio |
|---|---|
| **same** first committee | **15.2** [9.3–25.0], n = 440 |
| **different** first committee | 5.5 [3.0–10.3], n = 204 |
| difference | **z = +2.49, p = 0.013** |

**Both are true:** idea quality persists (5.5×) and the room roughly **triples** it. Stable across eras — OR
12.9 in 2020–22, 16.1 in 2023–26.

**The dose-response is the best evidence it is real:** the tighter the idea match, the stronger the memory
(exact 10.8 > subject 2.6). Noise does not do that.

## The asymmetry — the part a lobbyist would not guess

| | same room | moved to another room |
|---|---|---|
| room **killed** it before → dies again | 85% | **81%** |
| room **cleared** it before → dies | **27%** | 43% |

**Once a room has said no, moving rooms barely helps** (85% → 81%). What the room adds is on the **yes** side:
an idea it cleared before clears again 73%, against 57% sent elsewhere. What does break a room's no is a
change of carrier standing — [[failures/assumptions_audit|#129]]: a failed minority bill handed to a majority
patron goes from 6% to 41%.

## Coverage and Standard #3

| on 2026 | bills | share |
|---|---|---|
| exact-title earlier attempt | 280 | 11.8% |
| …in the same first committee | 199 | 8.4% |
| subject-clause earlier attempt, same committee | 1,083 | 45.8% |

**Exact title equality** compares two values of an official LIS field — identity, like comparing bill numbers
— and is the only form proposed for the lobbyist path. The **subject-clause** rule splits the title string,
which is text parsing: **internal only** under Standard #3. That leaves the lobbyist-facing version at 8–12%
coverage with a very strong signal — a sparse screen, the same shape as [[testing/member_subject]].

## What it would look like on the War Room

A sourced line, not a score: *"Filed before as HB 1234 (2024) — died in House Privileges and Elections."* The
earlier bill number and its fate are LIS facts. The rate behind it — *rooms kill an idea again 80% of the time
after killing it once* — is a count, so it takes no colour (P20b).

## Also found this session, and smaller

**Second chamber** ([[testing/second_chamber]]). When the patron's party runs the chamber the bill is going
to, cross-party support in the first chamber is worth **nothing** — 86%, 89%, 86%, 87% across the range. When
it does not, the other party's support swings the second chamber from 24% to 80% — but the headline vote total
already carries almost all of it (AUC 0.756 vs 0.775) and nearly the whole effect sits in 2023's split control.
**Kept as an asymmetry, not a feature.**
