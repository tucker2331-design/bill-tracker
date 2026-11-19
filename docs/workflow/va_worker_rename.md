---
tags: [workflow, cloudflare, virginia, owner-step]
updated: 2026-11-19
status: active
open_loop: Rename the Virginia Worker bill-tracker → bill-tracker-va (owner asked 2026-11-19, parked "for later"). Steps below; the code change waits until the owner renames it in Cloudflare.
---

# Rename the Virginia site to `bill-tracker-va` (parked for later)

Owner, 2026-11-19: "the va is named out of order … can we rename it to match the schema?" — then "add it to a to do
for later". The schema is `bill-tracker-<state>`: PA is `bill-tracker-pa`, CA `bill-tracker-ca`, Virginia is still
`bill-tracker` (the first site, named before there were others).

## What changes
- The address: `https://bill-tracker.tucker2331.workers.dev` → `https://bill-tracker-va.tucker2331.workers.dev`.
  The old link stops working; anyone with a bookmark needs the new one.
- **Rename the Worker in Cloudflare — never create a new one.** A rename keeps its secrets (`TEAM_EMAILS`,
  `GCP_SA_JSON`, `GH_DISPATCH_TOKEN`, `SLACK_WEBHOOK_URL`), its D1 binding and its `*/15` cron — the cron is what
  dispatches Virginia's GitHub ticks ([[knowledge/lis_api_safety]]). A new Worker would start with none of them and
  Virginia's updates would stop.
- `wrangler.toml` `name` must equal the Worker's name, or the next `main` build fails (Workers Builds checks it).
  So the code change lands right AFTER the rename, never before.
- The D1 database keeps its name (`bill-tracker-db`): Cloudflare cannot rename D1 databases and nothing keys on it.

## Steps, in order
1. Owner — Google sign-in: the OAuth client `831223695835-cqd2…` → Authorized JavaScript origins → **add**
   `https://bill-tracker-va.tucker2331.workers.dev` (keep the old origin until step 4).
2. Owner — Cloudflare: Workers & Pages → `bill-tracker` → Settings → rename to `bill-tracker-va`. If no rename is
   offered: stop (do not create a new Worker).
3. Claude — set `name = "bill-tracker-va"` in `wrangler.toml`, update `docs/state/current_status.md` (Live site line)
   and `docs/audits/build_wave_2026-07/README.md`, merge, then check the new address: `/api/health`, the page, and the
   Google sign-in button (the same checks used for CA on 2026-11-19).
4. Owner — remove the old `https://bill-tracker.tucker2331.workers.dev` origin from Google sign-in.
