// Pennsylvania — its own site, built from the same code with VITE_STATE=PA (owner 2026-11-01). Mirrors the Python
// states/pa.py: two-year session, NO crossover, concurrence, adopted resolutions. test_states.py checks the two agree.
import type { StateConfig } from "./types";

export const PA: StateConfig = {
  code: "PA",
  name: "Pennsylvania",
  appName: "PA Bill Tracker",
  sourceName: "PA General Assembly",
  sourceLongName: "the Pennsylvania General Assembly (LDPC bulk feeds)",
  legislatureName: "the General Assembly",
  chambers: { H: "House", S: "Senate" },
  billIdPattern: /^[HS][BR]\d+$/,
  stages: [
    { id: "introduced", label: "Introduced" },
    { id: "committee1", label: "Committee" },
    { id: "floor1", label: "Floor" },
    { id: "committee2", label: "Committee" },
    { id: "floor2", label: "Floor" },
    { id: "concurrence", label: "Concurrence / enrolment" },
    { id: "governor", label: "Governor" },
    { id: "law", label: "Law" },
    { id: "adopted", label: "Adopted" },
  ],
  sessionYears: 2,
  crossoverBySession: {},
  // robots.txt protects /legislation/bills/* and no page URL is verified, so no per-bill link is guessed.
  billUrl: () => "",
  features: { calendar: false, timeline: false, warroom: true, predictions: false, committeeRoster: true, summaries: false, health: "intake" },
  intakeChecks: [
    { key: "verbs_unclassified", label: "Actions with an action type we do not recognise", limit: 0 },
    { key: "action_dates_unreadable", label: "Actions with an unreadable date", limit: 0 },
    { key: "schedule_bill_refs_unmatched", label: "Committee agenda entries naming no known bill", limit: 0 },
    { key: "schedule_dates_unreadable", label: "Committee meetings with an unreadable date", limit: 0 },
    { key: "bills_committee_without_roster", label: "Bills whose committee has no published member list", limit: 0 },
  ],
};
