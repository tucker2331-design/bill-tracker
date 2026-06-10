"""Golden tests for structural_router.classify_refid (PR-C8.1).

Locks the refid-identity classification of HISTORY rows — the text-free replacement for the
blank-route text patterns. Run: python3 test_classify_refid.py  (exit 0 = all pass).
Spec + measured namespace: docs/architecture/pr_c8_structural_classification.md,
docs/knowledge/history_refid_namespace.md.
"""
from structural_router import (
    classify_refid, REFID_VOTE_COMMITTEE, REFID_VOTE_FLOOR, REFID_BATCH_NOTICE,
    REFID_SINGLETON_DOC, REFID_COMMITTEE_REF, REFID_UNKNOWN, REFID_EMPTY,
)

CASES = [
    # (refid, fanout, in_vote_csv) -> expected class
    (("H14V2610034", 0, False), REFID_VOTE_COMMITTEE),    # committee vote record (V-grammar) is
                                                          # meeting evidence even though it never
                                                          # appears in VOTE.CSV (floor-only file)
    (("H14003V2610048", 0, False), REFID_VOTE_COMMITTEE), # subcommittee vote refid
    (("S2V1869", 0, False), REFID_VOTE_COMMITTEE),        # 1-digit committee vote refid
    (("26110000", 0, True), REFID_VOTE_FLOOR),            # floor roll-call (joins VOTE.CSV)
    (("5354", 63, False), REFID_BATCH_NOTICE),            # agenda-notice batch -> admin
    (("001", 112, False), REFID_BATCH_NOTICE),            # subcommittee-assignment batch -> admin
    (("5141", 1, False), REFID_SINGLETON_DOC),            # singleton clerk doc -> surface
    (("5141", 2, False), REFID_BATCH_NOTICE),             # K=2 boundary: fan-out 2 is a batch
    (("H14", 0, False), REFID_COMMITTEE_REF),             # committee code -> referral/admin
    (("S04", 0, False), REFID_COMMITTEE_REF),
    (("", 0, False), REFID_EMPTY),
    (("   ", 0, False), REFID_EMPTY),                     # whitespace-only -> empty
    (("WEIRD-XYZ", 0, False), REFID_UNKNOWN),
    # SAFETY INVARIANT: a numeric refid that DID join VOTE.CSV must never be BATCH, regardless
    # of fan-out — vote evidence outranks the batch law (chain rule 4 before rule 5).
    (("5354", 63, True), REFID_VOTE_FLOOR),
    # FLOAT ROBUSTNESS: pandas may infer the refid column as float64. classify_refid must
    # normalize these itself, not misclassify them as UNKNOWN (Gemini PR-C8.1 review).
    ((26110000.0, 0, True), REFID_VOTE_FLOOR),     # float refid joining VOTE.CSV
    (("5141.0", 2, False), REFID_BATCH_NOTICE),    # stringified-float artifact "5141.0"
    ((5141.0, 1, False), REFID_SINGLETON_DOC),     # bare float, fan-out < K
    ((float("nan"), 0, False), REFID_EMPTY),       # NaN float -> empty
    ((None, 0, False), REFID_EMPTY),
]


def main():
    failures = []
    for (refid, fanout, in_vote_csv), expected in CASES:
        got = classify_refid(refid, fanout=fanout, in_vote_csv=in_vote_csv)
        status = "ok" if got == expected else "FAIL"
        if got != expected:
            failures.append((refid, fanout, in_vote_csv, got, expected))
        print(f"  [{status}] classify_refid({refid!r}, fanout={fanout}, in_vote_csv={in_vote_csv}) -> {got}")
    if failures:
        print(f"\n*** {len(failures)} GOLDEN TEST FAILURE(S) ***")
        for f in failures:
            print(f"    {f}")
        return 1
    print(f"\nAll {len(CASES)} golden tests pass.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
