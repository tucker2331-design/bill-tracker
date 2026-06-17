"""Guardrail #4 (LIS request hard ceiling) unit tests. See docs/knowledge/lis_api_safety.md."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import calendar_worker as cw


class _R:  # stand-in for a requests.Response (the hook only counts; it ignores the body)
    pass


def main():
    fails = []

    # 1) counts below the cap without raising
    cw.LIS_REQUEST_CAP = 5
    cw.lis_request_count["n"] = 0
    for _ in range(5):
        cw._lis_request_counter_hook(_R())
    if cw.lis_request_count["n"] != 5:
        fails.append(f"1: expected count 5, got {cw.lis_request_count['n']}")

    # 2) the NEXT request (> cap) aborts via LisRequestCapExceeded
    try:
        cw._lis_request_counter_hook(_R())
        fails.append("2: did not raise above the cap")
    except cw.LisRequestCapExceeded:
        pass

    # 3) the abort is BaseException-derived (bypasses the worker's `except Exception`)
    if not (issubclass(cw.LisRequestCapExceeded, BaseException)
            and not issubclass(cw.LisRequestCapExceeded, Exception)):
        fails.append("3: LisRequestCapExceeded must be BaseException but NOT Exception")

    # 4) cap=0 disables the ceiling entirely
    cw.LIS_REQUEST_CAP = 0
    cw.lis_request_count["n"] = 0
    for _ in range(100):
        cw._lis_request_counter_hook(_R())
    if cw.lis_request_count["n"] != 100:
        fails.append("4: cap=0 should never raise")

    # 5) the hook is actually wired onto the armored session
    if cw._lis_request_counter_hook not in cw.get_armored_session().hooks["response"]:
        fails.append("5: counter hook not attached to the armored session")

    if fails:
        print("❌ FAILURES:")
        for x in fails:
            print("   -", x)
        sys.exit(1)
    print("✅ all request-cap tests passed (count, abort, BaseException, disable, hook-wired)")


if __name__ == "__main__":
    main()
