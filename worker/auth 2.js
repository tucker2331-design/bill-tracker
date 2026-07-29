/**
 * Google ID-token verification — F2 auth.
 *
 * WHY THIS SHAPE: Cloudflare Access was rejected on its pricing MODEL ($7/user/month past 50 seats against a
 * volunteer user base that grows with adoption — docs/architecture/verification_durability.md). This is the
 * replacement: the browser gets a signed ID token from Google, and we verify it here. No per-seat cost, and
 * no secret to hold — the client ID is public, and verification uses Google's published keys.
 *
 * EVERY CHECK BELOW IS LOAD-BEARING. Skipping any one of them makes the whole thing decorative:
 *   - signature   : without it, anyone can hand us a JSON blob claiming to be anyone.
 *   - aud         : without it, a token minted for ANY OTHER Google app is accepted here. This is the
 *                   classic OAuth confused-deputy hole and it is invisible in testing, because your own
 *                   tokens pass either way.
 *   - iss         : must be Google.
 *   - exp / iat   : a valid-forever token is a permanent credential if it ever leaks.
 *   - email_verified : Google will issue tokens for unverified addresses; treating those as identity lets
 *                   someone claim an email they do not control.
 *
 * Failure returns null. Callers MUST treat null as reject — never "anonymous is fine" (assumptions_audit
 * #53: absence of an identity must not read as a valid one).
 */

const GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs";
const GOOGLE_ISSUERS = new Set(["accounts.google.com", "https://accounts.google.com"]);

/** Small leeway for clock skew between Google and the edge. Seconds. */
const CLOCK_SKEW = 60;

function b64urlToBytes(s) {
  const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function b64urlToJSON(s) {
  return JSON.parse(new TextDecoder().decode(b64urlToBytes(s)));
}

/**
 * Google's public signing keys.
 *
 * Cached via the `cf` fetch option rather than a module-global: a Worker isolate can be recycled at any
 * time, and Google ROTATES these keys. A hand-rolled forever-cache would keep verifying against a retired
 * key and fail closed for every user until the isolate died — an outage that looks like "login is broken"
 * with no error to point at.
 */
async function fetchJwks() {
  const res = await fetch(GOOGLE_JWKS_URL, { cf: { cacheTtl: 3600, cacheEverything: true } });
  if (!res.ok) throw new Error(`JWKS fetch failed: HTTP ${res.status}`);
  return res.json();
}

/**
 * Verify a Google ID token. Returns the verified email, or null.
 *
 * @param {string} idToken   the raw JWT from the browser
 * @param {string} clientId  our OAuth client id; the token's `aud` must equal this exactly
 */
export async function verifyGoogleIdToken(idToken, clientId) {
  if (!idToken || !clientId) return null;

  const parts = idToken.split(".");
  if (parts.length !== 3) return null;
  const [rawHeader, rawPayload, rawSig] = parts;

  let header, claims;
  try {
    header = b64urlToJSON(rawHeader);
    claims = b64urlToJSON(rawPayload);
  } catch {
    return null;
  }

  // Only RS256 — accepting `alg` from the token is how "alg: none" and algorithm-confusion attacks work.
  if (header.alg !== "RS256" || !header.kid) return null;

  let jwks;
  try {
    jwks = await fetchJwks();
  } catch {
    // Cannot verify => cannot authenticate. Fail closed; never fall through to "trust the payload".
    return null;
  }

  const jwk = (jwks.keys || []).find((k) => k.kid === header.kid);
  if (!jwk) return null;

  let ok = false;
  try {
    const key = await crypto.subtle.importKey(
      "jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"],
    );
    ok = await crypto.subtle.verify(
      "RSASSA-PKCS1-v1_5", key, b64urlToBytes(rawSig),
      new TextEncoder().encode(`${rawHeader}.${rawPayload}`),
    );
  } catch {
    return null;
  }
  if (!ok) return null;

  // ---- claims. Signature proves Google minted it; these prove it was minted FOR US and is still valid. ----
  if (!GOOGLE_ISSUERS.has(claims.iss)) return null;
  if (claims.aud !== clientId) return null;

  const now = Math.floor(Date.now() / 1000);
  if (typeof claims.exp !== "number" || claims.exp + CLOCK_SKEW < now) return null;
  if (typeof claims.iat === "number" && claims.iat - CLOCK_SKEW > now) return null;

  // `email_verified` arrives as a boolean or the string "true" depending on the flow. Anything else is not
  // a verified address, and an unverified one is a claim rather than an identity.
  const verified = claims.email_verified === true || claims.email_verified === "true";
  if (!verified || !claims.email) return null;

  return String(claims.email).toLowerCase();
}
