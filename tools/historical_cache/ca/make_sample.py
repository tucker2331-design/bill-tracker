#!/usr/bin/env python3
"""Cut the CA golden sample from a REAL full pubinfo export: every row of a seeded, outcome-stratified set of bills,
plus the whole committee-code, legislator, motion and code tables. Rows are copied byte-for-byte (no re-encoding).

    python3 tools/historical_cache/ca/make_sample.py tools/historical_cache/ca/2025/pubinfo_2025.zip
Writes tools/historical_cache/ca/sample/{pubinfo_sample.zip, pubinfo_load.zip, expected.json}.
"""
import collections
import datetime
import io
import json
import os
import random
import shutil
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, ROOT)
from states import ca_adapter, ca_pubinfo  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sample")
WHOLE = {"LOCATION_CODE_TBL", "LEGISLATOR_TBL", "BILL_MOTION_TBL", "CODES_TBL"}
PER_STATUS = {"Chaptered": 60, "Vetoed": 30, "In Committee Process": 60, "In Floor Process": 30}


def main(full):
    os.makedirs(OUT, exist_ok=True)
    shutil.copy(os.path.join(HERE, "pubinfo_load.zip"), os.path.join(OUT, "pubinfo_load.zip"))
    schema = ca_pubinfo.load_schema(open(os.path.join(HERE, "pubinfo_load.zip"), "rb").read())
    ex = ca_pubinfo.Export(full, schema)
    bills = [b for b in ex.rows("BILL_TBL") if b["SESSION_NUM"] == "0"]
    rng = random.Random(20261118)
    by = collections.defaultdict(list)
    for b in bills:
        res = b["MEASURE_TYPE"] in ("ACR", "SCR", "AJR", "SJR", "HR", "SR")
        by["resolution" if res else b["CURRENT_STATUS"]].append(b)
    pick = []
    for k, n in list(PER_STATUS.items()) + [("resolution", 30)]:
        pick += rng.sample(by[k], min(n, len(by[k])))
    rest = [b for k, v in by.items() if k not in PER_STATUS and k != "resolution" for b in v]
    pick += rng.sample(rest, min(30, len(rest)))
    ids = {b["BILL_ID"] for b in pick}
    versions = {b["LATEST_BILL_VERSION_ID"] for b in pick}
    for v in ex.rows("BILL_VERSION_TBL"):
        if v["BILL_ID"] in ids:
            versions.add(v["BILL_VERSION_ID"])
    zin = ex.z
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for name in zin.namelist():
            tbl = name.split("/")[-1].upper()
            if not tbl.endswith(".DAT"):
                continue
            t = tbl[:-4]
            cols = schema.get(t)
            if cols is None:
                continue
            keep = []
            with zin.open(name) as f:
                for raw in io.TextIOWrapper(f, encoding="utf-8", errors="replace", newline="\n"):
                    if t in WHOLE:
                        keep.append(raw)
                        continue
                    parts = raw.rstrip("\n").split("\t")
                    if len(parts) != len(cols):
                        continue
                    row = dict(zip(cols, parts))
                    bid = row.get("BILL_ID", "").strip("`")
                    vid = row.get("BILL_VERSION_ID", "").strip("`")
                    if bid in ids or (t == "BILL_VERSION_AUTHORS_TBL" and vid in versions):
                        keep.append(raw)
            zout.writestr(name.split("/")[-1], "".join(keep))
    with open(os.path.join(OUT, "pubinfo_sample.zip"), "wb") as f:
        f.write(buf.getvalue())
    sx = ca_pubinfo.Export(os.path.join(OUT, "pubinfo_sample.zip"), schema)
    records, comp = ca_adapter.run_intake(sx, datetime.date(2026, 11, 18), "2026-11-18T21:00:00Z")
    outcomes = collections.Counter(r["outcome"] for r in records)
    raw = {f"{b['MEASURE_TYPE']}{int(b['MEASURE_NUM'])}": b for b in pick}
    checks = {}
    # anchors read from BILL_TBL fields (independent of the history routing): a chapter number = law; Vetoed = vetoed
    for b in [x for x in pick if x["CHAPTER_NUM"]][:3]:
        checks[f"{b['MEASURE_TYPE']}{int(b['MEASURE_NUM'])}"] = {"outcome": "signed", "stage": "law"}
    for b in [x for x in pick if x["CURRENT_STATUS"] == "Vetoed" and not x["CHAPTER_NUM"]][:3]:
        checks[f"{b['MEASURE_TYPE']}{int(b['MEASURE_NUM'])}"] = {"outcome": "vetoed"}
    for b in [x for x in pick if x["CURRENT_STATUS"] == "In Committee Process" and x["MEASURE_TYPE"] in ("AB", "SB")][:3]:
        checks[f"{b['MEASURE_TYPE']}{int(b['MEASURE_NUM'])}"] = {"outcome": "in_progress"}
    exp = {"source": os.path.basename(full), "cut_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "bills": len(pick), "outcomes": dict(outcomes), "bills_checked": checks, "completeness": comp}
    json.dump(exp, open(os.path.join(OUT, "expected.json"), "w"), indent=1)
    print(json.dumps({k: exp[k] for k in ("bills", "outcomes", "bills_checked")}, indent=1))
    print("sample zip", os.path.getsize(os.path.join(OUT, "pubinfo_sample.zip")), "bytes; raw kept", len(raw))


if __name__ == "__main__":
    main(sys.argv[1])
