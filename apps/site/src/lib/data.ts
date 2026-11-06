// Everything the pages print comes through here, read once at build time.
import fs from 'node:fs';
import path from 'node:path';
import { count } from './format';

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

export type Licence = 'no licence' | 'prospecting only' | 'restricted lease' | 'small-scale licence' | 'large-scale lease';

export interface Chip { date: string; files: Record<'720.webp', string> }

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
  // Set by the weekly signs step: open water in or beside the patch on land with no licence to mine
  likely_galamsey?: boolean;
  // Set here: the closest town or village with this patch within 1 km of it (data/towns.json)
  close?: string;
  signs?: { water: number; scene: string } | { missing: true; checked: string };
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
  covered: string[];
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
// A patch that merged into another keeps its old id in the index (ids are never reused), so its page would say it
// is no longer cleared. Instead it redirects to the place it joined, following a chain of merges to the end.
// An old id that is active again is a real place, so it keeps its own page.
export const redirects = new Map<string, string>();
for (const from of Object.keys(aliases)) {
  if (placeById.get(from)?.active) continue;
  let to = aliases[from];
  for (const seen = new Set([from]); aliases[to] && !placeById.get(to)?.active && !seen.has(to); seen.add(to)) to = aliases[to];
  if (placeById.get(to)?.active) redirects.set(from, to);
}

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
// Copernicus asks for "Contains modified Copernicus Sentinel data [Year]": the years of every picture on the site,
// inactive places' pages included. Empty when there are no pictures.
const pictureYearList = places.filter(hasPair).flatMap((p) => [p.chips.before.date, p.chips.after.date]).map((d) => d.slice(0, 4)).sort();
export const pictureYears = pictureYearList.length
  ? pictureYearList[0] === pictureYearList.at(-1) ? pictureYearList[0] : `${pictureYearList[0]}-${pictureYearList.at(-1)}`
  : '';
// Share cards for places of 3 ha or more (inactive ones keep their page, so they keep their card too).
// A card per small place would push the site past Cloudflare Pages' 20,000-file limit; they share the home card.
export const CARD_MIN_HA = 3;
export const hasCard = (p: Place): p is Place & { chips: { before: Chip; after: Chip } } => hasPair(p) && p.ha >= CARD_MIN_HA;
export const carded = places.filter(hasCard);



export const coverage = Object.values(tiles).map((t) => t.area);
export const placeNames = Object.values(tiles).map((t) => t.place);
// Where the totals come from, short enough for a headline however many areas are switched on
export const where = coverage.length > 1
  ? `across ${count(coverage.length)} areas of Ghana's southern gold belt`
  : `around ${placeNames[0] ?? 'the area we cover'}`;
export const lastSuccess: string | null = status.weekly?.last_success ?? null;
// The day of the last good weekly run, which is also when the licence register was last read
export const lastSuccessDate: string | null = lastSuccess?.slice(0, 10) ?? null;
// Trend points counted over every area switched on now. A new area recounts every month, and until that has
// finished the older points cover fewer areas, so they are left off the chart rather than mixed in.
export const trendNow = trend.filter((p) => {
  const on = Object.keys(tiles);
  return p.covered?.length === on.length && on.every((t) => p.covered.includes(t));
});
export const STALE_DAYS = 14;

export interface Town { name: string; place: string; district: string | null; lat: number; lon: number; ha: number; patches: number; ids: string[] }
// no_licence_ha: the part with no licence to mine (weekly runs from 9 November 2026 on), which the studio posts use
export interface WaterPlant { plant: string; river: string; ha: number; no_licence_ha?: number }

const townFile = read<{ radius_m: number; towns: Town[] }>(path.join(DATA, 'towns.json'), { radius_m: 1000, towns: [] });
export const towns = townFile.towns;
// The pipeline names a patch after the nearest town up to 15 km away, before any village. A village the patch
// touches (within 1 km, towns.json) says more, so each patch also gets the closest one of those
{
  const best = new Map<string, number>();
  for (const t of towns) for (const id of t.ids) {
    const p = placeById.get(id);
    if (!p) continue;
    const d = (t.lat - p.lat) ** 2 + ((t.lon - p.lon) * Math.cos((p.lat * Math.PI) / 180)) ** 2;
    if (d < (best.get(id) ?? Infinity)) { best.set(id, d); p.close = t.name; }
  }
}
export const townsNear = summary?.towns_near ?? null;
export const water = (summary?.water ?? []).slice().sort((a, b) => b.ha - a.ha);

// The villages the home page leads with: most cleared land within 1 km, each shown by its largest pictured
// patch. Neighbouring villages often share one big patch, so each picture is used once.
// `largest` says whether the picture is the town's own largest patch (it may have no clear picture yet, or a
// bigger town nearby may already show it), so the words never claim it when it is not
export function doorstep(n: number) {
  const used = new Set<string>();
  const out: { town: Town; place: Place & { chips: { before: Chip; after: Chip } }; largest: boolean }[] = [];
  for (const town of towns) {
    const place = town.ids.map((id) => placeById.get(id)).find((p) => p && hasPair(p) && !used.has(p.id));
    if (!place || !hasPair(place)) continue;
    used.add(place.id);
    out.push({ town, place, largest: place.id === town.ids[0] });
    if (out.length === n) break;
  }
  return out;
}
