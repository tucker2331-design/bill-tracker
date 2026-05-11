"""
PR-C7.1a — Trust math for the derived classifier.

Pure functions. No I/O. Testable in isolation.

Definitions
-----------
Training pair: (description_text, event_code)
  - description_text: free-form text from LIS LegislationEvent.Description
    (same shape as HISTORY.CSV.Outcome).
  - event_code: structural code from LIS LegislationEvent.EventCode
    (e.g., "H4020", "S8500"). Discrete alphabet.

Token: a sub-string extracted from description_text. We use lowercased
unigrams of length >= 3, filtered against a small stopword set.
Bigrams (adjacent-token pairs) added behind a flag for ablation; the
audit reports unigram-only vs unigram+bigram so the trust math can be
tuned.

Trust criterion for token t (information-theoretic):
  TRUSTED(t)
    <=>  N(t) >= MIN_SUPPORT                  (a)  rare-token guard
         AND
         H(EventCode | t) <= MAX_ENTROPY      (b)  ambiguous-token guard

  where:
    N(t)         = total occurrences of t across the training corpus
    P(c | t)     = N(t, c) / N(t) for each EventCode c
    H(EventCode | t) = - sum_c P(c | t) * log2(P(c | t))   [bits]

Row trust criterion:
  Given a row r with outcome text, tokenize and filter to TRUSTED
  tokens only. For each EventCode c, count how many of those trusted
  tokens vote for c (a token votes for its argmax_c P(c|t)).

  ROW_TRUSTED(r)
    <=>  |trusted_tokens(r)| >= MIN_TRUSTED_TOKENS
         AND
         top_votes(r) >= MIN_TOP_VOTES
         AND
         margin(r) := top_votes - second_votes >= MIN_MARGIN

  PASS  => classified as argmax_c votes(c, r)
  DLQ   => routed to "needs review" with the specific reason
           (which check failed) preserved for diagnostics

Mandate (per the math-proof directive): MIN_SUPPORT and MAX_ENTROPY
filter typos and chaotic words at the token level; MIN_TRUSTED_TOKENS,
MIN_TOP_VOTES, MIN_MARGIN filter low-signal rows. The audit's job is
to measure the PASS / DLQ split under a chosen (or swept) set of
thresholds, on the FULL HISTORY corpus.

No silent failures: every degraded path returns an explicit verdict
with a `reason` string so the DLQ is auditable.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

# Small stopword set. Tuned to parliamentary procedure vocabulary —
# we keep verbs ("reported", "passed", "stricken") and nouns
# ("committee", "subcommittee", "amendment") and drop only true
# function words. NEVER includes words that look like they might be
# discriminative — we let the entropy threshold filter those.
_STOPWORDS = frozenset({
    "the", "a", "an",
    "of", "to", "by", "from", "in", "on", "at", "with", "for",
    "and", "or", "but", "as",
    "this", "that", "these", "those",
    "was", "were", "is", "are", "be", "been", "being",
    "has", "have", "had",
})

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str, *, include_bigrams: bool = False) -> list[str]:
    """Lowercase + word-character split + length >= 3 + stopword filter.

    Returns a list (not a set) because some downstream operations
    care about per-row token counts; the trust math operates on
    distinct trusted tokens so the caller sets() as needed.

    Bigrams (when enabled) are joined with "_" so they're distinct
    from any unigram. Bigrams skip stopword filtering on internal
    components because phrases like "stricken from" carry signal
    that the unigram "from" loses.
    """
    if not text:
        return []
    lowered = text.lower()
    raw_tokens = _TOKEN_PATTERN.findall(lowered)
    unigrams = [t for t in raw_tokens if len(t) >= 3 and t not in _STOPWORDS]
    if not include_bigrams or len(raw_tokens) < 2:
        return unigrams
    bigrams = [
        f"{a}_{b}"
        for a, b in zip(raw_tokens[:-1], raw_tokens[1:])
        if len(a) >= 2 and len(b) >= 2
    ]
    return unigrams + bigrams


# ---------------------------------------------------------------------------
# Token statistics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenStats:
    """Per-token statistics + trust verdict.

    Frozen so accidental mutation is impossible; the audit treats
    TokenStats as a value-type.
    """
    token: str
    support: int                          # N(t)
    entropy: float                        # H(EventCode | t)  in bits
    top_event_code: str                   # argmax_c P(c|t)
    top_probability: float                # P(top_event_code | t)
    trusted: bool                         # passes MIN_SUPPORT and MAX_ENTROPY


def compute_token_stats(
    training_pairs: list[tuple[str, str]],
    *,
    min_support: int,
    max_entropy: float,
    include_bigrams: bool = False,
) -> dict[str, TokenStats]:
    """Build (token -> TokenStats) from a list of (description, event_code) pairs.

    Behavior on degenerate inputs:
      - Empty training_pairs: returns {}.
      - Pairs with empty description or empty event_code: skipped
        (do NOT contribute to N(t) or N(t, c)). This avoids the
        sentinel collision class identified in assumptions_audit #53.
      - Tokens that appear with only one event code: entropy = 0;
        if support >= min_support, they're TRUSTED. The classifier
        treats them as crisp signals.
      - Tokens at exactly the support / entropy boundary are TRUSTED
        (>=, <=) — inclusive on both sides.
    """
    # token -> (event_code -> count)
    counts: dict[str, Counter] = defaultdict(Counter)
    for description, event_code in training_pairs:
        if not description or not event_code:
            continue
        # De-dup tokens within a single description so repeating a word
        # in one event doesn't double-count.
        token_set = set(tokenize(description, include_bigrams=include_bigrams))
        for tok in token_set:
            counts[tok][event_code] += 1

    stats: dict[str, TokenStats] = {}
    for tok, event_counter in counts.items():
        support = sum(event_counter.values())
        if support == 0:
            # Defensive — should be unreachable given the inner increment
            # path, but keeps the function total.
            continue
        # Entropy in bits. log2(1) == 0 so single-class tokens get H = 0.
        h = 0.0
        for c, n in event_counter.items():
            p = n / support
            if p > 0.0:
                h -= p * math.log2(p)
        top_event, top_count = event_counter.most_common(1)[0]
        stats[tok] = TokenStats(
            token=tok,
            support=support,
            entropy=h,
            top_event_code=top_event,
            top_probability=top_count / support,
            trusted=(support >= min_support and h <= max_entropy),
        )
    return stats


# ---------------------------------------------------------------------------
# Row scoring
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RowVerdict:
    """The classifier's verdict on a single row."""
    verdict: str                          # "PASS" or "DLQ"
    predicted_event_code: str             # "" if DLQ
    trusted_tokens_used: int              # count of trusted tokens found in the row
    top_votes: int                        # votes for the winning event code
    second_votes: int                     # votes for the runner-up (0 if only one)
    margin: int                           # top_votes - second_votes
    reason: str                           # "" if PASS, else specific DLQ reason


# DLQ reason strings — enumerable so downstream consumers don't substring-match.
DLQ_NO_TRUSTED_TOKENS = "no_trusted_tokens"
DLQ_INSUFFICIENT_TRUSTED_TOKENS = "insufficient_trusted_tokens"
DLQ_INSUFFICIENT_TOP_VOTES = "insufficient_top_votes"
DLQ_INSUFFICIENT_MARGIN = "insufficient_margin"


def score_row(
    outcome_text: str,
    token_stats: dict[str, TokenStats],
    *,
    min_trusted_tokens: int,
    min_top_votes: int,
    min_margin: int,
    include_bigrams: bool = False,
) -> RowVerdict:
    """Apply the trust math to one row.

    See module docstring for the precise criterion. Returns RowVerdict
    with an explicit DLQ reason on FAIL so the audit can categorize
    the failure modes (rare-vocabulary vs ambiguous-text vs no-margin).
    """
    if not outcome_text:
        return RowVerdict(
            verdict="DLQ",
            predicted_event_code="",
            trusted_tokens_used=0,
            top_votes=0,
            second_votes=0,
            margin=0,
            reason=DLQ_NO_TRUSTED_TOKENS,
        )

    row_tokens = set(tokenize(outcome_text, include_bigrams=include_bigrams))
    trusted = [token_stats[t] for t in row_tokens if t in token_stats and token_stats[t].trusted]

    if not trusted:
        return RowVerdict(
            verdict="DLQ",
            predicted_event_code="",
            trusted_tokens_used=0,
            top_votes=0,
            second_votes=0,
            margin=0,
            reason=DLQ_NO_TRUSTED_TOKENS,
        )

    if len(trusted) < min_trusted_tokens:
        return RowVerdict(
            verdict="DLQ",
            predicted_event_code="",
            trusted_tokens_used=len(trusted),
            top_votes=0,
            second_votes=0,
            margin=0,
            reason=DLQ_INSUFFICIENT_TRUSTED_TOKENS,
        )

    # Each trusted token votes for its argmax EventCode.
    votes: Counter = Counter()
    for ts in trusted:
        votes[ts.top_event_code] += 1
    ranked = votes.most_common(2)
    top_event, top_votes = ranked[0]
    second_votes = ranked[1][1] if len(ranked) > 1 else 0
    margin = top_votes - second_votes

    if top_votes < min_top_votes:
        return RowVerdict(
            verdict="DLQ",
            predicted_event_code="",
            trusted_tokens_used=len(trusted),
            top_votes=top_votes,
            second_votes=second_votes,
            margin=margin,
            reason=DLQ_INSUFFICIENT_TOP_VOTES,
        )
    if margin < min_margin:
        return RowVerdict(
            verdict="DLQ",
            predicted_event_code="",
            trusted_tokens_used=len(trusted),
            top_votes=top_votes,
            second_votes=second_votes,
            margin=margin,
            reason=DLQ_INSUFFICIENT_MARGIN,
        )

    return RowVerdict(
        verdict="PASS",
        predicted_event_code=top_event,
        trusted_tokens_used=len(trusted),
        top_votes=top_votes,
        second_votes=second_votes,
        margin=margin,
        reason="",
    )


# ---------------------------------------------------------------------------
# Validation (held-out accuracy)
# ---------------------------------------------------------------------------


def validate_against_held_out(
    held_out_pairs: list[tuple[str, str]],
    token_stats: dict[str, TokenStats],
    *,
    min_trusted_tokens: int,
    min_top_votes: int,
    min_margin: int,
    include_bigrams: bool = False,
) -> dict:
    """Score a held-out (description, event_code) corpus and compute accuracy.

    Returns:
      {
        "n_held_out": int,
        "n_passed": int,             # PASS rows on the held-out set
        "n_correct_among_passed": int,
        "precision_on_passed": float,  # n_correct / n_passed
        "per_eventcode": {
            event_code: {
                "support": int,             # how many held-out rows had this true label
                "predicted_as": int,        # how many rows predicted this label
                "correctly_predicted": int  # intersection
            }
        }
      }

    Precision-on-passed is the headline accuracy metric: "of the rows
    the classifier was willing to classify, what fraction did it get
    right?" Recall-on-passed is implicit in the coverage / DLQ rate.
    """
    n_passed = 0
    n_correct = 0
    per_code: dict[str, dict[str, int]] = defaultdict(
        lambda: {"support": 0, "predicted_as": 0, "correctly_predicted": 0}
    )
    for description, true_code in held_out_pairs:
        if not description or not true_code:
            continue
        per_code[true_code]["support"] += 1
        v = score_row(
            description,
            token_stats,
            min_trusted_tokens=min_trusted_tokens,
            min_top_votes=min_top_votes,
            min_margin=min_margin,
            include_bigrams=include_bigrams,
        )
        if v.verdict != "PASS":
            continue
        n_passed += 1
        per_code[v.predicted_event_code]["predicted_as"] += 1
        if v.predicted_event_code == true_code:
            n_correct += 1
            per_code[true_code]["correctly_predicted"] += 1

    return {
        "n_held_out": sum(1 for d, c in held_out_pairs if d and c),
        "n_passed": n_passed,
        "n_correct_among_passed": n_correct,
        "precision_on_passed": (n_correct / n_passed) if n_passed > 0 else 0.0,
        "per_eventcode": {k: dict(v) for k, v in per_code.items()},
    }
