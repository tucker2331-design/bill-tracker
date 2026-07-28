"""Structural tests for composition-break detection (E2/E3)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from composition import _majority, detect_break, pooling_is_safe

def _c(session, chair_num, chair_name, party, seats, total):
    return {"session_code": session, "chair_member_number": chair_num, "chair_name": chair_name,
            "majority_party": party, "majority_seats": seats, "seats_total": total}

def test_majority_requires_more_than_half():
    assert _majority({"D": 9, "R": 6}) == ("D", 9, 15)
    assert _majority({"D": 8, "R": 8})[0] is None          # tie is not a majority
    assert _majority({}) == (None, 0, 0)

def test_unknown_party_counts_in_total_but_cannot_form_a_majority():
    """An unknown is not evidence of a side; folding it in would fabricate control."""
    p, seats, total = _majority({"D": 5, "?": 6})
    assert total == 11 and p is None and seats == 5     # 5 of 11 is not a majority
    p2, _, _ = _majority({"D": 6, "?": 5})
    assert p2 == "D"                                     # 6 of 11 is

def test_chair_change_alone_is_a_break():
    """Real case: committee 33 went Ebbin -> McPike with the majority party unchanged."""
    d = detect_break(_c("20251","S1","Ebbin","D",9,15), _c("20261","S2","McPike","D",10,16))
    assert d["changed"] and d["chair_changed"] and not d["majority_changed"]

def test_majority_flip_is_a_break():
    d = detect_break(_c("20251","S1","A","D",9,15), _c("20261","S1","A","R",8,15))
    assert d["changed"] and d["majority_changed"] and not d["chair_changed"]

def test_stable_committee_is_not_a_break():
    d = detect_break(_c("20251","S1","A","D",9,15), _c("20261","S1","A","D",10,16))
    assert not d["changed"]          # seat counts may drift without changing the regime

def test_absent_chair_both_sides_is_not_a_change():
    d = detect_break(_c("20251",None,None,"D",9,15), _c("20261",None,None,"D",9,15))
    assert not d["changed"]

def test_present_to_absent_chair_IS_reported():
    """A real difference in what we know must not read as stability."""
    d = detect_break(_c("20251","S1","A","D",9,15), _c("20261",None,None,"D",9,15))
    assert d["changed"] and d["chair_changed"]

def test_returns_structured_fields_never_a_sentence():
    """P25: callers render ONE invariant template. No prose may leak out of this module."""
    d = detect_break(_c("20251","S1","A","D",9,15), _c("20261","S2","B","R",8,15))
    for v in list(d["from"].values()) + list(d["to"].values()):
        assert not (isinstance(v, str) and " " in v.strip() and len(v) > 40)
    assert set(d) == {"changed","chair_changed","majority_changed","from","to"}

class _FakeFetcher:
    session_code = "20261"
    def __init__(self, members): self._m = members
    def members(self): return self._m


def test_chamber_counts_only_SEATED_members():
    """REGRESSION. members() returns everyone who SERVED, not everyone SEATED. Measured on 20261: 106 House
    people vs 100 seats, the extras being Outgoing/Inactive. Counting them inflates the denominator in
    `seats * 2 > total` and can erase a real majority."""
    from composition import chamber_composition
    mem = {}
    for i in range(51): mem[f"H{i:04d}"] = {"chamber": "H", "party": "D", "status": "Active"}
    for i in range(51, 100): mem[f"H{i:04d}"] = {"chamber": "H", "party": "R", "status": "Active"}
    for i in range(100, 106): mem[f"H{i:04d}"] = {"chamber": "H", "party": "R", "status": "Outgoing"}
    c = chamber_composition(_FakeFetcher(mem), "H")
    assert c["seats_total"] == 100 and c["served_not_seated"] == 6
    assert c["majority_party"] == "D" and c["majority_seats"] == 51
    # The bug this guards, and it is worse than a wrong denominator: with the 6 departed Republicans
    # counted, the chamber reads R 55 of 106 -- the majority FLIPS from D to R. A control filter built on
    # that would attribute Democratic-majority sessions to Republican control.
    bugged = chamber_composition(_FakeFetcher(mem), "H", seated_only=False)
    assert bugged["seats_total"] == 106
    assert bugged["majority_party"] == "R" and bugged["majority_seats"] == 55


def test_pooling_fails_closed_on_error():
    """We cannot prove the composition held, so we must not pool silently."""
    assert pooling_is_safe({"breaks": [], "errors": []}) is True
    assert pooling_is_safe({"breaks": [], "errors": [{"error": "boom"}]}) is False
    assert pooling_is_safe({"breaks": [{"changed": True}], "errors": []}) is False

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f(); print("  ok", f.__name__)
    print(f"\n{len(fns)} of {len(fns)} passed")
