#!/usr/bin/env python3
"""Goldens for the bill-text normalizer + shingler (W2/W3 pure core). Offline: no network, no credentials.

These pin the behaviours the similarity result depends on. A regression here would not crash anything — it
would quietly change every similarity score, which is the dangerous kind of bug.
"""
import sys

sys.path.insert(0, "tools/text_corpus")
import normalize as N  # noqa: E402

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"  {'✓' if ok else '✗'} {label}")
    if not ok:
        print(f"      got:  {got!r}\n      want: {want!r}")
        FAILURES.append(label)


print("— markup + entities —")
check("tags removed, text preserved",
      N.normalize("<p class=ldtitle>A BILL to amend §&nbsp;2.2-2744</p>"),
      "amend § 2 2 2744")
check("nbsp becomes a real space (not glued words)",
      "amend" in N.normalize("<p>amend&nbsp;the code</p>").split(), True)
check("an entity hidden in an attribute cannot leak into the text",
      "href" in N.normalize("<a href='&quot;x&quot;'>text</a>"), False)

print("\n— presentation stripped, substance kept —")
check("shall vs may is PRESERVED (never stemmed away)",
      N.normalize("The agency shall comply") != N.normalize("The agency may comply"), True)
check("line numbers in the gutter are dropped",
      N.normalize("1 the agency\n2 shall comply"), "the agency shall comply")
check("the section sign survives (it is part of a citation)",
      "§" in N.normalize("amend § 58.1-3506"), True)
check("case and whitespace are normalized",
      N.normalize("  The   AGENCY\n\tshall  "), "the agency shall")
check("curly quotes normalize to plain (NFKC)",
      N.normalize("“notice”") == N.normalize('"notice"'), True)

print("\n— VA enacting boilerplate —")
check("the enacting clause is dropped so it can't inflate similarity",
      N.normalize("Be it enacted by the General Assembly of Virginia, That the Code is amended"),
      "that the code is amended")
check("boilerplate removal can be turned OFF for exact-text work",
      N.normalize("A BILL to amend", drop_boilerplate=False), "a bill to amend")

print("\n— shingles —")
check("k-word windows, overlapping", len(N.shingles("a b c d e", k=3)), 3)
check("a text shorter than k still yields ONE shingle (never an empty set)",
      N.shingles("short text", k=8), {"short text"})
check("empty text yields no shingles", N.shingles("", k=3), set())

print("\n— similarity math —")
a = N.shingles(N.normalize("the agency shall provide written notice to each affected consumer"), k=4)
b = N.shingles(N.normalize("the agency shall provide written notice to each affected consumer"), k=4)
c = N.shingles(N.normalize("appropriations for the department of transportation highway maintenance fund"), k=4)
check("identical text scores 1.0", N.jaccard(a, b), 1.0)
check("unrelated text scores 0.0", N.jaccard(a, c), 0.0)
check("two EMPTY texts score 0.0, never 1.0 (missing data is not sameness)", N.jaccard(set(), set()), 0.0)
check("one empty side scores 0.0", N.jaccard(a, set()), 0.0)

# Containment: the model-bill shape Jaccard alone would miss.
small = N.shingles(N.normalize("the agency shall provide written notice to each affected consumer"), k=4)
omnibus = N.shingles(N.normalize(
    "unrelated preamble about budgets and appropriations for many agencies over several pages "
    "the agency shall provide written notice to each affected consumer "
    "followed by more unrelated text about transportation and education funding"), k=4)
check("a small bill fully absorbed into a large one: containment sees it", N.containment(small, omnibus), 1.0)
check("...while Jaccard alone would under-report it", N.jaccard(small, omnibus) < 0.5, True)
check("containment is directional (the omnibus is NOT contained in the small bill)",
      N.containment(omnibus, small) < 1.0, True)

print()
if FAILURES:
    print(f"❌ {len(FAILURES)} failure(s): {FAILURES}")
    sys.exit(1)
print("✅ all text-normalization goldens pass")
