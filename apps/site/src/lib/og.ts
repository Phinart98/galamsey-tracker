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
  // The river and its three stops drawn as one SVG, so the line runs exactly through every circle's centre
  const STOPS = [130, 300, 470];
  const track = svgUri(`<svg xmlns="http://www.w3.org/2000/svg" width="60" height="500"><rect x="25" y="0" width="10" height="${STOPS[2]}" fill="${RIVER}"/>${
    // One small chevron midway between stops, pointing downstream: the water flows from the picture to the tap
    [0, ...STOPS.slice(0, 2)].map((y, i) => (y + STOPS[i]) / 2).map((y) => `<path d="M17 ${y - 7} L30 ${y + 6} L43 ${y - 7}" fill="none" stroke="${RIVER}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>`).join('')}${
    STOPS.map((y, i) => `<circle cx="30" cy="${y}" r="20" fill="${i === 2 ? RIVER : PAPER}" stroke="${RIVER}" stroke-width="8"/>`).join('')}</svg>`);
  const stop = (title: string, sub: string, y: number) =>
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: LINE + 50, top: y - 30, width: 640 },
      h('div', { fontSize: 40, fontWeight: 700, lineHeight: 1.1 }, title), h('div', { fontSize: 28, lineHeight: 1.3, color: '#333', marginTop: 6 }, sub));
  // The caption sits inside the picture's bottom-left corner and never runs past its edge
  const pic = o.picture ? [
    img(await jpeg(o.picture), { position: 'absolute', left: PAD, top: TOP, width: PIC, height: PIC }),
    img(ring(56), { position: 'absolute', left: PAD + PIC / 2 - 28, top: TOP + PIC / 2 - 28, width: 56, height: 56 }),
    h('div', { position: 'absolute', left: PAD, top: TOP + PIC - 44, maxWidth: PIC, background: INK, color: '#fff', fontSize: 24, fontWeight: 700, padding: '6px 12px' }, `Upstream, ${shortDate(o.picture.date)}`),
  ] : [h('div', { position: 'absolute', left: PAD, top: TOP, width: PIC, height: PIC, background: '#DDD' })];
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { position: 'absolute', left: PAD, top: 56, width: INNER, fontSize: 40, fontWeight: 700 }, o.title),
    ...pic,
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD + PIC + 40, top: TOP + 14, width: INNER - PIC - 40 },
      h('div', { fontSize: 128, fontWeight: 700, lineHeight: 0.95, letterSpacing: -4, color: SIGNAL }, o.big),
      h('div', { fontSize: 40, fontWeight: 700, color: SIGNAL }, 'hectares'),
      h('div', { fontSize: 30, lineHeight: 1.3, marginTop: 18 }, o.line)),
    img(track, { position: 'absolute', left: LINE - 30, top: TOP + PIC, width: 60, height: 500 }),
    stop(o.river, 'Rain washes mud from the cleared land into it', TOP + PIC + STOPS[0]),
    stop(o.plant, 'More mud makes the water harder and dearer to treat', TOP + PIC + STOPS[1]),
    stop('Your tap', o.tap, TOP + PIC + STOPS[2]),
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

// One district: its total, then its three largest pictured patches side by side
export async function districtPost(o: { title: string; big: string; line: string; stat: string; places: { label: string; after: Chip }[] }) {
  const S = 296;
  const tiles = await Promise.all(o.places.slice(0, 3).map(async (p) =>
    h('div', { display: 'flex', flexDirection: 'column', width: S },
      h('div', { display: 'flex', position: 'relative', width: S, height: S },
        img(await jpeg(p.after), { width: S, height: S, objectFit: 'cover' }),
        img(ring(44), { position: 'absolute', left: S / 2 - 22, top: S / 2 - 22, width: 44, height: 44 })),
      h('div', { fontSize: 26, lineHeight: 1.25, marginTop: 12 }, p.label))));
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
    h('div', { width: INNER, fontSize: 40, fontWeight: 700 }, o.title),
    h('div', { width: INNER, fontSize: 200, fontWeight: 700, lineHeight: 0.95, letterSpacing: -6, color: SIGNAL, marginTop: 40 }, o.big),
    h('div', { width: INNER, fontSize: 40, lineHeight: 1.25, marginTop: 16 }, o.line),
    h('div', { width: INNER, fontSize: 40, fontWeight: 700, color: SIGNAL, marginTop: 8 }, o.stat),
    h('div', { display: 'flex', gap: (INNER - S * 3) / 2, marginTop: 64 }, ...tiles)),
    h('div', { display: 'flex', position: 'absolute', left: 0, bottom: 0, width: PW, height: 96, background: INK, alignItems: 'center', paddingLeft: PAD },
      brandRow('#fff', '#fff'))),
    PW, PH, 85);
}

// What licence is on the cleared land: one bar split by licence, the no-licence share as the headline
export async function licencePost(o: { big: string; line: string; parts: { label: string; ha: string; share: number; tiny: boolean; alarm: boolean }[]; sub: string }) {
  const BAR = INNER, H = 120;
  let x = 0;
  const shades = [SIGNAL, PINK, '#888', '#555', '#222'];
  const segs = o.parts.map((p, i) => {
    const w = Math.max(p.share * BAR, p.share > 0 ? 6 : 0);
    const seg = `<rect x="${x}" y="0" width="${w}" height="${H}" fill="${shades[i]}"/>`;
    x += w;
    return seg;
  }).join('');
  const bar = svgUri(`<svg xmlns="http://www.w3.org/2000/svg" width="${BAR}" height="${H}">${segs}</svg>`);
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
    h('div', { width: INNER, fontSize: 40, fontWeight: 700 }, 'What licence is on the cleared land'),
    h('div', { width: INNER, fontSize: 240, fontWeight: 700, lineHeight: 0.95, letterSpacing: -8, color: SIGNAL, marginTop: 40 }, o.big),
    h('div', { width: INNER, fontSize: 44, fontWeight: 700, lineHeight: 1.15, marginTop: 12 }, o.line),
    img(bar, { width: BAR, height: H, marginTop: 56 }),
    h('div', { display: 'flex', flexDirection: 'column', gap: 14, marginTop: 32 },
      ...o.parts.map((p, i) => h('div', { display: 'flex', alignItems: 'center', gap: 16, fontSize: 30 },
        h('div', { width: 28, height: 28, background: shades[i] }),
        h('div', { width: 560, fontWeight: p.alarm ? 700 : 400 }, p.label),
        h('div', { width: 200, textAlign: 'right' }, p.ha),
        h('div', { width: 120, textAlign: 'right', color: '#444' }, p.tiny ? 'under 1%' : `${Math.round(p.share * 100)}%`)))),
    h('div', { width: INNER, fontSize: 26, lineHeight: 1.35, color: '#333', marginTop: 32 }, o.sub)),
    h('div', { display: 'flex', position: 'absolute', left: 0, bottom: 0, width: PW, height: 96, background: INK, alignItems: 'center', paddingLeft: PAD },
      brandRow('#fff', '#fff'))),
    PW, PH, 85);
}
