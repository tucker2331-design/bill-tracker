#!/usr/bin/env python3
"""Goldens for the days-clean counter's DISPLAY logic (W1.6), run against the TypeScript via node.

Why test the frontend copy of this at all: the number is the visible artifact of the trust promise, so the
two implementations (Python `counter_state`, TS `counterFromRows`) must agree on the honesty rules —
genesis and drills never break the streak, an open incident reads from its start, and an unseeded ledger is
`null` rather than a reassuring zero. A drift between them would make the site claim something the ledger
does not say.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import os

if shutil.which("node") is None:
    print("⚠️  node not available — skipping counter-display goldens (CI runs them).")
    sys.exit(0)

SRC = "web/src/data/incidents.ts"
with open(SRC, encoding="utf-8") as fh:
    ts = fh.read()

# Strip the network half + its imports; the pure function is what we are asserting.
ts = ts.split("export async function loadCounter")[0]
ts = "\n".join(l for l in ts.splitlines() if not l.startswith("import "))
ts = ts.replace("export interface CounterState", "interface CounterState").replace("export function", "function")
# Erase the type annotations node cannot parse (a deliberately small, targeted transform).
import re
ts = re.sub(r": string\[\]\[\]", "", ts)
ts = re.sub(r": CounterState", "", ts)
ts = re.sub(r": Date = new Date\(\)", " = new Date()", ts)
ts = re.sub(r": number \| null", "", ts)
ts = re.sub(r": string\[\]", "", ts)
ts = re.sub(r"\(s: string\)", "(s)", ts)
ts = re.sub(r"\(fromMs: number, nowMs: number\)", "(fromMs, nowMs)", ts)
ts = re.sub(r"\(c: string\)", "(c)", ts)
ts = re.sub(r"^interface CounterState \{[\s\S]*?\n\}\n", "", ts, flags=re.M)
ts = re.sub(r"^\s*/\*\*[\s\S]*?\*/\s*$", "", ts, flags=re.M)

CASES = """
const NOW = new Date("2026-07-27T12:00:00Z");
const out = [];
const t = (name, rows, want) => {
  const got = counterFromRows(rows, NOW);
  out.push({name, got, want});
};
// genesis only -> clean since genesis, no incidents
t("genesis only", [["2026-07-01T00:00:00Z","","_genesis","began","setup"]],
  {daysClean:26, monitoringDays:26, incidentsEver:0, open:0});
// a CLOSED incident resets the clock to its END
t("closed incident", [["2026-07-01T00:00:00Z","","_genesis","x","s"],
                      ["2026-07-20T00:00:00Z","2026-07-22T00:00:00Z","accuracy","bad","sentinel"]],
  {daysClean:5, monitoringDays:26, incidentsEver:1, open:0});
// an OPEN incident reads from its START and reports itself open
t("open incident", [["2026-07-01T00:00:00Z","","_genesis","x","s"],
                    ["2026-07-25T00:00:00Z","","accuracy","bad","sentinel"]],
  {daysClean:2, monitoringDays:26, incidentsEver:1, open:1});
// a DRILL must NOT break the streak
t("drill does not reset", [["2026-07-01T00:00:00Z","","_genesis","x","s"],
                           ["2026-07-26T00:00:00Z","2026-07-26T00:00:00Z","_drill","fire drill","cron"]],
  {daysClean:26, monitoringDays:26, incidentsEver:0, open:0});
// unseeded -> null, never a reassuring 0
t("unseeded is null", [], {daysClean:null, monitoringDays:null, incidentsEver:0, open:0});
// a short row WITH data is malformed, not silently dropped
t("short row counted", [["2026-07-01T00:00:00Z","","_genesis","x","s"], ["oops"]],
  {daysClean:26, monitoringDays:26, incidentsEver:0, open:0, malformed:1});
console.log(JSON.stringify(out));
"""

with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as fh:
    fh.write(ts + CASES)
    path = fh.name
try:
    res = subprocess.run(["node", path], capture_output=True, text=True, timeout=30)
finally:
    os.unlink(path)

if res.returncode != 0:
    print("❌ node failed:\n", res.stderr[:800])
    sys.exit(1)

FAIL = []
for c in json.loads(res.stdout):
    g, w = c["got"], c["want"]
    checks = [("daysClean", g["daysClean"], w["daysClean"]),
              ("monitoringDays", g["monitoringDays"], w["monitoringDays"]),
              ("incidentsEver", g["incidentsEver"], w["incidentsEver"]),
              ("open", len(g["openNow"]), w["open"])]
    if "malformed" in w:
        checks.append(("malformedRows", g["malformedRows"], w["malformed"]))
    ok = all(a == b for _n, a, b in checks)
    print(f"  {'✓' if ok else '✗'} {c['name']}")
    if not ok:
        for n, a, b in checks:
            if a != b:
                print(f"      {n}: got {a!r} want {b!r}")
        FAIL.append(c["name"])

print()
if FAIL:
    print(f"❌ {len(FAIL)} failure(s): {FAIL}")
    sys.exit(1)
print("✅ all counter-display goldens pass")
