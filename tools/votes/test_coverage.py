"""Structural tests for coverage windows (E4)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from coverage import AUTHORIZED_SESSIONS, Coverage, coverage_from, coverage_of_votes, session_year


def test_session_year_parses_and_refuses():
    assert session_year("20261") == 2026
    assert session_year("20251") == 2025
    for bad in ("", None, "2026", "abcde", "20261x"):
        assert session_year(bad) is None, bad


def test_single_session_label():
    assert coverage_from(["20261"]).label() == "(2026)"


def test_span_label_uses_an_en_dash():
    lbl = coverage_from(["20261", "20251"]).label()
    assert lbl == "(2025–2026)"          # en-dash: a span, not a subtraction


def test_no_data_yields_None_not_a_plausible_span():
    """The whole point. "No data" and "data covering 2025-2026" must not render identically."""
    assert coverage_from([]).label() is None
    assert coverage_from(["", "  "]).label() is None
    assert Coverage(sessions=()).label() is None


def test_unparseable_codes_are_surfaced_not_dropped():
    c = coverage_from(["20261", "junk"])
    assert c.years == (2026,)
    assert c.unparseable == ("junk",)         # counted, so a caller can alert (Standard #4)
    assert c.label() == "(2026)"


def test_order_and_duplicates_do_not_change_identity():
    assert coverage_from(["20261", "20251"]) == coverage_from(["20251", "20261", "20251"])


def test_exceeds_authorized_flags_unauthorized_sessions():
    """A figure claiming pre-2025 data is a compliance problem, not a display problem."""
    assert coverage_from(["20261"]).exceeds_authorized() == ()
    assert coverage_from(["20201", "20261"]).exceeds_authorized() == ("20201",)


def test_authorized_set_is_the_shared_one_not_a_copy():
    import lis_authorization as la
    assert AUTHORIZED_SESSIONS is la.LIS_HISTORICAL_AUTHORIZED


def test_completeness_detects_mismatched_windows():
    """Two numbers side by side over different windows are not comparable; this is how a caller knows."""
    both = frozenset({"20251", "20261"})
    assert coverage_from(["20251", "20261"]).is_complete_over(both) is True
    assert coverage_from(["20261"]).is_complete_over(both) is False


class _VH:
    def __init__(self, by_member): self.by_member = by_member


def test_member_with_no_votes_has_no_window():
    """A zero must not wear a window that implies we looked and found nothing there."""
    vh = _VH({"S0098": {"V1": "Y"}})
    assert coverage_of_votes(vh, "S0098", "20261").label() == "(2026)"
    assert coverage_of_votes(vh, "H0368", "20261").label() is None


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print("  ok", f.__name__)
    print(f"\n{len(fns)} of {len(fns)} passed")
