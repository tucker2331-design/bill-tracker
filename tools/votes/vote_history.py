"""Per-member vote history from VOTE.CSV — queue item E1.

WHY THIS EXISTS: the call sheet and every entity profile need "how did this member vote on bills carrying
subject X". The data is ALREADY in a blob the calendar worker downloads every cycle, so this costs **zero
additional LIS requests** (docs/architecture/roster_and_votes_ingestion.md W5). This module is a re-parse,
not a new dependency.

TWO TRAPS, BOTH MEASURED (2026-07-27, session 20261) RATHER THAN ASSUMED:

1. **The file is RAGGED.** Row widths observed: 1, 31, 45, 81, 199, 201, … pandas/`safe_fetch_csv` mangles it
   to zero usable ids. It MUST be read with `csv.reader` over raw bytes. This is recorded in the worker's own
   comments and is re-asserted here because the failure is silent.

2. **2,046 of 11,175 roll calls carry NO per-member detail, and that is mostly CORRECT, not missing data.**
   The bulk are `VSV*` ids (1,341 rows, only 96 with members) — a vote with no recorded roll call has no
   per-member record *by nature*. Treating that as a parse failure would manufacture a bug; treating it as
   silently equal to "no votes" would understate a member's record. So every row that yields no pairs is
   COUNTED AND CATEGORISED by id shape (Standard #4), never dropped.

Measured baseline for 20261 — assert against this to catch upstream drift:
  11,175 rows · 9,129 with per-member detail · 318,264 member votes · 147 distinct members
  no-member-detail by shape: voice_or_standing 1,245 · chamber_committee 636 · other 155 · committee_id_only 10
  vote tokens: Y N X A  (X = not voting / abstain; A observed rarely). Unknown tokens: 0. Unpaired cells: 0.

ROSTER RECONCILIATION (2026-07-27): 148 roster members vs 147 distinct voters. **Exactly one member
(`H0368`) cast no vote, and zero voters are absent from the roster** — so the MemberNumber join is clean in
the direction that matters (no orphan votes we cannot attribute). A member with no votes is a real fact
(seated late, resigned, etc.), not a parse failure; `record_for()` returns an empty Counter and the caller's
denominator stays honest.
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter, defaultdict

VOTE_CSV_URL = "https://lis.blob.core.windows.net/lisfiles/{session}/VOTE.CSV"

# The controlled vocabulary observed in the file. An unseen token is an ALERT, never a silent skip:
# a new code (say a 'P' for present) silently dropped would quietly bias every member's record.
KNOWN_VOTE_TOKENS = frozenset({"Y", "N", "X", "A"})

# Vote-id shapes, used to CATEGORISE rows that carry no member pairs so the miss is explainable.
_ID_SHAPES = (
    ("committee_id_only", re.compile(r"^C\d+V\d+$")),      # committee vote, id only
    ("chamber_committee", re.compile(r"^[HS]\d+V\d+$")),   # chamber committee roll call
    ("floor", re.compile(r"^\d{8}$")),                     # floor roll call
    ("voice_or_standing", re.compile(r"^VSV")),            # no roll call recorded by nature
)


def id_shape(vote_id: str) -> str:
    v = (vote_id or "").strip()
    for name, rx in _ID_SHAPES:
        if rx.match(v):
            return name
    return "other"


class VoteHistory:
    """Parsed per-member roll calls.

    `parse()` never raises on a malformed row and never silently discards one — every row lands in exactly
    one of: `member_votes` (produced pairs) or `stats["no_member_detail"][shape]` (explained miss).
    """

    def __init__(self, session_code: str, http_get):
        self.session_code = str(session_code)
        self._http_get = http_get
        self.member_votes: dict[str, dict[str, str]] = {}      # vote_id -> {member_number: token}
        self.by_member: dict[str, dict[str, str]] = defaultdict(dict)  # member_number -> {vote_id: token}
        self.unknown_tokens: Counter = Counter()
        self.stats: dict = {
            "rows": 0,
            "rows_with_members": 0,
            "member_votes": 0,
            "no_member_detail": Counter(),
            "ragged_widths": Counter(),
            "unpaired_cells": 0,
        }

    # -- fetch -------------------------------------------------------------------------------------
    def fetch_raw(self) -> bytes:
        """Raw bytes. Deliberately NOT a DataFrame — see trap 1 in the module docstring."""
        url = VOTE_CSV_URL.format(session=self.session_code)
        resp = self._http_get(url)
        status = getattr(resp, "status_code", 200)
        if status != 200:
            raise RuntimeError(f"VOTE.CSV fetch failed: HTTP {status} for {url}")
        return resp.content if hasattr(resp, "content") else resp

    # -- parse -------------------------------------------------------------------------------------
    def parse(self, raw: bytes) -> "VoteHistory":
        text = raw.decode("utf-8-sig", "replace")
        for row in csv.reader(io.StringIO(text)):
            if not row or not row[0].strip():
                continue
            self.stats["rows"] += 1
            self.stats["ragged_widths"][len(row)] += 1
            vote_id = row[0].strip()

            pairs: dict[str, str] = {}
            # Cells after the id are (member_number, token) repeating. Walk in twos and require BOTH.
            i = 1
            while i < len(row):
                member = row[i].strip()
                token = row[i + 1].strip() if i + 1 < len(row) else ""
                if member and token:
                    if token not in KNOWN_VOTE_TOKENS:
                        # Surface, never flatten (Standard #4). Still recorded so the denominator is honest.
                        self.unknown_tokens[token] += 1
                    pairs[member] = token
                elif member or token:
                    # A half-pair means the row is shaped differently than we believe. Count it; do not guess.
                    self.stats["unpaired_cells"] += 1
                i += 2

            if pairs:
                self.stats["rows_with_members"] += 1
                self.stats["member_votes"] += len(pairs)
                self.member_votes[vote_id] = pairs
                for m, t in pairs.items():
                    self.by_member[m][vote_id] = t
            else:
                # NOT an error. A voice/standing vote has no roll call by nature -- but it must be
                # explainable, so it is bucketed by id shape rather than dropped.
                self.stats["no_member_detail"][id_shape(vote_id)] += 1
        return self

    # -- query -------------------------------------------------------------------------------------
    def record_for(self, member_number: str, vote_ids=None) -> Counter:
        """Token counts for a member, optionally restricted to a set of vote_ids (e.g. one subject's bills).

        Returns a Counter of Y/N/X/A. The CALLER decides the denominator -- this never invents one, because
        'of what?' is the question Standard #7 exists to force.
        """
        votes = self.by_member.get(member_number, {})
        if vote_ids is not None:
            wanted = set(vote_ids)
            votes = {k: v for k, v in votes.items() if k in wanted}
        return Counter(votes.values())

    def agreement(self, member_number: str, positions: dict[str, str]) -> tuple[int, int]:
        """'Voted with us k of n'. `positions` maps vote_id -> the token we wanted ('Y'/'N').

        Only votes the member actually cast AND we took a side on count toward n -- an absence is not a
        disagreement, and a bill we had no position on is not evidence either way.
        """
        member = self.by_member.get(member_number, {})
        n = k = 0
        for vote_id, wanted in positions.items():
            got = member.get(vote_id)
            if got is None or got not in ("Y", "N"):
                continue
            n += 1
            if got == wanted:
                k += 1
        return k, n

    # -- integrity ---------------------------------------------------------------------------------
    def health(self) -> dict:
        """Everything a caller needs to decide whether to trust this parse. No hidden denominators."""
        s = self.stats
        return {
            "rows": s["rows"],
            "rows_with_members": s["rows_with_members"],
            "rows_without_member_detail": s["rows"] - s["rows_with_members"],
            "member_votes": s["member_votes"],
            "distinct_members": len(self.by_member),
            "no_member_detail_by_shape": dict(s["no_member_detail"]),
            "unknown_vote_tokens": dict(self.unknown_tokens),
            "unpaired_cells": s["unpaired_cells"],
            "distinct_row_widths": len(s["ragged_widths"]),
        }
