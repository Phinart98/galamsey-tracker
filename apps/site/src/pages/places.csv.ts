import { active, summary } from '../lib/data';

const FIELDS = ['id', 'ha', 'first_seen', 'last_seen', 'licence', 'near', 'near_km', 'district', 'lat', 'lon'] as const;
// Every row repeats the data date, so a copy saved months ago still says how old it is
const DATA_UP_TO = summary?.data_date ?? '';
const cell = (v: unknown) => (v == null ? '' : /[",\n]/.test(String(v)) ? `"${String(v).replaceAll('"', '""')}"` : String(v));

export function GET() {
  const rows = active.map((p) => [...FIELDS.map((f) => cell(p[f])), DATA_UP_TO].join(','));
  return new Response([[...FIELDS, 'data_up_to'].join(','), ...rows].join('\n') + '\n', { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
}
