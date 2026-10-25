import { active, hasPair } from '../lib/data';
import { chipUrl, noPicture, placeName } from '../lib/format';

// Absolute image links, so the file still works after someone downloads it
const abs = (rel: string) => new URL(chipUrl(rel), import.meta.env.SITE).href;

export function GET() {
  return new Response(JSON.stringify({
    type: 'FeatureCollection',
    features: active.map((p) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      properties: {
        id: p.id, ha: p.ha, first_seen: p.first_seen, last_seen: p.last_seen, licence: p.licence,
        name: placeName(p), near: p.near, district: p.district,
        ...(!hasPair(p) && { no_picture: noPicture(p) }),
        ...(hasPair(p) && {
          before_date: p.chips.before.date, before_image: abs(p.chips.before.files['360.webp']),
          after_date: p.chips.after.date, after_image: abs(p.chips.after.files['360.webp']),
        }),
      },
    })),
  }), { headers: { 'Content-Type': 'application/geo+json' } });
}
