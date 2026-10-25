// Everything the pages print comes through here, read once at build time.
import fs from 'node:fs';
import path from 'node:path';

const SITE = process.cwd();
const REPO = path.resolve(SITE, '../..');
const DATA = path.join(REPO, 'data');

function read<T>(file: string, fallback: T): T {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8')) as T;
  } catch {
    return fallback;
  }
}

export type Licence = 'no licence' | 'prospecting only' | 'small-scale licence' | 'large-scale lease';

export interface Chip { date: string; files: Record<'360.avif' | '360.webp' | '720.avif' | '720.webp', string> }

export interface Place {
  id: string;
  active: boolean;
  ha: number;
  first_seen: string;
  last_seen: string;
  licence: Licence;
  near: string | null;
  near_km: number | null;
  district: string | null;
  lon: number;
  lat: number;
  tile: string;
  chips: null | { missing: true; checked: string } | { before: Chip; after: Chip };
}

export interface Summary {
  total_ha: number;
  football_pitches: number;
  patches: number;
  by_licence: Record<Licence, { ha: number; share: number }>;
  no_licence_to_mine: { ha: number; share: number | null };
  top_places: { id: string; ha: number }[];
  top_districts: { district: string; ha: number }[];
  data_date: string;
  window_days: number;
  tiles: string[];
  method_version: string;
  towns_near?: { radius_m: number; count: number; with_5ha: number };
  water?: WaterPlant[];
}

export interface TrendPoint {
  date: string;
  total_ha: number;
  no_licence_to_mine: { ha: number; share: number | null };
  tiles: string[];
  settled?: boolean;
}

export interface Tile { enabled: boolean; place: string; area: string; checked: string; checked_patches: number; showed_mining: number; bounds: [number, number, number, number] }

export const summary = read<Summary | null>(path.join(DATA, 'summary/latest.json'), null);
export const status = read<Record<string, any>>(path.join(DATA, 'status.json'), {});
export const aliases = read<Record<string, string>>(path.join(DATA, 'places/aliases.json'), {});
export const trend = Object.values(
  read<{ points: Record<string, TrendPoint> }>(path.join(DATA, 'trend.json'), { points: {} }).points,
).sort((a, b) => a.date.localeCompare(b.date));
export const tiles = Object.fromEntries(
  Object.entries(read<Record<string, Tile>>(path.join(REPO, 'pipeline/tiles.json'), {})).filter(([, t]) => t.enabled),
);
export const places = Object.values(read<Record<string, Place>>(path.join(SITE, '.data/places.json'), {}));
export const placeById = new Map(places.map((p) => [p.id, p]));

export const bulletins = fs.existsSync(path.join(DATA, 'summary'))
  ? fs.readdirSync(path.join(DATA, 'summary'))
      .filter((f) => /^\d{4}-\d{2}\.json$/.test(f))
      .map((f) => ({ month: f.slice(0, 7), summary: read<Summary>(path.join(DATA, 'summary', f), null as never) }))
      .sort((a, b) => b.month.localeCompare(a.month))
  : [];

export function hasPair(p: Place): p is Place & { chips: { before: Chip; after: Chip } } {
  return !!p.chips && 'before' in p.chips;
}

export const active = places.filter((p) => p.active).sort((a, b) => b.ha - a.ha);
export const withPairs = active.filter(hasPair);



export const coverage = Object.values(tiles).map((t) => t.area);
export const placeNames = Object.values(tiles).map((t) => t.place);
// Where the totals come from, short enough for a headline however many areas are switched on
export const where = coverage.length > 1
  ? `across ${coverage.length} areas of Ghana's southern gold belt`
  : `around ${placeNames[0] ?? 'the area we cover'}`;
export const check = Object.values(tiles).reduce(
  (acc, t) => ({ patches: acc.patches + (t.checked_patches ?? 0), mining: acc.mining + (t.showed_mining ?? 0) }),
  { patches: 0, mining: 0 },
);

export const lastSuccess: string | null = status.weekly?.last_success ?? null;
export const STALE_DAYS = 14;

export interface Town { name: string; place: string; district: string | null; lat: number; lon: number; ha: number; patches: number; ids: string[] }
export interface WaterPlant { plant: string; river: string; ha: number }

const townFile = read<{ radius_m: number; towns: Town[] }>(path.join(DATA, 'towns.json'), { radius_m: 1000, towns: [] });
export const towns = townFile.towns;
export const townsNear = summary?.towns_near ?? null;
export const water = (summary?.water ?? []).slice().sort((a, b) => b.ha - a.ha);

// The villages the home page leads with: most cleared land within 1 km, each shown by its largest pictured
// patch. Neighbouring villages often share one big patch, so each picture is used once.
export function doorstep(n: number) {
  const used = new Set<string>();
  const out: { town: Town; place: Place & { chips: { before: Chip; after: Chip } } }[] = [];
  for (const town of towns) {
    const place = town.ids.map((id) => placeById.get(id)).find((p) => p && hasPair(p) && !used.has(p.id));
    if (!place || !hasPair(place)) continue;
    used.add(place.id);
    out.push({ town, place });
    if (out.length === n) break;
  }
  return out;
}
