// This week's ready-to-post images and words, rebuilt by every weekly run and listed on the hidden /share page.
// Each post is made to be quoted: one picture that stands alone, one true fact, no question to the reader.
// The link goes in the first reply. Wording follows the site: no em dashes or semicolons, no verdicts on a place.
import { active, coverage, doorstep, hasPair, summary, water, type Chip, type Place } from './data';
import { LICENCES, LICENCE_SENTENCE, LICENCE_SHORT, count, hectares, longDate, num, pct, placeName, tidyDistrict } from './format';
import { catchments, inside } from './plants';
import { districtPost, licencePost, ratePost, townPost, waterPost } from './og';

const SITE = (import.meta.env.SITE ?? 'https://galamseytracker.org').replace(/\/$/, '');
const PITCH_HA = 0.714; // a 105 x 68 m football pitch, as on the site (docs/sources.json football-pitch)
const pitches = (ha: number) => Math.round(ha / PITCH_HA);

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

// 1. The town with the most cleared land around it (the same town the home page leads with)
const lead = doorstep(1)[0];
if (lead && summary) {
  const { town, place } = lead;
  const district = town.district ? tidyDistrict(town.district) : null;
  posts.push({
    slug: 'town',
    kind: 'Town of the week',
    title: `Town of the week: ${town.name}`,
    alt: `Two satellite pictures of the same land near ${town.name}${district ? `, ${district}` : ''}. Before, ${longDate(place.chips.before.date)}: green cover. After, ${longDate(place.chips.after.date)}: wide patches of bare orange ground.`,
    text: `Within 1 km of ${town.name}${district ? `, ${district}` : ''}, satellites saw ${hectares(town.ha)} of land cleared in the last 12 months. That is about ${num(pitches(town.ha))} football pitches.\n\nThe pictures show the largest patch, before and after. ${LICENCE_SENTENCE[place.licence]}`,
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
for (const c of CITIES) {
  const ha = water.filter((w) => c.plants.includes(w.plant)).reduce((t, w) => t + w.ha, 0);
  if (ha < 1) continue;
  const polys = catchments.filter((k) => c.plants.includes(k.name)).flatMap((k) => k.polys);
  // The largest patch there that carries the Likely galamsey label, so the picture shows what the post is about
  const largest = active.filter(pictured).find((p) => p.likely_galamsey && inside([p.lon, p.lat], polys));
  const haText = num(Math.round(ha));
  posts.push({
    slug: c.slug,
    kind: 'City water',
    title: `From this to your tap in ${c.city}`,
    alt: `${haText} hectares of land cleared in 12 months on the land that drains to ${c.name}.${largest ? ` A satellite picture of one cleared patch upstream, ${placeName(largest)}, with a line following the water from it` : ' A line follows the water'} down ${c.river.replace('The ', 'the ')} to ${c.plant} and to taps in ${c.city}.`,
    text: `${c.lead} In the last 12 months, satellites saw ${haText} hectares of land cleared on the land that drains to it.\n\nWhen it rains, mud from cleared land and mining pits washes into the river, and the water gets harder and dearer to treat.`,
    reply: `Every water plant downstream of the clearing, with the map: ${SITE}/#mud`,
    render: () => waterPost({
      title: `From this to your tap in ${c.city}`, big: haText,
      line: `cleared in 12 months on the land that drains to ${c.name}`,
      river: c.river, plant: c.plant, tap: c.tap, picture: largest?.chips.after,
    }),
  });
}

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

// 4. One district: its total and its three largest pictured patches (the district with the most clearing)
const topDistrict = summary?.top_districts[0];
if (topDistrict) {
  const name = tidyDistrict(topDistrict.district);
  const inDistrict = active.filter(pictured).filter((p) => p.district === topDistrict.district).slice(0, 3);
  if (inDistrict.length === 3) {
    posts.push({
      slug: 'district',
      kind: 'District spotlight',
      title: `District spotlight: ${name}`,
      alt: `${num(topDistrict.ha)} hectares of land cleared in 12 months in ${name}. Satellite pictures of its three largest cleared patches: ${inDistrict.map((p) => placeName(p)).join(', ')}.`,
      text: `${name} has more cleared land than any other district we track: ${num(topDistrict.ha)} hectares in 12 months, about ${num(pitches(topDistrict.ha))} football pitches.

These are its three largest cleared patches, seen by satellite.`,
      reply: `Every patch in ${name}, on the map: ${SITE}/map?district=${encodeURIComponent(topDistrict.district)}`,
      render: () => districtPost({
        title: `${name}, the district with the most cleared land`,
        big: `${num(topDistrict.ha)} ha`,
        line: `cleared in the 12 months leading up to ${dataDate}`,
        stat: `About ${num(pitches(topDistrict.ha))} football pitches`,
        places: inDistrict.map((p) => ({ label: `${hectares(p.ha)}, ${p.near ? `near ${p.near}` : 'unnamed place'}`, after: p.chips.after })),
      }),
    });
  }
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
// Here the second town in the list, so the library always shows a sample.
const second = doorstep(2)[1];
if (second && summary) {
  const { town, place } = second;
  const district = town.district ? tidyDistrict(town.district) : null;
  posts.push({
    slug: 'place',
    kind: 'One place (news days)',
    title: `One place: ${town.name}`,
    alt: `Two satellite pictures of the same land near ${town.name}. Before, ${longDate(place.chips.before.date)}: green cover. After, ${longDate(place.chips.after.date)}: bare ground.`,
    text: `Near ${town.name}${district ? `, ${district}` : ''}: ${hectares(place.ha)} of land cleared, first seen by satellite on ${longDate(place.first_seen)}.

${LICENCE_SENTENCE[place.licence]}`,
    reply: `Before and after up close: ${SITE}/places/${place.id}/`,
    render: () => townPost({
      headline: `${hectares(place.ha)} of land cleared near ${town.name}`,
      sub: `First seen by satellite on ${longDate(place.first_seen)}${district ? `, in ${district}` : ''}. ${LICENCE_SENTENCE[place.licence]}`,
      before: place.chips.before, after: place.chips.after,
    }),
  });
}

export const sharePosts = posts;
