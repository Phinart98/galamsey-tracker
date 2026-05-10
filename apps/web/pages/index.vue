<script setup lang="ts">
import type { AlertTimeRange, LayerKey, HotspotId } from '~/types/dashboard'

const { resolvedTheme } = useTheme()
const { initMap, setBasemap, setLayerVisibility, setAlertsTimeRange } = useMap()
const { isMobile } = useViewport()

const mapContainerRef = ref<HTMLElement | null>(null)
const mapReady        = ref(false)
const sheetExpanded   = ref(false)

const layers = ref<Record<LayerKey, boolean>>({
  gfw:       true,
  sar:       true,
  turbidity: true,
  reserves:  true,
})

const timeRange = ref<AlertTimeRange>({ pill: '30d', sliderVal: 1 })

const activeHotspot = ref<HotspotId | null>(null)

function toggleSheet() {
  sheetExpanded.value = !sheetExpanded.value
}

// Auto-collapse the rail when a hotspot opens on mobile
watch(activeHotspot, (id) => {
  if (id && isMobile.value) sheetExpanded.value = false
})

function closeDetail() {
  activeHotspot.value = null
  // Restore the rail so the user lands back on the layer list, not a blank map
  if (isMobile.value) sheetExpanded.value = true
}

onMounted(async () => {
  if (!mapContainerRef.value) return

  await initMap(mapContainerRef.value, resolvedTheme.value, layers.value)
  mapReady.value = true

  // Swap basemap when theme changes (re-adds synthetic data after style.load)
  watch(resolvedTheme, t => setBasemap(t, layers.value))

  // Toggle individual layers when switches change
  watch(
    layers,
    l => {
      for (const [key, visible] of Object.entries(l) as [LayerKey, boolean][]) {
        setLayerVisibility(key, visible)
      }
    },
    { deep: true },
  )

  // Re-fetch Martin tiles when the time slider changes
  watch(timeRange, r => setAlertsTimeRange(r), { deep: true })
})
</script>

<template>
  <!-- h-dvh: dynamic viewport height — avoids iOS Safari URL-bar resize crop -->
  <div class="app-shell flex h-dvh overflow-hidden bg-surface-canvas text-surface-fg">
    <!-- Left rail / mobile bottom sheet -->
    <TheRail
      v-model:layers="layers"
      v-model:time-range="timeRange"
      :active-hotspot="activeHotspot"
      :expanded="sheetExpanded"
      @select-hotspot="activeHotspot = $event"
      @toggle-sheet="toggleSheet"
    />

    <!-- Map canvas -->
    <main
      ref="mapContainerRef"
      class="relative flex-1 overflow-hidden min-h-0"
    >
      <!-- Mobile "Layers" FAB — hidden on desktop via CSS -->
      <button
        class="mobile-layers-btn"
        aria-label="Toggle layers panel"
        @click="toggleSheet"
      >
        &#9776; Layers
      </button>

      <!-- Overlays render once map is mounted so they appear above the canvas -->
      <template v-if="mapReady">
        <MapLegend :layers="layers" />
        <DetailPanel
          :hotspot-id="activeHotspot"
          @close="closeDetail"
        />
      </template>
    </main>
  </div>
</template>
