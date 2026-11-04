// The posting calendar: one post every weekday at 13:00 GMT, worked out from the date so it needs no upkeep.
// Monday the town of the week (after the weekly run), Tuesday and Thursday a place in the news (or, with no fresh
// story, the newest clearing and a district), Wednesday a city's water in turn, Friday the football pitches or the
// licence split in turn. Weekends off. The numbers change only on Mondays, so the news days keep the week fresh.
import { sharePosts, type Post } from '../../src/lib/share';

const WATER = ['water-accra', 'water-kumasi', 'water-takoradi', 'water-winneba'];
const FRIDAY = ['rate', 'licence'];
const BACKUP: Record<number, string> = { 2: 'new', 4: 'district' }; // news days: the post when no story fits
const BACKUP_NAME: Record<number, string> = { 2: 'the newest clearing', 4: 'a district spotlight' };
const NAMES_A_PLACE = new Set(['town', 'district', 'new']);
const FRESH_HOURS = 48; // a story older than this is not worth quoting
const DAY = 864e5;

function isoWeek(d: Date) {
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
  const start = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return Math.ceil(((t.getTime() - start.getTime()) / DAY + 1) / 7);
}

// True for the first Monday-to-Friday day of its month: the day of the monthly email
function firstWeekday(d: Date) {
  let x = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1));
  while (x.getUTCDay() === 0 || x.getUTCDay() === 6) x = new Date(x.getTime() + DAY);
  return x.getTime() === d.getTime();
}

export interface Story { date: string; title: string; link: string; source: string; post: Post }
export interface Slot {
  date: string;
  day: string;
  status: 'done' | 'today' | 'ahead';
  title: string;
  post: Post | null; // what to post; null when it is made from data that has not arrived yet
  story: Story | null; // on a news day: the story to quote
  note: string; // what may still change, in one sentence
  email: boolean;
}

export const mondayOf = (d: Date) => new Date(d.getTime() - ((d.getUTCDay() + 6) % 7) * DAY);

// The five weekdays from `monday`, seen from `today` (both at 00:00 UTC). `stories` are news posts, newest first
export function week(monday: Date, today: Date, stories: Story[]): Slot[] {
  const bySlug = new Map(sharePosts.map((p) => [p.slug, p]));
  // The weekly run on the next Monday brings new data. Posts that name a place are made from it then
  const nextRun = today.getTime() + (((8 - today.getUTCDay()) % 7) || 7) * DAY;
  const fresh = stories.filter((s) => today.getTime() + DAY - Date.parse(s.date) <= FRESH_HOURS * 3600e3);
  return [0, 1, 2, 3, 4].map((i): Slot => {
    const d = new Date(monday.getTime() + i * DAY);
    const wd = d.getUTCDay();
    const status = d.getTime() < today.getTime() ? 'done' : d.getTime() === today.getTime() ? 'today' : 'ahead';
    const w = isoWeek(d);
    const slug = wd === 1 ? 'town' : wd === 3 ? WATER[w % WATER.length] : wd === 5 ? FRIDAY[w % FRIDAY.length] : BACKUP[wd];
    const newData = d.getTime() >= nextRun;
    const known = bySlug.get(slug);
    let post = newData && NAMES_A_PLACE.has(slug) ? null : known ?? null;
    let title = post?.title ?? `${known?.kind ?? 'Post'}, made from Monday's new data`;
    let story: Story | null = null;
    let note = '';
    if (wd in BACKUP) {
      title = `A place in the news, or ${BACKUP_NAME[wd]}`;
      if (status === 'today' && fresh.length) {
        story = fresh[0];
        post = story.post;
        title = `In the news: ${post.title.replace(/^One place: /, '')}`;
      } else if (status === 'today') {
        note = `No story from the last two days names a place we cover, so post ${BACKUP_NAME[wd]}.`;
      } else if (status === 'ahead') {
        note = `Decided that morning from the news. If no story names a place we cover, post ${BACKUP_NAME[wd]}${post ? ', shown here' : ", made from Monday's new data"}.`;
      }
    } else if (!post) {
      note = 'It is made from the data that arrives on Monday morning, so it shows here from then.';
    } else if (newData) {
      note = "Shown with this week's numbers. Monday's update may change them a little.";
    }
    // A past day only says what kind of post it was: the rotation has moved on, so its name could be wrong
    if (status === 'done') { title = wd in BACKUP ? `A place in the news, or ${BACKUP_NAME[wd]}` : known?.kind ?? title; post = null; note = ''; story = null; }
    return {
      date: d.toISOString().slice(0, 10),
      day: d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' }),
      status, title, post, story, note,
      email: firstWeekday(d),
    };
  });
}
