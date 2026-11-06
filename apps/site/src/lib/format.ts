import type { Chip, Licence, Place } from './data';

const nf = new Intl.NumberFormat('en-GB');
export const num = (n: number) => nf.format(Math.round(n));
const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
// Small counts read better as words in a sentence
export const count = (n: number) => WORDS[n] ?? num(n);
export const Count = (n: number) => count(n).charAt(0).toUpperCase() + count(n).slice(1);
export const pct = (share: number | null | undefined) => (share == null ? 'n/a' : `${Math.round(share * 100)}%`);

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

// Month first ("October 31, 2026"), as Ghanaian newsrooms write it. No ordinals ("31st"): one less rule to get wrong
export function longDate(iso: string) {
  const [y, m, d] = iso.split('-').map(Number);
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

export function shortDate(iso: string) {
  const [y, m, d] = iso.split('-').map(Number);
  return `${MONTHS[m - 1].slice(0, 3)} ${d}, ${y}`;
}

export function monthName(ym: string) {
  const [y, m] = ym.split('-').map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}

// Every licence label, in the order pages list them (summaries made before November 2026 lack 'restricted lease')
export const LICENCES = Object.keys({
  'no licence': 0, 'prospecting only': 0, 'restricted lease': 0, 'small-scale licence': 0, 'large-scale lease': 0,
} satisfies Record<Licence, number>) as Licence[];

// No licence at all, or only one to explore: there is no licence to mine, so mining here is galamsey.
// The pipeline uses the same pair (pipeline/tracker/licences.py NO_LICENCE_TO_MINE).
export const NO_LICENCE_TO_MINE: readonly Licence[] = ['no licence', 'prospecting only'];
export const noLicenceToMine = (licence: Licence) => NO_LICENCE_TO_MINE.includes(licence);

// A 105 x 68 m football pitch (docs/sources.json football-pitch), the unit the site and posts use for area.
// The pipeline uses the same figure (pipeline/tracker/summary.py PITCH_HA).
export const PITCH_HA = 0.714;
export const DAY_MS = 864e5;

// The wording rule: describe the licence on the land, never a verdict on the people or the site
export const LICENCE_SHORT: Record<Licence, string> = {
  'no licence': 'No licence to mine',
  'prospecting only': 'Prospecting licence only',
  'restricted lease': 'Stone or sand lease',
  'small-scale licence': 'Small-scale mining licence',
  'large-scale lease': 'Large-scale mining lease',
};

export const LICENCE_SENTENCE: Record<Licence, string> = {
  'no licence': 'The register shows no mining licence on this land.',
  'prospecting only': 'The register shows only a prospecting licence here, which does not allow mining.',
  'restricted lease': 'The register shows this land inside a lease for quarrying stone or digging sand, gravel or clay. It does not allow mining gold.',
  'small-scale licence': 'The register shows this land inside a small-scale mining licence.',
  'large-scale lease': 'The register shows this land inside a large-scale mining lease.',
};

// geoBoundaries writes some district names with a lower-case word after a slash
export const tidyDistrict = (d: string) => d.replace(/\/(\w)/g, (_, c: string) => `/${c.toUpperCase()}`);

// "near X" only when the patch is close to X: its nearest town within 2 km, or else a town or village within 1 km
// of the patch. Otherwise the distance to the nearest town (up to 15 km), so nobody looks for the patch in the town
export const NEAR_KM = 2;
// Distances are shown rounded, so the cutoff applies to the rounded value: 2.4 km reads "near", 2.6 km "3 km from".
// A town with no distance on record is taken as near
export const closeTo = (p: Place) => (p.near && (p.near_km == null || Math.round(p.near_km) <= NEAR_KM) ? p.near : p.close ?? null);
export const nearLabel = (p: Place) => closeTo(p) ?? (p.near ? `${Math.round(p.near_km!)} km from ${p.near}` : null);
export const nearText = (p: Place) => { const c = closeTo(p); return c ? `near ${c}` : nearLabel(p); };

export function placeName(p: Place) {
  const n = nearText(p);
  if (n && p.district) return `${n}, ${tidyDistrict(p.district)}`;
  if (n) return n;
  if (p.district) return `in ${tidyDistrict(p.district)}`;
  return `at ${coords(p)}`;
}

export const district = (p: Place) => (p.district ? tidyDistrict(p.district) : null);

export function coords(p: Pick<Place, 'lat' | 'lon'>) {
  return `${Math.abs(p.lat).toFixed(4)}° ${p.lat >= 0 ? 'N' : 'S'}, ${Math.abs(p.lon).toFixed(4)}° ${p.lon >= 0 ? 'E' : 'W'}`;
}

export const hectares = (ha: number) => (ha < 10 ? `${ha.toFixed(1)} hectares` : `${num(ha)} hectares`);

const CHIPS = (import.meta.env.CHIPS_BASE_URL ?? '').replace(/\/$/, '');
export const chipUrl = (rel: string) => `${CHIPS}/${rel}`;

// One size per picture: a picture holds 160 real pixels across, so a smaller copy would add no detail
export const chipSrc = (chip: Chip) => chipUrl(chip.files['720.webp']);

// Why a place has no pictures. Most have simply not been tried yet, so never blame cloud unless we looked.
export type NoPicture = 'cloudy' | 'pending';
export const NO_PICTURE: Record<NoPicture, string> = {
  cloudy: 'No clear picture yet. Cloud or haze covered this place in every picture we checked.',
  pending: 'No pictures yet. New places get them within a week or two, the largest first.',
};
export function noPicture(p: Place): NoPicture {
  return p.chips && 'missing' in p.chips ? 'cloudy' : 'pending';
}

// Sharper pictures than ours, but often years older and undated in Maps: every link carries GOOGLE_NOTE nearby.
// Maps uses Google's documented link format (it opens the app on phones); Earth's format is not documented.
const ll = (lat: number, lon: number) => `${lat.toFixed(5)},${lon.toFixed(5)}`;
export const googleMaps = (lat: number, lon: number) =>
  `https://www.google.com/maps/@?api=1&map_action=map&center=${ll(lat, lon)}&zoom=16&basemap=satellite`;
export const googleEarth = (lat: number, lon: number) => `https://earth.google.com/web/@${ll(lat, lon)},0a,1500d,35y,0h,0t,0r`;
export const GOOGLE_NOTE = "Google's pictures are sharper than ours but can be years older, so they may show forest where the land has since been cleared. Google Earth shows the date of its picture.";
