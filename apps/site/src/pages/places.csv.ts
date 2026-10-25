import { active } from '../lib/data';

const FIELDS = ['id', 'ha', 'first_seen', 'last_seen', 'licence', 'near', 'near_km', 'district', 'lat', 'lon'] as const;
const cell = (v: unknown) => (v == null ? '' : /[",\n]/.test(String(v)) ? `"${String(v).replaceAll('"', '""')}"` : String(v));

export function GET() {
  const rows = active.map((p) => FIELDS.map((f) => cell(p[f])).join(','));
  return new Response([FIELDS.join(','), ...rows].join('\n') + '\n', { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
}
