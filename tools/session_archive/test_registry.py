"""Registry resolution — the chain's index. Pure, no credentials.

Run: python3 tools/session_archive/test_registry.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from registry import (REGISTRY_HEADER, RegistryError, parse_rows, resolve_active, find_session,
                      already_archived, next_title, new_row)

_p = _f = 0


def is_(name, got, want):
    global _p, _f
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {name} -> {got!r}{'' if ok else f' (want {want!r})'}")
    _p, _f = (_p + 1, _f) if ok else (_p, _f + 1)


H = REGISTRY_HEADER
A = "1AA-archive-one"
B = "1BB-archive-two"


def sheet(*rows):
    return [H] + list(rows)


print("parsing")
recs, bad = parse_rows(sheet(
    ["VA", "20261", A, "VA · Archive", "2026-06-14T00:00:00Z", "37542", "29"],
    ["VA", "20262", A, "VA · Archive", "2026-07-30T00:00:00Z", "3617", "29"],
))
is_("two records", len(recs), 2)
is_("no malformed", bad, 0)
is_("empty sheet", parse_rows([]), ([], 0))

# A row missing an identity field is counted, never silently dropped (Standard #4).
recs2, bad2 = parse_rows(sheet(
    ["VA", "20261", A, "VA · Archive", "2026-06-14T00:00:00Z", "37542", "29"],
    ["VA", "", A, "", "", "", ""],            # no session code
    ["", "20263", A, "", "", "", ""],          # no jurisdiction
    ["VA", "20264", "", "", "", "", ""],       # no workbook id
    ["", "", "", "", "", "", ""],              # blank row: skipped, not counted as malformed
))
is_("keeps only the valid row", len(recs2), 1)
is_("counts the 3 malformed", bad2, 3)

# A renamed/missing column must RAISE, not read as blank — the positional-drift bug class.
try:
    parse_rows([["Jurisdiction", "SessionCode"], ["VA", "20261"]])
    is_("missing WorkbookId column raises", "no raise", "RegistryError")
except RegistryError as e:
    is_("missing WorkbookId column raises", "WorkbookId" in str(e), True)

# Column ORDER must not matter — header-driven, so appending a column later cannot shift the read.
shuffled = [["WorkbookId", "SessionCode", "Jurisdiction", "ArchivedUTC", "Extra"],
            [A, "20261", "VA", "2026-06-14T00:00:00Z", "ignored"]]
recs3, _ = parse_rows(shuffled)
is_("reads by header, not position", recs3[0]["WorkbookId"], A)
is_("an unknown extra column is ignored", "Extra" in recs3[0], False)

print("\nresolution")
is_("active = most recently archived", resolve_active(recs, "VA"), A)
is_("unknown jurisdiction => None (never a default)", resolve_active(recs, "NY"), None)
is_("empty registry => None", resolve_active([], "VA"), None)
is_("case-insensitive jurisdiction", resolve_active(recs, "va"), A)

# 'Active' is by timestamp, NOT sheet row order — row order is not a guarantee anyone maintains.
out_of_order, _ = parse_rows(sheet(
    ["VA", "20271", B, "VA · Archive 2", "2027-01-05T00:00:00Z", "40000", "29"],
    ["VA", "20261", A, "VA · Archive", "2026-06-14T00:00:00Z", "37542", "29"],
))
is_("newest wins regardless of row order", resolve_active(out_of_order, "VA"), B)

print("\nlookup + idempotence")
is_("finds a session's workbook", find_session(recs, "VA", "20261"), A)
is_("finds by int too", find_session(recs, "VA", 20261), A)
is_("unknown session => None", find_session(recs, "VA", "29991"), None)
is_("already archived", already_archived(recs, "VA", "20262"), True)
is_("not yet archived", already_archived(recs, "VA", "20271"), False)

print("\nchain naming")
is_("first workbook keeps the base title", next_title([], "VA", "VA · Archive"), "VA · Archive")
is_("second is ' 2'", next_title(recs, "VA", "VA · Archive"), "VA · Archive 2")
is_("counts DISTINCT books, not rows", next_title(out_of_order, "VA", "VA · Archive"), "VA · Archive 3")
# Another jurisdiction's books must not affect VA's numbering (Standard #6).
mixed, _ = parse_rows(sheet(
    ["VA", "20261", A, "VA · Archive", "2026-06-14T00:00:00Z", "37542", "29"],
    ["NY", "2025A", B, "NY · Archive", "2026-06-14T00:00:00Z", "1000", "29"],
))
is_("NY rows do not renumber VA", next_title(mixed, "VA", "VA · Archive"), "VA · Archive 2")
is_("VA rows do not renumber NY", next_title(mixed, "NY", "NY · Archive"), "NY · Archive 2")
is_("NY resolves to its own book", resolve_active(mixed, "NY"), B)

print("\nrow construction")
import datetime
r = new_row("va", 20271, B, "VA · Archive 2", 40000, 29,
            now=datetime.datetime(2027, 1, 5, 12, 0, 0, tzinfo=datetime.timezone.utc))
is_("row matches header arity", len(r), len(H))
is_("jurisdiction upper-cased", r[0], "VA")
is_("session stringified", r[1], "20271")
is_("timestamp is ISO-Z (lexically sortable)", r[4], "2027-01-05T12:00:00Z")
# Round-trip: a row we write must parse back to what we wrote.
back, _ = parse_rows([H, r])
is_("round-trips", (back[0]["WorkbookId"], back[0]["SessionCode"]), (B, "20271"))
is_("round-trip is resolvable", resolve_active(back, "VA"), B)

print(f"\n{_p} of {_p + _f} passed")
sys.exit(1 if _f else 0)
