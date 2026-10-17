#!/usr/bin/env python3
"""Committee-meeting transcripts from the Internet Archive -- the legitimate route to what is said in committee.

Owner, 2026-10-14: "transcripts: whats the work around. get creative." The House (Sliq) and Senate (Granicus) video hosts
both disallow automated access in robots.txt, and YouTube's captions are owner-only. The Internet Archive holds a
"virginiageneralassembly" collection (1,083 items: committee, subcommittee and floor meetings, 2008-2026) and generates a
speech-to-text caption file for each video. archive.org's robots.txt disallows only /control/ and /report/; its
advancedsearch and metadata endpoints are its public, documented programmatic interface.

Only the CAPTION TEXT is fetched (~50 KB per meeting) -- never the video. Raw captions are cached outside git; the parsed,
per-bill segments are committed. Used for internal research; not redistributed.
LOAD: 2 requests per meeting, 2-4 s apart, identified user agent; resumable.

Run: python3 tools/historical_cache/ia_transcripts.py 2019 2026     (meetings dated in those years, inclusive)
"""
from __future__ import annotations
import json, os, random, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "va_transcripts", "raw")
# a fresh connection per request: pooled keep-alive connections went stale on a flaky network (2026-10-14)
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)", "Connection": "close"}
SEARCH = ("https://archive.org/advancedsearch.php?q=collection%3Avirginiageneralassembly&fl%5B%5D=identifier"
          "&fl%5B%5D=title&fl%5B%5D=date&rows=5000&output=json")


def get(s, url, tries=4):
    """GET with retries on dropped connections (counted in the log, never silent)."""
    import requests
    for attempt in range(tries):
        try:
            return s.get(url, headers=UA, timeout=60)
        except requests.RequestException as e:
            print(f"  {type(e).__name__} on {url[-60:]} (attempt {attempt + 1}), waiting", flush=True)
            time.sleep(20 * (attempt + 1))
    return None


def first(v):
    return (v[0] if isinstance(v, list) else v) or ""


def main(y0, y1):
    import requests
    s = requests.Session()
    os.makedirs(RAW, exist_ok=True)
    first_page = get(s, SEARCH)
    if first_page is None or first_page.status_code != 200:
        raise SystemExit("could not read the collection listing -- stopping (nothing guessed)")
    docs = first_page.json()["response"]["docs"]
    items = []
    for d in docs:
        m = re.search(r"-(\d{8})-", d["identifier"])
        date = first(d.get("date"))[:10] or (f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else "")
        if date and y0 <= int(date[:4]) <= y1:
            items.append((d["identifier"], date, first(d.get("title"))))
    index_path = os.path.join(RAW, "index.json")
    index = json.load(open(index_path)) if os.path.exists(index_path) else {}
    print(f"{len(items)} items dated {y0}-{y1}; {len(index)} already done", flush=True)
    missing = 0
    for n, (ident, date, title) in enumerate(sorted(items, key=lambda x: x[1])):
        if ident in index:
            continue
        time.sleep(2 + random.random() * 2)
        meta = get(s, f"https://archive.org/metadata/{ident}")
        if meta is None:
            missing += 1; continue                                  # unreachable: not recorded, retried next run
        if meta.status_code != 200:
            index[ident] = {"date": date, "title": title,
                            "status": f"metadata {'unreachable' if meta is None else 'HTTP %d' % meta.status_code}"}
            missing += 1
            continue
        files = meta.json().get("files", [])
        cap = next((f["name"] for f in files if f["name"].endswith(".vtt")), None) or \
              next((f["name"] for f in files if f["name"].endswith(".srt")), None)
        if not cap:
            index[ident] = {"date": date, "title": title, "status": "no caption file"}; missing += 1
            continue
        time.sleep(2 + random.random() * 2)
        r = get(s, f"https://archive.org/download/{ident}/{cap}")
        if r is None:
            missing += 1; continue                                  # unreachable: not recorded, retried next run
        if r.status_code != 200:
            index[ident] = {"date": date, "title": title,
                            "status": f"caption {'unreachable' if r is None else 'HTTP %d' % r.status_code}"}
            missing += 1
            continue
        open(os.path.join(RAW, f"{ident}.vtt"), "w").write(r.text)
        index[ident] = {"date": date, "title": title, "status": "ok", "file": cap, "chars": len(r.text)}
        if n % 20 == 0:
            json.dump(index, open(index_path, "w"), indent=0); print(f"  {n}/{len(items)}", flush=True)
    json.dump(index, open(index_path, "w"), indent=0)
    ok = sum(1 for v in index.values() if v["status"] == "ok")
    print(f"done: {ok} transcripts; {missing} items without one this run (reasons recorded in index.json)")


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
