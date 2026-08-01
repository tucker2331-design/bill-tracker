"""Archive registry — where each archived session actually lives.

An archive that "lasts forever" is a CHAIN of workbooks, and a chain is only usable if something records
which workbook holds which session. Without that, ``Session_20261`` is in book A and ``Session_20351`` is
in book D and nothing can find either. The registry is that record, and it is the load-bearing piece — the
workbook CREATION is one API call.

SCHEMA (a tab named ``Archive_Registry``, in the VA·Ops workbook — see WHY OPS below)
    Jurisdiction | SessionCode | WorkbookId | WorkbookTitle | ArchivedUTC | Rows | Cols

``Jurisdiction`` is first and is NOT decoration: Standard #6 says no logic may assume Virginia. NY is
already a live second state with its own brain, and it will archive too. Keying on (jurisdiction, session)
means one registry serves every state and the roller never needs a per-state code path.

WHY THE REGISTRY LIVES IN VA·Ops, NOT IN AN ARCHIVE WORKBOOK
------------------------------------------------------------
It cannot live in the archive workbooks it indexes: those are the things that fill up and get replaced, so
the index would roll away with them and the chain would lose its head. Ops is the stable, near-empty
workbook that already exists for exactly this class of small operational state (it is the A-2 witness shard
target).

FAIL-CLOSED CONTRACT
--------------------
Every resolution failure returns None or raises — never a default workbook id. A silent fallback would
write session N+1 on top of a full workbook, or worse, into the WRONG workbook where it would be
invisible to every reader. `resolve_active` returning None means "I do not know", and the caller must stop.

ORDERING: a registry row is written only AFTER `_copy_tab` has verified the snapshot landed intact. The row
is the assertion "this session is safely archived HERE", so writing it first would let a failed copy leave
a pointer to a tab that does not exist — and every later reader would trust it (confirm-before-advance).
"""
from __future__ import annotations

import datetime

REGISTRY_TAB = "Archive_Registry"
REGISTRY_HEADER = ["Jurisdiction", "SessionCode", "WorkbookId", "WorkbookTitle",
                   "ArchivedUTC", "Rows", "Cols"]

# The workbook the chain STARTS from, for a jurisdiction whose registry has no rows yet. This is a genesis
# value, not a fallback: it is used ONLY to seed an empty registry, and once any row exists the registry is
# the sole authority. Distinguishing those two cases is the whole point — a fallback that applies whenever
# a lookup fails is how a full workbook gets written to anyway.
GENESIS_ARCHIVE = {
    "VA": ("1AA-dCUDAPvq59Hv01DqteEquBJ1kkqI0QR5ECd10QeA", "VA · Archive"),
}


class RegistryError(RuntimeError):
    """Raised when the registry cannot answer. Never swallowed into a default."""


def parse_rows(values):
    """Rows-of-cells (as gspread returns) -> list of dicts. Header-driven, so a column added later does not
    shift the read (the positional-index bug class that moved the completeness cell three times).

    A row missing the required identity fields is SKIPPED AND COUNTED, never silently dropped: the count
    comes back so the caller can alert (Standard #4).
    """
    if not values:
        return [], 0
    header = [str(h).strip() for h in values[0]]
    idx = {name: header.index(name) for name in REGISTRY_HEADER if name in header}
    missing_cols = [c for c in ("Jurisdiction", "SessionCode", "WorkbookId") if c not in idx]
    if missing_cols:
        raise RegistryError(f"{REGISTRY_TAB} is missing required column(s): {', '.join(missing_cols)}")
    out, malformed = [], 0
    for raw in values[1:]:
        if not any(str(c).strip() for c in raw):
            continue
        rec = {name: (str(raw[i]).strip() if i < len(raw) else "") for name, i in idx.items()}
        if not (rec.get("Jurisdiction") and rec.get("SessionCode") and rec.get("WorkbookId")):
            malformed += 1
            continue
        out.append(rec)
    return out, malformed


def resolve_active(records, jurisdiction):
    """The workbook the LAST archive for this jurisdiction went into, or None if there is none.

    'Active' is the most recently archived, ordered by ArchivedUTC then SessionCode — never 'the last row',
    because row order in a sheet is not a guarantee anyone maintains.
    """
    mine = [r for r in records if r.get("Jurisdiction", "").upper() == jurisdiction.upper()]
    if not mine:
        return None
    newest = max(mine, key=lambda r: (r.get("ArchivedUTC", ""), r.get("SessionCode", "")))
    return newest.get("WorkbookId") or None


def find_session(records, jurisdiction, session_code):
    """Which workbook holds a given archived session? None when unknown."""
    for r in records:
        if (r.get("Jurisdiction", "").upper() == jurisdiction.upper()
                and r.get("SessionCode", "") == str(session_code)):
            return r.get("WorkbookId") or None
    return None


def already_archived(records, jurisdiction, session_code):
    """Idempotence: snapshotting a session twice must not create a second registry row."""
    return find_session(records, jurisdiction, session_code) is not None


def next_title(records, jurisdiction, base_title):
    """Title for the NEXT workbook in the chain: 'VA · Archive 2', 'VA · Archive 3', …

    Derived from how many DISTINCT workbooks the jurisdiction already has, so it stays correct even if a
    session is archived out of order or a row is re-written.
    """
    books = {r.get("WorkbookId") for r in records
             if r.get("Jurisdiction", "").upper() == jurisdiction.upper() and r.get("WorkbookId")}
    return base_title if not books else f"{base_title} {len(books) + 1}"


def new_row(jurisdiction, session_code, workbook_id, workbook_title, rows, cols, now=None):
    """One registry row, in REGISTRY_HEADER order."""
    ts = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [jurisdiction.upper(), str(session_code), workbook_id, workbook_title, ts, int(rows), int(cols)]
