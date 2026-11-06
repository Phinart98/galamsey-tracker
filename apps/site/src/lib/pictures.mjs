// Rules shared by the site (lib/format.ts, lib/data.ts) and the scripts that publish the pictures (scripts/pairs.mjs),
// so the pages and the pictures site always agree. Plain JavaScript with no imports: Node runs it as is.

// A place's two pictures are published as one file, before on the left and after on the right:
// chips/<id>/before-720.webp and chips/<id>/after-720.webp become chips/<id>/pair-720.webp
export const pairRel = (rel) => rel.replace(/(before|after)-720\.webp$/, 'pair-720.webp');

// A place leaves the site (page, share card, pictures) two years after its land last changed. The place index never
// shrinks, and Cloudflare Pages takes at most 20,000 files per site.
export const RETIRE_YEARS = 2;
// The first last_seen date that still keeps a place, or null when there is no data date yet
export const retiredBefore = (dataDate) =>
  dataDate ? `${Number(dataDate.slice(0, 4)) - RETIRE_YEARS}${dataDate.slice(4)}` : null;
