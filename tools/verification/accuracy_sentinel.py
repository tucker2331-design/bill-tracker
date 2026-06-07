#!/usr/bin/env python3
"""Accuracy Sentinel — the continuous, SESSION-AGNOSTIC guardian of calendar
accuracy (Standard #2 bank-grade + #8 zero-maintenance).

A one-time audit can't protect next session's NEW data. This runs the SAME
accuracy metric the X-Ray's Section 9 uses, against the LIVE sheet, on a schedule,
and FAILS LOUDLY on any regression — so 2027's data can't silently lose the
accuracy 2026 reached. It reads the sheet directly (whatever session the worker
wrote), extracts the REAL `classify_action`/`normalize_time` from pages/ray2.py
(so it can never drift from production semantics), and checks four invariants:

  1. SECTION 9   meeting-classified rows WITHOUT a time            == 0   (the goal)
  2. UNCLASSIFIED real legislative rows the classifier can't place == 0   (the goal's 2nd half)
  3. FLOOR       legislative row count >= MIN_ROWS                        (partial/empty-sheet guard, lesson #75:
                 "Section 9 = 0 on a 277-row sheet" — a collapsed sheet must FAIL, not pass)
  4. DERIVED     flagged assumed-time rows <= DERIVED_MAX                 (over-derivation guard, G2)

System rows (SYSTEM_ALERT / SYSTEM_METRICS / Committee "System Status") are
EXCLUDED — they are the worker's own diagnostics, not legislative actions.

Exit 0 = all invariants hold; non-zero = regression (the scheduled workflow then
fails and alerts). No secrets — reads the live sheet via the public gviz CSV.
Usage: python3 tools/verification/accuracy_sentinel.py [--min-rows 5000] [--derived-max 25]
"""
import sys, io, csv, re, ast, argparse, urllib.request, time

RAY = "pages/ray2.py"
SHEET = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"

def _get(url, tries=4):
    for a in range(tries):
        try:
            return urllib.request.urlopen(url, timeout=120).read().decode()
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(2 ** a)

def _load_ray2_semantics():
    """Extract the REAL classify_action / normalize_time / PLACEHOLDER_TIMES from
    ray2.py so the sentinel can NEVER drift from production classification."""
    tree = ast.parse(open(RAY).read())
    consts = {"PLACEHOLDER_TIMES", "NON_CONCRETE_LIS_TIMES", "MEETING_ACTION_PATTERNS",
              "ADMINISTRATIVE_PATTERNS", "ADMIN_OVERRIDE_PATTERNS"}
    funcs = {"normalize_time", "classify_action"}
    body = [n for n in tree.body
            if (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in consts for t in n.targets))
            or (isinstance(n, ast.FunctionDef) and n.name in funcs)]
    ns = {"re": re}
    exec(compile(ast.Module(body, []), "ray2-extract", "exec"), ns)
    return ns["classify_action"], ns["normalize_time"], ns["PLACEHOLDER_TIMES"]

def _is_system_row(bill, committee):
    return str(bill).startswith("SYSTEM_") or str(committee).strip() == "System Status"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rows", type=int, default=5000, help="partial-sheet floor (lesson #75)")
    ap.add_argument("--derived-max", type=int, default=25, help="over-derivation guard (G2)")
    ap.add_argument("--section9-max", type=int, default=0)
    ap.add_argument("--unclassified-max", type=int, default=0)
    args = ap.parse_args()

    classify_action, normalize_time, PLACEHOLDER = _load_ray2_semantics()
    rows = list(csv.reader(io.StringIO(_get(
        f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&sheet=Sheet1"))))
    ci = {c: i for i, c in enumerate(rows[0])}
    g = lambda r, c: (r[ci[c]] if c in ci and ci[c] < len(r) else "")

    total = meeting = mwt = unclass = derived = system = 0
    s9_rows, uc_rows = [], []
    for r in rows[1:]:
        if not any(x.strip() for x in r):
            continue
        if _is_system_row(g(r, "Bill"), g(r, "Committee")):
            system += 1
            continue
        total += 1
        cls = classify_action(g(r, "Outcome"), g(r, "LegEventRoute"))
        has_time = normalize_time(g(r, "Time")) not in PLACEHOLDER
        if g(r, "Origin") == "derived_standing":
            derived += 1
        if cls == "meeting":
            meeting += 1
            if not has_time:
                mwt += 1
                if len(s9_rows) < 15: s9_rows.append((g(r, "Bill"), g(r, "Date"), g(r, "Committee"), g(r, "Outcome")[:50]))
        elif cls == "unclassified":
            unclass += 1
            if len(uc_rows) < 15: uc_rows.append((g(r, "Bill"), g(r, "Date"), g(r, "Outcome")[:60]))

    print(f"=== ACCURACY SENTINEL (live sheet, {total} legislative rows; {system} system rows excluded) ===")
    print(f"  meeting={meeting}  unclassified={unclass}  derived_standing={derived}")
    failed = []
    def gate(name, val, mx, examples):
        ok = val <= mx
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {val} (max {mx})")
        if not ok:
            failed.append(name)
            for ex in (examples or []):
                print(f"        - {ex}")
    gate("SECTION 9 (meeting without time)", mwt, args.section9_max, s9_rows)
    gate("UNCLASSIFIED legislative rows", unclass, args.unclassified_max, uc_rows)
    # 3: floor
    floor_ok = total >= args.min_rows
    print(f"  [{'PASS' if floor_ok else 'FAIL'}] FLOOR (legislative rows): {total} (min {args.min_rows}) — partial/empty-sheet guard")
    if not floor_ok:
        failed.append("FLOOR (partial sheet — lesson #75)")
    gate("DERIVED volume (over-derivation guard)", derived, args.derived_max, None)

    if failed:
        print(f"\n🚨 SENTINEL FAIL — {len(failed)} invariant(s) breached: {', '.join(failed)}")
        return 1
    print("\n✅ SENTINEL PASS — all accuracy invariants hold.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
