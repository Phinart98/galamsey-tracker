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

async function download(url: string) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Share card picture failed: ${res.status} ${url}`);
  return Buffer.from(await res.arrayBuffer());
}

// Satori cannot read WebP or AVIF, so each picture is re-encoded as JPEG
async function jpeg(chip: Chip) {
  const rel = chip.files['720.webp'];
  // The weekly run has the pictures on disk even when the site links to them on the pictures site
  const here = [path.join(process.cwd(), 'public', rel), path.join(process.cwd(), '../../pipeline/out', rel)].find((f) => fs.existsSync(f));
  const buf = here ? fs.readFileSync(here) : await download(chipUrl(rel));
  const out = await sharp(buf).jpeg({ quality: 82 }).toBuffer();
  return `data:image/jpeg;base64,${out.toString('base64')}`;
}

// JPEG, not PNG: a card is mostly satellite photo, and as PNG it came to about 700 KB, past what WhatsApp
// will show as a preview (around 300 KB)
async function card(root: Node, width = 1200, height = 630, quality = 80) {
  const svg = await satori(root as never, { width, height, fonts });
  return sharp(new Resvg(svg).render().asPng()).jpeg({ quality, mozjpeg: true }).toBuffer();
}

function shot(src: string, date: string) {
  return h('div', { display: 'flex', position: 'relative', width: 540, height: 400 },
    img(src, { width: 540, height: 400, objectFit: 'cover' }),
    h('div', { position: 'absolute', left: 12, bottom: 12, background: '#000', color: '#fff', fontSize: 26, fontWeight: 700, padding: '4px 12px' }, date));
}

export async function placeCard(o: { title: string; licence: Licence; likely: boolean; before: Chip; after: Chip }) {
  const alarm = o.licence === 'no licence' || o.licence === 'prospecting only';
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

// Portrait images for posting (1080 x 1350, the shape that fills a phone screen on X, Instagram and WhatsApp).
// One look for all of them: paper, black type, the site's magenta for the one number that matters, a black
// footer with the address. Pictures keep their satellite colours and carry the same ring as on the site.
const PW = 1080, PH = 1350, PAD = 64, INNER = PW - PAD * 2;
const INK = '#000', PAPER = '#F5F6F3', SIGNAL = '#B8155A', SIGNAL_DARK = '#FF6FA6';

function footer(dark = false) {
  return h('div', { display: 'flex', width: PW, height: 96, background: dark ? PAPER : INK, color: dark ? INK : '#fff' },
    h('div', { display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: INNER, marginLeft: PAD, fontSize: 30, fontWeight: 700 },
      h('div', {}, 'Galamsey Tracker'), h('div', { fontWeight: 400 }, 'galamseytracker.org')));
}

// White ring with a thin black edge inside and out, hollow so the patch shows through (same as the site).
// Drawn as SVG: satori offsets nested and bordered circles by a pixel or two.
const RING = `data:image/svg+xml;base64,${Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="52" height="52"><circle cx="26" cy="26" r="20" fill="none" stroke="#000" stroke-width="9"/><circle cx="26" cy="26" r="20" fill="none" stroke="#fff" stroke-width="5"/></svg>').toString('base64')}`;
function ring(size: number) {
  return img(RING, { position: 'absolute', left: size / 2 - 26, top: size / 2 - 26, width: 52, height: 52 });
}

async function pairRow(before: Chip, after: Chip, size: number) {
  const one = async (chip: Chip, word: string) => h('div', { display: 'flex', position: 'relative', width: size, height: size },
    img(await jpeg(chip), { width: size, height: size, objectFit: 'cover' }),
    ring(size),
    h('div', { position: 'absolute', left: 0, bottom: 0, display: 'flex', flexDirection: 'column', background: INK, color: '#fff', padding: '8px 14px' },
      h('div', { fontSize: 26, fontWeight: 700 }, word), h('div', { fontSize: 24 }, shortDate(chip.date))));
  return h('div', { display: 'flex', gap: INNER - size * 2 }, await one(before, 'Before'), await one(after, 'After'));
}

function page(children: Node[], dark = false) {
  return h('div', { display: 'flex', flexDirection: 'column', justifyContent: 'space-between', width: PW, height: PH, background: dark ? INK : PAPER, color: dark ? '#fff' : INK, fontFamily: 'Atkinson' },
    h('div', { display: 'flex', flexDirection: 'column', width: INNER, marginLeft: PAD, marginTop: PAD }, ...children),
    footer(dark));
}

// The town with the most cleared land around it, and its largest patch before and after
export async function townPost(o: { headline: string; sub: string; stat: string; note: string; before: Chip; after: Chip }) {
  return card(page([
    h('div', { width: INNER, fontSize: 66, fontWeight: 700, lineHeight: 1.08, letterSpacing: -1 }, o.headline),
    h('div', { width: INNER, fontSize: 34, lineHeight: 1.3, marginTop: 20, marginBottom: 40 }, o.sub),
    await pairRow(o.before, o.after, 468),
    h('div', { width: INNER, fontSize: 60, fontWeight: 700, color: SIGNAL, marginTop: 36, letterSpacing: -1 }, o.stat),
    h('div', { width: INNER, fontSize: 32, lineHeight: 1.35, marginTop: 14 }, o.note),
  ]), PW, PH, 85);
}

// A city's water: the hectares cleared on the land that drains to its treatment plant
export async function waterPost(o: { top: string; big: string; line: string; note: string; before?: Chip; after?: Chip }) {
  const pics = o.before && o.after ? [await pairRow(o.before, o.after, 468), h('div', { width: INNER, fontSize: 28, lineHeight: 1.3, marginTop: 16, color: '#333' }, o.note)] : [];
  return card(page([
    h('div', { width: INNER, fontSize: 38, fontWeight: 700 }, o.top),
    h('div', { width: INNER, fontSize: 170, fontWeight: 700, lineHeight: 1, letterSpacing: -4, color: SIGNAL, marginTop: 24 }, o.big),
    h('div', { width: INNER, fontSize: 40, lineHeight: 1.25, marginTop: 20, marginBottom: 40 }, o.line),
    ...pics,
  ]), PW, PH, 85);
}

// The average rate, said as football pitches an hour
export async function ratePost(o: { top: string; big: string; line: string; sub: string }) {
  return card(page([
    h('div', { width: INNER, fontSize: 38, fontWeight: 700 }, o.top),
    h('div', { width: INNER, fontSize: 440, fontWeight: 700, lineHeight: 1, letterSpacing: -12, color: SIGNAL_DARK, marginTop: 60 }, o.big),
    h('div', { width: INNER, fontSize: 84, fontWeight: 700, lineHeight: 1.05, letterSpacing: -1, marginTop: 10 }, o.line),
    h('div', { width: INNER, fontSize: 34, lineHeight: 1.35, marginTop: 48, color: '#DDD' }, o.sub),
  ], true), PW, PH, 85);
}
