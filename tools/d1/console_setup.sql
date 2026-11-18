-- One paste for a NEW state's D1 database in the Cloudflare dashboard Console (Storage & Databases -> D1 -> <db> ->
-- Console). It creates the end state of migrations/0001..0003 directly (same tables, columns, checks and indexes)
-- and records those three migrations as applied, so a later `wrangler d1 migrations apply` skips them.
CREATE TABLE IF NOT EXISTS positions (state TEXT NOT NULL CHECK (state GLOB '[A-Z][A-Z]'), session_code TEXT NOT NULL, bill_number TEXT NOT NULL, stance TEXT NOT NULL CHECK (stance IN ('involved','supporting','watching','opposing')), updated_at TEXT NOT NULL, updated_by TEXT NOT NULL, PRIMARY KEY (state, session_code, bill_number));
CREATE TABLE IF NOT EXISTS interactions (id INTEGER PRIMARY KEY, state TEXT NOT NULL CHECK (state GLOB '[A-Z][A-Z]'), member_number TEXT, session_code TEXT NOT NULL, bill_number TEXT, occurred_on TEXT NOT NULL CHECK (occurred_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'), actor TEXT NOT NULL, tone TEXT CHECK (tone IS NULL OR tone IN ('positive','neutral','negative')), note TEXT, created_at TEXT NOT NULL, created_by TEXT, CHECK (member_number IS NOT NULL OR bill_number IS NOT NULL));
CREATE INDEX IF NOT EXISTS idx_interactions_member ON interactions (state, member_number, occurred_on DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_bill ON interactions (state, session_code, bill_number, occurred_on DESC);
CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, display_name TEXT, home_state TEXT CHECK (home_state IS NULL OR home_state GLOB '[A-Z][A-Z]'), district_house TEXT, district_senate TEXT, district_congress TEXT, districts_confirmed_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS alert_state (state TEXT NOT NULL CHECK (state GLOB '[A-Z][A-Z]'), session_code TEXT NOT NULL, bill_number TEXT NOT NULL, snapshot TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (state, session_code, bill_number));
CREATE TABLE IF NOT EXISTS d1_migrations (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);
INSERT OR IGNORE INTO d1_migrations (name) VALUES ('0001_init.sql'), ('0002_contact_log.sql'), ('0003_alert_state.sql');
