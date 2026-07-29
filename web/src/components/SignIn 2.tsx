// Sign-in control for the header — F3.
//
// Three states, and each SAYS what it is rather than showing an ambiguous blank:
//   signed in    -> the name, plus sign out
//   signed out   -> Google's own button
//   unavailable  -> plain text explaining why. Never an inert button.
//
// The unavailable state is the one that matters. If Google's script is blocked (an extension, an offline
// tab, a corporate network), a button that renders but does nothing is WORSE than no button: the user
// clicks, nothing happens, and they conclude the product is broken rather than that sign-in is blocked.

import { useEffect, useRef, useState } from "react";
import { initSignIn, signOut, useIdentity } from "../state/auth";

export function SignIn() {
  const identity = useIdentity();
  const slot = useRef<HTMLDivElement | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    if (identity || !slot.current) return;
    let alive = true;
    initSignIn(slot.current).catch((e) => {
      // Surfaced, never swallowed (Standard #4): the user is told, and the reason reaches the console.
      console.error("sign-in unavailable:", e);
      if (alive) setFailed(e?.message || "sign-in unavailable");
    });
    return () => { alive = false; };
  }, [identity]);

  if (identity) {
    return (
      <span className="signin">
        <span className="signin-who">{identity.name}</span>
        <button className="signin-out" onClick={signOut}>Sign out</button>
      </span>
    );
  }
  if (failed) return <span className="signin muted" title={failed}>Sign-in unavailable</span>;
  return <span className="signin" ref={slot} />;
}
