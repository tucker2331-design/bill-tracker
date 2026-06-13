"""Golden tests for structural_router.classify_refid (PR-C8.1).

Locks the refid-identity classification of HISTORY rows — the text-free replacement for the
blank-route text patterns. Run: python3 test_classify_refid.py  (exit 0 = all pass).
Spec + measured namespace: docs/architecture/pr_c8_structural_classification.md,
docs/knowledge/history_refid_namespace.md.
"""
from structural_router import (
    classify_refid, REFID_VOTE_COMMITTEE, REFID_VOTE_FLOOR, REFID_BATCH_NOTICE,
    REFID_SINGLETON_DOC, REFID_COMMITTEE_REF, REFID_VOTE_UNMATCHED, REFID_DOCUMENT,
    REFID_UNKNOWN, REFID_EMPTY,
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
    (("nan", 0, False), REFID_EMPTY),              # string reprs of missing values
    (("none", 0, False), REFID_EMPTY),
    (("NA", 0, False), REFID_EMPTY),               # pandas nullable NA reprs (Gemini PR-C8.1)
    (("<NA>", 0, False), REFID_EMPTY),
    (("5354.0", 63, False), REFID_BATCH_NOTICE),   # float-string batch refid still batches
    # NUMERIC LENGTH LAW (PR-C8.4a, measured 20261): len<=6 = document, len>=7 = vote-id namespace.
    (("123456", 1, False), REFID_SINGLETON_DOC),   # len-6 numeric, not in VOTE.CSV -> document
    (("123456", 5, False), REFID_BATCH_NOTICE),    # len-6 numeric, fan-out>=K -> batch document
    (("2610807", 0, False), REFID_VOTE_UNMATCHED), # len-7 vote-id-shaped but NOT in VOTE.CSV ->
                                                   # SURFACE (failed join; never read as a document)
    (("26110000", 0, False), REFID_VOTE_UNMATCHED),# len-8 vote-id-shaped, not in VOTE.CSV -> surface
    (("2610807", 0, True), REFID_VOTE_FLOOR),      # same len-7 but IN VOTE.CSV -> meeting (join wins)
    # LEADING-ZERO CONTRACT (Gemini #115): the caller must pass the RAW string (worker reads
    # dtype=str). A correctly-preserved leading-zero len-7 vote-id surfaces; the catastrophic case
    # (float-truncation to len 6) is unrecoverable in-function and is prevented at the read site.
    (("0123456", 0, False), REFID_VOTE_UNMATCHED), # len-7 with leading zero, string-preserved -> surface
    # BILL-VERSION DOCUMENT refids (PR-C8.4c): \d+[A-Z] = a printed/received document id -> DOCUMENT
    # (-> admin). 0% VOTE.CSV join. Closes the "Governor's substitute printed" / "Veto Received" lane.
    (("26108316D", 0, False), REFID_DOCUMENT),     # substitute-printed document id
    (("26110164G", 0, False), REFID_DOCUMENT),     # other version-letter suffix
    (("26109829C", 0, False), REFID_DOCUMENT),     # conference-substitute document id
    (("HB1F122", 0, False), REFID_UNKNOWN),        # bill-prefixed (fiscal impact) is NOT \d+[A-Z] -> still UNKNOWN
    (("SV866", 0, False), REFID_UNKNOWN),          # bill-prefixed -> UNKNOWN (not a \d+[A-Z] document id)
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
