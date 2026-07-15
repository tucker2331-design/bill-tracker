#!/usr/bin/env python3
"""The Change Ledger differ — the pure, source-agnostic core (build-wave TASK 1 L1).

Answers "what changed since last cycle?" as a list of typed deltas with exact before → after. This module is
PURE (stdlib only, no I/O, no network) so it is exhaustively golden-testable now, independent of the live
wiring (which is 2027-in-season-gated — see docs/architecture/change_ledger.md). The live job feeds it two
consecutive snapshots; here we only define the diff.

STRUCTURAL IDENTITY (Standard #3 — key on ids, not prose):
  * a HISTORY action's identity is (bill, date, refid). LIS's `History_refid` is the vote/action's structural
    id, so a tally correction ("12-Y 9-N" → "12-Y 10-N") keeps the SAME key → we emit `history_edited`, not a
    spurious remove+add. When refid is EMPTY (some admin rows), identity falls back to (bill, date, action) —
    which structurally CANNOT distinguish an edit from a remove+add, so such a change honestly surfaces as a
    remove + an add, never a guessed "edit" (honest-absent beats plausible-wrong).
  * a MEETING's identity is (date, committee); a time/status change on the same key is an edit of that meeting.
  * a DOCKET's identity is (date, committee) → the set of bills on it; membership changes are add/remove.

KIND vocabulary is CLOSED (the ledger never paraphrases LIS prose — it QUOTES old→new verbatim):
"""
from __future__ import annotations

# The closed kind set. `unclassified_change` is the differ's honest fallback for a change it detected but
# could not type — it must ALWAYS carry the raw old→new so the UI shows a generic-but-true row + the caller
# fires a drift canary. The frontend maps each kind to ONE sentence template (docs/design register pattern).
KINDS = (
    "history_added", "history_edited", "history_removed",
    "schedule_time_moved", "schedule_cancelled",
    "docket_added", "docket_removed",
    "unclassified_change",
)


def _delta(kind, *, bill="", committee="", date="", refid="", old="", new=""):
    assert kind in KINDS, f"unknown ledger kind: {kind}"   # a typo here is a bug, not runtime data
    return {"kind": kind, "bill": bill, "committee": committee, "date": date,
            "refid": refid, "old": old, "new": new}


# ── History rows ──────────────────────────────────────────────────────────────────────────────────────
# A history row is a mapping with keys: bill, date, refid, action. Extra keys are ignored (source-agnostic).
def _hist_key(row):
    bill = str(row.get("bill", "")).strip()
    date = str(row.get("date", "")).strip()
    refid = str(row.get("refid", "")).strip()
    # refid present → structural identity independent of the action TEXT (so a tally EDIT is detectable).
    # refid absent → identity must include the action, so a text change reads as remove+add (honest — no
    # stable id means we cannot truthfully call it an edit).
    return (bill, date, "refid", refid) if refid else (bill, date, "action", str(row.get("action", "")).strip())


def diff_history(prev, curr):
    """prev/curr: iterables of history-row dicts {bill,date,refid,action}. → deltas (added/edited/removed)."""
    def _index(rows):
        m = {}
        for r in rows:                        # last-writer-wins: identical keys are the same action
            m[_hist_key(r)] = {"action": str(r.get("action", "")).strip(),
                               "bill": str(r.get("bill", "")).strip(),
                               "date": str(r.get("date", "")).strip(),
                               "refid": str(r.get("refid", "")).strip()}
        return m

    pmap, cmap = _index(prev), _index(curr)
    out = []
    for key, c in cmap.items():
        p = pmap.get(key)
        if p is None:
            out.append(_delta("history_added", bill=c["bill"], date=c["date"], refid=c["refid"], new=c["action"]))
        elif p["action"] != c["action"]:
            out.append(_delta("history_edited", bill=c["bill"], date=c["date"], refid=c["refid"],
                              old=p["action"], new=c["action"]))
    for key, p in pmap.items():
        if key not in cmap:
            out.append(_delta("history_removed", bill=p["bill"], date=p["date"], refid=p["refid"], old=p["action"]))
    # deterministic order so a cycle's ledger is stable/reproducible (testable).
    return sorted(out, key=lambda d: (d["bill"], d["date"], d["kind"], d["new"], d["old"]))


# ── Meetings (schedule) ───────────────────────────────────────────────────────────────────────────────
# A meeting is a mapping: date, committee, time, status. Identity (date, committee).
def _mtg_key(m):
    return (str(m.get("date", "")).strip(), str(m.get("committee", "")).strip())


def diff_schedule(prev, curr):
    """Time moves + cancellations on the SAME meeting (identity = date+committee)."""
    pmap = {_mtg_key(m): m for m in prev}
    out = []
    for m in curr:
        key = _mtg_key(m)
        p = pmap.get(key)
        if p is None:
            continue  # a brand-new meeting is a docket/schedule ADD — surfaced via diff_docket / the witness,
                      # not here; this function reports CHANGES to a meeting we already knew.
        date, committee = key
        p_status = str(p.get("status", "")).strip().upper()
        c_status = str(m.get("status", "")).strip().upper()
        if c_status == "CANCELLED" and p_status != "CANCELLED":
            out.append(_delta("schedule_cancelled", committee=committee, date=date,
                              old=str(p.get("time", "")).strip()))
            continue
        p_time = str(p.get("time", "")).strip()
        c_time = str(m.get("time", "")).strip()
        if p_time != c_time:
            out.append(_delta("schedule_time_moved", committee=committee, date=date, old=p_time, new=c_time))
    return sorted(out, key=lambda d: (d["date"], d["committee"], d["kind"]))


# ── Dockets (which bills are on a meeting) ──────────────────────────────────────────────────────────────
# A docket is a mapping (date, committee) -> iterable of bill ids.
def diff_docket(prev, curr):
    """Bills added to / removed from a meeting's agenda. prev/curr: {(date,committee): [bills]}."""
    out = []
    keys = set(prev) | set(curr)
    for key in keys:
        date, committee = key
        pb = {str(b).strip() for b in prev.get(key, [])}
        cb = {str(b).strip() for b in curr.get(key, [])}
        for b in sorted(cb - pb):
            out.append(_delta("docket_added", bill=b, committee=committee, date=date))
        for b in sorted(pb - cb):
            out.append(_delta("docket_removed", bill=b, committee=committee, date=date))
    return sorted(out, key=lambda d: (d["date"], d["committee"], d["bill"], d["kind"]))
