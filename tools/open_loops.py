#!/usr/bin/env python3
"""Stranded-work detector — a plan page may not hide unfinished work from the to-do.

WHY THIS EXISTS (owner, 2026-07-10: "how did it end up we had like half scoped something like this
and just let it sit when we thought our to-dos had been cleared?").

The honest answer was structural, not human. `docs/state/current_status.md` is the to-do, and its
queue section was defined as **"NEXT (needs owner infra / a decision — then I execute)"**. So a
plain unfinished engineering residual — blocked on nobody, just not done — had NO HOME:

  · not NOW    (it isn't being worked on)
  · not NEXT   (nothing is blocked on the owner)
  · so it lived only inside a plan page in docs/ideas/, which nothing forces anyone to re-read

That is exactly what happened to the §9 relative-time residual: measured, scoped, written down —
and invisible to every subsequent "is the to-do clear?" check. The `status:` frontmatter field
could not have caught it either: 60 of 62 vault pages say `status: active`. A signal that never
varies is not a signal.

THE INVARIANT THIS ENFORCES
  1. A page declaring `open_loop:` in its frontmatter MUST be wikilinked from current_status.md.
     Unfinished work is therefore always reachable from the one page that answers "what's left?".
  2. A page marked `status: shipped` (or `archived`) MUST NOT declare an `open_loop:`.
     A finished plan cannot carry a residual — that contradiction is how a done-looking page hides
     an undone thing.

Neither rule asks anyone to remember anything, which is the point. Run standalone, or via
`tools/prepush_audit.py`, or in CI.

    python3 tools/open_loops.py           # report + enforce (exit 1 on violation)
    python3 tools/open_loops.py --list    # just print the open loops, exit 0
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
STATUS_PAGE = os.path.join(DOCS, "state", "current_status.md")

# A page whose work is done. `active` is the vault default and carries no information (see docstring),
# so only these two are treated as "closed" for rule 2.
CLOSED_STATUSES = {"shipped", "archived"}

# `[[folder/page]]`, `[[page]]`, `[[page|alias]]`, `[[page#anchor]]` — capture the target before | or #.
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")


def frontmatter(text):
    """The page's YAML-ish frontmatter as a flat dict. Deliberately not a YAML parser: the vault's
    frontmatter is one level deep, and taking a dependency to read six keys is not worth it."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out = {}
    for line in text[3:end].splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        k, _, v = line.partition(":")
        # Strip trailing `# comment` — the vault uses them on `status:` lines.
        out[k.strip()] = v.split("#", 1)[0].strip()
    return out


def page_names(rel_path):
    """Every wikilink form that legitimately targets this page: 'folder/page' and bare 'page'."""
    stem = rel_path[:-3] if rel_path.endswith(".md") else rel_path
    return {stem, os.path.basename(stem)}


def main():
    list_only = "--list" in sys.argv

    if not os.path.isfile(STATUS_PAGE):
        print(f"open_loops: FAIL — the status page is missing: {STATUS_PAGE}")
        return 1
    with open(STATUS_PAGE, encoding="utf-8") as f:
        status_text = f.read()
    linked = {m.strip() for m in WIKILINK_RE.findall(status_text)}

    loops, violations = [], []
    for dirpath, _dirs, files in os.walk(DOCS):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, DOCS)
            with open(full, encoding="utf-8") as f:
                fm = frontmatter(f.read())
            loop = fm.get("open_loop", "")
            if not loop:
                continue
            status = fm.get("status", "").lower()
            loops.append((rel, loop, status))

            if status in CLOSED_STATUSES:
                violations.append(
                    f"{rel}: status '{status}' but still declares open_loop — a finished page "
                    f"cannot carry a residual. Close the loop or reopen the page.")
            elif not (page_names(rel) & linked):
                violations.append(
                    f"{rel}: declares an open_loop but current_status.md never links it — the work "
                    f"is invisible to 'what's left?'. Add [[{rel[:-3]}]] to NOW/NEXT/READY.")

    print(f"open_loops: {len(loops)} declared across {DOCS.replace(ROOT + os.sep, '')}/")
    for rel, loop, status in loops:
        mark = " " if (page_names(rel) & linked) else "!"
        print(f"  {mark} {rel}  [{status or 'no-status'}]\n      {loop}")

    if list_only:
        return 0
    if violations:
        print("\nopen_loops: FAIL — unfinished work is not reachable from the to-do:")
        for v in violations:
            print(f"  ✗ {v}")
        return 1
    print("\nopen_loops: OK — every declared open loop is linked from current_status.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
