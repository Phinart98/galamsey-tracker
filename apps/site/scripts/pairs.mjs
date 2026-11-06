// Both pictures of a place are published as one file, before on the left and after on the right. Half as many
// files as two separate pictures, so the pictures site stays under Cloudflare Pages' 20,000-file limit. The site
// shows each half in its own square box (lib/format.ts chipSrc, global.css img[data-half]).
// Used by prepare-data.mjs (local builds) and deploy-pictures.mjs (the weekly run).
import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';
import { pairRel, retiredBefore } from '../src/lib/pictures.mjs';

const SIDE = 720;

// Writes the pair for one place into `root` (keeping the chips/<id>/ path) from the pictures under `from`.
// Returns the pair's path, or null when a picture is missing on disk.
export async function writePair(from, chips, root) {
  const [before, after] = [chips.before.files['720.webp'], chips.after.files['720.webp']].map((rel) => path.join(from, rel));
  if (!fs.existsSync(before) || !fs.existsSync(after)) return null;
  const rel = pairRel(chips.before.files['720.webp']);
  const dest = path.join(root, rel);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  const [b, a] = await Promise.all([before, after].map((f) => sharp(f).resize(SIDE, SIDE).toBuffer()));
  await sharp({ create: { width: SIDE * 2, height: SIDE, channels: 3, background: '#000' } })
    .composite([{ input: b, left: 0, top: 0 }, { input: a, left: SIDE, top: 0 }])
    .webp({ quality: 80 })
    .toFile(dest);
  return rel;
}

// Every place with both pictures and not retired, a few at a time. Returns how many pairs were written and missed.
export async function writePairs(from, index, root, dataDate) {
  const cutoff = retiredBefore(dataDate);
  const todo = Object.values(index).filter((p) => p.chips?.before && p.chips?.after && (!cutoff || p.last_seen >= cutoff));
  let written = 0;
  let missing = 0;
  for (let i = 0; i < todo.length; i += 16) {
    const done = await Promise.all(todo.slice(i, i + 16).map((p) => writePair(from, p.chips, root)));
    for (const rel of done) rel ? written++ : missing++;
  }
  return { written, missing };
}
