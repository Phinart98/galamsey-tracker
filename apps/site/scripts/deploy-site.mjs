// Build the site and publish it on Cloudflare Pages.
// Usage: npm run deploy:site -- <project-name>   (after `npx wrangler@4 login` once)
// PREVIEW=1 makes a hidden test copy instead: kept out of search engines, and it does not promise weekly updates.
// The noindex files are written into dist only, never into the source.
// On a slow upload link wrangler's 40 MB batches get cut off: set WRANGLER to a copy patched for smaller batches.
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const LIVE = 'galamsey-tracker';
const project = process.argv[2];
// The build treats any non-empty PREVIEW as a preview, so this script does too
const preview = !!process.env.PREVIEW;
if (!project) throw new Error('Name the Cloudflare Pages project: npm run deploy:site -- <project-name>');
// A hidden copy on the live project would take galamseytracker.org out of search engines
if (preview && project === LIVE) throw new Error(`PREVIEW is set: deploy the hidden copy to another project, not ${LIVE}`);
const site = path.resolve(import.meta.dirname, '..');
const dist = path.join(site, 'dist');
const run = (cmd, env = {}) => execSync(cmd, { cwd: site, stdio: 'inherit', env: { ...process.env, ...env } });

// Pictures live on their own Pages project (deploy-pictures.mjs), never inside this site
const pictures = process.env.CHIPS_BASE_URL ?? 'https://galamsey-tracker-pictures.pages.dev';
// Canonical and share links use the real domain, which serves this same Pages project
const siteUrl = process.env.SITE_URL ?? 'https://galamseytracker.org';
run('npm run build', { SITE_URL: siteUrl, CHIPS_BASE_URL: pictures });
if (preview) {
  fs.writeFileSync(path.join(dist, '_headers'), '/*\n  X-Robots-Tag: noindex, nofollow\n');
  fs.writeFileSync(path.join(dist, 'robots.txt'), 'User-agent: *\nDisallow: /\n');
}
// Pages refuses more than 20,000 files per site: stop with a clear message before that happens
const count = (dir) => fs.readdirSync(dir, { withFileTypes: true }).reduce((n, e) => n + (e.isDirectory() ? count(path.join(dir, e.name)) : 1), 0);
const files = count(dist);
console.log(`site: ${files} files${preview ? ' (hidden preview)' : ''}`);
if (files > 19000) throw new Error(`${files} files is over 19,000: Cloudflare Pages takes at most 20,000 per site`);
run(`${process.env.WRANGLER ?? 'npx --yes wrangler@4'} pages deploy dist --project-name ${project} --branch main --commit-dirty=true`);
