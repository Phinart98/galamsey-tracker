import { active, hasPair, summary } from '../lib/data';
import { chipSrc, noPicture, placeName } from '../lib/format';

// Absolute image links, so the file still works after someone downloads it. `image` holds both pictures, before on
// the left half and after on the right (the data page says so).
const abs = (src: string) => new URL(src, import.meta.env.SITE).href;

export function GET() {
  return new Response(JSON.stringify({
    type: 'FeatureCollection',
    data_date: summary?.data_date ?? null,
    features: active.map((p) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      properties: {
        id: p.id, ha: p.ha, first_seen: p.first_seen, last_seen: p.last_seen, licence: p.licence,
        name: placeName(p), near: p.near, district: p.district,
        ...(p.likely_galamsey && { likely_galamsey: true }),
        ...(!hasPair(p) && { no_picture: noPicture(p) }),
        ...(hasPair(p) && {
          before_date: p.chips.before.date, after_date: p.chips.after.date, image: abs(chipSrc(p.chips.before)),
        }),
      },
    })),
  }), { headers: { 'Content-Type': 'application/geo+json' } });
}
