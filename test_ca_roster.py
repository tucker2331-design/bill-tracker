#!/usr/bin/env python3
"""California committee rosters — Open States' public-domain (CC0) data joined to pubinfo's committees.
Golden snapshot: tools/historical_cache/ca/openstates_sample (commit bcdda40, 2026-11-05). Needs PyYAML, so it runs
in the golden-tests job (the structural job installs nothing). No network.

    python3 test_ca_roster.py
"""
from __future__ import annotations

import datetime
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from states import ca_adapter, ca_pubinfo  # noqa: E402

SAMPLE = os.path.join(HERE, "tools", "historical_cache", "ca", "sample")
FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


schema = ca_pubinfo.load_schema(open(os.path.join(SAMPLE, "pubinfo_load.zip"), "rb").read())
_x: dict = {}
_rc, _cc = ca_adapter.run_intake(ca_pubinfo.Export(os.path.join(SAMPLE, "pubinfo_sample.zip"), schema),
                                 datetime.date(2026, 11, 18), "2026-11-18T21:00:00Z", extras=_x)

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


check("roster: no unreadable file in the snapshot", rst["roster_files_unreadable"] == 0 and rst["roster_members_unreadable"] == 0)
# one broken file is skipped and COUNTED — it never sinks the whole roster (Gemini #275)
_tmp = tempfile.mkdtemp(prefix="ca_roster_bad_")
shutil.copytree(OS_DIR, os.path.join(_tmp, "ca"))
open(os.path.join(_tmp, "ca", "committees", "zz-broken.yml"), "w").write("- just: a list\n")
open(os.path.join(_tmp, "ca", "legislature", "zz-broken.yml"), "w").write(": : not yaml [\n")
r2, s2 = ca_roster.build_roster(os.path.join(_tmp, "ca"), _x["committees"], datetime.date(2026, 11, 19))
check("an unreadable committee or legislator file is skipped and counted, the rest of the roster stands",
      s2["roster_files_unreadable"] == 2 and sorted(s2["roster_files_unreadable_sample"]) == ["zz-broken.yml", "zz-broken.yml"]
      and len(r2) == len(roster), str(s2))

print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
sys.exit(1 if FAILS else 0)
