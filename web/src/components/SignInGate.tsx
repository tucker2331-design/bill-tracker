// The sign-in gate — F3.
//
// Nobody sees a bill until we know who they are. The owner's reason is practical rather than security-led:
// an optional floating button gets ignored, and then every interaction is logged against nobody and the
// call sheet's "Tom — Mar 3" has no Tom.
//
// THIS GATES THE UI ONLY. The Worker independently rejects every unauthenticated /api request, so this is
// the front door, not the boundary. Flip REQUIRE_SIGN_IN in config.ts to lift it for testing; org data stays
// protected either way because the server does not care what the browser decided.

import { useEffect, useRef, useState } from "react";
import { APP_NAME, REQUIRE_SIGN_IN } from "../config";
import { initSignIn, useIdentity } from "../state/auth";

export function SignInGate({ children }: { children: React.ReactNode }) {
  const identity = useIdentity();
  const slot = useRef<HTMLDivElement | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const open = !REQUIRE_SIGN_IN || !!identity;

  useEffect(() => {
    if (open || !slot.current) return;
    let alive = true;
    initSignIn(slot.current).catch((e) => {
      // Surfaced, never swallowed. A blocked script must SAY so — a gate that shows a dead button teaches
      // the user the product is broken rather than that sign-in is unavailable.
      console.error("sign-in unavailable:", e);
      if (alive) setFailed(e?.message || "Sign-in is unavailable right now.");
    });
    return () => { alive = false; };
  }, [open]);

  if (open) return <>{children}</>;

  return (
    <div className="gate">
      <div className="gate-panel">
        <h1 className="gate-h">{APP_NAME}</h1>
        <p className="gate-p">Sign in to continue.</p>
        {failed ? (
          <>
            <p className="gate-err">{failed}</p>
            <p className="gate-hint">
              Sign-in usually fails here because a browser extension or network is blocking Google. Nothing is
              wrong with your account.
            </p>
          </>
        ) : (
          <div ref={slot} className="gate-btn" />
        )}
        <p className="gate-hint">Used for legislative advocacy optimization.</p>
      </div>
    </div>
  );
}
