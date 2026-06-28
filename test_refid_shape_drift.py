#!/usr/bin/env python3
"""Golden tests for the refid SHAPE drift monitor (structural_router.validate_refid_shapes).

The sustainable answer to UNKNOWN_REFID: instead of hand-coding a grammar per new refid shape, a
baseline of acknowledged shapes + a runtime diff that ALERTS when a NOVEL shape appears in volume →
human review (mirrors validate_status_grouping). Locks the signature normalization, the known-shape
baseline (no false drift on today's cohort), the volume floor, and the novel-shape detection.

Run: python3 test_refid_shape_drift.py  (exit 0 = all pass).
"""
from structural_router import (
    refid_shape_signature, validate_refid_shapes, KNOWN_REFID_SHAPES, REFID_SHAPE_MIN_VOLUME,
)

SIG_CASES = [
    # (refid, expected signature) — each maximal digit-run -> '#', letters/underscore literal
    ("HB1000F122", "HB#F#"),
    ("HB1002ERF122", "HB#ERF#"),
    ("HB1001H1F122", "HB#H#F#"),
    ("SB106S1F122", "SB#S#F#"),
    ("26101239D_H8120", "#D_H#"),
    ("SV100", "SV#"),
    ("VSV900", "VSV#"),
    ("H14V2610034", "H#V#"),
    ("26108316D", "#D"),
    ("5354", "#"),
    ("HB1046", "HB#"),
    (26110000.0, "#"),          # float refid normalizes first (no ".0" artifact in the signature)
    ("", ""),                   # empty -> empty signature
]

def _bag(sig, n):
    """n refids that all normalize to `sig` (vary the digits so they're distinct strings)."""
    return [sig.replace("#", str(1000 + i)) for i in range(n)]

def main():
    failures = []

    # 1. signature normalization
    for refid, expected in SIG_CASES:
        got = refid_shape_signature(refid)
        ok = got == expected
        if not ok:
            failures.append(("signature", refid, got, expected))
        print(f"  [{'ok' if ok else 'FAIL'}] signature({refid!r:18}) -> {got!r} (exp {expected!r})")

    # 2. today's acknowledged cohort produces NO drift (no false alarm), even at high volume
    today = []
    for sig in KNOWN_REFID_SHAPES:
        today += _bag(sig, REFID_SHAPE_MIN_VOLUME + 5)
    drift = validate_refid_shapes(today)
    ok = drift == {}
    if not ok:
        failures.append(("no-false-drift", "known-cohort", drift, {}))
    print(f"  [{'ok' if ok else 'FAIL'}] known cohort ({len(today)} refids) -> drift {drift or 'NONE'}")

    # 3. a NOVEL shape at/above the volume floor IS reported
    novel = _bag("ZZ#Q#", REFID_SHAPE_MIN_VOLUME)
    drift = validate_refid_shapes(novel)
    ok = drift.get("ZZ#Q#") == REFID_SHAPE_MIN_VOLUME
    if not ok:
        failures.append(("novel-at-floor", "ZZ#Q#", drift, {"ZZ#Q#": REFID_SHAPE_MIN_VOLUME}))
    print(f"  [{'ok' if ok else 'FAIL'}] novel shape x{REFID_SHAPE_MIN_VOLUME} -> drift {drift}")

    # 4. a NOVEL shape BELOW the floor stays quiet (one-off, not a systematic namespace)
    drift = validate_refid_shapes(_bag("ZZ#Q#", REFID_SHAPE_MIN_VOLUME - 1))
    ok = drift == {}
    if not ok:
        failures.append(("novel-below-floor", "ZZ#Q#", drift, {}))
    print(f"  [{'ok' if ok else 'FAIL'}] novel shape x{REFID_SHAPE_MIN_VOLUME - 1} (below floor) -> drift {drift or 'NONE'}")

    # 5. empty / None input never raises, returns no drift — and a regression here MUST fail the
    #    script (CodeRabbit #178: the old form only printed, never appended to `failures`, so it
    #    could exit 0 even if validate_refid_shapes(None) started returning non-empty).
    for empty in (None, []):
        d = validate_refid_shapes(empty)
        ok = d == {}
        if not ok:
            failures.append(("empty-input", empty, d, {}))
        print(f"  [{'ok' if ok else 'FAIL'}] empty input {empty!r} -> drift {d or 'NONE'}")

    if failures:
        print(f"\n*** {len(failures)} FAILURE(S) ***")
        for f in failures:
            print(f"    {f}")
        return 1
    print(f"\nAll refid-shape-drift golden tests pass ({len(KNOWN_REFID_SHAPES)} acknowledged shapes, "
          f"volume floor {REFID_SHAPE_MIN_VOLUME}).")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
