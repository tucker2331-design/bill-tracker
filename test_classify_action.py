"""Golden tests for structural_router.classify_action (centralized in PR-hardening1a).

classify_action is the single source of truth for the meeting / administrative / executive /
unconfirmed classification, imported by pages/ray2.py, calendar_xray.py, the accuracy sentinel,
and calendar_worker.py. This locks its behavior so the centralization (and any future edit) can
never silently change the lobbyist-facing classification. Run: python3 test_classify_action.py.
"""
from structural_router import classify_action

CASES = [
    # (outcome, route, refid_class, schedule_class) -> expected
    # 1. LegEventRoute is the top authority (wins over every other signal).
    (("anything", "meeting", "BATCH_NOTICE", "DOCKET"), "meeting"),
    (("anything", "admin", "VOTE_COMMITTEE", "MEETING_EVENT"), "administrative"),
    (("Vetoed by Governor", "executive", "", ""), "executive"),
    (("Reported from X (12-Y)", "meeting", "", ""), "meeting"),
    # 2. Blank route + empty/skeleton outcome -> administrative (null-check, not prose).
    (("", "", "", ""), "administrative"),
    (("none", "", "", ""), "administrative"),
    (("nan", "", "", ""), "administrative"),
    (("NaN", "", "", ""), "administrative"),   # case-insensitive null check
    # 3. RefidClass document signals -> administrative (blank route, non-empty outcome).
    (("H Placed on Finance Agenda", "", "SINGLETON_DOC", ""), "administrative"),
    (("H Assigned sub", "", "BATCH_NOTICE", ""), "administrative"),
    (("H Referred to X", "", "COMMITTEE_REF", ""), "administrative"),
    # 4. RefidClass admin OUTRANKS a meeting ScheduleClass (C8.4a consistency: a docket placement
    #    that also matched a same-day meeting is still the placement, like the BATCH equivalents).
    (("H Placed on Agenda", "", "SINGLETON_DOC", "MEETING_EVENT"), "administrative"),
    # 5. ScheduleClass meeting (no admin refid) -> meeting; docket/caucus -> administrative.
    (("Scheduled hearing", "", "", "MEETING_EVENT"), "meeting"),
    (("Floor session", "", "", "FLOOR"), "meeting"),
    (("Commission meeting", "", "", "COMMISSION"), "meeting"),
    (("Placed on agenda", "", "", "DOCKET"), "administrative"),
    (("Caucus", "", "", "CAUCUS"), "administrative"),
    # 6. VOTE_* refid with blank route is NOT a meeting (route is the meeting authority, audit #81)
    #    -> falls through to unconfirmed (surfaced).
    (("H Referred to Appropriations", "", "VOTE_COMMITTEE", ""), "unconfirmed"),
    # 7. No structural signal at all -> unconfirmed (surfaced fail-safe).
    (("Governor's substitute printed", "", "UNKNOWN_REFID", ""), "unconfirmed"),
    (("Some new action", "", "", ""), "unconfirmed"),
    (("vote-id failed join", "", "VOTE_UNMATCHED", ""), "unconfirmed"),
    # 8. Defaults / robustness.
    ((), "administrative"),  # all-default -> empty outcome -> administrative
    ((None, None, None, None), "administrative"),  # None-safe -> empty outcome
]


def main():
    failures = []
    for args, expected in CASES:
        got = classify_action(*args)
        status = "ok" if got == expected else "FAIL"
        if got != expected:
            failures.append((args, got, expected))
        print(f"  [{status}] classify_action{args!r} -> {got} (exp {expected})")
    if failures:
        print(f"\n*** {len(failures)} GOLDEN TEST FAILURE(S) ***")
        for f in failures:
            print(f"    {f}")
        return 1
    print(f"\nAll {len(CASES)} classify_action golden tests pass.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
