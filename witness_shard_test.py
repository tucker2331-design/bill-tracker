"""Unit tests for the A-2 Part 2 zero-touch witness shard (`_autoshard_witness_if_full`).

This path DELETES a tab from the live workbook, so it must be provably safe: it may relocate only when the
workbook is actually full, it must VERIFY the copy before deleting the original, and any failure must leave
VA·Live untouched (fail-closed). Duck-typed fakes — no gspread/network — matching cadence_test.py /
session_rollover_test.py (standalone, runnable with plain python3).
"""
import calendar_worker as cw

_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


def expect_raise(fn, msg):
    global _checks
    _checks += 1
    try:
        fn()
    except Exception:
        return
    raise AssertionError(f"expected a raise: {msg}")


class WSNotFound(Exception):
    pass


# Point the worker's gspread.exceptions.WorksheetNotFound at our fake so `except` clauses match.
cw.gspread.exceptions.WorksheetNotFound = WSNotFound

_BOOKS = {}


class FakeCell:
    def __init__(self, value):
        self.value = value


class FakeWS:
    def __init__(self, title, rows, cols, header=None, sid=None):
        self.title, self.row_count, self.col_count = title, rows, cols
        self._header = list(header or [])
        self.id = sid if sid is not None else (abs(hash(title)) % 90000) + 1000
        self.deleted = False
        self.book_id = None
        self._cells = {}

    def row_values(self, n):
        return list(self._header) if n == 1 else []

    def acell(self, a1):
        return FakeCell(self._cells.get(a1))

    def update_acell(self, a1, val):
        self._cells[a1] = val

    def copy_to(self, dest_id):
        dest = _BOOKS[dest_id]
        clone = FakeWS(f"Copy of {self.title}", self.row_count, self.col_count, self._header, sid=dest._next_sid())
        dest._add(clone)
        return {"sheetId": clone.id}


class FakeClient:
    def open_by_key(self, key):
        return _BOOKS[key]


class FakeBook:
    def __init__(self, key, tabs):
        self.id = key
        self._tabs = {t.title: t for t in tabs}
        for t in tabs:
            t.book_id = key
        self._sid = 1
        self.client = FakeClient()
        _BOOKS[key] = self

    def _next_sid(self):
        self._sid += 1
        return 5000 + self._sid

    def _add(self, ws):
        ws.book_id = self.id
        self._tabs[ws.title] = ws

    def worksheets(self):
        return list(self._tabs.values())

    def worksheet(self, title):
        if title not in self._tabs:
            raise WSNotFound(title)
        return self._tabs[title]

    def batch_update(self, body):
        for req in body["requests"]:
            if "deleteSheet" in req:
                sid = req["deleteSheet"]["sheetId"]
                for t in list(self._tabs.values()):
                    if t.id == sid:
                        t.deleted = True
                        del self._tabs[t.title]
            elif "updateSheetProperties" in req:
                p = req["updateSheetProperties"]["properties"]
                sid, new_title = p["sheetId"], p["title"]
                for t in list(self._tabs.values()):
                    if t.id == sid:
                        del self._tabs[t.title]
                        t.title = new_title
                        self._tabs[new_title] = t


HDR = cw.WITNESS_HEADER if hasattr(cw, "WITNESS_HEADER") else ["seen_at_utc", "run_id"]
THRESH = cw.WITNESS_SHARD_THRESHOLD_CELLS


def build(live_cells, witness_present=True, ops_tabs=None):
    """A VA·Live workbook whose Sheet1 grid alone sums to ~live_cells, plus a VA·Ops (empty unless ops_tabs).
    Location is DERIVED from tab presence — there is no state-cell flag any more (audit #99)."""
    _BOOKS.clear()
    cols = 30
    sheet1 = FakeWS("Sheet1", max(1, live_cells // cols), cols)
    tabs = [sheet1]
    if witness_present:
        tabs.append(FakeWS("Schedule_Witness", 200000, len(HDR), HDR))
    live = FakeBook("LIVE", tabs)
    FakeBook("1X7wa4brFROP9Bn81Esf4z3zjlxTZvpKeUdPWpyBkD3c", ops_tabs or [])
    cw.OPS_WORKBOOK_ID = "1X7wa4brFROP9Bn81Esf4z3zjlxTZvpKeUdPWpyBkD3c"
    return live, sheet1


# 1. Already sharded — witness ABSENT from VA·Live, PRESENT in VA·Ops → location "ops", no work, no move.
live, s1 = build(THRESH * 2, witness_present=False,
                 ops_tabs=[FakeWS("Schedule_Witness", 200000, len(HDR), HDR)])
loc, did, rec = cw._autoshard_witness_if_full(live, "Schedule_Witness")
ok((loc, did, rec) == ("ops", False, 0), "already in VA·Ops → 'ops', no re-move, no FYI (even over threshold)")

# 2. Under threshold → witness stays in VA·Live, untouched.
live, s1 = build(THRESH // 2)
loc, did, rec = cw._autoshard_witness_if_full(live, "Schedule_Witness")
ok((loc, did) == ("live", False), "under threshold → no shard")
ok(not live.worksheet("Schedule_Witness").deleted, "witness NOT deleted under threshold")

# 3. Over threshold + witness present in VA·Live → copy, verify, delete-from-live.
live, s1 = build(THRESH + 100000, ops_tabs=[])
src = live.worksheet("Schedule_Witness")
loc, did, rec = cw._autoshard_witness_if_full(live, "Schedule_Witness")
ok(loc == "ops" and did, "over threshold + present → sharded")
ok(rec == 200000 * len(HDR), "reclaimed cells = witness grid size")
ok(src.deleted, "original witness deleted from VA·Live AFTER verify")
ok("Schedule_Witness" in {w.title for w in _BOOKS[cw.OPS_WORKBOOK_ID].worksheets()}, "witness now present in VA·Ops")

# 4. Over threshold but witness tab absent from BOTH books → direct future writes to VA·Ops, no copy, no crash.
live, s1 = build(THRESH + 1, witness_present=False)
loc, did, rec = cw._autoshard_witness_if_full(live, "Schedule_Witness")
ok((loc, did, rec) == ("ops", True, 0), "full + no witness tab anywhere → 'ops', nothing to copy")

# 4b. RECOVERY (audit #98/#99): a prior move landed the witness in VA·Ops (VA·Live now BELOW threshold since
# the move shrank it). Location is DERIVED from actual presence, NOT the threshold → 'ops', no re-move.
live, s1 = build(THRESH // 2, witness_present=False,
                 ops_tabs=[FakeWS("Schedule_Witness", 200000, len(HDR), HDR)])
loc, did, rec = cw._autoshard_witness_if_full(live, "Schedule_Witness")
ok((loc, did, rec) == ("ops", False, 0), "recovery: present in VA·Ops + below threshold → 'ops' from actual location")

# 5. FAIL-CLOSED: a verify mismatch must RAISE and NOT delete the original from VA·Live.
def _raise_verify(*a, **k):
    raise RuntimeError("dims mismatch — looks partial")


live, s1 = build(THRESH + 100000, ops_tabs=[])
src = live.worksheet("Schedule_Witness")
_orig_verify = cw._verify_sharded_tab
cw._verify_sharded_tab = _raise_verify
try:
    expect_raise(lambda: cw._autoshard_witness_if_full(live, "Schedule_Witness"), "verify failure must propagate")
    ok(not src.deleted, "FAIL-CLOSED: original NOT deleted when verify fails")
finally:
    cw._verify_sharded_tab = _orig_verify

# 6. _workbook_total_cells sums grids; None when unmeasurable.
live, s1 = build(THRESH)
ok(cw._workbook_total_cells(live) == sum(w.row_count * w.col_count for w in live.worksheets()),
   "_workbook_total_cells sums every tab")


class Boom:
    def worksheets(self):
        raise RuntimeError("cannot reach the API")


ok(cw._workbook_total_cells(Boom()) is None, "_workbook_total_cells → None when the workbook can't be measured")

print(f"ALL {_checks} witness-shard tests passed")
