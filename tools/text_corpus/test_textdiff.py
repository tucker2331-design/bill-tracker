"""Structural tests for the text-difference percentage (E5)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from textdiff import compare_versions, difference_label, difference_pct, drift_from_introduced

A = "A BILL to amend the Code of Virginia relating to consumer data protection."
B = "A BILL to amend the Code of Virginia relating to consumer privacy protection."


def test_identical_is_zero():
    assert difference_pct(A, A) == 0.0


def test_edit_lands_strictly_between_zero_and_hundred():
    assert 0.0 < difference_pct(A, B) < 100.0


def test_missing_side_is_None_not_zero_and_not_hundred():
    """'We have no text for one side' is evidence of neither sameness nor difference."""
    for pair in ((A, ""), ("", A), (A, None), (None, A), (None, None), ("", "")):
        assert difference_pct(*pair) is None, pair


def test_symmetric():
    assert difference_pct(A, B) == difference_pct(B, A)


def test_label_never_bands_or_judges():
    """P25: no 'minor edits' / 'substantial rewrite'. The number plus its unit, nothing more."""
    assert difference_label(0.0) == "0% different"
    assert difference_label(11.0) == "11% different"
    assert difference_label(None) == "not comparable"


def test_compare_versions_keeps_both_endpoints():
    vs = [{"label": "Introduced", "text": A}, {"label": "Substitute", "text": B}]
    out = compare_versions(vs)
    assert out[0]["from"] == "Introduced" and out[0]["to"] == "Substitute"
    assert out[0]["pct"] == difference_pct(A, B)


def test_missing_version_is_kept_with_none_not_dropped():
    """A missing version must not make the chain look shorter than it is."""
    vs = [{"label": "Introduced", "text": A}, {"label": "Substitute", "text": ""},
          {"label": "Engrossed", "text": B}]
    out = compare_versions(vs)
    assert len(out) == 2
    assert out[0]["pct"] is None and out[1]["pct"] is None


def test_drift_is_one_comparison_not_a_sum():
    """Summing consecutive diffs double-counts twice-edited text and can exceed 100%."""
    vs = [{"label": "Introduced", "text": A}, {"label": "Substitute", "text": B},
          {"label": "Engrossed", "text": A}]
    steps = compare_versions(vs)
    drift = drift_from_introduced(vs)
    assert drift["pct"] == 0.0                     # ended where it started
    assert sum(s["pct"] for s in steps) > 0.0      # but the path was not zero
    assert drift["from"] == "Introduced" and drift["to"] == "Engrossed"


def test_drift_needs_two_versions():
    assert drift_from_introduced([{"label": "Introduced", "text": A}]) is None


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print("  ok", f.__name__)
    print(f"\n{len(fns)} of {len(fns)} passed")
