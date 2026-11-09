// Distances on a river walk, shared by the pages (at build time) and the walk's script (in the browser).
// A walk's picture follows the river's valley, so it is shorter than the river: "km N" in a link (#km-N) is
// picture km, and what readers see is real river km still to go, read from km_left (one value per 0.5 km of
// picture, made by the pipeline, tracker/rivers.py km_left).

export interface WalkGeo { length_km: number; river_km: number; km_left: number[] }

// River km still to go from a point `km` down the picture
export function leftOf(r: WalkGeo, km: number): number {
  const a = r.km_left;
  if (!a?.length) return Math.max(0, r.length_km - km);
  const j = Math.max(0, Math.min(a.length - 2, Math.floor(km / 0.5)));
  const p0 = j * 0.5, p1 = Math.min((j + 1) * 0.5, r.length_km);
  const f = Math.min(1, Math.max(0, (km - p0) / (p1 - p0 || 1)));
  return Math.max(0, a[j] + (a[j + 1] - a[j]) * f);
}

// The picture km where `left` river km are still to go (the inverse of leftOf)
export function pictureKm(r: WalkGeo, left: number): number {
  let lo = 0, hi = r.length_km;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    if (leftOf(r, mid) > left) lo = mid; else hi = mid;
  }
  return (lo + hi) / 2;
}

// Metres on the ground between two lon/lat points (flat-earth, fine over a few km)
export function groundM(a: { lon: number; lat: number }, b: { lon: number; lat: number }): number {
  const k = Math.cos(((a.lat + b.lat) / 2) * (Math.PI / 180));
  return Math.hypot((a.lon - b.lon) * k, a.lat - b.lat) * 111_320;
}

// Distances read as "4.5 km" under 10 km and "62 km" above
export const kmText = (k: number) => (k < 10 ? `${k.toFixed(1)} km` : `${Math.round(k)} km`);

// Towns are labelled before villages
export const TOWN_ORDER: Record<string, number> = { city: 0, town: 1, village: 2 };
// A town's name runs away from the river, except near the picture's edge, where it turns inward so it is not cut off.
// off_m is positive on the picture's left. True: the name sits to the left of its dot
export const labelOnLeft = (offM: number) => (Math.abs(offM) > 400 ? offM < 0 : offM > 0);
