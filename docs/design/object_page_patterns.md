---
tags: [design, research, information-architecture, object-page, bill-page, war-room]
updated: 2026-07-16
status: active
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

## 4. Our own constraint the prior art does NOT solve — the trust partition

CRMs have ONE truth (everything in the record is the org's own data). **We have two**, and blending them is
forbidden: **LIS-verified fact vs org-entered intel** must stay visibly distinct
([[ideas/lobbyist_jtbd_ideation]] §8b V4; [[ideas/product_identity]]). So we cannot simply copy Salesforce's
activity timeline and interleave "Maya called the aide" into the LIS action history — that would blend the
two classes in one stream. The bill page needs the two as **separate, visually-classed streams** (or one
stream with an unmistakable class distinction). **This is the one place we must design past the prior art,
not adopt it.**

---

## 5. Synthesis — the shape the research implies for the bill page

Not a decision (owner's call), but this is where the four sources converge:

- **Card stays** = the compact layout's fast, in-context preview (§2.1). Additive page, nothing removed.
- **Bill page** = an **object page**: pinned **highlights strip** (the same compact layout) → then sections
  that are **related objects**, previewed not inlined (§2.3):
  - **Next** (the Meeting object — shipped Now→Next) and **History** (Action objects) = the next/past split (§2.2)
  - **Committee & members** (Committee + Member objects, with vote-history attributes) = the "war room" count
  - **Our position + our contacts** (our attribute + Contact objects) — **visually partitioned** as org data (§4)
  - later: **Versions**, **Documents** (fiscal), **related Bills** (companions) — each a related object, each
    with an obvious home, none of them a bolt-on
- **Single scrolling column with sections, not tabs** (§3) — because the hearing-prep case is a comparison case.
- **A bill gets a URL** — the present-day gap (no routing exists at all; the org coordinates by text and cannot
  link a bill today). This is the strongest *current* reason for the page, independent of future features.

Everything above is the *skeleton*; the visual treatment still obeys [[design/dashboard_and_visual_language]]
(registers are monochrome, colour is reserved, routine is grey) and [[design/information_display]].

## 6. Added to the reading queue by this pass
- **Sophia Prater — *Object-Oriented UX*** (the book / OOUX course material) — read in full when the bill page
  is built; the ORCA object-map exercise is worth doing properly for Bill/Meeting/Committee/Member/Position/Contact.
- **Jira / Linear / GitHub issue anatomy** — the modern "central object + attribute sidebar + activity stream"
  variants; mine for the sidebar-vs-inline attribute decision.

See also [[design/information_display]] (the rules), [[design/reading_notes]] (the quantitative canon),
[[architecture/strategic_tools_placement]], [[ideas/war_room_scoping]], [[ideas/product_identity]].
