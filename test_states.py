#!/usr/bin/env python3
"""The per-state registry (Standard #6) — stdlib only, runs in the fast structural lane.

Checks: the registry fails CLOSED on an unknown state; VA's config carries the crossover marker and its chamber
map; an unknown bill prefix is an error, not a silent default; and the Python and SPA halves of the VA config agree
on the code, the publisher, the stage ids and the bill link — so the backend and the front end cannot drift apart.
(The TS file is read as text HERE ONLY, in a test, to compare two configs we own — never on a data path.)

Run: python3 test_states.py
"""
import os
import re
import sys

import states

FAILS = 0
HERE = os.path.dirname(os.path.abspath(__file__))


def check(name, ok, detail=""):
    global FAILS
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    FAILS += 0 if ok else 1


va = states.get_state("VA")
check("lookup is case-insensitive", states.get_state("va") is va)
try:
    states.get_state("ZZ")
    check("unknown state fails closed", False, "no KeyError")
except KeyError:
    check("unknown state fails closed", True)
check("VA has a crossover marker", va.has_crossover)
check("VA is an annual session", va.session_years == 1)
check("VA origin chamber HB", va.origin_chamber("HB1") == "House")
check("VA origin chamber sj", va.origin_chamber("sj3") == "Senate")
try:
    va.origin_chamber("X1")
    check("unknown prefix raises", False, "returned a chamber")
except ValueError:
    check("unknown prefix raises", True)
check("VA bill link", va.bill_url("20261", "HB1515") == "https://lis.virginia.gov/bill-details/20261/HB1515")
check("VA two-chamber bills are HB/SB only",
      [b for b in ("HB1", "SB2", "HJ3", "SR4") if va.two_chamber_bill_re.match(b)] == ["HB1", "SB2"])

with open(os.path.join(HERE, "web", "src", "states", "va.ts"), encoding="utf-8") as _f:
    ts = _f.read()
ts_stages = re.findall(r'\{ id: "([a-z0-9]+)"', ts)
check("Python and SPA agree on VA stage ids", ts_stages == [s.id for s in va.stages], f"{ts_stages}")
check("Python and SPA agree on the code", f'code: "{va.code}"' in ts)
check("Python and SPA agree on the publisher", f'sourceName: "{va.source_name}"' in ts)
check("Python and SPA agree on the bill link",
      "https://lis.virginia.gov/bill-details/${sessionCode}/${bill}" in ts
      and va.bill_url_template == "https://lis.virginia.gov/bill-details/{session}/{bill}")
pa = states.get_state("PA")
check("PA registered", "PA" in states.registered())
check("PA has NO crossover stage (no crossover deadline)", not pa.has_crossover)
check("PA is a two-year session", pa.session_years == 2)
check("PA stage list is exactly PA's own (introduced … law, adopted)",
      [s.id for s in pa.stages] == ["introduced", "committee1", "floor1", "committee2", "floor2", "concurrence",
                                     "governor", "law", "adopted"])
check("PA hardcodes no per-bill page link (robots.txt protects /legislation/bills/*)",
      pa.bill_url_template == "" and not any("/legislation/bills" in u for u in pa.urls.values()))
check("PA feeds are all on www.palegis.us", all(u.startswith("https://www.palegis.us/") for u in pa.urls.values()))
check("every registered state has a source adapter", all(states.get_state(c).adapter for c in states.registered()))

sys.exit(1 if FAILS else 0)
