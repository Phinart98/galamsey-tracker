// A private preview on Cloudflare Pages: build with the preview URL, keep it out of search engines, upload.
// The noindex files are written into dist only, never into the source, so the real launch is not affected.
// Usage: npm run deploy:preview -- <project-name>   (after `npx wrangler@4 login` once)
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const project = process.argv[2] ?? 'galamsey-tracker';
const site = path.resolve(import.meta.dirname, '..');
const dist = path.join(site, 'dist');
const run = (cmd, env = {}) => execSync(cmd, { cwd: site, stdio: 'inherit', env: { ...process.env, ...env } });

run('npm run build', { SITE_URL: `https://${project}.pages.dev` });
fs.writeFileSync(path.join(dist, '_headers'), '/*\n  X-Robots-Tag: noindex, nofollow\n');
fs.writeFileSync(path.join(dist, 'robots.txt'), 'User-agent: *\nDisallow: /\n');
run(`npx --yes wrangler@4 pages deploy dist --project-name ${project} --branch main --commit-dirty=true`);
