import { useEffect, useState } from "react";
import type { Completeness } from "../data/types";
import { BulletGraph } from "../components/BulletGraph";
import { bandTone, type Band } from "../components/bands";
import { HealthVitals, type Vital, type VitalSeg } from "../components/HealthVitals";
import { loadHealth, type HealthData } from "../data/health";
import { loadVerification, type GuardRun } from "../data/verification";

// The operator / Health tab (vision §3f + §7): the trust signals the system ALREADY produces, as Few
// bullet graphs with danger bands (PL-8 / owner's "RPM redline"). Bill-backend signals arrive via props
// (App loaded Bill_Tracker R1); calendar-subsystem signals load here from Sheet1 (lightweight, health.ts).
// "Allowed not to know; never to pretend." Access-gated to the owner + a few (Cloudflare Access — see
// docs/design/health_operator_tab.md). Calibration: bands from the worker's breaker thresholds + steady state.

// Band presets. lowerBetter: good→warn→DANGER (danger on the right; the bar grows INTO the redline).
const lower = (good: number, warn: number, max: number): Band[] =>
  [{ upto: good, tone: "good" }, { upto: warn, tone: "warn" }, { upto: max, tone: "danger" }];
// higherBetter: DANGER→warn→good (danger on the left; the bar fills toward the good target on the right).
const higher = (danger: number, warn: number, max = 100): Band[] =>
  [{ upto: danger, tone: "danger" }, { upto: warn, tone: "warn" }, { upto: max, tone: "good" }];

const hoursSince = (d: Date | null) => (d ? (Date.now() - d.getTime()) / 3.6e6 : NaN);
const hrs = (n: number) => (Number.isFinite(n) ? `${n.toFixed(1)}` : "—");
const oneDp = (n: number) => n.toFixed(1);
const agoText = (d: Date | null) => {
  if (!d) return "";
  const h = (Date.now() - d.getTime()) / 3.6e6;
  if (h < 1) return "just now";
  if (h < 24) return `${Math.round(h)}h ago`;
  return `${Math.round(h / 24)}d ago`;
};

export function Health({ completeness, dataAsOf }: { completeness: Completeness | null; dataAsOf: Date | null }) {
  const [h, setH] = useState<HealthData | null>(null);
  const [hErr, setHErr] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    loadHealth().then((d) => alive && setH(d)).catch((e) => alive && setHErr(String(e?.message || e)));
    return () => { alive = false; };
  }, []);
  const [guards, setGuards] = useState<GuardRun[] | null>(null);
  useEffect(() => {
    let alive = true;
    loadVerification().then((d) => alive && setGuards(d)).catch(() => alive && setGuards([]));
    return () => { alive = false; };
  }, []);

  if (!completeness && !h && !hErr) return <p className="center-msg">Loading operator health…</p>;

  // ── Bill-backend signals (props) ──
  const c = completeness;
  const universe = c?.universe_count ?? 0;
  const written = c?.records_written ?? 0;
  const anomalies = c?.in_history_not_in_universe?.length ?? 0;
  const completePct = universe > 0 ? (100 * written) / universe : 0;
  const patronPct = written > 0 ? (100 * (c?.patron_present ?? 0)) / written : 0;
  const driftPct = (c?.outcome_keyword_mismatch_rate ?? 0) * 100;
  const billFreshH = hoursSince(dataAsOf);

  // ── Calendar-subsystem signals (Sheet1) ──
  const m = h?.metrics ?? {};
  const total = m.total_processed ?? 0;
  const section9 = m.meeting_unsourced;          // the core accuracy metric
  const violations = m.invariant_violations;
  const unclassPct = total > 0 ? (100 * (m.legevent_route_blank ?? 0)) / total : 0;
  const calFreshH = hoursSince(h?.calendarFreshness ?? null);
  const breakerOk = h ? !h.breakerTrip : true;

  // ── At-a-glance vitals: roll the gauges below into four category rings. Each segment's tone comes from
  // `bandTone` over the SAME bands the matching gauge uses, so the donut and the detail never disagree; a
  // segment whose backend payload is absent is "unknown" (grey), never a false green. ──
  const sv = (label: string, value: number, bands: Band[], known: boolean): VitalSeg =>
    ({ label, tone: known ? bandTone(value, bands) : "unknown" });
  const critCount = h ? h.alerts.filter((a) => a.severity === "CRITICAL").length : 0;
  const warnCount = h ? h.alerts.filter((a) => a.severity === "WARN").length : 0;
  const vitals: Vital[] = [
    { name: "Accuracy", segs: [
      sv("Section-9 · meeting actions without a time", section9 ?? 0, lower(0.5, 25, 50), section9 != null),
      sv("Outcome drift · keyword↔structural", driftPct, lower(0.1, 1, 2), !!c),
    ] },
    { name: "Completeness", segs: [
      sv("Bill completeness · records vs universe", completePct, higher(98, 99.99, 100), !!c && universe > 0),
      sv("History-vs-universe anomalies", anomalies, lower(0.5, 5, 20), !!c),
      sv("Patron coverage", patronPct, higher(98, 99.99, 100), !!c && written > 0),
      sv("Unclassified share · router blank", unclassPct, lower(8, 15, 25), !!h),
    ] },
    { name: "Freshness", segs: [
      sv("Bill backend clock", billFreshH, lower(6, 12, 24), !!dataAsOf),
      sv("Calendar clock", calFreshH, lower(6, 12, 24), !!h?.calendarFreshness),
    ] },
    { name: "Stability", segs: [
      { label: "Circuit breaker", tone: !h ? "unknown" : breakerOk ? "good" : "danger" },
      sv("Write-time invariant violations", violations ?? 0, lower(0.5, 49, 60), violations != null),
      { label: "Active alerts", tone: !h ? "unknown" : critCount ? "danger" : warnCount ? "warn" : "good" },
    ] },
  ];

  return (
    <div>
      <h2 className="h">At a glance</h2>
      <HealthVitals vitals={vitals} />

      {/* ── System status: the breaker + the TWO freshnesses (different workers) ── */}
      <div className="hl-status">
        <span className={`hl-breaker ${breakerOk ? "ok" : "trip"}`}>
          {breakerOk ? "● Circuit breaker armed" : "▲ BREAKER TRIPPED"}
        </span>
        {!breakerOk && h?.breakerTrip && (
          <span className="muted" style={{ fontSize: 12 }}>
            tripped {String((h.breakerTrip as { trip_utc?: string }).trip_utc ?? "")} — Sheet1 holds last-known-good
          </span>
        )}
      </div>

      {/* ── "Are we right?" — the 5-layer durability guard's INDEPENDENT verification (reconciliation vs
            the MinutesBook, completeness vs LIS's own calendar), surfaced live from GitHub Actions
            (verification_durability.md). Turns the CI-only green into a visible trust signal; an
            unreachable API shows "—", never a fake pass. Layer 1 (the breaker) is the live chip above. ── */}
      <h2 className="h">Are we right? · independent verification</h2>
      {guards === null ? (
        <p className="muted" style={{ marginBottom: 18 }}>Loading independent verification…</p>
      ) : guards.length === 0 ? (
        <p className="muted" style={{ marginBottom: 18 }}>Independent verification unavailable (GitHub API unreachable).</p>
      ) : (
        <div className="hl-verify panel">
          {guards.map((g) => {
            const txt = g.status === "pass" ? `✓ verified ${agoText(g.lastRun)}`
              : g.status === "fail" ? `✕ FAILED ${agoText(g.lastRun)}`
              : g.status === "running" ? "running…" : "—";
            return (
              <div key={g.key} className="hl-vrow">
                <span className={`hl-vdot ${g.status}`} aria-hidden="true" />
                <span className="hl-vlabel">{g.label}</span>
                <span className="hl-vproves">{g.proves}</span>
                {g.url ? (
                  <a className={`hl-verstat ${g.status}${g.stale ? " stale" : ""}`} href={g.url} target="_blank" rel="noreferrer">
                    {txt}{g.stale ? " · stale" : ""}
                  </a>
                ) : (
                  <span className={`hl-verstat ${g.status}`}>{txt}</span>
                )}
              </div>
            );
          })}
          <div className="hl-vfoot muted">
            Live from GitHub Actions · a red or stale row means the independent check itself needs a look.
          </div>
        </div>
      )}

      <h2 className="h">Accuracy &amp; completeness — the lobbyist-facing guarantees</h2>
      <div className="hl-gauges">
        {h ? (
          <BulletGraph label="Section-9 accuracy · meeting actions without a time" value={section9 ?? 0}
            max={50} target={0} bands={lower(0.5, 25, 50)} sub="0 = every meeting action has a time (the project goal)" />
        ) : <CalLoading err={hErr} />}
        {/* Bill-backend gauges only render when the completeness payload is present — a null payload must NOT
            display as a real 0% / 0 (that would read as a false danger; "allowed not to know, never pretend"). */}
        {c ? (<>
          <BulletGraph label="Bill completeness · records written vs LIS universe" value={completePct}
            max={100} target={100} bands={higher(98, 99.99, 100)} unit="%" format={oneDp}
            sub={`${written.toLocaleString()} of ${universe.toLocaleString()} bills${anomalies ? ` · ${anomalies} in-history-not-in-universe` : ""}`} />
          <BulletGraph label="History-vs-universe anomalies" value={anomalies}
            max={20} target={0} bands={lower(0.5, 5, 20)} sub="bills seen in HISTORY but absent from the universe (scariest silent gap)" />
        </>) : <p className="muted">Bill-backend signals unavailable (no completeness payload in Bill_Tracker R1).</p>}
      </div>

      <h2 className="h">Freshness — two workers, two clocks</h2>
      <div className="hl-gauges">
        {dataAsOf ? (
          <BulletGraph label="Bill backend · hours since last good run" value={billFreshH}
            max={24} target={0} bands={lower(6, 12, 24)} unit=" h" format={hrs}
            sub={c?.checked_at_utc || dataAsOf.toISOString()} />
        ) : <p className="muted">Bill-backend freshness unknown (no timestamp).</p>}
        {h ? (
          <BulletGraph label="Calendar subsystem · hours since last good cycle" value={calFreshH}
            max={24} target={0} bands={lower(6, 12, 24)} unit=" h" format={hrs}
            sub={h.calendarFreshness?.toISOString() || "Sheet1!AA1 unreadable"} />
        ) : <CalLoading err={hErr} />}
      </div>

      <h2 className="h">Pipeline health</h2>
      <div className="hl-gauges">
        {h ? (
          <BulletGraph label="Write-time invariant violations" value={violations ?? 0}
            max={60} target={0} bands={lower(0.5, 49, 60)} sub="rows that failed a schema/Origin invariant at write (breaker trips at ≥50)" />
        ) : <CalLoading err={hErr} />}
        {c && (
          <BulletGraph label="Outcome drift · keyword↔structural mismatch" value={driftPct}
            max={2} target={0} bands={lower(0.1, 1, 2)} unit="%" format={oneDp}
            sub="self-calibrating reconciliation vs LIS's own flags (steady ≈ 0.03%)" />
        )}
        {h && (
          <BulletGraph label="Unclassified share · router returned blank" value={unclassPct}
            max={25} target={0} bands={lower(8, 15, 25)} unit="%" format={oneDp}
            sub={`${(m.legevent_route_blank ?? 0).toLocaleString()} of ${total.toLocaleString()} rows (floor/skeleton rows are legitimately blank)`} />
        )}
        {c && (
          <BulletGraph label="Patron coverage" value={patronPct}
            max={100} target={100} bands={higher(98, 99.99, 100)} unit="%" format={oneDp}
            sub={`${(c.patron_present ?? 0).toLocaleString()} of ${written.toLocaleString()} bills with a chief patron`} />
        )}
      </div>

      {/* ── Alert feed: the operator's "needs a human" list (Standard #8) ── */}
      <h2 className="h">Alerts {h && <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· latest from the calendar worker</span>}</h2>
      {h ? (
        h.alerts.length === 0 ? (
          <p className="muted" style={{ marginBottom: 18 }}>No active alerts — the worker is running clean.</p>
        ) : (
          <div className="panel" style={{ marginBottom: 18 }}>
            {h.alerts.map((a, i) => (
              <div key={i} className="hl-alert">
                <span className={`hl-sev ${a.severity.toLowerCase()}`}>{a.severity}</span>
                {a.category && <span className="hl-cat">{a.category}</span>}
                <span className="hl-amsg">{a.message}</span>
                {a.date && <span className="hl-adate">{a.date}</span>}
              </div>
            ))}
          </div>
        )
      ) : <CalLoading err={hErr} />}

      {/* ── Structural classification distribution (drift in the router is visible) ── */}
      {h && total > 0 && (
        <>
          <h2 className="h">Where the rows went · structural router</h2>
          <div className="hl-dist panel" style={{ marginBottom: 18 }}>
            {([
              ["meeting", m.legevent_route_meeting ?? 0, "var(--ok)"],
              ["admin", m.legevent_route_admin ?? 0, "var(--ink-soft)"],
              ["executive", m.legevent_route_executive ?? 0, "var(--o-await)"],
              ["blank", m.legevent_route_blank ?? 0, "var(--ink-faint)"],
            ] as const).map(([k, v, col]) => (
              <div key={k} className="hl-distrow">
                <span className="hl-distk">{k}</span>
                <span className="hl-distbar"><span style={{ width: `${(100 * v) / total}%`, background: col }} /></span>
                <span className="hl-distv">{v.toLocaleString()} · {((100 * v) / total).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Raw counters for deep inspection ── */}
      {h && Object.keys(m).length > 0 && (
        <details className="hl-raw">
          <summary>Raw SYSTEM_METRICS · {Object.keys(m).length} counters</summary>
          <div className="hl-rawgrid">
            {Object.entries(m).map(([k, v]) => (
              <div key={k} className="hl-rawcell"><span className="hl-rawk">{k}</span><span className="hl-rawv">{v.toLocaleString()}</span></div>
            ))}
          </div>
        </details>
      )}

      <p className="muted hl-foot">
        Operator view (vision §3f) — the diagnostics the workers already emit, read live from the sheet.
        Bands are calibrated from the worker's breaker thresholds + steady state, not magic numbers.
        {hErr && <span style={{ color: "var(--stale)" }}> · calendar signals unavailable: {hErr}</span>}
      </p>
    </div>
  );
}

function CalLoading({ err }: { err: string | null }) {
  return err
    ? <p className="muted" style={{ color: "var(--stale)" }}>Calendar signals unavailable: {err}</p>
    : <p className="muted">Loading calendar-subsystem signals…</p>;
}
