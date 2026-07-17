---
tags: [design, research, information-architecture, object-page, bill-page, war-room]
updated: 2026-07-17
status: active
open_loop: Two residuals — the roster ROW (LIS member + our whip mark in one row) defeats the region-level trust partition and is unresolved pending the mockup (§5); and Prater's OOUX book/course is still unread in full (§7), with the ORCA object-map exercise waiting on roster data that is not ingested at all today.
---

# The central-object page — research digest (the canon gap this fills)

> **Why this page exists.** The brain's design canon ([[design/reading_notes]], [[design/information_display]])
> is deep on **quantitative display** — Tufte, Few, Munzner (charts, density, channels) and Hearst (search).
> It contains **nothing** about the problem now in front of us, which the owner named exactly (2026-07-16):
> *"a war room having a center item — ie the bill — and a lot of features attached."* That is one of the
> most-studied problems in interface design and it has its own literature. This is the deep-read digest;
> actionable rules get distilled into [[design/information_display]] and applied in
> [[architecture/strategic_tools_placement]].
>
> Owner's standing instruction that produced it: *"you're only as smart as every smart human, and every smart
> human wrote shit down in books"* — read the prior art before inventing.

---

## 1. Object-Oriented UX (OOUX) — Sophia Prater — **the methodology that matches our problem exactly**

**The core claim: people think in OBJECTS, not in features or flows.** Traditional UX is flow-based — it
designs the *verbs*. OOUX inverts it: define the **nouns** first, because the verbs are easy once the nouns
are right. The process is **ORCA — Objects, Relationships, Calls-to-action, Attributes** — ending in the
**object map** (attributes defined on objects), which Prater calls the "holy grail" of the process.

**Why it's decisive for us — THE reframe:** our "13 per-bill features" are mostly **not features at all.**
They are **objects and relationships**. Slicing by nouns dissolves the pile:

| What I'd been calling a "feature" | What it actually is (OOUX) |
|---|---|
| committee math / whip board | the **Committee** object + its **Member** objects (each with vote-history attributes), related to the Bill |
| contact memory | **Contact** objects (Member × Bill × who × when × what was said) |
| our position | an **attribute** of the Bill (ours, not LIS's) |
| substitute redline | **Version** objects related to the Bill |
| fiscal-note watcher | a **Document** object related to the Bill |
| companion / copycat detection | a **Bill → Bill** relationship |
| survival odds | a computed **attribute** |
| history | **Action** objects related to the Bill |
| Now → Next (shipped) | the Bill's related **Meeting** object |

**Consequence — this is the answer to "won't the workspace just become the new junk drawer?":** NO, *if* the
page is structured by **objects and their relationships** rather than by a growing list of feature panels. A
new capability then almost always lands as **a new related object or a new attribute on an existing one** —
which has an obvious home — instead of a new box someone has to find room for. Structure by nouns and the
page scales; structure by features and it silts up. (This is the same instinct as our own "one dataset, four
lenses" spine in [[ideas/product_vision]] §2 — the lenses are views over objects.)

**CTAs also settle permissions early** (Prater): "what does each user type want to DO to each object" answers
who-can-do-what — directly relevant to org-vs-LIS data classes and the Access decision
([[ideas/war_room_scoping]]).

Sources: [What is OOUX](https://ooux.com/what-is-ooux) · [Intro to OOUX + how to do it](https://ooux.com/resources/an-introduction-to-object-oriented-ux-and-how-to-do-it) ·
[Prater on ORCA](https://sophiavux.medium.com/in-the-approach-to-ooux-that-i-teach-we-call-the-process-orca-e226dfdd015a) ·
[LogRocket: OOUX structured approach](https://blog.logrocket.com/ux-design/object-oriented-ux-ooux/)

---

## 2. The CRM record page (Salesforce Lightning) — **the most-iterated industrial answer**

Two decades of iteration on precisely "one record + many attached things + a team collaborating + a history."
Its anatomy is a tested skeleton:

- **Highlights panel** — a strip of the record's key fields at the **top, pinned while you scroll** the rest.
  Its content is defined by a **"compact layout"** — a single named field-set reused across surfaces.
- **Related lists** — the related objects, as cards; ~6 records each in a wide region, ~3 in a narrow one,
  each showing ~4 fields. (i.e. **a related object shows a PREVIEW, not its full self.**)
- **Activity timeline** — time-ordered activity **split into "Next steps" (upcoming) vs "Past activity."**

**→ THIS PRODUCT (three direct transfers):**
1. **The "compact layout" idea VALIDATES the card↔page consistency rule** I proposed
   ([[architecture/strategic_tools_placement]] follow-on): define the bill's key fields ONCE and render that
   same set in the **card (preview)** and in the **page's highlights strip**. Salesforce formalised exactly
   this to stop a record's summary drifting between surfaces. Our card **stays** — it becomes the compact
   layout's other rendering, not a competing view.
2. **"Next steps vs past activity" maps 1:1 onto the bill**: our shipped **Now → Next** row is the "next
   steps" half; **History** is the "past activity" half. That split is already right — the research just
   names it.
3. **Related lists preview, they don't inline the whole object** — so the Committee's 15 members do NOT all
   render on the bill page by default; the roster previews and expands. This is how the page holds many
   objects without crowding.

Sources: [Highlights panel + compact layout](https://salesforcedictionary.com/terms/highlights-panel) ·
[Related lists behaviour](https://trailhead.salesforce.com/content/learn/modules/lightning_app_builder/lightning_app_builder_recordpage) ·
[Activity timeline: next steps vs past](https://sfdcpenguin.com/blog/activity-timeline-view-activity-data-with-ease/)

---

## 3. NN/G — tabs vs one scroll vs accordions — **the constraint that decides our layout**

Tabs are right ONLY when: content has **clear groupings**; there are **few** of them (overflow → carousel →
dead); groupings are of **unequal importance** (the default tab gets the attention, so **non-default content
must be genuinely supplemental**); labels are **short**; and — the decisive one — **the user does NOT need to
compare across them**, because that "taxes short-term memory, increases cognitive load and interaction cost."
Accordions suit mobile; tabs handle longer content on desktop. If you can't find distinct groupings, *tabs are
the wrong control.*

**→ THIS PRODUCT — this rule actively constrains the bill page.** A lobbyist prepping Thursday's hearing needs
the **meeting time AND the committee roster AND our position at once** — that is exactly the *comparison* case
NN/G says tabs fail. So the whip/committee content **must not sit behind a tab from the overview**. The page
wants a **single scannable column with sections** (+ a pinned highlights strip), not a tab bar — with tabs, if
ever, reserved for genuinely supplemental bulk (e.g. full bill TEXT versions, which nobody compares against the
roster).

Source: [NN/G — Tabs, Used Right](https://www.nngroup.com/articles/tabs-used-right/)

---

## 4. Jira / GitHub / Linear — the modern issue anatomy, and **the sidebar question resolved**

Atlassian publishes Jira's issue-view anatomy as an explicit spec, which makes it the most quotable version
of the pattern GitHub and Linear also converge on:

- **Main left column** — the object's narrative/content, with an **activity feed at the bottom**: "a list of
  changes, updates, and comments on an issue," toggleable between history / transitions / comments.
- **Right sidebar** — the **fields** (status, assignee, priority, labels), plus **glances** (compact
  summaries that expand) and **collapsible context panels** for secondary information.
- **Top right** — the issue **actions**.
- An explicit placement rule: context panels and glances belong **exclusively** on the right; don't use them
  "if you want to add app information to the left side."

**→ THE SIDEBAR-VS-INLINE DECISION — the answer is that the question was mis-framed.** These tools put
attributes in a right sidebar because *their attributes are editable controls* — the sidebar is a **control
panel** and the main column is the **narrative**. The split isn't attribute-vs-content; it's
**control-vs-content**. That cuts our case cleanly, because our attributes divide on exactly that line:

| Our attribute | Nature | Where the prior art puts it |
|---|---|---|
| bill #, patron, chamber, location, stage, crossed-over | **read-only LIS fact** | Salesforce **highlights strip**, pinned (§2) — not a control panel |
| our position, tracked/star | **editable org control** | Jira-style **fields region** |

So **we do not need a generic attribute sidebar.** Read-only facts go to the pinned highlights strip; the
only things that behave like Jira's sidebar fields are the org's own editable attributes — which §5 already
requires to live in their own region anyway. The two rules land on the same layout instead of fighting.

Source: [Atlassian — Jira issue view design guidelines](https://developer.atlassian.com/cloud/jira/platform/issue-view/)

---

## 5. The trust partition — the prior art does NOT solve it, but **our own canon does**

CRMs have ONE truth (everything in the record is the org's own data). **We have two**, and blending them is
forbidden: **LIS-verified fact vs org-entered intel** must stay visibly distinct
([[ideas/lobbyist_jtbd_ideation]] §8b V4; [[ideas/product_identity]]). We cannot copy Salesforce's activity
timeline and interleave "Maya called the aide" into the LIS action history — that blends the two classes in
one stream. Jira has the same single-truth assumption (its activity feed mixes system transitions and human
comments freely, because both are Jira's own data).

**Searched the provenance-in-UI literature for prior art; it does not transfer.** The nearest hit,
[ProvenanceLens](https://arxiv.org/abs/2505.11784) (2026), argues provenance should be a **user-controlled
attribute mapped onto ordinary visual channels (color, size, filter, sort)** rather than hardwired — but its
"provenance" is **analytic** provenance (recency/frequency of *your own interactions*), not **source**
provenance (*who asserted this fact*). Different problem; recording it so nobody re-runs this search. The one
transferable half — *provenance is an encodable attribute, so pick its channel deliberately* — points
straight back at Munzner, who is **already in our canon**. So the decision is derivable from rules we hold:

- **Opacity/dimming is WRONG here.** (The one live pattern the search surfaced — AI tools render unverified
  blocks at 70% opacity until approved.) It says *provisional / lower-confidence*. Org intel is neither: it's
  the org's hard-won, highest-value data. Dimming it inverts the emphasis (P10 — spend ink on what must be
  noticed) and asserts something false about it.
- **Color is WRONG here.** P10 reserves saturated color for attention/exception states (stale, dead, deadline).
  The org layer is not an exception — it's a permanent half of the page. Spending the attention channel on an
  always-on structural distinction burns the one signal we've reserved.
- **Position/spatial grouping is RIGHT.** It's Munzner's **top-ranked** channel, it's the canon's preferred
  grouping device (P17 — group by proximity and whitespace, not lines), it's always-on without ever shouting,
  and it leaves color free. Plus a **text label** per region, because P19 forbids encoding by anything alone.

**→ THE RULE: LIS fact and org intel never share a region.** The partition is spatial and labeled — and it
rides on a layout convention (§4) users already know, so it costs nothing to learn.

**The bonus finding — the trust line and the permission line are the SAME line.** The org region is exactly
what Access gates and what the write path (Worker+D1) writes; the LIS region is public and read-only. One
boundary, drawn once, carries both the trust partition and the security model — and a viewer can *see* which
part is org-private. Prater called this shot: §1's "CTAs settle permissions early" predicts precisely this
(the objects the org can act on are the org's objects). **This also answers the owner's open question about
whether the war room is its own tab: it isn't — the war room *is* the org-owned region of the bill page.**

**The one honestly-unresolved spot — the committee roster.** It's the hard case: a Member is LIS fact, but our
whip mark on that member is org intel, and they meet *in the same row*. Spatial partition works at the region
level and breaks down at the row level. The rule that must hold is **no single cell blends the two — any given
piece of text is either sourced or asserted, never both**. How the row expresses that is a **mockup question**,
flagged here rather than hand-waved.

---

## 6. Synthesis — the shape the research implies for the bill page

Not a decision (owner's call), but this is where the five sources converge:

- **Card stays** = the compact layout's fast, in-context preview (§2.1). Additive page, nothing removed.
- **Bill page** = an **object page**, in two labeled regions split by trust (§5):
  - **LIS region (public, read-only):** pinned **highlights strip** = the compact layout, the same field set
    the card renders (§2.1, §4) → **Next** (the Meeting object — shipped Now→Next) and **History** (Action
    objects), which is Salesforce's next-steps/past-activity split (§2.2) and Jira's activity feed (§4).
  - **Org region (Access-gated, writable) — this IS the war room:** our **position** (an editable attribute,
    the one thing that behaves like a Jira sidebar field, §4) + our **contacts** (Contact objects) +
    **committee & members** with whip marks (the roster row being the open question, §5).
  - later: **Versions**, **Documents** (fiscal), **related Bills** (companions) — each a related object with
    an obvious home in the LIS region, none of them a bolt-on (§1).
- **Related objects preview, they don't inline** (§2.3) — the committee's 15 members don't all render by default.
- **Single scrolling column with sections, not tabs** (§3) — the hearing-prep case is a comparison case
  (time + roster + position at once), which is exactly where NN/G says tabs fail.
- **A bill gets a URL** — the present-day gap (no routing exists at all; the org coordinates by text and cannot
  link a bill today). This is the strongest *current* reason for the page, independent of future features.

Everything above is the *skeleton*; the visual treatment still obeys [[design/dashboard_and_visual_language]]
(registers are monochrome, colour is reserved, routine is grey) and [[design/information_display]].

## 7. Reading queue — state after this pass
- ✅ **Jira / Linear / GitHub issue anatomy** — done (§4). Resolved the sidebar question by re-framing it as
  control-vs-content; Atlassian's published spec is the citable primary source.
- ✅ **Provenance-in-UI literature** — searched (§5). **Does not transfer** (analytic ≠ source provenance);
  logged so the search isn't re-run. The partition resolves from Munzner + P10/P17/P19 instead.
- ⏳ **Sophia Prater — *Object-Oriented UX*** — the ORCA **method** is digested from her own primary material
  (§1) and is what this page applies; the **book/course in full** is still unread. Worth doing the object-map
  exercise properly for Bill/Meeting/Committee/Member/Position/Contact when the roster data exists — today
  **zero** member/committee roster is ingested, which is the hard blocker under the whip board anyway
  ([[ideas/war_room_scoping]]).

See also [[design/information_display]] (the rules), [[design/reading_notes]] (the quantitative canon),
[[architecture/strategic_tools_placement]], [[ideas/war_room_scoping]], [[ideas/product_identity]].
