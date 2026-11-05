// This week's ready-to-post images and words, rebuilt by every weekly run and listed on the hidden /share page.
// Each post is made to be quoted: one picture that stands alone, one true fact, no question to the reader.
// The link goes in the first reply. Wording follows the site: no em dashes or semicolons, no verdicts on a place.
import { active, coverage, hasPair, placeById, summary, towns, water, type Chip, type Place } from './data';
import { LICENCE_SENTENCE, LICENCE_SHORT, count, hectares, longDate, num, pct, placeName, shortDate, tidyDistrict } from './format';
import { catchments, inside } from './plants';
import fs from 'node:fs';
import path from 'node:path';
import { barsPost, districtPost, explainerPost, explorePost, findPost, licencePost, mapPost, newsPost, platePost, ratePost, shapePost, sheetPost, statPost, townPost, townsPost, waterPost } from './og';
import waterMap from '../data/water-map.json';

const SITE = (import.meta.env.SITE ?? 'https://galamseytracker.org').replace(/\/$/, '');
export const PITCH_HA = 0.714; // a 105 x 68 m football pitch, as on the site (docs/sources.json football-pitch)
const pitches = (ha: number) => Math.round(ha / PITCH_HA);
const RIVER_BLUE = '#1D5C8C', SIGNAL_RED = '#B8155A', SIGNAL_PINK = '#FF6FA6', INK_BLACK = '#000'; // the post palette (og.ts)

export interface Post {
  slug: string;
  kind: string;
  title: string;
  alt: string;
  text: string;
  reply: string;
  render: () => Promise<Buffer>;
}

const posts: Post[] = [];
const dataDate = summary ? longDate(summary.data_date) : '';
// A number that moves on by one each week of data, so the automatic posts rotate subjects and wording without
// anyone choosing: same data, same pick; next week, the next pick
const WEEK = summary ? Math.floor(Date.parse(summary.data_date) / (7 * 864e5)) : 0;
const pick = <T>(list: T[], salt = 0): T => list[(WEEK + salt) % list.length];
// Galamsey only: the posts show land the register gives no licence to mine (none at all, or prospecting only)
const galamsey = (p: Place) => p.licence === 'no licence' || p.licence === 'prospecting only';
type Pictured = Place & { chips: { before: Chip; after: Chip } };

// Towns by land cleared with no licence to mine within 1 km, each shown by its largest such pictured patch
// (neighbouring towns often share a patch, so each picture is used once)
function galamseyTowns(n: number) {
  const used = new Set<string>();
  const out: { town: (typeof towns)[number]; place: Pictured }[] = [];
  const ranked = towns.map((t) => {
    const mine = t.ids.map((id) => placeById.get(id)).filter((p): p is Place => !!p && p.active && galamsey(p));
    return { t: { ...t, ha: mine.reduce((s, p) => s + p.ha, 0) }, mine: mine.sort((a, b) => b.ha - a.ha) };
  }).filter((r) => r.t.ha > 0).sort((a, b) => b.t.ha - a.t.ha);
  for (const r of ranked) {
    const place = r.mine.find((p) => hasPair(p) && !used.has(p.id)) as Pictured | undefined;
    if (!place) continue;
    used.add(place.id);
    out.push({ town: r.t, place });
    if (out.length === n) break;
  }
  return out;
}

// 1. Town of the week: one of the eight towns with the most cleared land around it, a different one each week of
// data (the top town stays first for months, so always posting it would repeat the same place)
const ranked = galamseyTowns(8);
const leadRank = ranked.length ? WEEK % ranked.length : 0;
const lead = ranked[leadRank];
// The town of the week's pair, reused by the picture explainer
const townOfWeekPair = () => (lead ? { before: lead.place.chips.before, after: lead.place.chips.after } : null);
if (lead && summary) {
  const { town, place } = lead;
  const district = town.district ? tidyDistrict(town.district) : null;
  posts.push({
    slug: 'town',
    kind: 'Town of the week',
    title: `Town of the week: ${town.name}`,
    alt: `Two satellite pictures of the same land near ${town.name}${district ? `, ${district}` : ''}. Before, ${longDate(place.chips.before.date)}: green cover. After, ${longDate(place.chips.after.date)}: wide patches of bare orange ground.`,
    text: pick([
      `Within 1 km of ${town.name}${district ? `, ${district}` : ''}, satellites saw ${hectares(town.ha)} of land cleared with no licence to mine in the last 12 months. That is about ${num(pitches(town.ha))} football pitches.

The pictures show the largest patch, before and after.`,
      `${leadRank === 0 ? `No town we track has more land cleared with no licence to mine around it than ${town.name}` : `Few towns we track have more land cleared with no licence to mine around them than ${town.name}`}${district ? ` in ${district}` : ''}: ${hectares(town.ha)} within 1 km, in 12 months.

Here is its largest patch, before and after, seen by satellite.`,
      `${town.name}${district ? `, ${district}` : ''}, seen by satellite on ${longDate(place.chips.before.date)} and again on ${longDate(place.chips.after.date)}.

Within 1 km of the town, ${hectares(town.ha)} of land was cleared with no licence to mine in the last 12 months, about ${num(pitches(town.ha))} football pitches.`,
    ]),
    reply: `The pictures up close, and every patch around ${town.name}: ${SITE}/places/${place.id}/`,
    render: () => townPost({
      // Non-breaking spaces keep "1 km" and "12 months" on one line
      headline: `${hectares(town.ha)} cleared within 1 km of ${town.name}`,
      sub: `Land with no licence to mine, in 12 months: about ${num(pitches(town.ha))} football pitches${district ? `, in ${district}` : ''}.`,
      before: place.chips.before, after: place.chips.after,
    }),
  });
}

// 2. The cities' water: hectares cleared on the land that drains to the plants that supply them
// (who each plant supplies: docs/sources.json claim water-plant-towns)
const CITIES = [
  { slug: 'water-accra', city: 'Accra', plants: ['Weija'], name: 'the Weija plant', river: 'The Densu river', plant: 'Weija treatment plant',
    tap: 'Weija supplies central and western Accra',
    lead: 'Central and western Accra get their water from the Weija treatment plant on the Densu.' },
  { slug: 'water-kumasi', city: 'Kumasi', plants: ['Barekese', 'Owabi'], name: 'the Barekese and Owabi plants', river: 'The Offin and Owabi rivers',
    plant: 'Barekese and Owabi plants', tap: 'They supply Greater Kumasi',
    lead: 'Greater Kumasi gets its water from the Barekese and Owabi treatment plants.' },
  { slug: 'water-takoradi', city: 'Takoradi', plants: ['Daboase'], name: 'the Daboase plant', river: 'The Pra river', plant: 'Daboase treatment plant',
    tap: 'Daboase supplies Sekondi-Takoradi, with Inchaban',
    lead: 'Sekondi-Takoradi gets much of its water from the Daboase treatment plant on the Pra.' },
  { slug: 'water-winneba', city: 'Winneba', plants: ['Kwanyako'], name: 'the Kwanyako plant', river: 'The Ayensu river', plant: 'Kwanyako treatment plant',
    tap: 'Kwanyako supplies Winneba, Swedru and Kasoa',
    lead: 'Winneba, Swedru and Kasoa get their water from the Kwanyako treatment plant on the Ayensu.' },
];
const pictured = (p: Place): p is Place & { chips: { before: Chip; after: Chip } } => hasPair(p);
// Land cleared with no licence to mine on the land that drains to a plant (each patch counted by its point)
const upstream = (polys: (typeof catchments)[number]['polys']) => active.filter(galamsey).filter((p) => inside([p.lon, p.lat], polys)).reduce((t, p) => t + p.ha, 0);
CITIES.forEach((c, ci) => {
  const polys = catchments.filter((k) => c.plants.includes(k.name)).flatMap((k) => k.polys);
  const ha = upstream(polys);
  if (ha < 1) return;
  // One of the three largest patches there with the Likely galamsey label, a different one each week, so the
  // picture shows what the post is about and the same city's card does not repeat its picture
  const candidates = active.filter(pictured).filter((p) => p.likely_galamsey && inside([p.lon, p.lat], polys)).slice(0, 3);
  const largest = candidates.length ? pick(candidates, ci) : undefined;
  const haText = num(Math.round(ha));
  posts.push({
    slug: c.slug,
    kind: 'City water',
    title: `From this to your tap in ${c.city}`,
    alt: `${haText} hectares of land cleared with no licence to mine in 12 months, on the land that drains to ${c.name}.${largest ? ` A satellite picture of one cleared patch upstream, ${placeName(largest)}, with a line following the water from it` : ' A line follows the water'} down ${c.river.replace('The ', 'the ')} to ${c.plant} and to taps in ${c.city}.`,
    text: pick([
      `${c.lead} In the last 12 months, satellites saw ${haText} hectares of land cleared with no licence to mine on the land that drains to it.\n\nWhen it rains, mud from cleared land and mining pits washes into the river, and the water gets harder and dearer to treat.`,
      `${haText} hectares of land cleared with no licence to mine in 12 months, all on land that drains to ${c.name}. ${c.tap}.\n\nWhen it rains, mud from that land washes into the river the plant draws from.`,
      `Water for taps in ${c.city} is treated at ${c.name}. On the land that drains to it, satellites saw ${haText} hectares of land cleared with no licence to mine in the last 12 months.\n\nMore mud in the river makes the water harder and dearer to treat.`,
    ], ci),
    reply: `Every water plant downstream of the clearing, with the map: ${SITE}/#mud`,
    render: () => waterPost({
      title: `From this to your tap in ${c.city}`, big: haText,
      line: `cleared with no licence to mine in 12 months, on the land that drains to ${c.name}`,
      river: c.river, plant: c.plant, tap: c.tap, picture: largest?.chips.after,
    }),
  });
});

// 3. The average rate, as football pitches a day (an average of our own 12-month total, not a claim that it is rising)
const unlicensedHa = active.filter(galamsey).reduce((t, p) => t + p.ha, 0);
if (summary && unlicensedHa > 0) {
  const perDay = Math.round(unlicensedHa / PITCH_HA / 365);
  posts.push({
    slug: 'rate',
    kind: 'Football pitches a day',
    title: 'Football pitches a day',
    alt: `${perDay} football pitches drawn in rows: on average, the land cleared with no licence to mine every day in Ghana's southern gold belt. ${num(unlicensedHa)} hectares in the 12 months leading up to ${dataDate}.`,
    text: `Every day, on average, about ${perDay} football pitches of land are cleared with no licence to mine in the parts of Ghana's southern gold belt we track.

That is ${num(unlicensedHa)} hectares in the 12 months leading up to ${dataDate}, seen by satellite.`,
    reply: `Where it is, with before and after pictures of every patch: ${SITE}/`,
    render: () => ratePost({
      top: "Every day in Ghana's southern gold belt",
      perDay,
      line: 'football pitches of land cleared',
      sub: `With no licence to mine on the register. On average: ${num(unlicensedHa)} hectares in the 12 months leading up to ${dataDate}, seen by satellite in the ${count(coverage.length)} areas we cover.`,
    }),
  });
}

// 4. One district: its total and its three largest pictured patches. It rotates through the five districts with the
// most clearing, one a week, so the spotlight moves around the belt
const districtHa = [...active.filter(galamsey).reduce((m, p) => (p.district ? m.set(p.district, (m.get(p.district) ?? 0) + p.ha) : m), new Map<string, number>())]
  .map(([district, ha]) => ({ district, ha })).sort((a, b) => b.ha - a.ha);
const districtsReady = districtHa.slice(0, 5)
  .map((d, rank) => ({ ...d, rank, inDistrict: active.filter(pictured).filter(galamsey).filter((p) => p.district === d.district).slice(0, 3) }))
  .filter((d) => d.inDistrict.length === 3);
if (districtsReady.length) {
  const d = pick(districtsReady);
  const name = tidyDistrict(d.district);
  const standing = d.rank === 0 ? 'the district with the most land cleared with no licence to mine' : `one of the ${count(Math.min(5, districtHa.length))} districts with the most land cleared with no licence to mine`;
  posts.push({
    slug: 'district',
    kind: 'District spotlight',
    title: `District spotlight: ${name}`,
    alt: `${num(d.ha)} hectares of land cleared with no licence to mine in 12 months in ${name}. Satellite pictures of its three largest cleared patches: ${d.inDistrict.map((p) => placeName(p)).join(', ')}.`,
    text: `${name}: ${num(d.ha)} hectares of land cleared with no licence to mine in 12 months, about ${num(pitches(d.ha))} football pitches. It is ${standing} in the areas we track.

These are its three largest cleared patches, seen by satellite.`,
    reply: `Every patch in ${name}, on the map: ${SITE}/map?district=${encodeURIComponent(d.district)}`,
    render: () => districtPost({
      title: `${name}, ${standing}`,
      big: `${num(d.ha)} ha`,
      line: `cleared in the 12 months leading up to ${dataDate}`,
      stat: `About ${num(pitches(d.ha))} football pitches`,
      places: d.inDistrict.map((p) => ({ label: `${hectares(p.ha)}, ${p.near ? `near ${p.near}` : 'unnamed place'}`, after: p.chips.after })),
    }),
  });
}

// 5. The licence on the cleared land, as one split bar
if (summary) {
  // Galamsey only: the two no-licence-to-mine labels are shown, all licensed land is one grey remainder, unnamed
  const part = (label: string, ha: number, share: number, alarm: boolean) => ({ label, ha: `${num(ha)} ha`, share, tiny: ha > 0 && share < 0.005, alarm });
  const nl = summary.by_licence['no licence'] ?? { ha: 0, share: 0 }, pr = summary.by_licence['prospecting only'] ?? { ha: 0, share: 0 };
  const rest = { ha: summary.total_ha - nl.ha - pr.ha, share: Math.max(0, 1 - nl.share - pr.share) };
  const parts = [part(LICENCE_SHORT['no licence'], nl.ha, nl.share, true), part(LICENCE_SHORT['prospecting only'], pr.ha, pr.share, true), part('Land with a licence (we leave it out)', rest.ha, rest.share, false)];
  const share = pct(summary.no_licence_to_mine.share);
  posts.push({
    slug: 'licence',
    kind: 'Licence split',
    title: 'What licence is on the cleared land',
    alt: `A bar split by the licence on the cleared land. ${share} of it has no licence to mine: no licence at all, or only a licence to explore. ${parts.map((p) => `${p.label}: ${p.ha}`).join('. ')}.`,
    text: `${share} of the land cleared in Ghana's southern gold belt in the last 12 months has no licence to mine on it, going by the Minerals Commission's own register.

That is ${num(summary.no_licence_to_mine.ha)} hectares, seen by satellite.`,
    reply: `How we match each patch to the register: ${SITE}/method#licences`,
    render: () => licencePost({
      big: share,
      line: 'of the cleared land has no licence to mine',
      parts,
      sub: `No licence to mine means no licence at all, or only a licence to explore. From the Minerals Commission's public register, for the ${num(summary.total_ha)} hectares cleared in the 12 months leading up to ${dataDate}.`,
    }),
  });
}

// 6. One place, before and after: the template for news days (the skill picks the place from the news).
// Here the next town after the town of the week, so the library always shows a sample and the two never match.
const second = ranked.length > 1 ? ranked[(leadRank + 1) % ranked.length] : undefined;

// One place, before and after, near a named town. Also used by the studio's news section for places in the news.
export function placePost(name: string, districtName: string | null, place: Place & { chips: { before: Chip; after: Chip } }, slug = 'place', kind = 'One place (news days)'): Post {
  const district = districtName ? tidyDistrict(districtName) : null;
  return {
    slug,
    kind,
    title: `One place: ${name}`,
    alt: `Two satellite pictures of the same land near ${name}. Before, ${longDate(place.chips.before.date)}: green cover. After, ${longDate(place.chips.after.date)}: bare ground.`,
    text: `Near ${name}${district ? `, ${district}` : ''}: ${hectares(place.ha)} of land cleared, first seen by satellite on ${longDate(place.first_seen)}.

${LICENCE_SENTENCE[place.licence]}`,
    reply: `Before and after up close: ${SITE}/places/${place.id}/`,
    render: () => townPost({
      headline: `${hectares(place.ha)} of land cleared near ${name}`,
      sub: `First seen by satellite on ${longDate(place.first_seen)}${district ? `, in ${district}` : ''}. ${LICENCE_SENTENCE[place.licence]}`,
      before: place.chips.before, after: place.chips.after,
    }),
  };
}
if (second && summary) posts.push(placePost(second.town.name, second.town.district, second.place));

// A place in the news: the headline as the story told it, then what the satellite saw there (studio news days)
// `subject` is the town or district the story names, `name` the town the picture is near (the same for a town)
export function newsPlacePost(story: { title: string; source: string; date: string; link: string }, subject: string, name: string, districtName: string | null, place: Pictured, slug: string): Post {
  const district = districtName ? tidyDistrict(districtName) : null;
  // When the story names the district, it is said once already
  const where = subject === name && district ? `${name}, ${district}` : name;
  return {
    slug,
    kind: 'In the news',
    title: `In the news: ${name}`,
    alt: `The headline "${story.title}" (${story.source}), then satellite pictures near ${name}: before, ${longDate(place.chips.before.date)}, and after, ${longDate(place.chips.after.date)}, bare ground.`,
    // Reads right as a quote of the newsroom's post and on its own, because it names the story's subject itself
    text: `${story.source} reports on ${subject}. ${subject === name ? 'This is what satellites saw there' : `In ${subject}, satellites saw this`}: ${hectares(place.ha)} of land cleared near ${where}, first seen on ${longDate(place.first_seen)}.

${LICENCE_SENTENCE[place.licence]}`,
    reply: `The story: ${story.link}
Before and after up close: ${SITE}/places/${place.id}/`,
    render: () => newsPost({ headline: story.title, outlet: story.source, date: shortDate(story.date.slice(0, 10)), place: `near ${name}`, before: place.chips.before, after: place.chips.after, line: `${hectares(place.ha)} cleared, first seen ${shortDate(place.first_seen)}. ${LICENCE_SENTENCE[place.licence]}` }),
  };
}

// 7. New clearing: the largest pictured patch satellites first saw in the last two (or four) months. New land every week.
if (summary) {
  // New places often wait a while for a cloud-free picture, so look back four months when two find nothing
  const within = (days: number) => active.filter(pictured).filter(galamsey).filter((p) => p.ha >= 3 && Date.parse(p.first_seen) >= Date.parse(summary.data_date) - days * 864e5)[0];
  const months = within(60) ? 'two' : 'four';
  const fresh = within(60) ?? within(120);
  if (fresh) {
    const where = placeName(fresh);
    posts.push({
      slug: 'new',
      kind: 'New clearing',
      title: `New clearing ${where}`,
      alt: `Two satellite pictures of the same land ${where}. Before, ${longDate(fresh.chips.before.date)}. After, ${longDate(fresh.chips.after.date)}: newly bare ground.`,
      text: `${hectares(fresh.ha)} of land cleared ${where}, first seen by satellite on ${longDate(fresh.first_seen)}.

It is the largest patch satellites first saw in the last ${months} months. ${LICENCE_SENTENCE[fresh.licence]}`,
      reply: `Before and after up close: ${SITE}/places/${fresh.id}/`,
      render: () => townPost({
        headline: `${hectares(fresh.ha)} of land newly cleared ${where}`,
        sub: `First seen by satellite on ${longDate(fresh.first_seen)}, the largest new patch in the last ${months} months. ${LICENCE_SENTENCE[fresh.licence]}`,
        before: fresh.chips.before, after: fresh.chips.after,
      }),
    });
  }
}


// ---- More kinds (2026-11-05, third pass). Each is one idea with its own layout. Galamsey only: every place,
// picture and total here is land the register shows with no licence to mine (none, or prospecting only) ----
const photo = active.filter(pictured).filter(galamsey);
const unlicensed = active.filter(galamsey);
const near = (p: Place) => (p.near ? `near ${p.near}` : placeName(p));

// Real outlines, from the weekly run's working files (present in the weekly and daily studio jobs)
const outlines = (() => {
  const file = [path.join(process.cwd(), '../../pipeline/out/places/latest.geojson')].find((f) => fs.existsSync(f));
  const map = new Map<string, number[][][]>();
  if (!file) return map;
  for (const f of JSON.parse(fs.readFileSync(file, 'utf8')).features) {
    const g = f.geometry;
    if (g?.type === 'Polygon') map.set(f.properties.id, g.coordinates);
    else if (g?.type === 'MultiPolygon') map.set(f.properties.id, g.coordinates.flat());
  }
  return map;
})();

// The shape of it: one of the ten largest unlicensed patches, its outline beside a football pitch at the same scale
const shaped = unlicensed.filter((p) => outlines.has(p.id)).slice(0, 10);
if (shaped.length && summary) {
  const rank = WEEK % shaped.length;
  const p = shaped[rank];
  const standing = rank === 0 ? 'the largest patch we track with no licence to mine' : `one of the ${count(shaped.length)} largest patches we track with no licence to mine`;
  posts.push({
    slug: 'shape', kind: 'The shape of it', title: `The shape of it: ${hectares(p.ha)} ${near(p)}`,
    alt: `The outline of one cleared patch ${near(p)}, ${hectares(p.ha)}, drawn in pink beside a football pitch at the same scale. The patch is about ${num(pitches(p.ha))} times bigger.`,
    text: pick([
      `This is the real outline of one patch of cleared land ${placeName(p)}, traced from satellite data. The small rectangle is a football pitch at the same scale.\n\n${hectares(p.ha)}, ${standing}. No licence to mine on the register.`,
      `One patch, ${hectares(p.ha)}, ${placeName(p)}. About ${num(pitches(p.ha))} football pitches of land, in one piece, with no licence to mine on the register.`,
    ]),
    reply: `See it before and after: ${SITE}/places/${p.id}/`,
    render: () => shapePost({ title: `One patch ${near(p)}`, big: `${num(Math.round(p.ha))} ha`, line: `cleared in one piece, about ${num(pitches(p.ha))} football pitches`, sub: `Its real outline, traced from NASA land-change data. ${standing.charAt(0).toUpperCase() + standing.slice(1)}.`, rings: outlines.get(p.id)! }),
  });
}

// A specimen plate: the twelve largest unlicensed patches, one shared scale
const plate = unlicensed.filter((p) => outlines.has(p.id)).slice(0, 12);
if (plate.length === 12) {
  posts.push({
    slug: 'plate', kind: 'Twelve shapes', title: 'Twelve shapes of galamsey',
    alt: `Twelve black outlines of cleared patches, all at the same scale: ${plate.map((p) => `${hectares(p.ha)} ${near(p)}`).join(', ')}.`,
    text: `The twelve largest patches of cleared land we track with no licence to mine, traced from satellite data and drawn at the same scale.\n\n${plate.slice(0, 6).map((p) => `${hectares(p.ha)} ${near(p)}`).join('\n')}\n...and six more.`,
    reply: `Every patch on the map: ${SITE}/map?sort=largest`,
    render: () => platePost({ title: 'Twelve shapes of galamsey', line: 'The largest patches with no licence to mine, traced from satellite data, all at one scale.', items: plate.map((p) => ({ rings: outlines.get(p.id)!, label: `${hectares(p.ha)}, ${p.near ?? tidyDistrict(p.district ?? '')}` })) }),
  });
}

// Find it yourself: a Likely galamsey patch by its coordinates, so anyone can check it in Google Maps
const findable = photo.filter((p) => p.likely_galamsey && p.near).slice(0, 30);
if (findable.length) {
  const p = pick(findable, 4);
  posts.push({
    slug: 'find', kind: 'Check it yourself', title: `Check it yourself: ${near(p)}`,
    alt: `The coordinates ${p.lat.toFixed(4)}, ${p.lon.toFixed(4)} in large pink type, a small map of southern Ghana with a pin, and a satellite picture of bare ground ${near(p)}.`,
    text: pick([
      `${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}\n\nPaste that into Google Maps. It is ${hectares(p.ha)} of cleared land ${placeName(p)}, with open water in it and no licence to mine on the register.\n\nOur satellite picture is from ${longDate(p.chips.after.date)}. Google's may be older.`,
      `Don't take our word for it. Search ${p.lat.toFixed(4)}, ${p.lon.toFixed(4)} in Google Maps or Google Earth: ${hectares(p.ha)} cleared ${placeName(p)}, no licence to mine.`,
    ], 1),
    reply: `The place, with links to Google Maps and Earth: ${SITE}/places/${p.id}/`,
    render: () => findPost({ lat: p.lat, lon: p.lon, line: `${hectares(p.ha)} of cleared land ${placeName(p)}. Paste the numbers into Google Maps.`, sub: 'Open water in the patch and no licence to mine on the register: our Likely galamsey label. Google\'s pictures may be older than ours.', frame: waterMap.frame, land: waterMap.land as number[][][][], after: p.chips.after }),
  });
}

// Licensed to explore, not to mine: the register on the left, the satellite on the right
const explore = photo.filter((p) => p.licence === 'prospecting only').slice(0, 20);
if (explore.length) {
  const p = pick(explore, 5);
  posts.push({
    slug: 'explore', kind: 'Licensed to explore, not to mine', title: `Licensed to explore, not to mine: ${near(p)}`,
    alt: `Left, the register: licence on this land, prospecting only. It allows searching for minerals, not mining. Right, satellite pictures ${near(p)}: green before, bare ground after.`,
    text: pick([
      `A prospecting licence lets its holder search for minerals. It does not allow mining.\n\n${hectares(p.ha)} of land was cleared ${placeName(p)}, on land where the Minerals Commission's register shows only a prospecting licence.`,
      `The register says: licence to explore. The satellite says: ${hectares(p.ha)} of land cleared ${placeName(p)}.`,
    ], 2),
    reply: `What each licence allows: ${SITE}/method#licences`,
    render: () => explorePost({ place: placeName(p), ha: hectares(p.ha), after: p.chips.after, before: p.chips.before }),
  });
}

// Ten towns: ranked by cleared land with no licence to mine within 1 km
const rankedTowns = towns.map((t) => ({ t, ha: t.ids.reduce((sum, id) => { const p = placeById.get(id); return p && p.active && galamsey(p) ? sum + p.ha : sum; }, 0) }))
  .filter((r) => r.ha > 0).sort((a, b) => b.ha - a.ha).slice(0, 10);
if (rankedTowns.length === 10) {
  posts.push({
    slug: 'towns', kind: 'Ten towns', title: 'Ten towns, ranked by land cleared with no licence to mine',
    alt: `A ranked table of ten towns by land cleared within 1 km with no licence to mine: ${rankedTowns.map((r, i) => `${i + 1}, ${r.t.name}, ${num(r.ha)} hectares`).join('. ')}.`,
    text: `The ten towns and villages with the most land cleared within 1 km of them, on land with no licence to mine, in the last 12 months:\n\n${rankedTowns.map((r, i) => `${i + 1}. ${r.t.name}: ${num(r.ha)} ha`).join('\n')}`,
    reply: `Find any town: ${SITE}/#towns`,
    render: () => townsPost({ title: 'Ten towns, ranked', line: 'Land cleared within 1 km of each, with no licence to mine, in 12 months', rows: rankedTowns.map((r) => ({ name: r.t.name, district: r.t.district ? tidyDistrict(r.t.district) : '', ha: `${num(r.ha)} ha` })), sub: `Up to ${dataDate}. Town points from OpenStreetMap, licences from the Minerals Commission's register.` }),
  });
}

// The newest unlicensed patches as a contact sheet
const newest = photo.filter((p) => p.ha >= 2).sort((a, b) => b.first_seen.localeCompare(a.first_seen)).slice(0, 6);
if (newest.length === 6) {
  posts.push({
    slug: 'sheet', kind: 'Newest patches', title: 'The six newest patches',
    alt: `Six satellite pictures of newly cleared land with no licence to mine: ${newest.map((p) => `${hectares(p.ha)} ${near(p)}`).join(', ')}.`,
    text: `The six newest patches of cleared land the satellites have pictured with no licence to mine on the register, each 2 hectares or more:\n\n${newest.map((p) => `${hectares(p.ha)} ${near(p)}`).join('\n')}`,
    reply: `All patches, newest first: ${SITE}/map?sort=newest`,
    render: () => sheetPost({ title: 'The six newest patches', line: `No licence to mine, 2 hectares or more, first seen between ${shortDate(newest[5].first_seen)} and ${shortDate(newest[0].first_seen)}.`, places: newest.map((p) => ({ label: `${hectares(p.ha)}, ${p.near ?? 'unnamed place'}`, after: p.chips.after })) }),
  });
}

// Districts compared, by land cleared with no licence to mine
const byDistrict = [...unlicensed.reduce((m, p) => (p.district ? m.set(p.district, (m.get(p.district) ?? 0) + p.ha) : m), new Map<string, number>())]
  .sort((a, b) => b[1] - a[1]).slice(0, 8);
if (byDistrict.length >= 5) {
  posts.push({
    slug: 'districts', kind: 'Districts compared', title: 'The districts with the most land cleared with no licence to mine',
    alt: `Bars for the ${count(byDistrict.length)} districts with the most land cleared with no licence to mine: ${byDistrict.map(([d, ha]) => `${tidyDistrict(d)} ${num(ha)} hectares`).join(', ')}.`,
    text: `Land cleared with no licence to mine, in the 12 months leading up to ${dataDate}, by district:\n\n${byDistrict.map(([d, ha]) => `${tidyDistrict(d)}: ${num(ha)} ha`).join('\n')}`,
    reply: `Every district, with its patches: ${SITE}/map`,
    render: () => barsPost({ title: 'Where the most land was cleared', line: `With no licence to mine, by district, in the 12 months leading up to ${dataDate}`, rows: byDistrict.map(([d, ha]) => ({ label: tidyDistrict(d), value: ha, text: `${num(ha)} ha` })), sub: `From the ${count(coverage.length)} areas of the southern gold belt we cover.` }),
  });
}

// Patch sizes, unlicensed patches only
if (unlicensed.length) {
  const bins = [[1, 2, '1 to 2 hectares'], [2, 5, '2 to 5 hectares'], [5, 10, '5 to 10 hectares'], [10, Infinity, '10 hectares or more']] as const;
  const rows = bins.map(([lo, hi, label]) => {
    const inBin = unlicensed.filter((p) => p.ha >= lo && p.ha < hi);
    const ha = inBin.reduce((t, p) => t + p.ha, 0);
    return { label, value: inBin.length, text: `${num(inBin.length)} patches, ${num(ha)} ha`, ha };
  });
  const all = rows.reduce((t, r) => t + r.ha, 0);
  const tenths = Math.round(((rows[0].value + rows[1].value) / unlicensed.length) * 10);
  const smallHa = pct((rows[0].ha + rows[1].ha) / all);
  posts.push({
    slug: 'sizes', kind: 'Patch sizes', title: 'Small patches, a lot of land',
    alt: `Bars showing how many patches with no licence to mine there are of each size: ${rows.map((r) => `${r.label}, ${r.text}`).join('. ')}.`,
    text: `${tenths} in 10 patches of cleared land with no licence to mine are under 5 hectares. Together they hold ${smallHa} of that land.\n\nNot a few huge pits. Thousands of small ones, ${num(unlicensed.length)} patches in all.`,
    reply: `Every patch, smallest to largest: ${SITE}/map`,
    render: () => barsPost({ title: 'How big the patches are', big: `${tenths} in 10`, line: `patches with no licence to mine are under 5 hectares. They hold ${smallHa} of that land.`, rows, sub: `${num(unlicensed.length)} patches of 1 hectare or more with no licence to mine, in the 12 months leading up to ${dataDate}.` }),
  });
}

// Where it is: every unlicensed patch as a dot
if (unlicensed.length) {
  posts.push({
    slug: 'map', kind: 'Where it is', title: 'Every patch with no licence to mine, on one map',
    alt: `A map of southern Ghana with ${num(unlicensed.length)} pink dots, one for each patch of land cleared with no licence to mine, bigger dots for bigger patches.`,
    text: `Every dot is a patch of land cleared in the last 12 months where the register shows no licence to mine: ${num(unlicensed.length)} of them, across the ${count(coverage.length)} areas of the southern gold belt we cover.`,
    reply: `The map, where you can tap any dot: ${SITE}/map`,
    render: () => mapPost({ title: 'No licence to mine, one dot each', big: num(unlicensed.length), line: 'patches of land cleared in 12 months', sub: `Bigger dots are bigger patches. The ${count(coverage.length)} areas of the southern gold belt we cover, in the 12 months leading up to ${dataDate}.`, frame: waterMap.frame, land: waterMap.land as number[][][][], dots: unlicensed.map((p) => ({ lon: p.lon, lat: p.lat, ha: p.ha })) }),
  });
}

// All five water plants on one card, unlicensed land only like every post
const plantRows = water.map((w) => ({ ...w, ha: upstream(catchments.filter((k) => k.name === w.plant).flatMap((k) => k.polys)) })).sort((a, b) => b.ha - a.ha);
if (plantRows.length >= 3) {
  posts.push({
    slug: 'plants', kind: 'All five water plants', title: 'Cleared land upstream of each water plant',
    alt: `Bars for the land cleared with no licence to mine upstream of each water treatment plant: ${plantRows.map((w) => `${w.plant} on the ${w.river}, ${num(w.ha)} hectares`).join(', ')}.`,
    text: `Land cleared with no licence to mine in 12 months, on the land that drains to each water treatment plant:\n\n${plantRows.map((w) => `${w.plant} (${w.river}): ${num(w.ha)} ha`).join('\n')}\n\nWhen it rains, mud from cleared land washes into the rivers the plants draw from.`,
    reply: `The map of what drains where: ${SITE}/#mud`,
    render: () => barsPost({ title: 'Upstream of the water plants', line: 'Land cleared with no licence to mine in 12 months, on the land that drains to each plant', rows: plantRows.map((w) => ({ label: `${w.plant}, on the ${w.river}`, value: w.ha, text: `${num(w.ha)} ha` })), sub: 'When it rains, mud from cleared land washes into the river each plant draws from.', color: RIVER_BLUE }),
  });
}

// The water test: how many unlicensed patches show open water
const likely = active.filter((p) => p.likely_galamsey);
const pits = photo.filter((p) => p.likely_galamsey);
if (likely.length) {
  const ex = pick(pits.slice(0, 10), 3);
  posts.push({
    slug: 'water-test', kind: 'The water test', title: 'The water test',
    alt: `${num(likely.length)} cleared patches labelled Likely galamsey.${ex ? ` A satellite picture of one, ${near(ex)}, with dark ponds on bare ground.` : ''}`,
    text: `${num(likely.length)} cleared patches with no licence to mine also show open water in or right beside them. Mining pits fill with water, so we label these Likely galamsey.\n\nIt is our guess from the satellite, not a finding. A patch without the label can still be galamsey.`,
    reply: `How the test works: ${SITE}/method#likely`,
    render: () => statPost({ title: 'The water test', big: num(likely.length), line: 'patches labelled Likely galamsey', body: 'No licence to mine on the register, and open water in or right beside the cleared land. Mining pits fill with water. It is our guess, not a finding.', picture: ex?.chips.after, caption: ex ? `${hectares(ex.ha)} ${near(ex)}, ${shortDate(ex.chips.after.date)}` : undefined }),
  });
}

// Month in review: unlicensed land first seen in the last month the data covers to its end
if (summary) {
  const dd = new Date(summary.data_date);
  const lastDay = new Date(dd.getTime() + 864e5).getUTCDate() === 1;
  const monthStart = new Date(Date.UTC(dd.getUTCFullYear(), dd.getUTCMonth() - (lastDay ? 0 : 1), 1));
  const monthEnd = new Date(Date.UTC(monthStart.getUTCFullYear(), monthStart.getUTCMonth() + 1, 1));
  const inMonth = unlicensed.filter((p) => { const t = Date.parse(p.first_seen); return t >= monthStart.getTime() && t < monthEnd.getTime(); });
  // New patches often wait weeks for a cloud-free picture, so fall back to the newest pictured one
  const top = inMonth.filter(pictured)[0];
  const shown = top ?? newest[0];
  const month = monthStart.toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' });
  if (inMonth.length) {
    const ha = inMonth.reduce((t, p) => t + p.ha, 0);
    posts.push({
      slug: 'month', kind: 'Month in review', title: `${month} in review`,
      alt: `${num(ha)} hectares of land with no licence to mine first seen cleared in ${month}, in ${num(inMonth.length)} patches.${shown ? ` A satellite picture of one, ${near(shown)}.` : ''}`,
      text: `In ${month}, satellites first saw ${num(ha)} hectares of newly cleared land with no licence to mine on the register, in ${num(inMonth.length)} patches.${top ? `\n\nThe largest: ${hectares(top.ha)} ${placeName(top)}.` : ''}\n\nNASA confirms clearing over several weeks, so this number can still go up.`,
      reply: `All patches, newest first: ${SITE}/map?sort=newest`,
      render: () => statPost({ title: `${month} in review`, big: `${num(ha)} ha`, line: `newly cleared with no licence to mine, in ${num(inMonth.length)} patches`, body: 'First seen by satellite that month. NASA confirms clearing over several weeks, so the number can still go up.', picture: shown?.chips.after, caption: shown ? `${top ? 'The largest' : 'One of the newest'}: ${hectares(shown.ha)} ${near(shown)}` : undefined }),
    });
  }
}

// 22 to 24. Explainers: the same words each time, posted rarely, so readers learn how to read the evidence
const pairFor = townOfWeekPair();
posts.push({
  slug: 'explain-pictures', kind: 'How to read the pictures', title: 'How to read the pictures',
  alt: 'A before and after satellite pair with four notes on how to read it: green, orange, dark ponds and the ring.',
  text: 'How to read our satellite pictures:\n\nGreen is forest or farmland. Orange and cream is bare ground, where the soil is dug up. Dark ponds on bare ground are water, often in mining pits. The white ring marks the patch we are talking about.\n\nEach picture is about 1.6 km across.',
  reply: `How the pictures are chosen: ${SITE}/method`,
  render: () => explainerPost({ title: 'How to read the pictures', pair: pairFor ?? undefined, points: [
    { mark: '', markColor: '#2E6B34', head: 'Green', body: 'Forest, farms and bush.' },
    { mark: '', markColor: '#C46A2B', head: 'Orange and cream', body: 'Bare ground, where the soil has been dug up.' },
    { mark: '', markColor: '#1D3A4F', head: 'Dark ponds', body: 'Water, often in mining pits.' },
    { mark: '', head: 'The white ring', body: 'The patch the post is about. Each picture is about 1.6 km across.' },
  ] }),
});
posts.push({
  slug: 'explain-licence', kind: 'How we check the licence', title: 'How we check the licence',
  alt: 'How each patch is checked against the licence register: no licence, or only a licence to explore, means no licence to mine, which is what galamsey is.',
  text: `For every patch of cleared land, we check the Minerals Commission's public licence register.

No licence at all, or only a licence to explore: there is no licence to mine on that land. Mining without one is what galamsey is.

Those are the only places we post about.`,
  reply: `What each label means: ${SITE}/method#licences`,
  render: () => explainerPost({ title: 'How we check the licence', points: [
    { mark: '', markColor: SIGNAL_RED, head: 'No licence', body: "Nothing on the Minerals Commission's register for this land." },
    { mark: '', markColor: SIGNAL_PINK, head: 'Prospecting only', body: 'A licence to search for minerals. It does not allow mining.' },
    { mark: '', markColor: INK_BLACK, head: 'Galamsey', body: 'Mining without a licence to mine. Both labels above mean there is none.' },
    { mark: '', markColor: '#888', head: 'What we post', body: 'Only land with no licence to mine. We check the register again every week.' },
  ] }),
});
posts.push({
  slug: 'explain-satellites', kind: 'How satellites see it', title: 'How satellites see it',
  alt: 'Three steps: satellites pass every few days, NASA flags land that lost its cover, we add the licence and pictures.',
  text: 'How the tracker works, in three steps:\n\n1. American and European satellites photograph Ghana every few days.\n2. NASA flags land that has lost its plant cover, and we keep patches of 1 hectare or more in the forest zone.\n3. Every Monday we check each patch against the licence register and pick a clear before and after picture.\n\nNo one has to do it by hand. It runs by itself.',
  reply: `The full method, in plain words: ${SITE}/method`,
  render: () => explainerPost({ title: 'How satellites see it', points: [
    { mark: '1', head: 'Satellites pass every few days', body: 'American Landsat and European Sentinel-2 satellites photograph the same land again and again.' },
    { mark: '2', head: 'NASA flags lost plant cover', body: 'Its land-change data marks where cover is gone. We keep patches of 1 hectare or more in the forest zone.' },
    { mark: '3', head: 'Every Monday, a fresh check', body: 'Each patch is matched to the licence register and gets the clearest before and after picture.' },
    { mark: '4', head: 'No one in the loop', body: 'It runs by itself on free tools, and the method is public.' },
  ] }),
});

export const sharePosts = posts;

