// Posts that show real places: new clearing, the shape of one patch, twelve shapes, check it yourself, licensed to
// explore, ten towns and the newest patches. Every place they picture or name is Likely galamsey (rules.ts).
import { active, summary } from '../../../src/lib/data';
import { DAY_MS, LICENCE_SENTENCE, count, hectares, longDate, nearLabel, num, placeName, shortDate, tidyDistrict } from '../../../src/lib/format';
import { explorePost, findPost, platePost, shapePost, sheetPost, townPost, townsPost } from '../designs';
import { SITE, WEEK, dataDate, likely, likelyLand, near, newest, outlines, photo, pick, pitches, reviewMonth, townTotals, type Post } from './rules';
import waterMap from '../../../src/data/water-map.json';

export const placePosts: Post[] = [];
const SIGNS = 'signs of mining (open water, as in mining pits)';

// New clearing: the largest pictured patch first seen in the last two (or four) months, skipping the month in
// review's picture so the two posts never show the same place
if (summary) {
  const end = Date.parse(summary.data_date);
  const since = (days: number) => photo.filter((p) => p.ha >= 3 && Date.parse(p.first_seen) >= end - days * DAY_MS);
  // New places often wait a while for a cloud-free picture, so look back four months when two find nothing
  const notMonth = (list: typeof photo) => list.filter((p) => p.id !== reviewMonth?.top?.id);
  const days = notMonth(since(60)).length ? 60 : 120;
  const months = days === 60 ? 'two' : 'four';
  const [fresh] = notMonth(since(days));
  // When the month in review took the largest, this is the next one, and the words say so
  const rank = fresh && since(days)[0]?.id !== fresh.id ? 'one of the largest patches' : 'the largest patch';
  if (fresh) {
    const where = placeName(fresh);
    placePosts.push({
      slug: 'new',
      kind: 'New clearing',
      title: `New clearing ${where}`,
      alt: `Two satellite pictures of the same land ${where}: before, ${longDate(fresh.chips.before.date)}, and after, ${longDate(fresh.chips.after.date)}.`,
      text: `${hectares(fresh.ha)} of land cleared ${where}, first seen by satellite on ${longDate(fresh.first_seen)}.

It is ${rank} with ${SIGNS} that satellites first saw in the last ${months} months. ${LICENCE_SENTENCE[fresh.licence]}`,
      reply: `Before and after up close: ${SITE}/places/${fresh.id}/`,
      render: () => townPost({
        headline: `${hectares(fresh.ha)} of land newly cleared ${where}`,
        sub: `First seen by satellite on ${longDate(fresh.first_seen)}, ${rank} with signs of mining first seen in the last ${months} months. ${LICENCE_SENTENCE[fresh.licence]}`,
        before: fresh.chips.before, after: fresh.chips.after,
      }),
    });
  }
}

// The largest Likely galamsey patches that have an outline, for the shape posts
const shaped = likely.filter((p) => outlines.has(p.id));

// The shape of it: one of the ten largest, its real outline beside a football pitch at the same scale
if (shaped.length && summary) {
  const top = shaped.slice(0, 10);
  const rank = WEEK % top.length;
  const p = top[rank];
  // "The largest" only when no bigger Likely galamsey patch lacks an outline
  const standing = rank === 0 && likely[0]?.id === p.id ? 'the largest patch we track with signs of mining' : `one of the ${count(top.length)} largest patches we track with signs of mining`;
  placePosts.push({
    slug: 'shape', kind: 'The shape of it', title: `The shape of it: ${hectares(p.ha)} ${near(p)}`,
    alt: `The outline of one cleared patch ${near(p)}, ${hectares(p.ha)}, drawn in pink beside a football pitch at the same scale. The patch is about ${num(pitches(p.ha))} times bigger.`,
    text: pick([
      `This is the real outline of one patch of cleared land ${placeName(p)}, traced from satellite data. The small rectangle is a football pitch at the same scale.\n\n${hectares(p.ha)}, ${standing}: no licence to mine on the register, and open water in it.`,
      `One patch, ${hectares(p.ha)}, ${placeName(p)}. About ${num(pitches(p.ha))} football pitches of land, in one piece, with no licence to mine on the register.`,
    ]),
    reply: `See it before and after: ${SITE}/places/${p.id}/`,
    render: () => shapePost({ title: `One patch ${near(p)}`, big: `${num(Math.round(p.ha))} ha`, line: `cleared in one piece, about ${num(pitches(p.ha))} football pitches`, sub: `Its real outline, traced from NASA land-change data. ${standing.charAt(0).toUpperCase() + standing.slice(1)}.`, rings: outlines.get(p.id)! }),
  });
}

// Twelve shapes: the twelve largest at one shared scale, like a page of a field guide
const plate = shaped.slice(0, 12);
if (plate.length === 12) {
  placePosts.push({
    slug: 'plate', kind: 'Twelve shapes', title: 'Twelve shapes of galamsey',
    alt: `Twelve black outlines of cleared patches, all at the same scale: ${plate.map((p) => `${hectares(p.ha)} ${near(p)}`).join(', ')}.`,
    text: `The twelve largest patches of cleared land we track with no licence to mine and ${SIGNS}, traced from satellite data and drawn at the same scale.\n\n${plate.slice(0, 6).map((p) => `${hectares(p.ha)} ${near(p)}`).join('\n')}\n...and six more.`,
    reply: `Every patch on the map: ${SITE}/map`,
    render: () => platePost({ title: 'Twelve shapes of galamsey', line: 'The largest patches with no licence to mine and signs of mining, traced from satellite data, all at one scale.', items: plate.map((p) => ({ rings: outlines.get(p.id)!, label: `${hectares(p.ha)}, ${nearLabel(p) ?? tidyDistrict(p.district ?? '')}` })) }),
  });
}

// Check it yourself: a patch by its coordinates, so anyone can look it up in Google Maps
const findable = photo.filter((p) => p.near).slice(0, 30);
if (findable.length) {
  const p = pick(findable, 4);
  placePosts.push({
    slug: 'find', kind: 'Check it yourself', title: `Check it yourself: ${near(p)}`,
    alt: `The coordinates ${p.lat.toFixed(4)}, ${p.lon.toFixed(4)} in large pink type, a small map of southern Ghana with a pin, and a satellite picture of the cleared land ${near(p)}.`,
    text: pick([
      `${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}\n\nPaste that into Google Maps. It is ${hectares(p.ha)} of cleared land ${placeName(p)}, with open water in it and no licence to mine on the register.\n\nOur satellite picture is from ${longDate(p.chips.after.date)}. Google's may be older.`,
      `Don't take our word for it. Search ${p.lat.toFixed(4)}, ${p.lon.toFixed(4)} in Google Maps or Google Earth: ${hectares(p.ha)} cleared ${placeName(p)}, no licence to mine.`,
    ], 1),
    reply: `The place, with links to Google Maps and Earth: ${SITE}/places/${p.id}/`,
    render: () => findPost({ lat: p.lat, lon: p.lon, line: `${hectares(p.ha)} of cleared land ${placeName(p)}. Paste the numbers into Google Maps.`, sub: 'Open water in the patch, as in mining pits, and no licence to mine on the register. Google\'s pictures may be older than ours.', frame: waterMap.frame, land: waterMap.land as number[][][][], after: p.chips.after }),
  });
}

// Licensed to explore, not to mine: the register on the left, the satellite on the right
const explore = photo.filter((p) => p.licence === 'prospecting only').slice(0, 20);
if (explore.length) {
  const p = pick(explore, 5);
  placePosts.push({
    slug: 'explore', kind: 'Licensed to explore, not to mine', title: `Licensed to explore, not to mine: ${near(p)}`,
    alt: `Left, the register: licence on this land, prospecting only. It allows searching for minerals, not mining. Right, satellite pictures ${near(p)}, before and after.`,
    text: pick([
      `A prospecting licence lets its holder search for minerals. It does not allow mining.\n\n${hectares(p.ha)} of land was cleared ${placeName(p)}, on land where the Minerals Commission's register shows only a prospecting licence.`,
      `The register says: licence to explore. The satellite says: ${hectares(p.ha)} of land cleared ${placeName(p)}.`,
    ], 2),
    reply: `What each licence allows: ${SITE}/method#licences`,
    render: () => explorePost({ place: placeName(p), ha: hectares(p.ha), after: p.chips.after, before: p.chips.before }),
  });
}

// Ten towns, ranked by land cleared with no licence to mine within 1 km. A town is named only if some of that
// land shows signs of mining
const tenTowns = townTotals.filter((r) => r.mine.some(likelyLand)).slice(0, 10);
if (tenTowns.length === 10) {
  placePosts.push({
    slug: 'towns', kind: 'Ten towns', title: 'Ten towns, ranked by land cleared with no licence to mine',
    alt: `A ranked table of ten towns by land cleared within 1 km with no licence to mine: ${tenTowns.map((r, i) => `${i + 1}, ${r.town.name}, ${num(r.town.ha)} hectares`).join('. ')}.`,
    text: `The ten towns and villages with the most land cleared within 1 km of them, on land with no licence to mine, in the last 12 months:\n\n${tenTowns.map((r, i) => `${i + 1}. ${r.town.name}: ${num(r.town.ha)} ha`).join('\n')}`,
    reply: `Find any town: ${SITE}/#towns`,
    render: () => townsPost({ title: 'Ten towns, ranked', line: 'Land cleared within 1 km of each, with no licence to mine, in 12 months', rows: tenTowns.map((r) => ({ name: r.town.name, district: r.town.district ? tidyDistrict(r.town.district) : '', ha: `${num(r.town.ha)} ha` })), sub: `Up to ${dataDate}. Town points from OpenStreetMap, licences from the Minerals Commission's register.` }),
  });
}

// The six newest pictured patches as a contact sheet
if (newest.length === 6) {
  placePosts.push({
    slug: 'sheet', kind: 'Newest patches', title: 'The six newest patches',
    alt: `Six satellite pictures of newly cleared land with signs of mining and no licence to mine: ${newest.map((p) => `${hectares(p.ha)} ${near(p)}`).join(', ')}.`,
    text: `The six newest patches of cleared land the satellites have pictured with ${SIGNS} and no licence to mine, each 2 hectares or more:\n\n${newest.map((p) => `${hectares(p.ha)} ${near(p)}`).join('\n')}`,
    reply: `All patches, newest first: ${SITE}/map?sort=new`,
    render: () => sheetPost({ title: 'The six newest patches', line: `Signs of mining and no licence to mine, 2 hectares or more, first seen between ${shortDate(newest[5].first_seen)} and ${shortDate(newest[0].first_seen)}.`, places: newest.map((p) => ({ label: `${hectares(p.ha)}, ${nearLabel(p) ?? 'unnamed place'}`, after: p.chips.after })) }),
  });
}
