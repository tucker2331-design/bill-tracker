/**
 * The data gate — every sheet read the app makes goes through here, behind sign-in AND the team list.
 *
 * WHY (owner, 2026-09-28): "i need the whole thing gate kept for now only to me and who ever else i add." Until
 * this file, the SPA read the Google Sheet straight from the browser via gviz, and the sheet was readable by
 * anyone who had its id -- which is committed in the public repo. Gating the UI alone would have been a
 * curtain, not a lock. LIS ToS §2 ("personal and non-commercial use only", docs/knowledge/lis_tos_commercial_use)
 * is the reason it matters now: republishing LIS-derived data to the open web is the thing to avoid.
 *
 * HOW: `GET /api/sheet?tab=…[&tq=…][&range=…][&headers=…]` re-issues the SAME gviz CSV query server-side, for
 * ONE fixed spreadsheet (env.SPREADSHEET_ID), and streams the CSV back. The front end keeps its parsers.
 *   - With `GCP_SA_JSON` set (Worker secret: the service-account JSON the Python workers already write with),
 *     the request carries a read-only OAuth token, so the sheet can then be made PRIVATE.
 *   - Without it, the request goes out unauthenticated -- which only works while the sheet is still link-shared.
 *     That mode is REPORTED (`x-sheet-auth: none` on every response, `sheet_auth` on /api/health), never silent.
 *
 * NOT AN OPEN PROXY: the spreadsheet id comes from server config, never the request, and every parameter is
 * shape-checked. A private sheet read without a token comes back as Google's HTML sign-in page with a 200; that
 * is caught by content type and answered 502 with a reason, never passed to a CSV parser.
 */

const SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly";
const TOKEN_URL = "https://oauth2.googleapis.com/token";

/** Shape checks for the four pass-through parameters. Returns an error string, or null when all are valid. */
export function validateSheetParams(p) {
  if (!p.tab || !/^[A-Za-z0-9_ ]{1,64}$/.test(p.tab)) return "tab must be 1-64 letters, digits, spaces or _";
  if (p.tq != null && (typeof p.tq !== "string" || p.tq.length > 2000)) return "tq must be at most 2000 characters";
  if (p.range != null && !/^[A-Z]{1,3}[0-9]{0,7}(:[A-Z]{1,3}[0-9]{0,7})?$/.test(p.range)) return "range must be A1 notation";
  if (p.headers != null && !/^[0-9]$/.test(p.headers)) return "headers must be a single digit";
  return null;
}

/** The upstream gviz URL for one validated request. The spreadsheet id is server config only. */
export function gvizUrl(spreadsheetId, p) {
  const q = new URLSearchParams({ tqx: "out:csv", sheet: p.tab });
  if (p.headers != null) q.set("headers", p.headers);
  if (p.range != null) q.set("range", p.range);
  if (p.tq != null) q.set("tq", p.tq);
  return `https://docs.google.com/spreadsheets/d/${encodeURIComponent(spreadsheetId)}/gviz/tq?${q.toString()}`;
}

const b64url = (bytes) => {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};
const b64urlJson = (o) => b64url(new TextEncoder().encode(JSON.stringify(o)));

/** PEM ("-----BEGIN PRIVATE KEY-----…") -> PKCS#8 bytes. Throws on anything else. */
export function pemToPkcs8(pem) {
  const m = /-----BEGIN PRIVATE KEY-----([\s\S]+?)-----END PRIVATE KEY-----/.exec(String(pem || ""));
  if (!m) throw new Error("service account private_key is not a PKCS#8 PEM");
  const bin = atob(m[1].replace(/\s+/g, ""));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** The unsigned JWT claim set for Google's token endpoint (exported for the test). */
export function claimSet(clientEmail, nowSec) {
  return { iss: clientEmail, scope: SCOPE, aud: TOKEN_URL, iat: nowSec, exp: nowSec + 3600 };
}

let cached = null;   // { token, exp } -- per isolate; a cold isolate simply mints a new one

/** A read-only OAuth access token for the service account, or null when GCP_SA_JSON is not configured. */
export async function serviceToken(env, now = Date.now()) {
  if (!env.GCP_SA_JSON) return null;
  if (cached && cached.exp - 60_000 > now) return cached.token;
  let sa;
  try { sa = JSON.parse(env.GCP_SA_JSON); } catch { throw new Error("GCP_SA_JSON is not valid JSON"); }
  if (!sa.client_email || !sa.private_key) throw new Error("GCP_SA_JSON lacks client_email/private_key");
  const nowSec = Math.floor(now / 1000);
  const unsigned = `${b64urlJson({ alg: "RS256", typ: "JWT" })}.${b64urlJson(claimSet(sa.client_email, nowSec))}`;
  const key = await crypto.subtle.importKey("pkcs8", pemToPkcs8(sa.private_key),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(unsigned)));
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion: `${unsigned}.${b64url(sig)}` }),
  });
  if (!res.ok) throw new Error(`token endpoint HTTP ${res.status}`);
  const body = await res.json();
  if (!body.access_token) throw new Error("token endpoint returned no access_token");
  cached = { token: body.access_token, exp: now + (Number(body.expires_in) || 3600) * 1000 };
  return cached.token;
}

/** Handle GET /api/sheet. The caller has ALREADY authenticated the user and applied the team gate. */
export async function handleSheet(url, env) {
  const json = (b, s) => new Response(JSON.stringify(b), { status: s, headers: { "content-type": "application/json; charset=utf-8" } });
  if (!env.SPREADSHEET_ID) return json({ error: "SPREADSHEET_ID not configured" }, 500);
  const p = {
    tab: url.searchParams.get("tab"),
    tq: url.searchParams.get("tq") ?? undefined,
    range: url.searchParams.get("range") ?? undefined,
    headers: url.searchParams.get("headers") ?? undefined,
  };
  const bad = validateSheetParams(p);
  if (bad) return json({ error: bad }, 400);

  const token = await serviceToken(env);            // throws -> the outer handler's categorized 500
  const upstream = await fetch(gvizUrl(env.SPREADSHEET_ID, p), token ? { headers: { Authorization: `Bearer ${token}` } } : {});
  const type = upstream.headers.get("content-type") || "";
  if (!upstream.ok || !/text\/csv/i.test(type)) {
    // Includes the private-sheet-without-a-token case: Google answers 200 with an HTML sign-in page.
    return json({ error: "sheet not readable", upstream_status: upstream.status, upstream_type: type.split(";")[0],
                  sheet_auth: token ? "service_account" : "none" }, 502);
  }
  return new Response(upstream.body, {
    status: 200,
    headers: { "content-type": "text/csv; charset=utf-8", "cache-control": "private, no-store",
               "x-sheet-auth": token ? "service_account" : "none" },
  });
}
