// Inline type avoids top-level module resolution of maplibre-gl in SSR bundle.
type MapLibreMap = import('maplibre-gl').Map
type VectorTileSource = import('maplibre-gl').VectorTileSource

import type { AlertTimeRange, MinConfidence } from '~/types/dashboard'
import { rangeToFromTo } from '~/composables/useTimeRange'

const MVT_SOURCE_LAYER = 'gfw_alerts'

export const ALERTS_LAYER_IDS = ['alerts-glow', 'alerts-dot'] as const

// Shared across the single MapLibre instance so TheRail's slider mutates the
// same 'gfw-tiles' source the layer was created against. Promote to a Pinia
// store if a second map view is ever added.
let _minConfidence: MinConfidence = 'low'
let _range: AlertTimeRange = { pill: '30d', sliderVal: 1 }

function buildTilesUrl(martinBaseUrl: string, range: AlertTimeRange, minConf: MinConfidence): string {
  const { from, to } = rangeToFromTo(range)
  const qs = new URLSearchParams({ from, to, min_confidence: minConf }).toString()
  // {z}/{x}/{y} are MapLibre placeholders, kept unencoded so the runtime can substitute.
  return `${martinBaseUrl}/gfw_alerts_mvt/{z}/{x}/{y}?${qs}`
}

export const useAlertsLayer = () => {
  const { public: { martinBaseUrl } } = useRuntimeConfig()

  function currentTilesUrl(): string {
    return buildTilesUrl(martinBaseUrl, _range, _minConfidence)
  }

  function add(map: MapLibreMap): void {
    if (!map.getSource('gfw-tiles')) {
      map.addSource('gfw-tiles', {
        type: 'vector',
        tiles: [currentTilesUrl()],
        minzoom: 4,
        maxzoom: 14,
      })
    }
    if (!map.getLayer('alerts-glow')) {
      map.addLayer({
        id: 'alerts-glow',
        type: 'circle',
        source: 'gfw-tiles',
        'source-layer': MVT_SOURCE_LAYER,
        paint: {
          'circle-radius': 10,
          'circle-color': '#B8472A',
          'circle-opacity': 0.15,
          'circle-blur': 1,
        },
      })
    }
    if (!map.getLayer('alerts-dot')) {
      map.addLayer({
        id: 'alerts-dot',
        type: 'circle',
        source: 'gfw-tiles',
        'source-layer': MVT_SOURCE_LAYER,
        paint: {
          'circle-radius': 4,
          'circle-color': '#B8472A',
          'circle-stroke-width': 1,
          'circle-stroke-color': '#F5F1EA',
        },
      })
    }
  }

  function setTimeRange(map: MapLibreMap, range: AlertTimeRange): void {
    _range = range
    const src = map.getSource('gfw-tiles') as VectorTileSource | undefined
    src?.setTiles([currentTilesUrl()])
  }

  return { add, setTimeRange }
}
