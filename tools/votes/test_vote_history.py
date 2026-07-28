"""Structural tests for the VOTE.CSV per-member parser (E1).

The golden fixtures below are RAGGED and shaped like the wire, not like a tidy table. That is deliberate:
a fake that does not match the wire is a test that certifies fiction (docs/failures lesson, roster golden).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from vote_history import VoteHistory, id_shape, KNOWN_VOTE_TOKENS


def _vh(rows_text):
    vh = VoteHistory("20261", lambda *a, **k: None)
    return vh.parse(rows_text.encode())


def test_ragged_rows_parse():
    vh = _vh("26110000,H0056,N,H0108,Y\n26110001,H0056,Y,H0108,Y,H0124,X,H0136,N\n")
    assert vh.stats["rows"] == 2
    assert vh.stats["member_votes"] == 6
    assert vh.by_member["H0056"] == {"26110000": "N", "26110001": "Y"}


def test_rows_without_member_detail_are_categorised_not_dropped():
    """The 2,046-row case. A voice vote has no roll call BY NATURE -- it must be explained, never silent."""
    vh = _vh("VSV1001\nC10V2650\n26110000,H0056,Y\n")
    assert vh.stats["rows"] == 3
    assert vh.stats["rows_with_members"] == 1
    assert vh.stats["no_member_detail"]["voice_or_standing"] == 1
    assert vh.stats["no_member_detail"]["committee_id_only"] == 1
    # every row is accounted for in exactly one bucket -- no silent loss
    assert vh.stats["rows_with_members"] + sum(vh.stats["no_member_detail"].values()) == vh.stats["rows"]


def test_unknown_token_is_surfaced_not_skipped():
    """A new code silently dropped would quietly bias every member's record."""
    vh = _vh("26110000,H0056,P,H0108,Y\n")
    assert vh.unknown_tokens["P"] == 1
    assert vh.by_member["H0056"]["26110000"] == "P"   # still recorded -- denominator stays honest
    assert vh.stats["member_votes"] == 2


def test_half_pair_counted_never_guessed():
    vh = _vh("26110000,H0056,Y,H0108\n")
    assert vh.stats["unpaired_cells"] == 1
    assert vh.stats["member_votes"] == 1


def test_agreement_absence_is_not_disagreement():
    """'Voted with us k of n' -- a vote not cast must not count against a member."""
    vh = _vh("V1,H0056,Y\nV2,H0056,N\nV3,H0108,Y\n")
    k, n = vh.agreement("H0056", {"V1": "Y", "V2": "Y", "V3": "Y"})
    assert (k, n) == (1, 2)          # V3 absent -> excluded from BOTH numerator and denominator


def test_agreement_ignores_non_positional_tokens():
    vh = _vh("V1,H0056,X\nV2,H0056,Y\n")
    assert vh.agreement("H0056", {"V1": "Y", "V2": "Y"}) == (1, 1)   # X is not a 'no'


def test_record_for_requires_caller_to_choose_denominator():
    vh = _vh("V1,H0056,Y\nV2,H0056,N\n")
    assert dict(vh.record_for("H0056")) == {"Y": 1, "N": 1}
    assert dict(vh.record_for("H0056", vote_ids=["V1"])) == {"Y": 1}


def test_id_shapes():
    assert id_shape("C10V2650") == "committee_id_only"
    assert id_shape("H01001V2610749") == "chamber_committee"
    assert id_shape("26110000") == "floor"
    assert id_shape("VSV1001") == "voice_or_standing"
    assert id_shape("weird") == "other"


def test_known_tokens_frozen():
    assert KNOWN_VOTE_TOKENS == frozenset({"Y", "N", "X", "A"})


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f(); print("  ok", f.__name__)
    print(f"\n{len(fns)} of {len(fns)} passed")
