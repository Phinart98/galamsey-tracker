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

const NO_LICENCE_TO_MINE: Licence[] = ['no licence', 'prospecting only'];
export const noLicenceToMine = (p: Place) => NO_LICENCE_TO_MINE.includes(p.licence);

// The lead picture: the largest recent patch with a clear pair, preferring land with no licence to mine
export const lead = withPairs.find(noLicenceToMine) ?? withPairs[0] ?? null;

export const coverage = Object.values(tiles).map((t) => t.area);
export const placeNames = Object.values(tiles).map((t) => t.place);
export const check = Object.values(tiles).reduce(
  (acc, t) => ({ patches: acc.patches + (t.checked_patches ?? 0), mining: acc.mining + (t.showed_mining ?? 0) }),
  { patches: 0, mining: 0 },
);

export const lastSuccess: string | null = status.weekly?.last_success ?? null;
export const STALE_DAYS = 14;
