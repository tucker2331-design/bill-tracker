#!/usr/bin/env python3
"""Every GitHub workflow must say what its token may do (pre-push audit point 19).

WHY (2026-11-22, docs/ideas/going_private.md §C "workflow token permissions"): 25 of 38 workflows set no
`permissions:` block, so each inherited the repository's default token rights. The going-private checklist asks the
owner to set that default to Read. A job that silently relied on the old default would then break on the next run
with nothing in the diff to explain it. Declaring the rights in each file makes the default irrelevant: the file
says what the job may do, and changing the setting cannot change any job.

Rules (line-based, no YAML library: CI's structural job installs nothing):
  1. a top-level `permissions:` key (column 0), OR, when there is none, a `permissions:` key in EVERY job;
  2. never `write-all` (every scope writable): name the scopes the job needs.

Usage: python3 tools/workflow_permissions.py [workflows_dir]    exit 0 = every file declares; 1 = a problem.
"""
import os
import re
import sys

_TOP = re.compile(r"^permissions\s*:")
_WRITE_ALL = re.compile(r"^\s*permissions\s*:\s*['\"]?write-all['\"]?\s*(#.*)?$")


def _meaningful(line):
    s = line.strip()
    return s and not s.startswith("#")


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def job_permissions(text):
    """{job_name: has its own permissions key} for the jobs under the top-level `jobs:` key."""
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if re.match(r"^jobs\s*:", ln))
    except StopIteration:
        return {}
    jobs, current, job_indent, child_indent = {}, None, None, None
    for ln in lines[start + 1:]:
        if not _meaningful(ln):
            continue
        ind = _indent(ln)
        if ind == 0:                       # the next top-level key ends the jobs block
            break
        if job_indent is None:
            job_indent = ind
        if ind == job_indent:
            current = ln.strip().split(":", 1)[0].strip("'\"")
            jobs[current] = False
            child_indent = None
        elif current is not None and ind > job_indent:
            if child_indent is None:
                child_indent = ind
            if ind == child_indent and re.match(r"permissions\s*:", ln.strip()):
                jobs[current] = True
    return jobs


def problems(text):
    """Why one workflow file fails the rule ([] = it passes)."""
    out = []
    lines = text.splitlines()
    if not any(_TOP.match(ln) for ln in lines):
        jobs = job_permissions(text)
        bare = [j for j, has in jobs.items() if not has]
        if not jobs:
            out.append("no top-level `permissions:` and no jobs found")
        elif bare:
            out.append("no top-level `permissions:` and these jobs declare none: " + ", ".join(bare))
    for i, ln in enumerate(lines, 1):
        if _WRITE_ALL.match(ln):
            out.append(f"line {i}: `write-all` grants every scope; name the scopes the job needs")
    return out


def scan(directory):
    """[(file, problem)] for every workflow file in `directory`; raises OSError if it cannot be read."""
    found = []
    names = sorted(n for n in os.listdir(directory) if n.endswith((".yml", ".yaml")))
    for name in names:
        with open(os.path.join(directory, name), encoding="utf-8") as fh:
            for p in problems(fh.read()):
                found.append((name, p))
    return found, len(names)


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    directory = argv[1] if len(argv) > 1 else os.path.join(root, ".github", "workflows")
    try:
        found, n = scan(directory)
    except OSError as e:
        print(f"workflow_permissions: cannot read {directory}: {e}")
        return 2
    if n == 0:
        print(f"workflow_permissions: no workflow files in {directory} (wrong path?)")
        return 2
    for name, p in found:
        print(f"  ✗ {name}: {p}")
    bad = len({name for name, _ in found})
    print(f"workflow_permissions: {n - bad} of {n} workflow files declare their token rights.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
