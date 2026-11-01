// Health for a state whose site has no calendar subsystem (Pennsylvania, owner 2026-11-01): ITS OWN intake checks only.
// Every row comes from the completeness payload the state's job writes (pa_bill_tracker.py) — nothing from Virginia's
// guards, calendar or days-clean ledger. Grey = clean; red = the standing "something is wrong" colour. A missing value
// is red too: an unreadable check is never shown as a pass.
import { useState } from "react";
import type { Completeness } from "../data/types";
import { STATE } from "../states";
import { SOURCE, STALE_AFTER_HOURS } from "../config";

export function HealthIntake({ completeness, dataAsOf }: { completeness: Completeness | null; dataAsOf: Date | null }) {
  const c = (completeness ?? {}) as unknown as Record<string, unknown>;
  const num = (k: string) => (typeof c[k] === "number" ? (c[k] as number) : null);
  const universe = num("universe_count"), written = num("records_written");
  const [now] = useState(() => Date.now());   // read once per mount: render stays pure (react-hooks/purity)
  const ageH = dataAsOf ? (now - dataAsOf.getTime()) / 3.6e6 : null;
  const rows: { label: string; value: string; bad: boolean }[] = [
    { label: `Bills and resolutions held vs listed by ${SOURCE}`,
      value: universe == null || written == null ? "not readable" : `${written.toLocaleString()} of ${universe.toLocaleString()}`,
      bad: universe == null || written == null || written !== universe },
    { label: "Data age", value: ageH == null ? "unknown" : ageH < 48 ? `${Math.round(ageH)} hours` : `${Math.round(ageH / 24)} days`,
      bad: ageH == null || ageH >= STALE_AFTER_HOURS },
    ...STATE.intakeChecks.map((k) => {
      const v = num(k.key);
      return { label: k.label, value: v == null ? "not readable" : v.toLocaleString(), bad: v == null || v > k.limit };
    }),
  ];
  return (
    <div className="panel">
      <h2 className="h">{STATE.name} data checks</h2>
      {rows.map((r) => (
        <div key={r.label} className="metarow"><span className="k">{r.label}</span>
          <span style={r.bad ? { color: "var(--stale)" } : undefined}>{r.value}</span></div>
      ))}
      <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>
        From the last run of {STATE.name}'s own job{typeof c.export_date === "string" ? ` (export of ${c.export_date})` : ""}.
        Grey = clean; red = needs a look.
      </p>
    </div>
  );
}
