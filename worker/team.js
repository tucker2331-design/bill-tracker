/**
 * Team membership — who may read or write the org's private data (positions, interactions).
 *
 * WHY THIS EXISTS: `authenticatedEmail()` proves WHO someone is, not that they belong here. Before this gate,
 * any Google account on the internet passed auth and could read the org's stances and contact log -- the exact
 * disclosure the auth comment in index.js calls the worse failure ("a leaked whip count is a leaked strategy").
 * Found 2026-09-28 while wiring the first UI write; the tables were still empty, so nothing had leaked.
 *
 * THE LIST IS A WORKER SECRET (`TEAM_EMAILS`, comma-separated), never committed config: the repo is public and
 * a member list is personal data. Set it with `npx wrangler secret put TEAM_EMAILS`.
 *
 * FAILS CLOSED. Unset, empty, or unparseable => nobody is a member, and the data routes answer 403 with a reason
 * the UI can show. The self-scoped /me route is NOT gated: a person may always manage their own profile.
 */

/** Normalise one address for comparison. Google emails are case-insensitive in practice; we compare lowercased. */
const norm = (e) => String(e ?? "").trim().toLowerCase();

/** The configured team as a Set, or null when the secret is missing/empty (=> "not configured", distinct from
 *  "configured, and you are not on it" -- the UI says different things for the two). */
export function teamSet(env) {
  const raw = env && typeof env.TEAM_EMAILS === "string" ? env.TEAM_EMAILS : "";
  const list = raw.split(/[\s,;]+/).map(norm).filter((e) => e.includes("@"));
  return list.length ? new Set(list) : null;
}

/**
 * "member" | "not_member" | "not_configured". Never a boolean: callers must not collapse "the list is missing"
 * into "you are not on it", or a misconfigured deploy reads as a permissions problem for every user.
 */
export function membership(email, env) {
  const team = teamSet(env);
  if (!team) return "not_configured";
  const e = norm(email);
  return e && team.has(e) ? "member" : "not_member";
}

/** Routes that are scoped to the caller's own row and so need identity only, not membership. */
const SELF_SCOPED = new Set(["/me"]);

/**
 * The gate the API applies after authentication: null = proceed, otherwise `{status, body}` to return.
 * Pulled out of the handler so the test exercises the SAME decision the Worker makes.
 */
export function teamGate(path, email, env) {
  if (SELF_SCOPED.has(path)) return null;
  const m = membership(email, env);
  return m === "member" ? null : { status: 403, body: { error: "not on this team", reason: m } };
}
