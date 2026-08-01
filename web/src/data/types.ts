// The bill record shape emitted by bill_tracker.py into the Bill_Tracker tab, plus the derived
// product types the UI works in. Everything here is structural (Standard #3) — no probabilistic guesses.

export type Outcome =
  | "signed" | "vetoed" | "dead" | "carried_over" | "awaiting_governor" | "in_progress";

export type Chamber = "House" | "Senate";

// A chamber-floor event from LIS's controlled vocabulary: "passed" (cleared that floor), "defeated"
// (reached that floor and was voted down — the Timeline places its ✕ at Floor), "" (no floor event).
export type FloorEvent = "" | "passed" | "defeated";

export interface LatestVote {
  tally: string;     // DISPLAY of LIS's own published tally, e.g. "15-Y 0-N"
  location: string;  // structural: committee name from the vote refid, else "Floor"
  date: string;
}

export interface Meeting {
  date: string;
  committee: string;
}

export interface HistoryRow {
  action: string;
  date: string;
}

export interface Bill {
  bill: string;            // clean id, e.g. "HB1"
  title: string;           // catchline
  statusLis: string;       // LIS's authoritative status string (always shown)
  outcome: Outcome;        // structural-first convenience label
  patron: string;          // chief patron (surname today; full name once upgraded)
  patronId: string;        // LIS member number, e.g. "H0173"
  chamber: Chamber;        // current chamber (origin until it crosses)
  crossedOver: boolean;    // a committee action in the chamber opposite origin
  floorHouse: FloorEvent;  // House floor: "passed" | "defeated" (reached the floor, voted down) | ""
  floorSenate: FloorEvent; // Senate floor: same enum — Timeline Floor stages
  lastCommittee: string;   // chamber-qualified, e.g. "Senate Finance and Appropriations"
  referrals: number;       // distinct sequential committees (the Nth-referral badge)
  latestVote: LatestVote;
  upcoming: Meeting[];     // future committee meetings (empty off-season)
  lastAction: string;      // date of the most recent history row
  history: HistoryRow[];   // [{action, date}] — newest-handling is the UI's job
  dataAsOf: string;        // ISO UTC the record was built
  /** LIS's own LegislationClass. "" when the class call failed — an honest blank, never a guess. */
  legislationClass: string;
  source: string;          // "LIS"
}

// The completeness / trust payload written to R1 of the tab.
export interface Completeness {
  universe_count: number;
  records_written: number;
  history_bills: number;
  prefiled_no_history: number;
  in_history_not_in_universe: string[];
  skipped_malformed_universe: number;
  docket_unparseable_dates?: number;
  docket_rows_total?: number;
  docket_unparseable_rate?: number;
  bills_meta_rows?: number;
  bills_skipped_no_bill?: number;
  outcome_structural?: number;
  outcome_keyword_fallback?: number;
  patron_present?: number;
  patron_missing?: number;
  // LIS's status STRING disagreeing with LIS's own FLAGS. We publish the flag (the oracle), so this measures
  // UPSTREAM internal consistency — NOT our accuracy. It must never drive the Accuracy ring: doing so is what
  // turned the ring red on 2026-07-25 while every published value was correct.
  outcome_keyword_mismatches?: number;
  outcome_keyword_mismatch_rate?: number;
  // OUR accuracy signals (W0c). `impeached` = we published a value later shown wrong. `unverified` = we
  // published a text-derived outcome no structural flag confirms; split into `_terminal` (its own status says
  // SETTLED yet no flag exists — the real anomaly, no legitimate steady state) and `_absent` (still in
  // progress, so no flag is owed yet — expected, disclosed, never alarmed).
  outcome_impeached?: number;
  outcome_unverified?: number;
  outcome_unverified_rate?: number;
  outcome_unverified_terminal?: number;
  outcome_unverified_absent?: number;
  checked_at_utc?: string;
  session_code?: string;   // authoritative 5-digit code if the backend stamps it (preferred over inference)
  // LIS's OWN words for the session ("2026 Special Session I") from Session/api/GetSessionListAsync's
  // DisplayName + SessionYear. Optional: absent on a pre-migration sheet, or "" when the lookup failed —
  // both mean "show the raw code", never "invent a label from the code's last digit".
  session_display?: string;
}

export interface BillData {
  bills: Bill[];
  completeness: Completeness | null;
  dataAsOf: Date | null;   // freshest record timestamp
  sessionCode: string;     // derived "20261" — for the LIS bill link
}
