"""Composition-break detection across sessions — queue items E2 + E3.

WHY THIS IS A CORRECTNESS REQUIREMENT, NOT A FEATURE:

A committee's record pooled across sessions silently averages over *different committees* — different
members, a different chair, sometimes a different majority. "Reported 96 of 214" spanning a chair change is
not one rate; it is two rates hidden inside an average, and the average can sit in a range **neither regime
ever occupied**. Rendering that as a single silent number is a Standard #7 violation: a metric whose
denominator conceals a partition.

The owner's instinct was a window switch. A switch alone is not enough — it makes the USER responsible for
remembering when control flipped. So detection is structural, from data we already ingest
(`roster.chair_of` / `roster.party_split`), and the UI is obliged to show the split whenever a break falls
inside the selected window.

DISPLAY CONTRACT (P25 — no text-per-signal): callers render ONE invariant sentence with substituted values.
There is no lookup table of situation → wording, and this module deliberately returns **structured fields,
never a formatted sentence**, so that stays true.

    Composition changed. Chair {a} → {b} · majority {p} {x}–{y} → {q} {m}–{n}.

The authorised window is 2025–2026 only ([[knowledge/lis_api_authorization]]); pre-2025 comparisons require
the legacylis CSV path and are NOT available through this module.
"""
from __future__ import annotations

from roster import chair_of, party_split


def _majority(counts: dict) -> tuple[str | None, int, int]:
    """(party, seats, total). Party is None when no side holds more than half.

    Unknown-party members are counted in the TOTAL but can never form a majority — an unknown is not
    evidence of a side, and quietly folding it into one would fabricate control.
    """
    total = sum(counts.values())
    if not total:
        return None, 0, 0
    known = {p: n for p, n in counts.items() if p and p != "?"}
    if not known:
        return None, 0, total
    party, seats = max(known.items(), key=lambda kv: kv[1])
    return (party if seats * 2 > total else None), seats, total


def committee_composition(fetcher, committee_id: int) -> dict:
    """One committee's composition for ONE session: chair + party split + derived majority."""
    members = fetcher.members()
    assignments = fetcher.roster_for(committee_id)
    chair = chair_of(assignments)
    counts = party_split(assignments, members)
    party, seats, total = _majority(counts)
    return {
        "committee_id": committee_id,
        "session_code": fetcher.session_code,
        "chair_member_number": (chair or {}).get("member_number"),
        "chair_name": (chair or {}).get("name"),
        "party_counts": dict(counts),
        "majority_party": party,
        "majority_seats": seats,
        "seats_total": total,
        "roster_size": len(assignments),
    }


def detect_break(a: dict, b: dict) -> dict:
    """Compare two single-session compositions. Returns structured fields only — never a sentence.

    `changed` is True when EITHER the chair or the majority party differs. Both matter and for different
    reasons: the chair decides whether a bill is heard at all; the majority decides whether it can be
    reported. A change in either makes a pooled rate a blend of two different regimes.

    An ABSENT chair (LIS lists none) is not treated as a change against another absent chair, but a
    present→absent transition IS reported, because that is a real difference in what we know.
    """
    chair_changed = a.get("chair_member_number") != b.get("chair_member_number")
    majority_changed = a.get("majority_party") != b.get("majority_party")
    return {
        "changed": bool(chair_changed or majority_changed),
        "chair_changed": chair_changed,
        "majority_changed": majority_changed,
        "from": {
            "session_code": a.get("session_code"),
            "chair_name": a.get("chair_name"),
            "majority_party": a.get("majority_party"),
            "majority_seats": a.get("majority_seats"),
            "seats_total": a.get("seats_total"),
        },
        "to": {
            "session_code": b.get("session_code"),
            "chair_name": b.get("chair_name"),
            "majority_party": b.get("majority_party"),
            "majority_seats": b.get("majority_seats"),
            "seats_total": b.get("seats_total"),
        },
    }


def scan(fetchers: dict, committee_ids) -> dict:
    """Detect breaks for many committees across an ORDERED set of sessions.

    `fetchers` maps session_code -> RosterFetcher. Sessions are compared in sorted order, consecutively.
    Returns {committee_id: {"compositions": [...], "breaks": [...]}}. A committee we cannot read is recorded
    with an explicit `error` rather than omitted — a missing committee must never look like a stable one.
    """
    codes = sorted(fetchers)
    out: dict = {}
    for cid in committee_ids:
        comps, errs = [], []
        for code in codes:
            try:
                comps.append(committee_composition(fetchers[code], cid))
            except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
                errs.append({"session_code": code, "error": repr(exc)[:200]})
        breaks = [
            detect_break(comps[i], comps[i + 1])
            for i in range(len(comps) - 1)
            if detect_break(comps[i], comps[i + 1])["changed"]
        ]
        out[cid] = {"compositions": comps, "breaks": breaks, "errors": errs}
    return out


# Only these members hold a seat. MEASURED 2026-07-27 and this is not cosmetic:
# `members()` returns everyone who SERVED in the session, not everyone SEATED. For 20261 that is
# 106 House / 42 Senate people against 100 / 40 actual seats -- the extras are `Outgoing` (6) and
# `Inactive` (2). Filtering to Active yields EXACTLY 100 and 40.
#
# Why it is a correctness bug and not a rounding detail: the majority test is `seats * 2 > total`. The
# 20251 House was D51-R49 -- a two-seat margin. Inflating `total` with departed members can push a real
# majority below the threshold and report NO majority where one exists, or shift which party leads.
SEATED_STATUSES = frozenset({"Active"})


def chamber_composition(fetcher, chamber_code: str, *, seated_only: bool = True) -> dict:
    """E3 — the CHAMBER's party split for one session. The control filter (V1) needs this, not just the
    committee split: a subject profile pools bills across many committees, so the meaningful regime for it
    is who controlled the chamber.

    `chamber_code` is "H" or "S". Members with no party are counted separately, never folded into a side.
    Non-seated members are counted in `served_not_seated` rather than dropped silently.
    """
    counts: dict = {}
    not_seated = 0
    for m in fetcher.members().values():
        if (m.get("chamber") or "").upper() != chamber_code.upper():
            continue
        if seated_only and (m.get("status") or "").strip() not in SEATED_STATUSES:
            not_seated += 1
            continue
        party = (m.get("party") or "").strip() or "?"
        counts[party] = counts.get(party, 0) + 1
    party, seats, total = _majority(counts)
    return {
        "chamber_code": chamber_code.upper(),
        "session_code": fetcher.session_code,
        "party_counts": counts,
        "majority_party": party,
        "majority_seats": seats,
        "seats_total": total,
        "served_not_seated": not_seated,
    }


def detect_chamber_break(a: dict, b: dict) -> dict:
    """Same contract as `detect_break` but chamber-scoped: only the majority can change (no chair)."""
    changed = a.get("majority_party") != b.get("majority_party")
    return {
        "changed": bool(changed),
        "chair_changed": False,
        "majority_changed": changed,
        "from": {k: a.get(k) for k in ("session_code", "majority_party", "majority_seats", "seats_total")},
        "to": {k: b.get(k) for k in ("session_code", "majority_party", "majority_seats", "seats_total")},
    }


def pooling_is_safe(scan_entry: dict) -> bool:
    """True when a figure may be pooled across the scanned window WITHOUT showing a split.

    Fail-closed: an entry carrying errors is NOT safe, because we cannot prove the composition held.
    """
    return not scan_entry.get("breaks") and not scan_entry.get("errors")
