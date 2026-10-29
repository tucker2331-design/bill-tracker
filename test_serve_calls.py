"""Goldens for tools/calibration/serve_calls.py -- the pure parts of serving War Room calls.

The model itself is frozen and scored by the pre-registration; these check what the page is told: the call rule,
the per-bill grouping and its counts, the k-of-n evidence, and that a changed pinned file serves nothing.
Run: python3 test_serve_calls.py   (no network, no zips, no credentials)
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "calibration"))
import serve_calls as S  # noqa: E402

_n = 0


def ok(cond, msg):
    global _n
    _n += 1
    if not cond:
        raise AssertionError(msg)


# the pre-registered edge, both sides, exactly at the line
ok(S.call_of(0.81) == "yes" and S.call_of(0.19) == "no", "a call at exactly |p-.5| = .31")
ok(S.call_of(0.80) == "cant_call" and S.call_of(0.20) == "cant_call" and S.call_of(0.5) == "cant_call",
   "inside the edge is can't call")
ok(S.call_of(0.99) == "yes" and S.call_of(0.01) == "no", "far calls")


def ballot(who, y, party="D", **k):
    r = {"bill": ("2026", "HB 1515"), "who": who, "party": party, "y": y, "room": "Rules", "date": "2026-02-06"}
    r.update(k)
    return r


te = [ballot("Tran", 1, k_mpat=61, n_mpat=62), ballot("Kilgore", 0, party="R"), ballot("Hayes", 1),
      ballot("Helmer", 0), ballot("Sullivan", 1)]
p = [0.95, 0.10, 0.60, 0.90, 0.85]
rows, tot = S.bill_rows(te, p)
ok(len(rows) == 1, "one row per bill")
r = rows[0]
ok(r[0] == "HB1515" and r[1] == "2026" and r[2] == "Rules", f"bill id normalised, session kept: {r[:3]}")
ok(r[4] == 5 and r[5] == 3, f"5 ballots -> 3 yes needed: {r[4:6]}")
ok(r[6:10] == [3, 1, 1, 3], f"called yes / no / can't call / actual yes: {r[6:10]}")
ok(len(S.HEADER) == len(r), "row width == header width")
members = json.loads(r[10])
ok([m["who"] for m in members] == sorted(m["who"] for m in members), "members in name order (no ranking implied)")
tran = next(m for m in members if m["who"] == "Tran")
ok(tran["ev"]["mpat"] == [61, 62] and tran["ev"]["sim"] == [0, 0], f"evidence is k-of-n counts: {tran['ev']}")
# Helmer was called yes at .90 but voted no: a WRONG call must be counted, not hidden
ok(tot["ballots"] == 5 and tot["yes"] == 3 and tot["no"] == 1 and tot["right"] == 3 and tot["wrong"] == 1,
   f"run totals count the wrong call: {dict(tot)}")

# a vote that has not happened yet (live mode, y = -1): no actual, and it never scores a call right or wrong
rows2, tot2 = S.bill_rows([ballot("Tran", -1)], [0.95])
ok(json.loads(rows2[0][10])[0]["actual"] == "" and tot2["right"] == 0 and tot2["wrong"] == 0 and tot2["yes"] == 1,
   f"an unvoted ballot is called but not scored: {dict(tot2)}")

# a changed pinned file serves nothing
real = S.SPEC
tmp = ""
try:
    with open(real, encoding="utf-8") as fh:
        spec = json.load(fh)
    spec["code_sha256"] = {"booster_2027.py": "0" * 64}
    tmp = os.path.join(os.path.dirname(real), "..", ".cache_test_spec.json")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(spec, fh)
    S.SPEC = tmp
    good, bad = S.pinned_code_ok()
    ok(not good and bad == ["booster_2027.py"], "a hash mismatch is refused")
finally:
    S.SPEC = real
    if tmp and os.path.exists(tmp):
        os.remove(tmp)
ok(S.pinned_code_ok() == (True, []), "the committed pins match the committed code")
print(f"ALL {_n} serve-calls tests passed")
