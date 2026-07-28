/**
 * F2 write path — the Worker in front of the SPA.
 *
 * THE DEPLOY RISK THIS FILE IS WRITTEN AROUND: `wrangler.toml` was assets-only. Adding `main` makes this
 * script run for every request that does NOT match a static asset — including deep links like `/search`,
 * which previously fell through to `not_found_handling = "single-page-application"` on their own. If this
 * script forgets to delegate, every deep link 404s and the live site breaks. So the default branch here is
 * "hand it back to ASSETS", and only `/api/*` is claimed.
 *
 * AUTH FAILS CLOSED. Cloudflare Access is not configured yet, so `ACCESS_AUD` / `ACCESS_TEAM_DOMAIN` are
 * unset. Every mutating request is REJECTED until they are set — an unauthenticated write path that silently
 * accepts data is worse than no write path, because the bad data outlives the mistake.
 */

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });

/** Closed vocabularies. A value outside these is a 400, never a silent coercion. */
const STANCES = new Set(["involved", "supporting", "watching", "opposing"]);
const TONES = new Set(["positive", "neutral", "negative"]);

/**
 * Identity from the Access JWT.
 *
 * Returns null when Access is not configured OR the header is absent. Callers MUST treat null as "reject",
 * never as "anonymous is fine" — that is the sentinel-collision trap (assumptions_audit #53) applied to
 * auth: absence of an identity must not read as a valid one.
 */
function accessIdentity(request, env) {
  if (!env.ACCESS_AUD || !env.ACCESS_TEAM_DOMAIN) return null;
  const jwt = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!jwt) return null;
  // Cloudflare Access terminates in front of this Worker, so the header's presence already means Access
  // admitted the request. Signature verification against the team's JWKS is still required before this is
  // load-bearing -- tracked as the follow-up below, and until then only the email claim is read.
  try {
    const [, payload] = jwt.split(".");
    const claims = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    return claims.email || null;
  } catch {
    return null;
  }
}

async function handleApi(request, env, url) {
  const path = url.pathname.replace(/^\/api/, "");

  if (path === "/health") {
    // Deliberately reports whether auth is ARMED, so a misconfigured deploy is visible rather than quiet.
    return json({
      ok: true,
      db: Boolean(env.DB),
      access_configured: Boolean(env.ACCESS_AUD && env.ACCESS_TEAM_DOMAIN),
    });
  }

  if (!env.DB) return json({ error: "database binding missing" }, 500);

  if (request.method === "GET" && path === "/positions") {
    const session = url.searchParams.get("session");
    if (!session) return json({ error: "session is required" }, 400);
    const { results } = await env.DB.prepare(
      "SELECT bill_number, stance, updated_at, updated_by FROM positions WHERE session_code = ?",
    ).bind(session).all();
    return json({ positions: results ?? [] });
  }

  if (request.method === "GET" && path === "/interactions") {
    const member = url.searchParams.get("member_number");
    if (!member) return json({ error: "member_number is required" }, 400);
    // Newest first: the call sheet shows recent contact, and the list must stay readable once it scrolls.
    const { results } = await env.DB.prepare(
      `SELECT id, session_code, bill_number, occurred_on, actor, tone, note
         FROM interactions WHERE member_number = ? ORDER BY occurred_on DESC, id DESC LIMIT 200`,
    ).bind(member).all();
    return json({ interactions: results ?? [] });
  }

  // ---- mutations: identity required, no exceptions ----
  const email = accessIdentity(request, env);
  if (!email) return json({ error: "not authenticated" }, 401);

  if (request.method === "PUT" && path === "/positions") {
    const body = await request.json().catch(() => null);
    if (!body?.session_code || !body?.bill_number) return json({ error: "session_code and bill_number are required" }, 400);
    if (!STANCES.has(body.stance)) return json({ error: `stance must be one of ${[...STANCES].join(", ")}` }, 400);
    await env.DB.prepare(
      `INSERT INTO positions (session_code, bill_number, stance, updated_at, updated_by)
       VALUES (?1, ?2, ?3, ?4, ?5)
       ON CONFLICT(session_code, bill_number)
       DO UPDATE SET stance = ?3, updated_at = ?4, updated_by = ?5`,
    ).bind(body.session_code, body.bill_number, body.stance, new Date().toISOString(), email).run();
    return json({ ok: true });
  }

  if (request.method === "POST" && path === "/interactions") {
    const body = await request.json().catch(() => null);
    if (!body?.member_number || !body?.session_code || !body?.occurred_on) {
      return json({ error: "member_number, session_code and occurred_on are required" }, 400);
    }
    if (!TONES.has(body.tone)) return json({ error: `tone must be one of ${[...TONES].join(", ")}` }, 400);
    await env.DB.prepare(
      `INSERT INTO interactions
         (member_number, session_code, bill_number, occurred_on, actor, tone, note, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    ).bind(body.member_number, body.session_code, body.bill_number ?? null, body.occurred_on,
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
