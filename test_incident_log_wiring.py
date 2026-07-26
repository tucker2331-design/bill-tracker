#!/usr/bin/env python3
"""Guard→ledger WIRING goldens — proves the days-clean ledger is reachable FROM THE GUARDS AS CI RUNS THEM.

WHY THIS FILE EXISTS (a bug caught in review of W1, before merge)
The three guards call the ledger through fail-open helpers — correct, because a bookkeeping problem must never
flip an accuracy verdict. But fail-open has a failure mode of its own: if the ledger can't even be IMPORTED,
every call is swallowed with a warning and the ledger silently records nothing, forever, while the guards keep
reporting success. That is exactly what a bare `from tools.incident_log.log import …` does here: the workflows
invoke `python3 tools/verification/accuracy_sentinel.py`, so `sys.path[0]` is `tools/verification` — the repo
root is NOT on the path and the import raises ModuleNotFoundError.

So these tests do NOT import the guards as modules (which would put the repo root on sys.path and hide the
bug). They spawn each guard THE WAY THE WORKFLOW DOES — as a script, from the repo root — and assert the
ledger API resolves inside that process.

    python3 test_incident_log_wiring.py
"""
import os
import subprocess
import sys
import textwrap

ROOT = os.path.dirname(os.path.abspath(__file__))
FAILURES = []
_checks = 0

# (guard path, the detector name it must register under)
GUARDS = [
    ("tools/verification/accuracy_sentinel.py", "accuracy_sentinel"),
    ("tools/verification/completeness_tripwire.py", "completeness_tripwire"),
    ("tools/reconciliation/reconcile_votes.py", "reconcile_votes"),
]


def ok(cond, label):
    global _checks
    _checks += 1
    print(f"  {'✓' if cond else '✗'} {label}")
    if not cond:
        FAILURES.append(label)


def run_in_guard_context(guard_path, snippet):
    """Execute `snippet` in a process whose sys.path[0] is the GUARD's directory — i.e. exactly the import
    context the workflow gives it. A temp file inside that directory is the only faithful way to reproduce it.
    """
    d = os.path.join(ROOT, os.path.dirname(guard_path))
    probe = os.path.join(d, "_wiring_probe.py")
    with open(probe, "w", encoding="utf-8") as fh:
        fh.write(snippet)
    try:
        return subprocess.run([sys.executable, os.path.join(os.path.dirname(guard_path), "_wiring_probe.py")],
                              cwd=ROOT, capture_output=True, text=True, timeout=60)
    finally:
        os.remove(probe)


print("— the naive import really is broken (so the fix is load-bearing, not decoration) —")
naive = run_in_guard_context(GUARDS[0][0], textwrap.dedent('''
    try:
        from tools.incident_log.log import record_incident        # noqa: F401
        print("RESOLVED")
    except ModuleNotFoundError:
        print("MODULE_NOT_FOUND")
'''))
ok("MODULE_NOT_FOUND" in naive.stdout,
   "a bare `from tools.…` import fails in the guards' real invocation context "
   f"(got: {naive.stdout.strip() or naive.stderr.strip()[:80]})")

print("\n— every guard's `_ledger_api()` resolves in that same context —")
for path, det in GUARDS:
    mod = os.path.splitext(os.path.basename(path))[0]
    res = run_in_guard_context(path, textwrap.dedent(f'''
        import importlib
        g = importlib.import_module("{mod}")          # sibling import: the guard's own dir is sys.path[0]
        rec, close = g._ledger_api()
        assert callable(rec) and callable(close), "ledger API is not callable"
        print("RESOLVED", g._LEDGER_DETECTOR)
    '''))
    ok("RESOLVED" in res.stdout,
       f"{mod}: _ledger_api() imports the ledger as a script would "
       f"({(res.stdout or res.stderr).strip()[:90]})")
    ok(f"RESOLVED {det}" in res.stdout,
       f"{mod}: registers under its own detector name '{det}' (dedup is per-detector)")

print("\n— the ledger call itself is FAIL-OPEN (a broken ledger must not change a verdict) —")
res = run_in_guard_context(GUARDS[0][0], textwrap.dedent('''
    import importlib
    g = importlib.import_module("accuracy_sentinel")
    g._ledger_api = lambda: (_ for _ in ()).throw(RuntimeError("ledger down"))
    g._ledger("accuracy", "x")      # must NOT raise
    g._ledger_close("accuracy")     # must NOT raise
    print("SURVIVED")
'''))
ok("SURVIVED" in res.stdout,
   f"a totally broken ledger is swallowed, not propagated ({(res.stdout or res.stderr).strip()[:90]})")
ok("non-fatal" in res.stdout, "…and it says so out loud rather than failing silently")

print()
if FAILURES:
    print(f"❌ {len(FAILURES)} failure(s):")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print(f"ALL {_checks} guard→ledger wiring tests passed")
