// The monthly pitch email: one journalist or organisation a month, with one ready angle. The numbers come from this
// week's data, so the draft is always current. Contacts marked "verified" were read from the outlet's own contact
// page (2026-11-04); for the rest, Claude finds the reporter who covered the subject when that month comes.
import { summary, townsNear, water } from '../../src/lib/data';
import { longDate, num, pct } from '../../src/lib/format';

const SITE = 'https://galamseytracker.org';
const pra = water.find((w) => w.plant === 'Daboase');
const weija = water.find((w) => w.plant === 'Weija');

export interface Pitch { month: string; who: string; contact: string; verified: boolean; angle: string }

// In order, one a month. Cocoa comes before 30 December 2026, when the EU deforestation law starts.
export const PITCHES: Pitch[] = [
  { month: 'November 2026', who: 'The Fourth Estate (investigative newsroom, Media Foundation for West Africa)', contact: 'thefourthestate@mfwa.org', verified: true,
    angle: 'Water: most of the cleared land drains to the plant that supplies Sekondi-Takoradi. They reported on Weija and Kwanyako in May 2026.' },
  { month: 'December 2026', who: 'Fern (EU forest and trade campaigners) and Mighty Earth', contact: 'Claude finds the cocoa or forests lead when drafting', verified: false,
    angle: 'Cocoa: the EU deforestation law starts on 30 December. Weekly evidence of land cleared in Ghana\'s cocoa and gold belt.' },
  { month: 'January 2027', who: 'GhanaFact (fact-checkers)', contact: 'info@ghanafact.com', verified: true,
    angle: 'A tool to check claims about galamsey against what the satellites saw, place by place.' },
  { month: 'February 2027', who: 'Citi Newsroom (the #StopGalamseyNow campaign)', contact: 'Claude finds the reporter of their latest galamsey story', verified: false,
    angle: 'Weekly data and pictures for their galamsey coverage, free to use with a credit.' },
  { month: 'March 2027', who: 'JoyNews', contact: 'Claude finds the reporter of their latest galamsey story', verified: false,
    angle: 'World Water Day (22 March): what is cleared upstream of each city\'s water plant.' },
  { month: 'April 2027', who: 'Mongabay (environment news)', contact: 'Claude finds their West Africa editor', verified: false,
    angle: 'An open, automatic way to track forest loss to mining, with the licence on the land.' },
  { month: 'May 2027', who: 'Code for Africa', contact: 'Claude finds their data journalism contact', verified: false,
    angle: 'Open data and code that newsrooms can reuse.' },
];

// This month's draft, from this week's numbers (written for the November pitch: water)
export function draft() {
  if (!summary) return null;
  const share = pra ? pct(pra.ha / summary.total_ha) : '';
  const subject = 'Free weekly satellite data on galamsey and Ghana\'s water plants';
  const body = `Hello,

I run Galamsey Tracker (${SITE}), a free website that uses NASA and European satellite data to show, every week, where land has been cleared in Ghana's southern gold belt, with what the Minerals Commission's register says about the licence on the land.

A few things from this week's data, which you are free to use:

- ${num(summary.total_ha)} hectares cleared in the 12 months leading up to ${longDate(summary.data_date)}. ${pct(summary.no_licence_to_mine.share)} of it has no licence to mine on it.
${pra ? `- ${share} of that cleared land, ${num(pra.ha)} hectares, drains into the River Pra above the Daboase plant, which supplies Sekondi-Takoradi.\n` : ''}${weija ? `- ${num(weija.ha)} hectares were cleared on the land that drains to the Weija plant, which supplies central and western Accra.\n` : ''}${townsNear ? `- At least ${num(townsNear.count)} towns and villages have cleared land within 1 km of them.
` : ''}
Every place has before and after satellite pictures, and the full data can be downloaded as a spreadsheet: ${SITE}/data

If a story would help, I can pull the numbers and pictures for a particular district, river or town.

Thank you for your reporting on this.

Galamsey Tracker
${SITE}`;
  return { subject, body };
}
