// Publishes the before/after pictures to their own Cloudflare Pages project. The site links to them through
// CHIPS_BASE_URL, so neither deployment comes near Pages' limit of 20,000 files per site.
// Only the 720 px picture of each place that has a pair is published. Older runs also made 360 px and AVIF copies.
// Usage: node scripts/deploy-pictures.mjs <project-name>   (after `npx wrangler@4 login` once, or with
// CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID set, as in the weekly workflow).
// The project was made once (2026-10-29) with `wrangler pages project create <name> --production-branch main --force`:
// newer wrangler versions otherwise try to make a Workers project instead of a classic Pages one.
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const project = process.argv[2] ?? 'galamsey-tracker-pictures';
const LIMIT = 19000; // Pages refuses more than 20,000: stop with a clear message before that happens
const site = path.resolve(import.meta.dirname, '..');
const out = path.resolve(site, '../../pipeline/out');
const wrangler = process.env.WRANGLER ?? 'npx --yes wrangler@4';

const index = JSON.parse(fs.readFileSync(path.join(out, 'places/index.json'), 'utf8'));
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pictures-'));
let copied = 0;
let missing = 0;
for (const place of Object.values(index)) {
  const chips = place.chips;
  if (!chips?.before || !chips?.after) continue;
  for (const side of ['before', 'after']) {
    const rel = chips[side].files?.['720.webp'];
    if (!rel || !fs.existsSync(path.join(out, rel))) { missing++; continue; }
    const from = path.join(out, rel);
    fs.mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true });
    fs.copyFileSync(from, path.join(dir, rel));
    copied++;
  }
}
console.log(`pictures: ${copied} files to publish, ${missing} listed but not on disk`);
// A warning on the run page months before the hard stop: places are never dropped from the index, so this only grows
if (copied > 16000) console.log(`::warning::${copied} picture files, close to Cloudflare Pages' 20,000. Leave out long-inactive places, or move pictures to R2.`);
if (copied > LIMIT) throw new Error(`${copied} picture files is over ${LIMIT}: Cloudflare Pages takes at most 20,000 per site`);

// Pictures are never meant for search results. A retake overwrites the same file name, so no long cache.
fs.writeFileSync(path.join(dir, '_headers'), '/*\n  X-Robots-Tag: noindex, nofollow\n');
fs.writeFileSync(path.join(dir, 'robots.txt'), 'User-agent: *\nDisallow: /\n');

execSync(`${wrangler} pages deploy "${dir}" --project-name ${project} --branch main --commit-dirty=true`, { stdio: 'inherit' });
