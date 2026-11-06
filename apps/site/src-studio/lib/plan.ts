// The posting calendar: one post every weekday at 13:00 GMT, worked out from the date so it needs no upkeep.
// Monday the town of the week (after the weekly run). Tuesday and Thursday a place in the news, or else the next
// kind from the PLACE list. Wednesday a city's water in turn. Friday the next kind from the NUMBERS list, and on the
// first Friday of a month the month in review. Weekends off. Each list moves on a step a week, so a kind returns
// only after the whole list has gone round (PLACE every 3 weeks, NUMBERS every 11).
import { status as runs } from '../../src/lib/data';
import { sharePosts, type Post } from './posts';

const WATER = ['water-accra', 'water-kumasi', 'water-takoradi', 'water-winneba', 'plants'];
const PLACE = ['new', 'shape', 'find', 'explore', 'sheet', 'towns'];
const NUMBERS = ['rate', 'licence', 'districts', 'explain-pictures', 'sizes', 'map', 'district', 'water-test', 'plate', 'explain-licence', 'explain-satellites'];
const NEWS_DAYS = new Set([2, 4]);
// Kinds whose picture or numbers name a place: made from Monday's data, so not shown before it arrives
const NAMES_A_PLACE = new Set(['town', 'district', 'month', 'explain-pictures', 'water-test', 'plate', ...WATER.filter((k) => k !== 'plants'), ...PLACE]);
const EPOCH = Date.UTC(2026, 0, 5); // a Monday: weeks are counted from here, so the lists never restart in January
const FRESH_HOURS = 48; // a story older than this is not worth quoting
const DAY = 864e5;

const weekNo = (d: Date) => Math.floor((d.getTime() - EPOCH) / (7 * DAY));

// The kind at this step of a list, skipping any the data could not make this week
function fromList(list: string[], step: number, have: Set<string>, not = '') {
  for (let k = 0; k < list.length; k++) {
    const slug = list[(((step + k) % list.length) + list.length) % list.length];
    if (have.has(slug) && slug !== not) return slug;
  }
  return list[0];
}
const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);

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

// GitHub sometimes starts the Monday run hours late (9 hours on 2 November 2026)
const ranToday = (d: Date) => String(runs.weekly?.last_success ?? '').slice(0, 10) === d.toISOString().slice(0, 10);

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
    const w = weekNo(d);
    const have = new Set(bySlug.keys());
    const tuesday = fromList(PLACE, 2 * w, have);
    const firstFriday = wd === 5 && d.getUTCDate() <= 7;
    const slug = wd === 1 ? 'town'
      : wd === 2 ? tuesday
      : wd === 3 ? fromList(WATER, w, have)
      : wd === 4 ? fromList(PLACE, 2 * w + 1, have, tuesday)
      : firstFriday && have.has('month') ? 'month' : fromList(NUMBERS, w, have);
    const newData = d.getTime() >= nextRun;
    const known = bySlug.get(slug);
    const backupName = known ? lower(known.kind) : 'another post';
    let post = newData && NAMES_A_PLACE.has(slug) ? null : known ?? null;
    let title = post?.title ?? (known ? `${known.kind}, made from Monday's new data` : 'Nothing ready for this day');
    let story: Story | null = null;
    let note = '';
    if (NEWS_DAYS.has(wd)) {
      title = `A place in the news, or ${backupName}`;
      if (status === 'today' && fresh.length) {
        story = fresh[0];
        post = story.post;
        title = post.title; // 'In the news: <place>'
      } else if (status === 'today') {
        note = `No story from the last two days names a place we cover, so post ${backupName}.`;
      } else if (status === 'ahead') {
        note = `Decided that morning from the news. If no story names a place we cover, post ${backupName}${post ? ', shown here' : ", made from Monday's new data"}.`;
      }
    } else if (wd === 1 && status === 'today' && !ranToday(d)) {
      note = "The weekly update has not finished yet, so this is last week's town. Check again after it runs, or post another day's kind.";
    } else if (!known) {
      note = "This week's data could not make this kind of post. Use any post from another day, or skip the day.";
    } else if (!post) {
      note = 'It is made from the data that arrives on Monday morning, so it shows here from then.';
    } else if (newData) {
      note = "Shown with this week's numbers. Monday's update may change them a little.";
    }
    // A past day only says what kind of post it was: the rotation has moved on, so its name could be wrong
    if (status === 'done') { title = NEWS_DAYS.has(wd) ? `A place in the news, or ${backupName}` : known?.kind ?? title; post = null; note = ''; story = null; }
    return {
      date: d.toISOString().slice(0, 10),
      day: d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC' }),
      status, title, post, story, note,
      email: firstWeekday(d),
    };
  });
}
