#!/usr/bin/env python3
"""Every cell the Bill_Tracker writer touches in its one batched write must be DISTINCT.

Regression for the 2026-07-30 -> 2026-09-28 collision: completeness moved T -> U onto cadence's
BILL_LAST_RUN_CELL (U1), so the batch wrote the trust payload to U1 and then overwrote it with a timestamp --
every cycle, silently. Runs the REAL write_bill_tracker against a fake gspread, captures the batch ranges,
and checks (1) no two ranges share a top-left cell, (2) the completeness payload survives as the value at
its cell, (3) the prior-payload read happens at the same cell the payload is written to.

Run: python3 test_bill_tracker_cells.py
"""
import json, os, re, sys
from unittest import mock

import bill_tracker as bt
import cadence

FAILS = 0


def check(name, ok, detail=""):
    global FAILS
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    FAILS += 0 if ok else 1


class FakeWS:
    def __init__(self):
        self.row_count, self.col_count, self.batches, self.read = 10, 10, [], []
    def resize(self, rows, cols):
        self.row_count, self.col_count = rows, cols
    def acell(self, a1):
        self.read.append(a1)
        return mock.Mock(value=None)
    def clear(self):
        pass
    def batch_update(self, updates):
        self.batches.append(updates)


def main():
    comp_cell = getattr(bt, "COMPLETENESS_CELL", None)
    check("completeness cell is a named constant that differs from the cadence marker",
          comp_cell is not None and comp_cell != cadence.BILL_LAST_RUN_CELL,
          f"{comp_cell} vs {cadence.BILL_LAST_RUN_CELL}")
    ws = FakeWS()
    sheet = mock.Mock(); sheet.worksheet.return_value = ws
    rec = {"bill": "HB1", "title": "t", "status_lis": "s", "outcome": "in_progress", "outcome_origin": "keyword_fallback",
           "patron": "p", "patron_id": "H1", "chamber": "House", "crossed_over": False, "floor_house": "",
           "floor_senate": "", "last_committee": "", "referral_count": 0, "latest_vote": {}, "upcoming": [],
           "last_action_date": "", "history": [], "data_as_of_utc": "x", "source": "LIS", "legislation_class": ""}
    comp = {"universe_count": 1, "records_written": 1}
    with mock.patch.dict(os.environ, {"GCP_CREDENTIALS": "{}"}), \
         mock.patch.object(bt, "Credentials") as C, mock.patch.object(bt.gspread, "authorize") as A:
        A.return_value.open_by_key.return_value = sheet
        C.from_service_account_info.return_value = None
        bt.write_bill_tracker([rec], comp)
    ranges = [u["range"] for u in ws.batches[-1]]
    tops = [re.match(r"[A-Z]+\d+", r).group(0) for r in ranges]
    check("no two batched writes share a cell", len(set(tops)) == len(tops), f"ranges {ranges}")
    # Replay the batch in order, as Sheets does: the LAST write to a cell wins.
    final = {}
    for u in ws.batches[-1]:
        final[re.match(r"[A-Z]+\d+", u["range"]).group(0)] = u["values"]
    survived = []
    for cell, vals in final.items():
        top = vals[0][0] if vals and vals[0] else None
        # Only a JSON object can be the payload; the timestamp and the header grid are skipped by SHAPE, not by
        # swallowing a parse error (house rule: no silent except).
        if isinstance(top, str) and top.startswith("{") and json.loads(top).get("universe_count") == 1:
            survived.append(cell)
    check("the completeness payload SURVIVES the batch (last write per cell wins)", len(survived) == 1,
          f"final cells {list(final)}")
    check("the prior-payload read is the cell the payload survives at", bool(survived) and survived[0] in ws.read,
          f"read {ws.read}, payload at {survived}")
    print(f"\n{'ALL PASS' if not FAILS else str(FAILS) + ' FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
