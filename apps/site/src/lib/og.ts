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
  // Few pitches are drawn large, so a small number still fills the picture
  const per = shown <= 6 ? 2 : 10, iw = shown <= 6 ? 440 : 84, ih = shown <= 6 ? 293 : 56, gap = shown <= 6 ? 24 : 12;
  for (let r = 0; r * per < shown; r++) {
    rows.push(h('div', { display: 'flex', gap }, ...Array.from({ length: Math.min(per, shown - r * per) }, () => img(PITCH, { width: iw, height: ih }))));
  }
  return card(h('div', { display: 'flex', flexDirection: 'column', position: 'relative', width: PW, height: PH, background: INK, fontFamily: 'Atkinson', color: '#fff', padding: `${PAD}px ${PAD}px 0` },
    h('div', { width: INNER, fontSize: 40, fontWeight: 700 }, o.top),
    h('div', { display: 'flex', alignItems: 'flex-end', gap: 28, marginTop: 30 },
      h('div', { fontSize: 230, fontWeight: 700, lineHeight: 0.85, letterSpacing: -8, color: PINK }, String(o.perDay)),
      h('div', { fontSize: 54, fontWeight: 700, lineHeight: 1.05, width: 560, paddingBottom: 6 }, o.line)),
    h('div', { display: 'flex', flexDirection: 'column', gap: shown <= 6 ? 24 : 14, marginTop: 64 }, ...rows),
    h('div', { width: INNER, fontSize: 28, lineHeight: 1.35, color: '#CCC', marginTop: 40 }, o.sub),
    h('div', { display: 'flex', position: 'absolute', left: PAD, top: PH - 76 }, brandRow('#fff', '#AAA'))),
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

// ---- More kinds of post (2026-11-05). Same palette, type and footer as above, so the feed reads as one voice ----

const footer = () => h('div', { display: 'flex', position: 'absolute', left: 0, bottom: 0, width: PW, height: 96, background: INK, alignItems: 'center', paddingLeft: PAD },
  brandRow('#fff', '#fff'));

// One place as a single picture split down the middle: before on the left half, after on the right half of the
// same view, so the change reads across one line. A different look from the side-by-side and inset posts.
export async function splitPost(o: { headline: string; sub: string; before: Chip; after: Chip }) {
  const IMG = 1000, HALF = PW / 2;
  const [b, a] = await Promise.all([jpeg(o.before), jpeg(o.after)]);
  const half = (src: string, left: boolean) => h('div', { display: 'flex', position: 'absolute', left: left ? 0 : HALF, top: 0, width: HALF, height: IMG, overflow: 'hidden' },
    img(src, { position: 'absolute', left: left ? 0 : -HALF, top: 0, width: PW, height: IMG, objectFit: 'cover' }));
  const label = (text: string, left: boolean) => h('div', { position: 'absolute', top: 32, ...(left ? { left: 32 } : { right: 32 }), background: INK, fontSize: 26, fontWeight: 700, padding: '6px 14px' }, text);
  return card(h('div', { display: 'flex', flexDirection: 'column', width: PW, height: PH, background: INK, fontFamily: 'Atkinson', color: '#fff' },
    h('div', { display: 'flex', position: 'relative', width: PW, height: IMG, overflow: 'hidden' },
      half(b, true), half(a, false),
      h('div', { position: 'absolute', left: HALF - 3, top: 0, width: 6, height: IMG, background: '#fff' }),
      img(ring(64), { position: 'absolute', left: HALF - 32, top: IMG / 2 - 32, width: 64, height: 64 }),
      label(`Before, ${shortDate(o.before.date)}`, true), label(`After, ${shortDate(o.after.date)}`, false)),
    h('div', { display: 'flex', flexDirection: 'column', justifyContent: 'space-between', width: PW - 80, marginLeft: 40, height: PH - IMG, padding: '34px 0 30px' },
      h('div', { display: 'flex', flexDirection: 'column' },
        h('div', { fontSize: 56, fontWeight: 700, lineHeight: 1.05, letterSpacing: -1 }, o.headline),
        h('div', { fontSize: 30, lineHeight: 1.3, marginTop: 16, color: '#DDD' }, o.sub)),
      brandRow('#fff', '#AAA'))),
    PW, PH, 85);
}

// A contact sheet: six places in a 3 x 2 grid, each with its ring and a short label
export async function sheetPost(o: { title: string; line: string; places: { label: string; after: Chip }[] }) {
  const S = 296, GAP = (INNER - S * 3) / 2;
  const tiles = await Promise.all(o.places.slice(0, 6).map(async (p) =>
    h('div', { display: 'flex', flexDirection: 'column', width: S, height: S + 84 },
      h('div', { display: 'flex', position: 'relative', width: S, height: S },
        img(await jpeg(p.after), { width: S, height: S, objectFit: 'cover' }),
        img(ring(40), { position: 'absolute', left: S / 2 - 20, top: S / 2 - 20, width: 40, height: 40 })),
      h('div', { fontSize: 24, lineHeight: 1.25, marginTop: 10 }, p.label))));
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
      h('div', { width: INNER, fontSize: 56, fontWeight: 700, lineHeight: 1.05, letterSpacing: -1 }, o.title),
      h('div', { width: INNER, fontSize: 30, lineHeight: 1.3, marginTop: 14, color: '#333' }, o.line),
      h('div', { display: 'flex', flexWrap: 'wrap', gap: `24px ${GAP}px`, width: INNER, marginTop: 40 }, ...tiles)),
    footer()),
    PW, PH, 85);
}

// Horizontal bars, longest first, value at the end of each bar. One colour: it is one measure
export async function barsPost(o: { title: string; big?: string; line: string; rows: { label: string; value: number; text: string }[]; sub: string; color?: string }) {
  const color = o.color ?? SIGNAL;
  const max = Math.max(...o.rows.map((r) => r.value), 1);
  const BAR = 620;
  const rowH = o.rows.length > 6 ? 76 : 96;
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
      h('div', { width: INNER, fontSize: 40, fontWeight: 700 }, o.title),
      ...(o.big ? [h('div', { width: INNER, fontSize: 160, fontWeight: 700, lineHeight: 0.95, letterSpacing: -5, color, marginTop: 28 }, o.big)] : []),
      h('div', { width: INNER, fontSize: 38, fontWeight: 700, lineHeight: 1.15, marginTop: o.big ? 10 : 24 }, o.line),
      h('div', { display: 'flex', flexDirection: 'column', marginTop: 36, width: INNER },
        ...o.rows.map((r) => h('div', { display: 'flex', flexDirection: 'column', height: rowH, justifyContent: 'center' },
          h('div', { fontSize: 26, lineHeight: 1.2 }, r.label),
          h('div', { display: 'flex', alignItems: 'center', gap: 14, marginTop: 6 },
            h('div', { width: Math.max(6, Math.round((r.value / max) * BAR)), height: 26, background: color }),
            h('div', { fontSize: 26, fontWeight: 700 }, r.text))))),
      h('div', { width: INNER, fontSize: 24, lineHeight: 1.35, color: '#333', marginTop: 20 }, o.sub)),
    footer()),
    PW, PH, 85);
}

// The belt as a map: land outline, then every cleared patch as a dot sized by its area
export async function mapPost(o: { title: string; big: string; line: string; sub: string; frame: number[]; land: number[][][][]; dots: { lon: number; lat: number; ha: number }[] }) {
  const [W0, S0, E0, N0] = o.frame;
  const MW = INNER, MH = Math.round(MW * ((N0 - S0) / (E0 - W0)));
  const x = (lon: number) => ((lon - W0) / (E0 - W0)) * MW;
  const y = (lat: number) => ((N0 - lat) / (N0 - S0)) * MH;
  const land = o.land.map((poly) => poly.map((r) => `M${r.map(([lo, la]) => `${x(lo).toFixed(1)} ${y(la).toFixed(1)}`).join('L')}Z`).join('')).join('');
  const dots = o.dots.map((d) => `<circle cx="${x(d.lon).toFixed(1)}" cy="${y(d.lat).toFixed(1)}" r="${Math.min(9, 1.6 + Math.sqrt(d.ha) * 0.9).toFixed(1)}"/>`).join('');
  const map = svgUri(`<svg xmlns="http://www.w3.org/2000/svg" width="${MW}" height="${MH}"><rect width="${MW}" height="${MH}" fill="#DCE6EE"/><path d="${land}" fill="#fff" stroke="#888" stroke-width="1.5"/><g fill="${SIGNAL}" fill-opacity="0.75">${dots}</g></svg>`);
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
      h('div', { width: INNER, fontSize: 40, fontWeight: 700 }, o.title),
      h('div', { display: 'flex', alignItems: 'flex-end', gap: 20, marginTop: 20 },
        h('div', { fontSize: 120, fontWeight: 700, lineHeight: 0.9, letterSpacing: -4, color: SIGNAL }, o.big),
        h('div', { fontSize: 36, fontWeight: 700, lineHeight: 1.1, width: 520, paddingBottom: 6 }, o.line)),
      img(map, { width: MW, height: MH, marginTop: 32, border: '2px solid #000' }),
      h('div', { width: INNER, fontSize: 24, lineHeight: 1.35, color: '#333', marginTop: 18 }, o.sub)),
    footer()),
    PW, PH, 85);
}

// One big number with what it means, and one real picture that shows it
export async function statPost(o: { title: string; big: string; line: string; body: string; picture?: Chip; caption?: string }) {
  const PIC = { w: INNER, h: 560 };
  const pic = o.picture ? [h('div', { display: 'flex', position: 'relative', width: PIC.w, height: PIC.h, marginTop: 36, overflow: 'hidden' },
    img(await jpeg(o.picture), { position: 'absolute', left: 0, top: -(PIC.w - PIC.h) / 2, width: PIC.w, height: PIC.w }),
    img(ring(56), { position: 'absolute', left: PIC.w / 2 - 28, top: PIC.h / 2 - 28, width: 56, height: 56 }),
    ...(o.caption ? [h('div', { position: 'absolute', left: 0, bottom: 0, maxWidth: PIC.w, background: INK, color: '#fff', fontSize: 24, fontWeight: 700, padding: '6px 12px' }, o.caption)] : []))] : [];
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
      h('div', { width: INNER, fontSize: 40, fontWeight: 700 }, o.title),
      h('div', { width: INNER, fontSize: 200, fontWeight: 700, lineHeight: 0.95, letterSpacing: -6, color: SIGNAL, marginTop: 28 }, o.big),
      h('div', { width: INNER, fontSize: 40, fontWeight: 700, lineHeight: 1.15, marginTop: 10 }, o.line),
      h('div', { width: INNER, fontSize: 30, lineHeight: 1.35, marginTop: 20, color: '#222' }, o.body),
      ...pic),
    footer()),
    PW, PH, 85);
}

// An explainer: a short list of points, each with a marker (a number for steps in order, a colour swatch for
// labels), and optionally a real before and after pair at the top
export async function explainerPost(o: { title: string; points: { mark: string; markColor?: string; head: string; body: string }[]; pair?: { before: Chip; after: Chip } }) {
  const S = (INNER - 24) / 2, PH2 = Math.round(S * 0.72);
  const shotOf = async (c: Chip, word: string) => h('div', { display: 'flex', position: 'relative', width: S, height: PH2, overflow: 'hidden' },
    img(await jpeg(c), { position: 'absolute', left: 0, top: -(S - PH2) / 2, width: S, height: S }),
    img(ring(44), { position: 'absolute', left: S / 2 - 22, top: PH2 / 2 - 22, width: 44, height: 44 }),
    h('div', { position: 'absolute', left: 0, bottom: 0, background: INK, color: '#fff', fontSize: 24, fontWeight: 700, padding: '5px 12px' }, `${word}, ${shortDate(c.date)}`));
  const pair = o.pair ? [h('div', { display: 'flex', gap: 24, marginTop: 32 }, await shotOf(o.pair.before, 'Before'), await shotOf(o.pair.after, 'After'))] : [];
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
      h('div', { width: INNER, fontSize: 56, fontWeight: 700, lineHeight: 1.05, letterSpacing: -1 }, o.title),
      ...pair,
      h('div', { display: 'flex', flexDirection: 'column', gap: o.pair ? 26 : 48, marginTop: o.pair ? 36 : 64, width: INNER },
        ...o.points.map((p) => h('div', { display: 'flex', gap: 22, alignItems: 'flex-start' },
          h('div', { display: 'flex', alignItems: 'center', justifyContent: 'center', width: 52, height: 52, flexShrink: 0, background: p.markColor ?? INK, color: '#fff', fontSize: 30, fontWeight: 700 }, p.mark),
          h('div', { display: 'flex', flexDirection: 'column', width: INNER - 74 },
            h('div', { fontSize: o.pair ? 32 : 40, fontWeight: 700, lineHeight: 1.15 }, p.head),
            h('div', { fontSize: o.pair ? 27 : 32, lineHeight: 1.35, marginTop: 6, color: '#222' }, p.body)))))),
    footer()),
    PW, PH, 85);
}
