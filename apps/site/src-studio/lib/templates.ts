// Ready words for every place the evidence can go beyond X: an email, WhatsApp, Facebook, LinkedIn, Reddit and
// Hacker News. Every number comes from this week's data, so each template stays current with no editing.
// Same rules as the posts: no em dashes or semicolons, never call a place illegal, never name anyone.
import { doorstep, summary, townsNear, water } from '../../src/lib/data';
import { hectares, longDate, num, pct, tidyDistrict } from '../../src/lib/format';

const SITE = 'https://galamseytracker.org';

export interface Template { slug: string; name: string; use: string; image?: string; fields: [string, string][] }

export function templates(): Template[] {
  if (!summary) return [];
  const date = longDate(summary.data_date);
  const total = `${num(summary.total_ha)} hectares`;
  const noLicence = pct(summary.no_licence_to_mine.share ?? 0);
  const perDay = Math.round(summary.total_ha / 0.714 / 365);
  const pra = water.find((w) => w.plant === 'Daboase');
  const weija = water.find((w) => w.plant === 'Weija');
  const praShare = pra ? pct(pra.ha / summary.total_ha) : '';
  const lead = doorstep(1)[0];
  const town = lead ? `${lead.town.name}${lead.town.district ? `, ${tidyDistrict(lead.town.district)}` : ''}` : '';
  const towns = townsNear ? num(townsNear.count) : '';

  const facts = [
    `Satellites saw ${total} of land cleared in the 12 months leading up to ${date}, about ${perDay} football pitches a day.`,
    `${noLicence} of it is on land with no licence to mine, going by the Minerals Commission's public register.`,
    pra && `${praShare} of it drains into the River Pra above the Daboase plant, which supplies Sekondi-Takoradi.`,
    weija && `${hectares(weija.ha)} were cleared on land that drains to the Weija plant, which supplies central and western Accra.`,
    towns && `At least ${towns} towns and villages have cleared land within 1 km of them.`,
  ].filter(Boolean) as string[];

  return [
    {
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
    },
    {
      slug: 'whatsapp', name: 'WhatsApp (family groups and Status)',
      use: 'Short, so it is read in the chat. Send it with the image of the day.',
      fields: [['Message', `Satellites saw ${total} of land cleared in Ghana's gold belt in the last 12 months, about ${perDay} football pitches every day. ${noLicence} of it has no licence to mine on it.

You can look up any town and see the before and after pictures: ${SITE}`]],
    },
    {
      slug: 'facebook', name: 'Facebook (hometown and diaspora groups)',
      use: 'For groups of people from the affected areas or who live abroad. Post it with the town image.',
      image: 'town',
      fields: [['Post', `Many of us grew up drinking from these rivers. Satellites now show what is happening to the land around them.

${facts.slice(0, 2).join(' ')}${pra ? ` ${facts[2]}` : ''}

${town ? `The town with the most cleared land around it this week is ${town}. ` : ''}You can search for your own town or village and see before and after satellite pictures of every patch, with what the licence register says about the land.

${SITE}`]],
    },
    {
      slug: 'linkedin', name: 'LinkedIn',
      use: 'It shows your real name, so it speaks about the project, not as its maker. LinkedIn shows posts with links to fewer people, so the link goes in the first comment.',
      image: 'rate',
      fields: [
        ['Post', `Every day, on average, about ${perDay} football pitches of land are cleared in Ghana's southern gold belt.

Galamsey Tracker is a free, open website that turns NASA and European satellite data into weekly evidence of where land is being cleared, place by place, and checks each patch against the Minerals Commission's public licence register.

From the latest data, up to ${date}:
${facts.slice(1).map((f) => `- ${f}`).join('\n')}

Every patch has before and after satellite pictures, and all the data is free to download and reuse. It is useful for journalists, NGOs, researchers, and anyone buying cocoa or gold from Ghana who needs to know what is happening on the ground.

#Galamsey #Ghana #OpenData #Satellite #Environment`],
        ['First comment, with the link', `See any town or district, with before and after pictures: ${SITE}`],
      ],
    },
    {
      slug: 'reddit-ghana', name: 'Reddit r/ghana',
      use: 'Post the town image with this title and text. Reddit readers dislike adverts, so it leads with what the satellites saw.',
      image: 'town',
      fields: [
        ['Title', town ? `Satellite pictures of the land around ${town}, before and after a year of clearing` : 'Satellite pictures of land cleared in Ghana\'s gold belt, before and after'],
        ['Text', `${facts.join('\n\n')}

These numbers come from Galamsey Tracker, a free site that updates every week from NASA and European satellite data. You can search for any town and see before and after pictures of every cleared patch, with what the Minerals Commission's register says about the licence on that land: ${SITE}

It cannot see everything. River dredging leaves no cleared land, so it misses that, and some cleared patches could be farms or roads. The method is explained in plain words on the site.`],
      ],
    },
    {
      slug: 'reddit-dataisbeautiful', name: 'Reddit r/dataisbeautiful',
      use: 'Post the football pitches image. The rules ask for [OC] in the title and a comment naming the data and tools.',
      image: 'rate',
      fields: [
        ['Title', `[OC] Land cleared in Ghana's gold belt: about ${perDay} football pitches a day, ${total} in 12 months`],
        ['Comment with sources and tools', `Data: NASA OPERA DIST-ALERT (land surface disturbance from Landsat and Sentinel-2), Copernicus Sentinel-2 pictures, the Minerals Commission's public licence register, OpenStreetMap towns.
Tools: Python (rasterio, geopandas), Astro, MapLibre. It reruns every Monday on GitHub Actions.
Patches of 1 hectare or more in the forest zone, in the 12 months leading up to ${date}. Interactive map and before and after pictures of every patch: ${SITE}`],
      ],
    },
    {
      slug: 'hacker-news', name: 'Hacker News (Show HN)',
      use: 'Once only. A link post with the site, then this text as the first comment.',
      fields: [
        ['Title', 'Show HN: Galamsey Tracker, weekly satellite evidence of gold mining clearance in Ghana'],
        ['First comment', `Galamsey is illegal small-scale gold mining in Ghana. It strips forest and fills rivers with mud, and some water treatment plants have had to cut supply.

The site rebuilds itself every Monday on free GitHub Actions and Cloudflare Pages, with no server and no one in the loop:
- NASA's OPERA DIST-ALERT product flags land that lost its vegetation cover. We keep confirmed patches of 1 ha or more in the forest zone.
- Each patch is checked against the Minerals Commission's public licence register (no licence, prospecting only, small-scale, large-scale).
- The clearest Sentinel-2 picture before and after gives a pair for every patch, and open water in or next to a no-licence patch earns a "Likely galamsey" label, because mining pits fill with water.
- Nearest town from OpenStreetMap, drainage to each city's water plant from HydroSHEDS.

${facts.slice(0, 3).join(' ')}

Known gaps: river dredging leaves no cleared land, and the savanna north is left out because dry-season farm burning looks the same as mining from space. Questions and criticism welcome.`],
      ],
    },
  ];
}
