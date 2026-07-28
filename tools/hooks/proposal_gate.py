#!/usr/bin/env python3
"""Inject the proposal audit into context at the moment a proposal is produced.

WHY THIS EXISTS (owner, 2026-07-27): the 17-point pre-push audit gates COMMITS.
Nothing gated PROPOSALS -- mockups, stat lists, recommendations -- and in a design
phase those ARE the output. Six failures in one session, every one against a rule
already read at session start. Reading the vault is not the problem; checking it at
output time is. A doc cannot enforce itself, so the enforcement lives here.

Reads the hook event from stdin, emits additionalContext as JSON on stdout.
Full rule: docs/workflow/proposal_audit.md
"""
import json
import sys

FULL = """PROPOSAL AUDIT — run before this artifact is published, and show it filled in.
1 SOURCE      every number: where from, and are we authorized to have it? LIS API = 2025/2026 ONLY
              (pre-2025 -> legacylis.virginia.gov CSV). Cannot name a source -> delete it, do not estimate.
2 CLAIM CLASS each statement sourced / derived / asserted. "similar", "like this", "typical" = tripwires.
3 PRIOR ART   has docs/ already decided this? Follow it or say plainly why you are overriding it.
4 TEST APPLIED  invoked a multi-clause rule? Evaluate EVERY clause, not the one that gets your answer.
5 NO PROSE PER CASE  P25. One invariant template with substituted values, or nothing.
6 ARITHMETIC  compute every total, split and complement. Mockup numbers get checked like real ones.
7 PERSONA     advocacy org lobbying for itself, staffed by volunteers (jtbd 8a) -- not an expert."""

TERSE = ("Proposal audit is live (docs/workflow/proposal_audit.md). If this turn produces a mockup, "
         "stat list, feature proposal or recommendation: source every number (LIS = 2025/26 only), "
         "label claim class, check docs/ for prior decisions, apply every clause of any rule you cite, "
         "no prose-per-case, verify the arithmetic, and write for a volunteer rather than an expert.")

def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        event = {}
    name = event.get("hook_event_name") or ("PreToolUse" if event.get("tool_name") else "UserPromptSubmit")
    print(json.dumps({
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": name,
            "additionalContext": FULL if name == "PreToolUse" else TERSE,
        },
    }))
    return 0

if __name__ == "__main__":
    sys.exit(main())
