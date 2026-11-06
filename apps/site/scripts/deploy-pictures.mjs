// Publishes the before/after pictures to their own Cloudflare Pages project. The site links to them through
// CHIPS_BASE_URL, so neither deployment comes near Pages' limit of 20,000 files per site.
// Each place with both pictures is published as one pair file (scripts/pairs.mjs), except places retired from
// the site two years after their last change. Older runs also made single, 360 px and AVIF copies: never published.
// Usage: node scripts/deploy-pictures.mjs <project-name>   (after `npx wrangler@4 login` once, or with
// CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID set, as in the weekly workflow).
// The project was made once (2026-10-29) with `wrangler pages project create <name> --production-branch main --force`:
// newer wrangler versions otherwise try to make a Workers project instead of a classic Pages one.
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { writePairs } from './pairs.mjs';

const project = process.argv[2] ?? 'galamsey-tracker-pictures';
const LIMIT = 19000; // Pages refuses more than 20,000: stop with a clear message before that happens
const site = path.resolve(import.meta.dirname, '..');
const out = path.resolve(site, '../../pipeline/out');
const wrangler = process.env.WRANGLER ?? 'npx --yes wrangler@4';

const index = JSON.parse(fs.readFileSync(path.join(out, 'places/index.json'), 'utf8'));
const dataDate = JSON.parse(fs.readFileSync(path.resolve(site, '../../data/summary/latest.json'), 'utf8')).data_date;
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pictures-'));
const { written, missing } = await writePairs(out, index, dir, dataDate);
let files = written;
// KEEP_SINGLES=1 also publishes the single before/after files, for the one run that switches the site to pairs: the
// site still live while this runs links to single files, and keeps working if the new site fails to publish
if (process.env.KEEP_SINGLES === '1') {
  const singles = Object.values(index).filter((p) => p.chips?.before && p.chips?.after)
    .flatMap((p) => [p.chips.before.files?.['720.webp'], p.chips.after.files?.['720.webp']])
    .filter((rel) => rel && fs.existsSync(path.join(out, rel)));
  // Never at the cost of the limit: then the old site's pictures go for the few minutes until the new site is up
  if (written + singles.length > LIMIT) {
    console.log(`::warning::${written + singles.length} files with the single pictures is over ${LIMIT}: publishing the pairs only`);
  } else {
    for (const rel of singles) {
      fs.mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true });
      fs.copyFileSync(path.join(out, rel), path.join(dir, rel));
    }
    files += singles.length;
  }
}
console.log(`pictures: ${written} pairs, ${files} files to publish, ${missing} places listed with pictures not on disk`);
// A warning on the run page long before the hard stop
if (files > 16000) console.log(`::warning::${files} picture files, close to Cloudflare Pages' 20,000. Retire places sooner (src/lib/pictures.mjs RETIRE_YEARS).`);
if (files > LIMIT) throw new Error(`${files} picture files is over ${LIMIT}: Cloudflare Pages takes at most 20,000 per site`);

// Pictures are never meant for search results. A retake overwrites the same file name, so no long cache.
fs.writeFileSync(path.join(dir, '_headers'), '/*\n  X-Robots-Tag: noindex, nofollow\n');
fs.writeFileSync(path.join(dir, 'robots.txt'), 'User-agent: *\nDisallow: /\n');

execSync(`${wrangler} pages deploy "${dir}" --project-name ${project} --branch main --commit-dirty=true`, { stdio: 'inherit' });
