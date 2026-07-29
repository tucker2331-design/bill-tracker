// Address → districts, client-side — F3 / queue item P2.
//
// THE PRIVACY PROPERTY IS THE TOPOLOGY, NOT A PROMISE. This call is made FROM THE USER'S BROWSER directly
// to the Census Bureau. The address never reaches our infrastructure, so "we do not store addresses" is not
// a policy we could quietly break — there is no code path on our side that could store one. That is why
// this lives in the front end rather than behind our Worker.
//
// The user then CONFIRMS the three districts and we persist those. Full rationale, including the
// redistricting detector that reads the layer vintage, is in docs/knowledge/district_lookup.md.
//
// No API key. Verified 2026-07-28 against 1000 Bank St, Richmond (the Virginia State Capitol — a public
// building, deliberately not a person's home): Senate 14, House 78, Congressional 4.

const GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress";

export interface DistrictLookup {
  house: string | null;
  senate: string | null;
  congress: string | null;
  /** The map vintage the Census used, e.g. "2024". Changing => districts were redrawn. */
  vintage: string | null;
}

/** Pull the district number out of a Census geography row, whichever field carries it. */
function numberFrom(row: Record<string, unknown> | undefined): string | null {
  if (!row) return null;
  for (const k of ["SLDUST", "SLDLST", "CD119", "CD118", "BASENAME"]) {
    const v = row[k];
    if (typeof v === "string" && v.trim()) return v.trim().replace(/^0+(?=\d)/, "");
  }
  return null;
}

/** The 4-digit year in a layer name like "2024 State Legislative Districts - Upper". */
const vintageFrom = (layerKey: string): string | null => layerKey.match(/\b(19|20)\d{2}\b/)?.[0] ?? null;

/**
 * Look up districts for an address.
 *
 * Throws on failure rather than returning empty districts: "we could not look this up" and "you live in no
 * district" must not be the same value. The caller shows the error and the manual-entry fields stay usable —
 * the lookup is a convenience, never a gate (docs/knowledge/district_lookup.md: fail-open).
 */
export async function lookupDistricts(address: string): Promise<DistrictLookup> {
  const q = address.trim();
  if (!q) throw new Error("Enter an address to look up.");

  const url = `${GEOCODER}?address=${encodeURIComponent(q)}&benchmark=Public_AR_Current`
    + "&vintage=Current_Current&format=json";
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Census lookup failed (HTTP ${res.status}). Enter your districts manually.`);

  const data = await res.json();
  const match = data?.result?.addressMatches?.[0];
  if (!match) throw new Error("No match for that address. Check it, or enter your districts manually.");

  const geos: Record<string, Record<string, unknown>[]> = match.geographies ?? {};
  let house: string | null = null, senate: string | null = null, congress: string | null = null;
  let vintage: string | null = null;

  for (const [layer, rows] of Object.entries(geos)) {
    const row = rows?.[0];
    if (/State Legislative Districts?\s*-\s*Lower/i.test(layer)) {
      house = numberFrom(row); vintage ??= vintageFrom(layer);
    } else if (/State Legislative Districts?\s*-\s*Upper/i.test(layer)) {
      senate = numberFrom(row); vintage ??= vintageFrom(layer);
    } else if (/Congressional Districts?/i.test(layer)) {
      congress = numberFrom(row);
    }
  }

  // Partial results are returned, not rejected: a user may legitimately sit outside one layer, and the form
  // lets them fill the gap by hand. Silently zeroing the missing one would be the wrong kind of tidy.
  return { house, senate, congress, vintage };
}
