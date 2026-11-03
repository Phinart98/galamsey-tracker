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
// Design (2026-11-03, second pass): the satellite picture is the headline, so the town image runs edge to edge;
// the water image follows the mud from a cleared patch down the river to the reader's tap; the rate image draws
// one day's clearing as football pitches you can count. Site colours, plus river blue for water.
const PW = 1080, PH = 1350, PAD = 64, INNER = PW - PAD * 2;
const INK = '#000', PAPER = '#F5F6F3', SIGNAL = '#B8155A', PINK = '#FF6FA6', RIVER = '#1D5C8C';
const svgUri = (svg: string) => `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;

// White ring with a thin black edge, hollow so the patch shows through (same as the site). SVG, because satori
// offsets nested bordered circles by a pixel or two.
const ring = (d: number) => svgUri(`<svg xmlns="http://www.w3.org/2000/svg" width="${d}" height="${d}"><circle cx="${d / 2}" cy="${d / 2}" r="${d * 0.38}" fill="none" stroke="#000" stroke-width="${d * 0.17}"/><circle cx="${d / 2}" cy="${d / 2}" r="${d * 0.38}" fill="none" stroke="#fff" stroke-width="${d * 0.1}"/></svg>`);
const PITCH = svgUri('<svg xmlns="http://www.w3.org/2000/svg" width="84" height="56"><rect width="84" height="56" fill="#FF6FA6"/><rect x="3" y="3" width="78" height="50" fill="none" stroke="#000" stroke-width="2"/><line x1="42" y1="3" x2="42" y2="53" stroke="#000" stroke-width="2"/><circle cx="42" cy="28" r="9" fill="none" stroke="#000" stroke-width="2"/><rect x="3" y="16" width="10" height="24" fill="none" stroke="#000" stroke-width="2"/><rect x="71" y="16" width="10" height="24" fill="none" stroke="#000" stroke-width="2"/></svg>');

function brandRow(color: string, muted: string) {
  return h('div', { display: 'flex', justifyContent: 'space-between', width: INNER, fontSize: 28 },
    h('div', { fontWeight: 700, color }, 'Galamsey Tracker'), h('div', { color: muted }, 'galamseytracker.org'));
}

// The town with the most cleared land around it: the after picture edge to edge, the before small in a corner
export async function townPost(o: { headline: string; sub: string; before: Chip; after: Chip }) {
  const IMG = 1000, INSET = 300;
  return card(h('div', { display: 'flex', flexDirection: 'column', width: PW, height: PH, background: INK, fontFamily: 'Atkinson', color: '#fff' },
    h('div', { display: 'flex', position: 'relative', width: PW, height: IMG, overflow: 'hidden' },
      img(await jpeg(o.after), { position: 'absolute', left: 0, top: -(PW - IMG) / 2, width: PW, height: PW }),
      img(ring(64), { position: 'absolute', left: PW / 2 - 32, top: IMG / 2 - 32, width: 64, height: 64 }),
      h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: 40, top: 40, border: '6px solid #fff', background: '#fff' },
        img(await jpeg(o.before), { width: INSET, height: INSET }),
        h('div', { fontSize: 24, fontWeight: 700, color: INK, padding: '8px 10px 4px' }, `Before, ${shortDate(o.before.date)}`)),
      h('div', { position: 'absolute', left: 40, bottom: 32, background: INK, fontSize: 26, fontWeight: 700, padding: '6px 14px' }, `After, ${shortDate(o.after.date)}`)),
    h('div', { display: 'flex', flexDirection: 'column', justifyContent: 'space-between', width: PW - 80, marginLeft: 40, height: PH - IMG, padding: '34px 0 30px' },
      h('div', { display: 'flex', flexDirection: 'column' },
        h('div', { fontSize: 58, fontWeight: 700, lineHeight: 1.05, letterSpacing: -1 }, o.headline),
        h('div', { fontSize: 30, lineHeight: 1.3, marginTop: 16, color: '#DDD' }, o.sub)),
      brandRow('#fff', '#AAA'))),
    PW, PH, 85);
}

// A city's water: a cleared patch upstream, then the river, the plant and the reader's tap
export async function waterPost(o: { title: string; big: string; line: string; river: string; plant: string; tap: string; picture?: Chip }) {
  const PIC = 470, LINE = PAD + PIC / 2, TOP = 136;
  const stop = (title: string, sub: string, y: number, filled: boolean) => [
    h('div', { position: 'absolute', left: LINE - 22, top: y - 22, width: 44, height: 44, borderRadius: '50%', background: filled ? RIVER : PAPER, border: `8px solid ${RIVER}` }),
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: LINE + 50, top: y - 30, width: 640 },
      h('div', { fontSize: 40, fontWeight: 700, lineHeight: 1.1 }, title), h('div', { fontSize: 28, lineHeight: 1.3, color: '#333', marginTop: 6 }, sub))];
  const pic = o.picture ? [
    img(await jpeg(o.picture), { position: 'absolute', left: PAD, top: TOP, width: PIC, height: PIC }),
    img(ring(56), { position: 'absolute', left: PAD + PIC / 2 - 28, top: TOP + PIC / 2 - 28, width: 56, height: 56 }),
    h('div', { position: 'absolute', left: PAD, top: TOP + PIC - 44, background: INK, color: '#fff', fontSize: 24, fontWeight: 700, padding: '6px 12px' }, `One cleared patch upstream, ${shortDate(o.picture.date)}`),
  ] : [h('div', { position: 'absolute', left: PAD, top: TOP, width: PIC, height: PIC, background: '#DDD' })];
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { position: 'absolute', left: PAD, top: 56, width: INNER, fontSize: 40, fontWeight: 700 }, o.title),
    ...pic,
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD + PIC + 40, top: TOP + 14, width: INNER - PIC - 40 },
      h('div', { fontSize: 128, fontWeight: 700, lineHeight: 0.95, letterSpacing: -4, color: SIGNAL }, o.big),
      h('div', { fontSize: 40, fontWeight: 700, color: SIGNAL }, 'hectares'),
      h('div', { fontSize: 30, lineHeight: 1.3, marginTop: 18 }, o.line)),
    h('div', { position: 'absolute', left: LINE - 5, top: TOP + PIC, width: 10, height: 470, background: RIVER }),
    ...stop(o.river, 'Rain washes mud from the cleared land into it', TOP + PIC + 130, false),
    ...stop(o.plant, 'More mud makes the water harder and dearer to treat', TOP + PIC + 300, false),
    ...stop('Your tap', o.tap, TOP + PIC + 470, true),
    h('div', { display: 'flex', position: 'absolute', left: 0, bottom: 0, width: PW, height: 96, background: INK, alignItems: 'center', paddingLeft: PAD },
      brandRow('#fff', '#fff'))),
    PW, PH, 85);
}

// One day's clearing, on average, drawn as football pitches you can count
export async function ratePost(o: { top: string; perDay: number; line: string; sub: string }) {
  const rows: Node[] = [];
  const shown = Math.min(o.perDay, 100);
  for (let r = 0; r * 10 < shown; r++) {
    rows.push(h('div', { display: 'flex', gap: 12 }, ...Array.from({ length: Math.min(10, shown - r * 10) }, () => img(PITCH, { width: 84, height: 56 }))));
  }
  return card(h('div', { display: 'flex', flexDirection: 'column', position: 'relative', width: PW, height: PH, background: INK, fontFamily: 'Atkinson', color: '#fff', padding: `${PAD}px ${PAD}px 0` },
    h('div', { width: INNER, fontSize: 40, fontWeight: 700 }, o.top),
    h('div', { display: 'flex', alignItems: 'flex-end', gap: 28, marginTop: 30 },
      h('div', { fontSize: 230, fontWeight: 700, lineHeight: 0.85, letterSpacing: -8, color: PINK }, String(o.perDay)),
      h('div', { fontSize: 54, fontWeight: 700, lineHeight: 1.05, width: 560, paddingBottom: 6 }, o.line)),
    h('div', { display: 'flex', flexDirection: 'column', gap: 14, marginTop: 64 }, ...rows),
    h('div', { width: INNER, fontSize: 28, lineHeight: 1.35, color: '#CCC', marginTop: 40 }, o.sub),
    h('div', { display: 'flex', position: 'absolute', left: PAD, bottom: 40 }, brandRow('#fff', '#AAA'))),
    PW, PH, 85);
}
