"""Golden tests for _clean_legevent_cell + its heal telemetry (assumptions_audit #66, scalability_audit).

The helper normalizes a nullable LIS structural field so cache-RELOADED events (which carry the persisted
string "None") route identically to fresh-API events (which carry real ``None``). The 2026-07-10 addition is
a heal COUNTER: the stringified-sentinel heal ("None"/"null"/"nan" -> "") should be near-zero in steady
state, so a flood is a drift canary. A routine ``None`` -> "" must NOT be counted (governor events null
ChamberCode every cycle — counting that would drown the signal).

Pure: no network, no gspread. Run: python3 test_clean_legevent_cell.py
"""
import calendar_worker as cw

_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


# ── normalization: the value transform ─────────────────────────────────────────────────────────────
for raw, want in [
    (None, ""),          # fresh-API null
    ("None", ""),        # persisted str(None) sentinel — the #66 mis-route source
    ("null", ""),
    ("nan", ""),
    ("NONE", ""),        # case-insensitive
    (" None ", ""),      # whitespace-wrapped sentinel
    ("S01", "S01"),      # real committee code — untouched
    ("0", "0"),          # a legit "0" must survive (not a sentinel)
    ("", ""),            # already empty
]:
    got = cw._clean_legevent_cell(raw)
    ok(got == want, f"clean({raw!r}) -> {got!r}, want {want!r}")

# "None" must NOT be stripped out of a real value that merely CONTAINS it (substring safety).
ok(cw._clean_legevent_cell("Noney") == "Noney", "only an EXACT sentinel heals, not a substring")


# ── heal telemetry: count the anomaly, not the routine ──────────────────────────────────────────────
cw._LEGEVENT_HEAL["sentinel"] = 0
cw._LEGEVENT_HEAL["cells_seen"] = 0
for raw in [None, None, "None", "S01", "null", "H14", "nan", None]:
    cw._clean_legevent_cell(raw)
# 8 cells seen; sentinels are only the 3 STRINGIFIED nulls — the 3 real None are routine, not counted.
ok(cw._LEGEVENT_HEAL["cells_seen"] == 8, f"cells_seen counts every call -> {cw._LEGEVENT_HEAL}")
ok(cw._LEGEVENT_HEAL["sentinel"] == 3,
   f"only stringified-null heals count; real None is routine and excluded -> {cw._LEGEVENT_HEAL}")

# The denominator makes the metric honest: a real-null-heavy load (governor events) does not inflate the
# canary, because those go through the None branch, not the sentinel branch.
cw._LEGEVENT_HEAL["sentinel"] = 0
cw._LEGEVENT_HEAL["cells_seen"] = 0
for _ in range(1000):
    cw._clean_legevent_cell(None)
ok(cw._LEGEVENT_HEAL["sentinel"] == 0,
   f"1000 routine nulls raise the canary by 0 (the whole point) -> {cw._LEGEVENT_HEAL}")

print(f"ALL {_checks} _clean_legevent_cell tests passed")
