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

0 WHAT GOVERNS THIS, AND HAVE I READ IT?  <- the general form; checks 1-8 are just its common answers.
  Every failure so far had an authority (a vault rule, a vendor's terms, an API contract, a schema I had
  just written) that I did not open first. If you cannot name what governs a choice, STOP and go find it.
  A longer list of past mistakes never catches the next one; this question does.

1 SOURCE      every number: where from, and are we authorized to have it? LIS API = 2025/2026 ONLY
              (pre-2025 -> legacylis.virginia.gov CSV). Cannot name a source -> delete it, do not estimate.
2 CLAIM CLASS each statement sourced / derived / asserted. "similar", "like this", "typical" = tripwires.
3 PRIOR ART   has docs/ already decided this? Follow it or say plainly why you are overriding it.
4 TEST APPLIED  invoked a multi-clause rule? Evaluate EVERY clause, not the one that gets your answer.
5 NO PROSE PER CASE  P25. One invariant template with substituted values, or nothing.
6 ARITHMETIC  compute every total, split and complement. Mockup numbers get checked like real ones.
7 PERSONA     advocacy org lobbying for itself, staffed by volunteers (jtbd 8a) -- not an expert.
8 VISUAL      grey by default; colour ONLY for the standing meanings (amber=caution, red=dead/stale,
              accent=links/times/active). NO coloured bands or accent rails on cards (doctrine rule 5, and
              an AI tell). Category/state = small-caps TEXT column, not a filled chip.
9 DEPENDENCY  new vendor/API/service? Read its TERMS and its PRICING MODEL before recommending it. Ask:
              does the cost curve bend with OUR growth? Free-at-our-size != free-at-our-shape.
              (LegiScan attestation, VPAP sub-licensing, Access per-seat -- three misses, same class.)"""

CODE = """CODE GATE — you are writing code, which the audit used to skip entirely.
0 WHAT GOVERNS THIS?  the schema, the standards, the doc for this subsystem. Open it, do not recall it.
* PROPAGATION  did this change break a caller? A schema edit means every query; a signature change means
  every call site. Grep for them NOW -- do not wait to be told. (The `state` column was added to the
  migration and no query was updated: every write would have failed the NOT NULL.)
* STANDARD #6  is anything here VA-specific that should be a data dimension? (state, session, chamber)
* STANDARD #4  every failure categorised and counted; no bare except/continue, no silent drop.
* FAIL CLOSED  an absent identity, an empty result, a missing config -- none may read as a valid value.
* MEASURE      assert against a real measured baseline, not a plausible number."""

TERSE = ("Proposal audit is live (docs/workflow/proposal_audit.md). If this turn produces a mockup, "
         "stat list, feature proposal or recommendation: source every number (LIS = 2025/26 only), "
         "label claim class, check docs/ for prior decisions, apply every clause of any rule you cite, "
         "no prose-per-case, verify the arithmetic, write for a volunteer rather than an expert, and keep "
         "the visual grey-by-default -- no coloured bands or accent rails, colour only for standing meanings.")

def main() -> int:
    """Emit the right gate for the event.

    A MALFORMED PAYLOAD IS AN ERROR, NOT A NORMAL EVENT (CodeRabbit, 2026-07-28). The old code coerced
    unparseable stdin to `{}` and then inferred an event name from it, so a broken hook contract would have
    quietly delivered the wrong guidance forever -- the silent-fallback anti-pattern living inside the tool
    built to catch it. We now fail LOUDLY on stderr and exit non-zero; the harness surfaces that, which is
    the only way a dead gate becomes visible.
    """
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"proposal_gate: unparseable hook payload ({exc}); gate did NOT run", file=sys.stderr)
        return 1
    if not isinstance(event, dict):
        print(f"proposal_gate: hook payload was {type(event).__name__}, expected object; gate did NOT run",
              file=sys.stderr)
        return 1
    name = event.get("hook_event_name") or ("PreToolUse" if event.get("tool_name") else "UserPromptSubmit")
    tool = event.get("tool_name") or ""
    if name == "PreToolUse":
        context = CODE if tool in ("Write", "Edit", "NotebookEdit") else FULL
    else:
        context = TERSE
    print(json.dumps({
        "suppressOutput": True,
        "hookSpecificOutput": {"hookEventName": name, "additionalContext": context},
    }))
    return 0

if __name__ == "__main__":
    sys.exit(main())
