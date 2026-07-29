// Google sign-in, client half — F3.
//
// PAIRS WITH worker/auth.js. The browser obtains a signed ID token from Google; the Worker verifies it
// against Google's published keys. There is no client secret anywhere in this repo, because the flow we use
// does not have one — the client id is public by design (it ships in the page for every "Sign in with
// Google" button on the web).
//
// WHY NOT CLOUDFLARE ACCESS: rejected on its pricing MODEL, not its price -- $7/user/month past 50 seats,
// against a user base of volunteers that grows with adoption, which would make our cost scale with our own
// success at the segment least able to pay (docs/architecture/verification_durability.md).
//
// THE TOKEN IS HELD IN MEMORY ONLY. Not localStorage, not a cookie we manage:
//   - localStorage is readable by any script on the origin, so one XSS is a stolen identity that outlives
//     the page. An in-memory token dies with the tab.
//   - Google's library re-issues silently on reload, so persistence buys nothing a refresh does not.
// The cost is honest and small: a hard reload requires a re-prompt, which is usually invisible.

import { useCallback, useEffect, useState } from "react";

import { GOOGLE_CLIENT_ID } from "../config";

const GSI_SRC = "https://accounts.google.com/gsi/client";

export { GOOGLE_CLIENT_ID };

export interface Identity {
  email: string;
  name: string;
  /** The raw ID token. Sent as `Authorization: Bearer …`; never logged, never persisted. */
  token: string;
}

type Listener = (id: Identity | null) => void;

let current: Identity | null = null;
const listeners = new Set<Listener>();
const emit = () => listeners.forEach((l) => l(current));

/** Decode the payload for DISPLAY ONLY. The Worker is the only thing that VERIFIES. */
function readClaims(jwt: string): { email?: string; name?: string; given_name?: string } | null {
  try {
    const p = jwt.split(".")[1];
    const pad = p.length % 4 === 0 ? "" : "=".repeat(4 - (p.length % 4));
    return JSON.parse(atob(p.replace(/-/g, "+").replace(/_/g, "/") + pad));
  } catch {
    return null;
  }
}

let scriptPromise: Promise<void> | null = null;
// Google's library warns that repeated initialize() calls mean "only the last instance will be used", which
// is the kind of last-writer-wins behaviour that produces an unreproducible sign-in bug. React StrictMode
// re-runs effects in dev, so this WILL happen without a guard. Initialise once per page.
let initialised = false;

/** Load Google's script once. Rejects on failure so the caller can say "sign-in unavailable" out loud. */
function loadGsi(): Promise<void> {
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${GSI_SRC}"]`)) return resolve();
    const s = document.createElement("script");
    s.src = GSI_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Google sign-in script failed to load"));
    document.head.appendChild(s);
  });
  return scriptPromise;
}

/**
 * Prepare sign-in and render Google's button into `target`.
 *
 * Google's own button is used deliberately rather than a styled div: their branding rules require it, and a
 * home-made button is the classic place a phishing lookalike hides. Users should see the control they
 * already recognise.
 */
export async function initSignIn(target: HTMLElement): Promise<void> {
  if (!GOOGLE_CLIENT_ID) throw new Error("GOOGLE_CLIENT_ID is not set in web/src/config.ts");
  await loadGsi();
  const g = (window as unknown as { google?: any }).google;
  if (!g?.accounts?.id) throw new Error("Google sign-in did not initialise");

  if (!initialised) {
    initialised = true;
    g.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: (res: { credential?: string }) => {
      const token = res?.credential;
      if (!token) return;                       // no token => not signed in. Never a partial identity.
      const c = readClaims(token);
      if (!c?.email) return;                    // an identity without an email cannot attribute anything
      current = { email: c.email, name: c.given_name || c.name || c.email, token };
      emit();
    },
      auto_select: false,
      cancel_on_tap_outside: true,
    });
  }
  // renderButton is idempotent per element and must run even when initialize() was skipped, otherwise a
  // remount (StrictMode, or a sign-out) leaves an empty slot where the button should be.
  g.accounts.id.renderButton(target, { theme: "outline", size: "large", text: "signin_with" });
}

export function signOut(): void {
  const g = (window as unknown as { google?: any }).google;
  try { g?.accounts?.id?.disableAutoSelect?.(); } catch { /* best effort; local state is what matters */ }
  current = null;
  emit();
}

/** Current identity, re-rendering on sign-in/out. */
export function useIdentity(): Identity | null {
  const [id, setId] = useState<Identity | null>(current);
  useEffect(() => {
    listeners.add(setId);
    return () => { listeners.delete(setId); };
  }, []);
  return id;
}

/**
 * `fetch` with the bearer token attached.
 *
 * Throws when unauthenticated rather than sending an anonymous request: the Worker would 401 anyway, and a
 * silent anonymous call is how a UI ends up showing "no data" for what is really "not signed in".
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!current) throw new Error("not signed in");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${current.token}`);
  return fetch(path, { ...init, headers });
}

/** For tests and for the sign-out path. Not exported through the barrel. */
export const __setIdentityForTest = (id: Identity | null) => { current = id; emit(); };
export const useSignOut = () => useCallback(() => signOut(), []);
