import type { Hotspot, HeroStat, HotspotDetail, HotspotId } from '~/types/dashboard'

// Minimal GeoJSON shape types (avoids depending on 'geojson' pkg not hoisted by pnpm)
type GeoPoint   = { type: 'Point';      coordinates: [number, number] }
type GeoLine    = { type: 'LineString'; coordinates: [number, number][] }
type GeoPoly    = { type: 'Polygon';    coordinates: [number, number][][] }
type Feature<G> = { type: 'Feature'; properties: Record<string, unknown>; geometry: G }
type FC<G>      = { type: 'FeatureCollection'; features: Feature<G>[] }

export const HOTSPOTS: Hotspot[] = [
  { id: 'wassa', name: 'Wassa Amenfi',  region: 'Western Region',    coords: [-2.05, 5.35], alerts: 234 },
  { id: 'atewa', name: 'Atewa Range',   region: 'Eastern Region',    coords: [-0.55, 6.20], alerts: 187 },
  { id: 'birim', name: 'Birim North',   region: 'Eastern Region',    coords: [-1.05, 6.35], alerts: 143 },
  { id: 'tano',  name: 'Tano Nimiri',   region: 'Brong-Ahafo',       coords: [-2.50, 7.15], alerts: 98  },
  { id: 'pra',   name: 'Pra Basin',     region: 'Central / Western', coords: [-1.60, 5.70], alerts: 312 },
]

export const HERO_STATS: HeroStat[] = [
  { num: '60%',    cap: "of Ghana's water bodies polluted by mercury and cyanide leaching from galamsey operations" },
  { num: '44',     cap: 'of 288 forest reserves degraded or actively invaded by illegal artisanal mining' },
  { num: '7,000+', cap: 'excavators active across mining corridors, many unregistered and unmonitored' },
]

export const DETAIL_DATA: Record<HotspotId, HotspotDetail> = {
  wassa: {
    title: 'Wassa Amenfi West',
    alerts: 234, excavators: 47, rivers: 12,
    description: 'One of the most heavily mined corridors in Ghana, Wassa Amenfi has seen near-total deforestation of its riparian zones since 2018.',
    incidents: [
      { id: 'GHA-0441', desc: 'Excavator convoy detected on Ankobra River tributary',           date: '2026-04-29' },
      { id: 'GHA-0438', desc: 'Mercury discharge event, community report + SAR confirmation',   date: '2026-04-22' },
      { id: 'GHA-0421', desc: 'Security forces confrontation, 3 excavators seized',             date: '2026-04-09' },
    ],
  },
  atewa: {
    title: 'Atewa Range Forest Reserve',
    alerts: 187, excavators: 31, rivers: 8,
    description: 'The Atewa Range is the source of three major rivers supplying water to 5 million Ghanaians. Mining within the reserve boundary has tripled since 2022.',
    incidents: [
      { id: 'GHA-0399', desc: 'Reserve boundary breach, 2.3 ha clearing detected by Sentinel-2', date: '2026-04-25' },
      { id: 'GHA-0387', desc: 'Headwaters turbidity spike, NTU index 340% above baseline',        date: '2026-04-18' },
    ],
  },
  birim: {
    title: 'Birim North District',
    alerts: 143, excavators: 22, rivers: 6,
    description: 'The Birim River, once a key water source, now runs ochre-brown year-round through this district.',
    incidents: [
      { id: 'GHA-0362', desc: 'Clandestine sluice box operation dismantled',                date: '2026-04-20' },
      { id: 'GHA-0351', desc: 'Night-time excavation detected via SAR coherence change',    date: '2026-04-12' },
    ],
  },
  tano: {
    title: 'Tano Nimiri Forest Reserve',
    alerts: 98, excavators: 15, rivers: 4,
    description: 'A UNESCO-designated important bird area now facing systematic encroachment. Satellite analysis shows 14% canopy loss in 18 months.',
    incidents: [
      { id: 'GHA-0319', desc: 'Armed miners camp found, 18 excavators, forest service access blocked', date: '2026-04-15' },
    ],
  },
  pra: {
    title: 'Pra River Basin',
    alerts: 312, excavators: 68, rivers: 22,
    description: 'The Pra Basin represents the most severe cumulative impact zone. Mercury levels now exceed WHO safe limits by 12x.',
    incidents: [
      { id: 'GHA-0471', desc: 'Mass fish die-off, 40 km stretch, cause under investigation', date: '2026-04-30' },
      { id: 'GHA-0464', desc: 'Illegal dredge boat operational, AIS spoofing suspected',     date: '2026-04-27' },
      { id: 'GHA-0455', desc: 'Community blockade of mining access road',                    date: '2026-04-21' },
      { id: 'GHA-0440', desc: 'MIDAS radar confirmed 12 new excavation pits',               date: '2026-04-16' },
    ],
  },
}

export const BASEMAP_URLS = {
  light: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  dark:  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
} as const

export const TIME_OPTIONS = ['7d', '30d', '90d', '365d', 'custom'] as const

export function generateAlerts(): FC<GeoPoint> {
  const features: Feature<GeoPoint>[] = []
  for (const h of HOTSPOTS) {
    const count = Math.floor(h.alerts / 15)
    for (let i = 0; i < count; i++) {
      features.push({
        type: 'Feature',
        properties: {
          id: `GHA-${String(Math.floor(Math.random() * 9000) + 1000)}`,
          kind: Math.random() > 0.4 ? 'alert' : 'citizen',
          hotspot: h.id,
        },
        geometry: {
          type: 'Point',
          coordinates: [
            h.coords[0] + (Math.random() - 0.5) * 0.8,
            h.coords[1] + (Math.random() - 0.5) * 0.8,
          ],
        },
      })
    }
  }
  return { type: 'FeatureCollection', features }
}

export function generateRivers(): FC<GeoLine> {
  return {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', properties: { severity: 0.9 }, geometry: { type: 'LineString', coordinates: [[-1.8,5.5],[-1.65,5.6],[-1.55,5.75],[-1.45,5.9]] } },
      { type: 'Feature', properties: { severity: 0.7 }, geometry: { type: 'LineString', coordinates: [[-2.1,5.2],[-2.0,5.35],[-1.9,5.5],[-1.8,5.6]] } },
      { type: 'Feature', properties: { severity: 0.6 }, geometry: { type: 'LineString', coordinates: [[-0.6,6.1],[-0.55,6.2],[-0.5,6.3],[-0.42,6.45]] } },
      { type: 'Feature', properties: { severity: 0.5 }, geometry: { type: 'LineString', coordinates: [[-1.1,6.2],[-1.05,6.35],[-0.95,6.5]] } },
      { type: 'Feature', properties: { severity: 0.8 }, geometry: { type: 'LineString', coordinates: [[-2.55,7.0],[-2.5,7.15],[-2.4,7.3]] } },
    ],
  }
}

export function generateReserves(): FC<GeoPoly> {
  return {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', properties: { name: 'Atewa Range' }, geometry: { type: 'Polygon', coordinates: [[[-0.65,6.1],[-0.45,6.1],[-0.45,6.35],[-0.65,6.35],[-0.65,6.1]]] } },
      { type: 'Feature', properties: { name: 'Tano Nimiri' }, geometry: { type: 'Polygon', coordinates: [[[-2.65,7.05],[-2.35,7.05],[-2.35,7.25],[-2.65,7.25],[-2.65,7.05]]] } },
      { type: 'Feature', properties: { name: 'Oda River'   }, geometry: { type: 'Polygon', coordinates: [[[-1.15,6.15],[-0.90,6.15],[-0.90,6.40],[-1.15,6.40],[-1.15,6.15]]] } },
    ],
  }
}
