#!/usr/bin/env python3
"""Verify the X-Ray Section 9 bug count against the LIVE production artifact.

WHY THIS EXISTS (assumptions_audit #62): PR #57/#58 were certified by
`full_validate.py`, which fetched each bill's LegislationEvents *fresh* from
LIS — it never exercised the worker's persisted (and, at the time, truncated)
cache. So it reported a 90% collapse that did NOT happen in production. The
lesson: **verify a metric win against the actual production artifact, not a
sidecar tool that reconstructs the inputs independently.**

This script IS that production-faithful check. It:
  1. Reads the LIVE Sheet1 the worker writes (public gviz CSV — no LIS API,
     no auth, read-only, safe to run anytime; adds zero LIS-ban exposure).
  2. Uses the EXACT `classify_action` + pattern lists from the deployed
     X-Ray (`pages/ray2.py`), extracted via `ast` so Streamlit doesn't run
     and so the classifier can NEVER drift from what the X-Ray actually uses.
  3. Reports Section 9 (meeting actions without times) under BOTH the
     text-only classifier (the pre-PR-#57 baseline) and the route-aware
     classifier (production), plus the route distribution on the flagged
     subset and the cache coverage — the numbers that prove (or disprove)
     the drop.

Run it AFTER re-hydrating the LegEvent cache (PR #61 + a Backfill Burst or
several worker cycles). Before re-hydration it will show the routes mostly
blank and the count un-dropped — which is itself the correct, honest signal.

Usage:
    python tools/c7_section9_verify/verify_section9.py
    python tools/c7_section9_verify/verify_section9.py --sheet-id <id>
    python tools/c7_section9_verify/verify_section9.py --json   # machine-readable

Exit code is 0 always (this is a report, not a gate) unless the fetch fails.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import sys
import urllib.request
from collections import Counter

import pandas as pd

# Default Sheet1 — the worker's output, same id the X-Ray defaults to
# (pages/ray2.py DEFAULT_SHEET_ID). Override with --sheet-id if it moves.
DEFAULT_SHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"

# Schema columns the worker writes (everything past these is trailing grid
# padding that gviz exports as Unnamed/blank — we drop it).
_SCHEMA_COLS = [
    "Date", "Time", "SortTime", "Status", "Committee", "Bill", "Outcome",
    "AgendaOrder", "Source", "Origin", "DiagnosticHint", "LegEventRoute",
]


def _repo_root() -> str:
    """tools/c7_section9_verify/ -> repo root."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_production_classifier(repo_root: str):
    """Extract classify_action + its constants from pages/ray2.py via ast.

    We do NOT import pages/ray2.py (it executes Streamlit at module load).
    Extracting the function + the pattern-list constants by source segment
    guarantees we score with the SAME logic the deployed X-Ray uses — the
    single-source-of-truth property that kills worker-vs-tool classifier
    drift (the whole reason the structural router lives at repo root too).
    """
    xray_path = os.path.join(repo_root, "pages", "ray2.py")
    with open(xray_path, encoding="utf-8") as f:  # Gemini PR #65: context manager
        src = f.read()
    tree = ast.parse(src)
    wanted_funcs = {"classify_action", "normalize_time"}
    wanted_consts = {
        "MEETING_ACTION_PATTERNS", "ADMINISTRATIVE_PATTERNS",
        "ADMIN_OVERRIDE_PATTERNS", "PLACEHOLDER_TIMES",
    }
    # Gemini PR #65: collect found constants in ONE pass (no second
    # traversal; robust to multi-target / tuple-unpack assignments).
    const_src, func_src = [], []
    found_consts = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in wanted_consts:
                    const_src.append(ast.get_source_segment(src, node))
                    found_consts.add(t.id)
        if isinstance(node, ast.FunctionDef) and node.name in wanted_funcs:
            func_src.append(ast.get_source_segment(src, node))
    missing = wanted_consts - found_consts
    if missing:
        raise RuntimeError(
            f"pages/ray2.py is missing expected constants {missing!r} — the "
            f"X-Ray schema changed; update this tool to match."
        )
    ns: dict = {}
    exec("\n".join(const_src) + "\n" + "\n".join(func_src), ns)
    return ns["classify_action"], ns["normalize_time"], ns["PLACEHOLDER_TIMES"]


def fetch_tab_csv(sheet_id: str, tab: str) -> pd.DataFrame:
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/gviz/tq?tqx=out:csv&sheet={tab}")
    with urllib.request.urlopen(url, timeout=30) as resp:  # Gemini PR #65: close socket
        raw = resp.read().decode("utf-8")
    return pd.read_csv(io.StringIO(raw))


def verify(sheet_id: str) -> dict:
    repo_root = _repo_root()
    classify_action, normalize_time, placeholder_times = load_production_classifier(repo_root)

    df = fetch_tab_csv(sheet_id, "Sheet1")
    df = df[[c for c in df.columns if c in _SCHEMA_COLS]].copy()
    for col in _SCHEMA_COLS:
        if col not in df.columns:
            df[col] = ""

    has_route = df["LegEventRoute"].fillna("").astype(str).str.strip().ne("").any()
    has_time = ~df["Time"].map(normalize_time).isin(placeholder_times)

    # Text-only (pre-PR-#57) vs route-aware (production) classification.
    text_class = df["Outcome"].map(classify_action)
    route_class = pd.Series(
        [classify_action(o, r) for o, r in
         zip(df["Outcome"].fillna(""), df["LegEventRoute"].fillna(""))],
        index=df.index,
    )

    text_bugs = int(((text_class == "meeting") & ~has_time).sum())
    route_bugs = int(((route_class == "meeting") & ~has_time).sum())

    # Route distribution on the text-flagged subset (the proof block).
    flagged = (text_class == "meeting") & ~has_time
    route_on_flagged = (
        df.loc[flagged, "LegEventRoute"].fillna("").astype(str)
        .str.strip().str.lower().replace("", "blank")
    )
    rc = Counter(route_on_flagged)

    # Cache coverage — how many bills actually have persisted events. This is
    # the gauge that goes from ~29% (truncated) toward ~100% as re-hydration
    # proceeds; it's the leading indicator that the routes will populate.
    coverage = None
    try:
        ev = fetch_tab_csv(sheet_id, "LegEvent_Events")
        bills_meta = fetch_tab_csv(sheet_id, "LegEvent_Bills")
        ev_bills = ev["Bill"].astype(str).str.strip().nunique() if "Bill" in ev.columns else 0
        meta_bills = bills_meta["Bill"].astype(str).str.strip().nunique() if "Bill" in bills_meta.columns else 0
        coverage = {
            "bills_with_events": int(ev_bills),
            "bills_in_metadata": int(meta_bills),
            "events_rows": int(len(ev)),
            "pct": round(100.0 * ev_bills / meta_bills, 1) if meta_bills else None,
        }
    except Exception as exc:  # pragma: no cover - network/permission dependent
        coverage = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "sheet_rows": int(len(df)),
        "route_column_populated": bool(has_route),
        "section9_text_only": text_bugs,
        "section9_route_aware": route_bugs,
        "flagged_subset_total": int(flagged.sum()),
        "flagged_route_admin": int(rc.get("admin", 0)),
        "flagged_route_meeting": int(rc.get("meeting", 0)),
        "flagged_route_blank": int(rc.get("blank", 0)),
        "flagged_route_unexpected": {
            k: int(v) for k, v in rc.items()
            if k not in ("admin", "meeting", "blank")
        },
        "cache_coverage": coverage,
    }


def render(report: dict) -> str:
    lines = []
    a = lines.append
    a("=" * 66)
    a("  X-Ray SECTION 9 VERIFICATION (live Sheet1 — production artifact)")
    a("=" * 66)
    a(f"  Sheet1 rows: {report['sheet_rows']:,}   "
      f"LegEventRoute populated: {report['route_column_populated']}")
    a("")
    a(f"  Section 9 (meeting actions WITHOUT times):")
    a(f"    text-only  (pre-PR#57 baseline): {report['section9_text_only']:,}")
    a(f"    route-aware (PRODUCTION now)    : {report['section9_route_aware']:,}")
    delta = report['section9_text_only'] - report['section9_route_aware']
    direction = "drop" if delta > 0 else ("NO CHANGE" if delta == 0 else "INCREASE ⚠️")
    a(f"    delta: {delta:+,}  ({direction})")
    a("")
    ft = report["flagged_subset_total"]
    a(f"  Router verdict on the {ft:,} text-flagged rows (the proof):")
    if ft:
        a(f"    admin   (reclassified — the win)     : {report['flagged_route_admin']:,}")
        a(f"    meeting (genuine — needs time recovery): {report['flagged_route_meeting']:,}")
        a(f"    blank   (no cached event yet)        : {report['flagged_route_blank']:,}")
        if report["flagged_route_unexpected"]:
            a(f"    ⚠️ UNEXPECTED route values: {report['flagged_route_unexpected']}")
    cov = report.get("cache_coverage") or {}
    a("")
    if "pct" in cov and cov.get("pct") is not None:
        a(f"  Cache coverage: {cov['bills_with_events']:,}/{cov['bills_in_metadata']:,} "
          f"bills have events ({cov['pct']}%), {cov['events_rows']:,} event rows.")
        if cov["pct"] < 95:
            a("    → cache NOT fully hydrated yet; blank routes are expected. "
              "Re-run after more cycles / a Backfill Burst.")
        else:
            a("    → cache hydrated; the route-aware number above is the real one.")
    elif "error" in cov:
        a(f"  Cache coverage: unavailable ({cov['error']})")
    a("=" * 66)
    # Honest interpretation guard (the #62 lesson, inline).
    _pct = cov.get("pct")
    if not report["route_column_populated"]:
        a("  VERDICT: LegEventRoute is empty — worker hasn't written routes "
          "(pre-C7.1b-1 code or stale read). Not a real measurement yet.")
    elif _pct is None:
        # Codex P2 (PR #65): coverage unavailable (cache tabs unreadable /
        # malformed / missing) means we CANNOT confirm the cache is
        # hydrated — so we must NOT fall through to a success verdict even
        # if Section 9 dropped. Treat as inconclusive (the whole point of
        # this tool is to refuse premature-victory calls — #62).
        a("  VERDICT: cache coverage could not be measured — INCONCLUSIVE. "
          "Can't confirm the LegEvent cache is hydrated, so the route-aware "
          "count is not yet trustworthy. Fix cache-tab access and re-run.")
    elif _pct < 95:
        a("  VERDICT: cache still hydrating — this is a partial, honest "
          "snapshot, NOT the final number. Do not declare the drop yet.")
    elif delta > 0:
        a(f"  VERDICT: route-aware count is {report['section9_route_aware']:,} "
          f"(down {delta:,} from text-only), cache hydrated. Measured "
          f"against production ✓")
    else:
        a("  VERDICT: cache hydrated but no drop in production. Investigate "
          "before claiming a win.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet-id", default=DEFAULT_SHEET_ID)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()
    try:
        report = verify(args.sheet_id)
    except Exception as exc:
        print(f"ERROR: could not verify ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
