#!/usr/bin/env python3
"""Summaries.csv -> Bill_Summaries tab: the ingest's contracts, on fixture rows shaped like LIS's (measured 20261).

(1) zero-padded ids normalize to the tracker's form (HB0001 -> HB1); an unreadable id is COUNTED, not guessed;
(2) tags are stripped -- nothing from the feed reaches the app as markup; entities decode;
(3) every measured SUMMARY_TYPE gets its lifecycle rank; an unknown type is kept, UNRANKED, and counted;
(4) an empty fetch returns no rows, and the writer then leaves the tab untouched (last good summaries stay);
(5) the header the worker writes is the header the app checks (web/src/data/summaries.ts EXPECTED_HEADER);
(6) the content hash is written WITH the data (one batch), and an identical cycle skips the rewrite.

Run: python3 test_bill_summaries.py
"""
import re, sys
from unittest import mock

import pandas as pd
import bill_tracker as bt

FAILS = 0


def check(name, ok, detail=""):
    global FAILS
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    FAILS += 0 if ok else 1


FIXTURE = pd.DataFrame({
    "SUM_BILNO": ["HB0001", "HB0001", "SJ0012", "XX", "SB0005"],
    "SUMMARY_DOCID": ["HB1S", "HB1SER", "SJ12S", "?", "SB5S"],
    "SUMMARY_TYPE": ["SUMMARY AS INTRODUCED", "SUMMARY AS PASSED", "SUMMARY AS PASSED SENATE",
                     "SUMMARY AS INTRODUCED", "SUMMARY AS SOMETHING NEW"],
    "SUMMARY_TEXT": ["<p class=sumtext><b>Minimum wage.</b>  Increases the  wage.</p>",
                     "<p class='sumtext'><b>Minimum wage.</b> Increases it &amp; indexes it.</p>",
                     "<p>Study; report.</p>", "<p>orphan</p>", "<p>New stage.</p>"],
}, dtype=str)


def main():
    with mock.patch.object(bt, "safe_fetch_csv", return_value=FIXTURE):
        rows, st = bt._build_summaries("20261")
    by = {(r[0], r[1]): r for r in rows}
    check("HB0001 -> HB1, SJ0012 -> SJ12", ("HB1", "SUMMARY AS INTRODUCED") in by and ("SJ12", "SUMMARY AS PASSED SENATE") in by,
          f"{list(by)}")
    check("unreadable id counted and skipped", st["skipped_bad_bill"] == 1 and not any(r[0] == "XX" for r in rows), f"{st}")
    t = by[("HB1", "SUMMARY AS PASSED")][3]
    check("tags stripped, entities decoded, whitespace collapsed", t == "Minimum wage. Increases it & indexes it.", repr(t))
    check("no '<' survives in any published text", not any("<" in r[3] for r in rows))
    check("measured types ranked (introduced 0 < passed 2)",
          by[("HB1", "SUMMARY AS INTRODUCED")][2] == 0 and by[("HB1", "SUMMARY AS PASSED")][2] == 2)
    check("unknown type kept, unranked, counted",
          by.get(("SB5", "SUMMARY AS SOMETHING NEW"), [None, None, "x"])[2] == "" and st["unknown_types"] == 1, f"{st}")
    check("every measured type has a rank", set(bt.SUMMARY_STAGE_RANK) == {
        "SUMMARY AS INTRODUCED", "SUMMARY AS PASSED HOUSE", "SUMMARY AS PASSED SENATE", "SUMMARY AS PASSED",
        "SUMMARY AS ENACTED WITH GOVERNOR'S RECOMMENDATION"})

    with mock.patch.object(bt, "safe_fetch_csv", return_value=pd.DataFrame()):
        rows0, st0 = bt._build_summaries("20261")
    sheet = mock.Mock()
    wrote = bt.write_bill_summaries(sheet, rows0, st0)
    check("empty fetch -> no rows, tab untouched", rows0 == [] and st0["rows"] == 0 and wrote is False
          and not sheet.worksheet.called and not sheet.add_worksheet.called)

    class WS:
        row_count, col_count = 10, 4
        def __init__(self): self.cells, self.batches, self.cleared = {}, [], 0
        def acell(self, a1): return mock.Mock(value=self.cells.get(a1))
        def resize(self, rows, cols): self.row_count, self.col_count = rows, cols
        def clear(self): self.cleared += 1; self.cells = {}
        def batch_update(self, ups):
            self.batches.append(ups)
            for u in ups: self.cells[u["range"]] = u["values"][0][0] if u["range"] != "A1" else u["values"]
    ws = WS(); sheet2 = mock.Mock(); sheet2.worksheet.return_value = ws
    first = bt.write_bill_summaries(sheet2, rows, st)
    ranges = [u["range"] for u in ws.batches[-1]] if ws.batches else []
    check("first write: data + hash in ONE batch", first is True and ranges == ["A1", bt.BILL_SUMMARIES_HASH_CELL], f"{ranges}")
    check("hash cell sits clear of the data columns",
          bt._col_number(bt.BILL_SUMMARIES_HASH_CELL) > len(bt.BILL_SUMMARIES_HEADER))
    second = bt.write_bill_summaries(sheet2, rows, st)
    check("identical cycle skips the rewrite", second is False and ws.cleared == 1 and len(ws.batches) == 1)
    third = bt.write_bill_summaries(sheet2, rows[:-1], st)
    check("changed content rewrites", third is True and ws.cleared == 2)

    ts = open("web/src/data/summaries.ts").read()
    m = re.search(r"EXPECTED_HEADER = \[([^\]]*)\]", ts)
    app_header = re.findall(r'"([^"]*)"', m.group(1)) if m else None
    check("worker header == app's expected header", app_header == bt.BILL_SUMMARIES_HEADER,
          f"{app_header} vs {bt.BILL_SUMMARIES_HEADER}")
    print(f"\n{'ALL PASS' if not FAILS else str(FAILS) + ' FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
