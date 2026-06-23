// Robust LIS date parsing. Date.parse is unreliable here (CodeRabbit/Gemini/Qodo #165): it is
// format/locale-dependent for `M/D/YYYY`, and it treats `YYYY-MM-DD` as UTC midnight — which shifts the
// displayed calendar day by one in western timezones. Parse explicitly into a LOCAL date instead.
export function parseLisDate(raw: string | undefined | null): Date | null {
  const s = String(raw ?? "").trim();
  let y: number, mo: number, d: number;
  let m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(s);
  if (m) { y = +m[1]; mo = +m[2]; d = +m[3]; }
  else {
    m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(s);
    if (!m) return null;
    mo = +m[1]; d = +m[2]; y = +m[3];
  }
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;          // reject out-of-range parts
  const dt = new Date(y, mo - 1, d);
  // reject JS rollover (e.g. Feb 31 → Mar 3): the constructed date must echo the parts back
  if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) return null;
  return dt;
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
