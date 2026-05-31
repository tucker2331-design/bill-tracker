---
tags: [workflow, process]
updated: 2026-05-13
status: active
---

# Bot Review Fold-In

External bot review (Codex, Gemini) runs on every open PR. **The bots do not re-review your replies — they review commits.** Responding in the GitHub UI without a follow-up commit leaves the finding unaddressed.

## The loop

1. **Read** the bot reviews on the open PR (`gh pr view <n> --json reviews,comments` + `gh api repos/.../pulls/<n>/comments` for inline).
2. **Triage** each finding:
   - **good / necessary** → fix in code
   - **noise** → respond inline noting why not (rare; assume necessary by default)
3. **Implement** the fixes.
4. **Re-walk the 15-point pre-push audit** on the new diff. Fixes can introduce new issues — especially when the original review missed something the fix surfaces.
5. **Push** the fold-in commit. Tight commit message that lists each finding + how it was addressed.
6. **Brain writeback** in the same PR:
   - log entry noting the fold-in
   - `assumptions_audit` entry IF the finding revealed a recurring bug class (not for one-off style nits)

## What counts as a real signal

- **Codex P1** + **Gemini critical** agreement → definitive; always fix.
- **Codex P2** / **Gemini high** → almost always fix.
- **Gemini medium** → usually fix; the bots are reliable at convention + defensive-coding catches.
- **Style / nits** with no correctness impact → judgment call; tendency should be to fix (cheap, removes review noise).

## What NOT to do

- Don't reply to a fixable finding without also pushing a fix. The bot doesn't re-read; the human reviewer sees an unaddressed comment.
- Don't fold in a fix without re-walking the 15-point audit. Same-class regressions are common (see PR #44 Codex fold-in revealing the dormant `UnboundLocalError`).
- Don't promote a single bot catch into a new CLAUDE.md Standard or new audit Point unless the same shape has appeared multiple times. One nit ≠ a universal rule.

## Examples in this session

- **PR #41** Codex P1 + Gemini critical → [[failures/assumptions_audit#50]] + [[failures/assumptions_audit#51]]
- **PR #44** Codex P1 fold-in → caught a dormant `UnboundLocalError` the original fix exposed (Dead-Path Resurrection, Point 13)
- **PR #45** Codex P2 → [[failures/assumptions_audit#53]] (sentinel-value collision; Point 15)
- **PR #51** Codex P2 + 4 Gemini → this page itself (the loop was implicit; codified after it was reused for the 10th time)
