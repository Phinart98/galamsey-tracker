<script setup lang="ts">
import type { AlertTimeRange, LayerKey, HotspotId, TimeRangePill } from '~/types/dashboard'
import { HOTSPOTS, HERO_STATS, TIME_OPTIONS } from '~/composables/useSyntheticData'
import { rangeToFromTo } from '~/composables/useTimeRange'

const props = defineProps<{
  layers: Record<LayerKey, boolean>
  activeHotspot: HotspotId | null
  expanded: boolean
}>()

const emit = defineEmits<{
  'update:layers': [layers: Record<LayerKey, boolean>]
  'select-hotspot': [id: HotspotId]
  'toggle-sheet': []
}>()

// Two-way bound from pages/index.vue. Default 30d window ending today
// is the most useful first impression for a dashboard ("what's happening lately").
const timeRange = defineModel<AlertTimeRange>('timeRange', {
  default: () => ({ pill: '30d' as TimeRangePill, sliderVal: 1 }),
})

const { mode, setMode } = useTheme()
const { isMobile } = useViewport()

// ── Hero stat rotation ─────────────────────────────────────────────────────
const statIndex = ref(0)
let rotationTimer: ReturnType<typeof setInterval> | null = null

function startRotation() {
  if (rotationTimer) return
  rotationTimer = setInterval(() => {
    statIndex.value = (statIndex.value + 1) % HERO_STATS.length
  }, 6000)
}

function stopRotation() {
  if (rotationTimer) { clearInterval(rotationTimer); rotationTimer = null }
}

onUnmounted(() => stopRotation())

// Suspend rotation when the bottom sheet is collapsed — avoids invisible reflow work.
// Guard with import.meta.client: watchEffect runs during SSR but setInterval is browser-only.
if (import.meta.client) {
  watchEffect(() => {
    const shouldRun = !isMobile.value || props.expanded
    if (shouldRun) startRotation(); else stopRotation()
  })
}

// ── Time slider ────────────────────────────────────────────────────────────
const sliderTrackRef = ref<HTMLElement | null>(null)

const sliderLabel = computed(() => rangeToFromTo(timeRange.value).from)

function setSliderVal(v: number) {
  timeRange.value = { ...timeRange.value, sliderVal: Math.max(0, Math.min(1, v)) }
}

function setPill(p: TimeRangePill) {
  timeRange.value = { ...timeRange.value, pill: p }
}

function onTrackClick(e: MouseEvent) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  setSliderVal((e.clientX - rect.left) / rect.width)
}

let _dragRect: DOMRect | null = null

function startDrag(e: PointerEvent) {
  const thumb = e.currentTarget as HTMLElement
  thumb.setPointerCapture(e.pointerId)
  _dragRect = sliderTrackRef.value?.getBoundingClientRect() ?? null
  thumb.addEventListener('pointermove', onDrag)
  thumb.addEventListener('pointerup', endDrag, { once: true })
}

function onDrag(e: Event) {
  if (!_dragRect) return
  const pe = e as PointerEvent
  setSliderVal((pe.clientX - _dragRect.left) / _dragRect.width)
}

function endDrag(e: Event) {
  _dragRect = null
  ;(e.currentTarget as HTMLElement).removeEventListener('pointermove', onDrag)
}

// ── Layer definitions ──────────────────────────────────────────────────────
const LAYER_GROUPS = [
  {
    label: 'Satellite alerts',
    layers: [
      { key: 'gfw'  as LayerKey, name: 'GFW Integrated',  sub: 'Hansen + GLAD alerts',     color: '#B8472A', shape: 'circle',  peekLabel: 'GFW'       },
      { key: 'sar'  as LayerKey, name: 'Sentinel-1 SAR',  sub: 'Citizen detections',        color: '#7A2E1A', shape: 'square',  peekLabel: 'SAR'       },
    ],
  },
  {
    label: 'Reference & community',
    layers: [
      { key: 'turbidity' as LayerKey, name: 'River turbidity', sub: 'Landsat-derived NTU index', color: '#C4926B', shape: 'line',    peekLabel: 'Turbidity' },
      { key: 'reserves'  as LayerKey, name: 'Forest reserves', sub: 'FC Ghana boundaries',        color: '#1A4030', shape: 'hatched', peekLabel: 'Reserves'  },
    ],
  },
]

const PEEK_LAYERS = LAYER_GROUPS.flatMap(g => g.layers)

function toggleLayer(key: LayerKey) {
  emit('update:layers', { ...props.layers, [key]: !props.layers[key] })
}

// ── Theme icons (minimal inline SVG) ─────────────────────────────────────
const THEME_MODES = [
  { value: 'system' as const, label: 'System', icon: 'M8 1v2M8 13v2M1 8h2M13 8h2M3.22 3.22l1.42 1.42M9.36 9.36l1.42 1.42M3.22 12.78l1.42-1.42M9.36 6.64l1.42-1.42' },
  { value: 'light'  as const, label: 'Light',  icon: 'M8 11A3 3 0 1 0 8 5a3 3 0 0 0 0 6z' },
  { value: 'dark'   as const, label: 'Dark',   icon: 'M6 2a6 6 0 1 0 6 6 4 4 0 0 1-6-6z' },
]
</script>

<template>
  <aside
    class="rail-aside w-[320px] min-w-[320px] flex flex-col overflow-y-auto overflow-x-hidden z-10 relative"
    :class="{ expanded }"
  >
    <!-- Bottom-sheet drag handle (visible only on mobile via CSS) -->
    <div
      class="bottom-sheet-handle"
      @click="emit('toggle-sheet')"
    />

    <!-- Mobile peek bar: the mini-legend in the 56px collapsed strip.
         Shows labeled layer markers + expand arrow. No title — the mast
         section immediately below has the site name. Hidden on desktop. -->
    <div
      class="rail-peek-bar"
      @click="emit('toggle-sheet')"
    >
      <template
        v-for="layer in PEEK_LAYERS"
        :key="layer.key"
      >
        <span
          class="peek-dot"
          :class="layer.key"
          :style="{ opacity: layers[layer.key] ? 1 : 0.22 }"
        />
        <span class="peek-lbl">{{ layer.peekLabel }}</span>
      </template>
      <span class="peek-hint">↑</span>
    </div>

    <!-- Mast -->
    <div class="rail-section animate-fadein-0">
      <div class="mast-title">
        GALAMSEY TRACKER
      </div>
      <div class="mast-sub">
        The watch on Ghana's illegal mining&nbsp;&middot;&nbsp;Est.&nbsp;2026
      </div>
    </div>

    <!-- Hero stat rotation -->
    <div class="rail-section animate-fadein-80">
      <div class="hero-stat-wrap">
        <div
          v-for="(stat, i) in HERO_STATS"
          :key="i"
          class="hero-stat"
          :style="{ opacity: i === statIndex ? 1 : 0, pointerEvents: i === statIndex ? 'auto' : 'none' }"
        >
          <div class="stat-num">
            {{ stat.num }}
          </div>
          <div class="stat-cap">
            {{ stat.cap }}
          </div>
        </div>
      </div>
      <div class="stat-dots">
        <div
          v-for="(_, i) in HERO_STATS"
          :key="i"
          class="stat-dot"
          :class="{ active: i === statIndex }"
          @click="statIndex = i"
        />
      </div>
    </div>

    <!-- Layer toggles -->
    <div class="rail-section animate-fadein-160">
      <div
        v-for="group in LAYER_GROUPS"
        :key="group.label"
        class="layer-group"
      >
        <div class="layer-group-label">
          {{ group.label }}
        </div>
        <div
          v-for="layer in group.layers"
          :key="layer.key"
          class="layer-row"
          @click="toggleLayer(layer.key)"
        >
          <div
            class="layer-marker"
            :class="layer.shape"
            :style="layer.shape !== 'hatched' ? { background: layer.color } : {}"
          />
          <div class="flex-1">
            <div class="layer-name">
              {{ layer.name }}
            </div>
            <div class="layer-sub">
              {{ layer.sub }}
            </div>
          </div>
          <div class="toggle-switch">
            <div
              class="toggle-track"
              :class="{ on: props.layers[layer.key] }"
            >
              <div class="toggle-thumb" />
            </div>
          </div>
        </div>
        <!-- Inline methodology disclosure under the Satellite alerts group only -->
        <MethodologyAlerts v-if="group.label === 'Satellite alerts'" />
      </div>
    </div>

    <!-- Time slider -->
    <div class="rail-section animate-fadein-240">
      <div class="layer-group-label">
        Time window
      </div>
      <div class="time-pills">
        <button
          v-for="opt in TIME_OPTIONS"
          :key="opt"
          class="time-pill"
          :class="{ active: timeRange.pill === opt }"
          @click="setPill(opt as TimeRangePill)"
        >
          {{ opt }}
        </button>
      </div>
      <div
        ref="sliderTrackRef"
        class="time-slider-track"
        @click="onTrackClick"
      >
        <div
          class="time-slider-fill"
          :style="{ width: `${timeRange.sliderVal * 100}%` }"
        />
        <div
          class="time-slider-thumb"
          :style="{ left: `${timeRange.sliderVal * 100}%` }"
          @pointerdown.prevent="startDrag"
        />
      </div>
      <div class="time-label">
        {{ sliderLabel }}
      </div>
    </div>

    <!-- Trend by region (one mini sparkline per Ghana region) -->
    <RegionSparklines :time-range="timeRange" />

    <!-- Hotspots -->
    <div class="rail-section animate-fadein-320">
      <div class="layer-group-label">
        Active hotspots
      </div>
      <div
        v-for="spot in HOTSPOTS"
        :key="spot.id"
        class="hotspot-row"
        :class="{ 'opacity-100': activeHotspot === spot.id }"
        @click="emit('select-hotspot', spot.id)"
      >
        <div class="hotspot-pulse" />
        <div class="hotspot-name">
          {{ spot.name }}
        </div>
        <div class="hotspot-count">
          {{ spot.alerts }}
        </div>
      </div>
    </div>

    <!-- Footer: theme toggle + attribution -->
    <div class="rail-footer animate-fadein-400">
      <div class="theme-toggle-wrap">
        <div class="theme-toggle-label">
          Appearance
        </div>
        <div class="theme-seg">
          <button
            v-for="tm in THEME_MODES"
            :key="tm.value"
            class="theme-seg-btn"
            :class="{ active: mode === tm.value }"
            @click="setMode(tm.value)"
          >
            <svg
              class="theme-icon"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                :d="tm.icon"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
                fill="none"
              />
            </svg>
            {{ tm.label }}
          </button>
        </div>
      </div>
      <div
        class="px-5 py-3 text-[10px] opacity-40"
        :style="{ color: 'var(--rail-text-muted)' }"
      >
        Data: GFW, Minerals Commission, OSM &middot; Phase 1
      </div>
    </div>
  </aside>
</template>
