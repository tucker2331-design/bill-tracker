"""Unit tests for the §9 ANCHOR LADDER in `_resolve_one_day` (calendar_chain_ordering §9).

Every fixture below is transcribed from REAL Sheet1/Schedule rows that shipped as `relative_unresolved`
(measured 2026-07-09: 19 meetings / 370 bill-rows). This is a Section-9-critical path — the resolved
SortTime times bill ACTIONS — so the tests assert BOTH that the residual now resolves AND, crucially,
that the new rungs are strictly additive: a row an existing rung already resolved must not move.

Pure: no network, no gspread. Runnable with plain python3, like cadence_test.py / witness_shard_test.py.
"""
import calendar_worker as cw

_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


def row(owner, sched_time="", desc=""):
    return {"OwnerName": owner, "ScheduleTime": sched_time, "Description": desc}


def unresolved(r, key):
    """A relative node the resolver REFUSED to place is left OUT of the map (resolve_node returns the
    06:00 sentinel without recording it); the caller then falls back to the unresolved default. So
    'refused' means absent-or-sentinel — assert that, not a specific string."""
    return r.get(key) in (None, "06:00", "23:59")


# ── Class A: phrase names NO body → anchor to the meeting's OWN chamber ──────────────────────────
# Real: 2026-01-21 "Senate adjourned"@1:26 PM; Senate General Laws and Technology = "30 minutes after
# adjournment" → 13:56.
day = [
    row("Senate Convenes", "12:00 PM"),
    row("Senate adjourned", "1:26 PM"),
    row("Senate General Laws and Technology", "30 minutes after adjournment (View Meeting)"),
]
r = cw._resolve_one_day(day)
ok(r["senate adjourned"] == "13:26", f"A: floor anchor keeps its published clock -> {r['senate adjourned']}")
ok(r["senate general laws and technology"] == "13:56",
   f"A: bare 'after adjournment' anchors to OWN chamber +30 -> {r['senate general laws and technology']}")

# Class A, recess verb: real 2026-02-06 "Senate recessed until 1:10 p.m."@12:40 PM; "Upon Recess" → 12:41.
# (Zero-offset children take the pre-existing +1 chain epsilon so they sort strictly AFTER their anchor
# rather than tying with it and falling to the alphabetical secondary sort. Ordering only — the DISPLAYED
# time stays LIS's verbatim "Upon Recess".) The point of this case is WHICH marker is chosen.
day = [
    row("Senate Convenes", "11:30 AM"),
    row("Senate recessed until 1:10 p.m.", "12:40 PM"),
    row("Senate adjourned", "1:56 PM"),
    row("Senate Finance and Appropriations", "Upon Recess (View Meeting)"),
]
r = cw._resolve_one_day(day)
ok(r["senate finance and appropriations"] == "12:41",
   f"A: 'Upon Recess' picks the RECESS marker (12:40+eps), not the 13:56 adjournment -> {r['senate finance and appropriations']}")

# The verb selects the marker: "30 Minutes after Recess" -> recess+30 (real 2026-01-14, recess @2:10 PM).
day = [
    row("Senate recessed until 2:40 p.m.", "2:10 PM"),
    row("Senate adjourned", "7:55 PM"),
    row("Senate Privileges and Elections", "30 Minutes after Recess (View Meeting)"),
]
r = cw._resolve_one_day(day)
ok(r["senate privileges and elections"] == "14:40",
   f"A: recess verb -> recess anchor +30 (not the 19:55 adjournment) -> {r['senate privileges and elections']}")

# No cross-verb substitution: an adjournment phrase with NO adjourned marker published stays unresolved
# rather than silently borrowing the recess clock (they are different events).
day = [
    row("Senate recessed until 2:40 p.m.", "2:10 PM"),
    row("Senate Privileges and Elections", "30 minutes after adjournment"),
]
r = cw._resolve_one_day(day)
ok(unresolved(r, "senate privileges and elections"),
   f"A: missing adjourned marker -> stays unresolved, no recess substitution -> {r.get('senate privileges and elections')}")


# ── Class B: "full committee" self-reference → the node's OWN parent (from Parent-Sub name) ───────
# Real 2026-01-28: Senate adjourned@12:43 -> GL&T = 13:13 -> Housing "upon adjournment of full committee".
day = [
    row("Senate adjourned", "12:43 PM"),
    row("Senate General Laws and Technology", "30 minutes after adjournment (View Meeting)"),
    row("Senate General Laws and Technology-Housing", "Upon adjournment of full committee (View Meeting)"),
]
r = cw._resolve_one_day(day)
ok(r["senate general laws and technology"] == "13:13", f"B: parent via chamber rung -> {r['senate general laws and technology']}")
ok(r["senate general laws and technology-housing"] == "13:14",
   f"B: 'full committee' anchors to OWN parent (+1 chain epsilon) -> {r['senate general laws and technology-housing']}")
ok(r["senate general laws and technology-housing"] > r["senate general laws and technology"],
   "B: child sorts strictly AFTER its parent (transitive A->B)")

# A "full committee" whose parent isn't a real node that day must NOT invent an anchor.
day = [
    row("Senate adjourned", "12:43 PM"),
    row("Senate General Laws and Technology-Housing", "Upon adjournment of full committee"),
]
r = cw._resolve_one_day(day)
ok(unresolved(r, "senate general laws and technology-housing"),
   "B: no parent node published -> refuses (stays unresolved), never invents")


# ── Class C: sibling near-miss — the reference carries a token the node lacks ─────────────────────
# Real 2026-01-30 House Appropriations chain. Note the reference says "GENERAL Government and Capital
# Outlay Subcommittee" while the real node is "Government and Capital Outlay" -> strict subset fails.
# "house general laws" is present so "general" IS in the day vocabulary (that's what broke the subset).
day = [
    row("House Convenes", "11:00 AM"),
    row("House adjourned", "11:00 AM"),
    row("House General Laws", "9:00 AM"),
    row("House Appropriations", "15 minutes after adjournment of the House"),
    row("House Appropriations - Government and Capital Outlay", "1/2 hour after adjournment of House Appropriations"),
    row("House Appropriations - Elementary and Secondary Education", "",
        "Immediately after General Government and Capital Outlay Subcommittee"),
    row("House Appropriations - Health & Human Resources", "",
        "Immediately after adjournment of the Elementary and Secondary Education Subcommittee"),
]
r = cw._resolve_one_day(day)
ok(r["house appropriations"] == "11:15", f"C: base of the chain unchanged -> {r['house appropriations']}")
ok(r["house appropriations - government and capital outlay"] == "11:45",
   f"C: existing rung still resolves (unmoved) -> {r['house appropriations - government and capital outlay']}")
elem = r["house appropriations - elementary and secondary education"]
hhr = r["house appropriations - health & human resources"]
ok(elem == "11:46", f"C: sibling near-miss ('GENERAL ...') resolves via overlap rung -> {elem}")
ok(hhr == "11:47", f"C: next link resolves transitively off it -> {hhr}")
ok("11:45" < elem < hhr, "C: chain strictly ordered GG&CO -> Elementary -> Health & Human")

# Ambiguity REFUSES: two siblings tie on overlap -> stay unresolved rather than mis-anchor.
# ("House General Laws" puts "general" in the day vocabulary, so the reference is NOT a strict subset of
# either sibling — that is what drops it past _committee_parent and into the overlap rung under test.)
day = [
    row("House adjourned", "11:00 AM"),
    row("House General Laws", "9:00 AM"),
    row("House Appropriations", "15 minutes after adjournment of the House"),
    row("House Appropriations - Capital Outlay Alpha", "9:00 AM"),
    row("House Appropriations - Capital Outlay Beta", "9:00 AM"),
    row("House Appropriations - Chaser", "", "Immediately after General Capital Outlay Subcommittee"),
]
r = cw._resolve_one_day(day)
ok(unresolved(r, "house appropriations - chaser"),
   f"C: tied sibling overlap -> refuses to guess -> {r.get('house appropriations - chaser')}")

# A phrase that NAMES a body nobody matched must never fall through to the chamber floor — anchoring it to
# an adjournment hours away is the assumptions_audit #70 mis-anchor class. Refusal is the only safe answer.
day = [
    row("Senate adjourned", "6:12 PM"),
    row("Senate Rules", "Upon adjournment of the Committee on Nothing At All"),
]
r = cw._resolve_one_day(day)
ok(unresolved(r, "senate rules"),
   f"C: named-but-unmatched body never falls through to the floor -> {r.get('senate rules')}")


# ── §9d: _committee_parent — MULTISET containment, and a tie REFUSES ─────────────────────────────
# Real 2025-01-29. LIS names a subcommittee by REPEATING the distinctive word, so the reference's token
# SET is identical to the parent committee's. Only the multiset ("agriculture" twice) tells them apart.
day = [
    row("House adjourned", "11:00 AM"),
    row("House Agriculture, Chesapeake and Natural Resources", "9:00 AM"),
    row("House Agriculture, Chesapeake and Natural Resources-Agriculture", "10:00 AM"),
    row("House Agriculture, Chesapeake and Natural Resources-Natural Resources", "10:30 AM"),
    row("House Agriculture, Chesapeake and Natural Resources-Chesapeake", "",
        "Immediately upon adjournment of the House Agriculture, Chesapeake and Natural Resources Agriculture Subcommittee"),
]
r = cw._resolve_one_day(day)
ok(r["house agriculture, chesapeake and natural resources-chesapeake"] == "10:01",
   "9d: repeated token anchors to the SUBcommittee (10:00+eps), not its token-set-identical parent -> "
   f"{r['house agriculture, chesapeake and natural resources-chesapeake']}")

# Real 2026-01-22. "Subcommittee #2" reduces to the bare ordinal {2} — which fits ANOTHER committee's
# Subcommittee #2 equally well. It is a SELF-LINEAGE reference: scope it to the referring node's committee.
day = [
    row("House adjourned", "11:00 AM"),
    row("House Labor and Commerce-Subcommittee #2", "9:00 AM"),
    row("House Public Safety-Subcommittee #2", "8:00 AM"),
    row("House Labor and Commerce-Subcommittee #3", "", "Immediately upon adjournment of Subcommittee #2"),
]
r = cw._resolve_one_day(day)
ok(r["house labor and commerce-subcommittee #3"] == "09:01",
   f"9d: bare ordinal scopes to the node's OWN lineage, not another committee's #2 -> "
   f"{r['house labor and commerce-subcommittee #3']}")

# ...and when lineage CANNOT disambiguate, refuse. (Alphabetical order is a coin flip in a determinism
# costume: it would silently hand this to House Labor because "labor" < "public".)
day = [
    row("House adjourned", "11:00 AM"),
    row("House Labor and Commerce-Subcommittee #2", "9:00 AM"),
    row("House Public Safety-Subcommittee #2", "8:00 AM"),
    row("Senate Rules", "", "Immediately upon adjournment of Subcommittee #2"),
]
r = cw._resolve_one_day(day)
ok(unresolved(r, "senate rules"),
   f"9d: ambiguous ordinal with no shared lineage -> refuses -> {r.get('senate rules')}")


# ── SAFETY (the Section-9 gate): the new rungs are strictly ADDITIVE ──────────────────────────────
# A published concrete clock is never re-derived, and a row an EXISTING rung resolves is unchanged.
day = [
    row("House adjourned", "11:00 AM"),
    row("House Appropriations", "15 minutes after adjournment of the House"),   # existing rung (named body)
    row("Senate Courts of Justice", "2:00 PM"),                                  # concrete, published
]
r = cw._resolve_one_day(day)
ok(r["senate courts of justice"] == "14:00", "SAFETY: published clock untouched")
ok(r["house appropriations"] == "11:15", "SAFETY: row resolved by an EXISTING rung is unmoved")

# Telemetry: each rung is counted, and the unresolved rung is the one to watch.
cw.ANCHOR_RUNG_COUNTS.clear()
cw._resolve_one_day([
    row("Senate adjourned", "12:43 PM"),
    row("Senate General Laws and Technology", "30 minutes after adjournment"),            # chamber rung
    row("Senate General Laws and Technology-Housing", "Upon adjournment of full committee"),  # parent rung
    row("Senate Rules", "Immediately after the Committee on Nothing At All"),             # unresolved
])
c = cw.ANCHOR_RUNG_COUNTS
ok(c.get("anchor_chamber") == 1, f"telemetry: chamber rung counted -> {c}")
ok(c.get("anchor_parent") == 1, f"telemetry: parent rung counted -> {c}")
ok(c.get("anchor_unresolved", 0) >= 1, f"telemetry: unresolved counted (the drift canary) -> {c}")

# The canary counts unplaceable MEETINGS. A relative "House Convenes" also spawns the synthetic "house" /
# "the house" lookup aliases, and a refused node is never memoized (so resolve_node re-walks it). Both would
# inflate one unplaceable meeting into three. Real row: 2025-02-22, pointing at a PRIOR session's recess.
cw.ANCHOR_RUNG_COUNTS.clear()
cw._resolve_one_day([row("House Convenes", "", "15 minutes after the Recess of the 2024 Special Session I")])
ok(cw.ANCHOR_RUNG_COUNTS.get("anchor_unresolved") == 1,
   f"telemetry: one unplaceable meeting counts ONCE, not once per alias/call -> {dict(cw.ANCHOR_RUNG_COUNTS)}")

print(f"ALL {_checks} anchor-ladder tests passed")
