---
tags: [workflow, principle, directive]
updated: 2026-05-11
status: active
---

# Use Tools When Stuck (Web Search, External Probes, Cross-Domain Lookups)

**Owner directive, 2026-05-11:**

> Consider opensource info — I see a lot on twitter github reddit etc — make use of your tools, not just your training data.

> You seemed to have gone pretty surface level with your open source search; this is a very specific web developer problem not just political one. It could be someone solved this problem for a very different reason etc. We need more thought and better precision and understanding.

> Use your tools more when necessary or in a mental block.

## The principle

**When an architecture choice feels like a forced trade-off** (precision vs coverage, automation vs accuracy, performance vs correctness), **the unblocking move is external research, not deeper local reasoning.**

WebSearch, WebFetch, sampling the actual upstream data, and checking how analogous problems are solved in other domains frequently reveal that the apparent trade-off was a framing problem.

## When to reach for tools

| Symptom | Tool to use first |
|---|---|
| "I think the answer is X but I'm not sure if other people have solved this" | WebSearch for the problem class |
| "The spec says A but I want to verify against the actual API behavior" | Bash + curl against the live endpoint |
| "I know there's an open-source project that does this" | WebFetch the specific repo/docs URL |
| "I'm stuck between two architectural options" | WebSearch for cross-domain analogues (healthcare/finance/protocols often solved the same shape first) |
| "The data looks structured but I haven't confirmed the pattern" | Bash + jq/python to enumerate the actual cardinality in cached data |
| "I'm assuming the upstream publishes X" | Probe their site or API for the catalog/dictionary endpoint directly |

## Anti-pattern: spinning on local reasoning

**Symptoms of getting stuck in local reasoning:**

- Reading the same code repeatedly looking for an insight
- Drafting and re-drafting a proposal that feels almost-right but not-quite
- Generating elaborate trade-off analyses without external reference points
- Re-using the same training-data examples that may be stale or incomplete
- Citing "the way this is usually done" without naming the specific source

**The break-out move:** stop reasoning, start searching. Even a 30-second WebFetch against a specific documentation URL beats 5 minutes of inferring what the docs probably say.

## Specific tools and when each is right

### WebSearch
- General problem space lookup ("how do open-source X tools solve Y problem")
- Identifying the canonical names for a pattern (e.g., "entity resolution" vs "record linkage" vs "data joining")
- Finding state-of-the-art in adjacent fields
- **Rate limit:** check the response; the message identifies the reset time
- **MANDATORY:** include sources in the response per WebSearch tool contract

### WebFetch
- Specific documentation URLs you already know
- GitHub raw file URLs (raw.githubusercontent.com)
- Wikipedia for cross-domain analogues
- Live API endpoint probes (when the response is JSON or HTML and you want a summary)
- **Note:** GitHub code search results page requires auth; use specific raw URLs instead

### Bash + curl/jq/python
- Direct API probes when you have credentials or it's a public endpoint
- Enumerating cardinality, distinct values, schema shapes from cached data
- Counting distinct EventCode values across a real corpus before architecting

### gh CLI
- GitHub-specific operations (PR view, issue search, repo metadata)
- Avoids WebFetch's auth limitations
- Useful for finding civic-tech projects that have catalogued state-specific data

## Cross-domain analogue checklist

Before committing to an architecture, ask: **has another domain solved this exact problem shape?** The answer is often yes.

| Problem shape | Domains that solved it first |
|---|---|
| "Coded namespace, finite alphabet, structural identifiers" | HTTP status codes, POSIX errno, MIME types, IANA registries |
| "Vendor-published code dictionary, consumers cache locally" | Healthcare ICD-10/CPT/SNOMED, Financial NAICS, Customs HTS |
| "Multi-source agreement = trust, disagreement = alert" | Distributed consensus (Paxos/Raft), TMR in spacecraft, multi-sig crypto |
| "Free-text-to-structured-category classification" | Spam filters, customer-support routing, search query intent classification |
| "Entity resolution between two structured sources" | Healthcare patient matching, customs declaration matching, ad-tech identity resolution |
| "Hierarchical taxonomy with extensible alphabet" | Linnaean biology, Library of Congress subject headings, Open Civic Data |

If you can name the cross-domain analogue, you can usually find the canonical solution by searching for that domain's name + the problem.

## Concrete example from today (2026-05-11)

**Stuck:** "Our derived classifier hits 17.94% PASS at 85% precision. Sample-size, bigrams, embeddings — all probabilistic. None reach 99/0. Is this lost cause?"

**Local reasoning would have said:** "Try Path A (bigrams), then Path B (TF-IDF), then Path C (sentence-transformers). Each gives marginal gains. Probably 60-85% PASS at best."

**External tools revealed:**
1. WebFetch of the live LIS API endpoint surfaced `EventCode`, `LegislationEventTypeID`, `IsPassed`, `IsMapped`, `Status`, `ActorType`, `ReferenceType` — structural fields we'd never been extracting.
2. WebFetch of OpenStates' canonical taxonomy revealed the 30-category cross-state target vocabulary already exists.
3. Bash probe of 10 bills via curl surfaced the EventCode structural pattern: prefix encodes actor (H/S/G), numeric range encodes phase (4xxx=intro, 5xxx=passage, 7xxx=executive, 9xxx=enacted).
4. Cross-domain analogy: this is the same shape as HTTP status codes — no mapping table needed because the structure IS the semantics.

**Result:** the architecture pivots from "build a better classifier" to "extract the structural function from the LIS spec; cross-validate against OpenStates and Description regex." Zero LLM dependency. Zero routine maintenance.

**Cost of running the tools:** ~2 minutes of WebFetch + Bash calls.
**Cost of NOT running them:** would have shipped a probabilistic classifier that violates Standard #8.

## Process upgrade

Add to [[three_phase_protocol]]'s Phase 1 (context routing) as a routing rule:

> **External research check:** If the task involves a third-party API contract, an industry-standard data shape, or a "how is this usually done" question, the first move is WebSearch/WebFetch/curl against the actual upstream source — not inference from training data. Stale training data is the most common source of "almost-right but not-quite" architectural proposals.

## Related principles

- [[zero_routine_maintenance]] — the architectural constraint that drove this turn's research
- [[../failures/assumptions_audit#54]] — the failure mode this principle prevents
- [[persistent_memory]] — once the external research yields a finding, log it to the brain so future sessions don't re-fetch
