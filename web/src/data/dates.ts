// Robust LIS date parsing. Date.parse is unreliable here (CodeRabbit/Gemini/Qodo #165): it is
// format/locale-dependent for `M/D/YYYY`, and it treats `YYYY-MM-DD` as UTC midnight — which shifts the
// displayed calendar day by one in western timezones. Parse explicitly into a LOCAL date instead.
export function parseLisDate(raw: string | undefined | null): Date | null {
  const s = String(raw ?? "").trim();
  let m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(s);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
  m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(s);
  if (m) return new Date(+m[3], +m[1] - 1, +m[2]);
  return null;
}

// Local calendar-day key, for same-day comparison.
export function dayKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Sort key (ms) for a LIS date string; 0 (oldest) when unparseable.
export function dateSort(raw: string): number {
  const d = parseLisDate(raw);
  return d ? d.getTime() : 0;
}
