// What a post may show, and the lists and rankings several kinds of post share. Read this first: every post
// kind (town.ts, water.ts, places.ts, numbers.ts, explainers.ts) builds on it.
//
// The two rules (Philip, November 2026):
// 1. Galamsey only. Totals count land the register shows with no licence to mine (none at all, or only a licence
//    to explore), the same figures as the main site. Licensed mining is never shown or counted.
// 2. Every picture, outline and named place in a post is Likely galamsey: no licence to mine AND open water in or
//    right beside the patch, as in mining pits. Posts call this "signs of mining", in plain words.
import fs from 'node:fs';
import path from 'node:path';
import { active, hasPair, onePictureEach, placeById, summary, towns, type Chip, type Place, type Town } from '../../../src/lib/data';
import { DAY_MS, PITCH_HA, longDate, nearText, noLicenceToMine, placeName } from '../../../src/lib/format';
import { SITE } from '../../../src/lib/site';

// One post: the picture plus the three things Philip copies (post text, image description, first reply)
export interface Post {
  slug: string; // the picture's file name and the post's key in the plan (plan.ts)
  kind: string; // what kind of post it is, in words
  title: string;
  alt: string; // image description
  text: string; // the post itself
  reply: string; // the first reply, which carries the link
  render: () => Promise<Buffer>;
}

export { SITE };
export const pitches = (ha: number) => Math.round(ha / PITCH_HA);
export const dataDate = summary ? longDate(summary.data_date) : '';

// A number that moves on by one each week of data, so the posts rotate places and wording without anyone
// choosing: same data, same pick; next week, the next pick
export const WEEK = summary ? Math.floor(Date.parse(summary.data_date) / (7 * DAY_MS)) : 0;
export const pick = <T>(list: T[], salt = 0): T => list[(WEEK + salt) % list.length];

export type Pictured = Place & { chips: { before: Chip; after: Chip } };
export const galamsey = (p: Place) => noLicenceToMine(p.licence);
export const likelyLand = (p: Place) => galamsey(p) && !!p.likely_galamsey;
// A place a post may picture: Likely galamsey, with a before and after picture
export const showable = (p: Place): p is Pictured => hasPair(p) && likelyLand(p);
// "near Obuasi" when it is close, else "4 km from Obuasi" (format.ts nearText)
export const near = (p: Place) => nearText(p) ?? placeName(p);

// ---- Shared lists, largest first (active places come sorted by size) ----
export const unlicensed = active.filter(galamsey); // for totals
export const likely = active.filter(likelyLand); // what may be named
export const photo = active.filter(showable); // what may be pictured
// The six newest pictured patches of 2 ha or more
export const newest = photo.filter((p) => p.ha >= 2).sort((a, b) => b.first_seen.localeCompare(a.first_seen)).slice(0, 6);

// Real patch outlines, from the weekly run's working files (the weekly and daily studio jobs restore them)
export const outlines = (() => {
  const file = path.join(process.cwd(), '../../pipeline/out/places/latest.geojson');
  const map = new Map<string, number[][][]>();
  if (!fs.existsSync(file)) return map;
  for (const f of JSON.parse(fs.readFileSync(file, 'utf8')).features) {
    const g = f.geometry;
    if (g?.type === 'Polygon') map.set(f.properties.id, g.coordinates);
    else if (g?.type === 'MultiPolygon') map.set(f.properties.id, g.coordinates.flat());
  }
  return map;
})();

// Districts by land cleared with no licence to mine, most first
export const districtTotals = [...unlicensed.reduce((m, p) => (p.district ? m.set(p.district, (m.get(p.district) ?? 0) + p.ha) : m), new Map<string, number>())]
  .map(([district, ha]) => ({ district, ha })).sort((a, b) => b.ha - a.ha);

// Towns by land cleared with no licence to mine within 1 km (towns.json no_licence_ha, which counts only the part of
// each patch inside the ring), most first. `mine` lists their patches with no licence to mine, largest first.
// Summaries made before 9 November 2026 lack the figure, and the town posts then wait for the next weekly run.
export const townTotals = towns.filter((t) => (t.no_licence_ha ?? 0) > 0).map((t) => ({
  town: { ...t, ha: t.no_licence_ha! } as Town,
  mine: t.ids.map((id) => placeById.get(id)).filter((p): p is Place => !!p && p.active && galamsey(p)),
})).sort((a, b) => b.town.ha - a.town.ha);

// The town of the week: one of the eight top towns with a picture of land showing signs of mining, a different one
// each week of data (the top town stays first for months, so always posting it would repeat the same place). `rank`
// is the town's place in townTotals (0 = the most land of all). The news template sample uses the next one.
export const ranked = onePictureEach(townTotals, (r) => r.mine.filter(likelyLand), 8)
  .map(({ row, place, rank, largest }) => ({ town: row.town, place: place as Pictured, rank, largest }));
export const lead = ranked.length ? ranked[WEEK % ranked.length] : undefined;
export const second = ranked.length > 1 ? ranked[(WEEK + 1) % ranked.length] : undefined;

// The month in review covers the last month the data covers to its end. `top` is its largest pictured patch,
// which the New clearing post then skips, so the two never show the same place.
export const reviewMonth = (() => {
  if (!summary) return null;
  const dd = new Date(summary.data_date);
  const lastDay = new Date(dd.getTime() + DAY_MS).getUTCDate() === 1;
  const start = new Date(Date.UTC(dd.getUTCFullYear(), dd.getUTCMonth() - (lastDay ? 0 : 1), 1));
  const end = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 1));
  const inMonth = unlicensed.filter((p) => { const t = Date.parse(p.first_seen); return t >= start.getTime() && t < end.getTime(); });
  return { start, inMonth, top: inMonth.filter(showable)[0] };
})();
