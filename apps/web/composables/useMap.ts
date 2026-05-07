// Inline type avoids top-level module resolution of maplibre-gl in SSR bundle.
type MapLibreMap = import('maplibre-gl').Map

import type { LayerKey, ThemeResolved } from '~/types/dashboard'
import { BASEMAP_URLS, generateAlerts, generateRivers, generateReserves } from '~/composables/useSyntheticData'

// Maps UI toggle keys to the MapLibre layer IDs they control.
const LAYER_MAP: Record<LayerKey, string[]> = {
  gfw:       ['alerts-dot', 'alerts-glow'],
  sar:       ['citizen-dot'],
  turbidity: ['rivers'],
  reserves:  ['reserves-fill', 'reserves-outline'],
}

// Lazily initialised so the generators don't run during SSR module evaluation.
let _alertData:   ReturnType<typeof generateAlerts>   | null = null
let _riverData:   ReturnType<typeof generateRivers>   | null = null
let _reserveData: ReturnType<typeof generateReserves> | null = null

function getSyntheticData() {
  if (!_alertData)   _alertData   = generateAlerts()
  if (!_riverData)   _riverData   = generateRivers()
  if (!_reserveData) _reserveData = generateReserves()
  return { alerts: _alertData, rivers: _riverData, reserves: _reserveData }
}

export const useMap = () => {
  // MapLibreMap's type depth triggers TS2589 with ref<T> — any is intentional here.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = ref<any>(null)
  const ready  = ref(false)

  function addSyntheticData(map: MapLibreMap, theme: ThemeResolved) {
    const citizenColor = theme === 'light' ? '#7A2E1A' : '#D9C9B0'
    const { alerts, rivers, reserves } = getSyntheticData()

    if (!map.getSource('reserves')) {
      map.addSource('reserves', { type: 'geojson', data: reserves })
    }
    if (!map.getLayer('reserves-fill')) {
      map.addLayer({
        id: 'reserves-fill',
        type: 'fill',
        source: 'reserves',
        paint: { 'fill-color': '#1A4030', 'fill-opacity': 0.25 },
      })
    }
    if (!map.getLayer('reserves-outline')) {
      map.addLayer({
        id: 'reserves-outline',
        type: 'line',
        source: 'reserves',
        paint: { 'line-color': '#1A4030', 'line-width': 1.5, 'line-dasharray': [3, 2] },
      })
    }

    if (!map.getSource('rivers')) {
      map.addSource('rivers', { type: 'geojson', data: rivers })
    }
    if (!map.getLayer('rivers')) {
      map.addLayer({
        id: 'rivers',
        type: 'line',
        source: 'rivers',
        paint: {
          'line-color': ['interpolate', ['linear'], ['get', 'severity'],
            0.4, '#C4926B',
            0.7, '#B8472A',
            1.0, '#7A2E1A',
          ],
          'line-width': ['interpolate', ['linear'], ['get', 'severity'], 0.4, 2, 1.0, 4],
          'line-opacity': 0.85,
        },
      })
    }

    if (!map.getSource('alerts')) {
      map.addSource('alerts', { type: 'geojson', data: alerts })
    }
    if (!map.getLayer('alerts-glow')) {
      map.addLayer({
        id: 'alerts-glow',
        type: 'circle',
        source: 'alerts',
        filter: ['==', ['get', 'kind'], 'alert'],
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
        source: 'alerts',
        filter: ['==', ['get', 'kind'], 'alert'],
        paint: {
          'circle-radius': 4,
          'circle-color': '#B8472A',
          'circle-stroke-width': 1,
          'circle-stroke-color': '#F5F1EA',
        },
      })
    }
    if (!map.getLayer('citizen-dot')) {
      map.addLayer({
        id: 'citizen-dot',
        type: 'circle',
        source: 'alerts',
        filter: ['==', ['get', 'kind'], 'citizen'],
        paint: {
          'circle-radius': 5,
          'circle-color': citizenColor,
          'circle-stroke-width': 1.5,
          'circle-stroke-color': theme === 'light' ? '#F5F1EA' : '#0F1410',
        },
      })
    }
  }

  function applyLayerVisibility(map: MapLibreMap, layers: Record<LayerKey, boolean>) {
    for (const [key, visible] of Object.entries(layers) as [LayerKey, boolean][]) {
      const ids = LAYER_MAP[key]
      for (const id of ids) {
        if (map.getLayer(id)) {
          map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
        }
      }
    }
  }

  async function initMap(
    container: HTMLElement,
    theme: ThemeResolved,
    layers: Record<LayerKey, boolean>,
  ) {
    const maplibregl = await import('maplibre-gl')

    const map = new maplibregl.Map({
      container,
      style: BASEMAP_URLS[theme],
      center: [-1.0232, 7.9465],  // Ghana centroid
      zoom: 6.5,
      attributionControl: false,
    })

    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')

    map.once('load', () => {
      addSyntheticData(map, theme)
      applyLayerVisibility(map, layers)
      ready.value = true
    })

    mapRef.value = map
    return map
  }

  function setBasemap(theme: ThemeResolved, layers: Record<LayerKey, boolean>) {
    if (!mapRef.value) return
    const map = mapRef.value as MapLibreMap
    map.setStyle(BASEMAP_URLS[theme])
    map.once('style.load', () => {
      addSyntheticData(map, theme)
      applyLayerVisibility(map, layers)
    })
  }

  function setLayerVisibility(key: LayerKey, visible: boolean) {
    if (!mapRef.value || !ready.value) return
    const map = mapRef.value as MapLibreMap
    for (const id of LAYER_MAP[key]) {
      if (map.getLayer(id)) {
        map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
      }
    }
  }

  function getMap(): MapLibreMap | null {
    return mapRef.value as MapLibreMap | null
  }

  onUnmounted(() => {
    if (mapRef.value) {
      (mapRef.value as MapLibreMap).remove()
      mapRef.value = null
      ready.value = false
    }
  })

  return { ready, initMap, setBasemap, setLayerVisibility, getMap }
}
