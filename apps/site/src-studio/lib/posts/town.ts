// Posts about one place: the town of the week, the one-place sample for news days, and a place in the news
import { summary } from '../../../src/lib/data';
import { LICENCE_SENTENCE, hectares, longDate, num, shortDate, tidyDistrict } from '../../../src/lib/format';
import { newsPost, townPost } from '../designs';
import { SITE, lead, pick, pitches, second, type Pictured, type Post } from './rules';

export const townPosts: Post[] = [];

// Town of the week: land with no licence to mine within 1 km of one of the top towns, and its largest such patch
if (lead && summary) {
  const { town, place, rank } = lead;
  // "Ayensuano district" when the district has the town's name, so no line reads "Ayensuano in Ayensuano"
  const district = town.district ? ((d) => (d === town.name ? `${d} district` : d))(tidyDistrict(town.district)) : null;
  const where = `${town.name}${district ? `, ${district}` : ''}`;
  // Its largest patch, unless a bigger town nearby already showed that one
  const which = lead.largest ? 'its largest patch' : 'one of its largest patches';
  townPosts.push({
    slug: 'town',
    kind: 'Town of the week',
    title: `Town of the week: ${town.name}`,
    alt: `Two satellite pictures of the same land near ${where}: before, ${longDate(place.chips.before.date)}, and after, ${longDate(place.chips.after.date)}.`,
    text: pick([
      `Within 1 km of ${where}, satellites saw ${hectares(town.ha)} of land cleared with no licence to mine in the last 12 months. That is about ${num(pitches(town.ha))} football pitches.

The pictures show ${which} with signs of mining (open water, as in mining pits), before and after.`,
      `${rank === 0 ? `No town we track has more land cleared with no licence to mine around it than ${town.name}` : `Few towns we track have more land cleared with no licence to mine around them than ${town.name}`}${district ? ` in ${district}` : ''}: ${hectares(town.ha)} within 1 km, in 12 months.

Here is ${which} with signs of mining (open water, as in mining pits), before and after, seen by satellite.`,
      `${where}, seen by satellite on ${longDate(place.chips.before.date)} and again on ${longDate(place.chips.after.date)}.

Within 1 km of the town, ${hectares(town.ha)} of land was cleared with no licence to mine in the last 12 months, about ${num(pitches(town.ha))} football pitches.`,
    ]),
    reply: `The pictures up close, and every patch around ${town.name}: ${SITE}/places/${place.id}/`,
    render: () => townPost({
      // Non-breaking spaces keep "1 km" and "12 months" on one line
      headline: `${hectares(town.ha)} cleared within 1 km of ${town.name}`,
      sub: `Land with no licence to mine, in 12 months: about ${num(pitches(town.ha))} football pitches${district ? `, in ${district}` : ''}. The picture is ${which} with signs of mining, ${hectares(place.ha)}.`,
      before: place.chips.before, after: place.chips.after,
    }),
  });
}

// One place, before and after, near a named town: the sample of what a news-day post looks like
export function placePost(name: string, districtName: string | null, place: Pictured, slug = 'place', kind = 'One place (news days)'): Post {
  const district = districtName ? tidyDistrict(districtName) : null;
  return {
    slug,
    kind,
    title: `One place: ${name}`,
    alt: `Two satellite pictures of the same land near ${name}: before, ${longDate(place.chips.before.date)}, and after, ${longDate(place.chips.after.date)}.`,
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
if (second && summary) townPosts.push(placePost(second.town.name, second.town.district, second.place));

// A place in the news (made by ../news.ts): the headline as the story told it, then what the satellite saw there.
// `subject` is the town or district the story names, `name` the town the picture is near (the same for a town).
export function newsPlacePost(story: { title: string; source: string; date: string; link: string }, subject: string, name: string, districtName: string | null, place: Pictured, slug: string): Post {
  const district = districtName ? tidyDistrict(districtName) : null;
  // When the story names the district, it is said once already
  const where = subject === name && district ? `${name}, ${district}` : name;
  return {
    slug,
    kind: 'In the news',
    title: `In the news: ${name}`,
    alt: `The headline "${story.title}" (${story.source}), then satellite pictures near ${name}: before, ${longDate(place.chips.before.date)}, and after, ${longDate(place.chips.after.date)}.`,
    // Reads right as a quote of the newsroom's post and on its own, because it names the story's subject itself
    text: `${story.source} reports on ${subject}. ${subject === name ? 'This is what satellites saw there' : `In ${subject}, satellites saw this`}: ${hectares(place.ha)} of land cleared near ${where}, first seen on ${longDate(place.first_seen)}.

${LICENCE_SENTENCE[place.licence]}`,
    reply: `The story: ${story.link}
Before and after up close: ${SITE}/places/${place.id}/`,
    render: () => newsPost({ headline: story.title, outlet: story.source, date: shortDate(story.date.slice(0, 10)), place: `near ${name}`, before: place.chips.before, after: place.chips.after, line: `${hectares(place.ha)} cleared, first seen ${shortDate(place.first_seen)}. ${LICENCE_SENTENCE[place.licence]}` }),
  };
}
