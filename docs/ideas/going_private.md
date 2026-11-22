---
tags: [ideas, security, github, privacy, owner-request]
updated: 2026-11-22
status: active
open_loop: Repo going private (owner 2026-11-19) — do NOT flip until your §D step 1 is done (VA key, then sheets Restricted). Engineering side done: A2, headers, tick gate (~1,840 min/month measured, A1‴), workflow token rights. Your calls: Actions budget, review bot, contact address.
---

# Going private: checklist and security audit (owner, 2026-11-19)

> *"im getting ready to change the github repository to private so prepare what ever to make sure everything goes
> prviate and nothing gets broken off, also make there there are no keys anywhere public at all … look in reddit data
> security threads about ai built app secuiry vulnerabilities and try to identify them in the things weve built"*

Claim classes: **[sourced]** = a file, command or page named beside it; **[derived]** = computed from sourced facts;
**[owner check]** = I could not see it from here.

## Verdict
- **No live keys anywhere in the code or its history.** Every file version in all 1,894 commits on 91 branches was
  scanned (`python3 tools/secret_scan.py --history`, plus a wider pattern pass) [sourced].
- **0 forks, no GitHub Pages** [sourced: GitHub search API, 2026-11-19], so flipping leaves no public copy on GitHub.
- **Don't flip yet.** The two things that would have broken are fixed: the Actions minutes (A1: ~1,840 a month
  measured against 2,000 free, A1‴) and the Virginia Health page (A2). What's left is your §D step 1, in that order.

## A. What breaks when the repo goes private
| # | what | what happens | fix | who |
|---|---|---|---|---|
| A1 | **GitHub Actions minutes** (tick gate built 2026-11-20; measure after merge) | Public repos run free. A private repo on the Free plan gets **2,000 minutes a month** [sourced: docs.github.com Actions billing]. We use about **9,000–13,000 a month with the legislature out of session** [derived: last 100 runs = 6.0 h and 109 billed minutes (each run billed at least 1) → 13,045 per 30 days; the 15-minute ticks alone start 3 runs each → 8,640]. In session, more. Past 2,000 the jobs stop unless billing is on; extra Linux minutes cost $0.006 [sourced: GitHub runner pricing], about **$40–66 a month** off-session [derived]. | (1) Cut idle runs: let the Cloudflare tick check whether there is work before it starts a job (most off-session ticks start a job that exits at once), and run the accuracy sentinel only after a worker actually wrote. (2) Measure a week. (3) Pay for what is left (set an Actions budget). | me, then your call on the budget |
| A1′ | **Expected after the tick gate** (VA at daily, off-session) | [derived] calendar ~1 full cycle (~8 min) + ~3.4 GitHub-cron skips a day; bill ~1 (~3 min) + ~3.4; sentinel ~4.4 → **~670 min/month** for the three (was ~9,000). Other scheduled jobs ~610 (CA 278, PA 76, NY 76, retention 102, guard 51, sentinel cron 25). CI on PRs: see A1‴ (measured ~500/month; the "~1,190 on a busy day" first written here did not reproduce). Total **~1,840/month at November's pace** (A1‴). In session at a faster speed, real cycles add up: budget for paid minutes then. | measure the first week after merge |
| A1″ | **Measured day 1 (2026-11-21)** | [sourced: 200 runs, 02:16–18:01 UTC] the gate was **not active**: calendar and bill each dispatched 63× (every tick), sentinel 66×, ~207 billed min in 15.75 h (~9,500/month, no better). The workers DO write `Tick_Gate` (logs: "next calendar cycle due 22:56 UTC", "next bill cycle due 19:46 UTC"); the Cloudflare reader required the service account, which the VA Worker does not have yet, so it read "unavailable" and offered every job (the designed fail-open). Fixed 2026-11-21: it reads the tab like every `/api/sheet` read, with the key when set, otherwise the link-shared sheet. **Re-measured after #281 (2026-11-21, 18:30–22:15 UTC):** calendar 0 and bill 1 tick-started job (19:45, its due time was 19:46) against 14 and 14 in the 3.75 h before; the sentinel followed 1 calendar run instead of ~14. **The gate works.** **Full day (2026-11-21 18:30 → 11-22 16:46 UTC, 22.3 h, a weekend with no PRs):** 23 runs, ~39 billed min → **~1,260 min/month** [derived; each run billed at least 1 min] against 2,000 free (was ~11,000). Calendar 1 full cycle (7 min), bill 2, sentinel 5, GitHub-cron backups 8, CA/NY/guards/retention the rest. Not in the window: PA (runs weekdays, ~76/month measured earlier) and CI on PRs (A1‴). | done |
| A1‴ | **CI on PRs, measured 2026-11-22** | [sourced: every PR-triggered run 2026-11-02 17:52 → 11-22 18:30 UTC, 20 days: 100 runs on 36 PR commits, plus 13 merges to `main`] A commit runs 5 jobs (structural-tests 1, prepush-audit 1, web-build 2 at ~80 s, mypy 1, Semgrep 1 billed min) plus golden-tests (1) when worker files change (29 of 36): 36×6 + 29 = 245 min on PRs, ~88 on merges → **~330 in 20 days, ~500/month** [derived; each job billed at least 1 min, rounded up]. Busiest day (11-19): ~90. The earlier "~1,190 on a busy day" did not reproduce and is withdrawn. **Month total at this pace: ~1,260 scheduled + ~76 PA + ~500 CI ≈ 1,840 of 2,000.** Trims considered and not made: skipping web-build when `web/`/`worker/` are untouched (18 of 36 commits) and Semgrep/mypy on docs-only commits (4 of 36) would save ~66/month (3%) and the web-build filter would need its file list kept in sync with what the build reads (`cadence_profiles.json` sits outside `web/`). Not worth the risk. In session, faster worker cycles add minutes, so a small Actions budget is still the safe call then. | your budget call |
| A2 | **Virginia Health page** ✅ fixed 2026-11-20 | `web/src/data/verification.ts` and `guards.ts` read GitHub's public API from the browser with no token. Private → every guard and run history shows "unknown" (red). It fails safe, but the page goes red. | The trust-surface guard already reads GitHub with the Actions token every 6 h and writes `Guard_Status` to the sheet. Have it also write the run history and the four guard verdicts there; the page reads them through the Worker like everything else. No new key, so nothing new expires. (Runner-up: a Worker route with a read-only token: live, but one more token to renew yearly.) | me |
| A3 | **Streamlit (X-Ray)** | Community Cloud allows **one private app per workspace**, and an app deployed from a private repo counts as that one [sourced: docs.streamlit.io "Share your app"]. | Re-authorize Streamlit's GitHub access for private repos. If more than one app deploys from this repo, only one survives. | owner check |
| A4 | **Cloudflare builds** (VA, PA, CA) | The Cloudflare GitHub app must have access to the now-private repo. | After the flip, merge a tiny change and watch all three builds run. | owner check |
| A5 | **Cloudflare ticks token** | `GH_DISPATCH_TOKEN` is fine-grained, this repo only, Actions read & write [sourced: [[knowledge/lis_api_safety]]], so it keeps working. | Note its expiry date; fine-grained tokens expire. | owner |
| A6 | **Code review bot** | CodeRabbit's free plan on private repos gives PR summaries only, no reviews [sourced: docs.coderabbit.ai plans]. Semgrep, mypy, pyflakes and the pre-push audit keep running (they use Actions minutes). | Decide: pay, self-host PR-Agent ([[workflow/reviewer_strategy]]), or rely on the deterministic checks. | your call |
| A7 | **GitHub's free secret scanning** | Covers public repos; not included for a private personal repo. | **Done in this PR:** `tools/secret_scan.py` runs on every push (pre-push audit point 18, and CI). | done |
| A8 | **Contact line we send to data sources** | PA and NY fetchers identify us by the repo URL ("contact = the repo", owner 2026-11-01). Private → that link 404s for the site operators. 14 older research scripts in `tools/` put your personal Gmail in their User-Agent, which goes to outside sites (GDELT, the Internet Archive, …). | Pick a project contact address (not personal); I swap it in everywhere. | your call, then me |
| A9 | Links to GitHub run pages in docs and the Health page | Fine for you (a collaborator); clients never see them. | — | — |

## B. Keys and personal data
- **Public by design, not secrets:** the Google sign-in client ID (it ships in every sign-in page), the two LIS
  `WebAPIKey` values (LIS's own website sends them; [[knowledge/lis_api_reference]]), and sheet / D1 IDs (access is
  controlled by sharing and the Worker's gate).
- **Removed in this PR:** `.wrangler/` (the local Cloudflare dev folder) was committed. It held the Cloudflare account
  ID and your email, and a local test database (2 test rows, no real data) [sourced]. It is now untracked and ignored;
  `.gitignore` also covers `.env`, `.dev.vars`, `.streamlit/secrets.toml`.
- **Public until the flip:** your Gmail (15 files today, and every commit's author line), client names and plans in
  `docs/`, and the Actions logs. Going private hides them from new viewers; anyone who already cloned keeps a copy.
  Going forward: GitHub → Settings → Emails → "Keep my email addresses private".

## C. Common holes in AI-built apps, checked against what we built
What people keep finding in AI-built apps [sourced, §Sources]: keys in the code or the browser, databases open to
anyone (Supabase with row-level security off: CVE-2025-48757, 170+ Lovable apps), API routes without a sign-in
check, source maps and debug mode left on, no security headers, no rate limits, and leaky CI. Veracode found
security flaws in 45% of AI-written code samples.

| common hole | ours | evidence |
|---|---|---|
| keys in the code or browser bundle | none | full-history scan; the CA bundle holds only the public sign-in client ID |
| database open to anyone | protected | D1 sits behind the Worker; every route needs a verified Google sign-in AND the team list; one database per state; parameterized queries (`worker/index.js`) |
| API routes without a sign-in check | protected | live check of CA from outside: `/api/sheet`, `/api/positions`, `/api/me` all answer 401; `/api/health` shows configuration yes/no only |
| sign-in token not checked properly | protected | `worker/auth.js`: RS256 only, Google's keys, audience, issuer, expiry, verified email |
| **our version of "open database": the Google Sheets** | **[owner check]** | The sheet IDs are in the public repo. Until each sheet is *Restricted*, anyone with an ID can read every tab, and the "whole app goes private" step 4 is still open on the to-do. VA, PA, CA, NY: Share → General access → Restricted (the service account stays an editor). |
| internal dashboard public | **[owner check]** | Streamlit X-Ray: app settings → Sharing → private. The legacy page `pages/v2_shadow_test.py` has a "Force Manual Sync" button that starts a GitHub workflow with a token from Streamlit's secrets: if the app is public, anyone can press it. Recommend deleting that paused page. |
| source maps / debug in production | OK | CA: `.js.map` is not served; API errors answer "internal error", details stay in server logs |
| security headers | ✅ fixed 2026-11-20 | Every Worker response now carries frame-ancestors 'none', X-Frame-Options, nosniff, Referrer-Policy and Permissions-Policy (`worker/headers.js`, tested). A full script-src policy is a separate change: it must allow Google sign-in and be tried in a real browser. |
| rate limits | low risk | every data route needs a team sign-in; `/api/health` is static configuration |
| vulnerable packages | OK in production | `npm audit`: 0 in what ships; 17 in build-only dev tools (moderate/high denial-of-service) → `npm audit fix` later |
| leaky CI | OK | no `pull_request_target`; no PR text pasted into shell steps; only GitHub's own actions; fork PRs get no secrets |
| workflow token permissions | ✅ fixed 2026-11-22 | 25 of 38 workflows set no `permissions:` block and inherited the repo default. Each one now declares its rights: `contents: read` for the 23 that only check out the code (sheet writes use `GCP_CREDENTIALS`, not the GitHub token), `{}` for the Slack test (no checkout); the 13 that already declared keep theirs (2 need more: the guard reads run history, the backfill burst dispatches). `api_test.yml`, a Python script saved as a workflow that GitHub could never run, is deleted. Pre-push audit point 19 (`tools/workflow_permissions.py`) fails CI if a workflow stops declaring. Your Settings → Actions → General → Workflow permissions → **Read** step is now safe, and still worth doing for anything added outside the audit. |
| prompt injection | n/a | no AI model runs inside the product |

Limits: my sandbox can't reach the VA and PA sites or Google Sheets, so the live checks ran on CA (same code).

## D. The order
1. **Owner, about 15 minutes:** **first** give the VA Worker its service-account key (`npx wrangler secret put GCP_SA_JSON`, the same JSON the GitHub workers use; CA already has one) and check a `/api/sheet` answer says `x-sheet-auth: service_account`, **then** set every sheet Restricted (VA, PA, CA, NY). In the other order the VA site stops loading (measured 2026-11-21: the VA Worker reads its sheet without a key today); Streamlit app private + how many apps deploy
   from this repo; Actions workflow permissions → Read; commit email private.
2. **Me:** ~~A2 Health reads via the sheet~~ (done 2026-11-20: the guard publishes LastRunUTC + Recent, the page reads
   Guard_Status); ~~security headers~~ (done); ~~A1 idle-run cut~~ (built 2026-11-20: the Tick_Gate tab, [[knowledge/lis_api_safety]]), then a week of minute counts (measured: A1‴); ~~workflow token rights~~ (done 2026-11-22, audit point 19); delete the legacy
   force-sync page (with your OK); the contact swap (after you pick the address).
3. **Your calls:** the Actions budget for what's left after the cut; the review bot (A6).
4. **Flip:** GitHub → Settings → General → Danger Zone → Change visibility → Private.
5. **After:** merge a tiny PR; check the three Cloudflare builds, one worker run, the Health page, Streamlit.

## Sources
- GitHub: [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) ·
  [runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing) ·
  [2026 pricing changes](https://github.com/resources/insights/2026-pricing-changes-for-github-actions) ·
  [visibility changes](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
- [Streamlit: share your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app) ·
  [CodeRabbit plans](https://docs.coderabbit.ai/management/plans)
- AI-built app holes: [Lovable RLS exposure](https://www.superblocks.com/blog/lovable-rls-breach) ·
  [CVE-2025-48757](https://vibeappscanner.com/cve-2025-48757) ·
  [Veracode GenAI code report](https://www.veracode.com/press-release/ai-generated-code-poses-major-security-risks-in-nearly-half-of-all-development-tasks-veracode-research-reveals/) ·
  [vibe security checklist](https://nmn.gl/blog/vibe-security-checklist) ·
  [25-check pre-launch list](https://dev.to/hacksafe/the-vibe-coders-pre-launch-security-checklist-25-checks-for-cursor-lovable-bolt-replit-apps-12i).
  The searches returned blogs and vendor write-ups rather than Reddit threads themselves; counts in vendor posts vary.
