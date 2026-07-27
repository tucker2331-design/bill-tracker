#!/usr/bin/env python3
"""Bill-text normalization + shingling — the PURE core of the similarity engine (W2/W3).

Separated from any fetching so it is exhaustively golden-testable offline with zero network and zero
credentials, the same split that made the change-ledger differ provable before its live wiring existed.

WHY NORMALIZATION IS THE WHOLE BALLGAME
Two chambers' copies of the same bill, or two states' copies of one model act, are never byte-identical:
they differ in enacting clauses, line numbers, section numbering styles, whitespace, and HTML wrapping. Raw
comparison therefore reports "different" for text a human would call identical. ~80% of similarity quality
lives here, not in the comparison math — so this file is deliberately conservative and every rule is
documented with what it assumes and how it breaks (Standard #1).

WHAT THIS DELIBERATELY DOES NOT DO
No stemming, no stopword removal, no embeddings, no AI. Legislative text turns on exact words ("shall" vs
"may"), and a lossy transform would erase the very difference a lobbyist is asking about. Everything here is
reversible in meaning: we strip PRESENTATION, never SUBSTANCE.
"""
from __future__ import annotations

import re
import unicodedata

# ── presentation-only patterns (safe to strip: none of these carry legal meaning) ──────────────────────
_TAG_RE = re.compile(r"<[^>]+>")                      # HTML wrapper from LIS's DraftText
_LINE_NO_RE = re.compile(r"^\s*\d{1,4}\s", re.M)      # printed line numbers in the left gutter
_WS_RE = re.compile(r"\s+")
# HTML entities LIS actually emits (&nbsp; dominates). Kept explicit rather than a general unescape so a
# surprise entity shows up as itself in the output instead of being silently transformed.
_ENTITIES = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#160;": " ", "&#38;": "&"}

# Enacting/boilerplate openers. VA-specific TODAY and marked as such: when a second state is onboarded these
# move behind the source contract (Standard #6) rather than growing into a 50-state list here.
_VA_BOILERPLATE = (
    re.compile(r"^\s*be it enacted by the general assembly of virginia[,:]?\s*", re.I),
    re.compile(r"^\s*a bill to\s+", re.I),
)


def strip_markup(raw: str) -> str:
    """HTML → plain text. Entity decoding happens BEFORE tag removal so an entity inside an attribute can
    never leak into the visible text."""
    if not raw:
        return ""
    out = raw
    for ent, ch in _ENTITIES.items():
        out = out.replace(ent, ch)
    out = _TAG_RE.sub(" ", out)
    return out


def normalize(raw: str, *, drop_boilerplate: bool = True) -> str:
    """Presentation-stripped, comparison-ready text.

    ASSUMES: input is a single bill version's body (LIS `DraftText` or equivalent).
    BREAKS IF: a state encodes substance in markup (e.g. strike-through marking deleted language). VA does
    not — deletions arrive as separate VERSIONS, which is why version-to-version diffing is a distinct
    feature. A state that does would need its own extractor behind the source contract.
    VALIDATED BY: test_text_normalize.py, plus the companion-pair separation measurement in W3 — if
    normalization were lossy or over-aggressive, known-identical pairs would stop separating from random ones.
    """
    text = strip_markup(raw)
    text = unicodedata.normalize("NFKC", text)          # curly quotes/dashes → canonical forms
    text = text.replace(" ", " ")
    text = _LINE_NO_RE.sub(" ", text)
    text = text.lower()
    # Punctuation is presentation for our purposes, EXCEPT the section sign, which is part of a citation.
    text = re.sub(r"[^\w\s§]", " ", text)
    text = _WS_RE.sub(" ", text).strip()
    if drop_boilerplate:
        for pat in _VA_BOILERPLATE:
            text = pat.sub("", text)
    return text.strip()


def shingles(text: str, k: int = 8) -> set[str]:
    """Overlapping k-word windows — the unit of comparison.

    WHY WORD-LEVEL, k=8: character shingles match on shared vocabulary alone and would call any two bills
    about taxation "similar"; 8 consecutive identical words is a strong signal of copied drafting and is the
    size the model-legislation research settled on. Shorter k over-matches boilerplate; longer k misses bills
    that were lightly edited. k is a parameter so W3 can MEASURE the best value against the companion-pair
    ground truth instead of us asserting one (Standard #7).

    A text shorter than k yields ONE shingle (the whole text) rather than an empty set — an empty set would
    make every short bill 0%-similar to everything, silently.
    """
    words = text.split()
    if not words:
        return set()
    if len(words) <= k:
        return {" ".join(words)}
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    """|A∩B| / |A∪B|. Two empty texts are 0.0, never 1.0: "we have no text for either" is not evidence of
    sameness, and returning 1.0 there would manufacture a false near-identical match from missing data."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


def containment(a: set[str], b: set[str]) -> float:
    """|A∩B| / |A| — how much of A appears in B. Jaccard punishes size differences, so a 3-page bill lifted
    wholesale into a 60-page omnibus scores low on Jaccard while being a total copy. Containment catches that
    'partial' case, which is exactly the model-bill shape a lobbyist cares about."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)
