#!/usr/bin/env python3
"""LIS endpoint-inventory audit — the parity "unknown-unknowns" catcher.

THE OWNER'S GOAL (docs/ideas/lobbyist_jtbd_ideation §8b): "ensure my lobbyists see EVERYTHING they could see
on the state legislative website." A flagged gap costs nearly as much as an unflagged error. The scariest
gap is the one we don't know exists — content on LIS served by an API route we never knew about.

WHAT THIS DOES (read-only, zero LIS *data*-API load):
  1. Fetch the LIS SPA shell (lis.virginia.gov/) + its hashed JS chunks — STATIC assets, not the data API.
  2. Extract every `/<Area>/api/<Method>` route string the SPA references.
  3. Classify each: write/admin/partner (LIS-staff surfaces — never a lobbyist data source) vs public-read.
  4. Diff public-read routes against tools/parity/consumed_endpoints.json (`consumed` + `acknowledged_ignore`).
  5. Report — and, when creds are present (CI), push a categorized alert — for any public-read route in
     NEITHER list: a NEW LIS surface a human should triage (consume it, or park it with a reason).

CHEAPNESS: the SPA chunk filenames carry content hashes; if the shell's script set is unchanged since the
last run (state cell), we still re-parse (it's a few hundred KB of static JS, negligible) but the alert
dedups on the route set so an unchanged surface is silent. No LIS data endpoint is ever called.

Run locally (no creds needed for the audit itself; the alert is skipped):
    python3 tools/parity/endpoint_audit.py
CI (weekly workflow) sets GCP_CREDENTIALS → the alert is written to Sheet1 SYSTEM_ALERT via the same
push mechanism the worker uses. Exit code: 0 always (this is an observability tool, not a gate) UNLESS
--strict is passed (used by a test), which exits 1 when new routes are found.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

LIS_ROOT = "https://lis.virginia.gov"
MANIFEST = Path(__file__).with_name("consumed_endpoints.json")
UA = {"User-Agent": "va-bill-tracker parity-audit (contact: tucker2331@gmail.com)"}
ROUTE_RE = re.compile(r"/[A-Za-z][A-Za-z0-9]*/api/[A-Za-z][A-Za-z0-9]*")
SCRIPT_SRC_RE = re.compile(r'<script[^>]+src="([^"]+)"')


def _fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def extract_routes_from_bundles(root: str = LIS_ROOT):
    """Return (routes:set[str], chunks:list[str]). Never raises — a fetch failure yields empty so the
    caller reports 'could not read the SPA' instead of crashing a scheduled job."""
    try:
        index = _fetch(root + "/")
    except Exception as e:  # network / DNS / TLS — degrade visibly, don't crash
        print(f"⚠️ could not fetch LIS shell ({e}); audit skipped this run.")
        return set(), []
    srcs = SCRIPT_SRC_RE.findall(index)
    chunks = [s for s in srcs if "/static/js/" in s and s.endswith(".js")]
    routes: set[str] = set()
    for src in chunks:
        url = src if src.startswith("http") else root + ("" if src.startswith("/") else "/") + src
        try:
            routes.update(ROUTE_RE.findall(_fetch(url)))
        except Exception as e:
            print(f"⚠️ chunk fetch failed ({src}): {e}")
    return routes, chunks


def _norm(route: str) -> str:
    return route.strip().lower()


def _area(route: str) -> str:
    # "/Member/api/GetX" -> "member"
    return route.strip("/").split("/", 1)[0].lower()


def classify(routes: set[str], manifest: dict):
    """Split live routes into buckets so the residual `new` set is small + meaningful.

    Order matters: consumed → non-public AREA (staff/account/infra) → write/admin VERB → reference/taxonomy
    SUFFIX → specifically-parked public-data → NEW. Everything but `new` is deliberately-not-a-gap; `new` is
    'a public-read DATA route we neither consume nor have a reason for' — the thing a human must triage."""
    consumed = {_norm(e["route"]) for e in manifest["consumed"]}
    ign = manifest["acknowledged_ignore"]
    write_pats = tuple(p.lower() for p in ign["write_admin_patterns"])
    non_public_areas = {a.lower() for a in ign.get("non_public_areas", [])}
    ref_suffixes = tuple(s.lower() for s in ign.get("reference_suffixes", []))
    parked = {_norm(e["route"]) for e in ign["public_read_parked"]}

    out = {"consumed": [], "non_public": [], "reference": [], "parked": [], "new": []}
    for r in sorted(routes):
        n = _norm(r)
        if n in consumed:
            out["consumed"].append(r)
        elif _area(r) in non_public_areas:
            out["non_public"].append(r)    # whole area is a staff/account/infra surface
        elif any(p in n for p in write_pats):
            out["non_public"].append(r)    # write/admin/partner verb
        elif n.endswith(ref_suffixes):
            out["reference"].append(r)     # taxonomy/lookup, not lobbyist-facing DATA
        elif n in parked:
            out["parked"].append(r)
        else:
            out["new"].append(r)           # public-read DATA + not known → a human should look
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 if any NEW public-read route is found")
    ap.add_argument("--root", default=LIS_ROOT)
    ns = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    routes, chunks = extract_routes_from_bundles(ns.root)
    if not routes:
        # No routes parsed: either LIS is down or restructured its bundles. Either is worth a WARN, but not
        # a crash. In CI the alert fires; locally it just prints.
        _maybe_alert("LIS endpoint audit could not extract any API routes from the SPA bundle "
                     f"({len(chunks)} chunk(s) seen). LIS may be down or its bundle layout changed — "
                     "the parity monitor is blind until this is checked.",
                     severity="WARN", dedup="parity_audit_no_routes")
        print("no routes extracted — see alert.")
        return 0

    c = classify(routes, manifest)
    print(f"LIS SPA: {len(chunks)} JS chunk(s), {len(routes)} distinct /api/ routes.")
    print(f"  consumed by us : {len(c['consumed'])}")
    print(f"  non-public     : {len(c['non_public'])}  (staff/account/infra areas + write/admin verbs)")
    print(f"  reference      : {len(c['reference'])}  (taxonomy/lookup, not lobbyist DATA)")
    print(f"  public parked  : {len(c['parked'])}  (known public-read DATA, deliberately not consumed)")
    print(f"  NEW / untriaged: {len(c['new'])}")
    for r in c["new"]:
        print(f"     ⚠ {r}")

    if c["new"]:
        sample = ", ".join(c["new"][:10])
        _maybe_alert(
            f"LIS endpoint parity: {len(c['new'])} API route(s) on the state site are neither consumed nor "
            f"acknowledged: {sample}. Triage each — start reading it (add to consumed_endpoints.json) or "
            f"park it with a reason. A NEW public route can mean data a lobbyist can see on LIS but not here.",
            severity="INFO", dedup="parity_audit_new_routes")

    # Reverse-parity liveness hint (print-only, never alerts): consumed routes the SPA no longer references.
    # A route we depend on that vanishes from the SPA MIGHT be getting deprecated — worth a human glance,
    # but not a fault (verified 2026-07-13 that GetLegislationStatusListAsync is 200-alive yet SPA-absent).
    spa = {_norm(r) for r in routes}
    absent = [e["route"] for e in manifest["consumed"] if _norm(e["route"]) not in spa]
    if absent:
        print(f"  note: {len(absent)} consumed route(s) not referenced by the current SPA "
              f"(direct/independent calls — not a fault): {', '.join(absent)}")

    if ns.strict and c["new"]:
        return 1
    return 0


def _maybe_alert(msg: str, *, severity: str, dedup: str):
    """Push a SYSTEM_ALERT row when creds are present (CI); otherwise print. Mirrors the worker's alert
    row shape so X-Ray/Health surface it. Fail-open: an alert-write failure never breaks the audit."""
    creds = os.environ.get("GCP_CREDENTIALS")
    if not creds:
        print(f"[{severity}] {msg}")
        return
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from datetime import datetime, timezone
        gc = gspread.authorize(Credentials.from_service_account_info(
            json.loads(creds), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
        ws = gc.open_by_key("1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM").worksheet("Metrics_History")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ws.append_row([ts, severity, "system_alert", f"[{severity}:PARITY] {msg}"],
                      value_input_option="RAW")
        print(f"alert written ({severity}): {dedup}")
    except Exception as e:
        print(f"⚠️ alert write failed ({e}); message was: {msg}")


if __name__ == "__main__":
    sys.exit(main())
