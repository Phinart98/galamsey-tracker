// Every post the studio can offer this week, rebuilt from the latest data by each studio build. Each post is made to
// be quoted: one picture that stands alone, one true fact, no question to the reader, the link in the first reply.
// Wording follows the site: plain English, no em dashes or semicolons, never a verdict on a place.
//
// rules.ts      what a post may show, and the shared lists and rankings (start here)
// town.ts       town of the week, the one-place sample, a place in the news
// water.ts      the cities' water and all five plants
// places.ts     new clearing, shapes, check it yourself, licensed to explore, ten towns, newest patches
// numbers.ts    pitches a day, licence split, districts, patch sizes, the map, the water test, month in review
// explainers.ts how to read the pictures, the licence and the satellites
// ../designs.ts draws each kind of picture; ../plan.ts decides which post goes on which day
import { explainerPosts } from './explainers';
import { numberPosts } from './numbers';
import { placePosts } from './places';
import { townPosts } from './town';
import { waterPosts } from './water';

export type { Pictured, Post } from './rules';
export { showable } from './rules';
export { newsPlacePost } from './town';

export const sharePosts = [...townPosts, ...waterPosts, ...numberPosts, ...placePosts, ...explainerPosts];
