// Share cards for the public site (1200 x 630), drawn at build time so WhatsApp and X previews show the evidence
// itself. The drawing helpers here (h, img, jpeg, card) are also used by the studio's posts (src-studio/lib/designs.ts).
import fs from 'node:fs';
import path from 'node:path';
import { Resvg } from '@resvg/resvg-js';
import satori from 'satori';
import sharp from 'sharp';
import type { Chip, Licence } from './data';
import { LICENCE_SHORT, chipUrl, halfOf, noLicenceToMine, pairOf, shortDate } from './format';

const FONTS = path.join(process.cwd(), 'node_modules/@fontsource/atkinson-hyperlegible-next/files');
const fonts = [400, 700].map((weight) => ({
  name: 'Atkinson', weight: weight as 400 | 700, style: 'normal' as const,
  data: fs.readFileSync(path.join(FONTS, `atkinson-hyperlegible-next-latin-${weight}-normal.woff`)),
}));

// satori takes a React-like tree: h() makes an element with an inline style, img() a picture
export type Node = { type: string; props: Record<string, unknown> };
export const h = (type: string, style: Record<string, unknown>, ...children: (Node | string)[]): Node =>
  ({ type, props: { style, children } });
export const img = (src: string, style: Record<string, unknown>): Node => ({ type: 'img', props: { src, style } });

async function download(url: string) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Share card picture failed: ${res.status} ${url}`);
  return Buffer.from(await res.arrayBuffer());
}

// A file of the pictures site, from wherever it is: pipeline/out (the weekly run restores it, as does a local copy),
// public/ (a local build copies it there), else downloaded from the pictures site
async function pictureFile(rel: string) {
  const local = [path.join(process.cwd(), '../../pipeline/out', rel), path.join(process.cwd(), 'public', rel)].find((f) => fs.existsSync(f));
  return local ? fs.readFileSync(local) : download(chipUrl(rel));
}

// JPEG as a data URI: satori cannot read WebP or AVIF
export async function jpegUri(img: ReturnType<typeof sharp>, quality = 82) {
  return `data:image/jpeg;base64,${(await img.jpeg({ quality }).toBuffer()).toString('base64')}`;
}

// One side of a place's pictures: the single file when it is on disk, else that half of the published pair
// (lib/format.ts chipSrc)
async function picture(chip: Chip) {
  const rel = chip.files['720.webp'];
  const single = path.join(process.cwd(), '../../pipeline/out', rel);
  if (fs.existsSync(single)) return fs.readFileSync(single);
  const pair = await pictureFile(pairOf(chip));
  const side = 720;
  return sharp(pair).extract({ left: halfOf(chip) === 'before' ? 0 : side, top: 0, width: side, height: side }).toBuffer();
}

export async function jpeg(chip: Chip) {
  return jpegUri(sharp(await picture(chip)));
}

// JPEG, not PNG: a card is mostly satellite photo, and as PNG it came to about 700 KB, past what WhatsApp
// will show as a preview (around 300 KB)
export async function card(root: Node, width = 1200, height = 630, quality = 80) {
  const svg = await satori(root as never, { width, height, fonts });
  return sharp(new Resvg(svg).render().asPng()).jpeg({ quality, mozjpeg: true }).toBuffer();
}

function shot(src: string, date: string) {
  return h('div', { display: 'flex', position: 'relative', width: 540, height: 400 },
    img(src, { width: 540, height: 400, objectFit: 'cover' }),
    h('div', { position: 'absolute', left: 12, bottom: 12, background: '#000', color: '#fff', fontSize: 26, fontWeight: 700, padding: '4px 12px' }, date));
}

export async function placeCard(o: { title: string; licence: Licence; likely: boolean; before: Chip; after: Chip }) {
  const alarm = noLicenceToMine(o.licence);
  return card(h('div', { display: 'flex', flexDirection: 'column', width: 1200, height: 630, background: '#F5F6F3', color: '#000', fontFamily: 'Atkinson', padding: 40 },
    h('div', { display: 'flex', gap: 40 }, shot(await jpeg(o.before), shortDate(o.before.date)), shot(await jpeg(o.after), shortDate(o.after.date))),
    h('div', { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: 28, width: 1120 },
      h('div', { display: 'flex', flexDirection: 'column', gap: 12, width: 840 },
        h('div', { fontSize: 38, fontWeight: 700, lineHeight: 1.15 }, o.title),
        h('div', { display: 'flex', gap: 12 },
          h('div', alarm ? { background: '#B8155A', color: '#fff', fontSize: 24, fontWeight: 700, padding: '2px 12px' }
                         : { border: '2px solid #000', fontSize: 24, fontWeight: 700, padding: '0 10px' }, LICENCE_SHORT[o.licence]),
          ...(o.likely ? [h('div', { background: '#000', color: '#fff', fontSize: 24, fontWeight: 700, padding: '2px 12px' }, 'Likely galamsey')] : []))),
      h('div', { fontSize: 26, fontWeight: 700, flexShrink: 0 }, 'Galamsey Tracker'))));
}

export async function homeCard(o: { line: string; sub: string; before?: Chip; after?: Chip }) {
  const pics = o.before && o.after
    ? [h('div', { display: 'flex', flexDirection: 'column', gap: 10, flexShrink: 0 },
        img(await jpeg(o.before), { width: 270, height: 270, objectFit: 'cover' }),
        img(await jpeg(o.after), { width: 270, height: 270, objectFit: 'cover' }))]
    : [];
  return card(h('div', { display: 'flex', width: 1200, height: 630, background: '#F5F6F3', color: '#000', fontFamily: 'Atkinson', padding: 40, gap: 48 },
    h('div', { display: 'flex', flexDirection: 'column', justifyContent: 'space-between', width: pics.length ? 802 : 1120, height: 550 },
      h('div', { fontSize: 30, fontWeight: 700 }, 'Galamsey Tracker'),
      h('div', { display: 'flex', flexDirection: 'column', gap: 20 },
        h('div', { fontSize: 52, fontWeight: 700, lineHeight: 1.1, letterSpacing: -1 }, o.line),
        h('div', { fontSize: 30, lineHeight: 1.3 }, o.sub))),
    ...pics));
}

// One 5 km tile of a river walk, as a file and as JPEG
export const riverTileFile = pictureFile;
export const riverTile = async (rel: string) => jpegUri(sharp(await pictureFile(rel)));

// A river walk's card: three 5 km pieces of the picture side by side, beside the river's name
export async function riverCard(o: { name: string; line: string; tiles: string[] }) {
  const pics = await Promise.all(o.tiles.map(riverTile));
  return card(h('div', { display: 'flex', width: 1200, height: 630, background: '#F5F6F3', color: '#000', fontFamily: 'Atkinson', padding: 40, gap: 48 },
    h('div', { display: 'flex', flexDirection: 'column', justifyContent: 'space-between', width: 600, height: 550 },
      h('div', { fontSize: 30, fontWeight: 700 }, 'Galamsey Tracker'),
      h('div', { display: 'flex', flexDirection: 'column', gap: 20 },
        h('div', { fontSize: 64, fontWeight: 700, lineHeight: 1.05, letterSpacing: -1 }, `Follow the ${o.name}`),
        h('div', { fontSize: 30, lineHeight: 1.3 }, o.line))),
    h('div', { display: 'flex', gap: 8 }, ...pics.map((src) => img(src, { width: 160, height: 550, objectFit: 'cover', objectPosition: 'center top' })))));
}
