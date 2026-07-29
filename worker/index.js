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
 * Every mutating request requires a verified identity; `authenticatedEmail()` returns null on any failure
 * and callers reject on null. An unauthenticated write path that silently accepts data is worse than no
 * write path, because the bad data outlives the mistake.
 */

import { verifyGoogleIdToken } from "./auth.js";

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });

/** Closed vocabularies. A value outside these is a 400, never a silent coercion. */
const STANCES = new Set(["involved", "supporting", "watching", "opposing"]);
const TONES = new Set(["positive", "neutral", "negative"]);

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
    });
  }

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
    const member = url.searchParams.get("member_number");
    if (!state || !member) return json({ error: "state and member_number are required" }, 400);
    // Newest first: the call sheet shows recent contact, and the list must stay readable once it scrolls.
    // A member_number is only unique WITHIN a state, so the state must be in the WHERE clause.
    const { results } = await env.DB.prepare(
      `SELECT id, session_code, bill_number, occurred_on, actor, tone, note
         FROM interactions WHERE state = ? AND member_number = ?
         ORDER BY occurred_on DESC, id DESC LIMIT 200`,
    ).bind(state, member).all();
    return json({ interactions: results ?? [] });
  }

  // ---- mutations: identity required, no exceptions ----
  const email = await authenticatedEmail(request, env);
  if (!email) return json({ error: "not authenticated" }, 401);

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

  if (request.method === "POST" && path === "/interactions") {
    const body = await request.json().catch(() => null);
    if (!body?.state || !body?.member_number || !body?.session_code || !body?.occurred_on) {
      return json({ error: "state, member_number, session_code and occurred_on are required" }, 400);
    }
    if (!TONES.has(body.tone)) return json({ error: `tone must be one of ${[...TONES].join(", ")}` }, 400);
    await env.DB.prepare(
      `INSERT INTO interactions
         (state, member_number, session_code, bill_number, occurred_on, actor, tone, note, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).bind(body.state, body.member_number, body.session_code, body.bill_number ?? null, body.occurred_on,
           body.actor || email, body.tone, body.note ?? null, new Date().toISOString()).run();
    return json({ ok: true }, 201);
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
};
