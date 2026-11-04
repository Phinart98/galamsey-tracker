// The posting calendar: which post goes out on which day, worked out from the date so it needs no upkeep.
// Monday the town of the week (after the weekly run), Wednesday a city's water in turn, Friday one of the other
// kinds in turn (new clearing, district, rate, licence), so no Friday kind repeats within four weeks. News about a place we cover beats the plan on any day.
import { sharePosts } from '../../src/lib/share';

const WATER = ['water-accra', 'water-kumasi', 'water-takoradi', 'water-winneba'];
const FRIDAY = ['new', 'district', 'rate', 'licence'];

function isoWeek(d: Date) {
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
  const start = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return Math.ceil(((t.getTime() - start.getTime()) / 864e5 + 1) / 7);
}

export interface Slot { date: string; day: string; slug: string; title: string; pitch: boolean }

// The next `days` days from `from`, with the post planned for each Monday, Wednesday and Friday
export function plan(from: Date, days = 14): Slot[] {
  const have = new Set(sharePosts.map((p) => p.slug));
  const out: Slot[] = [];
  for (let i = 0; i < days; i++) {
    const d = new Date(from.getTime() + i * 864e5);
    const wd = d.getUTCDay();
    const w = isoWeek(d);
    let slug: string | null = null;
    if (wd === 1) slug = 'town';
    if (wd === 3) slug = WATER[w % WATER.length];
    if (wd === 5) slug = FRIDAY[w % FRIDAY.length];
    if (!slug || !have.has(slug)) continue;
    const post = sharePosts.find((p) => p.slug === slug)!;
    out.push({
      date: d.toISOString().slice(0, 10),
      day: d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' }),
      slug, title: post.title,
      // A pitch email on the first posting day of each month
      pitch: d.getUTCDate() <= 7 && !out.some((s) => s.date.slice(0, 7) === d.toISOString().slice(0, 7)),
    });
  }
  return out;
}
