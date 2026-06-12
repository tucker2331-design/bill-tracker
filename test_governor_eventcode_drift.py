"""Golden tests for structural_router.validate_governor_eventcodes (PR-hardening3).

Locks the drift check that closes the executive prefix rule's one fail-UNSAFE gap (PR-C8.4b):
a brand-new action-required governor EventCode family OUTSIDE G72/G73/G79 would route admin ->
Ledger (a buried veto). This validator SHOUTS on any G-prefix code LIS publishes that we have not
classified. Run: python3 test_governor_eventcode_drift.py  (exit 0 = all pass).
"""
from structural_router import validate_governor_eventcodes, KNOWN_GOVERNOR_EVENTCODES

CASES = [
    # (live_g_codes, expected_drift)
    (["G7900", "G7320", "G7050", "G9998"], []),                        # all known -> no drift
    (sorted(KNOWN_GOVERNOR_EVENTCODES), []),                           # the full classified set -> no drift
    (["G7900", "G8100"], ["G8100"]),                                   # a NEW family (G81xx) -> flagged
    (["G7900", "G8100", "G8100", "G7350"], ["G7350", "G8100"]),        # dedup + sort, multiple new
    ([], []),                                                          # empty
    (None, []),                                                        # None-safe
    (["H7300", "S7300", "G7050"], []),                                 # non-G ignored; G known
    # EventCodes are UPPERCASE by LIS convention (route_event keys on `code[:1]=="G"`); a
    # lowercase token is not a governor code and is correctly ignored, not flagged as drift.
    (["g7900"], []),
    ([" G8100 "], ["G8100"]),                                          # whitespace-tolerant (via _s strip)
]


def main():
    failures = []
    for inp, expected in CASES:
        got = validate_governor_eventcodes(inp)
        status = "ok" if got == expected else "FAIL"
        if got != expected:
            failures.append((inp, got, expected))
        print(f"  [{status}] validate_governor_eventcodes({inp!r}) -> {got} (exp {expected})")
    if failures:
        print(f"\n*** {len(failures)} GOLDEN TEST FAILURE(S) ***")
        for f in failures:
            print(f"    {f}")
        return 1
    print(f"\nAll {len(CASES)} drift-check golden tests pass.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
