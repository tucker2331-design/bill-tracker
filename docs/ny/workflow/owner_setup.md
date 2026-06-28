---
tags: [ny, workflow, setup]
updated: 2026-06-24
status: active
---

# New York Owner Setup

These are the owner-controlled inputs needed to move from local scaffold to live
New York dry run and write.

## 1. OpenLeg API key

Create a New York OpenLegislation API key and add it as:

- Local env: `NY_OPENLEG_API_KEY`
- GitHub secret: `NY_OPENLEG_API_KEY`

This enables `dry-run`.

## 2. New York Google Sheet

Create or choose the Google Sheet that will hold New York output. The first
write creates/updates the tab `NY_Bill_Tracker` unless `NY_BILL_TRACKER_TAB` is
set.

Add the spreadsheet ID as:

- Local env: `NY_SPREADSHEET_ID`
- GitHub secret: `NY_SPREADSHEET_ID`

Share the sheet with the existing service-account email used by
`GCP_CREDENTIALS` with editor access.

## 3. Google service account credentials

Use the same service-account JSON pattern as Virginia:

- Local env: `GCP_CREDENTIALS`
- GitHub secret: `GCP_CREDENTIALS`

If the existing service account is reused, no new key is needed; just share the
new NY sheet with that account.

## 4. First validation sequence

1. GitHub Actions -> `New York Bill Tracker` -> mode `check-config`.
2. GitHub Actions -> `New York Bill Tracker` -> mode `dry-run`.
3. Review the dry-run completeness metrics in [[ny/testing/validation_plan]].
4. Only then run mode `write`.

No scheduled workflow should be added until those steps pass and cadence is
decided.
