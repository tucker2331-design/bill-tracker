// A tiny inline trend line — the "fever chart" beside a gauge's point-in-time value. Direction matters
// more than the instant: "0, 0, 1, 3, 7 — climbing" is an early warning even while today's value is still
// green. Reads the per-cycle Metrics_History series (data/history.ts). Pure SVG, no deps.
//
// "Never pretend": with fewer than two points there is no trend to draw, so we render a muted "—" rather
// than a flat line that would imply a measured-steady history we don't have.

export function Sparkline({
  values,
  width = 96,
  height = 22,
  // lowerBetter: a RISING line is bad (Section-9, violations) → tint the trend red when the last point is
  // above the first. higherBetter flips it. Tone is a hint, not a verdict — the gauge's band is the verdict.
  lowerBetter = true,
}: {
  values: number[];
  width?: number;
  height?: number;
  lowerBetter?: boolean;
}) {
  if (!values || values.length < 2) {
    return <span className="spark-empty" aria-hidden="true">—</span>;
  }
  const n = values.length;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1; // avoid /0 when the series is dead-flat
  const pad = 2;
  const w = width - pad * 2;
  const h = height - pad * 2;
  const x = (i: number) => pad + (n === 1 ? 0 : (i / (n - 1)) * w);
  const y = (v: number) => pad + h - ((v - min) / span) * h;
  const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");

  const first = values[0];
  const last = values[n - 1];
  const rising = last > first;
  const flat = last === first;
  // Worsening = moving the wrong way for this metric's polarity.
  const worsening = !flat && (lowerBetter ? rising : !rising);
  const tone = flat ? "flat" : worsening ? "bad" : "good";
  const lastX = x(n - 1);
  const lastY = y(last);

  return (
    <svg
      className={`spark spark-${tone}`}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`trend: ${values.length} points, ${flat ? "flat" : worsening ? "worsening" : "improving"} (now ${last})`}
    >
      <polyline className="spark-line" points={pts} fill="none" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle className="spark-dot" cx={lastX} cy={lastY} r="1.9" />
    </svg>
  );
}
