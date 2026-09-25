#!/usr/bin/env python3
"""Introduced bill TEXT for 2025/2026 from LIS's keyless blob -- the owner-approved fetch (2026-09-25).

SCOPE: only sessions 2025 and 2026 (inside the LIS authorization window). Pre-2025 version links point to the
old `lis.virginia.gov/cgi-bin/legp604.exe` system and are NOT fetched. Only HB/SB INTRODUCED versions (what is
knowable before a bill's first vote). Only the host lis.blob.core.windows.net -- anything else is refused.

GUARDRAILS (docs/knowledge/lis_api_safety.md, applied to a one-off backfill):
  #1 never re-download: a file on disk is never requested again
  #2 jitter: 1.2-2.4 s random spacing, never a metronome
  #3 a 429/503 or 5 consecutive errors STOPS the run (resume later picks up where it left off)
  #4 hard cap per run (BLOB_TEXT_CAP, default 6000)
Honest User-Agent. Read-only.
"""
from __future__ import annotations
import os, sys, io, csv, time, random, zipfile, json, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ZIPS = os.path.join(ROOT, "tools", "historical_cache", "openstates_va")
OUT = os.path.join(ROOT, ".va_text_corpus", "blob")
HOST = "lis.blob.core.windows.net"
CAP = int(os.environ.get("BLOB_TEXT_CAP", "6000"))
UA = "va-bill-tracker/1.0 (research backfill; paced; contact via repository owner)"


def targets():
    out = []
    for s in ("2025", "2026"):
        z = zipfile.ZipFile(os.path.join(ZIPS, f"VA_{s}.zip"))
        n = z.namelist()
        rd = lambda suf: csv.DictReader(io.TextIOWrapper(z.open([x for x in n if x.endswith(suf)][0]), "utf-8"))
        ident = {r["id"]: r["identifier"] for r in rd("_bills.csv")}
        vers = {r["id"]: (r["bill_id"], r["note"]) for r in rd("_bill_versions.csv")}
        seen = set()
        for r in rd("_bill_version_links.csv"):
            bid, note = vers.get(r["version_id"], ("", ""))
            b = ident.get(bid, "")
            if b[:3] not in ("HB ", "SB ") or "introduc" not in note.lower() or "html" not in r["media_type"]:
                continue
            if b in seen:
                continue
            seen.add(b)
            out.append((s, b, r["url"]))
    return out


def main():
    ts = targets()
    todo = [(s, b, u) for s, b, u in ts
            if not os.path.exists(os.path.join(OUT, s, b.replace(" ", "") + ".html"))]
    print(f"{len(ts)} introduced HB/SB texts; {len(ts)-len(todo)} already cached; {len(todo)} to fetch (cap {CAP})",
          flush=True)
    errs = spent = 0
    for s, b, u in todo:
        if spent >= CAP:
            print("hard cap reached -- stopping (guardrail #4)", flush=True); break
        if urllib.parse.urlparse(u).hostname != HOST:
            print(f"refused non-blob host: {u}", flush=True); continue
        time.sleep(random.uniform(1.2, 2.4))
        spent += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60) as r:
                body = r.read()
            os.makedirs(os.path.join(OUT, s), exist_ok=True)
            open(os.path.join(OUT, s, b.replace(" ", "") + ".html"), "wb").write(body)
            errs = 0
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                print(f"{e.code} from LIS -- STOPPING (guardrail #3). Resume later.", flush=True); return 2
            errs += 1; print(f"HTTP {e.code} {s} {b}", flush=True)
        except Exception as e:
            errs += 1; print(f"error {s} {b}: {type(e).__name__}", flush=True)
        if errs >= 5:
            print("5 consecutive errors -- STOPPING (guardrail #3)", flush=True); return 3
        if spent % 200 == 0:
            print(f"  {spent} fetched", flush=True)
    print(f"done: {spent} requests this run", flush=True)
    return 0


if __name__ == "__main__":
    import urllib.parse
    sys.exit(main())
