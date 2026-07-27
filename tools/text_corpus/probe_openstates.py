#!/usr/bin/env python3
"""Minimal live probe: does the OPENSTATES_API_KEY work, and what shape is the payload? (W6)

Runs in CI, where the secret lives — the key is never read on a developer machine and never printed. Spends
at most a HANDFUL of requests against a 400/day self-imposed budget, and prints what it spent.

It answers the two questions the corpus design hangs on, by MEASURING rather than assuming:
  1. does the key authenticate at all?
  2. does a bill payload carry version/text links (`versions`), i.e. is the API a viable *targeted* text
     lookup — or is bulk genuinely the only path for text?

Read-only. Never writes a sheet, never mutates anything.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openstates import ATTRIBUTION, KEY_ENV, OpenStates, OpenStatesError, redact  # noqa: E402
from budget import BudgetExceeded  # noqa: E402


def main():
    client = OpenStates()
    print(f"probe_openstates — key present: {client.has_key}")
    if not client.has_key:
        print(f"❌ {KEY_ENV} not in the environment. In CI, pass it via `env:` from the repository secret.")
        return 1

    findings = {}
    try:
        # A single, deliberately boring lookup: one known VA bill from the session we already work with.
        # (Jurisdiction/session naming is Open States' own, which is part of what we're measuring.)
        data = client.bill("Virginia", "2026", "HB 176")
        findings["authenticated"] = True
        findings["top_level_keys"] = sorted(data.keys())[:20]
        versions = data.get("versions") or []
        findings["versions_present"] = bool(versions)
        findings["version_count"] = len(versions)
        if versions:
            v0 = versions[0]
            findings["version_keys"] = sorted(v0.keys())
            links = v0.get("links") or []
            findings["version_link_count"] = len(links)
            # The decisive question: are texts INLINE, or only linked documents we'd have to fetch?
            findings["text_is_inline"] = any(
                isinstance(val, str) and len(val) > 2000 for val in v0.values())
            findings["link_media_types"] = sorted({(l.get("media_type") or "?") for l in links})[:6]
        findings["identifier"] = data.get("identifier")
        findings["title_present"] = bool(data.get("title"))
    except OpenStatesError as e:
        print(f"❌ API error: {redact(str(e))}")
        findings["authenticated"] = False
        findings["error"] = redact(str(e))
    except BudgetExceeded as e:
        print(f"⛔ budget: {e}")
        return 1

    print(json.dumps(findings, indent=2))
    print(f"\nbudget after probe: {client.budget_snapshot()}")
    print(f"attribution string we will render: {ATTRIBUTION!r}")

    if not findings.get("authenticated"):
        return 1
    print("\n✅ key authenticates; payload shape recorded above.")
    print("   NOTE: corpus work still uses BULK downloads — 500 req/day cannot carry a text corpus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
