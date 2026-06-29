"""Golden tests for structural_router.route_event — the dictionary-free calendar/ledger/executive
router (PR-C7.1b .. C8.4b). Run: python3 test_route_event.py  (exit 0 = all pass).

Locks the structural verdicts, especially the PR-C8.4b EXECUTIVE split: action-required governor
events (veto G79xx / recommendation G72xx/G73xx) -> "executive" (surface on the calendar), while
milestone executive codes (approved/deadline G70xx, Acts-chapter G99xx) stay "admin" (ledger). The
ordering invariant (a veto that is ALSO a ministerial code must STILL surface) is the critical one:
it is the live veto-blindspot guard.
"""
from structural_router import route_event, validate_reference_types

CASES = [
    # (event_dict, ministerial_codes) -> expected route
    # 1. A recorded vote is always a meeting (checked first) — incl. a chamber vote ON a
    #    governor recommendation ("House concurred ... 64-Y 35-N").
    (({"EventCode": "H7300", "VoteTally": "64-Y 35-N"}, frozenset()), "meeting"),
    # 2. EXECUTIVE action-required: veto (G79xx) + recommendation (G72xx / G73xx) -> calendar.
    (({"EventCode": "G7900"}, frozenset()), "executive"),   # Vetoed by Governor
    (({"EventCode": "G7910"}, frozenset()), "executive"),   # veto-family variant
    (({"EventCode": "G7210"}, frozenset()), "executive"),   # recommendation received (House)
    (({"EventCode": "G7220"}, frozenset()), "executive"),   # recommendation received (Senate)
    (({"EventCode": "G7320"}, frozenset()), "executive"),   # recommendation adopted
    (({"EventCode": "G7321"}, frozenset()), "executive"),   # recommendation variant
    (({"EventCode": "G7324"}, frozenset()), "executive"),   # recommendation variant
    # 3. MILESTONE executive -> ledger (admin): approved/deadline (G70xx), Acts chapter (G99xx).
    (({"EventCode": "G7010"}, frozenset()), "admin"),       # Governor's Action Deadline
    (({"EventCode": "G7050"}, frozenset()), "admin"),       # Approved by Governor-Chapter
    (({"EventCode": "G9998"}, frozenset()), "admin"),       # Acts of Assembly chapter text
    (({"EventCode": "G9999"}, frozenset()), "admin"),       # chapter variant
    # 4. CRITICAL ORDERING: a veto/recommendation that is ALSO a ministerial code (no vote/time)
    #    must STILL surface as executive — the executive check runs BEFORE the ministerial check,
    #    or the veto gets buried in the ledger (the live blindspot this PR fixes).
    (({"EventCode": "G7900"}, frozenset({"G7900", "G7050", "G9998"})), "executive"),
    (({"EventCode": "G7320"}, frozenset({"G7320"})), "executive"),
    #    ...but a MILESTONE that is ministerial still goes admin (correct).
    (({"EventCode": "G7050"}, frozenset({"G7050"})), "admin"),
    # 5. A governor actor with no G EventCode -> admin (executive milestone, e.g. blank code).
    (({"ActorType": "Governor", "EventCode": ""}, frozenset()), "admin"),
    # 6. Non-governor structural verdicts still hold (regression guard).
    (({"EventCode": "H5620", "Status": ""}, frozenset({"H5620"})), "admin"),  # ministerial chamber code
    (({"VoteTally": "Y-99"}, frozenset()), "meeting"),       # any recorded vote
    # blank Status is treated as an in-session floor action (existing design: "Read third time" /
    # "Rules suspended" carry blank Status), so a content-less event falls to meeting, not admin.
    (({}, frozenset()), "meeting"),
    ("not a dict", frozenset()),  # placeholder; replaced below
]
# the non-dict defensive case (route_event must never raise):
CASES[-1] = (("not a dict", frozenset()), "admin")


def main():
    failures = []
    for (event, ministerial), expected in CASES:
        got = route_event(event, ministerial_codes=ministerial).route
        status = "ok" if got == expected else "FAIL"
        if got != expected:
            failures.append((event, got, expected))
        label = event.get("EventCode") or event.get("ActorType") or type(event).__name__ if isinstance(event, dict) else repr(event)
        print(f"  [{status}] route_event({label!r:14}) -> {got:10s} (exp {expected})")
    # validate_reference_types drift monitor (sustainability hardening 2026-06-28): the live
    # ReferenceType set is checked against the measured KNOWN_REFERENCE_TYPES vocabulary; a NEW value
    # (LIS adds one) must surface, today's full vocab + blank must not.
    V_CASES = [
        (["Vote", "LegislationText", "Committee", "Subcommittee", "Legislation", "Minutes", "Calendar"], []),
        (["LegislationFile", "", None], []),                 # known + blank/None skipped -> no drift
        (["Vote", "Amendment", "Conference"], ["Amendment", "Conference"]),  # 2 NEW types -> drift (sorted)
        (["nan", "<NA>", "none", "NA", "null", "Committee"], []),  # all NA-like string reprs skipped (CodeRabbit #180)
        ([float("nan"), "Vote"], []),                        # real float NaN skipped (not str("nan"))
        ([], []), (None, []),                                # empty/None -> no drift, never raises
    ]
    for live, expected in V_CASES:
        got = validate_reference_types(live)
        if got != expected:
            failures.append(("validate_reference_types", live, got, expected))
        print(f"  [{'ok' if got==expected else 'FAIL'}] validate_reference_types({live!r}) -> {got}")

    if failures:
        print(f"\n*** {len(failures)} GOLDEN TEST FAILURE(S) ***")
        for f in failures:
            print(f"    {f}")
        return 1
    print(f"\nAll {len(CASES)} route_event + {len(V_CASES)} validate_reference_types golden tests pass.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
