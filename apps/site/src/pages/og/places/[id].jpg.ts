import { carded } from '../../../lib/data';
import { placeCard } from '../../../lib/og';
import { hectares, placeName } from '../../../lib/format';

export function getStaticPaths() {
  return carded.map((place) => ({ params: { id: place.id }, props: { place } }));
}

export async function GET({ props }: { props: { place: (typeof carded)[number] } }) {
  const p = props.place;
  const card = await placeCard({ title: `${hectares(p.ha)} cleared ${placeName(p)}`, licence: p.licence, likely: !!p.likely_galamsey, before: p.chips.before, after: p.chips.after });
  return new Response(new Uint8Array(card), { headers: { 'Content-Type': 'image/jpeg' } });
}
