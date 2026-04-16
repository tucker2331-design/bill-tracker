---
tags: [workflow, meta]
updated: 2026-04-16
status: active
---

# Persistent Memory Routing

**For this project, `docs/` is the brain.** Not global `~/.claude/...` memory. Not chat history. Not CLAUDE.md buffers.

## The rule

When the LLM would ordinarily save a persistent memory (user preference, project fact, failure lesson, workflow rule, API quirk), it writes to a page in `docs/` instead. See the routing table in [[workflow/three_phase_protocol#PHASE 3: Write-Back Mandate]].

When the LLM starts a new session, it reads [[index]] + [[state/current_status]] + [[state/open_anti_patterns]] before answering any substantive question. That's enough context for most tasks. Other pages are loaded on demand per the Phase 1 routing table.

## Why

1. **Visibility.** Obsidian is the visual interface. The user browses `docs/` in Obsidian with graph view and backlinks — not `~/.claude/`.
2. **Version control.** `docs/` is git-tracked. Knowledge changes have diffs, history, and can be branched/reverted.
3. **One source of truth.** Two memory systems means facts drift. One vault, one answer.
4. **Portability.** If the project ever moves to a different LLM or a different machine, `docs/` travels with the repo. Global memory doesn't.

## Migrated entries (2026-04-16)

Two entries from `~/.claude/projects/-Users-tuckerward-Documents-Projects-bill-tracker/memory/` were moved into this vault:

| Old location | New home |
|--------------|----------|
| `feedback_always_push.md` | [[workflow/push_and_pr]] |
| `project_tba_discovery.md` | [[knowledge/tba_times]] |

The old global files are left in place (the Claude auto-memory harness may re-write them) but this vault is now canonical. If content diverges, `docs/` wins.

## If the auto-memory system writes to global memory anyway

If a future session auto-writes a memory to `~/.claude/.../memory/MEMORY.md` (because the harness does so automatically on certain triggers), treat that as a drift. On the next session, migrate the entry into the appropriate `docs/` page and update [[index]] + [[log]].
