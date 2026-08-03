#!/usr/bin/env python3
"""A GATE for analysis results, not a checklist about them.

WHY THIS EXISTS
---------------
Owner, 2026-08-02: *"why do we keep making these easy and simple mistakes, i thought we put in a protocol
that forced you to check everything ahead of time? not just writing but genuinely forced you"*

Because the protocol we had is PROSE. `docs/workflow/proposal_audit.md` fires as a reminder on every
message — "source every number, verify the arithmetic" — and it has caught nothing, because reading a
reminder and running a check are different acts. The things that HAVE caught errors in this project are all
scripts that exit non-zero: `prepush_audit.py` caught a stranded open_loop, the pyflakes gate caught a
NameError on a once-a-session code path, `reindex_caselaw --check` caught two lost audit entries.

The difference is not diligence. It is that a script runs whether or not I remember it.

WHAT IT CHECKS, and which real error each one would have caught:

  1. SELECTED POOL — the filtered pool's base rate differs sharply from the population it was drawn from.
     Would have caught: the survival curve conditioned on `span >= 42`, whose pool passes 83% against a
     49% population. FIRST VERSION OF THIS CHECK DID NOT WORK: it shuffled the outcome and re-applied the
     filter, which is blind whenever the filter conditions on a CORRELATE of the outcome rather than the
     outcome column itself — exactly the case here, since `span` is not `passed`. Comparing base rates
     catches conditioning on any correlate, named or not.

  2. PERMUTATION NULL — shuffle the outcome, re-run, confirm the effect disappears.
     Would have caught: any spurious split. The general backstop.

  3. SEPARATION TOO GOOD — a near-perfect split is leakage until proven otherwise.
     Would have caught: text_versions (1 version 3%, 4 versions 100%), re-referral (59% vs 0%).

  4. THIN MINORITY CLASS — fewer than 30 of the rarer outcome makes any rate unstable.
     Would have caught: the Senate committee-stage results, built on 10 failures out of 737.

  5. BASE-RATE DRIFT between the fitted period and the tested one.
     Would have caught: scoring against the train-year base rate, which paid every stat for drift and
     gave a do-nothing predictor +75.8% in the Senate.

Usage:
    from verify import check
    warnings = check(rows, key=lambda r: r["standing"], outcome="passed")
    for w in warnings: print(w)
"""
from __future__ import annotations
import collections
import random

MIN_MINORITY_CLASS = 30
SUSPICIOUS_SEPARATION = 0.90      # a bucket gap this wide is leakage until shown otherwise
PERMUTATION_ROUNDS = 200


def _rates(rows, key, outcome):
    agg = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        k = key(r)
        if k is None:
            continue
        a = agg[k]
        a[0] += 1 if r[outcome] else 0
        a[1] += 1
    return {k: (s, n) for k, (s, n) in agg.items() if n > 0}


def _spread(rates, minn):
    vals = [s / n for s, n in rates.values() if n >= minn]
    return (max(vals) - min(vals)) if len(vals) >= 2 else 0.0


SELECTION_GAP = 0.10          # pool vs population base-rate gap that signals a selected pool


def check(rows, key, outcome="passed", minn=25, parent=None, label=""):
    """Return a list of warning strings. EMPTY means the result passed every mechanical check.

    `parent`, if given, is the UNFILTERED population `rows` was drawn from. Comparing the two base rates
    detects a pool selected on the outcome or on anything correlated with it.
    """
    out = []
    tag = f"[{label}] " if label else ""
    if not rows:
        return [f"{tag}EMPTY: no rows to check."]

    # 4 — thin minority class
    pos = sum(1 for r in rows if r[outcome])
    neg = len(rows) - pos
    if min(pos, neg) < MIN_MINORITY_CLASS:
        out.append(f"{tag}UNDERPOWERED: only {min(pos, neg)} of the rarer outcome "
                   f"({pos} yes / {neg} no). Below {MIN_MINORITY_CLASS} any rate is unstable.")

    rates = _rates(rows, key, outcome)
    usable = {k: v for k, v in rates.items() if v[1] >= minn}
    if len(usable) < 2:
        out.append(f"{tag}NOT COMPARABLE: fewer than 2 buckets reach n>={minn} "
                   f"({len(rates)} buckets exist).")
        return out

    observed = _spread(rates, minn)

    # 3 — separation too good to be true
    if observed >= SUSPICIOUS_SEPARATION:
        lo = min(usable.items(), key=lambda kv: kv[1][0] / kv[1][1])
        hi = max(usable.items(), key=lambda kv: kv[1][0] / kv[1][1])
        out.append(f"{tag}SUSPICIOUS SEPARATION {observed:.0%}: {lo[0]}={lo[1][0]}/{lo[1][1]} vs "
                   f"{hi[0]}={hi[1][0]}/{hi[1][1]}. Treat as LEAKAGE until you can name the moment "
                   f"this feature is knowable and show it precedes the outcome.")

    # 2 — permutation null
    shuffled = [dict(r) for r in rows]
    outs = [r[outcome] for r in rows]
    beat = 0
    for _ in range(PERMUTATION_ROUNDS):
        random.shuffle(outs)
        for r, o in zip(shuffled, outs):
            r[outcome] = o
        if _spread(_rates(shuffled, key, outcome), minn) >= observed:
            beat += 1
    p = beat / PERMUTATION_ROUNDS
    if p > 0.05:
        out.append(f"{tag}FAILS THE PERMUTATION NULL: shuffling the outcome reproduced a spread this "
                   f"large in {beat} of {PERMUTATION_ROUNDS} runs (p={p:.2f}). The split is not "
                   f"distinguishable from chance.")

    # 1 — selected pool
    if parent:
        pr = sum(1 for r in rows if r[outcome]) / len(rows)
        pa = sum(1 for r in parent if r[outcome]) / len(parent)
        if abs(pr - pa) >= SELECTION_GAP:
            out.append(f"{tag}SELECTED POOL: this subset passes {pr:.0%} against {pa:.0%} for the "
                       f"population it came from ({len(rows):,} of {len(parent):,}). The filter is "
                       f"picking on the outcome or something correlated with it, so any comparison "
                       f"inside it is conditioned on survival.")
    return out


def drift(train, test, outcome="passed", label=""):
    """5 — base-rate drift. Scoring a stat against the TRAINING period's base rate pays it for drift."""
    a = sum(1 for r in train if r[outcome]) / len(train)
    b = sum(1 for r in test if r[outcome]) / len(test)
    if abs(a - b) >= 0.05:
        return [f"[{label}] BASE-RATE DRIFT {a:.0%} -> {b:.0%}. Score against the TEST period's rate, "
                f"or a do-nothing predictor scores well for the shift alone."]
    return []


class VerificationFailed(AssertionError):
    """Raised by require(). A result that cannot pass the gate must not be reported."""


def require(rows, key, outcome="passed", **kw):
    """FAIL-CLOSED form. check() returns a list, which a caller can ignore; this raises.
    Use it anywhere a number is about to be written down or shown to someone."""
    w = check(rows, key, outcome=outcome, **kw)
    if w:
        raise VerificationFailed("\n".join(w))
    return True
