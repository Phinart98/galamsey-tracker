import { riverCard } from '../../../lib/og';
import { rivers, thumbnail, totals, type River } from '../../../lib/rivers';
import { tileRel } from '../../../lib/pictures.mjs';
import { hectares } from '../../../lib/format';

export function getStaticPaths() {
  return rivers.map((r) => ({ params: { slug: r.slug }, props: { r } }));
}

export async function GET({ props }: { props: { r: River } }) {
  const { r } = props;
  // The stretch with the most cleared land, and the 5 km pieces either side of it
  const t = thumbnail(r);
  const first = Math.max(0, Math.min(t - 1, r.tiles.length - 3));
  const tiles = [first, first + 1, first + 2].filter((i) => i < r.tiles.length).map((i) => tileRel(r.slug, r.version, i));
  const { ha } = totals(r.slug);
  const jpg = await riverCard({
    name: r.name,
    line: `${Math.round(r.river_km)} km to ${r.ends} as satellites saw it, with ${hectares(ha)} cleared within 1 km in the last 12 months.`,
    tiles,
  });
  return new Response(new Uint8Array(jpg), { headers: { 'Content-Type': 'image/jpeg' } });
}
