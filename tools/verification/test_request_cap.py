"""Guardrail #4 (LIS request hard ceiling) unit tests. See docs/knowledge/lis_api_safety.md."""
import os, sys
import unittest.mock as mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import calendar_worker as cw


def main():
    fails = []
    adapter = cw._CountingHTTPAdapter()

    # The counter increments in send() BEFORE the real upstream call — mock the parent send to
    # avoid any network and isolate the counting/cap logic.
    with mock.patch.object(cw.HTTPAdapter, "send", return_value="resp") as parent_send:
        # 1) counts each logical request below the cap, without raising
        cw.LIS_REQUEST_CAP = 5
        cw.lis_request_count["n"] = 0
        for _ in range(5):
            adapter.send(None)
        if cw.lis_request_count["n"] != 5:
            fails.append(f"1: expected count 5, got {cw.lis_request_count['n']}")
        if parent_send.call_count != 5:
            fails.append(f"1: parent send should run 5x below cap, ran {parent_send.call_count}")

        # 2) the next request (> cap) aborts via LisRequestCapExceeded WITHOUT making the call
        try:
            adapter.send(None)
            fails.append("2: did not raise above the cap")
        except cw.LisRequestCapExceeded:
            if parent_send.call_count != 5:
                fails.append("2: the over-cap request must NOT reach the upstream (parent send)")

    # 3) counting happens even when the upstream RAISES (retries exhausted) — the Codex P1:
    #    a response hook would count 0 here; send()-counting still counts the logical request.
    cw.LIS_REQUEST_CAP = 100
    cw.lis_request_count["n"] = 0
    with mock.patch.object(cw.HTTPAdapter, "send", side_effect=RuntimeError("retries exhausted")):
        try:
            adapter.send(None)
        except RuntimeError:
            pass
    if cw.lis_request_count["n"] != 1:
        fails.append(f"3: a raising upstream call must still be counted (got {cw.lis_request_count['n']})")

    # 4) the abort is BaseException-derived (bypasses the worker's `except Exception`)
    if not (issubclass(cw.LisRequestCapExceeded, BaseException)
            and not issubclass(cw.LisRequestCapExceeded, Exception)):
        fails.append("4: LisRequestCapExceeded must be BaseException but NOT Exception")

    # 5) cap=0 disables the ceiling entirely
    cw.LIS_REQUEST_CAP = 0
    cw.lis_request_count["n"] = 0
    with mock.patch.object(cw.HTTPAdapter, "send", return_value="resp"):
        for _ in range(100):
            adapter.send(None)
    if cw.lis_request_count["n"] != 100:
        fails.append("5: cap=0 should never raise")

    # 6) get_armored_session resets the counter (no cross-cycle accumulation — Gemini #156)
    cw.lis_request_count["n"] = 99
    cw.get_armored_session()
    if cw.lis_request_count["n"] != 0:
        fails.append(f"6: get_armored_session must reset the counter, got {cw.lis_request_count['n']}")

    # 7) the armored session mounts the counting adapter
    s = cw.get_armored_session()
    if not isinstance(s.get_adapter("https://x"), cw._CountingHTTPAdapter):
        fails.append("7: armored session must mount _CountingHTTPAdapter")

    if fails:
        print("❌ FAILURES:")
        for x in fails:
            print("   -", x)
        sys.exit(1)
    print("✅ all request-cap tests passed (count-in-send, abort-before-call, count-on-raise, "
          "BaseException, disable, per-cycle reset, adapter-mounted)")


if __name__ == "__main__":
    main()
