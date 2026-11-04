import { sharePosts } from '../../src/lib/share';
import { newsPosts } from '../lib/news';

const all = [...sharePosts, ...newsPosts];

// One portrait image per post
export function getStaticPaths() {
  return all.map((p) => ({ params: { slug: p.slug } }));
}

export async function GET({ params }: { params: { slug: string } }) {
  const post = all.find((p) => p.slug === params.slug)!;
  return new Response(new Uint8Array(await post.render()), { headers: { 'Content-Type': 'image/jpeg' } });
}
