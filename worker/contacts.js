/**
 * The contact log's write rules (migrations/0002_contact_log.sql) — pure, so the test checks the SAME function the
 * Worker runs. Owner, 2026-09-28: "a simple name date and note so whoever is using knows who contacted."
 *
 * Required: state, session_code, a date (YYYY-MM-DD, a real calendar day), a name, a note, and a bill OR a
 * legislator. Optional: tone -- absent stays absent (null), never defaulted to 'neutral' (#53).
 */
const TONES = new Set(["positive", "neutral", "negative"]);
const MAX_NOTE = 2000;
const MAX_NAME = 80;

/** A real calendar date in ISO form. The schema checks the SHAPE; this checks the day exists (no 2026-02-31). */
export function isIsoDay(s) {
  if (typeof s !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(`${s}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

/** -> { error } or { row } with every column the INSERT needs. `email` is the VERIFIED caller, never the body. */
export function validateContact(body, email, nowIso) {
  if (!body || typeof body !== "object") return { error: "body must be JSON" };
  const str = (v) => (typeof v === "string" ? v.trim() : "");
  const state = str(body.state), session = str(body.session_code);
  if (!/^[A-Z]{2}$/.test(state)) return { error: "state must be a 2-letter code" };
  if (!session) return { error: "session_code is required" };
  const bill = str(body.bill_number) || null, member = str(body.member_number) || null;
  if (!bill && !member) return { error: "a bill_number or a member_number is required" };
  if (!isIsoDay(body.occurred_on)) return { error: "occurred_on must be a real date, YYYY-MM-DD" };
  const actor = str(body.actor);
  if (!actor) return { error: "a name is required (who made the contact)" };
  if (actor.length > MAX_NAME) return { error: `name must be at most ${MAX_NAME} characters` };
  const note = str(body.note);
  if (!note) return { error: "a note is required" };
  if (note.length > MAX_NOTE) return { error: `note must be at most ${MAX_NOTE} characters` };
  const tone = body.tone == null || body.tone === "" ? null : body.tone;
  if (tone !== null && !TONES.has(tone)) return { error: "tone, if given, must be positive, neutral or negative" };
  return { row: { state, member, session, bill, occurred_on: body.occurred_on, actor, tone, note,
                  created_at: nowIso, created_by: email } };
}
