import { active, summary, type Place } from '../lib/data';

const FIELDS = ['id', 'ha', 'first_seen', 'last_seen', 'licence', 'near', 'near_km', 'district', 'lat', 'lon'] as const;
// Every row repeats the data date, so a copy saved months ago still says how old it is
const DATA_UP_TO = summary?.data_date ?? '';
// Blank until the weekly job has measured the place (it only measures land with no licence to mine)
const water = (p: Place) => (p.signs && 'water' in p.signs ? p.signs.water : null);
const likely = (p: Place) => (water(p) == null ? null : p.likely_galamsey ? 'yes' : 'no');
const cell = (v: unknown) => (v == null ? '' : /[",\n]/.test(String(v)) ? `"${String(v).replaceAll('"', '""')}"` : String(v));

export function GET() {
  const rows = active.map((p) => [...FIELDS.map((f) => cell(p[f])), cell(likely(p)), cell(water(p)), DATA_UP_TO].join(','));
  return new Response([[...FIELDS, 'likely_galamsey', 'open_water_share', 'data_up_to'].join(','), ...rows].join('\n') + '\n', { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
}
