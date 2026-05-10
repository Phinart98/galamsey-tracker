<script setup lang="ts">
import type { AlertTimeRange, RegionSparkline } from '~/types/dashboard'
import { rangeToFromTo } from '~/composables/useTimeRange'

const props = defineProps<{ timeRange: AlertTimeRange }>()

const emit = defineEmits<{
  'region-click': [regionId: number]
}>()

interface RegionRow {
  region_id: number
  region_name: string
  total: number
  points: string
}

const data = ref<RegionSparkline[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const api = useApi()

async function fetchData() {
  const { from, to } = rangeToFromTo(props.timeRange)
  loading.value = true
  error.value = null
  try {
    data.value = await api<RegionSparkline[]>('/alerts/by-region', { query: { from, to } })
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load region trends'
    data.value = []
  }
  finally {
    loading.value = false
  }
}

onMounted(fetchData)
watch(() => props.timeRange, fetchData, { deep: true })

// Shared y-axis across all regions: a 5x-larger Western jumps out visually,
// which is the point of the "which region is hottest" panel. Per-region
// auto-scaling would hide that.
// SVG viewBox is 60 wide, 18 tall; 1px top/bottom padding keeps strokes from clipping.
const rows = computed<RegionRow[]>(() => {
  let yMax = 1
  for (const r of data.value)
    for (const d of r.dates) if (d.count > yMax) yMax = d.count

  return data.value.map((r) => {
    const stepX = 60 / Math.max(1, r.dates.length - 1)
    let total = 0
    const coords: string[] = []
    for (let i = 0; i < r.dates.length; i++) {
      const d = r.dates[i]!
      total += d.count
      coords.push(`${(i * stepX).toFixed(2)},${(17 - (d.count / yMax) * 16).toFixed(2)}`)
    }
    return {
      region_id: r.region_id,
      region_name: r.region_name,
      total,
      points: coords.join(' '),
    }
  })
})
</script>

<template>
  <div class="rail-section animate-fadein-280">
    <div class="layer-group-label">
      Trend by region
    </div>

    <div
      v-if="loading && data.length === 0"
      class="px-5 py-3 text-[11px] opacity-50"
    >
      Loading region trends&hellip;
    </div>
    <div
      v-else-if="error"
      class="px-5 py-3 text-[11px] opacity-60"
    >
      {{ error }}
    </div>
    <div
      v-else-if="data.length === 0"
      class="px-5 py-3 text-[11px] opacity-50"
    >
      No alerts in this window.
    </div>

    <div
      v-for="r in rows"
      :key="r.region_id"
      class="region-spark-row"
      :title="`${r.region_name}: ${r.total} alerts`"
      @click="emit('region-click', r.region_id)"
    >
      <div class="region-spark-name">
        {{ r.region_name }}
      </div>
      <svg
        class="region-spark-svg"
        viewBox="0 0 60 18"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <polyline
          :points="r.points"
          fill="none"
          stroke="#B8472A"
          stroke-width="1"
          stroke-linejoin="round"
          stroke-linecap="round"
          vector-effect="non-scaling-stroke"
        />
      </svg>
      <div class="region-spark-count">
        {{ r.total }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.region-spark-row {
  display: grid;
  grid-template-columns: 90px 1fr 36px;
  align-items: center;
  gap: 10px;
  padding: 6px 20px;
  cursor: pointer;
  font-size: 11px;
  color: var(--rail-text);
}
.region-spark-row:hover {
  background: var(--row-hover);
}
.region-spark-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}
.region-spark-svg {
  width: 100%;
  height: 18px;
  display: block;
}
.region-spark-count {
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--rail-text-muted);
}
</style>
