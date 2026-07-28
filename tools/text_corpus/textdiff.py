"""Text-difference percentage — queue item E5.

WHY THIS EXISTS (owner, 2026-07-27): the product was rendering OUR INTERPRETATION of a text comparison as
prose — "in sync", "high overlap". Owner: *"that's a reasonable place to use a percentage of difference
between the two versions, that way we aren't interpreting a simple stat into text when a human should just
look at the number."*

**The trust consequence is the real payoff, not the word count.** "High overlap" is a DERIVED claim (amber,
[[design/information_display]] P20a) — our software's judgement, which a user cannot audit. A diff percentage
is **deterministic arithmetic on two texts we already hold**, so it is exact math, not an estimate. Replacing
the words with the number moved three claims out of the derived class:

  1. companion drift   — House vs Senate version of the same bill
  2. version drift     — substitute vs introduced
  3. cross-state       — a Virginia bill vs another state's

This is also the ONLY sanctioned use of a percentage under P26 as amended: a rate over a COUNT must be shown
as `k of n`, but text difference is a ratio of a continuous quantity with no natural-frequency form — there
is nothing to count.

NOT the same thing as `normalize.similarity` (jaccard / containment). Those compare SHINGLE SETS and answer
"was this drafted from that?" — order-insensitive, good for model-legislation detection. This compares
SEQUENCES and answers "how much of the text changed?" — which is the question a lobbyist asks about a
substitute. Both are wanted; they are not substitutes for one another.
"""
from __future__ import annotations

from difflib import SequenceMatcher

from normalize import normalize

# SequenceMatcher's autojunk heuristic treats any element appearing in >1% of a sequence longer than 200 as
# "popular" junk and skips it when matching. In legislative text the commonest words ("the", "shall",
# "section") are exactly that, so the setting is DEFENSIVE: a deterministic figure must not depend on an
# undocumented popularity heuristic deciding which words count.
#
# HONESTY NOTE (2026-07-27): I first wrote that autojunk "inflates the difference", then tried to
# demonstrate it -- a 1,320-word constructed pair scored 9.1% either way. **The distortion did not
# reproduce, so it is not claimed as fact.** autojunk stays False on principle, not on a measured harm.
_AUTOJUNK = False


def difference_pct(text_a: str, text_b: str, *, already_normalized: bool = False) -> float | None:
    """Percent of the text that differs, 0.0–100.0. Returns **None when it cannot be computed.**

    None, never 0.0 and never 100.0, when either side is missing or empty. This is the same rule
    `normalize.jaccard` follows for empty shingle sets, and for the same reason: "we have no text for one
    side" is not evidence of sameness OR of difference, and encoding it as either manufactures a fact.
    Callers must render absence as absence -- the sentinel-collision trap in
    [[failures/assumptions_audit]] #53.
    """
    if text_a is None or text_b is None:
        return None
    a = text_a if already_normalized else normalize(text_a)
    b = text_b if already_normalized else normalize(text_b)
    wa, wb = a.split(), b.split()
    if not wa or not wb:
        return None
    ratio = SequenceMatcher(_AUTOJUNK and None, wa, wb, autojunk=_AUTOJUNK).ratio()
    return round((1.0 - ratio) * 100.0, 1)


def difference_label(pct: float | None) -> str:
    """The ONLY string this module produces, and it is not a judgement — it is the number plus its unit.

    P25 forbids text-per-signal, so there is deliberately no banding here ("minor edits" / "substantial
    rewrite"). Banding would be exactly the interpretation the owner removed. A caller that wants emphasis
    should style the number, not relabel it.
    """
    return "not comparable" if pct is None else f"{pct:g}% different"


def compare_versions(versions: list[dict], *, text_key: str = "text", label_key: str = "label") -> list[dict]:
    """Consecutive diffs across an ordered version list (introduced → substitute → engrossed → …).

    Each result carries BOTH endpoints' labels so a caller never has to infer which pair a number describes.
    A version with no text yields `pct: None` rather than being dropped -- a missing version must not make
    the chain look shorter than it is.
    """
    out = []
    for i in range(len(versions) - 1):
        a, b = versions[i], versions[i + 1]
        out.append({
            "from": a.get(label_key),
            "to": b.get(label_key),
            "pct": difference_pct(a.get(text_key), b.get(text_key)),
        })
    return out


def drift_from_introduced(versions: list[dict], *, text_key: str = "text",
                          label_key: str = "label") -> dict | None:
    """Cumulative difference between the FIRST version and the current one.

    Distinct from summing consecutive diffs, which double-counts text edited twice and can exceed 100%.
    'How far has this moved from what was introduced?' is one comparison, not a sum.
    """
    if len(versions) < 2:
        return None
    first, last = versions[0], versions[-1]
    return {
        "from": first.get(label_key),
        "to": last.get(label_key),
        "pct": difference_pct(first.get(text_key), last.get(text_key)),
    }
