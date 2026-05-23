// Inline type avoids top-level module resolution of maplibre-gl in SSR bundle.
type MapLibreMap = import('maplibre-gl').Map
type VectorTileSource = import('maplibre-gl').VectorTileSource

import type { AlertTimeRange, ThemeResolved } from '~/types/dashboard'
import { rangeToFromTo } from '~/composables/useTimeRange'

const MVT_SOURCE_LAYER = 'sar_alerts'

export const SAR_LAYER_IDS = ['sar-fill', 'sar-outline'] as const

// SAR fills use --laterite-deep with theme-dependent opacity. The CSS variable
// in main.css is the source of truth for the editorial pages; MapLibre paint
// can't read CSS vars so we mirror the values here.
const SAR_OPACITY: Record<ThemeResolved, number> = {
  light: 0.25,
  dark: 0.35,
}

// Shared across the single MapLibre instance, same approach as useAlertsLayer.
let _range: AlertTimeRange = { pill: '30d', sliderVal: 1 }

function buildTilesUrl(martinBaseUrl: string, range: AlertTimeRange): string {
  const { from, to } = rangeToFromTo(range)
  // min_confidence=medium hides the 'low' bucket on the dashboard by default
  // (those polygons are kept in PostGIS but never load on the main map).
  const qs = new URLSearchParams({ from, to, min_confidence: 'medium' }).toString()
  return `${martinBaseUrl}/sar_alerts_mvt/{z}/{x}/{y}?${qs}`
}

export const useSarLayer = () => {
  const { public: { martinBaseUrl } } = useRuntimeConfig()

  function currentTilesUrl(): string {
    return buildTilesUrl(martinBaseUrl, _range)
  }

  function add(map: MapLibreMap, theme: ThemeResolved): void {
    if (!map.getSource('sar-tiles')) {
      map.addSource('sar-tiles', {
        type: 'vector',
        tiles: [currentTilesUrl()],
        minzoom: 4,
        maxzoom: 14,
      })
    }
    if (!map.getLayer('sar-fill')) {
      map.addLayer({
        id: 'sar-fill',
        type: 'fill',
        source: 'sar-tiles',
        'source-layer': MVT_SOURCE_LAYER,
        paint: {
          'fill-color': '#7A2E1A',
          'fill-opacity': SAR_OPACITY[theme],
        },
      })
    }
    if (!map.getLayer('sar-outline')) {
      map.addLayer({
        id: 'sar-outline',
        type: 'line',
        source: 'sar-tiles',
        'source-layer': MVT_SOURCE_LAYER,
        paint: {
          'line-color': '#7A2E1A',
          'line-width': 1,
          'line-opacity': 0.8,
        },
      })
    }
  }

  function setTimeRange(map: MapLibreMap, range: AlertTimeRange): void {
    _range = range
    const src = map.getSource('sar-tiles') as VectorTileSource | undefined
    src?.setTiles([currentTilesUrl()])
  }

  return { add, setTimeRange }
}
