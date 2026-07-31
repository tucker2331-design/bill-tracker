// Agenda classification — the pure rules that decide what a meeting row IS.
//
// This module has NO runtime imports on purpose. `calendar.ts` (its only consumer) pulls in gviz + config
// and cannot be loaded by a bare `node` golden; splitting the rules out means the goldens can import and
// run the REAL code instead of a hand-maintained copy, which is the only version of a test worth having.
// Same instinct that made `classifyMeetingKind` exported in the first place (CodeRabbit #186): a
// classification buried inline is a classification nobody can test.

import type { Chamber } from "./types";   // type-only: erased at compile time, so this stays dep-free

export type MeetingKind = "floor" | "committee";

/** One marker inside a collapsed floor session — a recess, a reconvening, the adjournment. */
export interface SessionMarker { time: string; label: string; minutes: number; }

export interface AgendaItem {
  bill: string;
  action: string;
}

// Floor SESSION MARKERS (a chamber convening / reconvening / recessing / adjourning) vs actual committee
// meetings. DISPLAY-ONLY heuristic: it only chooses how a row is STYLED (quiet session tissue vs a meeting
// card) — it never hides, drops, or re-counts a row, so it is NOT the structural-completeness path Standard
// #3 governs (a misclassification shows the wrong style, never wrong/missing data). There is no structural
// floor/committee field in Sheet1 (LIS encodes it only in the meeting NAME), and the calendar WORKER already
// floor-detects on these same LIS verbs — this mirrors that classification, it doesn't invent one.
//   ASSUMES: LIS names floor markers with convene/reconvene/adjourn/recess (+ conjugations) — e.g.
//     "House Convenes", "Senate adjourned", "House recessed until…". Caucuses ("Rural Caucus") are group
//     meetings, not floor markers, so they stay "committee" (no verb match).
//   BREAKS: a committee whose name contained one of those WHOLE words would misclassify (none in the VA
//     committee list today); the pattern is word-bounded + conjugation-explicit to avoid substring over-match
//     (Gemini/Qodo #186). The relative-time "…after adjournment of X" phrase lives in the TIME field, not the
//     name, so a relative-timed committee meeting is never misread as floor.
const FLOOR_MARKER = /\b(?:re)?conven(?:es?|ed)\b|\badjourn(?:s|ed)?\b|\brecess(?:es|ed)?\b/i;
export function classifyMeetingKind(committee: string): MeetingKind {
  return FLOOR_MARKER.test(committee) ? "floor" : "committee";
}

export interface Meeting {
  dateKey: string;       // local YYYY-MM-DD
  committee: string;     // chamber-qualified meeting name ("House Appropriations", "Senate Convenes")
  chamber: Chamber | null;
  kind: MeetingKind;
  time: string;          // display, e.g. "9:00 AM" — or "Time TBA" when no concrete time is published
  tba: boolean;          // true when LIS published the meeting but no concrete time (never hidden — §7)
  minutes: number;       // sort key — minutes past midnight (from the worker's SortTime, the authority)
  unresolved: boolean;   // worker TimeClass=relative_unresolved: LIS gives only a relative time whose anchor
                         // could NOT be resolved — position unknown, so it surfaces at the TOP of the day,
                         // highlighted, instead of a silently-wrong end-of-day slot (§7.2, "never pretend")
  bills: AgendaItem[];   // real bills on the agenda (deduped; empty for skeleton/commission meetings)
  agendaUrl: string;     // the agenda PDF (worker col P) — "" when LIS hasn't posted one (common for FUTURE
                         // meetings: the livestream link exists before the agenda does → card says "not posted yet")
  meetingUrl: string;    // the livestream / "View Meeting" link (worker col Q) — "" when none
  markers: SessionMarker[]; // a collapsed floor session's recesses/adjournment; [] for a committee meeting
}

/**
 * Collapse a day's floor markers into ONE session card per chamber.
 *
 * WHY: LIS emits every parliamentary event as its own dated entry — convene, each recess, each
 * reconvening, the adjournment — and rendering them as siblings gave each the same weight as a real
 * committee hearing. MEASURED on the live calendar before this existed: 50 days carried floor cards, a
 * MEDIAN of 4 per day and up to 9, and on the worst day (2026-03-14) all NINE carried zero bills. A day
 * where nothing was heard was spending nine cards saying so.
 *
 * A chamber sits ONCE a day; the recesses are the shape of that one sitting, not separate gatherings.
 * So they become `markers` inside the session card. Nothing is dropped — every marker, time and bill
 * survives, it just stops competing for the eye.
 *
 * Grouping is by (day, chamber), which is structural: `chamber` is derived from the meeting name's own
 * prefix upstream, not re-parsed here. A floor marker with NO chamber is left alone rather than guessed
 * into a group — it stays its own card, honestly unattributed.
 */
export function collapseFloorSessions(ms: Meeting[]): Meeting[] {
  const out: Meeting[] = [];
  const groups = new Map<string, Meeting[]>();
  for (const m of ms) {
    if (m.kind !== "floor" || !m.chamber) { out.push(m); continue; }
    const g = groups.get(m.chamber);
    if (g) g.push(m); else groups.set(m.chamber, [m]);
  }
  for (const group of groups.values()) {
    if (group.length === 1) { out.push(group[0]); continue; }
    // Earliest first. A non-concrete time sorts to end-of-day upstream, so the head is a real clock
    // time whenever the chamber published one — i.e. the convening.
    const sorted = [...group].sort((a, b) => a.minutes - b.minutes);
    const head = sorted[0];
    const merged: Meeting = {
      ...head,
      bills: [],
      markers: sorted.map((s) => ({ time: s.time, label: s.committee, minutes: s.minutes })),
      // Adopt the first link of each kind that exists anywhere in the sitting — a livestream posted
      // against the convening covers the whole day.
      agendaUrl: sorted.find((s) => s.agendaUrl)?.agendaUrl ?? "",
      meetingUrl: sorted.find((s) => s.meetingUrl)?.meetingUrl ?? "",
      // Honesty flags are UNIONS, never averages: one unplaceable marker makes the sitting unplaceable,
      // and the sitting only reads "Time TBA" when not one marker carried a clock.
      unresolved: sorted.some((s) => s.unresolved),
      tba: sorted.every((s) => s.tba),
    };
    for (const s of sorted) {
      for (const b of s.bills) {
        if (!merged.bills.some((x) => x.bill === b.bill)) merged.bills.push({ ...b });
      }
    }
    merged.bills.sort((a, b) => a.bill.localeCompare(b.bill, undefined, { numeric: true }));
    out.push(merged);
  }
  return out;
}
