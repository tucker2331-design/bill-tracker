---
tags: [workflow, git]
updated: 2026-04-16
status: active
---

# Branching Rules

Extracted from [[failures/assumptions_audit]] #40, which corrected an earlier over-broad rule (PR#20) that caused branch sprawl.

## The rule

Before `git commit` on a follow-up fix, ask: **is the previous PR still open, or closed/merged?**

- **Previous PR still open** (e.g., addressing a Gemini review on an open branch): **push the fix to the existing PR branch.** Do NOT create a new branch — that splits related fixes across multiple PRs.
- **Previous PR closed/merged** (e.g., deploy failure surfaces after merge, user sends fresh screenshots from the running app, Gemini audit references commits that were already in the merged PR): **new branch from `origin/main`.**

## How to infer PR state when the user doesn't say

If the user is sending NEW data (fresh screenshots of a deployed change, a Gemini audit of the PR, deploy outcomes), the previous PR was almost certainly merged/closed first — otherwise that artifact couldn't exist.

Verify with:

```bash
git branch --show-current
gh pr view $(git branch --show-current) --json state -q .state
```

If `MERGED` / `CLOSED` → new branch from main. If `OPEN` → push to current.

## Why this rule exists

Two-time offender pattern: after finishing a PR I'd leave the branch checked out, muscle-memory reaches for `git commit && git push` on whatever branch is current, not "create a new branch from main first." PR#15→PR#16 and PR#19→PR#20 both hit this.

An earlier over-correction ("always new branch for follow-up") caused the opposite problem — Gemini-review fixes getting split into separate PRs needlessly. The current rule turns on PR state, not on "is this a follow-up."

## Invariant

**One PR per branch, and a merged/closed PR's branch is dead.** Don't push to a dead branch.
