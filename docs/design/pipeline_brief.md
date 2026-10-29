---
tags: [design, timeline, pipeline, brief, owner-feedback]
updated: 2026-10-29
status: shipped
---

# Pipeline (Timeline) redesign — what the owner wants, and a brief for a fresh model

> **BUILT 2026-10-29 — the SUBWAY, on real data** (owner brief: "Pipeline = the SUBWAY", mockup v9). Two lines (bills
> that started in the Senate / the House) swap tracks at crossover and meet at the Governor; still-here counts at the
> stations, "✕ N ended here" branches, signed / awaiting / vetoed, carried-over and died totals. Same counting and drill
> lists as the spine it replaced (`deriveStage` / `furthestStage` / `stageSide`); no option switcher.
> `web/src/views/Timeline.tsx`. The other candidates below stay as the record.

## What went wrong in three rounds (2026-10-27)

| Round | What I showed | Owner verdict | Why it missed |
|---|---|---|---|
| 1 | Session map — every bill a dot in the Timeline's grid | "terrible … harder to read than the og" | Same layout as the Timeline, worse to read |
| 2 | Subway, River, Staircase, Mirror bars, Arch | Subway "the only improvement … more of a slight redesign" | Four were the same left-to-right stage strip in costume |
| 3 | Committee braid, Your bills, Survival lines, Session over time, Departures board | Braid "the only slightly novel" — but it is still the subway | I answered "give more" by adding OTHER questions (your bills, odds, time, schedule) that other tabs already answer |

## The diagnosis — what the owner is actually asking for

1. **Same question, new picture.** The view answers ONE question — the "by stage" lens of
   [[ideas/product_vision]] §2: *where does every bill in the session stand right now, and where did the
   ones that ended stop?* Not urgency (What's new), not time (Calendar), not my bills (the Tracking switch /
   War Room), not odds (the War Room model). Adding those is not "more", it is a different screen.
2. **"More" means more depth on that same question**, not more questions. The braid landed because it
   opened up the committee level — exactly the committee board the vision already specifies (§3b detail).
3. **Novel means a different spatial idea**, not a restyle of a left-to-right strip of stages. The subway
   won because its metaphor carries meaning (lines physically swap tracks at crossover — "the word becomes
   the picture", vision §3b). The ask is another idea of that calibre.
4. **Intuitive and readable beat clever.** It must read faster than today's Timeline, for a volunteer.

## The brief (paste into Gemini as-is)

```text
You are a senior information designer. I need fresh, genuinely different concepts for ONE data visualization.
Please do not give me a restyled version of a left-to-right row of stages; I already have that twice.

THE PRODUCT
A web app that tracks every bill in the Virginia General Assembly session. Its users are small advocacy
organizations lobbying for themselves, often staffed by volunteers who are not experts in legislative process.
The app already has separate screens for: a daily feed of new actions, a calendar of hearings, search, and a
"war room" page for the bills the organization tracks (with vote predictions). Do NOT re-create any of those.

THE ONE QUESTION THIS VIEW ANSWERS
"Right now, where is every bill in the session, and where did the ones that are finished stop?"
It is the at-a-glance picture of the whole session's progress. Someone should be able to look at it for five
seconds and understand the state of the session; then click into any part of it to get the list of bills there.

HOW A VIRGINIA BILL MOVES (the structure the picture must respect)
- A bill starts in one chamber (House or Senate). It may be prefiled before the session starts.
- It is referred to a committee in its own chamber (often heard first by a subcommittee). Committees are
  chamber-specific: e.g. "House Courts of Justice" and "Senate Courts of Justice" are different bodies.
  Bills with a cost are often re-referred to a money committee (House Appropriations / House Finance /
  Senate Finance and Appropriations).
- If reported, it goes to a floor vote in its own chamber.
- CROSSOVER is a single session-wide deadline about halfway through: any bill that has not passed its own
  chamber by then is dead. Bills that passed move to the OTHER chamber.
- In the second chamber it again goes to a committee, then a floor vote.
- Then it goes to the Governor, who signs it, vetoes it, or it waits ("awaiting").
- A bill can END at any step: it "dies" (killed, failed, passed by indefinitely) or is "carried over" to next
  year's session (still alive in principle). Where a bill ended is important information.

THE DATA (per bill, all structural, no text)
- current step: prefiled | committee (1st chamber) | floor (1st chamber) | committee (2nd chamber) |
  floor (2nd chamber) | at the Governor
- which chamber that step is in (House or Senate) and the chamber the bill started in
- current committee (chamber-qualified), and subcommittee if any
- if ended: the step and chamber where it ended, and how (died or carried over)
- if at the Governor: signed | vetoed | awaiting

MADE-UP MID-SESSION NUMBERS TO DESIGN WITH (1,496 bills; please use these so concepts are comparable)
Still at each step / ended at that step, by the chamber the step is in:
  Prefiled:            Senate 4 / 0       House 6 / 1
  Committee (1st):     Senate 120 / 160   House 310 / 340
  Floor (1st):         Senate 18 / 3      House 25 / 5
  Committee (2nd):     Senate 140 / 12    House 160 / 10     (2nd-chamber bills: Senate side = House bills)
  Floor (2nd):         Senate 22 / 1      House 30 / 2
  At the Governor:     40 signed, 85 awaiting, 2 vetoed
  Of the 534 that ended: 180 carried over, 354 died
First-chamber committees (still / ended):
  Senate: Courts of Justice 30/45, Education and Health 30/35, Commerce and Labor 20/30,
          General Laws and Technology 15/20, Finance and Appropriations 15/20, other 10/10
  House:  Courts of Justice 60/70, Labor and Commerce 55/60, Health and Human Services 50/55,
          Education 45/40, General Laws 40/45, Appropriations 30/40, other 30/30
By starting chamber: 559 started in the Senate, 937 in the House.

WHAT EVERY CONCEPT MUST SHOW (no less, and no unrelated extras)
- how many bills are still at each step, for each chamber
- how many ended at each step, for each chamber (and died vs carried over overall)
- crossover as a visible moment where bills change chambers
- the Governor's three outcomes
- every count is clickable to open that group's bill list
Optional deeper level: the committee breakdown (this is the one kind of "more" that is welcome).

WHAT I HAVE ALREADY SEEN — please do not repeat these
- A horizontal pipeline: stages left to right, Senate counts above a centre line, House below, a crossover
  divider, outcomes at the end. (This is the current design.)
- A subway map of the same: two lines that swap tracks at crossover. (The best so far — because the
  metaphor itself explains crossover. I want ideas of THAT quality, but different.)
- A version of the subway where each chamber's line splits into one track per committee. (Novel, liked.)
- Restyles of the left-to-right strip: a funnel/river, a staircase, mirrored bar chart, a semicircle arch,
  a dot-per-bill grid. (Rejected: same layout in costume, or harder to read.)
- Adding other questions: the user's own bills, odds of passing, a timeline over days, this week's hearings.
  (Rejected: other screens already answer those.)

VISUAL RULES
- Dark interface. Grey by default. Colour only for fixed meanings: blue = still moving / awaiting;
  red = vetoed / died; amber = carried over; near-white = signed. No decorative colour, no coloured bands.
- Counts are shown as whole numbers ("340 of 930"), never percentages.
- Must be readable on a laptop and still work on a phone (it may reflow).
- It may animate or be interactive, but the still frame must already answer the question.

WHAT I WANT BACK
1. Five or more concepts that each use a DIFFERENT spatial metaphor or structure (at most one of them may be
   a left-to-right strip). For each: a name, a one-paragraph description of what the viewer sees, how each
   required piece of data maps onto the picture, what it makes obvious in five seconds that a table would
   not, and its main weakness.
2. Your honest pick of the best one and why.
3. A single self-contained HTML file (inline SVG + vanilla JS, no external libraries) that draws your pick
   with the numbers above, with every count clickable (a click can just show "N bills: <group>").
```

## Gemini's answer (2026-10-27) — checked, and three built into the mockup

Gemini returned six concepts and picked a **custody matrix**: rows = whose bill (Senate / House), columns = which
chamber has it now. Home turf sits on the diagonal and visiting turf off it. Every derived count it quoted was
recomputed and is correct (305 / 254 / 202 / 52 for Senate bills; 687 / 250 / 175 / 75 for House bills; 304 / 176
and 531 / 358 by custody).

| Concept | Verdict |
|---|---|
| Custody matrix (its pick) | **Built.** The real insight: it separates "whose bill" from "where it is now", the exact confusion the Timeline's "Senate side = House bills after crossover" causes |
| Concentric bullseye (distance to centre = distance to law) | **Built.** The most visually new; outer rings = first chamber, inner = second; half-ring area ∝ bills |
| Territory map (every bill the same area; crossover a fault line) | **Built.** The fault line sits lower for the House, which shows at once that more House bills are still stuck |
| Committee switchboard | Not built — the committee braid rotated |
| Canal locks | Not built — the rejected staircase |
| Attrition pyramid | Not built — the rejected mirror bars (Gemini says so itself) |

Gemini's own HTML was not used: it breaks our visual rules (tinted count pills = filled chips, a blue accent rail on
the inspector, two different blues and reds) and writes prose per case in its drill text (P25).
