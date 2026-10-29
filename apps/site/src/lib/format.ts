import type { Chip, Licence, Place } from './data';

const nf = new Intl.NumberFormat('en-GB');
export const num = (n: number) => nf.format(Math.round(n));
const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
// Small counts read better as words in a sentence
export const count = (n: number) => WORDS[n] ?? num(n);
export const Count = (n: number) => count(n).charAt(0).toUpperCase() + count(n).slice(1);
export const pct = (share: number | null | undefined) => (share == null ? 'n/a' : `${Math.round(share * 100)}%`);

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export function longDate(iso: string) {
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

export function shortDate(iso: string) {
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MONTHS[m - 1].slice(0, 3)} ${y}`;
}

export function monthName(ym: string) {
  const [y, m] = ym.split('-').map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}

// The wording rule: describe the licence on the land, never a verdict on the people or the site
export const LICENCE_SHORT: Record<Licence, string> = {
  'no licence': 'No licence to mine',
  'prospecting only': 'Prospecting licence only',
  'small-scale licence': 'Small-scale mining licence',
  'large-scale lease': 'Large-scale mining lease',
};

export const LICENCE_SENTENCE: Record<Licence, string> = {
  'no licence': 'There is no mining licence on this land.',
  'prospecting only': 'The only licence here is for prospecting, which does not allow mining.',
  'small-scale licence': 'This land is inside a small-scale mining licence.',
  'large-scale lease': 'This land is inside a large-scale mining lease.',
};

// geoBoundaries writes some district names with a lower-case word after a slash
export const tidyDistrict = (d: string) => d.replace(/\/(\w)/g, (_, c: string) => `/${c.toUpperCase()}`);

export function placeName(p: Place) {
  if (p.near && p.district) return `near ${p.near}, ${tidyDistrict(p.district)}`;
  if (p.near) return `near ${p.near}`;
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
