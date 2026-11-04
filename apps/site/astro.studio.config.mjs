// @ts-check
// The private posting studio: this week's images and words, the plan and the calendar. Built from the same code as
// the site (src/lib), published to its own Cloudflare Pages project, never linked from the site.
import { defineConfig } from 'astro/config';

export default defineConfig({
  output: 'static',
  // Links inside the posts point at the real site
  site: process.env.SITE_URL || 'https://galamseytracker.org',
  srcDir: './src-studio',
  publicDir: './public-studio',
  outDir: './dist-studio',
  trailingSlash: 'ignore',
  compressHTML: true,
});
