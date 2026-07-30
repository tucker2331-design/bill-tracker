// Ceremonial vs substantive, from LIS's own classification — 2026-07-30.
//
// WHY THIS EXISTS: session 20262 is 215 commending + 80 memorial = 295 of 300 bills. Without a split, the
// five bills that matter are invisible in a wall of "Commending the Petersburg High School boys' basketball
// team". The owner spotted it as "498 awaiting governor and the mass majority are unmeaningful to us".
//
// MEASURED both ways before shipping: the REGULAR session 20261 sampled 100 bills and contained ZERO
// ceremonial (98 Legislation, 2 Budget). So this can never quietly bury real work in a normal session — it
// only ever fires where the ceremony actually is.
//
// STRUCTURAL, never a keyword. `LegislationClass` is a field on LIS's own bill record; matching the word
// "commending" in a title would be text parsing on the lobbyist path (Standard #3 forbids it) and would
// mis-handle a substantive bill that happens to contain the word.

import type { Bill } from "./types";

/** LIS's ceremonial classes. Anything else — including a blank — is treated as substantive. */
const CEREMONIAL = new Set(["Commending Resolution", "Memorial Resolution"]);

/**
 * True when LIS classifies this as ceremonial.
 *
 * FAILS TOWARD VISIBILITY: an unknown or blank class returns false, so a bill we cannot classify stays in
 * the main list. Getting one commending resolution in the wrong group costs a second of confusion; hiding
 * one real bill costs the thing the product exists for.
 */
export const isCeremonial = (b: Bill): boolean => CEREMONIAL.has((b.legislationClass || "").trim());

export interface ClassSplit { substantive: Bill[]; ceremonial: Bill[]; commending: number; memorial: number; }

/** Split a list, preserving each side's incoming order. */
export function splitByClass(bills: Bill[]): ClassSplit {
  const substantive: Bill[] = [], ceremonial: Bill[] = [];
  let commending = 0, memorial = 0;
  for (const b of bills) {
    if (isCeremonial(b)) {
      ceremonial.push(b);
      if (b.legislationClass.trim() === "Commending Resolution") commending++; else memorial++;
    } else substantive.push(b);
  }
  return { substantive, ceremonial, commending, memorial };
}

/** "65 commending · 25 memorial" — counts only, no judgement about them. */
export function ceremonialLabel(s: ClassSplit): string {
  const parts: string[] = [];
  if (s.commending) parts.push(`${s.commending.toLocaleString()} commending`);
  if (s.memorial) parts.push(`${s.memorial.toLocaleString()} memorial`);
  return parts.join(" · ");
}
