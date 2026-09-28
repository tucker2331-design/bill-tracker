/**
 * F2 write path — the Worker in front of the SPA.
 *
 * THE DEPLOY RISK THIS FILE IS WRITTEN AROUND: `wrangler.toml` was assets-only. Adding `main` makes this
 * script run for every request that does NOT match a static asset — including deep links like `/search`,
 * which previously fell through to `not_found_handling = "single-page-application"` on their own. If this
 * script forgets to delegate, every deep link 404s and the live site breaks. So the default branch here is
 * "hand it back to ASSETS", and only `/api/*` is claimed.
 *
 * AUTH FAILS CLOSED, and the mechanism CHANGED 2026-07-27. Cloudflare Access was rejected on its pricing
 * MODEL, not its price: $7/user/month past 50 seats, against a user base of volunteers that grows with
 * adoption — our cost would scale with our own success at the segment least able to pay
 * (docs/architecture/verification_durability.md, "AUTH DECISION"). Replaced by application-level Google
 * sign-in, which has no per-seat cost and which we needed anyway, because the interaction log is worthless
 * without knowing WHO made contact.
 *
 * EVERY /api route except /health requires a verified identity -- reads included. `authenticatedEmail()`
 * returns null on any failure and the handler rejects on null. Two distinct reasons, both load-bearing:
 * an unauthenticated WRITE path silently accepts data that outlives the mistake, and an unauthenticated
 * READ path discloses the org's stances and its contact history to anyone who guesses a URL. For this
 * product disclosure is the worse of the two -- a leaked whip count is a leaked strategy.
 */

import { verifyGoogleIdToken } from "./auth.js";
import { membership, teamGate } from "./team.js";
import { handleSheet } from "./sheets.js";
import { validateContact } from "./contacts.js";
import { runAlerts } from "./alerts.js";

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });

/** Closed vocabularies. A value outside these is a 400, never a silent coercion. */
const STANCES = new Set(["involved", "supporting", "watching", "opposing"]);

/**
 * The signed-in user's verified email, or null.
 *
 * ASYNC — verification fetches Google's signing keys. Every call site must await it; a forgotten await
 * yields a Promise, which is truthy, and would let EVERY request through as authenticated. That is the
 * failure mode this comment exists to prevent.
 *
 * Callers MUST treat null as "reject", never as "anonymous is fine" — the sentinel-collision trap
 * (assumptions_audit #53) applied to auth: absence of an identity must not read as a valid one.
 */
async function authenticatedEmail(request, env) {
  if (!env.GOOGLE_CLIENT_ID) return null;          // unconfigured => nobody is authenticated
  const header = request.headers.get("Authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (!token) return null;
  return verifyGoogleIdToken(token, env.GOOGLE_CLIENT_ID);
}

async function handleApi(request, env, url) {
  const path = url.pathname.replace(/^\/api/, "");

  if (path === "/health") {
    // Deliberately reports whether auth is ARMED, so a misconfigured deploy is visible rather than quiet.
    return json({
      ok: true,
      db: Boolean(env.DB),
      // Whether writes are possible at all, so a half-configured deploy is visible rather than quiet.
      // Reports CONFIGURATION, never the caller's own auth state -- a health endpoint must not become an
      // oracle for probing whether a given token is valid.
      auth_configured: Boolean(env.GOOGLE_CLIENT_ID),
      team_configured: membership("", env) !== "not_configured",
      // How /api/sheet reads the Google Sheet: "service_account" (the sheet can be private) or "none" (works
      // only while the sheet is still link-shared). Configuration only, never the caller's state.
      sheet_auth: env.GCP_SA_JSON ? "service_account" : "none",
      // Whether the 15-minute Slack digest can run (worker/alerts.js). Configuration only.
      alerts_configured: Boolean(env.SLACK_WEBHOOK_URL && env.BILL_TRACKER_STATE),
    });
  }


  // AUTHENTICATION GATES EVERY ROUTE BELOW, READS INCLUDED (CodeRabbit, 2026-07-28 — a real hole I shipped).
  // Positions and interactions are ORG-PRIVATE: our stance on a bill, and who from the org spoke to which
  // legislator and how it went. I had gated only the mutations, which protects the data from being CHANGED
  // while leaving it readable by anyone who guessed the URL. For this product, disclosure is the worse
  // failure -- a leaked whip count is a leaked strategy.
  const email = await authenticatedEmail(request, env);
  if (!email) return json({ error: "not authenticated" }, 401);

  // TEAM GATE for the org-private routes (positions, interactions). Identity is not membership: without this,
  // any Google account could read the org's stances. /me stays open -- it is scoped to the caller's own row.
  // 403 carries a machine-readable reason so the UI can say "not set up yet" vs "not on this team".
  const denied = teamGate(path, email, env);
  if (denied) return json(denied.body, denied.status);

  // Every read of the Google Sheet (bills, calendar, health) — the data itself is behind the team gate now.
  if (request.method === "GET" && path === "/sheet") return handleSheet(url, env);

  if (!env.DB) return json({ error: "database binding missing" }, 500);

  // `state` is required on EVERY route. It is never defaulted to 'VA': a caller that forgets it must get a
  // 400, not silently read or write Virginia's data (migrations/0001_init.sql).
  const state = url.searchParams.get("state");

  if (request.method === "GET" && path === "/positions") {
    const session = url.searchParams.get("session");
    if (!state || !session) return json({ error: "state and session are required" }, 400);
    const { results } = await env.DB.prepare(
      "SELECT bill_number, stance, updated_at, updated_by FROM positions WHERE state = ? AND session_code = ?",
    ).bind(state, session).all();
    return json({ positions: results ?? [] });
  }

  if (request.method === "GET" && path === "/interactions") {
    // Two views of the same log: one legislator (the call sheet) or one bill (the bill card). Newest first either
    // way; a member_number is only unique WITHIN a state, and a bill number only within a state + session.
    const member = url.searchParams.get("member_number");
    const bill = url.searchParams.get("bill_number");
    const session = url.searchParams.get("session");
    const cols = "id, member_number, session_code, bill_number, occurred_on, actor, tone, note, created_by";
    if (state && member) {
      const { results } = await env.DB.prepare(
        `SELECT ${cols} FROM interactions WHERE state = ? AND member_number = ?
          ORDER BY occurred_on DESC, id DESC LIMIT 200`,
      ).bind(state, member).all();
      return json({ interactions: results ?? [] });
    }
    if (state && session && bill) {
      const { results } = await env.DB.prepare(
        `SELECT ${cols} FROM interactions WHERE state = ? AND session_code = ? AND bill_number = ?
          ORDER BY occurred_on DESC, id DESC LIMIT 200`,
      ).bind(state, session, bill).all();
      return json({ interactions: results ?? [] });
    }
    return json({ error: "state and member_number, or state, session and bill_number, are required" }, 400);
  }


  if (request.method === "PUT" && path === "/positions") {
    const body = await request.json().catch(() => null);
    if (!body?.state || !body?.session_code || !body?.bill_number) {
      return json({ error: "state, session_code and bill_number are required" }, 400);
    }
    if (!STANCES.has(body.stance)) return json({ error: `stance must be one of ${[...STANCES].join(", ")}` }, 400);
    await env.DB.prepare(
      `INSERT INTO positions (state, session_code, bill_number, stance, updated_at, updated_by)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6)
       ON CONFLICT(state, session_code, bill_number)
       DO UPDATE SET stance = ?4, updated_at = ?5, updated_by = ?6`,
    ).bind(body.state, body.session_code, body.bill_number, body.stance,
           new Date().toISOString(), email).run();
    return json({ ok: true });
  }

  if (request.method === "DELETE" && path === "/positions") {
    const session = url.searchParams.get("session");
    const bill = url.searchParams.get("bill_number");
    if (!state || !session || !bill) return json({ error: "state, session and bill_number are required" }, 400);
    await env.DB.prepare(
      "DELETE FROM positions WHERE state = ? AND session_code = ? AND bill_number = ?",
    ).bind(state, session, bill).run();
    return json({ ok: true });
  }

  if (request.method === "POST" && path === "/interactions") {
    const v = validateContact(await request.json().catch(() => null), email, new Date().toISOString());
    if (v.error) return json({ error: v.error }, 400);
    const r = v.row;
    const res = await env.DB.prepare(
      `INSERT INTO interactions
         (state, member_number, session_code, bill_number, occurred_on, actor, tone, note, created_at, created_by)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).bind(r.state, r.member, r.session, r.bill, r.occurred_on, r.actor, r.tone, r.note, r.created_at,
           r.created_by).run();
    return json({ ok: true, id: res?.meta?.last_row_id ?? null }, 201);
  }


  // ---- the signed-in user's own profile ----
  // Scoped to `email` from the VERIFIED token, never from the body: a client must not be able to read or
  // write another person's profile by naming them.
  if (path === "/me") {
    if (request.method === "GET") {
      const row = await env.DB.prepare(
        `SELECT email, display_name, home_state, district_house, district_senate, district_congress,
                districts_confirmed_at
           FROM users WHERE email = ?`,
      ).bind(email).first();
      // A first-time user is NOT an error -- `profile: null` means "ask them", which is what the UI needs
      // to distinguish from "we failed to load".
      return json({ profile: row ?? null });
    }

    if (request.method === "PUT") {
      const body = await request.json().catch(() => null);
      const name = (body?.display_name ?? "").trim();
      if (!name) return json({ error: "display_name is required" }, 400);

      // Districts are stored as the user CONFIRMED them. We never store an address; the Census lookup that
      // helps them find these runs in their browser and its input is discarded
      // (docs/knowledge/district_lookup.md). There is deliberately nowhere here to put one.
      const dist = (v) => {
        const t = String(v ?? "").trim();
        return t === "" ? null : t;
      };
      const st = String(body?.home_state ?? "").trim().toUpperCase();
      if (st && !/^[A-Z]{2}$/.test(st)) return json({ error: "home_state must be a 2-letter code" }, 400);

      const now = new Date().toISOString();
      await env.DB.prepare(
        `INSERT INTO users (email, display_name, home_state, district_house, district_senate,
                            district_congress, districts_confirmed_at, created_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
         ON CONFLICT(email) DO UPDATE SET
           display_name = ?2, home_state = ?3, district_house = ?4, district_senate = ?5,
           district_congress = ?6, districts_confirmed_at = ?7`,
      ).bind(email, name, st || null, dist(body?.district_house), dist(body?.district_senate),
             dist(body?.district_congress), now, now).run();
      return json({ ok: true, confirmed_at: now });
    }
  }

  return json({ error: "not found" }, 404);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
      try {
        return await handleApi(request, env, url);
      } catch (err) {
        // Never leak an internal message to the client, but never swallow it either (Standard #4).
        console.error("api_error", url.pathname, request.method, err && err.stack ? err.stack : String(err));
        return json({ error: "internal error" }, 500);
      }
    }
    // EVERYTHING else is the SPA. This is the line that keeps the existing site working.
    return env.ASSETS.fetch(request);
  },

  // Cron Trigger (wrangler.toml [triggers]): the Slack digest. A failure is logged with its stack and re-thrown
  // so Cloudflare records the run as failed (visible in the dashboard) -- never swallowed.
  async scheduled(event, env, ctx) {
    try {
      await runAlerts(env);
    } catch (err) {
      console.error("alerts_error", err && err.stack ? err.stack : String(err));
      throw err;
    }
  },
};
