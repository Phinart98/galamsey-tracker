// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  output: 'static',
  site: process.env.SITE_URL || 'https://galamsey-tracker.pages.dev',
  trailingSlash: 'ignore',
  // Astro 7 defaults to 'jsx', which drops the space between adjacent inline elements
  compressHTML: true,
});
