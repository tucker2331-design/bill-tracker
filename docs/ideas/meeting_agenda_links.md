---
tags: [ideas, calendar, lis, links, plan]
updated: 2026-07-10
status: active
open_loop: Surface meeting + agenda links (owner GO 2026-07-08) — measured + scoped, needs a Sheet1 migration (29→31 cols)
---

# Meeting + agenda links — measured, scoped, not yet built

> **Owner, 2026-07-08:** *"look into getting the links for the meetings and the agendas for those meetings…
> a link to the agenda pdf would be even more helpful."* → **GO.**

**Status: measured and designed; NOT implemented.** It needs a Sheet1 column migration and a change to which
URLs the worker fetches — both output-sensitive. Written down in full because the alternative is exactly the
failure [[log]] `[2026-07-10] process` describes.

---

## 1. What LIS actually publishes (measured 2026-07-10, live Schedule API, session 20261)

The Schedule API's `Description` field is **HTML containing anchors**. There is no separate link field.

```
3,533 rows | 2,222 carry a Description | 1,737 carry ≥1 <a>
links per description:  0:485   1:691   2:889   3:131   4:20   5:4   6:2
```

The anchor's **label** is the only discriminator between an agenda PDF and a livestream:

| count | label | what it is |
|------:|-------|------------|
| 1,429 | `(View Meeting)` | livestream / video (granicus, house.vga, apps.senate, youtube, zoom) |
| 1,036 | `(Agenda)` | **the agenda** — 299 on `lis.blob.core.windows.net/files/*.PDF`, rest on committee sites |
| 104 | `Subcommittee Info` | the committee's own site (`sfac.virginia.gov`, `hac.virginia.gov`) |
| 79 | `Committee Info` | ditto, plus `lis.virginia.gov/…/committee-details` |
| 35 | `(Meeting Materials)` | supporting docs, not the agenda |
| 25 | `Agenda` | same thing, no parens |
| 25 | `(Agenda and Meeting Materials)` | one link, both roles |
| 24 | `(Agenda and View Meeting)` | one link, both roles |
| 23 | `(Registration)` | webinar signup |

## 2. The existing `agenda_url` is right ~77% of the time, by accident

`calendar_worker.py:5667` takes the **first `href` in the string** whenever the description mentions
`agenda|docket|info` anywhere:

```python
link_match = re.search(r'href=[\'"]?([^\'" >]+)', raw_desc)
if link_match and any(x in raw_desc.lower() for x in ["agenda", "docket", "info"]):
    agenda_url = link_match.group(1)
```

Classifying the URL it *actually takes* by the anchor that URL belongs to — 1,337 fires:

| count | taken from label | verdict |
|------:|------------------|---------|
| 1,028 | `agenda`, `agenda and view meeting`, `agenda and meeting materials`, … | **correct** |
| 194 | `committee info` / `subcommittee info` | **correct by design** — see §3 |
| **89** | `registration`, `view meeting`, `meeting notice`, `public hearings notice`, `docket`, `(no matching anchor)` | **wrong target** |

**The `"info"` in the gate is not a bug.** `extract_rogue_agenda(url, session, target_date_dt)` is *built* to be
handed a committee homepage: it looks for a row whose text matches the target date, finds the `Agenda|Docket`
link or a `.pdf`, and recurses once. That is how VA committees that self-host their agendas (House/Senate
Appropriations) are covered. I nearly "fixed" this before reading the function — the measurement said 283
wrong, and 194 of those were the feature working.

**But 89 are real.** The worker fetches a webinar registration page or a granicus video page and regexes
`\b([HS][BJR]\s*\d+)` out of whatever text it finds. Two harms:
- **Accuracy:** `extract_rogue_agenda`'s no-date fallback is `agenda_links[0]` — the *first* PDF on the page,
  regardless of date. A committee homepage listing several agendas can attribute the **wrong date's bills** to
  this meeting.
- **LIS-safety:** ~89 pointless off-site fetches per full cycle (guardrail #4 budget).

## 3. Two findings that constrain the design

**(a) LIS's own data contains a typo: `'Subommittee Info'` × 17.** Not `Subcommittee`. Any hand-curated label
allowlist is therefore wrong on arrival and will rot further. This is Standard #1 in the flesh: a static value
**must** ship with a runtime drift check. Mirror `validate_governor_eventcodes` / `validate_status_grouping` —
collect the distinct anchor labels each cycle, diff against the known set, raise a categorized `DATA_ANOMALY`
alert listing the unknowns. Unknown label ⇒ classify as `other`, never as an agenda.

**(b) The Description HTML is malformed.** Observed labels include `'agenda) (view meeting'` and
`'agenda) <a href="https://virginia-senate.granicus.com/…"'` — unbalanced parens and anchors nested inside
anchor text. A regex over `<a…>(.*?)</a>` mis-segments these. **Parse with BeautifulSoup** (already a
dependency, already used by `extract_rogue_agenda`), not a regex.

## 4. The change

1. **`_extract_meeting_links(raw_desc) -> (agenda_url, meeting_url, unknown_labels)`** — BeautifulSoup over the
   anchors; classify each by normalized label:
   - contains `agenda` or `docket` → agenda candidate (a combined `(Agenda and View Meeting)` fills **both**)
   - contains `view meeting` → meeting/video
   - contains `committee info` / `subcommittee info` (and the typo, matched by **edit distance or `sub*mittee`**,
     never by adding the typo to a list) → rogue-nav candidate, agenda only if no direct agenda anchor exists
   - anything else → `other`, plus an entry in `unknown_labels`
   Pure, no network, golden-tested against the real malformed strings above.
2. **Replace `calendar_worker.py:5667`** with it. Preserves all 194 rogue-nav rows; removes the 89 wrong fetches.
3. **Drift alert** on `unknown_labels` (Standard #1/#4), routed like the G-code canary.
4. **Sheet1 migration → `AgendaURL`, `MeetingURL`.** ⚠️ **Sheet1 is 29 columns wide (A…AC). Writing col 30
   without growing the grid is exactly [[failures/assumptions_audit#99]]** (`AD1` 400'd every cycle). Grow the
   grid first, then write. Append at the END so existing gviz column indices don't shift.
5. **Front-end:** the click-to-expand meeting card ([[ideas/calendar_chain_ordering]] §30 work,
   `web/src/views/Calendar.tsx`) renders "Agenda (PDF)" and "Watch" when present. Absent ⇒ render nothing —
   never a dead link.

## 5. Validation gates

- **`_extract_meeting_links` is pure + golden** against the malformed real strings; 0 network in the test.
- **Re-measure the 1,337:** correct stays ≥ 1,028+194, wrong target → **0**, and `unknown_labels` is reported
  with a denominator (unknown / total anchors).
- **Migration:** confirm `ws.col_count` ≥ 31 **before** the first write (audit #99). Cold-start on a fresh sheet
  must create the wider grid, not assume it.
- **`WORKER_OUTPUT_LOGIC_VERSION` bump is MANDATORY** ([[failures/assumptions_audit#96]]) — dropping 89 rogue
  fetches changes which bills land on some meetings, and two columns change the row shape.
- Adding a column to a persisted store is a **MIGRATION, not a code change** — every consumer that assumes the
  old width must be checked (`web/src/data/calendar.ts` column indices, `pages/ray2.py`).

See also [[architecture/calendar_pipeline]], [[knowledge/lis_api_safety]], [[state/current_status]].
