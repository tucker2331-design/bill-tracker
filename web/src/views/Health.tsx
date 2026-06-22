import type { Completeness } from "../data/types";
import { relativeTime } from "../components/common";

// The operator / health tab (vision §3f + §7). Surfaces the trust signals bill_tracker already
// computes — the same data woven inline elsewhere, shown here raw. "The product is allowed not to
// know; it is never allowed to pretend."
export function Health({ completeness, dataAsOf }: { completeness: Completeness | null; dataAsOf: Date | null }) {
  if (!completeness) {
    return <p className="center-msg">No completeness payload found in the sheet (R1). Run bill_tracker, or check the sheet is link-readable.</p>;
  }
  const c = completeness;
  const fresh = relativeTime(dataAsOf);
  const anomalies = c.in_history_not_in_universe?.length ?? 0;
  const complete = c.universe_count === c.records_written && anomalies === 0;
  const pct = (n?: number, d?: number) => (d ? `${((100 * (n ?? 0)) / d).toFixed(1)}%` : "—");

  return (
    <div>
      <h2 className="h">Freshness</h2>
      <div className={`panel`} style={{ marginBottom: 16, display: "flex", gap: 12, alignItems: "center" }}>
        <span className={`pill ${fresh.stale ? "warn" : "good"}`} style={{ padding: "4px 12px", borderRadius: 999, fontWeight: 700 }}>
          ● Data as of {fresh.text}
        </span>
        <span className="muted">{c.checked_at_utc || dataAsOf?.toISOString() || ""}</span>
      </div>

      <h2 className="h">Completeness — do we have every bill LIS has?</h2>
      <div className="statgrid" style={{ marginBottom: 16 }}>
        <Stat n={c.records_written} l="records written" />
        <Stat n={c.universe_count} l="LIS universe" />
        <Stat n={anomalies} l="in-history-not-in-universe" bad={anomalies > 0} />
        <Stat n={c.prefiled_no_history ?? 0} l="prefiled, no history" />
        <Stat n={c.skipped_malformed_universe ?? 0} l="skipped (malformed)" bad={(c.skipped_malformed_universe ?? 0) > 0} />
      </div>
      <p className={complete ? "muted" : ""} style={{ marginBottom: 18, color: complete ? undefined : "var(--stale)" }}>
        {complete
          ? `✓ Complete: every bill in LIS's universe has a record, no anomalies.`
          : `! Completeness gap — investigate the anomaly list.`}
      </p>

      <h2 className="h">Outcome derivation (structural-first)</h2>
      <div className="statgrid" style={{ marginBottom: 16 }}>
        <Stat n={c.outcome_structural ?? 0} l="structural (BILLS.CSV flags)" />
        <Stat n={c.outcome_keyword_fallback ?? 0} l="keyword fallback" />
        <Stat n={c.outcome_keyword_mismatches ?? 0} l="keyword↔structural mismatch"
          bad={(c.outcome_keyword_mismatch_rate ?? 0) > 0.01}
          sub={`${((c.outcome_keyword_mismatch_rate ?? 0) * 100).toFixed(2)}% — self-calibrating drift`} />
      </div>

      <h2 className="h">Patron coverage</h2>
      <div className="statgrid" style={{ marginBottom: 16 }}>
        <Stat n={c.patron_present ?? 0} l="bills with patron" sub={pct(c.patron_present, c.records_written)} />
        <Stat n={c.patron_missing ?? 0} l="patron missing" bad={(c.patron_missing ?? 0) > 0} />
        <Stat n={c.bills_meta_rows ?? 0} l="BILLS.CSV rows" />
        <Stat n={c.bills_skipped_no_bill ?? 0} l="BILLS.CSV skipped" bad={(c.bills_skipped_no_bill ?? 0) > 0} />
      </div>

      <h2 className="h">Docket</h2>
      <div className="statgrid" style={{ marginBottom: 8 }}>
        <Stat n={c.docket_rows_total ?? 0} l="docket rows" />
        <Stat n={c.docket_unparseable_dates ?? 0} l="unparseable dates"
          bad={(c.docket_unparseable_rate ?? 0) > 0} sub={`${((c.docket_unparseable_rate ?? 0) * 100).toFixed(2)}%`} />
      </div>

      {anomalies > 0 && (
        <div className="panel" style={{ marginTop: 16, borderColor: "var(--stale)" }}>
          <b style={{ color: "var(--stale)" }}>In HISTORY but absent from the universe:</b>
          <div className="muted" style={{ marginTop: 6 }}>{c.in_history_not_in_universe.slice(0, 50).join(", ")}</div>
        </div>
      )}
    </div>
  );
}

function Stat({ n, l, bad, sub }: { n: number; l: string; bad?: boolean; sub?: string }) {
  return (
    <div className="stat">
      <div className="n" style={{ color: bad ? "var(--stale)" : undefined }}>{n.toLocaleString()}</div>
      <div className="l">{l}</div>
      {sub && <div className="l" style={{ marginTop: 2 }}>{sub}</div>}
    </div>
  );
}
