"""Golden tests for structural_router.classify_schedule_type (PR-C8.1b).

Locks the ScheduleTypeID -> structural class mapping (LIS's own integer typing, no prose) —
the companion to classify_refid for api_schedule-origin rows. Run: python3 test_classify_schedule_type.py
"""
from structural_router import (
    classify_schedule_type, SCHED_COMMITTEE, SCHED_FLOOR, SCHED_CAUCUS,
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
    if failures:
        print(f"\n*** {len(failures)} FAILURE(S): {failures} ***")
        return 1
    print(f"\nAll {len(CASES)} golden tests pass.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
