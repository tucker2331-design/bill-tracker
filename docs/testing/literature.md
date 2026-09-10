---
tags: [testing, research, war-room, literature, method]
updated: 2026-09-10
status: active
---

# The reading list: what the field already knows

## Why this exists

Owner, 2026-09-10: *"think big picture collect literature titles essays interviews etc from lobbyists and
those that might be relevent in our hunt for relevent historical info and signals."*

Every indicator here so far was derived bottom-up from whatever happened to be in the data. That is how we
spent weeks measuring floor votes while the room that actually decides — the subcommittee — sat unopened
in a file we already had. **A reading list is the corrective:** it says what is already settled, what has
already failed, and which signals practitioners actually act on, before another week goes into
rediscovering it.

## The corpus

**15 sources fetched to text, 182,968 words**, cached under `tools/literature/sources/` with a manifest
recording url, word count, sha256 and fetch date.

```bash
python3 tools/literature/corpus.py            # fetch what is missing (idempotent)
python3 tools/literature/corpus.py --status   # word counts, by medium
```

Mixed deliberately by **medium and by whose interest the author serves**, because each kind lies
differently:

| kind | n | what it is good for | how it misleads |
|---|---|---|---|
| peer-reviewed | 8 | denominators, controls, null results | studies Congress far more than statehouses |
| practitioner | 3 | what actually happens in a hearing room | is selling something |
| interview | 2 | the mechanism behind the statistic | unrepresentative by construction |
| journalism | 1 | the specific case an average hides | not systematic |
| government | 1 | definitive on procedure | silent on effectiveness |

**A claim that survives in all of them is worth building on. A claim in only one is a lead.**

### The three long-form works (>=10,000 words)

| words | work |
|---|---|
| **65,890** | Drutman, *The Business of America is Lobbying* — the full UC Berkeley dissertation behind the 2015 OUP book, with the appendices the trade edition drops |
| **52,540** | *Three Essays on Lobbying* — Harvard PhD dissertation (DASH open repository) |
| **10,465** | Butler & Miller, *Does Lobbying Affect Bill Advancement? Evidence from Three State Legislatures* |

## What the verified sources already say about OUR findings

Read before the digest pass, because three of these bear directly on numbers we have already shipped.

**1. Our structural-over-text thesis is confirmed at national scale, by someone else.**
Eidelman, Kornilova & Argyle (COLING 2018) predict floor action across **1.3M bills, 50 states + DC**,
reaching **85.9% accuracy / 0.85 AUROC**. Their feature ranking: **committee information is the most
predictive, sponsor second, bill text only a modest gain** — and *"knowing sponsor related information,
without reference to the subject of the legislation, is itself highly predictive."* That is
[[testing/kill_points]] and [[testing/subject_labels]] arrived at independently, on 60x our corpus.

**2. Our minority-penalty and co-patron findings replicate on a different corpus.**
Nay (PLOS ONE 2017), ~70,000 bills across the 103rd-113th Congress, AUC up to 0.96. Top features in order:
**sponsor's party in the majority**, bill text, **cosponsor count**, sponsor experience. We measured the
same two signals in Virginia (25pt minority penalty; co-patron effect) without knowing this existed.

**3. A caveat we must attach to our own kill-point finding.**
RVAHub / VCU Capital News Service (2017): of **571 failed House bills, more than two-thirds were killed on
UNRECORDED voice votes in subcommittee.** Those kills cannot appear in `Vote.csv`. **So our recorded
subcommittee roll calls are a SUBSET, and the subcommittee is a bigger kill point than we measured, not a
smaller one.** This does not weaken the finding; it means the true gate is even narrower.

**4. A finding that would reframe the product if it holds in Virginia.**
Baumgartner et al., *Lobbying and Policy Change* (2009), 98 randomly-sampled issues over four years:
**~60% of lobbying campaigns produced no policy change, and resources explain under 5% of the variance
between winning and losing.** If that transfers, the edge we sell is not money or volume — it is knowing
where the veto points are, which is exactly what [[testing/kill_points]] measures.

## The full list

**Peer-reviewed (8 fetched)** — Eidelman et al. 2018 (state floor action, 1.3M bills) · Nay 2017 PLOS ONE
+ 2016 preprint (law-making prediction) · Yano, Smith & Wilkerson NAACL 2012 (**bill survival in
committee** — the direct precedent for kill_points) · Shor & Kistner (state agenda influence 2011-2023) ·
Drutman dissertation · Harvard *Three Essays on Lobbying* · Butler & Miller (state bill advancement).

**Practitioner (3)** — Plural Policy and Quorum are **direct competitors**, and their own how-to pages are
the baseline our product has to beat; Bloomberg Government on why state work differs from federal.

**Interview (2)** — U.S. Senate Historical Office and U.S. House Oral History programs: first-person
accounts of how decisions were actually made, which is the mechanism behind every statistic above.

**Government (1)** — Virginia General Assembly's own **Glossary & Legislative Terms**: the publisher's
definitions of the action vocabulary our classifiers key on (*passed by indefinitely*, *stricken from
docket*, *continued to*). Authoritative for Standard #3 structural mapping.

**Journalism (1)** — RVAHub 2017 on unrecorded subcommittee votes.

**Books (3, not fetchable in full)** — Baumgartner et al. 2009 · Drutman 2015 (the dissertation IS
fetched, above) · Guyer, *Guide to State Legislative Lobbying* 3rd ed., a practitioner manual specifically
for **state** work where nearly all the academic literature is federal.

## UNREAD — 5 sources blocked, recorded rather than quietly dropped

A reading list that silently omits what it could not read is worse than one that says so.

| source | status |
|---|---|
| Kwak, *Party Cartels, Committee Gatekeepers, and Subcommittee Activity* (LSQ 2026) | 403 — publisher blocks both the fetcher and WebFetch. **The most costly gap: it is the one theoretical treatment of subcommittees as a distinct gatekeeping venue.** |
| Garlick, Junk & Brown, *How Lobbying Matters* (Annu. Rev. Pol. Sci. 28:457-475, 2025) | 403. Known from secondary sources to argue the empirical gap closed in the last decade via causal-inference designs, and to identify transactional access and informational persuasion as distinct mechanisms. Listed as open access — retry via the Copenhagen research portal. |
| CRS R44292, *The Lobbying Disclosure Act at 20* | 403 on congress.gov |
| Virginia Mercury, *What's alive and what's dead at the 2026 midway point* | 403 |
| OpenSecrets, *Lobbying Timeline* | 403 |

## The digest — what it changed

**THE CENTRAL FINDING REPLICATES, INDEPENDENTLY.** Butler & Miller, on the full universe of proposals in
THREE state legislatures: *"lobbying does not buy the votes of legislators on the committees of
jurisdiction for each bill, but lobbying does strongly predict what bills make it onto the agenda."*

We reached the same conclusion from a completely different direction — decomposing Virginia outcomes into
terminal events and finding timing beats votes **4.8 : 1**. They had lobbying-position data and no
committee roll calls; we had committee roll calls and no lobbying positions. **Different data, different
method, same answer.** That is the strongest evidence available that this is not a Virginia artifact.

**KILLING IS 2.4x EASIER THAN PASSING.** Same paper: one-sided lobbying FOR a bill is worth **+11
percentage points** of enactment probability; one-sided lobbying AGAINST is worth **-26**. A defensive
client and an offensive client are not running the same play at different odds — they are running
different games.

**THE ACTION IS BEFORE THE FLOOR.** Shor & Kistner find agenda-control effects **1.5-2x larger for
pre-final-passage votes than for final passage**, and that minority-sponsored bills are the ones most
likely to roll a majority. Consistent with [[testing/kill_points]]: the floor is where outcomes are
ratified, not decided.

**A WRONG SOURCE, caught by grepping for the claim it was cited for.** Yano et al. was first cited at ACL
id `N12-1033`, which is a **stylometry paper about detecting non-native English writers** — 9,469 words
sitting in the corpus as apparent evidence. Corrected to `N12-1097`. **Verify a fetched source says what
you cited it for before counting it as read**; a wrong source reads as support and its word count reads as
diligence.

## Related

[[testing/kill_points]] · [[testing/persuadability]] · [[testing/subject_labels]] ·
[[testing/calibration_ledger]] · [[index]] · [[log]]
