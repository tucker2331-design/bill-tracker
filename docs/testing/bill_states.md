---
tags: [testing, calibration, war-room, tags, design]
updated: 2026-09-18
status: active
---

# The tag vocabulary — every state a bill can be in, measured

Owner, 2026-09-18, on a mockup carrying two hand-written footnotes:
> *"how possibly could we compute this much text instantly for every scenario it needs to be simplified and
> put into a proper spot… is there any other tags that should go in the spot of the continued notification"*

Right on both counts. **A tag written for one bill is a caption.** A tag is only a product if one template
fills for all 2,326 bills. So the vocabulary is the finite measured list, not my judgement of the
interesting case.

`python3 tools/calibration/bill_states.py`

## The vocabulary

| a bill that was **ever**… | the record | bills | later got a floor passage vote | 2026 share |
|---|---|---|---|---|
| Reported to the floor | moves | 8,860 | 7,969 — **90%** | 50.5% |
| Re-referred | moves | 1,669 | 1,305 — **78%** | 0.2% |
| Left in committee | ends | 4,543 | 0 | 19.3% |
| Incorporated into another | ends · pointer | 664 | 0 | 3.6% |
| Failed to report | rarely leaves | 245 | 6 — 2.4% | 1.1% |
| Tabled | rarely leaves | 1,240 | 12 — 1.0% | 4.8% |
| Continued to next session | rarely leaves | 1,348 | 12 — 0.9% | 18.0% |
| Stricken from the docket | rarely leaves | 256 | 0 | 1.0% |
| (no committee action yet) | — | — | — | 1.5% |

> **⚠️ CORRECTED 2026-09-22 — the window is 2020-2026, not 2017-2026.** The corpus has **no committee-stage
> actions before 2020** and the gap is silent: the bills are present and the passage flag is intact, so the
> early years contributed kills without reports. It cost **16 points on one row** — Re-referred was
> published at 62.1% and is 78.2% on the years that have the record. The other seven rows moved under a
> point. See [[failures/openstates_committee_gap]]; `bill_states.assert_years` now fails loud.

**The rule, stated once so no page has to argue it:** *the tag always carries the count behind it.* Every
bill gets exactly one (the vocabulary covers 2026 exactly — a vocabulary with a hole renders a blank tag on
a real bill).

### ⚠️ CORRECTED 2026-09-19 — the first version spent colour, and colour was already spoken for

v1 of this page turned four of the eight tags **amber**. Owner: *"are colors really necessary do they
conflict with other aspects of the system would they scare lobbyists off unnecessarily?"* Yes to all three,
and **two standing rules already said so**:

1. **[[design/information_display]] P20b** — *"Arithmetic is exact — `5 of 15`, a days-remaining count — and
   takes **no marker**… Amber is for the probabilistic."* `12 of 1,367` is a tally anyone can recheck. It is
   not a guess, so it gets no amber. **P20b was written after the War Room v2 review saying exactly this**,
   and the very next War Room mockup did it again — the P20c lesson (*writing the rule down does not install
   it*) reproduced a third time.
2. **[[design/dashboard_and_visual_language]], outcome-tag doctrine (2026-07-08)** — *"Soft tint =
   significant but still pending. **Carried over = amber (still alive, just deferred — not red)**."* The
   product had **already** spent amber on this exact state, with the **opposite** meaning. One colour, one
   state, two contradictory readings: amber would have told a lobbyist *"deferred, still alive"* in one place
   and *"dead end"* in another.

**The fix costs nothing, because the number was always doing the work.** `Continued · 12 of 1,367 came back`
needs no colour to land. The state tag is now encoded by **position** (first in the row) and **weight**
(full ink against muted siblings) — Munzner's channel ranking puts position above colour, and P19 forbids
encoding by colour alone anyway. **The page now spends no colour at all.**

**The tag text is one template:** `{state} · {k} of {n} came back`. Nothing is written per bill.
`Left in committee` and `Incorporated` are grey because they are not warnings: the first is LIS's own
end-of-session mark (the bill is plainly over) and the second means the **text survives in another bill** —
a pointer, not a caution. *Open: naming the surviving bill needs a structural source; the LIS description
(`Incorporated by Finance (HB897-Sullivan)`) is text, forbidden on the lobbyist path under Standard #3.*

## The circularity that ate the first version

The natural framing is **"bills whose *last* committee action is a continuance"** — and it returns
**0 of 1,352**, which is **tautological**. A continued bill that was later reported has *Reported* as its
last action, so it leaves the bucket by succeeding. The zero is the definition, not the legislature.

Measured **ever-in-this-state**, the same question returns **12 of 1,367**. Both are "true"; only the
second is an answer. Same family as the outcome leak in [[testing/enacting_clause]] and the unreachable
numerator in [[testing/continuance]] — **a clean number produced by a question that could not have come
out otherwise.**

## Two more guards, both load-bearing

- **Special sessions.** `Continued to 2021 Sp. Sess. 1 in Education and Health` matches any reasonable
  carryover pattern and is **not a carryover** — it moves the bill to a session convening days later. There
  are **340** and they pass, dragging the continuance recovery rate from 0.9% to **13.3%**. Excluded by name.
  (Audit point #1 again, in its third form this session.)
- **Deduplication.** A carried-over bill has a record in **both** sessions, so counting session-rows
  double-counts 1,548 bills. Keyed on `(identifier, title)`, longest history wins: 22,659 → **21,111**.

## The two note slots beside the tag

The mockup's footnote was prose-per-case (P25). Both facts became one-line templates in a proper slot, and
both earn the space because their value **varies across bills** — a slot whose value is the same everywhere
is not information:

| slot | template | HB 1515 | range across rooms |
|---|---|---|---|
| how often the room votes no | `{k} of {n} recorded votes — {pct}, {rank} of {m} rooms` | 68 of 1,693 · 4.0% | **4.0% (H20) → 34.7% (S08)**, 25 rooms |
| how it treats the patron's side | `{k} of {n} — {pct}. Other {chamber} committees, {pct}` | 102 of 309 · 33% vs 62% | 29-point gap for Rules |

**And one column rename removed a whole paragraph.** *"Voted with the motion"* needed three sentences of
explanation, because a yes on a motion to table is a vote to kill. **`No votes cast, 2026`** needs none:
Sullivan 0 of 184, Kilgore 25 of 160. The footnote existed because the column was badly named.

Related: [[testing/continuance]], [[design/object_page_patterns]] §5a/§5b, [[design/information_display]].
