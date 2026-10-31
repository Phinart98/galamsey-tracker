import { bulletins, places } from '../lib/data';

// Every page search engines should find, in the same form as the canonical links (with the trailing slash).
// The map builds its list in the browser, so without this file crawlers would miss most place pages.
// Merged places only redirect, so they are left out. One file holds up to 50,000 links.
export function GET() {
  const paths = [
    '/', '/map/', '/method/', '/data/', '/about/',
    ...bulletins.map((b) => `/bulletins/${b.month}/`),
    ...places.map((p) => `/places/${p.id}/`),
  ];
  const urls = paths.map((p) => `<url><loc>${new URL(p, import.meta.env.SITE).href}</loc></url>`).join('\n');
  return new Response(
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`,
    { headers: { 'Content-Type': 'application/xml' } },
  );
}
