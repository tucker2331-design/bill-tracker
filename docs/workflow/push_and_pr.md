---
tags: [workflow, git, feedback]
updated: 2026-04-16
status: active
---

# Push + PR Without Asking

Migrated from global `~/.claude/.../memory/feedback_always_push.md` on 2026-04-16.

## Rule

Always push to remote after committing AND create the PR. Provide the PR link. No extra back-and-forth.

## Why

User wants the full workflow in one shot. "Push it for me" means: commit → push → create PR → return link. Asking first wastes a turn.

## How to apply

After every commit:
1. `git push -u origin <branch>` (or `git push` if tracking is already set)
2. `gh pr create --title "..." --body "..."` (per the HEREDOC convention in the Claude Code git guidance)
3. Return the PR URL to the user.

Exception: if the branch is dead per [[workflow/branching_rules]] (previous PR merged/closed), do not push — create a fresh branch from `origin/main` first.

## Don't ask "should I push?"

Unless there's a safety concern (force push to main, push of uncommitted sensitive files, etc.), proceed. The user has pre-authorized this for normal commits.
