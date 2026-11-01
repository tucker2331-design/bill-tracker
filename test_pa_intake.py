#!/usr/bin/env python3
"""Pennsylvania intake — goldens on a REAL download, plus the polite-fetch rules.

INPUT: tools/historical_cache/pa/2025_0/ — the real files fetched 2026-10-31 from www.palegis.us (MANIFEST.json has
the URLs, sizes and SHA-256): the hourly Bill History export (5,269 documents), the House and Senate
committee-schedule RSS (7 meetings, none listing bills yet), and the data index page. No hand-made fixture.

GOLDEN (goldens/pa_bill_records_2025_0.json): a SHA-256 of every record + the completeness payload + every URL the
intake asked for, with spot records that can be checked by eye against the export's own <fullAction> lines.

INVARIANTS (independent of the golden, from the export itself):
  * records == the export's own totalDocuments; 0 unclassified verbs; 0 unreadable dates
  * signed == the number of "Act No." actions (200); every signed bill is at stage `law`
  * nothing is declared dead (a two-year session still open) and there is no crossover stage
  * every bill that passed both floors is at concurrence or beyond
  * next meetings come only from the schedule's own Bills field (empty today -> no upcoming anywhere)

FETCH RULES (owner 2026-10-31): bulk feeds only (a /legislation/bills/ page is refused before any request), at most
once an hour per URL, one request at a time, an honest User-Agent with a contact address, and a 403 STOPS the intake
with no retry and no header change.

Re-capture ONLY for an intended output change:  python3 test_pa_intake.py --write
Run: python3 test_pa_intake.py
"""
import collections
import datetime
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import xml.etree.ElementTree as ET
import zipfile

from states import get_state
from states import pa_adapter as A
from states import pa_fetch as F

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "tools", "historical_cache", "pa", "2025_0")
GOLDEN = os.path.join(HERE, "goldens", "pa_bill_records_2025_0.json")
TODAY = datetime.date(2026, 10, 31)          # the day the sample was downloaded
NOW = "2026-10-31T23:36:00Z"
PA = get_state("PA")
FILES = {
    "https://www.palegis.us/data": "data_index.html",
    "https://www.palegis.us/data/file?documentType=BillHistoryData&session=2025_0":
        "PA-Bill-History-2025-RegularSession-202610311932.zip",
    "https://www.palegis.us/house/rss/committee/schedule": "house_committee_schedule.xml",
    "https://www.palegis.us/senate/rss/committee/schedule": "senate_committee_schedule.xml",
}
FAILS = 0


def check(name, ok, detail=""):
    global FAILS
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    FAILS += 0 if ok else 1


class SampleFetcher:
    """Serves the committed real files by URL; records what was asked for. No network."""
    def __init__(self):
        self.asked = []

    def get(self, url):
        self.asked.append(url)
        with open(os.path.join(CACHE, FILES[url]), "rb") as f:
            return f.read()


def run():
    fx = SampleFetcher()
    records, comp = A.run_intake(fx, None, TODAY, NOW)
    return {"records": records, "completeness": comp, "asked": fx.asked}


def summary(out):
    recs = out["records"]
    by = {r["bill"]: r for r in recs}
    blob = json.dumps(out, sort_keys=True, ensure_ascii=False).encode()

    def spot(b):
        r = dict(by[b])
        r["history"] = r["history"][-3:]
        r["copatrons"] = len(r["copatrons"])
        return r
    return {
        "sha256": hashlib.sha256(blob).hexdigest(),
        "records": len(recs),
        "asked": out["asked"],
        "completeness": out["completeness"],
        "outcomes": dict(sorted(collections.Counter(r["outcome"] for r in recs).items())),
        "stages": dict(sorted(collections.Counter(r["stage"] for r in recs).items())),
        "spot": {b: spot(b) for b in ("HB17", "HB1099", "HB257", "HR1", "SB160")},
    }


def export_root():
    with zipfile.ZipFile(os.path.join(CACHE, FILES["https://www.palegis.us/data/file?documentType=BillHistoryData&session=2025_0"])) as z:
        return ET.fromstring(z.read(z.namelist()[0]))


def fetch_rules():
    tmp = tempfile.mkdtemp()
    try:
        t = [1000.0]
        calls = []

        class Resp(io.BytesIO):
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def opener(req, timeout):
            calls.append((req.full_url, req.get_header("User-agent")))
            return Resp(b"<rss/>")
        f = F.PoliteFetcher(tmp, opener=opener, clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s))
        url = "https://www.palegis.us/house/rss/committee/schedule"
        f.get(url)
        check("honest User-Agent naming the repo as contact, sent as-is",
              calls[0][1] == F.USER_AGENT and "github.com/tucker2331-design/bill-tracker" in F.USER_AGENT
              and "Mozilla" not in F.USER_AGENT and "@" not in F.USER_AGENT)
        t[0] += 3599
        f.get(url)
        check("same URL inside the hour -> served from cache, no request", len(calls) == 1)
        t[0] += 2
        f.get(url)
        check("after the hour -> one new request", len(calls) == 2)
        for bad in ("https://www.palegis.us/legislation/bills/2025/hb17",
                    "https://www.palegis.us/legislation/bills/text/PDF/2025/0/HB0017/PN0002",
                    "https://example.org/data"):
            try:
                f.get(bad)
                check(f"refuses non-feed {bad}", False, "it fetched")
            except F.NotABulkFeed:
                check(f"refuses non-feed {bad} before any request", len(calls) == 2)
        f2 = F.PoliteFetcher(tmp + "/b", opener=opener, clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s))
        before = t[0]
        f2.get("https://www.palegis.us/senate/rss/committee/schedule")
        f2.get("https://www.palegis.us/data")
        check("consecutive requests are spaced", t[0] - before >= f2.spacing)

        refusals = []

        def refusing(req, timeout):
            refusals.append(req.get_header("User-agent"))
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
        f3 = F.PoliteFetcher(tmp + "/c", opener=refusing, clock=lambda: t[0], sleep=lambda s: None)
        try:
            f3.get("https://www.palegis.us/data")
            check("403 stops the intake", False, "no exception")
        except F.FeedRefused:
            check("403 stops the intake (FeedRefused)", True)
        check("403: exactly one request, no retry, header unchanged", refusals == [F.USER_AGENT])
    finally:
        shutil.rmtree(tmp)


def main():
    out = run()
    s = summary(out)
    if "--write" in sys.argv:
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        with open(GOLDEN, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {GOLDEN}: {s['sha256']} ({s['records']} records)")
        return 0

    recs, comp = out["records"], out["completeness"]
    root = export_root()
    acts = [a.findtext("verb") for a in root.iter("action")]
    check("session discovered from the data page = 2025_0", comp["session_code"] == "2025_0")
    check("only bulk feeds requested, each once", out["asked"] == list(FILES))
    check("records == the export's own totalDocuments", len(recs) == int(root.get("totalDocuments")) == 5269)
    check("0 unclassified verbs, 0 unreadable dates", comp["verbs_unclassified"] == 0 and comp["action_dates_unreadable"] == 0)
    check("PA's own 'Undefined Action' rows counted (22)", comp["undefined_actions"] == acts.count("Undefined Action") == 22)
    signed = [r for r in recs if r["outcome"] == "signed"]
    check("signed == 'Act No.' actions (200)", len(signed) == acts.count("Act No.") == 200)
    check("every signed bill is at stage law", all(r["stage"] == "law" for r in signed))
    check("nothing declared dead or carried over (open two-year session)",
          not any(r["outcome"] in ("dead", "carried_over") for r in recs))
    check("no crossover stage exists for PA", not PA.has_crossover and all(r["stage"] in A.STAGE_RANK for r in recs))
    both = [r for r in recs if r["floor_house"] == r["floor_senate"] == "passed" and r["bill"][1] == "B"]
    check("passed both floors -> concurrence or beyond",
          all(A.STAGE_RANK[r["stage"]] >= A.STAGE_RANK["concurrence"] for r in both), f"{len(both)} bills")
    check("schedule read: 7 meetings, none listing bills yet",
          comp["schedule_meetings"] == 7 and comp["schedule_meetings_with_bills"] == 0)
    check("no upcoming meeting invented", not any(r["upcoming"] for r in recs))
    by = {r["bill"]: r for r in recs}
    check("SB49: a reconsidered defeat no longer stands (Codex #254)",
          by["SB49"]["floor_senate"] == "" and by["SB49"]["outcome"] == "in_progress")
    check("SR1: adopted, reconsidered, adopted again -> adopted", by["SR1"]["outcome"] == "adopted")
    concurrent = [by[A.bill_key(b.findtext("body"), b.findtext("type"), b.findtext("number"))]
                  for b in root.iter("bill") if b.findtext("subType") == "C"]
    check("HR25 (concurrent, House only) is NOT final", by["HR25"]["outcome"] == "in_progress" and len(concurrent) == 12)
    check("a concurrent resolution is adopted only with both chambers",
          all(r["floor_house"] == r["floor_senate"] == "passed" for r in concurrent if r["outcome"] == "adopted"))
    big = max(root.iter("bill"), key=lambda b: len(list(b.iter("sponsor"))))
    nums = [int(s.get("sequenceNumber")) for s in big.iter("sponsor")]
    rb = by[A.bill_key(big.findtext("body"), big.findtext("type"), big.findtext("number"))]
    want = [s.text.strip() for s in sorted(big.iter("sponsor"), key=lambda s: int(s.get("sequenceNumber")))]
    check(f"co-sponsors in NUMERIC order past 99 ({rb['bill']}, {max(nums)} sponsors)",
          max(nums) > 99 and [rb["patron"]] + [c["name"] for c in rb["copatrons"]] == want)
    check("history keeps every action", sum(len(r["history"]) for r in recs) == comp["actions_total"] == 19915)
    check("contract keys match VA's record + stage", set(recs[0]) == {
        "bill", "title", "status_lis", "stage", "outcome", "outcome_origin", "patron", "patron_id", "chamber",
        "crossed_over", "floor_house", "floor_senate", "last_committee", "referral_count", "latest_vote", "upcoming",
        "last_action_date", "history", "data_as_of_utc", "source", "legislation_class", "copatrons"})

    with open(GOLDEN, encoding="utf-8") as f:
        want = json.load(f)
    for k in ("records", "asked", "completeness", "outcomes", "stages", "spot", "sha256"):
        ok = json.dumps(s[k], sort_keys=True) == json.dumps(want[k], sort_keys=True)
        check(f"golden: {k} matches {os.path.relpath(GOLDEN, HERE)}", ok)

    fetch_rules()
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
