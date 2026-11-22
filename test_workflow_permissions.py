#!/usr/bin/env python3
"""tools/workflow_permissions.py: every workflow declares its token rights (pre-push audit point 19)."""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from workflow_permissions import job_permissions, problems  # noqa: E402

TOOL = os.path.join(ROOT, "tools", "workflow_permissions.py")
fails = 0


def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


TOP = """name: x
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""
NONE = TOP.replace("permissions:\n  contents: read\n", "")
EMPTY = TOP.replace("permissions:\n  contents: read\n", "permissions: {}\n")
PER_JOB = """on: push
jobs:
  a:
    permissions:
      contents: read
    runs-on: ubuntu-latest
    steps:
      - run: echo a
  b:
    runs-on: ubuntu-latest
    permissions: {}
    steps:
      - run: echo b
"""
ONE_JOB_BARE = PER_JOB.replace("    permissions: {}\n", "")
# A step's `with:` holding a key named permissions is not the job's permissions.
NESTED = """on: push
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - uses: some/action@v1
        with:
          permissions: read
"""
WRITE_ALL = TOP.replace("permissions:\n  contents: read\n", "permissions: write-all\n")
JOB_WRITE_ALL = PER_JOB.replace("    permissions: {}\n", "    permissions: 'write-all'  # lazy\n")
COMMENTED = TOP.replace("permissions:\n  contents: read\n", "# permissions:\n#   contents: read\n")
FOUR_SPACE = """on: push
jobs:
    a:
        permissions:
            contents: read
        runs-on: ubuntu-latest
"""

check("top-level block passes", problems(TOP) == [])
check("`permissions: {}` (no rights at all) passes", problems(EMPTY) == [])
check("no block anywhere fails", problems(NONE) != [] and "a" in problems(NONE)[0])
check("every job declaring its own passes", problems(PER_JOB) == [])
check("per-job: the job without one is named", problems(ONE_JOB_BARE) == [
    "no top-level `permissions:` and these jobs declare none: b"])
check("a step input named permissions does not count", problems(NESTED) != [])
check("top-level write-all fails", any("write-all" in p for p in problems(WRITE_ALL)))
check("job-level quoted write-all fails", any("write-all" in p for p in problems(JOB_WRITE_ALL)))
check("a commented-out block does not count", problems(COMMENTED) != [])
check("4-space indentation is read", job_permissions(FOUR_SPACE) == {"a": True})
check("a file with no jobs key fails (not a workflow)", problems("import requests\nprint(1)\n") != [])
check("jobs parsed by name", job_permissions(PER_JOB) == {"a": True, "b": True})

with tempfile.TemporaryDirectory() as d:
    run = lambda: subprocess.run([sys.executable, TOOL, d], capture_output=True, text=True)
    r = run()
    check("an empty directory is an error (wrong path), not a pass", r.returncode == 2)
    open(os.path.join(d, "ok.yml"), "w").write(TOP)
    check("a directory of declared workflows passes", run().returncode == 0)
    open(os.path.join(d, "bad.yaml"), "w").write(NONE)
    r = run()
    check("one undeclared .yaml file fails the run", r.returncode == 1 and "bad.yaml" in r.stdout)
    check("the summary counts k of n", "1 of 2 workflow files" in r.stdout)

r = subprocess.run([sys.executable, TOOL], capture_output=True, text=True)
check("this repo's workflows all declare their token rights", r.returncode == 0)

sys.exit(1 if fails else 0)
