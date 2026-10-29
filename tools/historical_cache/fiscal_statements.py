#!/usr/bin/env python3
"""Fiscal impact statements (Department of Planning and Budget) for 2025 and 2026 -- what each bill would COST.

Owner, 2026-10-14: "go deeper in fiscal stuff ... both of the OKs are clear assuming they dont violate any internal or
external policy". Why this is inside both:
  * EXTERNAL -- the statements are public PDFs on LIS's file host (lis.blob.core.windows.net/files/<id>.PDF), linked from
    every LIS bill page and from Open States. If LIS's API terms reach these files, the use still complies: personal and
    non-commercial (pre-launch research), authorized sessions only, and a light load (ToS §4).
  * INTERNAL -- docs/knowledge/lis_api_authorization.md: 2025/2026 only, enforced here with assert_lis_authorized();
    docs/knowledge/lis_api_safety.md: more than a dozen requests is an INGEST, so the five guardrails apply:
      1 conditional -- a cached file is never fetched again        2 jitter -- 4-7 s between requests, randomized
      3 backoff -- 429/5xx back off and retry, 3 failures in a row stop the run
      4 hard ceiling -- MAX_REQUESTS per run                         5 one-off research pull, not a recurring job
URLs come from Open States' bill documents (no LIS lookups needed to find them). Only the DPB statement is used, the
FIRST one per bill (the one a committee sees before it votes). PDFs are cached outside git; parsed fields are committed.

Run: python3 tools/historical_cache/fiscal_statements.py fetch 2025 2026
     python3 tools/historical_cache/fiscal_statements.py parse 2025 2026
"""
from __future__ import annotations
import csv, io, json, os, random, re, sys, time, zipfile, warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from lis_authorization import assert_lis_authorized

OUT = os.path.join(HERE, "va_fiscal"); PDF = os.path.join(OUT, "pdf")
# a fresh connection per request: pooled keep-alive connections went stale on a flaky network (2026-10-14)
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)", "Connection": "close"}
MAX_REQUESTS = 3500
DPB = "Department of Planning and Budget"


def first_statements(year):
    """bill -> (url, note) for the earliest DPB statement (lowest file id = first issued)."""
    zf = zipfile.ZipFile(os.path.join(HERE, "openstates_va", f"VA_{year}.zip"))
    dn = next(n for n in zf.namelist() if n.endswith(f"VA_{year}_bill_documents.csv"))
    ln = next(n for n in zf.namelist() if n.endswith(f"VA_{year}_bill_document_links.csv"))
    docs = {d["id"]: d for d in csv.DictReader(io.TextIOWrapper(zf.open(dn), "utf-8"))}
    best = {}
    for l in csv.DictReader(io.TextIOWrapper(zf.open(ln), "utf-8")):
        d = docs.get(l["document_id"], {})
        m = re.search(r"\(((?:HB|SB)\d+)\)", d.get("note", ""))
        fid = re.search(r"/files/(\d+)\.PDF$", l["url"], re.I)
        if DPB in d.get("note", "") and m and fid and l["url"].startswith("https://lis.blob.core.windows.net/files/"):
            if m.group(1) not in best or int(fid.group(1)) < best[m.group(1)][0]:
                best[m.group(1)] = (int(fid.group(1)), l["url"])
    return best


def fetch(years):
    import requests
    s = requests.Session(); n = 0; fails = 0
    for y in years:
        assert_lis_authorized(f"{y}1")                       # 2025 / 2026 only -- raises otherwise
        os.makedirs(os.path.join(PDF, str(y)), exist_ok=True)
        todo = first_statements(y)
        print(f"{y}: {len(todo)} bills with a DPB statement", flush=True)
        for bill, (fid, url) in sorted(todo.items()):
            path = os.path.join(PDF, str(y), f"{bill}_{fid}.pdf")
            if os.path.exists(path):
                continue                                     # guardrail 1
            if n >= MAX_REQUESTS:
                raise SystemExit(f"hard ceiling {MAX_REQUESTS} reached -- stopping (guardrail 4)")
            for attempt in range(4):
                n += 1
                try:
                    r = s.get(url, headers=UA, timeout=60)
                except requests.RequestException as e:
                    print(f"  {bill}: {type(e).__name__}, backing off", flush=True); time.sleep(30 * (attempt + 1)); continue
                if r.status_code == 200:
                    open(path, "wb").write(r.content); fails = 0; break
                if r.status_code in (429, 500, 502, 503, 504):
                    wait = int(r.headers.get("Retry-After", 60 * (attempt + 1)))
                    print(f"  {bill}: HTTP {r.status_code}, waiting {wait}s (guardrail 3)", flush=True); time.sleep(wait)
                    continue
                print(f"  {bill}: HTTP {r.status_code} -- skipped, counted", flush=True); break
            else:
                fails += 1
                if fails >= 3:
                    raise SystemExit("3 bills failed in a row -- stopping (guardrail 3)")
            time.sleep(4 + random.random() * 3)              # guardrail 2
            if n % 100 == 0:
                print(f"  {n} requests", flush=True)
    print(f"done: {n} requests")




def _num(raw):
    raw = raw.strip()
    neg = raw.startswith("(") or raw.startswith("-")
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(million|billion)?", raw, re.I)
    if not m:
        return None
    v = float(m.group(1).replace(",", "") or 0) * {"million": 1e6, "billion": 1e9}.get((m.group(2) or "").lower(), 1)
    return -v if neg else v


def _table_total(t, heading):
    """The TOTAL row of a DPB table such as 'General Fund Expenditure Impact' -> list of yearly amounts."""
    i = t.lower().find(heading.lower())
    if i < 0:
        return None
    seg = t[i:i + 1500]
    m = re.search(r"TOTAL((?:\s+\(?-?\$?[\d,]+(?:\.\d+)?\)?)+)", seg)
    if not m:
        return None
    return [v for v in (_num(x) for x in re.findall(r"\(?-?\$?[\d,]+(?:\.\d+)?\)?", m.group(1))) if v is not None]


def parse_one(text):
    """Structured fields from a DPB State Fiscal Impact Statement. The form is fixed: 'Budget Amendment Necessary',
    'Items Impacted', 'Fiscal Summary' (one sentence), then tables whose last row is TOTAL, by fiscal year."""
    t = re.sub(r"\s+", " ", text)
    low = t.lower()
    f = {"chars": len(t), "prelim": int("is preliminary" in low)}
    m = re.search(r"budget amendment necessary:?\s*(yes|no)", low)
    f["budget_amendment"] = {"yes": 1, "no": 0}.get(m.group(1)) if m else None
    i = low.find("fiscal summary:"); summ = low[i:i + 700] if i >= 0 else ""
    f["summary_found"] = int(i >= 0)
    f["no_impact"] = int(bool(re.search(r"not expected to (?:create|have|result in)[^.]{0,40}(?:fiscal|budgetary) impact|"
                                        r"no (?:state )?(?:fiscal|budgetary) impact|no expected (?:state )?fiscal impact",
                                        summ)))
    f["indeterminate"] = int("indeterminate" in summ)
    f["revenue_mentioned"] = int("revenue" in summ)
    gf = _table_total(t, "General Fund Expenditure Impact")
    ngf = _table_total(t, "Nongeneral Fund Expenditure Impact")
    rev = _table_total(t, "Revenue Impact")
    f["gf_cost_max"] = max(gf) if gf else 0.0
    f["ngf_cost_max"] = max(ngf) if ngf else 0.0
    f["rev_max_abs"] = max((abs(v) for v in rev), default=0.0) if rev else 0.0
    f["has_cost_table"] = int(bool(gf or ngf))
    # a dollar figure stated in the summary when no table exists ("at least $37.35 million general fund per year")
    sm = [v for v in (_num(x) for x in re.findall(r"\$\s?[\d,]+(?:\.\d+)?\s*(?:million|billion)?", summ)) if v]
    f["summary_amount_max"] = max(sm) if sm else 0.0
    return f


def parse(years):
    import pypdf, logging
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    for y in years:
        out = {}; bad = 0
        d = os.path.join(PDF, str(y))
        for fn in sorted(os.listdir(d)):
            bill = fn.split("_")[0]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    text = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(os.path.join(d, fn)).pages)
            except Exception as e:                            # counted, never silent (Standard #4)
                bad += 1; out[bill] = {"parse_error": type(e).__name__}; continue
            out[bill] = parse_one(text)
        json.dump(out, open(os.path.join(OUT, f"{y}.json"), "w"), indent=0, sort_keys=True)
        print(f"{y}: parsed {len(out) - bad}, unreadable {bad}")


if __name__ == "__main__":
    cmd, yrs = sys.argv[1], [int(a) for a in sys.argv[2:]]
    {"fetch": fetch, "parse": parse}[cmd](yrs)
