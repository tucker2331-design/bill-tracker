#!/usr/bin/env python3
"""Machine-executable half of the 15-point pre-push audit (Fable B-3).

Prose rules fire only when the model THINKS to apply them — PR #189 (Fable's own) shipped an
output-affecting change with no WORKER_OUTPUT_LOGIC_VERSION bump; a bot caught it a PR later
(assumptions_audit #96). This script mechanically enforces the checkable subset against a diff, so the
miss fails CI without any bot. Stdlib-only EXCEPT the pyflakes undefined-name gate (audit #104), which
is required only when the diff touches .py files (structural_tests.yml installs it).

Usage:
  python3 tools/prepush_audit.py                       # diff origin/main...HEAD (the PR)
  python3 tools/prepush_audit.py --base origin/main    # explicit base
  python3 tools/prepush_audit.py --cached              # staged changes (pre-commit)
  python3 tools/prepush_audit.py --range A..B          # an arbitrary range (used by the self-test)

Exit non-zero if any hard check FAILs. WARN/reminder lines never fail the build — they print the
judgment-only points (the human still owns those). See CLAUDE.md "Pre-Push Audit (15 points)".
"""
import argparse
import os
import subprocess
import sys

# --- check 1: output-VALUE-affecting functions require a WORKER_OUTPUT_LOGIC_VERSION bump (audit #96) -----
# The curated set of functions/identifiers that compute Sheet1 CELL VALUES (not gating/alerting/archiving).
# A diff whose calendar_worker.py / structural_router.py hunks touch any of these MUST also change
# WORKER_OUTPUT_LOGIC_VERSION — otherwise the incremental-STM / Stage-2 cache serves pre-change rows because
# the inputs are byte-identical. Deliberately EXCLUDES gating/cadence/archive/auth (they don't change output
# values), so cadence/session-follow/rollover PRs are NOT flagged. Keep this list current when a new
# output-producing function is added (that addition is itself an output-affecting change → bump anyway).
OUTPUT_VALUE_ANCHORS = (
    "_append_event", "run_sequential_turing_machine", "_STM_EVENT_KEY_FIELDS",
    "build_time_graph", "_resolve_one_day", "parse_24h_time", "_committee_parent",
    "_build_standing_schedule_maps", "_derive_standing_committee_time", "_parse_relative_offset_minutes",
    "_is_relative_time_text", "_plausible_meeting_time", "find_api_schedule_match",
    "_resolve_via_legislation_event_api", "resolve_committee_from_refid",
    "classify_action", "route_event", "_route_for_row",
)
OUTPUT_FILES = ("calendar_worker.py", "structural_router.py")
VERSION_TOKEN = "WORKER_OUTPUT_LOGIC_VERSION"

# --- check 4: forbidden silent-fallback / source-miss patterns in worker files (audit points 6/9) ---------
# An ADDED line containing one of these, in a worker file, without an adjacent `# audited:` tag, FAILs.
FORBIDDEN_ADDED = (
    ("except: pass", "bare except: pass — categorize + route, never swallow (Standard #4)"),
    ("except:pass", "bare except:pass — categorize + route, never swallow (Standard #4)"),
    ('"Time TBA"', '"Time TBA" literal — must carry a visible tag/counter (source-miss visibility)'),
    ('"Journal Entry"', '"Journal Entry" literal — must carry a visible tag/counter (source-miss visibility)'),
    ('"Ledger Updates"', '"Ledger Updates" literal — must carry a visible tag/counter'),
)
WORKER_FILES = ("calendar_worker.py", "bill_tracker.py", "backend_worker.py", "structural_router.py")
AUDIT_TAG = "# audited:"

# The diff-identical backup pair (audit point 4).
RAY2 = "pages/ray2.py"
XRAY_BACKUP = "calendar_xray.py"


def _run(args):
    return subprocess.run(args, capture_output=True, text=True).stdout


def _get_diff(ns):
    if ns.range:
        return _run(["git", "diff", ns.range])
    if ns.cached:
        return _run(["git", "diff", "--cached"])
    return _run(["git", "diff", f"{ns.base}...HEAD"])


class FileDiff:
    __slots__ = ("path", "hunks", "added", "removed")

    def __init__(self, path):
        self.path = path
        self.hunks = []    # (context_text, [added_lines_in_hunk])
        self.added = []    # all added lines (without the leading '+')
        self.removed = []


def _parse(diff_text):
    files, cur, cur_hunk_added = {}, None, None
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            # "diff --git a/PATH b/PATH" — take the b/ path
            parts = line.split(" b/")
            path = parts[-1].strip() if len(parts) > 1 else line.split()[-1]
            cur = files.setdefault(path, FileDiff(path))
            cur_hunk_added = None
        elif line.startswith("@@") and cur is not None:
            ctx = line.split("@@")[-1].strip()   # the trailing "def foo(...)" context git includes
            cur_hunk_added = []
            cur.hunks.append((ctx, cur_hunk_added))
        elif cur is not None and line.startswith("+") and not line.startswith("+++"):
            body = line[1:]
            cur.added.append(body)
            if cur_hunk_added is not None:
                cur_hunk_added.append(body)
        elif cur is not None and line.startswith("-") and not line.startswith("---"):
            cur.removed.append(line[1:])
    return files


def _basename(path):
    return path.rsplit("/", 1)[-1]


def check_version_bump(files, fails):
    touched = []
    version_bumped = any(VERSION_TOKEN in ln for fd in files.values() for ln in fd.added)
    for fd in files.values():
        if _basename(fd.path) not in OUTPUT_FILES:
            continue
        for ctx, added in fd.hunks:
            blob = ctx + "\n" + "\n".join(added)
            hit = [a for a in OUTPUT_VALUE_ANCHORS if a in blob]
            if hit:
                touched.append((fd.path, sorted(set(hit))))
    if touched and not version_bumped:
        detail = "; ".join(f"{p} → {', '.join(a)}" for p, a in touched)
        fails.append(f"[1] output-VALUE-affecting change with NO {VERSION_TOKEN} bump (audit #96): {detail}")
    return bool(touched), version_bumped


def check_ray2_backup(files, fails):
    if any(_basename(fd.path) == RAY2 or fd.path == RAY2 for fd in files.values()):
        # compare the two files in the working tree; they MUST be diff-identical (audit point 4)
        out = subprocess.run(["git", "diff", "--no-index", "--", RAY2, XRAY_BACKUP],
                             capture_output=True, text=True)
        if out.returncode != 0 and out.stdout.strip():
            fails.append(f"[4] {RAY2} changed but {XRAY_BACKUP} (its diff-identical backup) DIFFERS — "
                         f"mirror the change into {XRAY_BACKUP}.")


def check_forbidden(files, fails):
    for fd in files.values():
        if _basename(fd.path) not in WORKER_FILES:
            continue
        for ctx, added in fd.hunks:
            for ln in added:
                if AUDIT_TAG in ln:
                    continue
                low = ln.replace(" ", "")
                for needle, why in FORBIDDEN_ADDED:
                    if needle.replace(" ", "") in low:
                        fails.append(f"[6/9] {fd.path}: added `{ln.strip()[:70]}` — {why}. "
                                     f"Tag the line `{AUDIT_TAG} <reason>` if intentional.")


def warns(files):
    out = []
    # check 5: a changed regex/pattern list → verb-forms reminder (judgment; only remind)
    for fd in files.values():
        for ln in fd.added + fd.removed:
            if "_RE" in ln and "re.compile" in ln:
                out.append(f"[5] {fd.path}: a `_RE` pattern changed — re-verify ALL verb conjugations "
                           f"(base/past/present/plural) for every keyword (audit point 1).")
                break
    # check 2: a new dict key near _append_event / master_events (fuzzy → remind, don't fail)
    for fd in files.values():
        if _basename(fd.path) in OUTPUT_FILES:
            for ctx, added in fd.hunks:
                if "_append_event" in ctx or "master_events" in ctx:
                    if any(":" in a and ("'" in a or '"' in a) for a in added):
                        out.append(f"[2] {fd.path}: a row/event dict near _append_event changed — if a NEW "
                                   f"output column/key was added, add it to _STM_EVENT_KEY_FIELDS + the "
                                   f"architecture schema table (audit #96).")
                        break
    return out


JUDGMENT_CHECKLIST = """\
Judgment-only points (the script can't check these — confirm each):
  #2  Function scope: new functions defined BEFORE all call sites (not inside a conditional/try/loop).
  #5  Architecture conformance: matches docs/architecture/calendar_pipeline.md (update the doc if flow changed).
  #7  Cross-list validation: no accidental overlap between NOISE/EVENT/MEETING/ADMIN/FLOOR lists.
 #11  Side-effect gating: a state-carrying side effect needed to RECOVER must not sit inside a gate that
      can stay permanently true — hoist it out (audit #51).
 #14  Threshold calibration: any absolute breaker threshold still correct against the new steady-state?
 #15  Sentinel collision: is a default-on-failure value ever a legitimate runtime value? Track presence
      as a separate flag if so (audit #53/#15)."""


def check_undefined_names(files, fails):
    """Point 17 (audit #104) — pyflakes 'undefined name' gate on changed worker .py files.

    An UnboundLocalError (a name referenced before its later assignment in the same function) is
    invisible to py_compile and to golden tests that never execute the enclosing loop — it shipped
    THREE times as the meeting_unsourced 0→66 regression, wearing an 'LIS API failed' costume from a
    broad except. `python3 -m pyflakes` flags it statically as `undefined name 'X'`. Only that message
    class fails (unused-import / f-string chatter stays advisory noise we ignore); only .py files in
    the diff are scanned, so doc-only pushes never need pyflakes installed. Fail-closed: if a worker
    .py changed and pyflakes is missing, the audit FAILS with the install command — a gate that can be
    absent silently is not a gate."""
    changed_py = [fd.path for fd in files.values()
                  if fd.path.endswith(".py") and os.path.isfile(fd.path)]
    if not changed_py:
        return
    try:
        import pyflakes  # noqa: F401 — presence check only; we shell out for clean per-file output
    except ImportError:
        fails.append("[17] pyflakes is not installed but the diff touches .py files — the undefined-name "
                     "gate (audit #104) cannot run. Install it: python3 -m pip install pyflakes")
        return
    r = subprocess.run([sys.executable, "-m", "pyflakes", *changed_py],
                       capture_output=True, text=True)
    hits = [ln for ln in r.stdout.splitlines()
            if "undefined name" in ln or "referenced before assignment" in ln]
    for h in hits:
        fails.append(f"[17] pyflakes: {h} — a runtime NameError/UnboundLocalError waiting in a code "
                     f"path py_compile can't see (audit #104).")


def check_open_loops(fails):
    """Point 16 — unfinished work must be reachable from the to-do (tools/open_loops.py).

    Runs on EVERY push, not only when docs change: the failure mode is a residual that quietly stops
    being linked, and a diff-scoped check would never see the page that dropped the link. Delegates to
    open_loops.py so the invariant has exactly one implementation."""
    tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "open_loops.py")
    if not os.path.isfile(tool):
        fails.append("tools/open_loops.py is missing — the stranded-work invariant is unenforced.")
        return
    try:
        r = subprocess.run([sys.executable, tool], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        # A filesystem stall shouldn't hang the whole CI job — fail fast with a clear reason (CodeRabbit).
        fails.append("open_loops: tools/open_loops.py did not finish within 30s (filesystem stall?).")
        return
    if r.returncode != 0:
        detail = "\n      ".join(line for line in r.stdout.splitlines() if line.strip().startswith("✗"))
        fails.append("open_loops: a page declares unfinished work that current_status.md never links.\n"
                     f"      {detail or r.stdout.strip() or r.stderr.strip()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--cached", action="store_true")
    ap.add_argument("--range", default=None)
    ns = ap.parse_args()

    diff = _get_diff(ns)
    if not diff.strip():
        print("prepush_audit: empty diff — nothing to check.")
        return 0
    files = _parse(diff)

    fails = []
    output_change, bumped = check_version_bump(files, fails)
    check_ray2_backup(files, fails)
    check_forbidden(files, fails)
    check_undefined_names(files, fails)
    check_open_loops(fails)
    warn_lines = warns(files)

    print(f"prepush_audit: {len(files)} file(s) in diff; "
          f"output-value change={'yes' if output_change else 'no'}, {VERSION_TOKEN} bumped={'yes' if bumped else 'no'}.")
    for w in warn_lines:
        print("  ⚠️  WARN " + w)
    print(JUDGMENT_CHECKLIST)

    if fails:
        print("\n❌ pre-push audit FAILED:")
        for f in fails:
            print("  • " + f)
        return 1
    print("\n✅ pre-push audit: mechanical checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
