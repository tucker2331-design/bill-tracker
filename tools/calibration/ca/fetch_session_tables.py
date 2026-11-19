#!/usr/bin/env python3
"""Pull ONLY the tables the CA stats need from Legislative Counsel's yearly pubinfo zips, with HTTP range requests:
the zip's central directory, then each wanted member's bytes — never the 1+ GB of bill text (.lob files).

Bulk host only (downloads.leginfo.legislature.ca.gov, public domain by Gov. Code §10248.5), honest User-Agent, one
pass per session, CRC-checked against the zip's own directory. Writes tools/historical_cache/ca/<year>/tables/*.dat
+ MANIFEST.json (gitignored: regenerate with this script).

    python3 tools/calibration/ca/fetch_session_tables.py 2017 2019 2021 2023
"""
import json
import os
import struct
import sys
import urllib.request
import zlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, ROOT)
from states.pa_fetch import USER_AGENT  # noqa: E402

BASE = "https://downloads.leginfo.legislature.ca.gov/pubinfo_{year}.zip"
WANT = {"BILL_TBL", "BILL_HISTORY_TBL", "BILL_VERSION_TBL", "BILL_VERSION_AUTHORS_TBL", "LEGISLATOR_TBL",
        "BILL_SUMMARY_VOTE_TBL", "BILL_DETAIL_VOTE_TBL", "LOCATION_CODE_TBL", "COMMITTEE_HEARING_TBL", "BILL_MOTION_TBL"}


def rng(url, a, b=None):
    h = {"User-Agent": USER_AGENT, "Range": f"bytes={a}-{'' if b is None else b}" if a >= 0 else f"bytes={a}"}
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r:
        if r.status != 206:
            raise RuntimeError(f"{url}: expected 206 Partial Content, got {r.status} — refusing a full download")
        return r.headers.get("Content-Range"), r.read()


def central_directory(url):
    cr, tail = rng(url, -65536)
    total = int(cr.split("/")[1])
    i = tail.rfind(b"PK\x05\x06")
    _n, cdsize, cdoff = struct.unpack("<HII", tail[i + 10:i + 20])
    j = tail.rfind(b"PK\x06\x06")
    if j >= 0:                                    # zip64 end record: 64-bit size and offset
        cdsize, cdoff = struct.unpack("<QQ", tail[j + 40:j + 56])
    start = total - len(tail)
    cd = tail[cdoff - start:cdoff - start + cdsize] if cdoff >= start else rng(url, cdoff, cdoff + cdsize - 1)[1]
    out, p = {}, 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        method, = struct.unpack("<H", cd[p + 10:p + 12])
        crc, csz, usz = struct.unpack("<III", cd[p + 16:p + 28])
        fl, el, cl = struct.unpack("<HHH", cd[p + 28:p + 34])
        off, = struct.unpack("<I", cd[p + 42:p + 46])
        name = cd[p + 46:p + 46 + fl].decode()
        extra = cd[p + 46 + fl:p + 46 + fl + el]
        q = 0
        while q + 4 <= len(extra):                # zip64 extra field carries the real sizes / offset
            hid, hsz = struct.unpack("<HH", extra[q:q + 4])
            if hid == 1:
                vals, k = [], q + 4
                for flag in (usz == 0xFFFFFFFF, csz == 0xFFFFFFFF, off == 0xFFFFFFFF):
                    if flag:
                        vals.append(struct.unpack("<Q", extra[k:k + 8])[0]); k += 8
                it = iter(vals)
                usz = next(it) if usz == 0xFFFFFFFF else usz
                csz = next(it) if csz == 0xFFFFFFFF else csz
                off = next(it) if off == 0xFFFFFFFF else off
            q += 4 + hsz
        out[name] = (method, crc, csz, usz, off)
        p += 46 + fl + el + cl
    return out


def fetch(year):
    url = BASE.format(year=year)
    cd = central_directory(url)
    dest = os.path.join(ROOT, "tools", "historical_cache", "ca", str(year), "tables")
    os.makedirs(dest, exist_ok=True)
    manifest = {"url": url, "tables": {}}
    for name, (method, crc, csz, usz, off) in sorted(cd.items()):
        t = name.split("/")[-1].upper()
        if not t.endswith(".DAT") or t[:-4] not in WANT:
            continue
        _, head = rng(url, off, off + 29)
        fl, el = struct.unpack("<HH", head[26:30])
        _, data = rng(url, off + 30 + fl + el, off + 30 + fl + el + csz - 1)
        raw = zlib.decompress(data, -15) if method == 8 else data
        if zlib.crc32(raw) & 0xFFFFFFFF != crc or len(raw) != usz:
            raise RuntimeError(f"{year} {t}: CRC/size mismatch — refusing to keep a corrupt table")
        with open(os.path.join(dest, t[:-4] + ".dat"), "wb") as f:
            f.write(raw)
        manifest["tables"][t[:-4]] = {"bytes": usz, "compressed": csz, "crc32": f"{crc:08x}"}
        print(year, t, usz)
    missing = WANT - set(manifest["tables"])
    if missing:
        raise RuntimeError(f"{year}: export lacks {sorted(missing)}")
    json.dump(manifest, open(os.path.join(dest, "MANIFEST.json"), "w"), indent=1)


if __name__ == "__main__":
    for y in sys.argv[1:]:
        fetch(y)
