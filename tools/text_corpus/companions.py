#!/usr/bin/env python3
"""Companion-bill detection + text DRIFT (W4) — pure logic over an already-fetched corpus.

WHAT A COMPANION IS: Virginia runs House/Senate mirrors of the same bill. Two simultaneous paths to one
outcome — and, once they start moving, the DRIFT between them is the negotiation state. Your carve-out
surviving in one chamber but not the other tells you whether a conference fight is coming and which version
to defend. That is why this reports drift, not just pairing (owner: "think about how important that info is").

WHY NOT AN API: probed 2026-07-27 — LIS exposes no companion/related-bill endpoint (five plausible routes,
all 404). So the pairing is DERIVED, and it must therefore carry a derived-class label on any surface
(docs/design/information_display.md P20a). Two independent signals agree before we call it a companion:
  1. STRUCTURAL — same session, opposite chambers, identical title. Cheap, and it comes from data we already
     hold in Bill_Tracker.
  2. TEXTUAL — the calibrated comparer. On 12 known pairs the same-pair floor was 0.857 while random pairs
     topped out at 0.011 (a +0.846 gap), so a title match that ALSO clears the text bar is not a coincidence.

Requiring both is what keeps this honest: a same-title pair whose texts diverge is reported as a WEAK pairing
rather than silently asserted, and it is exactly the case a human should look at.

PURE: takes text in, returns verdicts. No fetching, no network — so the thresholds are testable offline.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import containment, jaccard, normalize, shingles  # noqa: E402

# Calibrated on real bills, not chosen by feel (docs/architecture/text_similarity.md §W3):
#   known companions  min 0.857 · median 0.991 · max 1.000
#   random cross-pairs min 0.000 · median 0.001 · max 0.011
# Any cut in ~[0.02, 0.85] separates that sample perfectly, so the exact value is not delicate. 0.80 keeps
# margin below the observed same-pair floor. HONEST LIMIT: n=12, one session, VA only — re-measure before
# using these for cross-state text, where drafting conventions differ.
NEAR_IDENTICAL = 0.80
SUBSTANTIAL = 0.50
PARTIAL = 0.15
SHINGLE_K = 8

# Coarse words, never a fake-precise percentage (P20b). A number like "87.3% similar" implies a confidence
# the method cannot support; these labels say what we can actually stand behind.
LABELS = ("near-identical", "substantial overlap", "partial overlap", "loose")


def label_for(score):
    if score >= NEAR_IDENTICAL:
        return LABELS[0]
    if score >= SUBSTANTIAL:
        return LABELS[1]
    if score >= PARTIAL:
        return LABELS[2]
    return LABELS[3]


def compare(text_a, text_b, k=SHINGLE_K):
    """Both measures, because Jaccard alone under-reports the model-bill shape: a short bill absorbed whole
    into a long one scores low on Jaccard while being a total copy. Containment catches that."""
    sa, sb = shingles(normalize(text_a), k), shingles(normalize(text_b), k)
    j = jaccard(sa, sb)
    return {
        "jaccard": round(j, 4),
        "containment_a_in_b": round(containment(sa, sb), 4),
        "containment_b_in_a": round(containment(sb, sa), 4),
        "label": label_for(j),
        # The absorbed case, in BOTH directions. This checked only `A in B` — so a Senate bill lifted whole
        # into a House omnibus scored `weak` and the pair was missed, while the mirror image was caught.
        # An asymmetric test on a symmetric relationship is a silent half-blindness (CodeRabbit, PR #233).
        "absorbed": (containment(sa, sb) >= NEAR_IDENTICAL or containment(sb, sa) >= NEAR_IDENTICAL)
                    and j < SUBSTANTIAL,
    }


def candidate_pairs(bills):
    """STRUCTURAL signal only. Returns [(house, senate, title)].

    `bills` = iterable of `(bill_id, title)` or `(bill_id, title, session_code)`. The stated rule is "same
    SESSION, opposite chambers, identical title", but the 2-tuple form carries no session — so a caller
    mixing sessions would pair a 2025 HB with a 2026 SB on a recycled title, which is a real risk because
    bill titles repeat across sessions constantly (CodeRabbit, PR #233). When the 3-tuple form is used the
    session is part of the grouping key and cross-session pairing becomes impossible; the 2-tuple form is
    still accepted for single-session callers and treated as one implicit session.

    Deterministic ordering so a run is reproducible and diffable. A title shared by more than two bills is
    NOT silently collapsed to one pair — every cross-chamber combination is emitted, because picking one
    arbitrarily would hide a real 3-way relationship (honest-absent beats plausible-wrong).
    """
    by_title: dict = {}
    for row in bills:
        bill_id, title = row[0], row[1]
        session = row[2] if len(row) > 2 else ""      # "" = one implicit session (single-session caller)
        key = ((title or "").strip().lower(), str(session).strip())
        if not key[0] or not bill_id:
            continue
        by_title.setdefault(key, []).append(bill_id.strip())
    out = []
    for (title, _session), ids in by_title.items():
        house = sorted({b for b in ids if b.upper().startswith("HB")})
        senate = sorted({b for b in ids if b.upper().startswith("SB")})
        for h in house:
            for s in senate:
                out.append((h, s, title))
    return sorted(out)


def detect(pairs, texts, k=SHINGLE_K):
    """Confirm (or refuse to confirm) each structural candidate with text.

    Verdicts are deliberately three-valued, never a silent boolean:
      confirmed   — both signals agree; safe to present as a companion (still DERIVED, still amber)
      weak        — titles match but the texts do NOT; a human should look. Reported, never hidden.
      unverifiable— we have no text for one side; ABSENT, not evidence of anything either way.
    """
    results = []
    for h, s, title in pairs:
        ta, tb = texts.get(h), texts.get(s)
        if not ta or not tb:
            results.append({"house": h, "senate": s, "title": title, "verdict": "unverifiable",
                            "reason": f"no text for {h if not ta else s}"})
            continue
        cmp_ = compare(ta, tb, k)
        confirmed = cmp_["jaccard"] >= NEAR_IDENTICAL or cmp_["absorbed"]
        results.append({"house": h, "senate": s, "title": title,
                        "verdict": "confirmed" if confirmed else "weak", **cmp_})
    return results


def drift(results):
    """The lobbyist-facing half: of the CONFIRMED companions, which have started to diverge?

    A pair at 1.000 is still in sync. A confirmed pair below that has drifted, and the drift is the
    negotiation state — which is the whole reason this feature exists.
    """
    confirmed = [r for r in results if r.get("verdict") == "confirmed"]
    in_sync = [r for r in confirmed if r["jaccard"] >= 0.999]
    diverged = sorted((r for r in confirmed if r["jaccard"] < 0.999), key=lambda r: r["jaccard"])
    return {"confirmed": len(confirmed), "in_sync": len(in_sync), "diverged": len(diverged),
            "most_diverged": diverged[:10]}
