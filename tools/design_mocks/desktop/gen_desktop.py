#!/usr/bin/env python3
"""Build the desktop mockups (drafting room, legislator page) as they would render on the PA site.

Each page is its own file and its own artifact (owner 2026-11-19: "make them individually … the format id see them
on the page"). The header, tabs, 1180px main and tokens come from chrome.css, copied from web/src/index.css.
Rule: docs/workflow/design_proposal_protocol.md "Mockups use the real page".

Usage: python3 gen_desktop.py <out_dir> [drafting_url] [legislator_url]
Writes <out_dir>/drafting_room.html + drafting_room_data.json, and <out_dir>/legislator.html.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
LINKS = {"drafting": sys.argv[2] if len(sys.argv) > 2 else "", "legislator": sys.argv[3] if len(sys.argv) > 3 else ""}

GOLDEN = json.load(open(os.path.join(ROOT, "goldens", "pa_bill_records_2025_0.json")))["completeness"]
TABS = [("today", "Today"), ("calendar", "Calendar"), ("search", "Search"), ("warroom", "War Room"), ("health", "Health")]


def chrome(active: str) -> str:
    """App.tsx's header: brand, ScopeSwitch, spacer, TrustHeader, SignIn; then the tabs. The bill counts are the
    PA golden's completeness (records_written / universe_declared); clocks, tracking count and name are placeholders."""
    tabs = "".join(f'<a href="#" class="{"active" if k == active else ""}">{v}</a>' for k, v in TABS)
    written, universe = GOLDEN["records_written"], GOLDEN["universe_declared"]
    return (
        '<div class="appheader">'
        '<header class="topbar gut"><div class="brand">PA Bill Tracker</div>'
        '<div class="scope" role="group" aria-label="Scope"><button type="button" class="on">Tracking</button><button type="button">Full GA</button></div>'
        '<div class="spacer"></div>'
        '<div class="trust">'
        '<span class="tr-item">Bills <b>3 hr ago</b></span><span class="tr-div"></span>'
        '<span class="tr-item">Calendar <b>3 hr ago</b></span><span class="tr-div"></span>'
        f'<span class="tr-item">PA General Assembly bills <b>{written:,} / {universe:,}</b></span><span class="tr-div"></span>'
        '<span class="tr-item">Tracking <b>12</b></span><span class="tr-div"></span>'
        f'<span class="tr-item">Session {GOLDEN["session_code"]}</span>'
        '</div>'
        '<span class="signin"><span class="signin-who">[your name]</span><button type="button" class="signin-out">Sign out</button></span>'
        '</header>'
        f'<nav class="nav gut" aria-label="Tabs">{tabs}</nav>'
        '</div>'
    )


def fill(name: str, extra: dict) -> str:
    page = open(os.path.join(HERE, name)).read()
    css = open(os.path.join(HERE, "chrome.css")).read()
    for marker, value in {"/*CHROME_CSS*/": css, "<!--CHROME:warroom-->": chrome("warroom"), **extra}.items():
        if marker not in page:
            raise SystemExit(f"{name}: marker {marker} missing")
        page = page.replace(marker, value)
    return page


def drafting_data() -> dict:
    E = json.load(open(os.path.join(ROOT, "tools/calibration/pa/example_drafting.json")))
    prof = json.load(open(os.path.join(ROOT, "tools/historical_cache/census/district_profiles.json")))
    P = prof["states"]["PA"]["chambers"]["lower"]["districts"]
    dist = []
    for r in E["districts"]:
        pl = P[r["d"]]["places"]
        dist.append([r["d"], r["name"] or "(vacant)", r["party"] or "", r["seats"], r["new_member"], r["bills_filed_2025_26"],
                     r["municipalities"], r["school_districts"], r["counties"], r["senate_overlap"], r["people"],
                     pl["nursing_homes"], pl["nursing_home_beds"], pl["hospitals"], pl["schools"], r["majority"]])
    if len(dist) != len(E["shapes"][0]):
        raise SystemExit(f"districts {len(dist)} != map shapes {len(E['shapes'][0])}")
    return {"dist": dist, "mv": E["measure_values"], "ml": E["measures"], "shapes": E["shapes"], "senators": E["senators"],
            "steer": E["steering"], "ap": E["appropriations"], "ft": E["filing_time"], "parts": E["parts"],
            "mu": {k: v["of"] for k, v in prof["measures"].items()}}


def legislator_data() -> dict:
    L = json.load(open(os.path.join(ROOT, "tools/calibration/pa/legislator_example.json")))
    prof = json.load(open(os.path.join(ROOT, "tools/historical_cache/census/district_profiles.json")))
    ch = "lower" if L["body"] == "H" else "upper"
    L["names"] = {d: (v["member"] or {}).get("name", "") for d, v in prof["states"]["PA"]["chambers"][ch]["districts"].items()
                  if d in {n["d"] for n in L["map"]["inset"]["neighbors"]}}
    return L


def main():
    os.makedirs(OUT, exist_ok=True)
    leg = legislator_data()
    links = "const LINKS = " + json.dumps({**LINKS, "legislatorDistrict": leg["district"]}) + ";"
    with open(os.path.join(OUT, "drafting_room_data.json"), "w") as f:
        json.dump(drafting_data(), f, separators=(",", ":"))
    with open(os.path.join(OUT, "drafting_room.html"), "w") as f:
        f.write(fill("drafting_room.html", {"/*LINKS*/": links}))
    with open(os.path.join(OUT, "legislator.html"), "w") as f:
        f.write(fill("legislator.html", {"/*LINKS*/": links, "/*DATA*/": "const DATA = " + json.dumps(leg, separators=(",", ":")) + ";"}))
    for n in ("drafting_room.html", "drafting_room_data.json", "legislator.html"):
        print(n, os.path.getsize(os.path.join(OUT, n)))


if __name__ == "__main__":
    main()
