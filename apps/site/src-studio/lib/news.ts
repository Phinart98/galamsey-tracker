// This week's galamsey news, read when the studio is built (every day by .github/workflows/studio.yml).
// Two free feeds with no key: Google News search (covers Citi, GNA, GhanaWeb, Graphic and others, which have no
// working feed of their own) and MyJoyOnline's galamsey tag. Headlines that name a town or district we cover get
// a ready "One place" post of that town's largest pictured patch. If a feed fails, the studio still builds.
import { active, hasPair, placeById, towns } from '../../src/lib/data';
import { tidyDistrict } from '../../src/lib/format';
import { newsPlacePost, type Post } from '../../src/lib/share';

const FEEDS = [
  'https://news.google.com/rss/search?q=galamsey+when:7d&hl=en-GH&gl=GH&ceid=GH:en',
  'https://www.myjoyonline.com/tag/galamsey/feed/',
];
const DAYS = 7;
// Feeds that do not name themselves per item
const OUTLET: Record<string, string> = { 'www.myjoyonline.com': 'MyJoyOnline' };
const MAX_POSTS = 4;
const SHOW = 25; // stories listed, plus any older one that names a place
// Town names that are also everyday words or regions in news copy
const SKIP = new Set(['Ghana', 'Gold', 'Central', 'Western', 'Eastern', 'Ashanti', 'Mining', 'River', 'Forest', 'Police', 'Army', 'Station', 'Junction', 'Camp', 'Asafo',
  // also people's names, foreign places or words common in news copy
  'James', 'Baku', 'Tete', 'Pano', 'Kwahu', 'Bank', 'Market', 'Church', 'School', 'Town', 'Village', 'Lake', 'Hill', 'Mile', 'Zongo', 'Ahenkro', 'Krom', 'Fante', 'Akim', 'Wassa', 'Denkyira', 'Adansi', 'Amansie', 'Atwima', 'Sefwi']);

export interface NewsItem { title: string; link: string; source: string; date: string; match?: { name: string; post: Post } }

const text = (xml: string, tag: string) => {
  const m = xml.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`));
  return m ? m[1].replace(/<!\[CDATA\[|\]\]>/g, '').replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&#0?39;|&apos;|&#8217;/g, "'").replace(/&quot;|&#8220;|&#8221;/g, '"').replace(/&nbsp;|&#160;/g, ' ').replace(/\s+/g, ' ').trim() : '';
};

async function read(url: string) {
  try {
    const res = await fetch(url, { headers: { 'User-Agent': 'galamsey-tracker-studio' }, signal: AbortSignal.timeout(15000) });
    if (!res.ok) return [];
    const xml = await res.text();
    return [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)].map(([, item]) => {
      // Google News titles end with " - Outlet"
      const raw = text(item, 'title');
      const source = text(item, 'source') || OUTLET[new URL(url).hostname] || new URL(url).hostname.replace(/^www\./, '');
      const title = raw.endsWith(` - ${source}`) ? raw.slice(0, -(source.length + 3)) : raw;
      // An item without a readable date is left out on its own, so it cannot drop the rest of the feed
      const when = Date.parse(text(item, 'pubDate'));
      return Number.isNaN(when) ? null : { title, link: text(item, 'link'), source, date: new Date(when).toISOString(), about: `${title} ${text(item, 'description')}` };
    }).filter((i) => i !== null);
  } catch {
    return [];
  }
}

// Towns first (largest cleared land first), then districts
// Galamsey only: the picture is the largest patch near the town with no licence to mine on the register
const galamsey = (p: { licence: string }) => p.licence === 'no licence' || p.licence === 'prospecting only';
const pictured = (ids: string[]) => ids.map((id) => placeById.get(id)).filter((p) => p && p.active && galamsey(p) && hasPair(p)).sort((a, b) => b!.ha - a!.ha)[0];
const nameCount = towns.reduce((m, t) => m.set(t.name, (m.get(t.name) ?? 0) + 1), new Map<string, number>());
const named: { name: string; label: string; district: string | null; place: ReturnType<typeof pictured>; shared?: boolean }[] = [
  // A name shared by several towns only counts when the story also names the town's district
  ...towns.filter((t) => t.name.length >= 4 && !SKIP.has(t.name)).map((t) => ({ name: t.name, label: t.name, district: t.district, place: pictured(t.ids), shared: (nameCount.get(t.name) ?? 0) > 1 })),
  // A district in the news: its largest pictured patch, named by the town nearest to it
  ...[...new Set(active.map((p) => p.district).filter(Boolean) as string[])].map((d) => {
    const place = active.find((p) => p.district === d && galamsey(p) && hasPair(p));
    return { name: tidyDistrict(d), label: place?.near ?? tidyDistrict(d), district: d, place };
  }),
].filter((n) => n.place);
const pattern = (name: string) => new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`);

async function load(): Promise<NewsItem[]> {
  const since = Date.now() - DAYS * 864e5;
  const seen = new Set<string>();
  const items = (await Promise.all(FEEDS.map(read))).flat()
    // Feeds are outside data: keep only web links, so a bad feed cannot put a script link on the page
    .filter((i) => i.title && /^https?:\/\//i.test(i.link) && Date.parse(i.date) >= since)
    .sort((a, b) => b.date.localeCompare(a.date))
    .filter((i) => {
      const key = i.title.toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 60);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  let made = 0;
  const used = new Set<string>();
  return items.map(({ about, ...i }) => {
    const hit = made < MAX_POSTS ? named.find((n) => !used.has(n.place!.id) && pattern(n.name).test(about) && (!n.shared || (!!n.district && pattern(tidyDistrict(n.district)).test(about)))) : undefined;
    if (!hit || !hit.place || !hasPair(hit.place)) return i;
    used.add(hit.place.id);
    made++;
    return { ...i, match: { name: hit.name, post: newsPlacePost(i, hit.name, hit.label, hit.district, hit.place as never, `news-${made}`) } };
  }).filter((n: NewsItem, i) => i < SHOW || n.match);
}

export const news = await load();
export const newsPosts = news.flatMap((n) => (n.match ? [n.match.post] : []));
