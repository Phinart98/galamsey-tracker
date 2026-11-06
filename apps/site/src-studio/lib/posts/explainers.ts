// Explainers: the same words every time, posted rarely, so readers learn how to read the evidence
import { INK, PINK, SIGNAL, explainerPost } from '../designs';
import { SITE, lead, photo, type Post } from './rules';

// A real pair to explain: the town of the week's, or else the largest pictured patch
const example = lead?.place ?? photo[0];

export const explainerPosts: Post[] = [
  {
    slug: 'explain-pictures', kind: 'How to read the pictures', title: 'How to read the pictures',
    alt: 'A before and after satellite pair with four notes on how to read it: green, orange, dark ponds and the ring.',
    text: 'How to read our satellite pictures:\n\nGreen is forest or farmland. Orange and cream is bare ground, where the soil is dug up. Dark ponds on bare ground are water, often in mining pits. The white ring marks the patch we are talking about.\n\nEach picture is about 1.6 km across.',
    reply: `How the pictures are chosen: ${SITE}/method`,
    render: () => explainerPost({ title: 'How to read the pictures', pair: example ? { before: example.chips.before, after: example.chips.after } : undefined, points: [
      { mark: '', markColor: '#2E6B34', head: 'Green', body: 'Forest, farms and bush.' },
      { mark: '', markColor: '#C46A2B', head: 'Orange and cream', body: 'Bare ground, where the soil has been dug up.' },
      { mark: '', markColor: '#1D3A4F', head: 'Dark ponds', body: 'Water, often in mining pits.' },
      { mark: '', head: 'The white ring', body: 'The patch the post is about. Each picture is about 1.6 km across.' },
    ] }),
  },
  {
    slug: 'explain-licence', kind: 'How we check the licence', title: 'How we check the licence',
    alt: 'How each patch is checked against the licence register: no licence, or only a licence to explore, means no licence to mine, which is what galamsey is.',
    text: `For every patch of cleared land, we check the Minerals Commission's public licence register.

No licence at all, or only a licence to explore: there is no licence to mine on that land. Mining without one is what galamsey is.

Those are the only places we post about.`,
    reply: `What each label means: ${SITE}/method#licences`,
    render: () => explainerPost({ title: 'How we check the licence', points: [
      { mark: '', markColor: SIGNAL, head: 'No licence', body: "Nothing on the Minerals Commission's register for this land." },
      { mark: '', markColor: PINK, head: 'Prospecting only', body: 'A licence to search for minerals. It does not allow mining.' },
      { mark: '', markColor: INK, head: 'Galamsey', body: 'Mining without a licence to mine. Both labels above mean there is none.' },
      { mark: '', markColor: '#888', head: 'What we post', body: 'Only land with no licence to mine. We check the register again every week.' },
    ] }),
  },
  {
    slug: 'explain-satellites', kind: 'How satellites see it', title: 'How satellites see it',
    alt: 'Three steps: satellites pass every few days, NASA flags land that lost its cover, we add the licence and pictures.',
    text: 'How the tracker works, in three steps:\n\n1. American and European satellites photograph Ghana every few days.\n2. NASA flags land that has lost its plant cover, and we keep patches of 1 hectare or more in the forest zone.\n3. Every Monday we check each patch against the licence register and pick a clear before and after picture.\n\nNo one has to do it by hand. It runs by itself.',
    reply: `The full method, in plain words: ${SITE}/method`,
    render: () => explainerPost({ title: 'How satellites see it', points: [
      { mark: '1', head: 'Satellites pass every few days', body: 'American Landsat and European Sentinel-2 satellites photograph the same land again and again.' },
      { mark: '2', head: 'NASA flags lost plant cover', body: 'Its land-change data marks where cover is gone. We keep patches of 1 hectare or more in the forest zone.' },
      { mark: '3', head: 'Every Monday, a fresh check', body: 'Each patch is matched to the licence register and gets the clearest before and after picture.' },
      { mark: '4', head: 'No one in the loop', body: 'It runs by itself on free tools, and the method is public.' },
    ] }),
  },
];
