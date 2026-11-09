import { rivers, placesOn } from '../lib/rivers';
import { leftOf } from '../lib/rivers-geo';

// The river walks as data: each river's towns, rivers joining and water plants, and the patches within 1 km of it,
// placed by river km still to go
export function GET() {
  const body = rivers.map((r) => ({
    river: r.name, ends: r.ends, river_km: r.river_km, pictures_from: r.dates[0] ?? null, pictures_to: r.dates.at(-1) ?? null,
    towns: r.towns.filter((t) => t.water_m <= 1000).map((t) => ({ name: t.name, km_to_end: +leftOf(r, t.km).toFixed(1) })),
    joins: r.joins.filter((j) => j.name).map((j) => ({ name: j.name, km_to_end: +leftOf(r, j.km).toFixed(1) })),
    water_plants: r.plants.map((p) => ({ name: p.name, km_to_end: +leftOf(r, p.km).toFixed(1) })),
    patches: placesOn(r.slug).map((p) => ({ id: p.id, ha: p.ha, km_to_end: +leftOf(r, p.on.km).toFixed(1), metres_from_water: p.on.river_m })),
  }));
  return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
}
