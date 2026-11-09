// The river walk tiles, copied from pipeline/out/rivers (restored from the rivers-state release, where rivers.yml keeps
// each river's data beside its two newest tile sets). Used by prepare-data.mjs (local builds) and deploy-pictures.mjs
// (the weekly run). Both sets are published: the site still live links to the older one until the new site is up.
import fs from 'node:fs';
import path from 'node:path';
import { tileRel } from '../src/lib/pictures.mjs';

// Copies pipeline/out/rivers into `root`/rivers and returns the number of tiles. A river with a tile missing is only
// warned about: the site leaves that river out (src/lib/rivers.ts), and the place pictures and pages still publish.
export function copyRiverTiles(out, root) {
  const dir = path.join(out, 'rivers');
  if (!fs.existsSync(dir)) return 0;
  for (const r of fs.readdirSync(dir).filter((f) => f.endsWith('.json')).map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')))) {
    const missing = r.tiles.map((_, i) => tileRel(r.slug, r.version, i)).filter((rel) => !fs.existsSync(path.join(out, rel)));
    if (missing.length) console.warn(`::warning::river ${r.slug}: ${missing.length} tiles missing (${missing[0]}), so its walk is left off the site`);
  }
  // tiles only: the data (and the course saved with each set) is read at build time, and everything under /rivers/
  // on the pictures site is cached for good
  fs.cpSync(dir, path.join(root, 'rivers'), { recursive: true, filter: (src) => !src.endsWith('.json') });
  return fs.readdirSync(path.join(root, 'rivers'), { recursive: true }).filter((f) => f.endsWith('.webp')).length;
}
