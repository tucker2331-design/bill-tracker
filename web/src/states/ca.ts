// California — its own site, built from the same code with VITE_STATE=CA. Mirrors the Python states/ca.py: two-year
// session, a house-of-origin deadline (the crossover marker), chaptering or veto, the Assembly shown as a label.
// Data: Legislative Counsel's pubinfo bulk database (public domain, Gov. Code §10248.5), refreshed DAILY.
import type { StateConfig } from "./types";

export const CA: StateConfig = {
  code: "CA",
  name: "California",
  appName: "CA Bill Tracker",
  sourceName: "California Legislature (Legislative Counsel pubinfo)",
  sourceLongName: "the California Legislature (Legislative Counsel's pubinfo database)",
  legislatureName: "the Legislature",
  chambers: { A: "House", S: "Senate", H: "House" },
  chamberLabels: { House: "Assembly", Senate: "Senate" },
  billIdPattern: /^(AB|SB|ACA|SCA|ACR|SCR|AJR|SJR|HR|SR)\d+$/,
  stages: [
    { id: "introduced", label: "Introduced" },
    { id: "committee1", label: "Committee" },
    { id: "floor1", label: "Floor" },
    { id: "crossover", label: "House of origin deadline", marker: true },
    { id: "committee2", label: "Committee" },
    { id: "floor2", label: "Floor" },
    { id: "concurrence", label: "Concurrence / enrollment" },
    { id: "governor", label: "Governor" },
    { id: "law", label: "Chaptered" },
    { id: "adopted", label: "Adopted" },
  ],
  sessionYears: 2,
  crossoverBySession: {},
  // leginfo bill pages sit behind a bot challenge and are never fetched; no per-bill link is guessed.
  billUrl: () => "",
  features: { calendar: false, timeline: true, warroom: true, predictions: false, committeeRoster: false, summaries: false, health: "intake" },
  actionCodePrefix: null,
  jobDaysUTC: [0, 1, 2, 3, 4, 5, 6],
  pipelineMap: {
    stations: ["introduced", "committee1", "floor1", "committee2", "floor2", "concurrence"],
    otherChamber: ["committee2", "floor2"],
    mapBills: /^(AB|SB)\d/,
    idleDays: 365,
    governorOutcomes: ["signed", "vetoed", "awaiting_governor"],
    endedOutcomes: ["dead"],
    parkedOutcomes: [],
    stageSource: "pipeline",
    swapLabel: "House of origin deadline",
    endedWord: "died",
    parkedWord: "parked",
  },
  calendarNote: "",
  intakeChecks: [
    { key: "end_status_unclassified", label: "Actions with a status we do not recognise", limit: 0, cat: "Accuracy" },
    { key: "titles_blank", label: "Bills with no subject line in the source (House and Senate resolutions)", limit: 300, cat: "Completeness" },
  ],
};
