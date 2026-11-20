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

def _json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


GOLDEN = _json(os.path.join(ROOT, "goldens", "pa_bill_records_2025_0.json"))["completeness"]
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
    page = _text(os.path.join(HERE, name))
    css = _text(os.path.join(HERE, "chrome.css"))
    for marker, value in {"/*CHROME_CSS*/": css, "<!--CHROME:warroom-->": chrome("warroom"), **extra}.items():
        if marker not in page:
            raise SystemExit(f"{name}: marker {marker} missing")
        page = page.replace(marker, value)
    return page


def drafting_data() -> dict:
    E = _json(os.path.join(ROOT, "tools/calibration/pa/example_drafting.json"))
    prof = _json(os.path.join(ROOT, "tools/historical_cache/census/district_profiles.json"))
    P = prof["states"]["PA"]["chambers"]["lower"]["districts"]
    dist = []
    for r in E["districts"]:
        pl = P[r["d"]]["places"]
        dist.append([r["d"], r["name"] or "(vacant)", r["party"] or "", r["seats"], r["new_member"], r["bills_filed_2025_26"],
                     r["municipalities"], r["school_districts"], r["counties"], r["senate_overlap"], r["people"],
                     pl["nursing_homes"], pl["nursing_home_beds"], pl["hospitals"], pl["schools"], r["majority"]])
    if len(dist) != len(E["shapes"][0]):
        raise SystemExit(f"districts {len(dist)} != map shapes {len(E['shapes'][0])}")
    v5 = _v5()
    who = {r[0]: (r[1], r[2]) for r in dist}
    for law, rec in v5["law_record"].items():
        for row in rec["rows"]:
            if row["district"] not in who:
                raise SystemExit(f"{law}: co-signer district {row['district']} is not a House district")
            row["name"], row["party"] = who[row["district"]]
    return {"v5": {k: v5[k] for k in ("laws", "law_list", "law_record", "first_session")},"dist": dist, "mv": E["measure_values"], "ml": E["measures"], "shapes": E["shapes"], "senators": E["senators"],
            "steer": E["steering"], "ap": E["appropriations"], "ft": E["filing_time"], "parts": E["parts"],
            "mu": {k: v["of"] for k, v in prof["measures"].items()}}


def _v5() -> dict:
    """Facts computed by tools/calibration/pa/pa_mock_v5.py (owner feedback 2026-11-20)."""
    return _json(os.path.join(ROOT, "tools/calibration/pa/mock_v5.json"))


def legislator_data() -> dict:
    L = _json(os.path.join(ROOT, "tools/calibration/pa/legislator_example.json"))
    prof = _json(os.path.join(ROOT, "tools/historical_cache/census/district_profiles.json"))
    ch = "lower" if L["body"] == "H" else "upper"
    L["names"] = {d: (v["member"] or {}).get("name", "") for d, v in prof["states"]["PA"]["chambers"][ch]["districts"].items()
                  if d in {n["d"] for n in L["map"]["inset"]["neighbors"]}}
    v5 = _v5()
    L["v5"] = {"legislator": v5["legislator"], "first_session": v5["first_session"]}
    return L


def main():
    os.makedirs(OUT, exist_ok=True)
    leg = legislator_data()
    links = "const LINKS = " + json.dumps({**LINKS, "legislatorDistrict": leg["district"]}) + ";"
    with open(os.path.join(OUT, "drafting_room_data.json"), "w", encoding="utf-8") as f:
        json.dump(drafting_data(), f, separators=(",", ":"))
    with open(os.path.join(OUT, "drafting_room.html"), "w", encoding="utf-8") as f:
        f.write(fill("drafting_room.html", {"/*LINKS*/": links}))
    with open(os.path.join(OUT, "legislator.html"), "w", encoding="utf-8") as f:
        f.write(fill("legislator.html", {"/*LINKS*/": links, "/*DATA*/": "const DATA = " + json.dumps(leg, separators=(",", ":")) + ";"}))
    for n in ("drafting_room.html", "drafting_room_data.json", "legislator.html"):
        print(n, os.path.getsize(os.path.join(OUT, n)))


if __name__ == "__main__":
    main()
