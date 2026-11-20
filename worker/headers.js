/**
 * Security headers on every response the Worker sends — the app pages and the API alike.
 *
 * WHY (2026-11-20, docs/ideas/going_private.md §C): the live CA site sent no Content-Security-Policy,
 * frame-ancestors or Referrer-Policy. "No security headers" is one of the holes most often found in AI-built apps.
 * Deliberately MINIMAL, so nothing the app uses can break:
 *   - frame-ancestors 'none' + X-Frame-Options DENY: no other site can show our pages inside its own (clickjacking).
 *     This limits who may frame US; Google sign-in's own popup/iframe is unaffected.
 *   - nosniff: a file is only ever read as the type we sent.
 *   - Referrer-Policy: other sites see our origin, never a full URL with a bill or route in it.
 *   - Permissions-Policy: the app never needs camera, microphone or location.
 * A full script-src policy is NOT set here: it would have to allow Google's sign-in script and be tested in a real
 * browser first. That is a separate change.
 */
export const SECURITY_HEADERS = {
  "Content-Security-Policy": "frame-ancestors 'none'",
  "X-Frame-Options": "DENY",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

/** A copy of `response` carrying SECURITY_HEADERS. Copies first: a fetched response's headers are immutable. */
export function withSecurityHeaders(response) {
  const out = new Response(response.body, response);
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) out.headers.set(k, v);
  return out;
}
