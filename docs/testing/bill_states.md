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

| a bill that was **ever**… | tag | bills | later got a floor passage vote | 2026 share |
|---|---|---|---|---|
| Reported to the floor | grey | 8,859 | 7,968 — **90%** | 50.5% |
| Re-referred | grey | 2,363 | 1,467 — **62%** | 0.2% |
| Left in committee | grey · terminal | 6,728 | 0 | 19.3% |
| Incorporated into another | grey · pointer | 672 | 0 | 3.6% |
| Failed to report | **amber** | 245 | 6 — 2.4% | 1.1% |
| Tabled | **amber** | 1,303 | 13 — 1.0% | 4.8% |
| Continued to next session | **amber** | 1,367 | 12 — 0.9% | 18.0% |
| Stricken from the docket | **amber** | 287 | 0 | 1.0% |
| (no committee action yet) | grey | — | — | 1.5% |

**The rule, stated once so no page has to argue it:** *amber means the record shows bills rarely leave this
state; grey means they do.* Every bill carries exactly one tag (the vocabulary covers 2026 exactly — a
vocabulary with a hole renders a blank tag on a real bill). Amber fires on **588 of 2,366 = 24.9%**.

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
