// The water treatment plants downstream of the areas we cover, used by the home page and the share images.
import fs from 'node:fs';
import path from 'node:path';

// Who each plant supplies and what the news reported, each checked against the article
// (docs/sources.json claims water-plant-towns and plant-news). Only news that ties the plant to mud or mining,
// the latest relevant report first.
export const PLANTS: Record<string, { supplies: string; news: { when: string; text: string; src: string; outlet: string }[] }> = {
  Daboase: { supplies: 'Sekondi-Takoradi, with the Inchaban plant', news: [
    { when: 'August 2026', text: "Mud in the Pra at Daboase reached more than 20 times the permitted level. Drone footage showed mining right opposite the plant's intake.", src: 'citi-daboase-2026', outlet: 'Citi Newsroom' },
  ] },
  Weija: { supplies: 'central and western Accra', news: [
    { when: 'May 2026', text: 'Potroase, where the Densu comes down from the Atewa hills, has become a hotspot for illegal mining. Water Resources Commission data show the river getting dirtier there and at Weija over five years.', src: 'fourth-estate-2026-water', outlet: 'The Fourth Estate' },
  ] },
  Kwanyako: { supplies: 'Winneba, Swedru and Kasoa', news: [
    { when: 'September 2025', text: 'Ghana Water said mud in the Ayensu reached more than 12 times what the plant was built to treat.', src: 'gwcl-kwanyako-news', outlet: 'GNA' },
    { when: 'May 2026', text: 'Ghana Water records show the plant was shut for 2,541 hours in 2025, more than 100 days, because of mud and silt.', src: 'fourth-estate-2026-water', outlet: 'The Fourth Estate' },
  ] },
  Barekese: { supplies: 'Greater Kumasi, with Owabi', news: [
    { when: 'April 2025', text: "Ghana Water raised prices partly over the cost of treating water hit by illegal mining. Its Ashanti manager warned that if the Offin, Barekese's main source, is not protected, Barekese will be down.", src: 'joy-barekese-2025', outlet: 'MyJoyOnline' },
  ] },
  Owabi: { supplies: 'Greater Kumasi, with Barekese', news: [] },
};

type Ring = number[][];
type PlantFeature = { properties: { plant: string; plant_lat: number; plant_lon: number }; geometry: { type: string; coordinates: any } };
export type Plant = { name: string; lat: number; lon: number; polys: Ring[][] };
const plantsFile = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), '../../pipeline/water_plants.geojson'), 'utf8')) as { features: PlantFeature[] };
// Each plant with the land that drains to it (pipeline/water_plants.geojson)
export const catchments: Plant[] = plantsFile.features.map((f) => ({
  name: f.properties.plant, lat: f.properties.plant_lat, lon: f.properties.plant_lon,
  polys: (f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates) as Ring[][],
}));

export function inside([lon, lat]: number[], polys: Ring[][]) {
  let hit = false;
  for (const poly of polys) for (const r of poly) {
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const [xi, yi] = r[i], [xj, yj] = r[j];
      if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) hit = !hit;
    }
  }
  return hit;
}
