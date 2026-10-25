// Shared helpers for the v2 mockups: real numbers and pictures from data.json
export const fmt = new Intl.NumberFormat('en-GB');
export const num = (n) => fmt.format(Math.round(n));
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
export const longDate = (iso) => { const [y, m, d] = iso.split('-').map(Number); return `${d} ${MONTHS[m - 1]} ${y}`; };
export const shortDate = (iso) => { const [y, m, d] = iso.split('-').map(Number); return `${d} ${MONTHS[m - 1].slice(0, 3)} ${y}`; };
// OSM names are third-party text, so every data string is escaped before it goes into markup
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
export const tidy = (d) => esc((d || '').replace(/\/(\w)/g, (_, c) => `/${c.toUpperCase()}`));
export const data = await (await fetch('data.json')).json();
export const $ = (s) => document.querySelector(s);
export const html = (s) => { const t = document.createElement('template'); t.innerHTML = s.trim(); return t.content; };

// The settled trend as a small line chart, with provisional months dashed
export function trendSvg(points, w = 600, h = 160) {
  const max = Math.max(...points.map((p) => p.ha)) * 1.1;
  const x = (i) => (i / (points.length - 1)) * w;
  const y = (v) => h - (v / max) * h;
  const settled = points.filter((p) => p.settled);
  const line = (ps, off) => ps.map((p, i) => `${i ? 'L' : 'M'}${x(i + off).toFixed(1)},${y(p.ha).toFixed(1)}`).join('');
  const firstOpen = points.findIndex((p) => !p.settled);
  const open = firstOpen > 0 ? points.slice(firstOpen - 1) : [];
  return `<svg viewBox="0 0 ${w} ${h + 24}" width="100%" role="img" aria-label="Hectares cleared in the 12 months before each month, January 2024 to September 2026">
    <line x1="0" x2="${w}" y1="${h}" y2="${h}" stroke="var(--line)"/>
    <path d="${line(settled, 0)}" fill="none" stroke="var(--ink)" stroke-width="2.5"/>
    ${open.length ? `<path d="${line(open, firstOpen - 1)}" fill="none" stroke="var(--ink)" stroke-width="2" stroke-dasharray="5 4"/>` : ''}
    <text x="0" y="${h + 18}" font-size="13" fill="var(--muted)">2024</text>
    <text x="${x(12)}" y="${h + 18}" font-size="13" fill="var(--muted)">2025</text>
    <text x="${x(24)}" y="${h + 18}" font-size="13" fill="var(--muted)">2026</text>
  </svg>`;
}
