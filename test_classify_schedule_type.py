"""Golden tests for structural_router.classify_schedule_type (PR-C8.1b).

Locks the ScheduleTypeID -> structural class mapping (LIS's own integer typing, no prose) —
the companion to classify_refid for api_schedule-origin rows. Run: python3 test_classify_schedule_type.py
"""
from structural_router import (
    classify_schedule_type, validate_schedule_types, SCHED_COMMITTEE, SCHED_FLOOR, SCHED_CAUCUS,
    SCHED_COMMISSION, SCHED_DOCKET, SCHED_OTHER,
)

CASES = [
    (1, SCHED_COMMITTEE), ("1", SCHED_COMMITTEE),
    (2, SCHED_FLOOR),
    (4, SCHED_CAUCUS),
    (5, SCHED_COMMISSION), ("5", SCHED_COMMISSION),
    (6, SCHED_DOCKET),
    (3, SCHED_OTHER),        # id 3 unused in 20261 -> surface, not mis-bucketed
    (99, SCHED_OTHER),       # a future/unknown id lands visible, never silently wrong
    ("", SCHED_OTHER), (None, SCHED_OTHER),
    # FLOAT ROBUSTNESS (mirrors classify_refid): a float-inferred id must still map.
    (5.0, SCHED_COMMISSION), ("5.0", SCHED_COMMISSION),
    (1.0, SCHED_COMMITTEE), ("6.0", SCHED_DOCKET),
]


def main():
    failures = []
    for sid, expected in CASES:
        got = classify_schedule_type(sid)
        if got != expected:
            failures.append((sid, got, expected))
        print(f"  [{'ok' if got==expected else 'FAIL'}] classify_schedule_type({sid!r}) -> {got}")
    # validate_schedule_types drift monitor (sustainability hardening 2026-06-28): the live id set is
    # checked against _SCHEDULE_TYPE_MAP; a NEW id (LIS adds one) must surface, today's ids must not.
    V_CASES = [
        ([1, 2, 4, 5, 6], []),                 # the full current map -> no drift
        (["1", "5.0", 6], []),                 # str + float-inference forms of known ids -> no drift
        ([1, 3, 7], ["3", "7"]),               # NEW ids 3 + 7 -> drift (sorted, normalized)
        (["", None, 2], []),                   # blank/None skipped (missing ≠ a new type)
        ([float("nan"), 1], []),               # real float NaN skipped (not str("nan")) — CodeRabbit #180
        (["nan", "<NA>", "none", "NA", 5], []),# NA-like string sentinels skipped, not flagged as new ids
        ([], []), (None, []),                  # empty/None input -> no drift, never raises
    ]
    for live, expected in V_CASES:
        got = validate_schedule_types(live)
        if got != expected:
            failures.append(("validate_schedule_types", live, got, expected))
        print(f"  [{'ok' if got==expected else 'FAIL'}] validate_schedule_types({live!r}) -> {got}")

    if failures:
        print(f"\n*** {len(failures)} FAILURE(S): {failures} ***")
        return 1
    print(f"\nAll {len(CASES)} classify + {len(V_CASES)} validate golden tests pass.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
