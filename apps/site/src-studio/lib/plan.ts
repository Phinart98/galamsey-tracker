// The posting calendar: one post every weekday at 13:00 GMT, worked out from the date so it needs no upkeep.
// Monday the town of the week (after the weekly run), Tuesday and Thursday a place in the news (or, with no fresh
// story, the newest clearing and a district), Wednesday a city's water in turn, Friday the football pitches or the
// licence split in turn. Weekends off. The numbers change only on Mondays, so the news days keep the week fresh.
import { sharePosts, type Post } from '../../src/lib/share';

const WATER = ['water-accra', 'water-kumasi', 'water-takoradi', 'water-winneba'];
const FRIDAY = ['rate', 'licence'];
const NEWS_DAYS: Record<number, string> = { 2: 'new', 4: 'district' }; // weekday: the post when there is no fresh story
const NAMES_A_PLACE = new Set(['town', 'district', 'new']);
const FALLBACK_NAME: Record<number, string> = { 2: 'the newest clearing', 4: 'a district spotlight' };
const FRESH_HOURS = 48; // a story older than this is not worth quoting

function isoWeek(d: Date) {
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
  const start = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return Math.ceil(((t.getTime() - start.getTime()) / 864e5 + 1) / 7);
}

// `post` is what to post that day. For a day ahead it is a preview, and `note` says what may still change
export interface Slot { date: string; day: string; post: Post | null; title: string; news: boolean; pitch: boolean; note: string }

// The next `days` days from `from`, one slot per weekday. `stories` are this week's news posts with their dates
export function plan(from: Date, days: number, stories: { date: string; post: Post }[]): Slot[] {
  const bySlug = new Map(sharePosts.map((p) => [p.slug, p]));
  const out: Slot[] = [];
  // The weekly run on the next Monday brings new data, and posts that name a place are picked from it then
  const nextRun = from.getTime() + (((8 - from.getUTCDay()) % 7) || 7) * 864e5;
  const fresh = stories.filter((s) => from.getTime() + 864e5 - Date.parse(s.date) <= FRESH_HOURS * 3600e3);
  for (let i = 0; i < days; i++) {
    const d = new Date(from.getTime() + i * 864e5);
    const wd = d.getUTCDay();
    if (wd === 0 || wd === 6) continue;
    const w = isoWeek(d);
    const slug = wd === 1 ? 'town' : wd === 3 ? WATER[w % WATER.length] : wd === 5 ? FRIDAY[w % FRIDAY.length] : NEWS_DAYS[wd];
    let post = bySlug.get(slug) ?? null;
    let title = post?.title ?? '';
    let news = false;
    if (wd in NEWS_DAYS) {
      if (i === 0 && fresh.length) {
        // Today: the newest story that names a place we cover
        post = fresh[0].post;
        title = `In the news: ${post.title.replace(/^One place: /, '')}`;
        news = true;
      } else if (i > 0) {
        title = `A place in today's news (if there is none: ${FALLBACK_NAME[wd]})`;
        news = true;
      }
    }
    const newWeek = d.getTime() >= nextRun;
    let note = '';
    if (news && i > 0) note = `The studio picks the story that morning. If no story names a place we cover, post ${FALLBACK_NAME[wd]}${newWeek ? ", made from Monday's new data" : ' below'}.`;
    else if (newWeek && post && NAMES_A_PLACE.has(slug)) {
      title = `${post.kind}, picked from Monday's new data`;
      note = 'It is made from the data that arrives on Monday morning, so it shows here from then.';
    } else if (newWeek && i > 0) note = "Shown with this week's numbers. Monday's update may change them a little.";
    if (!post && !news) continue;
    out.push({
      date: d.toISOString().slice(0, 10),
      day: d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' }),
      // Days in a new data week that name a place have nothing to show yet
      post: newWeek && (NAMES_A_PLACE.has(slug)) ? (i === 0 ? post : null) : post,
      note,
      title,
      news,
      // The monthly email goes with the first posting day of each month
      pitch: d.getUTCDate() <= 7 && !out.some((s) => s.date.slice(0, 7) === d.toISOString().slice(0, 7)),
    });
  }
  return out;
}
