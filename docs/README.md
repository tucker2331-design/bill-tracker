---
tags: [meta, vault]
updated: 2026-04-16
status: active
---

# Project Brain — Vault Entry

This folder is an **Obsidian vault**. It's the single source of truth for everything the project has learned about itself: architecture, domain knowledge, failure lessons, workflow, and live state.

Open this vault in Obsidian (point Obsidian at this `docs/` directory). Start at [[index]].

## How this vault works

The pattern is the **[LLM-Wiki](https://github.com/)** approach:

- **You** curate sources, ask questions, direct exploration.
- **The LLM** reads sources, writes wiki pages, cross-references them, keeps the index and log current, flags contradictions.
- **Obsidian** is the visual interface — graph view, backlinks, Dataview.
- **Git** is version control — the whole vault is markdown files committed to the repo.

## Entry points (read in this order)

1. [[index]] — catalog of every page. Drill here first.
2. [[state/current_status]] — what's active right now, which PR is open, what the bug count is.
3. [[state/open_anti_patterns]] — known silent-fallback debt in the code.
4. [[log]] — chronological record of ingests / decisions / PRs.

## For the LLM maintaining this vault

Read [[workflow/persistent_memory]] first. The short version: **this vault is THE brain for this project**. Not global `~/.claude/` memory. All persistent memory writes land here.

The operating lifecycle is in [[workflow/three_phase_protocol]]:
- **Phase 1 — Context routing:** read [[index]] first, then the specific pages relevant to the task.
- **Phase 2 — Pre-push audit:** run the 9-point checklist before every commit.
- **Phase 3 — Write-back:** every lesson, API quirk, failure, metric delta, and PR event gets filed back into the vault before the session ends.

## Vault structure

```
docs/
├── README.md                          # this file — vault entry
├── index.md                           # catalog
├── log.md                             # chronological record
├── state/                             # live trackers
│   ├── current_status.md
│   └── open_anti_patterns.md
├── workflow/                          # how we work
│   ├── three_phase_protocol.md
│   ├── branching_rules.md
│   ├── push_and_pr.md
│   ├── source_miss_visibility.md
│   └── persistent_memory.md
├── architecture/                      # system design
│   └── calendar_pipeline.md
├── knowledge/                         # domain knowledge
│   ├── lis_api_reference.md
│   └── tba_times.md
├── testing/                           # metrics & baselines
│   └── crossover_week_baseline.md
├── failures/                          # post-mortems & patterns
│   ├── assumptions_audit.md
│   ├── gemini_review_patterns.md
│   └── pr22_post_mortem.md
└── ideas/                             # deferred work
    └── future_improvements.md
```

## Conventions

- **Wikilinks:** `[[page_name]]` or `[[folder/page_name]]` (not markdown links, unless linking to an external URL). Obsidian's graph view and backlinks need this syntax.
- **Frontmatter on every page:**
  ```yaml
  ---
  tags: [category, subcategory]
  updated: YYYY-MM-DD
  status: active | archived | stub
  ---
  ```
- **One concept per page.** Split if a page covers two things.
- **Cross-reference, don't duplicate.** If a fact belongs on page A, link to it from B rather than copy.
- **Update on touch:** bump the `updated:` field when revisiting a page.
- **Log every structural change:** append an entry to [[log]] using the `## [YYYY-MM-DD] <kind> | <title>` prefix.

## Obsidian settings recommendations (optional)

- **Files and links → Attachment folder path:** `raw/assets/` (for clipped images — not yet used in this vault).
- **Hotkey:** bind "Download attachments for current file" (useful for future web-clipped sources).
- **Graph view:** the graph is currently small (~15 nodes). As the vault grows, use the graph to spot orphan pages (no backlinks) — they usually mean a wikilink is missing somewhere.
- **Dataview plugin:** install to generate dynamic tables from the frontmatter. Example query:
  ````
  ```dataview
  TABLE updated, status FROM "failures" SORT updated DESC
  ```
  ````
- **Marp plugin** (optional): for generating slide decks from wiki pages.

## When the user asks "where do you log mistakes?"

Answer: **inside this vault.** Specifically:
- Line-level bug fixes → [[failures/assumptions_audit]] (numbered, append-only)
- Code-review anti-patterns → [[failures/gemini_review_patterns]] (numbered, append-only)
- Framework-level lessons → a new page in `failures/`, linked from [[index]]
- Live debt → [[state/open_anti_patterns]]

## Relationship to the codebase

The codebase at repo root (`calendar_worker.py`, `pages/ray2.py`, `backend_worker.py`, etc.) is the **raw** layer — immutable to this vault's LLM. The vault describes the code; it does not duplicate it. When the code changes, the vault is updated to reflect new reality — but the code is not edited from the vault.
