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
  billUrl: (sessionCode: string, bill: string) => string;
}
