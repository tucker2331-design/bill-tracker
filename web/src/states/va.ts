// Virginia. Every value here was a literal somewhere in web/src before the multi-state split (2026-10-31);
// states/__tests__/va.regression.mjs pins each one to the exact pre-split output.
import type { StateConfig } from "./types";

export const VA: StateConfig = {
  code: "VA",
  name: "Virginia",
  appName: "VA Bill Tracker",
  sourceName: "LIS",
  sourceLongName: "Virginia LIS",
  legislatureName: "the General Assembly",
  chambers: { H: "House", S: "Senate" },
  billIdPattern: /^[HS][BJR]\d+$/, // HB/SB/HJ/SJ/HR/SR + number
  // The crossover-lane pipeline (data/derive.ts `Stage`): origin committee + floor, the crossover deadline, the
  // second chamber, the Governor. Same ids as Python states/va.py.
  stages: [
    { id: "prefiled", label: "Prefiled" },
    { id: "committee1", label: "Committee" },
    { id: "floor1", label: "Floor" },
    { id: "crossover", label: "Crossover", marker: true },
    { id: "committee2", label: "Committee" },
    { id: "floor2", label: "Floor" },
    { id: "governor", label: "Governor" },
  ],
  sessionYears: 1,
  crossoverBySession: {
    "20261": "2026-02-17", // 2026 Regular Session — Tue Feb 17 (last day to act in house of origin)
  },
  // Deterministic LIS bill-detail link (recovered shadow_v2.py:535) — no API, not brittle. Uses the DYNAMIC
  // 5-digit session code (never hardcode 20261).
  billUrl: (sessionCode, bill) => `https://lis.virginia.gov/bill-details/${sessionCode}/${bill}`,
  features: { calendar: true, timeline: true, warroom: true, predictions: true, committeeRoster: false, summaries: true, health: "full" },
  intakeChecks: [],
};
