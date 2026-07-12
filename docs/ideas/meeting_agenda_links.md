---
tags: [ideas, calendar, lis, links, plan]
updated: 2026-07-12
status: shipped
---

# Meeting + agenda links — ✅ SHIPPED (re-shipped 2026-07-12 after the #211/#212 reverts)

> **Re-ship note (2026-07-12):** the 2026-07-10 ship was reverted twice — the capture block referenced
> `normalized_name` before its binding in the schedule loop (`UnboundLocalError` → mislabeled as an LIS API
> outage → `meeting_unsourced` 0→66 breaker trips; [[failures/assumptions_audit#105]]). Re-shipped FIXED in
> [PR #214](https://github.com/tucker2331-design/bill-tracker/pull/214) — the block now sits AFTER the final
> post-lexicon `normalized_name` binding (placement is load-bearing: the key must match the skeleton rows'
> `Committee`). Live verified: `agenda_links_meetings=859/1,684` in SYSTEM_METRICS, real PDFs/livestreams on
> Sheet1 rows, `meeting_unsourced=0`.


> **SHIPPED & browser-verified.** Worker: `_extract_meeting_links` (label-based, BeautifulSoup) →
> additive `AgendaURL`/`MeetingURL` columns on Sheet1 (safe rectangular write, §4) + a drift canary for
> unrecognised labels. Front-end: the Calendar expand-card renders "📄 Agenda" + "▶ Watch meeting" when
> present, "Agenda not posted yet" for a FUTURE meeting whose agenda hasn't dropped, and nothing when neither
> exists (honest-absent). Golden-tested (`test_meeting_links.py`, 13 cases) + preview-verified all three link
> states. Live extraction check: agenda_url points at a video host **0×** (was 89× with the old first-href
> heuristic); 1,181 agendas + 1,478 livestreams extracted, drift canary reports only ~12 ambiguous labels.
>
> **One follow-up left (NOT this feature):** the worker's bill-extraction FETCH (`agenda_url` at the schedule
> loop, feeding `extract_rogue_agenda`) still uses the old first-href heuristic and so fetches a
> registration/video page ~89× per cycle to regex bills out of it. That's a bill-extraction accuracy/LIS-budget
> issue on a different path — deliberately left untouched here (changing which bills get extracted is a
> separate, measured change). Tracked in [[state/open_anti_patterns]] #13.

# Meeting + agenda links — the original scope (now shipped)

> **Owner, 2026-07-08:** *"look into getting the links for the meetings and the agendas for those meetings…
> a link to the agenda pdf would be even more helpful."* → **GO.**
>
> **Owner, 2026-07-10:** *"meeting links and agendas are expected on both FUTURE and PAST meetings — almost
> more importantly the future ones."*

## 0. Future AND past meetings — both, future first (owner 2026-07-10)

The Schedule API is forward-looking: it lists **upcoming** meetings as well as past ones, and both carry the
`(View Meeting)` livestream link and (usually) the `(Agenda)` link in the same `Description` HTML — so the
same extraction covers both. Two future-specific rules the build MUST honour:
- **A future meeting often has a livestream link but NO agenda yet** (agendas post shortly before the meeting).
  The card must show the meeting/livestream link and say *"agenda not posted yet"* — never render an empty or
  dead agenda link, and never treat "no agenda" as "no meeting."
- **The worker already scrapes ahead of `test_end_date`** (`effective_scrape_end`, the off-season interim
  window) so future rows are already produced; this feature must attach links to those future rows too, not
  only historical ones.

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
4. **Sheet1 columns → `AgendaURL`, `MeetingURL` — DE-RISKED 2026-07-10, NOT the AD1 pattern.** Investigated the
   write mechanism: `sheet_data = [final_df.columns.tolist()] + final_df.values.tolist()`, then
   `worksheet.update(range_name="A1")`. Sheet1 columns are **dynamic** (defined by `final_df`), the data write
   is rectangular from A1, and the DATA columns are A–O (15) while the STATE cells (`S1` session, `W1` breaker,
   `AA1` freshness, …) live at columns S+ (18+). Adding two columns **after `TimeClass` (O)** makes the write
   A1:Q (17 cols) — **still inside the 29-col grid, with a spacer column (R) before the state cells.** So:
   **no grid growth, no off-grid `acell`, state cells untouched.** This is a plain additive column write, the
   opposite of the [[failures/assumptions_audit#99]] `AD1` single-off-grid-cell bug. Reorder explicitly right
   before the write — `final_df[[…existing…] + ["AgendaURL", "MeetingURL"]]` — so A–O never shift (the
   front-end reads by column letter) and the two new columns are always last.
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
