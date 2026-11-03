// This week's ready-to-post images and words, rebuilt by every weekly run and listed on the hidden /share page.
// Each post is made to be quoted: one picture that stands alone, one true fact, no question to the reader.
// The link goes in the first reply. Wording follows the site: no em dashes or semicolons, no verdicts on a place.
import { active, coverage, doorstep, hasPair, summary, water, type Chip, type Place } from './data';
import { LICENCE_SENTENCE, count, hectares, longDate, num, placeName, tidyDistrict } from './format';
import { catchments, inside } from './plants';
import { ratePost, townPost, waterPost } from './og';

const SITE = (import.meta.env.SITE ?? 'https://galamseytracker.org').replace(/\/$/, '');
const PITCH_HA = 0.714; // a 105 x 68 m football pitch, as on the site (docs/sources.json football-pitch)
const pitches = (ha: number) => Math.round(ha / PITCH_HA);

export interface Post {
  slug: string;
  title: string;
  alt: string;
  text: string;
  reply: string;
  render: () => Promise<Buffer>;
}

const posts: Post[] = [];
const dataDate = summary ? longDate(summary.data_date) : '';

// 1. The town with the most cleared land around it (the same town the home page leads with)
const lead = doorstep(1)[0];
if (lead && summary) {
  const { town, place } = lead;
  const district = town.district ? tidyDistrict(town.district) : null;
  posts.push({
    slug: 'town',
    title: `Town of the week: ${town.name}`,
    alt: `Two satellite pictures of the same land near ${town.name}${district ? `, ${district}` : ''}. Before, ${longDate(place.chips.before.date)}: green forest. After, ${longDate(place.chips.after.date)}: bare ground where the forest was.`,
    text: `Within 1 km of ${town.name}${district ? `, ${district}` : ''}, satellites saw ${hectares(town.ha)} of land cleared in the last 12 months. That is about ${num(pitches(town.ha))} football pitches.\n\nThe pictures show the largest patch, before and after. ${LICENCE_SENTENCE[place.licence]}`,
    reply: `The pictures up close, and every patch around ${town.name}: ${SITE}/places/${place.id}/`,
    render: () => townPost({
      headline: `${hectares(town.ha)} of land cleared within 1 km of ${town.name}`,
      sub: `${district ? `${district}. ` : ''}Seen by satellite in the 12 months leading up to ${dataDate}.`,
      stat: `About ${num(pitches(town.ha))} football pitches`,
      note: `The pictures show the largest patch, first seen on ${longDate(place.first_seen)}. ${LICENCE_SENTENCE[place.licence]}`,
      before: place.chips.before, after: place.chips.after,
    }),
  });
}

// 2. The cities' water: hectares cleared on the land that drains to the plants that supply them
// (who each plant supplies: docs/sources.json claim water-plant-towns)
const CITIES = [
  { slug: 'water-accra', top: 'Water for central and western Accra', plants: ['Weija'], name: 'the Weija treatment plant on the Densu',
    lead: 'Central and western Accra get their water from the Weija treatment plant on the Densu.' },
  { slug: 'water-kumasi', top: 'Water for Greater Kumasi', plants: ['Barekese', 'Owabi'], name: 'the Barekese and Owabi treatment plants',
    lead: 'Greater Kumasi gets its water from the Barekese and Owabi treatment plants.' },
  { slug: 'water-takoradi', top: 'Water for Sekondi-Takoradi', plants: ['Daboase'], name: 'the Daboase treatment plant on the Pra',
    lead: 'Sekondi-Takoradi gets much of its water from the Daboase treatment plant on the Pra.' },
  { slug: 'water-winneba', top: 'Water for Winneba, Swedru and Kasoa', plants: ['Kwanyako'], name: 'the Kwanyako treatment plant on the Ayensu',
    lead: 'Winneba, Swedru and Kasoa get their water from the Kwanyako treatment plant on the Ayensu.' },
];
const pictured = (p: Place): p is Place & { chips: { before: Chip; after: Chip } } => hasPair(p);
for (const c of CITIES) {
  const ha = water.filter((w) => c.plants.includes(w.plant)).reduce((t, w) => t + w.ha, 0);
  if (ha < 1) continue;
  const polys = catchments.filter((k) => c.plants.includes(k.name)).flatMap((k) => k.polys);
  // The largest patch there that carries the Likely galamsey label, so the picture shows what the post is about
  const largest = active.filter(pictured).find((p) => p.likely_galamsey && inside([p.lon, p.lat], polys));
  const haText = num(Math.round(ha));
  posts.push({
    slug: c.slug,
    title: c.top,
    alt: `${c.top}: ${haText} hectares of land cleared in 12 months on the land that drains to ${c.name}.${largest ? ` Satellite pictures of the largest patch there with the Likely galamsey label, ${placeName(largest)}, before and after.` : ''}`,
    text: `${c.lead} In the last 12 months, satellites saw ${haText} hectares of land cleared on the land that drains to it.\n\nWhen it rains, mud from cleared land and mining pits washes into the river, and the water gets harder and dearer to treat.`,
    reply: `Every water plant downstream of the clearing, with the map: ${SITE}/#mud`,
    render: () => waterPost({
      top: c.top, big: `${haText} ha`,
      line: `of land cleared in 12 months on the land that drains to ${c.name}.`,
      note: largest ? `The largest patch there with our Likely galamsey label, ${placeName(largest)}. An educated guess from satellite data, not a finding.` : '',
      before: largest?.chips.before, after: largest?.chips.after,
    }),
  });
}

// 3. The average rate, as football pitches an hour (an average of our own 12-month total, not a claim that it is rising)
if (summary && summary.total_ha > 0) {
  const perHour = summary.total_ha / PITCH_HA / 365 / 24;
  const big = perHour >= 1.5 ? String(Math.round(perHour)) : null;
  const perDay = Math.round(summary.total_ha / PITCH_HA / 365);
  posts.push({
    slug: 'rate',
    title: 'Football pitches an hour',
    alt: big
      ? `On average, about ${big} football pitches of land cleared every hour in Ghana's southern gold belt. ${num(summary.total_ha)} hectares in the 12 months leading up to ${dataDate}.`
      : `On average, about ${perDay} football pitches of land cleared every day in Ghana's southern gold belt.`,
    text: big
      ? `On average, about ${big} football pitches of land are cleared every hour in the parts of Ghana's southern gold belt we track.\n\nThat is ${num(summary.total_ha)} hectares in the 12 months leading up to ${dataDate}, seen by satellite.`
      : `On average, about ${perDay} football pitches of land are cleared every day in the parts of Ghana's southern gold belt we track.\n\nThat is ${num(summary.total_ha)} hectares in the 12 months leading up to ${dataDate}, seen by satellite.`,
    reply: `Where it is, with before and after pictures of every patch: ${SITE}/`,
    render: () => ratePost({
      top: "Ghana's southern gold belt, on average",
      big: big ?? String(perDay),
      line: big ? 'football pitches of land cleared every hour' : 'football pitches of land cleared every day',
      sub: `${num(summary.total_ha)} hectares in the 12 months leading up to ${dataDate}, seen by satellite in the ${count(coverage.length)} areas we cover.`,
    }),
  });
}

export const sharePosts = posts;
