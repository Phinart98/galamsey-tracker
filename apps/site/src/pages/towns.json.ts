import { towns } from '../lib/data';
import { tidyDistrict } from '../lib/format';

// Read by the home page search and the map's town filter, only when someone uses them.
// Each row: [name, district, hectares, patches, patch ids largest first, lat, lon]. The map URL names a town as
// "Name (District)", which stays the same from week to week, unlike a row number.
export function GET() {
  const rows = towns.map((t) => [t.name, t.district ? tidyDistrict(t.district) : null, t.ha, t.patches, t.ids, t.lat, t.lon]);
  return new Response(JSON.stringify(rows), { headers: { 'Content-Type': 'application/json' } });
}
