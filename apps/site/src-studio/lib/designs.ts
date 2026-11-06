// The post layouts (1080 x 1350, the shape that fills a phone screen on X). Each function draws one kind of post
// from the words and pictures it is given; what to say and which place to show is decided in posts/.
// Look: the satellite picture is the headline where there is one, site colours plus river blue for water,
// a big number in signal red, and the same brand footer on every post so the feed reads as one voice.
import type { Chip } from '../../src/lib/data';
import { shortDate } from '../../src/lib/format';
import { card, h, img, jpeg as encode, type Node } from '../../src/lib/og';

// Several posts show the same picture (the town of the week also heads the picture explainer), so each is
// downloaded and re-encoded once per build
const encoded = new Map<string, Promise<string>>();
const jpeg = (chip: Chip) => {
  const key = chip.files['720.webp'];
  if (!encoded.has(key)) encoded.set(key, encode(chip));
  return encoded.get(key)!;
};

const PW = 1080, PH = 1350, PAD = 64, INNER = PW - PAD * 2;
// The post palette: the site's colours, plus river blue for water
export const INK = '#000', PAPER = '#F5F6F3', SIGNAL = '#B8155A', PINK = '#FF6FA6', RIVER = '#1D5C8C';
const svgUri = (svg: string) => `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;

// White ring with a thin black edge, hollow so the patch shows through (same as the site). SVG, because satori
// offsets nested bordered circles by a pixel or two.
const ring = (d: number) => svgUri(`<svg xmlns="http://www.w3.org/2000/svg" width="${d}" height="${d}"><circle cx="${d / 2}" cy="${d / 2}" r="${d * 0.38}" fill="none" stroke="#000" stroke-width="${d * 0.17}"/><circle cx="${d / 2}" cy="${d / 2}" r="${d * 0.38}" fill="none" stroke="#fff" stroke-width="${d * 0.1}"/></svg>`);
const PITCH = svgUri('<svg xmlns="http://www.w3.org/2000/svg" width="84" height="56"><rect width="84" height="56" fill="#FF6FA6"/><rect x="3" y="3" width="78" height="50" fill="none" stroke="#000" stroke-width="2"/><line x1="42" y1="3" x2="42" y2="53" stroke="#000" stroke-width="2"/><circle cx="42" cy="28" r="9" fill="none" stroke="#000" stroke-width="2"/><rect x="3" y="16" width="10" height="24" fill="none" stroke="#000" stroke-width="2"/><rect x="71" y="16" width="10" height="24" fill="none" stroke="#000" stroke-width="2"/></svg>');

function brandRow(color: string, muted: string) {
  return h('div', { display: 'flex', justifyContent: 'space-between', width: INNER, fontSize: 28 },
    h('div', { fontWeight: 700, color }, 'Galamsey Tracker'), h('div', { color: muted }, 'galamseytracker.org'));
}
// The black band at the foot of every light post
const footer = () => h('div', { display: 'flex', position: 'absolute', left: 0, bottom: 0, width: PW, height: 96, background: INK, alignItems: 'center', paddingLeft: PAD },
  brandRow('#fff', '#fff'));
// Southern Ghana's outline as an SVG path, for the map posts (x and y turn lon/lat into pixels)
const landPath = (land: number[][][][], x: (lon: number) => number, y: (lat: number) => number) =>
  land.map((poly) => poly.map((r) => `M${r.map(([lo, la]) => `${x(lo).toFixed(1)} ${y(la).toFixed(1)}`).join('L')}Z`).join('')).join('');

// One place, before and after (town of the week, one place, new clearing): the after picture edge to edge,
// the before small in a corner
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
export async function waterPost(o: { title: string; big: string; line: string; river: string; plant: string; tap: string; picture?: Chip; caption?: string }) {
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
    h('div', { position: 'absolute', left: PAD, top: TOP + PIC - 44, maxWidth: PIC, background: INK, color: '#fff', fontSize: 24, fontWeight: 700, padding: '6px 12px' }, o.caption ?? `Upstream, ${shortDate(o.picture.date)}`),
  ] : [h('div', { position: 'absolute', left: PAD, top: TOP, width: PIC, height: PIC, background: '#DDD' })];
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { position: 'absolute', left: PAD, top: 56, width: INNER, fontSize: 40, fontWeight: 700 }, o.title),
    ...pic,
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD + PIC + 40, top: TOP + 14, width: INNER - PIC - 40 },
      h('div', { fontSize: 128, fontWeight: 700, lineHeight: 0.95, letterSpacing: -4, color: SIGNAL }, o.big),
      h('div', { fontSize: 40, fontWeight: 700, color: SIGNAL }, 'hectares'),
      h('div', { fontSize: 30, lineHeight: 1.3, marginTop: 18 }, o.line)),
    img(track, { position: 'absolute', left: LINE - 30, top: TOP + PIC, width: 60, height: 500 }),
    stop(o.river, `Rain washes mud from the cleared land into ${/ rivers$/.test(o.river) ? 'them' : 'it'}`, TOP + PIC + STOPS[0]),
    stop(o.plant, 'More mud makes the water harder and dearer to treat', TOP + PIC + STOPS[1]),
    stop('Your tap', o.tap, TOP + PIC + STOPS[2]),
    footer()),
    PW, PH, 85);
}

// One day's clearing, on average, drawn as football pitches you can count
export async function ratePost(o: { top: string; perDay: number; line: string; sub: string }) {
  const rows: Node[] = [];
  const shown = Math.min(o.perDay, 100);
  // Few pitches are drawn large, so a small number still fills the picture
  const few = shown <= 6, per = few ? (shown <= 4 ? 2 : 3) : 10, iw = few ? (shown <= 4 ? 440 : 288) : 84, ih = Math.round(iw * (56 / 84)), gap = few ? 24 : 12;
  for (let r = 0; r * per < shown; r++) {
    rows.push(h('div', { display: 'flex', gap }, ...Array.from({ length: Math.min(per, shown - r * per) }, () => img(PITCH, { width: iw, height: ih }))));
  }
  return card(h('div', { display: 'flex', flexDirection: 'column', position: 'relative', width: PW, height: PH, background: INK, fontFamily: 'Atkinson', color: '#fff', padding: `${PAD}px ${PAD}px 0` },
    h('div', { width: INNER, fontSize: 40, fontWeight: 700 }, o.top),
    h('div', { display: 'flex', alignItems: 'flex-end', gap: 28, marginTop: 30 },
      h('div', { fontSize: 230, fontWeight: 700, lineHeight: 0.85, letterSpacing: -8, color: PINK }, String(o.perDay)),
      h('div', { fontSize: 54, fontWeight: 700, lineHeight: 1.05, width: 560, paddingBottom: 6 }, o.line)),
    h('div', { display: 'flex', flexDirection: 'column', gap: few ? 24 : 14, marginTop: 64 }, ...rows),
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
    footer()),
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
    footer()),
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
  const land = landPath(o.land, x, y);
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

// Patch outlines arrive as lon/lat rings. Metres make shapes and the football pitch share one true scale
type Rings = number[][][];
const toMetres = (rings: Rings) => {
  const lat0 = rings[0][0][1];
  const kx = 111320 * Math.cos((lat0 * Math.PI) / 180), ky = 110540;
  return rings.map((r) => r.map(([lo, la]) => [lo * kx, -la * ky]));
};
const extent = (rings: number[][][]) => {
  const xs = rings.flatMap((r) => r.map((p) => p[0])), ys = rings.flatMap((r) => r.map((p) => p[1]));
  return { x0: Math.min(...xs), y0: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
};
const pathOf = (rings: number[][][], s: number, ox: number, oy: number) =>
  rings.map((r) => `M${r.map(([x, y]) => `${((x - ox) * s).toFixed(1)} ${((y - oy) * s).toFixed(1)}`).join('L')}Z`).join('');

// The shape of it: one patch's real outline, solid, with a football pitch drawn to the same scale
export async function shapePost(o: { title: string; big: string; line: string; sub: string; rings: Rings }) {
  const m = toMetres(o.rings), e = extent(m);
  const BOX = { w: INNER, h: 640 };
  const PITCH_M = { w: 105, h: 68 };
  // Leave room under the shape for the pitch, then fit both into the box
  const s = Math.min(BOX.w / Math.max(e.w, PITCH_M.w), (BOX.h - 40) / (e.h + PITCH_M.h * 1.6));
  const sw = e.w * s, sh = e.h * s, pw = PITCH_M.w * s, ph = PITCH_M.h * s;
  const pitch = `<g transform="translate(0 ${(BOX.h - ph).toFixed(1)})"><rect width="${pw.toFixed(1)}" height="${ph.toFixed(1)}" fill="none" stroke="${INK}" stroke-width="3"/><line x1="${(pw / 2).toFixed(1)}" y1="0" x2="${(pw / 2).toFixed(1)}" y2="${ph.toFixed(1)}" stroke="${INK}" stroke-width="2"/><circle cx="${(pw / 2).toFixed(1)}" cy="${(ph / 2).toFixed(1)}" r="${(9.15 * s).toFixed(1)}" fill="none" stroke="${INK}" stroke-width="2"/></g>`;
  const shape = `<g transform="translate(${((BOX.w - sw) / 2).toFixed(1)} 0)"><path d="${pathOf(m, s, e.x0, e.y0)}" fill="${SIGNAL}" fill-rule="evenodd"/></g>`;
  const art = svgUri(`<svg xmlns="http://www.w3.org/2000/svg" width="${BOX.w}" height="${BOX.h}">${shape}${pitch}</svg>`);
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
      h('div', { width: INNER, fontSize: 40, fontWeight: 700 }, o.title),
      h('div', { display: 'flex', alignItems: 'flex-end', gap: 24, marginTop: 18 },
        h('div', { fontSize: 140, fontWeight: 700, lineHeight: 0.9, letterSpacing: -5, color: SIGNAL }, o.big),
        h('div', { fontSize: 34, fontWeight: 700, lineHeight: 1.15, width: 520, paddingBottom: 8 }, o.line)),
      h('div', { display: 'flex', position: 'relative', width: BOX.w, height: BOX.h, marginTop: 40 },
        img(art, { width: BOX.w, height: BOX.h }),
        h('div', { position: 'absolute', left: pw + 18, top: BOX.h - ph / 2 - 18, fontSize: 26, color: '#333' }, 'A football pitch, to the same scale')),
      h('div', { width: INNER, fontSize: 26, lineHeight: 1.35, color: '#333', marginTop: 24 }, o.sub)),
    footer()),
    PW, PH, 85);
}

// A specimen plate: twelve real outlines at one shared scale, like a page of a field guide
export async function platePost(o: { title: string; line: string; items: { rings: Rings; label: string }[] }) {
  const CELL = 214, COLS = 4, GAPX = (INNER - CELL * COLS) / (COLS - 1);
  const shapes = o.items.slice(0, 12).map((it) => toMetres(it.rings));
  const span = Math.max(...shapes.map((m) => { const e = extent(m); return Math.max(e.w, e.h); }));
  const s = (CELL - 8) / span;
  const BAR_M = span > 3000 ? 1000 : 500;
  const cells = shapes.map((m, i) => {
    const e = extent(m);
    const svg = svgUri(`<svg xmlns="http://www.w3.org/2000/svg" width="${CELL}" height="${CELL}"><g transform="translate(${((CELL - e.w * s) / 2).toFixed(1)} ${((CELL - e.h * s) / 2).toFixed(1)})"><path d="${pathOf(m, s, e.x0, e.y0)}" fill="${INK}" fill-rule="evenodd"/></g></svg>`);
    return h('div', { display: 'flex', flexDirection: 'column', width: CELL },
      img(svg, { width: CELL, height: CELL }),
      h('div', { fontSize: 22, lineHeight: 1.25, marginTop: 8, color: '#333' }, o.items[i].label));
  });
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
      h('div', { width: INNER, fontSize: 56, fontWeight: 700, lineHeight: 1.05, letterSpacing: -1 }, o.title),
      h('div', { width: INNER, fontSize: 28, lineHeight: 1.35, marginTop: 12, color: '#333' }, o.line),
      h('div', { display: 'flex', flexWrap: 'wrap', gap: `22px ${GAPX}px`, width: INNER, marginTop: 34 }, ...cells),
      h('div', { display: 'flex', alignItems: 'center', gap: 14, marginTop: 26 },
        h('div', { width: Math.round(BAR_M * s), height: 8, background: INK }),
        h('div', { fontSize: 24 }, `${BAR_M === 1000 ? '1 km' : '500 m'}, the same for every shape`))),
    footer()),
    PW, PH, 85);
}

// Find it yourself: the coordinates as the headline, a pin on the map, and the picture
export async function findPost(o: { lat: number; lon: number; line: string; sub: string; frame: number[]; land: number[][][][]; after: Chip }) {
  const fmt = (v: number, pos: string, neg: string) => `${Math.abs(v).toFixed(4)}° ${v >= 0 ? pos : neg}`;
  const [W0, S0, E0, N0] = o.frame;
  const MW = 440, MH = Math.round(MW * ((N0 - S0) / (E0 - W0)));
  const x = (lon: number) => ((lon - W0) / (E0 - W0)) * MW, y = (lat: number) => ((N0 - lat) / (N0 - S0)) * MH;
  const land = landPath(o.land, x, y);
  const px = x(o.lon), py = y(o.lat);
  const map = svgUri(`<svg xmlns="http://www.w3.org/2000/svg" width="${MW}" height="${MH}"><path d="${land}" fill="#2A2A2A" stroke="#666" stroke-width="1.5"/><circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="22" fill="none" stroke="${PINK}" stroke-width="5"/><circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="7" fill="${PINK}"/></svg>`);
  const PIC = INNER - MW - 32;
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: INK, fontFamily: 'Atkinson', color: '#fff' },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
      h('div', { width: INNER, fontSize: 40, fontWeight: 700 }, 'Check it yourself'),
      h('div', { width: INNER, fontSize: 118, fontWeight: 700, lineHeight: 1.0, letterSpacing: -3, color: PINK, marginTop: 28 }, fmt(o.lat, 'N', 'S')),
      h('div', { width: INNER, fontSize: 118, fontWeight: 700, lineHeight: 1.0, letterSpacing: -3, color: PINK }, fmt(o.lon, 'E', 'W')),
      h('div', { width: INNER, fontSize: 32, lineHeight: 1.3, marginTop: 24 }, o.line),
      h('div', { display: 'flex', gap: 32, marginTop: 40, alignItems: 'flex-start' },
        h('div', { display: 'flex', flexDirection: 'column', width: MW },
          img(map, { width: MW, height: MH }),
          h('div', { fontSize: 24, color: '#AAA', marginTop: 10 }, 'Southern Ghana')),
        h('div', { display: 'flex', position: 'relative', width: PIC, height: PIC },
          img(await jpeg(o.after), { width: PIC, height: PIC }),
          img(ring(48), { position: 'absolute', left: PIC / 2 - 24, top: PIC / 2 - 24, width: 48, height: 48 }),
          h('div', { position: 'absolute', left: 0, bottom: 0, background: INK, fontSize: 22, fontWeight: 700, padding: '5px 10px' }, `Seen ${shortDate(o.after.date)}`))),
      h('div', { width: INNER, fontSize: 26, lineHeight: 1.35, color: '#CCC', marginTop: 28 }, o.sub)),
    h('div', { display: 'flex', position: 'absolute', left: PAD, top: PH - 76 }, brandRow('#fff', '#AAA'))),
    PW, PH, 85);
}

// Licensed to explore, not to mine: what the register allows on the left, what the satellite saw on the right
export async function explorePost(o: { place: string; ha: string; after: Chip; before: Chip }) {
  const COL = (INNER - 32) / 2;
  const row = (head: string, body: string, strong = false) => h('div', { display: 'flex', flexDirection: 'column', paddingTop: 18, paddingBottom: 18, borderTop: `3px solid ${INK}` },
    h('div', { fontSize: 26, color: '#444' }, head),
    h('div', { fontSize: strong ? 44 : 38, fontWeight: 700, lineHeight: 1.1, marginTop: 6, color: strong ? SIGNAL : INK }, body));
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
      h('div', { width: INNER, fontSize: 64, fontWeight: 700, lineHeight: 1.0, letterSpacing: -2 }, 'A licence to explore, not to mine'),
      h('div', { display: 'flex', gap: 32, marginTop: 48 },
        h('div', { display: 'flex', flexDirection: 'column', width: COL },
          h('div', { fontSize: 30, fontWeight: 700, marginBottom: 14 }, 'The register'),
          row('Licence on this land', 'Prospecting only'),
          row('It allows', 'Searching for minerals'),
          row('It does not allow', 'Mining', true),
          h('div', { borderTop: `3px solid ${INK}` })),
        h('div', { display: 'flex', flexDirection: 'column', width: COL },
          h('div', { fontSize: 30, fontWeight: 700, marginBottom: 14 }, 'The satellite'),
          h('div', { display: 'flex', position: 'relative', width: COL, height: COL },
            img(await jpeg(o.after), { width: COL, height: COL }),
            img(ring(48), { position: 'absolute', left: COL / 2 - 24, top: COL / 2 - 24, width: 48, height: 48 }),
            h('div', { position: 'absolute', left: 0, bottom: 0, background: INK, color: '#fff', fontSize: 22, fontWeight: 700, padding: '5px 10px' }, `After, ${shortDate(o.after.date)}`)),
          h('div', { display: 'flex', position: 'relative', width: COL, height: 150, marginTop: 16, overflow: 'hidden' },
            img(await jpeg(o.before), { position: 'absolute', left: 0, top: -(COL - 150) / 2, width: COL, height: COL }),
            h('div', { position: 'absolute', left: 0, bottom: 0, background: INK, color: '#fff', fontSize: 22, fontWeight: 700, padding: '5px 10px' }, `Before, ${shortDate(o.before.date)}`)))),
      h('div', { width: INNER, fontSize: 40, fontWeight: 700, lineHeight: 1.2, marginTop: 44 }, `${o.ha} of land cleared ${o.place}.`)),
    footer()),
    PW, PH, 85);
}

// News days: the headline as the story told it, then what the satellite saw at that place
export async function newsPost(o: { headline: string; outlet: string; date: string; place: string; before: Chip; after: Chip; line: string }) {
  const TOP = 450, IMG = PH - TOP - 96, INSET = 230;
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: 52, width: INNER, height: TOP - 52 },
      h('div', { fontSize: 140, fontWeight: 700, lineHeight: 0.8, color: SIGNAL, height: 76 }, '“'),
      h('div', { width: INNER, fontSize: o.headline.length > 90 ? 46 : 54, fontWeight: 700, lineHeight: 1.12, letterSpacing: -1 }, o.headline),
      h('div', { width: INNER, fontSize: 28, color: '#444', marginTop: 18 }, `${o.outlet}, ${o.date}`)),
    h('div', { display: 'flex', position: 'absolute', left: 0, top: TOP, width: PW, height: IMG, overflow: 'hidden' },
      img(await jpeg(o.after), { position: 'absolute', left: 0, top: -(PW - IMG) / 2, width: PW, height: PW }),
      img(ring(60), { position: 'absolute', left: PW / 2 - 30, top: IMG / 2 - 30, width: 60, height: 60 }),
      h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', right: 40, top: 32, border: '5px solid #fff', background: '#fff' },
        img(await jpeg(o.before), { width: INSET, height: INSET }),
        h('div', { fontSize: 22, fontWeight: 700, color: INK, padding: '6px 8px 2px' }, `Before, ${shortDate(o.before.date)}`)),
      h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: 40, bottom: 28, maxWidth: PW - 80, background: INK, color: '#fff', padding: '10px 16px' },
        h('div', { fontSize: 30, fontWeight: 700 }, `What the satellite saw ${o.place}`),
        h('div', { fontSize: 24, color: '#DDD', marginTop: 4 }, o.line))),
    footer()),
    PW, PH, 85);
}

// Ten towns: a ranked table, the ranking itself is the picture
export async function townsPost(o: { title: string; line: string; rows: { name: string; district: string; ha: string }[]; sub: string }) {
  return card(h('div', { display: 'flex', position: 'relative', width: PW, height: PH, background: PAPER, fontFamily: 'Atkinson', color: INK },
    h('div', { display: 'flex', flexDirection: 'column', position: 'absolute', left: PAD, top: PAD, width: INNER },
      h('div', { width: INNER, fontSize: 56, fontWeight: 700, lineHeight: 1.05, letterSpacing: -1 }, o.title),
      h('div', { width: INNER, fontSize: 28, lineHeight: 1.35, marginTop: 12, color: '#333' }, o.line),
      h('div', { display: 'flex', flexDirection: 'column', marginTop: 30, width: INNER },
        ...o.rows.slice(0, 10).map((r, i) => h('div', { display: 'flex', alignItems: 'center', height: i === 0 ? 108 : 78, borderTop: `${i === 0 ? 4 : 2}px solid ${INK}` },
          h('div', { width: 84, fontSize: i === 0 ? 64 : 40, fontWeight: 700, color: SIGNAL }, String(i + 1)),
          h('div', { display: 'flex', flexDirection: 'column', width: 640 },
            h('div', { fontSize: i === 0 ? 46 : 34, fontWeight: 700, lineHeight: 1.05 }, r.name),
            h('div', { fontSize: 22, color: '#555' }, r.district)),
          h('div', { width: INNER - 84 - 640, textAlign: 'right', fontSize: i === 0 ? 46 : 32, fontWeight: 700 }, r.ha)))),
      h('div', { width: INNER, fontSize: 24, lineHeight: 1.35, color: '#333', marginTop: 18 }, o.sub)),
    footer()),
    PW, PH, 85);
}
