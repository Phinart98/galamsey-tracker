// Share cards (1200 x 630), drawn at build time so WhatsApp and X previews show the evidence itself.
import fs from 'node:fs';
import path from 'node:path';
import { Resvg } from '@resvg/resvg-js';
import satori from 'satori';
import sharp from 'sharp';
import type { Chip, Licence } from './data';
import { LICENCE_SHORT, chipUrl, shortDate } from './format';

const FONTS = path.join(process.cwd(), 'node_modules/@fontsource/atkinson-hyperlegible-next/files');
const fonts = [400, 700].map((weight) => ({
  name: 'Atkinson', weight: weight as 400 | 700, style: 'normal' as const,
  data: fs.readFileSync(path.join(FONTS, `atkinson-hyperlegible-next-latin-${weight}-normal.woff`)),
}));

type Node = { type: string; props: Record<string, unknown> };
const h = (type: string, style: Record<string, unknown>, ...children: (Node | string)[]): Node =>
  ({ type, props: { style, children } });
const img = (src: string, style: Record<string, unknown>): Node => ({ type: 'img', props: { src, style } });

// Satori cannot read WebP or AVIF, so each picture is re-encoded as JPEG
async function jpeg(chip: Chip) {
  const rel = chip.files['720.webp'];
  const url = chipUrl(rel);
  const buf = url.startsWith('http')
    ? Buffer.from(await (await fetch(url)).arrayBuffer())
    : fs.readFileSync(path.join(process.cwd(), 'public', rel));
  const out = await sharp(buf).jpeg({ quality: 82 }).toBuffer();
  return `data:image/jpeg;base64,${out.toString('base64')}`;
}

async function png(root: Node) {
  const svg = await satori(root as never, { width: 1200, height: 630, fonts });
  return new Resvg(svg).render().asPng();
}

function shot(src: string, date: string) {
  return h('div', { display: 'flex', position: 'relative', width: 540, height: 400 },
    img(src, { width: 540, height: 400, objectFit: 'cover' }),
    h('div', { position: 'absolute', left: 12, bottom: 12, background: '#000', color: '#fff', fontSize: 26, fontWeight: 700, padding: '4px 12px' }, date));
}

export async function placeCard(o: { title: string; licence: Licence; before: Chip; after: Chip }) {
  const alarm = o.licence === 'no licence' || o.licence === 'prospecting only';
  return png(h('div', { display: 'flex', flexDirection: 'column', width: 1200, height: 630, background: '#F5F6F3', color: '#000', fontFamily: 'Atkinson', padding: 40 },
    h('div', { display: 'flex', gap: 40 }, shot(await jpeg(o.before), shortDate(o.before.date)), shot(await jpeg(o.after), shortDate(o.after.date))),
    h('div', { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: 28, width: 1120 },
      h('div', { display: 'flex', flexDirection: 'column', gap: 12, width: 840 },
        h('div', { fontSize: 38, fontWeight: 700, lineHeight: 1.15 }, o.title),
        h('div', { display: 'flex' },
          h('div', alarm ? { background: '#B8155A', color: '#fff', fontSize: 24, fontWeight: 700, padding: '2px 12px' }
                         : { border: '2px solid #000', fontSize: 24, fontWeight: 700, padding: '0 10px' }, LICENCE_SHORT[o.licence]))),
      h('div', { fontSize: 26, fontWeight: 700, flexShrink: 0 }, 'Galamsey Tracker'))));
}

export async function homeCard(o: { line: string; sub: string; before?: Chip; after?: Chip }) {
  const pics = o.before && o.after
    ? [h('div', { display: 'flex', flexDirection: 'column', gap: 10, flexShrink: 0 },
        img(await jpeg(o.before), { width: 270, height: 270, objectFit: 'cover' }),
        img(await jpeg(o.after), { width: 270, height: 270, objectFit: 'cover' }))]
    : [];
  return png(h('div', { display: 'flex', width: 1200, height: 630, background: '#F5F6F3', color: '#000', fontFamily: 'Atkinson', padding: 40, gap: 48 },
    h('div', { display: 'flex', flexDirection: 'column', justifyContent: 'space-between', width: pics.length ? 802 : 1120, height: 550 },
      h('div', { fontSize: 30, fontWeight: 700 }, 'Galamsey Tracker'),
      h('div', { display: 'flex', flexDirection: 'column', gap: 20 },
        h('div', { fontSize: 52, fontWeight: 700, lineHeight: 1.1, letterSpacing: -1 }, o.line),
        h('div', { fontSize: 30, lineHeight: 1.3 }, o.sub))),
    ...pics));
}
