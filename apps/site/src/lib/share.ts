// This week's ready-to-post images and words, rebuilt by every weekly run and listed on the hidden /share page.
// Each post is made to be quoted: one picture that stands alone, one true fact, no question to the reader.
// The link goes in the first reply. Wording follows the site: no em dashes or semicolons, no verdicts on a place.
import { active, coverage, doorstep, hasPair, summary, water, type Chip, type Place } from './data';
import { LICENCES, LICENCE_SENTENCE, LICENCE_SHORT, count, hectares, longDate, num, pct, placeName, shortDate, tidyDistrict } from './format';
import { catchments, inside } from './plants';
import { barsPost, districtPost, explainerPost, licencePost, mapPost, ratePost, sheetPost, splitPost, statPost, townPost, waterPost } from './og';
import waterMap from '../data/water-map.json';

const SITE = (import.meta.env.SITE ?? 'https://galamseytracker.org').replace(/\/$/, '');
const PITCH_HA = 0.714; // a 105 x 68 m football pitch, as on the site (docs/sources.json football-pitch)
const pitches = (ha: number) => Math.round(ha / PITCH_HA);
const RIVER_BLUE = '#1D5C8C', SIGNAL_RED = '#B8155A', SIGNAL_PINK = '#FF6FA6'; // the post palette (og.ts)

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

// 1. Town of the week: one of the eight towns with the most cleared land around it, a different one each week of
// data (the top town stays first for months, so always posting it would repeat the same place)
const ranked = doorstep(8);
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
      `Within 1 km of ${town.name}${district ? `, ${district}` : ''}, satellites saw ${hectares(town.ha)} of land cleared in the last 12 months. That is about ${num(pitches(town.ha))} football pitches.\n\nThe pictures show the largest patch, before and after. ${LICENCE_SENTENCE[place.licence]}`,
      `${leadRank === 0 ? `No town we track has more cleared land around it than ${town.name}` : `${town.name} is one of the ${count(ranked.length)} towns we track with the most cleared land around it`}${district ? ` in ${district}` : ''}: ${hectares(town.ha)} within 1 km, in 12 months.\n\nHere is its largest patch, before and after, seen by satellite. ${LICENCE_SENTENCE[place.licence]}`,
      `${town.name}${district ? `, ${district}` : ''}, seen by satellite on ${longDate(place.chips.before.date)} and again on ${longDate(place.chips.after.date)}.\n\nWithin 1 km of the town, ${hectares(town.ha)} of land was cleared in the last 12 months, about ${num(pitches(town.ha))} football pitches. ${LICENCE_SENTENCE[place.licence]}`,
    ]),
    reply: `The pictures up close, and every patch around ${town.name}: ${SITE}/places/${place.id}/`,
    render: () => townPost({
      // Non-breaking spaces keep "1 km" and "12 months" on one line
      headline: `${hectares(town.ha)} of land cleared within 1 km of ${town.name} in 12 months`,
      sub: `About ${num(pitches(town.ha))} football pitches${district ? `, in ${district}` : ''}. ${LICENCE_SENTENCE[place.licence]}`,
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
CITIES.forEach((c, ci) => {
  const ha = water.filter((w) => c.plants.includes(w.plant)).reduce((t, w) => t + w.ha, 0);
  if (ha < 1) return;
  const polys = catchments.filter((k) => c.plants.includes(k.name)).flatMap((k) => k.polys);
  // One of the three largest patches there with the Likely galamsey label, a different one each week, so the
  // picture shows what the post is about and the same city's card does not repeat its picture
  const candidates = active.filter(pictured).filter((p) => p.likely_galamsey && inside([p.lon, p.lat], polys)).slice(0, 3);
  const largest = candidates.length ? pick(candidates, ci) : undefined;
  const haText = num(Math.round(ha));
  posts.push({
    slug: c.slug,
    kind: 'City water',
    title: `From this to your tap in ${c.city}`,
    alt: `${haText} hectares of land cleared in 12 months on the land that drains to ${c.name}.${largest ? ` A satellite picture of one cleared patch upstream, ${placeName(largest)}, with a line following the water from it` : ' A line follows the water'} down ${c.river.replace('The ', 'the ')} to ${c.plant} and to taps in ${c.city}.`,
    text: pick([
      `${c.lead} In the last 12 months, satellites saw ${haText} hectares of land cleared on the land that drains to it.\n\nWhen it rains, mud from cleared land and mining pits washes into the river, and the water gets harder and dearer to treat.`,
      `${haText} hectares of land cleared in 12 months, all on land that drains to ${c.name}. ${c.tap}.\n\nWhen it rains, mud from that land washes into the river the plant draws from.`,
      `Water for taps in ${c.city} is treated at ${c.name}. On the land that drains to it, satellites saw ${haText} hectares of land cleared in the last 12 months.\n\nMore mud in the river makes the water harder and dearer to treat.`,
    ], ci),
    reply: `Every water plant downstream of the clearing, with the map: ${SITE}/#mud`,
    render: () => waterPost({
      title: `From this to your tap in ${c.city}`, big: haText,
      line: `cleared in 12 months on the land that drains to ${c.name}`,
      river: c.river, plant: c.plant, tap: c.tap, picture: largest?.chips.after,
    }),
  });
});

// 3. The average rate, as football pitches a day (an average of our own 12-month total, not a claim that it is rising)
if (summary && summary.total_ha > 0) {
  const perDay = Math.round(summary.total_ha / PITCH_HA / 365);
  posts.push({
    slug: 'rate',
    kind: 'Football pitches a day',
    title: 'Football pitches a day',
    alt: `${perDay} football pitches drawn in rows: on average, the land cleared every day in Ghana's southern gold belt. ${num(summary.total_ha)} hectares in the 12 months leading up to ${dataDate}.`,
    text: `On average, about ${perDay} football pitches of land are cleared every day in the parts of Ghana's southern gold belt we track.

That is ${num(summary.total_ha)} hectares in the 12 months leading up to ${dataDate}, seen by satellite.`,
    reply: `Where it is, with before and after pictures of every patch: ${SITE}/`,
    render: () => ratePost({
      top: "Every day in Ghana's southern gold belt",
      perDay,
      line: 'football pitches of land cleared',
      sub: `On average: ${num(summary.total_ha)} hectares in the 12 months leading up to ${dataDate}, seen by satellite in the ${count(coverage.length)} areas we cover.`,
    }),
  });
}

// 4. One district: its total and its three largest pictured patches. It rotates through the five districts with the
// most clearing, one a week, so the spotlight moves around the belt
const districtsReady = (summary?.top_districts ?? []).slice(0, 5)
  .map((d, rank) => ({ ...d, rank, inDistrict: active.filter(pictured).filter((p) => p.district === d.district).slice(0, 3) }))
  .filter((d) => d.inDistrict.length === 3);
if (districtsReady.length) {
  const d = pick(districtsReady);
  const name = tidyDistrict(d.district);
  const standing = d.rank === 0 ? 'the district with the most cleared land' : `one of the ${count(Math.min(5, districtsReady.length))} districts with the most cleared land`;
  posts.push({
    slug: 'district',
    kind: 'District spotlight',
    title: `District spotlight: ${name}`,
    alt: `${num(d.ha)} hectares of land cleared in 12 months in ${name}. Satellite pictures of its three largest cleared patches: ${d.inDistrict.map((p) => placeName(p)).join(', ')}.`,
    text: `${name} is ${standing} we track: ${num(d.ha)} hectares in 12 months, about ${num(pitches(d.ha))} football pitches.

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
  const parts = LICENCES.filter((l) => summary.by_licence[l]).map((l) => ({
    label: LICENCE_SHORT[l], ha: `${num(summary.by_licence[l].ha)} ha`, share: summary.by_licence[l].share,
    tiny: summary.by_licence[l].ha > 0 && summary.by_licence[l].share < 0.005,
    alarm: l === 'no licence' || l === 'prospecting only',
  }));
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

// 7. New clearing: the largest pictured patch satellites first saw in the last two (or four) months. New land every week.
if (summary) {
  // New places often wait a while for a cloud-free picture, so look back four months when two find nothing
  const within = (days: number) => active.filter(pictured).filter((p) => p.ha >= 3 && Date.parse(p.first_seen) >= Date.parse(summary.data_date) - days * 864e5)[0];
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


// ---- More kinds (2026-11-05). Each is a fixed design that refills from the week's data, with two or three
// wordings, and the place ones move through a ranked list a step each week, so the feed rarely repeats ----
const photo = active.filter(pictured);
const near = (p: Place) => (p.near ? `near ${p.near}` : placeName(p));
const metres = (km: number) => (km < 1 ? `${Math.max(50, Math.round((km * 1000) / 50) * 50)} metres` : `${km.toFixed(1)} km`);

// 8. The biggest patches: one of the ten largest pictured, a different one each week
const biggest = photo.slice(0, 10);
if (biggest.length && summary) {
  const rank = WEEK % biggest.length;
  const p = biggest[rank];
  const standing = rank === 0 ? 'The largest single patch of cleared land we track' : `One of the ${count(biggest.length)} largest single patches of cleared land we track`;
  posts.push({
    slug: 'biggest', kind: 'Biggest patches', title: `Biggest patches: ${hectares(p.ha)} ${near(p)}`,
    alt: `One satellite view of the same land ${near(p)}, split down the middle. Left half, before, ${longDate(p.chips.before.date)}: green cover. Right half, after, ${longDate(p.chips.after.date)}: bare ground.`,
    text: pick([
      `${standing}: ${hectares(p.ha)} ${placeName(p)}, about ${num(pitches(p.ha))} football pitches in one piece.\n\n${LICENCE_SENTENCE[p.licence]}`,
      `${hectares(p.ha)} of land cleared in one patch ${placeName(p)}. ${standing.replace(/^The|^One/, (m) => (m === 'The' ? 'It is the' : 'It is one'))}.\n\n${LICENCE_SENTENCE[p.licence]}`,
    ]),
    reply: `Before and after up close: ${SITE}/places/${p.id}/`,
    render: () => splitPost({ headline: `${hectares(p.ha)} cleared in one patch ${near(p)}`, sub: `${standing}. ${LICENCE_SENTENCE[p.licence]}`, before: p.chips.before, after: p.chips.after }),
  });
}

// 9. Water in the pits: a Likely galamsey patch, from the 20 largest, a step each week
const pits = photo.filter((p) => p.likely_galamsey).slice(0, 20);
if (pits.length) {
  const p = pick(pits, 3);
  posts.push({
    slug: 'pits', kind: 'Water in the pits', title: `Water in the pits ${near(p)}`,
    alt: `Satellite pictures of land ${near(p)}. Before, ${longDate(p.chips.before.date)}: green cover. After, ${longDate(p.chips.after.date)}: bare ground with dark ponds of water.`,
    text: pick([
      `Mining pits fill with water. ${hectares(p.ha)} of land was cleared ${placeName(p)}, and the satellite sees open water in or right beside it. The register shows no licence to mine there.\n\nThat is why we label it Likely galamsey. It is our guess, not a finding.`,
      `Dark ponds on bare ground ${placeName(p)}: ${hectares(p.ha)} cleared, open water seen in or beside it, and no licence to mine on the register.\n\nWe call that Likely galamsey, our educated guess from the satellite.`,
    ], 1),
    reply: `How the Likely galamsey guess works: ${SITE}/method#likely`,
    render: () => townPost({ headline: `Open water in a cleared patch ${near(p)}`, sub: `${hectares(p.ha)} cleared. Mining pits fill with water, and the register shows no licence to mine here, so we label it Likely galamsey.`, before: p.chips.before, after: p.chips.after }),
  });
}

// 10. Licensed to explore, not to mine: a patch on land where the register shows only a prospecting licence
const explore = photo.filter((p) => p.licence === 'prospecting only').slice(0, 20);
if (explore.length) {
  const p = pick(explore, 5);
  posts.push({
    slug: 'explore', kind: 'Licensed to explore, not to mine', title: `Licensed to explore, not to mine: ${near(p)}`,
    alt: `Satellite pictures of land ${near(p)}. Before, ${longDate(p.chips.before.date)}: green cover. After, ${longDate(p.chips.after.date)}: bare ground.`,
    text: pick([
      `A prospecting licence lets its holder look for gold. It does not allow mining.\n\n${hectares(p.ha)} of land was cleared ${placeName(p)}, on land where the Minerals Commission's register shows only a prospecting licence.`,
      `${hectares(p.ha)} cleared ${placeName(p)}. The register shows a licence to explore on this land, not a licence to mine.`,
    ], 2),
    reply: `What each licence allows: ${SITE}/method#licences`,
    render: () => townPost({ headline: `A licence to explore, not to mine`, sub: `${hectares(p.ha)} cleared ${placeName(p)}, on land where the register shows only a prospecting licence. Prospecting does not allow mining.`, before: p.chips.before, after: p.chips.after }),
  });
}

// 11. Not every patch is galamsey: clearing inside a mining licence, shown just as plainly. It keeps us fair
const licensed = photo.filter((p) => p.licence === 'large-scale lease' || p.licence === 'small-scale licence').slice(0, 20);
if (licensed.length) {
  const p = pick(licensed, 7);
  const lic = p.licence === 'large-scale lease' ? 'a large-scale mining lease' : 'a small-scale mining licence';
  posts.push({
    slug: 'licensed', kind: 'Not every patch is galamsey', title: `Not every patch is galamsey: ${near(p)}`,
    alt: `Satellite pictures of land ${near(p)}. Before, ${longDate(p.chips.before.date)}. After, ${longDate(p.chips.after.date)}: bare ground.`,
    text: pick([
      `Not every cleared patch is galamsey. These ${hectares(p.ha)} ${placeName(p)} are inside ${lic} on the Minerals Commission's register, so this may be licensed mining.\n\nWe show these too. The register is part of the evidence.`,
      `${hectares(p.ha)} cleared ${placeName(p)}, inside ${lic}. A licence on the land does not tell you who did the digging, but it does mean this may be licensed mining.`,
    ], 4),
    reply: `What each licence label means: ${SITE}/method#licences`,
    render: () => townPost({ headline: 'Not every patch is galamsey', sub: `${hectares(p.ha)} cleared ${placeName(p)}, inside ${lic} on the register. This may be licensed mining.`, before: p.chips.before, after: p.chips.after }),
  });
}

// 12. Close to home: big patches nearest to a town or village, by distance to its point on OpenStreetMap
const close = photo.filter((p) => p.ha >= 5 && p.near && p.near_km !== null).sort((a, b) => a.near_km! - b.near_km!).slice(0, 10);
if (close.length) {
  const p = pick(close, 2);
  const d = metres(p.near_km!);
  posts.push({
    slug: 'close', kind: 'Close to home', title: `Close to home: ${d} from ${p.near}`,
    alt: `One satellite view of land beside ${p.near}, split down the middle. Left, before, ${longDate(p.chips.before.date)}. Right, after, ${longDate(p.chips.after.date)}: bare ground.`,
    text: pick([
      `${hectares(p.ha)} of cleared land, about ${d} from the centre of ${p.near}${p.district ? `, ${tidyDistrict(p.district)}` : ''}.\n\n${LICENCE_SENTENCE[p.licence]}`,
      `This is ${p.near}'s doorstep: ${hectares(p.ha)} cleared about ${d} from the middle of the town, seen by satellite.\n\n${LICENCE_SENTENCE[p.licence]}`,
    ], 6),
    reply: `Every patch around ${p.near}: ${SITE}/places/${p.id}/`,
    render: () => splitPost({ headline: `${hectares(p.ha)} cleared about ${d} from ${p.near}`, sub: `Distance from the town's centre on OpenStreetMap. ${LICENCE_SENTENCE[p.licence]}`, before: p.chips.before, after: p.chips.after }),
  });
}

// 13. Village spotlight: towns ranked 9 to 60 by cleared land within 1 km, one a week (the town of the week is 1 to 8)
const villages = doorstep(60).slice(8);
if (villages.length) {
  const { town, place: p } = villages[WEEK % villages.length];
  const district = town.district ? tidyDistrict(town.district) : null;
  posts.push({
    slug: 'village', kind: 'Village spotlight', title: `Village spotlight: ${town.name}`,
    alt: `Satellite pictures of land near ${town.name}. Before, ${longDate(p.chips.before.date)}: green cover. After, ${longDate(p.chips.after.date)}: bare ground.`,
    text: pick([
      `You may never have heard of ${town.name}${district ? ` in ${district}` : ''}. Within 1 km of it, satellites saw ${hectares(town.ha)} of land cleared in 12 months.\n\nThis is its largest patch, before and after. ${LICENCE_SENTENCE[p.licence]}`,
      `${town.name}${district ? `, ${district}` : ''}: ${hectares(town.ha)} of land cleared within 1 km in the last 12 months, in ${count(town.patches)} patches.\n\n${LICENCE_SENTENCE[p.licence]}`,
    ], 8),
    reply: `Every patch around ${town.name}: ${SITE}/places/${p.id}/`,
    render: () => townPost({ headline: `${hectares(town.ha)} cleared within 1 km of ${town.name}`, sub: `In 12 months${district ? `, in ${district}` : ''}. ${LICENCE_SENTENCE[p.licence]}`, before: p.chips.before, after: p.chips.after }),
  });
}

// 14. The newest patches as a contact sheet: the six pictured patches satellites saw first most recently
const newest = photo.filter((p) => p.ha >= 2).sort((a, b) => b.first_seen.localeCompare(a.first_seen)).slice(0, 6);
if (newest.length === 6) {
  posts.push({
    slug: 'sheet', kind: 'Newest patches', title: 'The six newest patches',
    alt: `Six satellite pictures of newly cleared land: ${newest.map((p) => `${hectares(p.ha)} ${near(p)}`).join(', ')}.`,
    text: pick([
      `The six newest patches of cleared land the satellites have pictured, each 2 hectares or more: ${newest.map((p) => (p.near ?? tidyDistrict(p.district ?? ''))).filter(Boolean).join(', ')}.\n\nFirst seen between ${shortDate(newest[5].first_seen)} and ${shortDate(newest[0].first_seen)}.`,
      `Six places, newly cleared, seen by satellite. The ring marks the patch in each picture.\n\n${newest.map((p) => `${hectares(p.ha)} ${near(p)}`).join('\n')}`,
    ], 9),
    reply: `All patches, newest first: ${SITE}/map?sort=newest`,
    render: () => sheetPost({ title: 'The six newest patches', line: `Cleared land of 2 hectares or more, first seen between ${shortDate(newest[5].first_seen)} and ${shortDate(newest[0].first_seen)}.`, places: newest.map((p) => ({ label: `${hectares(p.ha)}, ${p.near ?? 'unnamed place'}`, after: p.chips.after })) }),
  });
}

// 15. Districts compared: the eight with the most cleared land
const eight = (summary?.top_districts ?? []).slice(0, 8);
if (eight.length >= 5 && summary) {
  posts.push({
    slug: 'districts', kind: 'Districts compared', title: 'The districts with the most cleared land',
    alt: `Bars for the ${count(eight.length)} districts with the most cleared land in 12 months: ${eight.map((d) => `${tidyDistrict(d.district)} ${num(d.ha)} hectares`).join(', ')}.`,
    text: `The ${count(eight.length)} districts with the most land cleared in the 12 months leading up to ${dataDate}:\n\n${eight.map((d) => `${tidyDistrict(d.district)}: ${num(d.ha)} ha`).join('\n')}`,
    reply: `Every district, with its patches: ${SITE}/map`,
    render: () => barsPost({ title: 'Where the most land was cleared', line: `The ${count(eight.length)} districts with the most, in the 12 months leading up to ${dataDate}`, rows: eight.map((d) => ({ label: tidyDistrict(d.district), value: d.ha, text: `${num(d.ha)} ha` })), sub: `From the ${count(coverage.length)} areas of the southern gold belt we cover.` }),
  });
}

// 16. Patch sizes: how the clearing splits into small and large patches
if (summary && active.length) {
  const bins = [[1, 2, '1 to 2 hectares'], [2, 5, '2 to 5 hectares'], [5, 10, '5 to 10 hectares'], [10, Infinity, '10 hectares or more']] as const;
  const rows = bins.map(([lo, hi, label]) => {
    const inBin = active.filter((p) => p.ha >= lo && p.ha < hi);
    return { label, value: inBin.length, text: `${num(inBin.length)} patches, ${num(inBin.reduce((t, p) => t + p.ha, 0))} ha`, ha: inBin.reduce((t, p) => t + p.ha, 0) };
  });
  const small = rows[0].value + rows[1].value;
  const smallShare = small / active.length;
  const smallHa = (rows[0].ha + rows[1].ha) / active.reduce((t, p) => t + p.ha, 0);
  const tenths = Math.round(smallShare * 10);
  posts.push({
    slug: 'sizes', kind: 'Patch sizes', title: 'Small patches, a lot of land',
    alt: `Bars showing how many cleared patches there are of each size: ${rows.map((r) => `${r.label}, ${r.text}`).join('. ')}.`,
    text: `${tenths} in 10 cleared patches are under 5 hectares. Together they hold ${pct(smallHa)} of all the cleared land we track.\n\nIt is not a few huge pits. It is thousands of small ones, ${num(active.length)} patches in all.`,
    reply: `Every patch, smallest to largest: ${SITE}/map`,
    render: () => barsPost({ title: 'How big the patches are', big: `${tenths} in 10`, line: `cleared patches are under 5 hectares. They hold ${pct(smallHa)} of the cleared land.`, rows, sub: `${num(active.length)} patches of 1 hectare or more, cleared in the 12 months leading up to ${dataDate}.` }),
  });
}

// 17. Where it is: the belt as a map, every patch a dot
if (summary && active.length) {
  posts.push({
    slug: 'map', kind: 'Where it is', title: 'Every cleared patch on one map',
    alt: `A map of southern Ghana with ${num(active.length)} pink dots, one for each patch of land cleared in 12 months, bigger dots for bigger patches.`,
    text: pick([
      `Every dot is a patch of land cleared in the last 12 months: ${num(active.length)} of them, ${num(summary.total_ha)} hectares, across the ${count(coverage.length)} areas of the southern gold belt we cover.`,
      `${num(active.length)} patches of cleared land, one dot each, seen by satellite in the 12 months leading up to ${dataDate}.`,
    ], 10),
    reply: `The map, where you can tap any dot: ${SITE}/map`,
    render: () => mapPost({ title: 'Every cleared patch, one dot each', big: num(active.length), line: `patches of land cleared in 12 months`, sub: `Bigger dots are bigger patches. The ${count(coverage.length)} areas of the southern gold belt we cover, in the 12 months leading up to ${dataDate}.`, frame: waterMap.frame, land: waterMap.land as number[][][][], dots: active.map((p) => ({ lon: p.lon, lat: p.lat, ha: p.ha })) }),
  });
}

// 18. All five water plants on one card
if (water.length >= 3) {
  posts.push({
    slug: 'plants', kind: 'All five water plants', title: 'Cleared land upstream of each water plant',
    alt: `Bars for the land cleared upstream of each water treatment plant: ${water.map((w) => `${w.plant} on the ${w.river}, ${num(w.ha)} hectares`).join(', ')}.`,
    text: `Land cleared in 12 months on the land that drains to each water treatment plant:\n\n${water.map((w) => `${w.plant} (${w.river}): ${num(w.ha)} ha`).join('\n')}\n\nWhen it rains, mud from cleared land washes into the rivers the plants draw from.`,
    reply: `The map of what drains where: ${SITE}/#mud`,
    render: () => barsPost({ title: 'Upstream of the water plants', line: 'Land cleared in 12 months on the land that drains to each plant', rows: water.map((w) => ({ label: `${w.plant}, on the ${w.river}`, value: w.ha, text: `${num(w.ha)} ha` })), sub: 'When it rains, mud from cleared land washes into the river each plant draws from.', color: RIVER_BLUE }),
  });
}

// 19. The rate again, per hour: the same 12-month average, a different unit, so it reads fresh
if (summary && summary.total_ha > 0) {
  const perHour = Math.max(1, Math.round(summary.total_ha / PITCH_HA / 365 / 24));
  posts.push({
    slug: 'rate-hour', kind: 'Football pitches an hour', title: 'Football pitches an hour',
    alt: `${perHour} football pitches: on average, the land cleared every hour in Ghana's southern gold belt.`,
    text: `About ${count(perHour)} football pitches of land cleared every hour, day and night, on average, in the parts of Ghana's southern gold belt we track.\n\n${num(summary.total_ha)} hectares in the 12 months leading up to ${dataDate}.`,
    reply: `Where it is, place by place: ${SITE}/`,
    render: () => ratePost({ top: "Every hour in Ghana's southern gold belt", perDay: perHour, line: 'football pitches of land cleared, day and night', sub: `On average: ${num(summary.total_ha)} hectares in the 12 months leading up to ${dataDate}.` }),
  });
}

// 20. The water test: how many no-licence patches show open water, and what that means
const noLicence = active.filter((p) => p.licence === 'no licence' || p.licence === 'prospecting only');
const likely = active.filter((p) => p.likely_galamsey);
if (likely.length && noLicence.length) {
  const ex = pits[0];
  posts.push({
    slug: 'water-test', kind: 'The water test', title: 'The water test',
    alt: `${num(likely.length)} cleared patches labelled Likely galamsey.${ex ? ` A satellite picture of one, ${near(ex)}, with dark ponds on bare ground.` : ''}`,
    text: `${num(likely.length)} cleared patches with no licence to mine also show open water in or right beside them. Mining pits fill with water, so we label these Likely galamsey.\n\nIt is our guess from the satellite, not a finding. A patch without the label can still be galamsey.`,
    reply: `How the test works: ${SITE}/method#likely`,
    render: () => statPost({ title: 'The water test', big: num(likely.length), line: 'patches labelled Likely galamsey', body: 'No licence to mine on the register, and open water in or right beside the cleared land. Mining pits fill with water. It is our guess, not a finding.', picture: ex?.chips.after, caption: ex ? `${hectares(ex.ha)} ${near(ex)}, ${shortDate(ex.chips.after.date)}` : undefined }),
  });
}

// 21. Month in review: land first seen in the last calendar month (posted on the first Friday of a month)
if (summary) {
  // The last month the data covers to its end: data up to 31 October reviews October, up to 5 December November
  const end = new Date(Date.parse(summary.data_date) - 10 * 864e5);
  const monthStart = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), 1));
  const monthEnd = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth() + 1, 1));
  const inMonth = active.filter((p) => { const t = Date.parse(p.first_seen); return t >= monthStart.getTime() && t < monthEnd.getTime(); });
  // New patches often wait weeks for a cloud-free picture, so fall back to the newest pictured one
  const top = inMonth.filter(pictured)[0];
  const shown = top ?? newest[0];
  const month = monthStart.toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' });
  if (inMonth.length) {
    const ha = inMonth.reduce((t, p) => t + p.ha, 0);
    posts.push({
      slug: 'month', kind: 'Month in review', title: `${month} in review`,
      alt: `${num(ha)} hectares of land first seen cleared in ${month}, in ${num(inMonth.length)} patches.${top ? ` A satellite picture of the largest, ${near(top)}.` : ''}`,
      text: `In ${month}, satellites first saw ${num(ha)} hectares of newly cleared land, in ${num(inMonth.length)} patches.${top ? `\n\nThe largest: ${hectares(top.ha)} ${placeName(top)}. ${LICENCE_SENTENCE[top.licence]}` : ''}\n\nNASA confirms clearing over several weeks, so this number can still go up.`,
      reply: `All patches, newest first: ${SITE}/map?sort=newest`,
      render: () => statPost({ title: `${month} in review`, big: `${num(ha)} ha`, line: `of newly cleared land, in ${num(inMonth.length)} patches`, body: 'First seen by satellite that month. NASA confirms clearing over several weeks, so the number can still go up.', picture: shown?.chips.after, caption: shown ? `${top ? 'The largest' : 'One of the newest'}: ${hectares(shown.ha)} ${near(shown)}` : undefined }),
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
  alt: 'Five labels for the licence on cleared land, from no licence to a large-scale mining lease, each with what it allows.',
  text: 'For every patch, we check the Minerals Commission\'s public licence register:\n\nNo licence: nothing on the register.\nProspecting only: a licence to explore, not to mine.\nStone or sand lease: quarrying, not gold.\nSmall-scale licence and large-scale lease: mining is allowed there.\n\nMining without a licence is what galamsey is.',
  reply: `What each label means: ${SITE}/method#licences`,
  render: () => explainerPost({ title: 'How we check the licence', points: [
    { mark: '', markColor: SIGNAL_RED, head: 'No licence', body: 'Nothing on the Minerals Commission\'s register for this land.' },
    { mark: '', markColor: SIGNAL_PINK, head: 'Prospecting only', body: 'A licence to explore. It does not allow mining.' },
    { mark: '', markColor: '#888', head: 'Stone or sand lease', body: 'For quarrying stone or digging sand. Not for gold.' },
    { mark: '', markColor: '#333', head: 'Small-scale licence or large-scale lease', body: 'Mining is allowed. A licence does not show who did the digging.' },
    { mark: '', markColor: '#000', head: 'Galamsey', body: 'Mining without a licence to mine. Our labels show where the register has none.' },
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
// The town the town post shows this week, for the studio's templates
export const townOfWeek = lead ? { ...lead, rank: leadRank } : null;
