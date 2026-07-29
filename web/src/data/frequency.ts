// Natural frequencies — queue item V5, canon P26 (docs/design/information_display §5e).
//
// ONE RULE: a rate over a COUNT renders as "k of n". Never a percentage.
//
// The research behind it (Gigerenzer) is that "31 out of 100" is comprehended better than "31%" **at every
// sample size, not just small ones** — natural frequencies are cardinal numbers, so people reason with them
// correctly where the same problem stated as a probability defeats trained professionals. A percentage
// silently discards the denominator, which is the one thing that tells a reader whether to believe it.
//
// P26 WAS AMENDED BY THE OWNER 2026-07-27 AND THIS MODULE IS THE AMENDED FORM, not the original:
//   - no percentage companion for counts (the original allowed one "for comparison"; that was me hedging
//     against my own finding — if "k of n" is better at every n, a percentage is never the better form)
//   - no sample-size threshold, so nothing to calibrate and no "is n big enough" branch at any render site
//   - no "too few to judge" label: `0 of 2` already says it, and the label was the product editorialising
//     about a number it had just shown
//   - no Wilson interval: an interval is a statement about an estimated PROPORTION, and we render none
//
// The whole statistical-honesty layer therefore collapses to one function. A rare case where the honest
// form is also the cheap one.
//
// The ONLY sanctioned percentage in the product is a ratio of a CONTINUOUS quantity with no
// natural-frequency form — text difference ("11% different"), where there is nothing to count.
// See tools/text_corpus/textdiff.py.

/** A count and its denominator. Both required — a `k` without an `n` is the thing P26 exists to prevent. */
export interface Frequency {
  k: number;
  n: number;
}

/**
 * Render "k of n", or null when there is nothing to render.
 *
 * **Null, not "0 of 0"**: a denominator of zero means we have no observations, which is a different claim
 * from "we observed zero successes". Collapsing them is the sentinel trap (assumptions_audit #53) — the
 * caller must show absence as absence ("no record"), never as a zero that implies we looked.
 */
export function formatFrequency(f: Frequency | null | undefined): string | null {
  if (!f) return null;
  const { k, n } = f;
  if (!Number.isFinite(k) || !Number.isFinite(n)) return null;
  if (n <= 0) return null;
  return `${k.toLocaleString()} of ${n.toLocaleString()}`;
}

/**
 * The complement: "voted with us 1 of 6" implies 5 against, but the owner asked for both explicitly, because
 * a member voting AGAINST our bills is the more actionable half and burying it inside a subtraction hides it.
 */
export function complement(f: Frequency): Frequency {
  return { k: Math.max(0, f.n - f.k), n: f.n };
}

/**
 * Build a Frequency from a predicate over rows. Returns null for an empty input rather than `{k:0,n:0}`,
 * so "nothing to count" cannot be mistaken for "counted, found none".
 */
export function frequencyOf<T>(rows: readonly T[], hit: (row: T) => boolean): Frequency | null {
  if (!rows.length) return null;
  let k = 0;
  for (const r of rows) if (hit(r)) k++;
  return { k, n: rows.length };
}

/**
 * Sort key for ranking by rate ACROSS different denominators — e.g. ordering committees by kill rate.
 *
 * This is the case the original P26 clause 2 wanted a percentage for. Comparison needs a scalar, but the
 * scalar is for SORTING ONLY and must never reach the screen: rank by this, render `formatFrequency`.
 * A zero denominator sorts last rather than dividing by zero.
 */
export function rateForSort(f: Frequency | null | undefined): number {
  if (!f || f.n <= 0) return -1;
  return f.k / f.n;
}
