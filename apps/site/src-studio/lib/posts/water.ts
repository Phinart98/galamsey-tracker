// The cities' water: land cleared with no licence to mine on the land that drains to the treatment plants that
// supply them (who each plant supplies: docs/sources.json claim water-plant-towns). The hectares come from the
// weekly run (summary water[].no_licence_ha), so they match the site's map of what drains where.
import { active, water } from '../../../src/lib/data';
import { num, placeName, shortDate } from '../../../src/lib/format';
import { catchments, inside } from '../../../src/lib/plants';
import { barsPost, waterPost } from '../designs';
import { SITE, pick, showable, type Post } from './rules';

export const waterPosts: Post[] = [];
const RIVER_BLUE = '#1D5C8C'; // designs.ts RIVER

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

// Land with no licence to mine upstream of each plant. Missing from summaries made before 9 November 2026, and then
// the water posts wait: the all-clearing figure would count licensed mines.
const noLicenceHa = new Map(water.filter((w) => w.no_licence_ha != null).map((w) => [w.plant, w.no_licence_ha!]));

CITIES.forEach((c, ci) => {
  if (!c.plants.every((p) => noLicenceHa.has(p))) return;
  const ha = c.plants.reduce((t, p) => t + noLicenceHa.get(p)!, 0);
  if (ha < 1) return;
  // One of the three largest pictured patches upstream, a different one each week, so the same city's post does
  // not repeat its picture
  const polys = catchments.filter((k) => c.plants.includes(k.name)).flatMap((k) => k.polys);
  const candidates = active.filter(showable).filter((p) => inside([p.lon, p.lat], polys)).slice(0, 3);
  const shown = candidates.length ? pick(candidates, ci) : undefined;
  const haText = num(Math.round(ha));
  const it = c.plants.length > 1 ? 'them' : 'it';
  waterPosts.push({
    slug: c.slug,
    kind: 'City water',
    title: `From this to your tap in ${c.city}`,
    alt: `${haText} hectares of land cleared with no licence to mine in 12 months, on the land that drains to ${c.name}.${shown ? ` A satellite picture of one cleared patch upstream, ${placeName(shown)}, with a line following the water from it` : ' A line follows the water'} down ${c.river.replace('The ', 'the ')} to ${c.plant} and to taps in ${c.city}.`,
    text: pick([
      `${c.lead} In the last 12 months, satellites saw ${haText} hectares of land cleared with no licence to mine on the land that drains to ${it}.\n\nWhen it rains, mud from cleared land and mining pits washes into the river, and the water gets harder and dearer to treat.`,
      `${haText} hectares of land cleared with no licence to mine in 12 months, all on land that drains to ${c.name}. ${c.tap}.\n\nWhen it rains, mud from that land washes into the river the plant draws from.`,
      `Water for taps in ${c.city} is treated at ${c.name}. On the land that drains to ${it}, satellites saw ${haText} hectares of land cleared with no licence to mine in the last 12 months.\n\nMore mud in the river makes the water harder and dearer to treat.`,
    ], ci),
    reply: `Every water plant downstream of the clearing, with the map: ${SITE}/#mud`,
    render: () => waterPost({
      title: `From this to your tap in ${c.city}`, big: haText,
      line: `cleared with no licence to mine in 12 months, on the land that drains to ${c.name}`,
      river: c.river, plant: c.plant, tap: c.tap, picture: shown?.chips.after,
      caption: shown ? `One patch, ${num(Math.round(shown.ha))} ha, ${shortDate(shown.chips.after.date)}` : undefined,
    }),
  });
});

// All five water plants on one card
const plantRows = water.filter((w) => w.no_licence_ha != null).map((w) => ({ ...w, ha: w.no_licence_ha! })).sort((a, b) => b.ha - a.ha);
if (plantRows.length >= 3) {
  waterPosts.push({
    slug: 'plants', kind: 'All five water plants', title: 'Cleared land upstream of each water plant',
    alt: `Bars for the land cleared with no licence to mine upstream of each water treatment plant: ${plantRows.map((w) => `${w.plant} on the ${w.river}, ${num(w.ha)} hectares`).join(', ')}.`,
    text: `Land cleared with no licence to mine in 12 months, on the land that drains to each water treatment plant:\n\n${plantRows.map((w) => `${w.plant} (${w.river}): ${num(w.ha)} ha`).join('\n')}\n\nWhen it rains, mud from cleared land washes into the rivers the plants draw from.`,
    reply: `The map of what drains where: ${SITE}/#mud`,
    render: () => barsPost({ title: 'Upstream of the water plants', line: 'Land cleared with no licence to mine in 12 months, on the land that drains to each plant', rows: plantRows.map((w) => ({ label: `${w.plant}, on the ${w.river}`, value: w.ha, text: `${num(w.ha)} ha` })), sub: 'When it rains, mud from cleared land washes into the river each plant draws from.', color: RIVER_BLUE }),
  });
}
