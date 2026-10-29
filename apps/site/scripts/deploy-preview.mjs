// A private preview on Cloudflare Pages: build with the preview URL, keep it out of search engines, upload.
// The noindex files are written into dist only, never into the source, so the real launch is not affected.
// Usage: npm run deploy:preview -- <project-name>   (after `npx wrangler@4 login` once)
// On a slow upload link wrangler's 40 MB batches get cut off: set WRANGLER to a copy patched for smaller batches.
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const project = process.argv[2] ?? 'galamsey-tracker';
const site = path.resolve(import.meta.dirname, '..');
const dist = path.join(site, 'dist');
const run = (cmd, env = {}) => execSync(cmd, { cwd: site, stdio: 'inherit', env: { ...process.env, ...env } });

// Pictures live on their own Pages project (deploy-pictures.mjs), never inside this site
const pictures = process.env.CHIPS_BASE_URL ?? 'https://galamsey-tracker-pictures.pages.dev';
run('npm run build', { SITE_URL: `https://${project}.pages.dev`, PREVIEW: '1', CHIPS_BASE_URL: pictures });
fs.writeFileSync(path.join(dist, '_headers'), '/*\n  X-Robots-Tag: noindex, nofollow\n');
fs.writeFileSync(path.join(dist, 'robots.txt'), 'User-agent: *\nDisallow: /\n');
// Pages refuses more than 20,000 files per site: stop with a clear message before that happens
const count = (dir) => fs.readdirSync(dir, { withFileTypes: true }).reduce((n, e) => n + (e.isDirectory() ? count(path.join(dir, e.name)) : 1), 0);
const files = count(dist);
console.log(`site: ${files} files`);
if (files > 19000) throw new Error(`${files} files is over 19,000: Cloudflare Pages takes at most 20,000 per site`);
run(`${process.env.WRANGLER ?? 'npx --yes wrangler@4'} pages deploy dist --project-name ${project} --branch main --commit-dirty=true`);
