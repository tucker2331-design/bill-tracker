"""PR-C3 helper unit tests — Codex P1 outcome_text matcher.

Reconstructed after the prior session crashed before flushing this file.
Exercises the real `_resolve_via_legislation_event_api` end-to-end by mocking
only the HTTP layer and the alert sink. No reimplementation of the scoring
loop — the production code is the system under test.

Cases:
  1. HB111 / HB505 / HB972 / HB609 on 2026-02-12 — the four Class-1 bugs
     the PR is built to collapse. Each must resolve to the time stated in
     the docstring at calendar_worker.py:603.
  2. HB1 on 2026-03-03 — multi-event same date, same chamber. The naive
     `real_time_events[-1]` would have mis-timed the earlier action; the
     description-overlap matcher must distinguish them.
  3. Negative — outcome_text with zero token overlap → must abstain
     (return None) and let the existing journal_default path emit its
     categorized alert.
  4. Pure helper `_legislation_event_token_set` — strips short / non-alpha
     tokens so chamber prefixes ("H", "S") and connectors ("by", "of")
     don't inflate the overlap score.

Run: `python3 test_pr_c3_helper_v2.py` (no pytest dependency).
"""
import sys
import types


# --- Stub heavyweight deps not installed in the local dev env ----------
# calendar_worker is a deployed worker module; importing it in a unit-test
# context requires stubbing what isn't present locally. CI / prod have
# the real packages.
def _install_stubs():
    for name in ("gspread", "pdfplumber"):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
    if "bs4" not in sys.modules:
        bs4 = types.ModuleType("bs4")
        bs4.BeautifulSoup = type("BeautifulSoup", (), {})
        sys.modules["bs4"] = bs4
    if "google" not in sys.modules:
        google = types.ModuleType("google")
        oauth2 = types.ModuleType("google.oauth2")
        sa = types.ModuleType("google.oauth2.service_account")

        class _Credentials:
            @classmethod
            def from_service_account_info(cls, *_a, **_kw):
                return cls()

        sa.Credentials = _Credentials
        sys.modules["google"] = google
        sys.modules["google.oauth2"] = oauth2
        sys.modules["google.oauth2.service_account"] = sa


_install_stubs()
import calendar_worker  # noqa: E402


# --- Mock plumbing ------------------------------------------------------
class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _FakeSession:
    """Routes by URL substring. The resolver makes two calls: a
    LegislationVersion lookup (skipped when the cache is pre-populated)
    and a LegislationEvent history fetch."""

    def __init__(self, event_payload):
        self.event_payload = event_payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "LegislationEvent" in url:
            return _FakeResponse({"LegislationEvents": self.event_payload})
        if "LegislationVersion" in url:
            return _FakeResponse(
                {"LegislationsVersion": [{"LegislationID": 99999}]}
            )
        raise AssertionError(f"Unexpected URL: {url}")


_alerts = []


def _capture_alert(message, status="WARN", category="UNKNOWN", severity="WARN", dedup_key=None):
    _alerts.append({"message": message, "category": category, "severity": severity, "dedup_key": dedup_key})


def _resolve(bill_num, action_date, outcome_text, events, chamber="H"):
    """Drive the real resolver against an in-memory event payload."""
    cache = {(bill_num, "20261"): 12345}  # pre-cache LegislationID, skip step 1
    session = _FakeSession(events)
    return calendar_worker._resolve_via_legislation_event_api(
        http_session=session,
        bill_num=bill_num,
        action_date_str=action_date,
        outcome_text=outcome_text,
        session_code_5d="20261",
        acting_chamber_code=chamber,
        legislation_id_cache=cache,
        push_alert=_capture_alert,
    )


# --- Tests --------------------------------------------------------------
def test_helper_token_set_filters_short_and_nonalpha():
    f = calendar_worker._legislation_event_token_set
    # "H " (1-letter chamber prefix) and "by" (2 letters) are dropped;
    # "VOTE" is 4 alpha chars so it survives — that's fine because the
    # zero-overlap case (test_zero_overlap_abstains_rather_than_guesses)
    # exercises the actual safety net at the matcher level.
    assert f("H Reported from Committee") == {"reported", "from", "committee"}
    assert f("VOTE: 99-Y 0-N") == {"vote"}
    assert f("Passed by for the day") == {"passed", "for", "the", "day"}
    assert f("") == set()
    assert f(None) == set()


def test_hb111_class1_bug_2026_02_12():
    # Realistic noise: a midnight "filed" event + a Senate-side event that
    # must be filtered out by chamber, plus the target House event.
    events = [
        {"EventDate": "2026-02-12T00:00:00", "ChamberCode": "H", "Description": "Prefiled and ordered printed"},
        {"EventDate": "2026-02-12T15:00:00", "ChamberCode": "S", "Description": "Senate Reported from Committee"},
        {"EventDate": "2026-02-12T21:02:00", "ChamberCode": "H", "Description": "Reported from Privileges and Elections"},
    ]
    result = _resolve("HB111", "2026-02-12", "Reported from Privileges and Elections", events, chamber="H")
    assert result == ("9:02 PM", "21:02", ""), result


def test_hb505_class1_bug_2026_02_12():
    events = [
        {"EventDate": "2026-02-12T21:02:00", "ChamberCode": "H", "Description": "Reported from Privileges and Elections with substitute"},
    ]
    result = _resolve("HB505", "2026-02-12", "Reported from Privileges and Elections with substitute", events, chamber="H")
    assert result == ("9:02 PM", "21:02", ""), result


def test_hb972_class1_bug_2026_02_12():
    events = [
        {"EventDate": "2026-02-12T21:03:00", "ChamberCode": "H", "Description": "Reported from Privileges and Elections"},
    ]
    result = _resolve("HB972", "2026-02-12", "Reported from Privileges and Elections", events, chamber="H")
    assert result == ("9:03 PM", "21:03", ""), result


def test_hb609_class1_bug_2026_02_12():
    events = [
        {"EventDate": "2026-02-12T09:24:00", "ChamberCode": "H", "Description": "Reported from Privileges and Elections"},
    ]
    result = _resolve("HB609", "2026-02-12", "Reported from Privileges and Elections", events, chamber="H")
    assert result == ("9:24 AM", "09:24", ""), result


def test_hb1_multi_event_picks_constitutional_reading_not_passed_by():
    """The exact bug Codex P1 was built to prevent: two events same date+chamber,
    naive `[-1]` would pick the later 'Passed by for the day'. The matcher
    must use the outcome_text to pick the EARLIER 'Constitutional reading'."""
    events = [
        {"EventDate": "2026-03-03T13:44:00", "ChamberCode": "S", "Description": "Constitutional reading dispensed"},
        {"EventDate": "2026-03-03T13:45:00", "ChamberCode": "S", "Description": "Passed by for the day"},
    ]
    result = _resolve("HB1", "2026-03-03", "Constitutional reading dispensed", events, chamber="S")
    assert result == ("1:44 PM", "13:44", ""), result


def test_hb1_multi_event_picks_passed_by_when_outcome_matches():
    """Same payload, opposite outcome — must pick the LATER event."""
    events = [
        {"EventDate": "2026-03-03T13:44:00", "ChamberCode": "S", "Description": "Constitutional reading dispensed"},
        {"EventDate": "2026-03-03T13:45:00", "ChamberCode": "S", "Description": "Passed by for the day"},
    ]
    result = _resolve("HB1", "2026-03-03", "Passed by for the day", events, chamber="S")
    assert result == ("1:45 PM", "13:45", ""), result


def test_zero_overlap_abstains_rather_than_guesses():
    """Codex P1's safety net: if outcome_text has no token overlap with
    any candidate, return None and let journal_default emit the alert."""
    events = [
        {"EventDate": "2026-02-12T21:02:00", "ChamberCode": "H", "Description": "Reported from Privileges and Elections"},
    ]
    result = _resolve("HBXXX", "2026-02-12", "VOTE: 99-Y 0-N", events, chamber="H")
    assert result is None, result


def test_empty_outcome_abstains():
    events = [
        {"EventDate": "2026-02-12T21:02:00", "ChamberCode": "H", "Description": "Reported from Privileges and Elections"},
    ]
    assert _resolve("HBXXX", "2026-02-12", "", events, chamber="H") is None
    assert _resolve("HBXXX", "2026-02-12", None, events, chamber="H") is None


def test_midnight_only_events_are_skipped():
    """Date-only stamps encode 'filed' actions, not real wall-clock times."""
    events = [
        {"EventDate": "2026-02-12T00:00:00", "ChamberCode": "H", "Description": "Reported from Privileges and Elections"},
    ]
    result = _resolve("HBXXX", "2026-02-12", "Reported from Privileges and Elections", events, chamber="H")
    assert result is None, result


def test_wrong_chamber_filtered_out():
    """House actions must not borrow Senate-side timestamps."""
    events = [
        {"EventDate": "2026-02-12T21:02:00", "ChamberCode": "S", "Description": "Reported from Privileges and Elections"},
    ]
    result = _resolve("HBXXX", "2026-02-12", "Reported from Privileges and Elections", events, chamber="H")
    assert result is None, result


# --- Runner -------------------------------------------------------------
if __name__ == "__main__":
    tests = [
        test_helper_token_set_filters_short_and_nonalpha,
        test_hb111_class1_bug_2026_02_12,
        test_hb505_class1_bug_2026_02_12,
        test_hb972_class1_bug_2026_02_12,
        test_hb609_class1_bug_2026_02_12,
        test_hb1_multi_event_picks_constitutional_reading_not_passed_by,
        test_hb1_multi_event_picks_passed_by_when_outcome_matches,
        test_zero_overlap_abstains_rather_than_guesses,
        test_empty_outcome_abstains,
        test_midnight_only_events_are_skipped,
        test_wrong_chamber_filtered_out,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(0 if failed == 0 else 1)
