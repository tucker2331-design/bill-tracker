import { useEffect, useState } from "react";

// A TRANSIENT, self-dismissing notice whose ONLY job is to tell a person WHY the page just changed under
// them after a background refresh (owner 2026-07-10). It is deliberately NOT a status pill and NOT a
// freshness readout — "how current is the data" already lives in the TrustHeader. This is the EVENT
// ("something just updated"), not the STATE ("data is N min old"). It appears on a refresh, then it's gone.
//
// Keyed by `token` (the App bumps it on each refresh): a new token re-mounts this and restarts the timer,
// so back-to-back refreshes each get their own full fade rather than the second being swallowed.
const VISIBLE_MS = 3500;   // long enough to read "Updated…", short enough to not linger
const FADE_MS = 400;

export function RefreshNotice({ token, label }: { token: number; label: string }) {
  const [phase, setPhase] = useState<"in" | "out">("in");
  useEffect(() => {
    setPhase("in");
    const toOut = setTimeout(() => setPhase("out"), VISIBLE_MS);
    return () => clearTimeout(toOut);
  }, [token]);

  if (token === 0) return null; // nothing has refreshed yet this session

  return (
    <div
      key={token}
      className={`refresh-note ${phase === "out" ? "leaving" : ""}`}
      role="status"
      aria-live="polite"
      style={{ ["--fade-ms" as string]: `${FADE_MS}ms` }}
    >
      {label}
    </div>
  );
}
