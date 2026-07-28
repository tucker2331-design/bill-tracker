-- F2 write path — initial schema.
--
-- DESIGN RULES THIS SCHEMA ENCODES:
--  * `member_number` (H0285 / S0098) is the join key everywhere a legislator is referenced. It is the SAME
--    namespace as VOTE.CSV and the roster API, so votes <-> roster <-> our intel join with no mapping table
--    (Standard #3, structural not text). NEVER store a legislator by name.
--  * There is NO address column, anywhere, by design. We store the three districts a user CONFIRMS; the
--    Census lookup that resolves an address is transient (docs/knowledge/district_lookup.md).
--  * `stance` is the closed ladder settled with the owner: involved / supporting / watching / opposing.
--    CHECK constraints make an unknown value a write failure rather than silent bad data.

CREATE TABLE IF NOT EXISTS positions (
  session_code TEXT NOT NULL,
  bill_number  TEXT NOT NULL,
  -- involved = we wrote it and/or got it introduced. A claim of fact, org-asserted, never shown as sourced.
  stance       TEXT NOT NULL CHECK (stance IN ('involved','supporting','watching','opposing')),
  updated_at   TEXT NOT NULL,
  updated_by   TEXT NOT NULL,
  PRIMARY KEY (session_code, bill_number)
);

CREATE TABLE IF NOT EXISTS interactions (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  member_number TEXT NOT NULL,
  session_code  TEXT NOT NULL,
  bill_number   TEXT,                       -- NULL = a general contact, not tied to one bill
  occurred_on   TEXT NOT NULL,              -- ISO date; the day it happened, not when it was logged
  actor         TEXT NOT NULL,              -- who from the org made contact
  tone          TEXT NOT NULL CHECK (tone IN ('positive','neutral','negative')),
  note          TEXT,
  created_at    TEXT NOT NULL
);
-- The call sheet reads "this member, newest first" on every open. Without this it is a full scan.
CREATE INDEX IF NOT EXISTS idx_interactions_member ON interactions (member_number, occurred_on DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_bill   ON interactions (session_code, bill_number);

CREATE TABLE IF NOT EXISTS users (
  email                  TEXT PRIMARY KEY,  -- from the Access JWT; we never store a password
  display_name           TEXT,              -- what to call them when they phone an office
  district_house         TEXT,
  district_senate        TEXT,
  district_congress      TEXT,              -- collected for the federal product, not displayed here
  districts_confirmed_at TEXT,              -- drives the 6-month re-ask; NULL = never confirmed
  created_at             TEXT NOT NULL
);
