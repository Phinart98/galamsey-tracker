// The river walks (pages /rivers/ and /rivers/<slug>/), read once at build time.
// Pictures and markers come from pipeline/out/rivers/<slug>.json, kept beside its tiles on the rivers-state release
// and made every three months by rivers.yml (pipeline tracker/rivers.py). The rings come from the weekly place
// index, so they stay current between pictures.
import fs from 'node:fs';
import path from 'node:path';
import { active, type Place, type PlaceOnRiver } from './data';
import { chipUrl, monthName } from './format';
import { tileRel } from './pictures.mjs';
import { kmText, leftOf } from './rivers-geo';

const REPO = path.resolve(process.cwd(), '../..');

export interface Town { name: string; place: 'city' | 'town' | 'village'; km: number; off_m: number; water_m: number; lon: number; lat: number }
export interface Join { name: string | null; slug: string | null; km: number; side: 'left' | 'right' }
export interface River {
  slug: string; name: string; ends: string; joins_to: string | null; version: string; visible_km2: number;
  length_km: number; river_km: number; streams_km: number; step_m: number; half_m: number; width: number; tile_km: number;
  km_left: number[]; course: [number, number][]; towns: Town[]; joins: Join[]; plants: { name: string; km: number }[];
  zone_end_km: number | null; tiles: { rows: number; days: string[]; cloud: number }[]; dates: string[];
}

const order = (JSON.parse(fs.readFileSync(path.join(REPO, 'pipeline/rivers.json'), 'utf8')) as { slug: string }[]).map((r) => r.slug);
const OUT = path.join(REPO, 'pipeline/out');
const file = (slug: string) => path.join(OUT, 'rivers', `${slug}.json`);
// Rivers whose pictures have been made, in the pipeline's order (the Pra, then the rivers that join it, then the rest).
// A river with a tile missing from disk is left out (no page, link or post) rather than shown with empty boxes:
// the tiles are published from the same disk (scripts/rivers.mjs), which warns about it.
const complete = (r: River) => r.tiles.every((_, i) => fs.existsSync(path.join(OUT, tileRel(r.slug, r.version, i))));
export const rivers: River[] = order.filter((s) => fs.existsSync(file(s)))
  .map((s): River => JSON.parse(fs.readFileSync(file(s), 'utf8'))).filter(complete);
export const riverBySlug = new Map(rivers.map((r) => [r.slug, r]));

export const toSea = (r: River) => /sea/.test(r.ends);
// Where a walk ends, as the words read: "the sea" or "the Pra"
export const endText = (r: River) => (toSea(r) ? 'the sea' : r.ends);
export const tileUrl = (r: River, i: number) => chipUrl(tileRel(r.slug, r.version, i));
// A spot on a walk: #km-N is picture km, which the walk's script scrolls to
export const walkHref = (slug: string, km: number) => `/rivers/${slug}/#km-${km.toFixed(1)}`;

// The river this one flows into, if we walk that one too, and where on its walk (picture km) they meet
export function parentOf(r: River) {
  const parent = r.joins_to ? riverBySlug.get(r.joins_to) : undefined;
  const at = parent?.joins.find((j) => j.slug === r.slug)?.km;
  return parent && at != null ? { river: parent, km: at, left: leftOf(parent, at) } : null;
}

// Active places within 1 km of each river's water, down the river, worked out once per build
const onEach = new Map<string, (Place & { on: PlaceOnRiver })[]>();
for (const p of active) for (const on of p.rivers ?? []) {
  if (!onEach.has(on.slug)) onEach.set(on.slug, []);
  onEach.get(on.slug)!.push({ ...p, on });
}
for (const list of onEach.values()) list.sort((a, b) => a.on.km - b.on.km);
export const placesOn = (slug: string) => onEach.get(slug) ?? [];

export function totals(slug: string) {
  const ps = placesOn(slug);
  return { places: ps, ha: ps.reduce((a, p) => a + p.ha, 0), likely: ps.filter((p) => p.likely_galamsey).length };
}

// The 5 km of picture shown small for a river: the one with most cleared land, among those with almost no cloud
export function thumbnail(r: River): number {
  const per = new Map<number, number>();
  for (const p of placesOn(r.slug)) {
    const t = Math.min(r.tiles.length - 1, Math.floor(p.on.km / r.tile_km));
    per.set(t, (per.get(t) ?? 0) + p.ha);
  }
  const all = r.tiles.map((_, i) => i);
  const clear = all.filter((i) => r.tiles[i].cloud < 0.02);
  const pool = clear.length ? clear : all;
  return pool.reduce((best, i) => ((per.get(i) ?? 0) > (per.get(best) ?? 0) ? i : best), pool[Math.floor(pool.length / 2)]);
}

// Where a place sits on the nearest river whose walk has been made, in words, with the link to that spot
export function onRiver(p: Place) {
  const on = p.rivers?.find((x) => riverBySlug.has(x.slug));
  if (!on) return null;
  const r = riverBySlug.get(on.slug)!;
  return { river: r, href: walkHref(r.slug, on.km), text: `By the ${r.name}, ${kmText(leftOf(r, on.km))} before ${endText(r)}` };
}

// The walk that passes a water plant, and the link to that spot
export function plantOnRiver(plant: string) {
  for (const r of rivers) {
    const at = r.plants.find((x) => x.name === plant);
    if (at) return { river: r, href: walkHref(r.slug, at.km) };
  }
  return null;
}

// The months of the pictures, as one span ("December 2025 to March 2026"); `month` formats a YYYY-MM
export function pictureSpan(dates: string[], month = monthName) {
  if (!dates.length) return '';
  const [a, b] = [month(dates[0].slice(0, 7)), month(dates.at(-1)!.slice(0, 7))];
  return a === b ? a : `${a} to ${b}`;
}
