import { sharePosts } from '../../lib/share';

// One portrait image per post, for the hidden /share page
export function getStaticPaths() {
  return sharePosts.map((p) => ({ params: { slug: p.slug } }));
}

export async function GET({ params }: { params: { slug: string } }) {
  const post = sharePosts.find((p) => p.slug === params.slug)!;
  return new Response(new Uint8Array(await post.render()), { headers: { 'Content-Type': 'image/jpeg' } });
}
