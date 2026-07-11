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
  // The PARENT remounts this via key={token} on each refresh, so each notice starts fresh and this effect
  // only schedules the two timers — no setState-in-effect (CodeRabbit: that's a react-hooks purity error).
  // Two phases: after VISIBLE_MS it starts to fade (`leaving`), and after the fade completes it fully
  // UNMOUNTS (`gone`) so no invisible element lingers at bottom-centre (it also has pointer-events:none,
  // but removing it is cleaner than a stack of faded ghosts).
  const [leaving, setLeaving] = useState(false);
  const [gone, setGone] = useState(false);
  useEffect(() => {
    const toLeave = setTimeout(() => setLeaving(true), VISIBLE_MS);
    const toGone = setTimeout(() => setGone(true), VISIBLE_MS + FADE_MS);
    return () => { clearTimeout(toLeave); clearTimeout(toGone); };
  }, []);

  if (token === 0 || gone) return null; // nothing refreshed yet, or the notice has finished + unmounted

  return (
    <div
      className={`refresh-note ${leaving ? "leaving" : ""}`}
      role="status"
      aria-live="polite"
      style={{ ["--fade-ms" as string]: `${FADE_MS}ms` }}
    >
      {label}
    </div>
  );
}
