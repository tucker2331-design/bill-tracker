#!/usr/bin/env python3
"""Extract structured LIS truth JSON from bill-details DOM dumps.

Parses <div class="history-event-row"> blocks in each bill's DOM dump and
filters to the crossover window (Feb 9-13, 2026). Emits exactly five fields
per action — no PDF links, no fiscal impact statements, no bill text.

Usage:
    python3 tools/crossover_audit/extract_truth.py \
        --dumps /tmp/lis_audit \
        --out docs/testing/crossover_lis_truth.json

Parser strategy:
    The LIS bill-details DOM uses NESTED spans in the description block
    (<span><span>text</span></span>) and has no blank lines between rows. A
    naive regex for a single row (e.g. `<span>(.*?)</span></div>`) over-
    captures across row boundaries. The fix: split the HTML first on
    `<div class="history-event-row">` starts, then parse each segment with
    narrower regexes. The segment boundary guarantees no cross-row
    contamination.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

ROW_SPLIT_RE = re.compile(r'<div class="history-event-row[^"]*">')
DATA_RE = re.compile(
    r'<div class="history-event-data"><span>([^<]+)</span><span>([^<]*)</span></div>'
)
DESC_RE = re.compile(
    # Match description block contents up to the FIRST </div>. Safe because
    # description content is only spans/buttons/anchors — no nested <div>.
    r'<div class="history-event-description">(.*?)</div>',
    re.DOTALL,
)
DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
BILL_NAME_RE = re.compile(r"^(HB|SB|HJ|SJ|HR|SR)\d+$")
COMMITTEE_ANCHOR_RE = re.compile(
    r'<a[^>]*committee-information/([^/]+)/committee-details"[^>]*>([^<]+)</a>'
)

WINDOW_START = (2026, 2, 9)
WINDOW_END = (2026, 2, 13)


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    # Unescape HTML entities (&amp;, &nbsp;, numeric refs) that LIS emits in
    # committee / bill text. Without this, downstream text comparisons against
    # API-sourced strings fail whenever names contain "&" etc.
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_description(segment: str) -> str:
    """Find the description block inside one row segment.

    Row descriptions have the shape
        <div class="history-event-description"><span><span>TEXT</span></span>...</div>
    The inner span close is followed immediately by the outer span close,
    then junk (<button>, <div>, etc.) until the description's </div>. A
    minimal `.*?` match is correct because the segment is already one row —
    there is no way to run past the row boundary (row segments were split
    first on history-event-row starts).
    """
    m = DESC_RE.search(segment)
    if not m:
        return ""
    inner = m.group(1)
    # The captured content still has the inner <span>...</span>; strip_tags
    # flattens all tags and normalizes whitespace.
    return inner


def parse_bill(path: Path):
    html = path.read_text()
    bill = path.stem
    if not BILL_NAME_RE.match(bill):
        return bill, None

    # Segment on row boundaries. Skip segment[0] — preamble before first row.
    segments = ROW_SPLIT_RE.split(html)[1:]

    rows = []
    for seg in segments:
        data_m = DATA_RE.search(seg)
        if not data_m:
            continue
        date_str = data_m.group(1).strip()
        chamber = data_m.group(2).strip()

        dm = DATE_RE.match(date_str)
        if not dm:
            continue
        mo, dy, yr = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        key = (yr, mo, dy)
        if not (WINDOW_START <= key <= WINDOW_END):
            continue

        desc_html = extract_description(seg)

        com_m = COMMITTEE_ANCHOR_RE.search(desc_html)
        committee_code = com_m.group(1) if com_m else ""
        committee_name = com_m.group(2).strip() if com_m else ""

        action = strip_tags(desc_html)

        rows.append({
            "date": f"{yr:04d}-{mo:02d}-{dy:02d}",
            "chamber": chamber,
            "committee_code": committee_code,
            "committee_name": committee_name,
            "action": action,
        })
    return bill, rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dumps", required=True, help="Directory of <BILL>.html dumps")
    ap.add_argument("--out", required=True, help="Output JSON path")
    args = ap.parse_args()

    dumps_dir = Path(args.dumps)
    out_path = Path(args.out)

    by_bill = {}
    n_rows = 0
    n_files = 0
    n_empty = 0
    for p in sorted(dumps_dir.glob("*.html")):
        bill, rows = parse_bill(p)
        if rows is None:  # non-bill file
            continue
        n_files += 1
        by_bill[bill] = rows
        n_rows += len(rows)
        if not rows:
            n_empty += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(by_bill, indent=2))
    print(f"Parsed {n_files} bills, {n_rows} Feb 9-13 actions. ({n_empty} bills empty in window.)")
    print(f"  → wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
