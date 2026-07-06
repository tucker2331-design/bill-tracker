---
tags: [workflow, deploy, hosting, cloudflare, va]
updated: 2026-07-04
status: active
---

# Deploy the web app to Cloudflare Pages (the decided host)

Platform decided 2026-06-18 ([[log]]): **React + Vite on Cloudflare Pages** — chosen over Streamlit for
the rich crossover-timeline interactivity, $0, never-sleeps CDN. The app reads live data client-side from
the Google Sheet via gviz (CORS-open, link-readable), so **a deployed build shows real production data
immediately** — and every push auto-rebuilds, so the flaky local Vite preview is retired.

## What's already prepped in the repo (done)
- `wrangler.toml` (repo root) — the deploy config. The project deploys via **Cloudflare Workers Static
  Assets** (the build log shows `wrangler` deploying a Worker named `bill-tracker` reading root `dist/`, not
  a classic Pages upload). SPA fallback is done here with `not_found_handling = "single-page-application"`.
- `package.json` (repo root) — build shim: `npm run build` → builds `web/` and copies `web/dist` → `./dist`
  (so a repo-ROOT build produces the assets `wrangler.toml` deploys). #196.
- `web/.node-version` = `22` — matches Vite 8's Node requirement so Cloudflare's build env doesn't drift.
- ~~`web/public/_redirects`~~ **REMOVED (2026-07-05, PR that fixed the deploy).** See the SPA-loop box below.

## ⚠️ THE #2 MISTAKE — `_redirects` SPA catch-all loops on Workers Assets
Symptom (build reaches "Deploying" then fails):
```
✘ [ERROR] A request to the Cloudflare API (/accounts/…/workers/scripts/bill-tracker/versions) failed.
  Invalid _redirects configuration:
    Line 4: Infinite loop detected in this rule. This would cause a redirect to strip `.html` or `/index`…
```
Cause: the classic Pages SPA rule `/*  /index.html  200` is **invalid on Workers Static Assets** — Workers
Assets canonicalises `/index.html` → `/`, which re-matches `/*`, so the rewrite loops and wrangler rejects it.
(A classic Pages project would accept the same rule — so this error *is* the proof you're on Workers Assets.)
Fix (done): deleted `web/public/_redirects` and put SPA routing in `wrangler.toml` →
`[assets] not_found_handling = "single-page-application"` (serves `index.html` for any non-asset path, no
loop). If this is ever reconnected as classic **Pages**, `wrangler.toml` is ignored and you re-add
`web/public/_redirects` with `/*  /index.html  200`.

## ⚠️ THE #1 MISTAKE — Root directory MUST be `web`
The app is in `web/`, not the repo root. If Root directory is left blank, Cloudflare runs `npm run build`
at the repo root, finds **no `package.json`** (it's `web/package.json`), and the build fails with:
```
npm error enoent Could not read package.json: ... open '/opt/buildhome/repo/package.json'
```
It will ALSO waste time auto-installing the workers' Python deps (streamlit, altair, …) from the root
`requirements.txt` — another symptom of building at the root. **Setting Root directory = `web` fixes both**
(the build context becomes `web/`, which is pure Node). The wizard hides this field under "Advanced," so it
is the single easiest thing to miss.

### If your build already failed with that error (fix the existing project — no re-create)
1. Open the Pages project → **Settings** → **Builds & deployments** (a.k.a. "Build configuration").
2. Find **Root directory** → set it to **`web`** → **Save**.
3. While there, confirm **Build command** = `npm run build` and **Build output directory** = `dist`.
4. Go to **Deployments** → **Retry deployment** on the failed one (or push any commit to `main`). It builds
   in ~1–2 min, Node-only.

## The one-time connect (owner action — needs YOUR Cloudflare account + GitHub OAuth)
This part cannot be automated from here (it's account creation + OAuth authorization). ~5 minutes, mostly
clicks. **Recommended: the dashboard Git integration** — Cloudflare builds on every push AND gives every
PR its own preview URL (which is exactly the "stop looking at a failing preview" fix).

1. Sign in / create an account at **dash.cloudflare.com** (free).
2. **Workers & Pages → Create → Pages → Connect to Git.**
3. Authorize the **Cloudflare Pages** GitHub app → select the **`bill-tracker`** repo.
4. Set the build configuration EXACTLY (the ⭐ field is the one everyone misses):
   - **Production branch:** `main`
   - **Framework preset:** `Vite` (or "None" — either works)
   - **Build command:** `npm run build`
   - **Build output directory:** `dist`
   - ⭐ **Root directory (under "Advanced"):** `web`   ← REQUIRED; the app lives in `web/`, not repo root
   - (Node version is read from `web/.node-version` = 22 automatically; no env var needed.)
5. **Save and Deploy.** You get a `https://<project>.pages.dev` URL in ~1–2 min. Every push to `main`
   redeploys; every PR gets its own `https://<hash>.<project>.pages.dev` preview.
6. **Record the URL** back here (replace this line): `PRODUCTION URL: <fill in>`.

## Alternative (only if you'd rather keep the build in our CI)
GitHub Actions + Wrangler: add repo secrets `CLOUDFLARE_API_TOKEN` (Pages:Edit template) +
`CLOUDFLARE_ACCOUNT_ID`, and a deploy workflow builds `web/` and pushes `dist/` via `wrangler pages
deploy`. More moving parts, no free per-PR previews — **not recommended for now**, but say the word and
the workflow gets added. (This is also the natural home once the [[audits/fable_2026-07/50_state_scaling_architecture]]
CDN inversion publishes static JSON — at which point the worker, not Cloudflare, owns the build.)

## Notes / gotchas
- **The sheet must stay link-readable** for gviz to work from the Pages domain (the app is client-side).
  This is a pre-launch acceptable exposure (metrics are operational, not secret); the
  [[audits/fable_2026-07/50_state_scaling_architecture]] CDN inversion removes the link-readable
  requirement later by publishing static JSON.
- **Health tab is publicly visible** on this deploy (no gating in the React code). Fine pre-launch; before
  public launch, gate it per [[design/health_operator_tab]] (separate operator Pages project + Cloudflare
  Access email-allowlist). Track that as a launch-blocker, not a today problem.
- **The old Streamlit X-Ray** (`test_auto_calender.py` / `pages/ray2.py`) is a SEPARATE, internal
  diagnostic and is unaffected — it keeps auto-deploying on Streamlit Cloud. This Cloudflare deploy is the
  lobbyist product only.
