// Gets the place index (and, locally, the images) that are too big to commit.
// Production: PLACES_INDEX_URL points at index.json on R2 and CHIPS_BASE_URL at the R2 folder.
// Local: both come from pipeline/out, and the images are copied into public/chips.
import fs from 'node:fs';
import path from 'node:path';

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
  if (!process.env.CHIPS_BASE_URL && fs.existsSync(path.join(local, 'chips'))) {
    fs.cpSync(path.join(local, 'chips'), path.join(site, 'public/chips'), { recursive: true });
  }
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
