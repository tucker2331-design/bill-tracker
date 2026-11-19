#!/usr/bin/env python3
"""California intake goldens — run on a REAL sample cut from the 2025-26 pubinfo export
(tools/historical_cache/ca/sample/pubinfo_sample.zip: every row of 240 bills chosen across outcomes, plus the
committee-code and legislator tables). Nothing here is synthetic.

    python3 test_ca_intake.py
"""
from __future__ import annotations

import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from states import get_state  # noqa: E402
from states import ca_adapter, ca_pubinfo  # noqa: E402
from states.ca_fetch import BulkFetcher  # noqa: E402
from states.pa_fetch import NotABulkFeed  # noqa: E402

SAMPLE = os.path.join(HERE, "tools", "historical_cache", "ca", "sample")
FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


CA = get_state("CA")
check("CA registered with a crossover marker (house-of-origin deadline)", CA.has_crossover)
check("CA chambers use the contract names", set(CA.chambers.values()) == {"House", "Senate"})
check("CA bill numbers place their origin", CA.origin_chamber("AB12") == "House" and CA.origin_chamber("SB3") == "Senate"
      and CA.origin_chamber("HR5") == "House")
try:
    CA.origin_chamber("XB1")
    check("an unknown prefix raises", False)
except ValueError:
    check("an unknown prefix raises", True)

import tempfile  # noqa: E402
f = BulkFetcher(tempfile.mkdtemp(prefix="ca_fetch_test_"))
for bad in ("https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202520260AB1",
            "https://downloads.leginfo.legislature.ca.gov/../etc/passwd"):
    try:
        f.path(bad)
        check(f"fetcher refuses {bad[:50]}", False)
    except NotABulkFeed:
        check(f"fetcher refuses {bad[:50]}", True)
check("fetcher allows the daily export", any(p.match("https://downloads.leginfo.legislature.ca.gov/pubinfo_daily_Wed.zip")
                                              for p in __import__("states.ca_fetch", fromlist=["_ALLOWED"])._ALLOWED))

schema = ca_pubinfo.load_schema(open(os.path.join(SAMPLE, "pubinfo_load.zip"), "rb").read())
check("schema read from the source's load scripts (18 tables)", len(schema) == 18, str(len(schema)))
ex = ca_pubinfo.Export(os.path.join(SAMPLE, "pubinfo_sample.zip"), schema)
records, comp = ca_adapter.run_intake(ex, datetime.date(2026, 11, 18), "2026-11-18T21:00:00Z")
expected = json.load(open(os.path.join(SAMPLE, "expected.json")))
check("every bill in the sample becomes a record", comp["records_written"] == comp["universe_declared"] == expected["bills"],
      f"{comp['records_written']} / {comp['universe_declared']} / {expected['bills']}")
check("no END_STATUS outside the mapped vocabulary", comp["end_status_unclassified"] == 0, str(comp["end_status_unclassified_sample"]))
check("no row with the wrong field count", not comp["rows_with_wrong_field_count"], str(comp["rows_with_wrong_field_count"]))
stage_ids = {s.id for s in CA.stages}
check("every stage is one of CA's", all(r["stage"] in stage_ids for r in records))
check("every chamber is a contract name", all(r["chamber"] in ("House", "Senate") for r in records))
by = {r["bill"]: r for r in records}
for bill, want in expected["bills_checked"].items():
    r = by.get(bill)
    got = {k: (r or {}).get(k) for k in want}
    check(f"{bill}: {want}", got == want, f"got {got}")
outs = {}
for r in records:
    outs[r["outcome"]] = outs.get(r["outcome"], 0) + 1
check("outcome counts match the measured sample", outs == expected["outcomes"], f"{outs} vs {expected['outcomes']}")

# --- Codex #274 fold-ins ------------------------------------------------------------------------------------------
# P2: a resolution's chapter number means ADOPTED (filed with the Secretary of State), never signed into law.
acr = by.get("ACR44")
check("ACR44 (status Chaptered, chapter 66) is adopted, not signed", acr is not None and acr["outcome"] == "adopted"
      and acr["stage"] == "adopted", str({k: (acr or {}).get(k) for k in ("outcome", "stage")}))
check("no resolution or constitutional amendment is ever 'signed'",
      not [r["bill"] for r in records if r["outcome"] == "signed" and not r["bill"].startswith(("AB", "SB"))])
# P2: the SPA finds the payload by a numeric universe_count (web/src/data/gviz.ts findCompleteness).
check("payload carries universe_count = universe_declared", comp.get("universe_count") == comp["universe_declared"])
check("payload carries the session's display name", comp.get("session_display") == "2025-2026 Regular Session",
      str(comp.get("session_display")))
check("in_history_not_in_universe is a list (Health reads its length)", isinstance(comp.get("in_history_not_in_universe"), list))
# the job stamps records with the SOURCE's publication time, not the check time
r2, c2 = ca_adapter.run_intake(ca_pubinfo.Export(os.path.join(SAMPLE, "pubinfo_sample.zip"), schema),
                               datetime.date(2026, 11, 18), "2026-11-18T21:00:00Z", as_of_utc="2026-11-18T05:23:00Z")
check("records are stamped as of the export, not as of our check",
      all(r["data_as_of_utc"] == "2026-11-18T05:23:00Z" for r in r2) and c2["checked_at_utc"] == "2026-11-18T21:00:00Z")


# P1: a malformed row in a universe table (BILL_TBL / BILL_HISTORY_TBL) refuses publication; elsewhere it is counted.
def _corrupt(table):
    """The real sample with ONE row of `table` cut short by a field (a wrong field count)."""
    import io
    import zipfile
    src = zipfile.ZipFile(os.path.join(SAMPLE, "pubinfo_sample.zip"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for n in src.namelist():
            data = src.read(n)
            if n.upper() == f"{table}.DAT":
                lines = data.decode("utf-8").split("\n")
                lines[0] = "\t".join(lines[0].split("\t")[:-1])
                data = "\n".join(lines).encode("utf-8")
            out.writestr(n, data)
    return ca_pubinfo.Export(buf.getvalue(), schema)


for tbl in ("BILL_TBL", "BILL_HISTORY_TBL"):
    try:
        ca_adapter.run_intake(_corrupt(tbl), datetime.date(2026, 11, 18), "2026-11-18T21:00:00Z")
        check(f"a malformed {tbl} row refuses publication", False)
    except ValueError as e:
        check(f"a malformed {tbl} row refuses publication", "wrong field count" in str(e), str(e))
_r, _c = ca_adapter.run_intake(_corrupt("LEGISLATOR_TBL"), datetime.date(2026, 11, 18), "2026-11-18T21:00:00Z")
check("a malformed row elsewhere is counted (Health: 'Source rows we could not read')",
      _c["rows_with_wrong_field_count_total"] == 1 and _c["rows_with_wrong_field_count"] == {"LEGISLATOR_TBL": 1},
      str(_c["rows_with_wrong_field_count"]))

# P1: the job reads the newest DAILY full export (the yearly file is rebuilt only on Sunday).
from states.ca_fetch import newest_daily  # noqa: E402
_IDX = ('<tr><td><a href="pubinfo_2025.zip">pubinfo_2025.zip</a></td><td align="right">2026-11-15 21:26  </td></tr>\n'
        '<tr><td><a href="pubinfo_daily_Tue.zip">pubinfo_daily_Tue.zip</a></td><td align="right">2026-11-17 21:23  </td></tr>\n'
        '<tr><td><a href="pubinfo_daily_Wed.zip">pubinfo_daily_Wed.zip</a></td><td align="right">2026-11-18 04:23  </td></tr>\n'
        '<tr><td><a href="pubinfo_daily_Thu.zip">pubinfo_daily_Thu.zip</a></td><td align="right">2026-11-12 21:23  </td></tr>\n')
check("the newest daily export is chosen by the index's own date", newest_daily(_IDX) == "pubinfo_daily_Wed.zip",
      newest_daily(_IDX))
try:
    newest_daily(_IDX.replace("daily_", "x_"))
    check("an index with no daily export refuses to guess", False)
except ValueError:
    check("an index with no daily export refuses to guess", True)


class _Resp(__import__("io").BytesIO):
    status = 200
    headers = {"Last-Modified": "Wed, 18 Nov 2026 12:23:41 GMT"}


_d = tempfile.mkdtemp(prefix="ca_fetch_prune_")
open(os.path.join(_d, "0" * 24 + ".body"), "w").write("last week's file")
open(os.path.join(_d, "0" * 24 + ".meta.json"), "w").write("{}")
open(os.path.join(_d, "keep-me.txt"), "w").write("not the fetcher's")
_f = BulkFetcher(_d, opener=lambda req, t: _Resp(b"PK"))
_url = "https://downloads.leginfo.legislature.ca.gov/pubinfo_daily_Wed.zip"
_f.path(_url)
check("the export's date is the server's Last-Modified, in UTC", _f.published_utc(_url) == "2026-11-18T12:23:41Z",
      _f.published_utc(_url))
check("pruning removes only stale fetcher files (2), keeps this run's and foreign files",
      _f.prune_untouched() == 2 and sorted(os.listdir(_d))[-1] == "keep-me.txt" and len(os.listdir(_d)) == 3,
      str(sorted(os.listdir(_d))))

# --- Calendar: committee hearings + floor sessions from the same export (states/ca_calendar.py) ---------------------
from states import ca_calendar  # noqa: E402
from states.ca_committees import sort_time  # noqa: E402
from states.pa_calendar import SHEET1_HEADER  # noqa: E402
_x: dict = {}
_rc, _cc = ca_adapter.run_intake(ca_pubinfo.Export(os.path.join(SAMPLE, "pubinfo_sample.zip"), schema),
                                 datetime.date(2026, 11, 18), "2026-11-18T21:00:00Z", extras=_x)
cal, cst = ca_calendar.build_calendar(ca_pubinfo.Export(os.path.join(SAMPLE, "pubinfo_sample.zip"), schema), _x)
want = expected["calendar"]
check("calendar is written in the shared Sheet1 layout", cal[0] == SHEET1_HEADER)
check("calendar counts match the measured sample", cst == want["stats"] and len(cal) - 1 == want["rows"],
      str({k: (cst.get(k), v) for k, v in want["stats"].items() if cst.get(k) != v}))
for a in want["anchors"]:
    check(f"calendar row {a[0]} {a[4]} {a[5] or '(no bills)'}", a in cal[1:], str(a))
check("every committee code's house agrees with the history (prefix rule checked)", _cc["committee_house_prefix_disagrees"] == 0)
for k in ("calendar_floor_desc_unclassified", "calendar_floor_code_unknown", "calendar_slot_code_unknown",
          "calendar_hearings_without_agenda", "calendar_agenda_bills_unmatched"):
    check(f"{k} = 0 on the real sample", cst[k] == 0, str(cst[k]))
_bills = {r["bill"] for r in _rc}
check("every calendar bill row names a bill on the site",
      all(r[5] in _bills for r in cal[1:] if r[5] and "Extraordinary" not in r[5]))
check("Assembly committees are labelled Assembly, never House", not [r for r in cal[1:] if r[4].startswith("House")]
      and any(r[4].startswith("Assembly ") for r in cal[1:]))
check("a blank source time is shown as Time TBA and counted",
      sum(1 for r in cal[1:] if r[1] == "Time TBA") >= 1 and cst["calendar_time_blank"] >= 1)
for t, want_st in (("1:30 p.m.", "13:30"), ("9 a.m.", "09:00"), ("9:00 AM", "09:00"), ("12 noon", "12:00"),
                   ("Upon Call of the Chair", ""), ("10 minutes prior to Session", ""), ("3 p.m. or upon adjournment", "15:00")):
    check(f"sort_time({t!r}) = {want_st!r}", sort_time(t) == want_st, sort_time(t))
check("a bill's committee in the record is house-qualified ('Assembly …' / 'Senate …')",
      all(r["last_committee"].startswith(("Assembly ", "Senate ")) for r in _rc if r["last_committee"]))

# --- Committee rosters: Open States' public-domain data (golden snapshot, tools/historical_cache/ca/openstates_sample) --
from states import ca_roster  # noqa: E402
from states.pa_roster import ROSTER_HEADER  # noqa: E402
OS_DIR = os.path.join(HERE, "tools", "historical_cache", "ca", "openstates_sample")
roster, rst = ca_roster.build_roster(OS_DIR, _x["committees"], datetime.date(2026, 11, 19))
cov = ca_roster.coverage(_rc, roster)
check("roster is written in the shared Committee_Roster layout", ca_roster.roster_rows(roster)[0] == ROSTER_HEADER)
check("every sample bill sitting in a committee finds its member list (name join checked)",
      cov["bills_committee_without_roster"] == 0, str(cov["committees_without_roster_sample"]))
check("roster: every member resolves to a sitting legislator (party + district)", rst["roster_members_unresolved"] == 0
      and all(x["party"] in ("D", "R", "I") and x["district"] for x in roster), str(rst))
check("roster: every role is one we map", rst["roster_roles_unrecognised"] == 0, str(rst))
check("roster: 57 committees that hear bills, 590 seats (snapshot 2026-11-05)",
      (rst["roster_committees"], rst["roster_seats"]) == (57, 590), str((rst["roster_committees"], rst["roster_seats"])))
_approps = [x for x in roster if x["key"] == "Assembly Appropriations"]
check("Assembly Appropriations: chair first, keyed as a bill's last_committee, chamber key House, name alone",
      bool(_approps) and _approps[0]["role"] == "Chair" and _approps[0]["chamber"] == "House"
      and _approps[0]["committee"] == "Appropriations", str(_approps[:1]))
check("a hyphen or an Oxford comma never splits a committee ('Long-Term' = 'Long Term')",
      ca_roster.norm("Aging and Long-Term Care") == ca_roster.norm("Aging and Long Term Care")
      and ca_roster.norm("Arts, Entertainment, Sports and Tourism") == ca_roster.norm("Arts, Entertainment, Sports, and Tourism"))
try:
    ca_roster.build_roster(os.path.join(OS_DIR, "nope"), _x["committees"], datetime.date(2026, 11, 19))
    check("a missing checkout raises (the job reports roster_status, keeps the old tab)", False)
except FileNotFoundError:
    check("a missing checkout raises (the job reports roster_status, keeps the old tab)", True)

# The site reads these payload keys as Health checks (web/src/states/ca.ts intakeChecks): each must be in the payload.
import re  # noqa: E402
_ts = open(os.path.join(HERE, "web", "src", "states", "ca.ts"), encoding="utf-8").read()
_keys = re.findall(r'\{ key: "([a-z_]+)"', _ts)
_payload = {**_cc, **cst, **cov}
check("every Health check on the CA site reads a key the job publishes", _keys and all(k in _payload for k in _keys),
      str([k for k in _keys if k not in _payload]))

print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
sys.exit(1 if FAILS else 0)
