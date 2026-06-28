#!/usr/bin/env python3
"""Producer/validator drift guard for the calendar worker's Origin enum.

WHY THIS EXISTS (PR #176): a FALSE ``invariant_violations=1`` fired on EVERY worker cycle
because the ``derived_standing`` Origin was PRODUCED in production (one real SJ209 row) but
was never registered in ``_VALID_ORIGINS`` — so the write-time I2 invariant flagged that
lone row forever. It was a silent producer/validator drift: a code path emitted an Origin
the validator didn't know about. The owner's question was "how do we prevent these false
alarms in the future?" — this test is the answer. It makes that class of drift impossible
to merge: every Origin the worker USES must be registered, and every registered Origin must
have a real use (no dead registrations hiding a typo).

HOW: ``_VALID_ORIGINS`` is a *function-local* set inside the worker (not importable), so we
read it the only deterministic way available — parse ``calendar_worker.py`` with ``ast``.
No execution, no Google/LIS credentials, no network: a pure static check safe for CI.

We collect the origins the source USES from three structural sites (every current Origin
flows through at least one, because the worker must branch on Origin to route a row):
  (a) ``origin = "literal"``            — the producer variable assignment
  (b) ``{"Origin": "literal"}``         — a direct event-dict literal
  (c) ``origin == "x"`` / ``origin in (...)`` / ``event.get("Origin") in (...)`` — dispatch
Then assert used ⊆ registered (no unregistered producer → the #176 bug) AND
registered ⊆ used ∪ REGISTRATION_ONLY (no dead/typo'd registration).

Run: ``python3 test_origin_registry_sync.py``   (exit 0 = in sync).
"""
from __future__ import annotations  # PEP 604 `str | None` annotations on Python 3.9 (lazy strings)

import ast
import pathlib
import sys

WORKER = pathlib.Path(__file__).resolve().parent / "calendar_worker.py"

# Origins that are intentionally REGISTERED before their producer ships (a later PR adds the
# emitter). List each here WITH the reason, and remove it once the producer lands. Keeping
# this explicit means a registered-but-never-produced Origin can't silently hide a typo —
# it must be a deliberate, documented forward-registration.
REGISTRATION_ONLY: dict[str, str] = {
    # "scheduled_future": "PR-FC1b producer not merged yet",
}


def _str_const(node: ast.AST) -> str | None:
    """The string value of a constant node, else None."""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def collect(tree: ast.AST) -> tuple[set[str], dict[str, int]]:
    """Return (registered origins from _VALID_ORIGINS, {used origin: first lineno})."""
    registered: set[str] = set()
    used: dict[str, int] = {}

    def mark(origin: str | None, lineno: int) -> None:
        # Skip empties/whitespace (e.g. the "" default in event.get("Origin", "")) and the
        # field name "Origin" itself — neither is an Origin VALUE.
        if origin and origin.strip() and origin != "Origin" and origin not in used:
            used[origin] = lineno

    for node in ast.walk(tree):
        # The registry: _VALID_ORIGINS = { "...", ... }
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Set):
            if any(isinstance(t, ast.Name) and t.id == "_VALID_ORIGINS" for t in node.targets):
                for elt in node.value.elts:
                    s = _str_const(elt)
                    if s:
                        registered.add(s)

        # (a) origin = "literal"  (plain Name target, not a tuple-unpack of a call result)
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "origin" for t in node.targets):
                mark(_str_const(node.value), node.lineno)

        # (b) {"Origin": "literal"}  — a direct event-dict literal
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if _str_const(k) == "Origin":
                    mark(_str_const(v), getattr(v, "lineno", node.lineno))

        # (c) any comparison that references the `origin` variable OR the "Origin" field —
        #     collect every string constant inside it (covers `==` and `in (set/tuple/list)`).
        if isinstance(node, ast.Compare):
            sub = list(ast.walk(node))
            refs_origin = any(isinstance(n, ast.Name) and n.id == "origin" for n in sub)
            refs_field = any(_str_const(n) == "Origin" for n in sub)
            if refs_origin or refs_field:
                for n in sub:
                    mark(_str_const(n), node.lineno)

    return registered, used


def main() -> int:
    tree = ast.parse(WORKER.read_text(encoding="utf-8"))
    registered, used = collect(tree)
    used_set = set(used)

    # Sanity: a parsing breakage that finds nothing must FAIL loudly, never pass vacuously.
    if len(registered) < 8:
        print(f"*** PARSE GUARD: only {len(registered)} registered origins found — "
              f"_VALID_ORIGINS moved or the parser broke. Refusing to pass vacuously.")
        return 1

    unregistered = sorted(used_set - registered)                       # the #176 bug class
    dead = sorted(registered - used_set - set(REGISTRATION_ONLY))      # registered but never used

    print(f"  registered origins (_VALID_ORIGINS): {len(registered)}")
    print(f"  origins used in source:              {len(used_set)}")
    if REGISTRATION_ONLY:
        print(f"  registration-only (allowlisted):     {sorted(REGISTRATION_ONLY)}")

    ok = True
    if unregistered:
        ok = False
        print("\n*** UNREGISTERED ORIGIN(S) — produced/used but missing from _VALID_ORIGINS:")
        for o in unregistered:
            print(f"      '{o}'  (first used at calendar_worker.py:{used[o]})")
        print("    -> add each to _VALID_ORIGINS, or the I2 write-time invariant will flag every"
              "\n       row carrying it (the persistent false invariant_violations the #176 fix killed).")
    if dead:
        ok = False
        print("\n*** DEAD REGISTRATION(S) — in _VALID_ORIGINS but never used as an Origin:")
        for o in dead:
            print(f"      '{o}'")
        print("    -> remove it, or (if a producer is coming in a later PR) add it to"
              "\n       REGISTRATION_ONLY with a reason.")

    if ok:
        print("\nOrigin registry is in sync: every produced Origin is registered, no dead registrations.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
