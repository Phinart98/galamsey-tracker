// The monthly email to one journalist, NGO or researcher. Every number comes from this week's data, so it stays
// current with no editing. Same rules as the posts: no em dashes or semicolons, never call a place illegal, never
// name anyone. (Templates for other platforms were dropped on 2026-11-05: X only for now.)
import { summary, townsNear, water } from '../../src/lib/data';
import { PITCH_HA, hectares, longDate, num, pct } from '../../src/lib/format';

const SITE = 'https://galamseytracker.org';

export interface Template { slug: string; name: string; use: string; fields: [string, string][] }

export function templates(): Template[] {
  if (!summary) return [];
  const date = longDate(summary.data_date);
  const perDay = Math.round(summary.total_ha / PITCH_HA / 365);
  const pra = water.find((w) => w.plant === 'Daboase');
  const weija = water.find((w) => w.plant === 'Weija');

  const facts = [
    `Satellites saw ${num(summary.total_ha)} hectares of land cleared in the 12 months leading up to ${date}, about ${perDay} football pitches a day.`,
    `${pct(summary.no_licence_to_mine.share ?? 0)} of it is on land with no licence to mine, going by the Minerals Commission's public register.`,
    pra && `${pct(pra.ha / summary.total_ha)} of it drains into the River Pra above the Daboase plant, which supplies Sekondi-Takoradi.`,
    weija && `${hectares(weija.ha)} were cleared on land that drains to the Weija plant, which supplies central and western Accra.`,
    townsNear && `At least ${num(townsNear.count)} towns and villages have cleared land within 1 km of them.`,
  ].filter(Boolean) as string[];

  return [{
    slug: 'email', name: 'Email to a journalist, NGO or researcher',
    use: 'One person at a time, with one angle that fits their work. Change the first line to say why you picked them.',
    fields: [
      ['Subject', 'Free weekly satellite data on galamsey and Ghana\'s water'],
      ['Email', `Hello,

I am writing because of your work on [their story or topic]. Galamsey Tracker (${SITE}) is a free website that uses NASA and European satellite data to show, every week, where land has been cleared in Ghana's southern gold belt, with what the Minerals Commission's register says about the licence on the land.

From this week's data, which you are free to use:

${facts.map((f) => `- ${f}`).join('\n')}

Every place has before and after satellite pictures, and the full data can be downloaded as a spreadsheet: ${SITE}/data

If it would help a story or report, I can pull the numbers and pictures for a particular district, river or town.

Thank you,
Galamsey Tracker
${SITE}`],
    ],
  }];
}
