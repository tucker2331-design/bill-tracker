#!/usr/bin/env python3
"""Goldens for companion detection + drift (W4). Offline: synthetic text, no network, no corpus."""
import sys

sys.path.insert(0, "tools/text_corpus")
import companions as C  # noqa: E402

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"  {'✓' if ok else '✗'} {label}")
    if not ok:
        print(f"      got: {got!r}  want: {want!r}")
        FAILURES.append(label)


BODY = ("the agency shall provide written notice to each affected consumer within thirty days "
        "and shall maintain a record of each notice for a period of not less than three years ") * 3
OTHER = ("appropriations for the department of transportation shall be allocated to the highway "
         "maintenance and operating fund for the fiscal biennium ") * 3

print("— structural candidates —")
bills = [("HB463", "Consumer data privacy"), ("SB402", "Consumer data privacy"),
         ("HB999", "Something else"), ("SB111", "consumer DATA privacy  ")]
pairs = C.candidate_pairs(bills)
check("cross-chamber same-title pairs found (case/space-insensitive)", len(pairs), 2)
check("pairs are (house, senate)", (pairs[0][0].startswith("HB"), pairs[0][1].startswith("SB")), (True, True))
check("a title with no counterpart chamber yields no pair",
      any("HB999" in p for p in pairs), False)
check("ordering is deterministic (reproducible runs)", pairs, sorted(pairs))

print("\n— three-valued verdicts, never a silent boolean —")
res = C.detect([("HB1", "SB1", "t")], {"HB1": BODY, "SB1": BODY})
check("identical text → confirmed", res[0]["verdict"], "confirmed")
check("...labelled in coarse words, not a fake percentage", res[0]["label"], "near-identical")

res = C.detect([("HB2", "SB2", "t")], {"HB2": BODY, "SB2": OTHER})
check("same title, unrelated text → WEAK (reported, never hidden)", res[0]["verdict"], "weak")

res = C.detect([("HB3", "SB3", "t")], {"HB3": BODY})
check("missing text → unverifiable, NOT a negative finding", res[0]["verdict"], "unverifiable")
check("...and it says which side was missing", "SB3" in res[0]["reason"], True)

print("\n— the absorbed case Jaccard alone would miss —")
omnibus = OTHER + BODY + OTHER
cmp_ = C.compare(BODY, omnibus)
check("a bill absorbed whole into an omnibus is flagged", cmp_["absorbed"], True)
check("...even though Jaccard is low", cmp_["jaccard"] < C.SUBSTANTIAL, True)
check("containment sees it", cmp_["containment_a_in_b"] >= C.NEAR_IDENTICAL, True)
res = C.detect([("HB4", "SB4", "t")], {"HB4": BODY, "SB4": omnibus})
check("so the pair is CONFIRMED on containment, not missed", res[0]["verdict"], "confirmed")

print("\n— absorption is SYMMETRIC (CodeRabbit, PR #233) —")
# The relationship "one bill is contained in the other" has no direction. Checking only A-in-B meant a
# Senate bill lifted into a House omnibus scored `weak` while the mirror image was caught — half-blind.
check("Senate absorbed into a House omnibus is caught too",
      C.compare(omnibus, BODY)["absorbed"], True)
check("...and so is the reverse (unchanged)", C.compare(BODY, omnibus)["absorbed"], True)
res = C.detect([("HB6", "SB6", "t")], {"HB6": omnibus, "SB6": BODY})
check("the reversed pair is CONFIRMED, not weak", res[0]["verdict"], "confirmed")

print("\n— pairing is SESSION-SCOPED (CodeRabbit, PR #233) —")
# Bill titles repeat across sessions constantly, so a caller mixing sessions would otherwise pair a 2025 HB
# with a 2026 SB on a recycled title.
check("identical titles in DIFFERENT sessions do not pair",
      C.candidate_pairs([("HB1", "same title", "20251"), ("SB1", "same title", "20261")]), [])
check("identical titles in the SAME session still pair",
      len(C.candidate_pairs([("HB1", "same title", "20261"), ("SB1", "same title", "20261")])), 1)
check("the 2-tuple form still works for single-session callers",
      len(C.candidate_pairs([("HB1", "same title"), ("SB1", "same title")])), 1)

print("\n— honesty defaults —")
check("two empty texts are NOT called identical", C.compare("", "")["jaccard"], 0.0)
res = C.detect([("HB5", "SB5", "t")], {"HB5": "", "SB5": ""})
check("...and an empty pair is unverifiable, not confirmed", res[0]["verdict"], "unverifiable")

print("\n— thresholds match the calibration —")
check("NEAR_IDENTICAL sits below the observed same-pair floor (0.857)", C.NEAR_IDENTICAL < 0.857, True)
check("...and far above the observed random-pair ceiling (0.011)", C.NEAR_IDENTICAL > 0.011, True)
check("labels are a closed set", len(C.LABELS), 4)

print("\n— drift: the negotiation state —")
results = [
    {"verdict": "confirmed", "jaccard": 1.0, "house": "HB1", "senate": "SB1"},
    {"verdict": "confirmed", "jaccard": 0.91, "house": "HB2", "senate": "SB2"},
    {"verdict": "confirmed", "jaccard": 0.83, "house": "HB3", "senate": "SB3"},
    {"verdict": "weak", "jaccard": 0.02, "house": "HB4", "senate": "SB4"},
]
d = C.drift(results)
check("weak pairs are excluded from the drift picture", d["confirmed"], 3)
check("an identical pair counts as in-sync", d["in_sync"], 1)
check("diverged pairs are counted", d["diverged"], 2)
check("most-diverged is ordered worst-first (where the fight is)",
      d["most_diverged"][0]["house"], "HB3")

print()
if FAILURES:
    print(f"❌ {len(FAILURES)} failure(s): {FAILURES}")
    sys.exit(1)
print("✅ all companion-detection goldens pass")
