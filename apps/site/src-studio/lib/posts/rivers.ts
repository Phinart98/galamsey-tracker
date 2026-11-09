// River walks: a 5 km slice of one river, the stretch with the most land labelled Likely galamsey within 1 km of the
// water, a different one of the top three each time the river comes round. Rings only on Likely galamsey patches,
// as on every post (rules.ts), and only those inside the 2 km picture, so the number is what the picture shows.
// The reply links to that spot on the walk.
import sharp from 'sharp';
import { riverTileFile } from '../../../src/lib/og';
import { tileRel } from '../../../src/lib/pictures.mjs';
import { endText, pictureSpan, placesOn, rivers, walkHref, type River } from '../../../src/lib/rivers';
import { groundM, kmText, labelOnLeft, leftOf, TOWN_ORDER } from '../../../src/lib/rivers-geo';
import { count, haNum, NEAR_KM, shortMonth } from '../../../src/lib/format';
import { RIVER_H, RIVER_W, riverPost } from '../designs';
import { SITE, likelyLand, pick, type Post } from './rules';

export const riverPosts: Post[] = [];
const SLICE_KM = 5;

// The rows of a walk's picture from row r0, SLICE_KM long, joined across the tiles they fall in
async function slice(r: River, r0: number) {
  const rows = (SLICE_KM * 1000) / r.step_m;
  const per = r.tiles[0].rows;
  const parts: { input: Buffer; top: number; left: number }[] = [];
  for (let row = r0, top = 0; row < r0 + rows;) {
    const t = Math.floor(row / per);
    if (t >= r.tiles.length) break;
    const from = row - t * per;
    const take = Math.min(r0 + rows - row, r.tiles[t].rows - from);
    if (take <= 0) break;
    const file = await riverTileFile(tileRel(r.slug, r.version, t));
    parts.push({ input: await sharp(file).extract({ left: 0, top: from, width: r.width, height: take }).toBuffer(), top, left: 0 });
    row += take; top += take;
  }
  return sharp({ create: { width: r.width, height: rows, channels: 3, background: '#3d4a37' } }).composite(parts).jpeg({ quality: 90 }).toBuffer();
}

rivers.forEach((r, ri) => {
  const shown = placesOn(r.slug).filter((p) => likelyLand(p) && p.on.in_picture);
  if (!shown.length || r.length_km < SLICE_KM) return;
  // Every 5 km window, 1 km apart, scored by Likely galamsey hectares in it; the three best that do not overlap
  const windows: { k0: number; ha: number }[] = [];
  for (let k0 = 0; k0 + SLICE_KM <= r.length_km; k0 += 1) {
    windows.push({ k0, ha: shown.filter((p) => p.on.km >= k0 && p.on.km < k0 + SLICE_KM).reduce((a, p) => a + p.ha, 0) });
  }
  const best: typeof windows = [];
  for (const w of windows.sort((a, b) => b.ha - a.ha)) {
    if (w.ha <= 0 || best.length === 3) break;
    if (best.every((b) => Math.abs(b.k0 - w.k0) >= SLICE_KM)) best.push(w);
  }
  if (!best.length) return;
  const { k0 } = pick(best, ri);
  const inside = shown.filter((p) => p.on.km >= k0 && p.on.km < k0 + SLICE_KM);
  const ha = inside.reduce((a, p) => a + p.ha, 0);
  // Towns in the picture: inside its 2 km width, towns before villages, at least 0.8 km apart, three at most. A town
  // is named only if a ringed patch is within 2 km of it on the ground, as for every place a post names (format.ts closeTo)
  const close = (t: River['towns'][0]) => inside.some((p) => groundM(p, t) <= NEAR_KM * 1000);
  const towns: typeof r.towns = [];
  for (const t of r.towns.filter((t) => t.km >= k0 + 0.2 && t.km < k0 + SLICE_KM - 0.4 && Math.abs(t.off_m) <= r.half_m - 100 && close(t))
    .sort((a, b) => TOWN_ORDER[a.place] - TOWN_ORDER[b.place])) {
    if (towns.length < 3 && towns.every((u) => Math.abs(u.km - t.km) >= 0.8)) towns.push(t);
  }
  const past = towns[0];
  const end = endText(r);
  const leftTop = leftOf(r, k0), leftBottom = leftOf(r, k0 + SLICE_KM);
  // The days of the pictures in this slice (each 5 km tile lists its own)
  const days = [...new Set(r.tiles.slice(Math.floor(k0 / r.tile_km), Math.ceil((k0 + SLICE_KM) / r.tile_km)).flatMap((t) => t.days))].sort();
  const haText = haNum(ha);
  const where = past ? `The ${r.name} at ${past.name}` : `The ${r.name}, ${kmText(leftTop)} before ${end}`;
  const patches = inside.length === 1 ? 'one patch' : `${count(inside.length)} patches`;
  const x = (off: number) => RIVER_W * (0.5 - off / (2 * r.half_m));
  const y = (km: number) => ((km - k0) / SLICE_KM) * RIVER_H;
  riverPosts.push({
    slug: `river-${r.slug}`,
    kind: `River walk: the ${r.name}`,
    title: where,
    alt: `A satellite picture of ${SLICE_KM} km of the ${r.name}${past ? ` at ${past.name}` : ''}, the river running from top to bottom, 2 km wide. Rings mark ${patches} of land cleared in the last 12 months within 1 km of the water, labelled Likely galamsey, ${haText} hectares in all.`,
    text: pick([
      `${where}. In these ${SLICE_KM} km of river, satellites saw ${haText} hectares cleared in the last 12 months within 1 km of the water, in ${patches} with signs of mining and no licence to mine.\n\nThe river runs from top to bottom. Rings mark the patches.`,
      `${SLICE_KM} km of the ${r.name}, ${kmText(leftTop)} to ${kmText(leftBottom)} before ${end}. ${haText} hectares cleared in 12 months within 1 km of the water, in ${patches} with signs of mining and no licence to mine.\n\nWhat runs into the river here runs on downstream.`,
    ], ri),
    reply: `Follow the ${r.name} all the way to ${end}, as satellites saw it: ${SITE}${walkHref(r.slug, k0 + SLICE_KM / 2)}`,
    render: async () => riverPost({
      title: where,
      big: haText,
      line: `cleared in 12 months within 1 km of the water, in ${patches} with signs of mining and no licence to mine`,
      sub: `${SLICE_KM} km of the ${r.name}, ${kmText(leftTop)} to ${kmText(leftBottom)} before ${end}. The river runs from top to bottom.`,
      caption: pictureSpan(days, shortMonth), // "Jan 2026 to Oct 2026" fits the picture's width
      slice: await slice(r, Math.round((k0 * 1000) / r.step_m)),
      towns: towns.map((t) => ({ name: t.name, x: x(t.off_m), y: y(t.km), left: labelOnLeft(t.off_m) })),
      rings: inside.map((p) => ({ x: x(p.on.off_m), y: y(p.on.km), d: Math.max(36, 2 * Math.sqrt((p.ha * 1e4) / Math.PI) * (RIVER_W / (2 * r.half_m))) })),
    }),
  });
});
