-- F2 write path — initial schema.
--
-- DESIGN RULES THIS SCHEMA ENCODES:
--  * `state` is on EVERY table. Added 2026-07-27 after the owner asked whether the deployment should be
--    named per-state ("btva"). It should NOT be -- ONE deployment serves every state and `state` is a data
--    dimension, because 50 deployments means 50 things to maintain (Standard #8, zero routine maintenance).
--    But that only works if the tables carry the dimension, and my first cut had NO state column at all --
--    a Virginia-only schema, which is exactly the VA-specific pattern Standard #6 forbids. Caught by the
--    naming question, fixed while the database is still empty and the change costs nothing.
--  * `member_number` (H0285 / S0098) is the join key everywhere a legislator is referenced. It is the SAME
--    namespace as VOTE.CSV and the roster API, so votes <-> roster <-> our intel join with no mapping table
--    (Standard #3, structural not text). NEVER store a legislator by name.
--  * There is NO address column, anywhere, by design. We store the three districts a user CONFIRMS; the
--    Census lookup that resolves an address is transient (docs/knowledge/district_lookup.md).
--  * `stance` is the closed ladder settled with the owner: involved / supporting / watching / opposing.
--    CHECK constraints make an unknown value a write failure rather than silent bad data.
--
-- `state` is the 2-letter USPS code ('VA', 'NY', …) and is deliberately NOT defaulted: a write that forgets
-- it must fail loudly rather than silently land in Virginia's data.

CREATE TABLE IF NOT EXISTS positions (
  state        TEXT NOT NULL,
  session_code TEXT NOT NULL,          -- session ids are per-state; '20261' means nothing without the state
  bill_number  TEXT NOT NULL,
  -- involved = we wrote it and/or got it introduced. A claim of fact, org-asserted, never shown as sourced.
  stance       TEXT NOT NULL CHECK (stance IN ('involved','supporting','watching','opposing')),
  updated_at   TEXT NOT NULL,
  updated_by   TEXT NOT NULL,
  PRIMARY KEY (state, session_code, bill_number)
);

CREATE TABLE IF NOT EXISTS interactions (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  state         TEXT NOT NULL,
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
-- A member_number is only unique WITHIN a state, so the state leads the key.
CREATE INDEX IF NOT EXISTS idx_interactions_member ON interactions (state, member_number, occurred_on DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_bill   ON interactions (state, session_code, bill_number);

CREATE TABLE IF NOT EXISTS users (
  email                  TEXT PRIMARY KEY,  -- from the Access JWT; we never store a password
  display_name           TEXT,              -- what to call them when they phone an office
  home_state             TEXT,              -- which state's site this person belongs to
  district_house         TEXT,
  district_senate        TEXT,
  district_congress      TEXT,              -- collected for the federal product, not displayed here
  districts_confirmed_at TEXT,              -- drives the 6-month re-ask; NULL = never confirmed
  created_at             TEXT NOT NULL
);
