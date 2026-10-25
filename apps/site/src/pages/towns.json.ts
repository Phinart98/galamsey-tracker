import { towns } from '../lib/data';

// The home page search loads this only when someone starts typing: [name, district, hectares, patches, largest patch id]
export function GET() {
  const rows = towns.map((t) => [t.name, t.district, t.ha, t.patches, t.ids[0]]);
  return new Response(JSON.stringify(rows), { headers: { 'Content-Type': 'application/json' } });
}
