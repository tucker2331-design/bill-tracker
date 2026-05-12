---
tags: [workflow, methodology]
updated: 2026-05-12
status: active
---

# Use External Tools Alongside Local Reasoning

**Owner directive, 2026-05-11:**

> Consider opensource info — I see a lot on twitter github reddit etc — make use of your tools, not just your training data.

> Why would you not local reason and just go to the web when you can do both.

## The directive

For technical questions with an authoritative upstream — API contracts, RFCs, published taxonomies, library docs — **the actual source is often better than what training data remembers about it.** Use WebSearch, WebFetch, direct API probes via Bash, and gh CLI alongside local reasoning. Both, not one or the other.

## What this is NOT

- Not "tools instead of reasoning." Local reasoning is fine. The point is don't *only* rely on training data when an authoritative source is one fetch away.
- Not "always probe externally first." Sometimes local reasoning gives the answer cleanly. Sometimes a single API probe saves an hour of inference. Judgment call.
- Not a rule for every task. For pure code edits or repo-local questions, training data + repo grep is usually enough.

## When the external probe is the high-value move

The single concrete example worth holding onto: on 2026-05-11, the derived-classifier audit returned 17.94% PASS / 85.81% precision. Local reasoning would have proposed bigrams / TF-IDF / sentence-transformers — all probabilistic, none reaching 99/0. A 2-minute WebFetch on the live LIS LegislationEvent API surfaced `EventCode`, `LegislationEventTypeID`, `IsPassed`, `IsMapped`, `Status` — structural fields we'd never extracted. The architecture pivoted from "build a better classifier" to "use the structural data that was already in the API response."

The pattern: when a problem feels stuck and the upstream is a documented external system, the upstream's actual response is often the missing piece.

## Tools available

- **WebSearch** — broad lookup, problem-space queries; mandatory "Sources:" footer per tool contract
- **WebFetch** — specific known URLs (docs, raw GitHub files, live API endpoints with public auth)
- **Bash + curl/jq/python** — direct probes against APIs you can reach
- **gh CLI** — GitHub-specific operations that avoid WebFetch's auth wall

## Related

- [[zero_routine_maintenance]] — the architectural principle that today's external research informed
- [[../failures/assumptions_audit#54]] — the failure mode (minimizing the cost of a "small" routine burden) that the external research helped surface
