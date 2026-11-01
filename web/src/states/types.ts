// The per-state contract on the front end (Standard #6). Mirrors the Python `states/base.py` StateConfig for the
// fields the SPA needs; `test_states.py` fails if the two disagree on code, source, stages or the bill link.
// Dependency-free so the bare-node golden (states/__tests__/va.regression.mjs) can import the real code.

export interface StageDef {
  id: string;
  label: string;
  /** A deadline marker (VA's crossover), not a place a bill sits. */
  marker?: boolean;
}

export interface StateConfig {
  code: string;               // USPS code — also the `state` dimension on every team write (migrations/0001)
  name: string;               // "Virginia"
  appName: string;            // product name in the title, header brand and sign-in gate
  sourceName: string;         // the authoritative publisher, as users see it ("LIS")
  sourceLongName: string;     // "Virginia LIS"
  legislatureName: string;    // "the General Assembly"
  chambers: Record<string, "House" | "Senate">;   // bill-number prefix -> chamber name
  /** A real bill id in this state's numbering (the calendar's skeleton rows hold addresses, not bills). */
  billIdPattern: RegExp;
  stages: StageDef[];
  sessionYears: number;       // 1 = annual (VA), 2 = two-year (PA)
  /** Session code -> crossover day (YYYY-MM-DD). Empty for a state with no crossover deadline. */
  crossoverBySession: Record<string, string>;
  /** "" = the source has no stable per-bill page we link to; the link is hidden rather than guessed. */
  billUrl: (sessionCode: string, bill: string) => string;
  /** Which screens this state's site has (owner 2026-11-01: PA = Search, bill card, What's new, Tracking, Health).
   *  Config only — a hidden screen is simply not offered; no screen branches on the state's name. */
  features: {
    calendar: boolean;     // Calendar tab, Today's calendar strip, next-meeting join, calendar freshness clock
    timeline: boolean;     // the pipeline drawing on Today
    warroom: boolean;      // War Room tab + bill page
    predictions: boolean;  // the vote model's served calls (War Room member bar, order, bill-page member calls)
    committeeRoster: boolean;   // the bill page lists the current committee's members from a roster tab
    summaries: boolean;    // the source's summary text on the bill card
    health: "full" | "intake";   // the same Health screen; intake = fed by the state's own job checks (no VA guards/ledger)
  };
  /** A fixed-position code field at the start of the source's action text, removed for display only (VA: LIS's
   *  "H "/"S " chamber column). null = none. Where an action happened is never read from it. */
  actionCodePrefix: RegExp | null;
  /** A sentence under the Calendar about what it can and cannot show for this state ("" = none). */
  calendarNote: string;
  /** Health "intake" rows: a completeness-payload key, its label, and the most that is still clean (grey). */
  intakeChecks: { key: string; label: string; limit: number; cat: "Accuracy" | "Completeness" }[];
}
