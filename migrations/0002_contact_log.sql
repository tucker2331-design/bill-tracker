-- The contact log, simplified to what the owner asked for (2026-09-28): "a simple name date and note so whoever
-- is using knows who contacted."
--
-- WHAT CHANGES, and why each one:
--  * `tone` becomes OPTIONAL. It was NOT NULL, which forces the form to ask for it; the owner asked for name,
--    date and note only. A NULL tone means "not recorded" -- we never default it to 'neutral', because
--    'neutral' is a real answer and a default would make "didn't say" indistinguishable from "it was neutral"
--    (assumptions_audit #53, the sentinel-collision class).
--  * `member_number` becomes OPTIONAL. A contact is logged from the bill card, and the app has no legislator
--    roster to pick from yet. The rule becomes: a row must name a legislator OR a bill (CHECK below), so no row
--    can float free of both.
--  * `created_by` is NEW: the verified email of whoever typed the row. `actor` stays the name of the person who
--    MADE the contact (someone may log a colleague's call); the two are different facts and both are kept.
--
-- SQLite cannot relax NOT NULL or change a CHECK in place, so the table is rebuilt and its rows copied. At the
-- time of writing the table is empty (no UI wrote to it before this migration), so the copy is a formality --
-- but it is written to preserve rows anyway, so this file stays correct if it is ever applied to live data.

CREATE TABLE interactions_new (
  id            INTEGER PRIMARY KEY,
  state         TEXT NOT NULL CHECK (state GLOB '[A-Z][A-Z]'),
  member_number TEXT,                       -- NULL = no specific legislator recorded
  session_code  TEXT NOT NULL,
  bill_number   TEXT,                       -- NULL = a general contact, not tied to one bill
  occurred_on   TEXT NOT NULL CHECK (occurred_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  actor         TEXT NOT NULL,              -- who from the org made contact (a name, as typed)
  tone          TEXT CHECK (tone IS NULL OR tone IN ('positive','neutral','negative')),
  note          TEXT,
  created_at    TEXT NOT NULL,
  created_by    TEXT,                       -- verified email of whoever logged it; NULL only for pre-0002 rows
  CHECK (member_number IS NOT NULL OR bill_number IS NOT NULL)
);

INSERT INTO interactions_new
  (id, state, member_number, session_code, bill_number, occurred_on, actor, tone, note, created_at, created_by)
SELECT id, state, member_number, session_code, bill_number, occurred_on, actor, tone, note, created_at, NULL
  FROM interactions;

DROP TABLE interactions;
ALTER TABLE interactions_new RENAME TO interactions;

CREATE INDEX IF NOT EXISTS idx_interactions_member ON interactions (state, member_number, occurred_on DESC);
-- The bill card reads "this bill, newest first" on every open.
CREATE INDEX IF NOT EXISTS idx_interactions_bill   ON interactions (state, session_code, bill_number, occurred_on DESC);
