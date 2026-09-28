-- Slack alerts (worker/alerts.js): the last-seen snapshot of each watched bill, so a cron run can tell what
-- CHANGED. One row per (state, bill). `snapshot` is the JSON of the four facts we alert on (LIS status, last action,
-- latest vote, next hearing). A bill with no row yet is recorded silently on first sight -- see alerts.js.
CREATE TABLE IF NOT EXISTS alert_state (
  state       TEXT NOT NULL CHECK (state GLOB '[A-Z][A-Z]'),
  bill_number TEXT NOT NULL,
  snapshot    TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  PRIMARY KEY (state, bill_number)
);
