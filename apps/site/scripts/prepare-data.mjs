// Gets the place index (and, locally, the images) that are too big to commit.
// Normally both come from pipeline/out (locally, and in the weekly workflow after it restores its working files),
// and each place's two images are joined into one pair file in public/chips (scripts/pairs.mjs). PLACES_INDEX_URL
// and CHIPS_BASE_URL can point at a remote copy instead.
import fs from 'node:fs';
import path from 'node:path';
import { writePairs } from './pairs.mjs';
import { copyRiverTiles } from './rivers.mjs';

const site = path.resolve(import.meta.dirname, '..');
const out = path.join(site, '.data');
const local = path.resolve(site, '../../pipeline/out');
fs.mkdirSync(out, { recursive: true });

let index = {};
if (process.env.PLACES_INDEX_URL) {
  const r = await fetch(process.env.PLACES_INDEX_URL);
  if (!r.ok) throw new Error(`place index: HTTP ${r.status}`);
  index = await r.json();
} else if (fs.existsSync(path.join(local, 'places/index.json'))) {
  index = JSON.parse(fs.readFileSync(path.join(local, 'places/index.json'), 'utf8'));
  // Clear old copies first, so pictures published on their own site (CHIPS_BASE_URL) are never also deployed here
  fs.rmSync(path.join(site, 'public/chips'), { recursive: true, force: true });
  fs.rmSync(path.join(site, 'public/rivers'), { recursive: true, force: true });
  if (!process.env.CHIPS_BASE_URL && fs.existsSync(path.join(local, 'chips'))) {
    const latest = path.resolve(site, '../../data/summary/latest.json');
    const dataDate = fs.existsSync(latest) ? JSON.parse(fs.readFileSync(latest, 'utf8')).data_date : null;
    const { written } = await writePairs(local, index, path.join(site, 'public'), dataDate);
    console.log(`prepare-data: ${written} picture pairs in public/chips`);
  }
  // River tiles whenever there are any: the site lists every river whose tiles are in pipeline/out (lib/rivers.ts)
  if (!process.env.CHIPS_BASE_URL) console.log(`prepare-data: ${copyRiverTiles(local, path.join(site, 'public'))} river tiles in public/rivers`);
} else {
  console.warn('prepare-data: no place index found, building without places');
}
fs.writeFileSync(path.join(out, 'places.json'), JSON.stringify(index));

// MapLibre loads its worker from next to its own file, which a bundler breaks. Serve its ES files as is.
const ml = path.join(site, 'node_modules/maplibre-gl');
const mlVersion = JSON.parse(fs.readFileSync(path.join(ml, 'package.json'), 'utf8')).version;
const vendor = path.join(site, 'public/vendor', `maplibre-${mlVersion}`);
if (!fs.existsSync(vendor)) {
  fs.rmSync(path.join(site, 'public/vendor'), { recursive: true, force: true });
  fs.mkdirSync(vendor, { recursive: true });
  for (const f of ['maplibre-gl.mjs', 'maplibre-gl-shared.mjs', 'maplibre-gl-worker.mjs', 'maplibre-gl.css']) {
    fs.copyFileSync(path.join(ml, 'dist', f), path.join(vendor, f));
  }
}
fs.writeFileSync(path.join(out, 'maplibre.json'), JSON.stringify({ base: `/vendor/maplibre-${mlVersion}` }));
console.log(`prepare-data: ${Object.keys(index).length} places`);
