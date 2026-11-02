// The chamber subway — one drawing for any state, from its settings (owner 2026-11-02: "every subway map", state
// differences are settings, never a new drawing). Same visual language as Virginia's v9 subway (Timeline.tsx):
// Senate track on top, House below; two grey lines, one per chamber a bill STARTED in; a line moves to the other
// chamber's track for that state's second-chamber stages (and back, for a stage held in the first chamber again —
// PA's concurrence); the lines meet at the Governor, which forks into the outcomes the source carries.
// Counts: bills sitting at a station; under it, the ones parked / idle there; "✕ N" in red = ended there.
// A deadline line is drawn only for a state that has one (none here: Virginia still draws its own map for now).
import type { PipelineCounts, PipelineSettings } from "../data/pipeline_rules";
import { trackOf } from "../data/pipeline_rules";

type Hit = (k: string, n: number, label: string) => Record<string, unknown>;
const Y = { Senate: 140, House: 280 } as const, GY = 210;
const LINE = { Senate: "#C9D0D4", House: "#6E787E" } as const;   // the Senate-started / House-started lines (VA's greys)
const OUT_LABEL: Record<string, string> = { signed: "Law", awaiting_governor: "Waiting", vetoed: "Vetoed" };

export function ChamberSubway({ s, c, labels, hit }: {
  s: PipelineSettings; c: PipelineCounts; labels: Record<string, string>; hit: Hit;
}) {
  const n = (v: number) => v.toLocaleString();
  // x positions: a fixed step, plus a wider gap wherever the lines change track
  const xs: number[] = [];
  s.stations.forEach((st, i) => {
    if (i === 0) { xs.push(90); return; }
    const swap = trackOf(st, "House", s) !== trackOf(s.stations[i - 1], "House", s);
    xs.push(xs[i - 1] + (swap ? 200 : 130));
  });
  const GX = xs[xs.length - 1] + 150, W = GX + 230;
  const path = (first: "House" | "Senate") => {
    let d = `M20 ${Y[trackOf(s.stations[0], first, s)]}`;
    s.stations.forEach((st, i) => {
      const y = Y[trackOf(st, first, s)];
      if (i > 0) {
        const py = Y[trackOf(s.stations[i - 1], first, s)];
        if (py !== y) { const a = xs[i - 1] + 35, b = xs[i] - 35, m = (a + b) / 2; d += ` H${a} C${m} ${py} ${m} ${y} ${b} ${y}`; }
      }
      d += ` H${xs[i]}`;
    });
    const ly = Y[trackOf(s.stations[s.stations.length - 1], first, s)], lx = xs[xs.length - 1];
    return `${d} H${lx + 50} C${GX - 45} ${ly} ${GX - 45} ${GY} ${GX} ${GY}`;
  };
  const swaps = s.stations.slice(1).map((st, i) => trackOf(st, "House", s) !== trackOf(s.stations[i], "House", s) ? (xs[i] + xs[i + 1]) / 2 : 0).filter(Boolean);
  const outs = s.governorOutcomes;
  return (
    <svg viewBox={`0 0 ${W} 410`} role="img" aria-label="Pipeline: two lines, one per starting chamber, that move to the other chamber's track when a bill passes and meet at the Governor">
      <g className="sw">
        {swaps.map((x, i) => (
          <g key={x}>
            <line x1={x} x2={x} y1="62" y2="352" stroke="var(--line-strong)" strokeDasharray="4 5" />
            <text x={x} y="368" className="sw-th" textAnchor="middle">{i === 0 ? "to the other chamber" : "back to the first chamber"}</text>
          </g>
        ))}
        <text x="24" y={Y.Senate - 50} className="sw-th">Senate</text>
        <text x="24" y={Y.House + 66} className="sw-th">House</text>
        <path d={path("Senate")} fill="none" stroke={LINE.Senate} strokeWidth="6" strokeLinecap="round" />
        <path d={path("House")} fill="none" stroke={LINE.House} strokeWidth="6" strokeLinecap="round" />
        {s.stations.map((st, i) => (
          <g key={st}>
            <text x={xs[i]} y="40" className="sw-th" textAnchor="middle">{labels[st] ?? st}</text>
            {(["Senate", "House"] as const).map((side) => {
              const y = Y[side], up = side === "Senate";
              const first = trackOf(st, "House", s) === side ? "House" : "Senate";   // which line runs here
              const k = `${st}|${side}`, still = c.at[k] || 0;
              const parked = c.sub[`${k}|parked`] || 0, idle = c.sub[`${k}|idle`] || 0, ended = c.sub[`${k}|ended`] || 0;
              const where = `${side} · ${labels[st] ?? st}`, dy = up ? 34 : -34;
              return (
                <g key={side}>
                  <circle cx={xs[i]} cy={y} r="10" fill="var(--surface)" stroke={LINE[first]} strokeWidth="4" />
                  <text x={xs[i]} y={up ? y - 24 : y + 38} textAnchor="middle" className={`sw-n${still ? "" : " zero"}`}
                    {...hit(`at|${k}`, still, `${where} · here now`)}>{n(still)}</text>
                  {(parked > 0 || idle > 0) && (
                    <text x={xs[i]} y={up ? y - 48 : y + 58} textAnchor="middle" className="sw-l">
                      {parked > 0 && <tspan {...hit(`sub|${k}|parked`, parked, `${where} · parked`)}>{n(parked)} parked</tspan>}
                      {parked > 0 && idle > 0 && " · "}
                      {idle > 0 && <tspan {...hit(`sub|${k}|idle`, idle, `${where} · idle`)}>{n(idle)} idle</tspan>}
                    </text>
                  )}
                  {ended > 0 && <>
                    <line x1={xs[i]} y1={y} x2={xs[i] + 20} y2={y + dy} stroke="var(--red)" strokeOpacity=".7" strokeWidth="3" strokeLinecap="round" />
                    <text x={xs[i] + 26} y={y + dy + (up ? 10 : 0)} className="sw-e" {...hit(`sub|${k}|ended`, ended, `${where} · ended`)}>✕ {n(ended)}</text>
                  </>}
                </g>
              );
            })}
          </g>
        ))}
        <circle cx={GX} cy={GY} r="16" fill="var(--surface)" stroke="var(--o-signed)" strokeWidth="4" />
        <text x={GX} y="40" className="sw-th" textAnchor="middle">{labels.governor ?? "Governor"}</text>
        {outs.map((o, j) => {
          const y = outs.length === 1 ? GY : 150 + (120 * j) / Math.max(1, outs.length - 1), v = c.out[o] || 0;
          return (
            <g key={o}>
              <path d={`M${GX + 16} ${GY} C${GX + 40} ${GY} ${GX + 40} ${y} ${GX + 66} ${y}`} fill="none"
                stroke={o === "signed" ? "var(--o-signed)" : o === "vetoed" ? "var(--red)" : "var(--accent)"} strokeWidth="3" />
              <text x={GX + 74} y={y + 6}>
                <tspan className={`sw-m${v ? "" : " zero"}`} {...hit(`out|${o}`, v, OUT_LABEL[o] ?? o)}>{n(v)}</tspan>
                <tspan className="sw-l" dx="8">{o === "signed" ? labels.law ?? "Law" : OUT_LABEL[o] ?? o}</tspan>
              </text>
            </g>
          );
        })}
        <text x="20" y="400" className="sw-l">Ended along the line:</text>
        <text x="152" y="400" className="sw-e">{n(c.totals.ended)} defeated</text>
        <text x="250" y="400" className="sw-l">· Stopped, may return: {n(c.totals.parked)} parked · {n(c.totals.idle)} idle {s.idleDays >= 365 ? "1 yr+" : `${s.idleDays} d+`}</text>
        <line x1={W - 400} x2={W - 370} y1="396" y2="396" stroke={LINE.Senate} strokeWidth="5" />
        <text x={W - 362} y="400" className="sw-l">started in the Senate</text>
        <line x1={W - 200} x2={W - 170} y1="396" y2="396" stroke={LINE.House} strokeWidth="5" />
        <text x={W - 162} y="400" className="sw-l">started in the House</text>
      </g>
    </svg>
  );
}
