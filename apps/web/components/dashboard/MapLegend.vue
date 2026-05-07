<script setup lang="ts">
import type { LayerKey } from '~/types/dashboard'

const props = defineProps<{
  layers: Record<LayerKey, boolean>
}>()

const LEGEND_ITEMS: { key: LayerKey; label: string; swatchClass: string; color?: string }[] = [
  { key: 'gfw',       label: 'GFW alert',       swatchClass: 'rounded-full',       color: '#B8472A' },
  { key: 'sar',       label: 'Citizen report',   swatchClass: 'rounded-full',       color: 'var(--citizen-pin)' },
  { key: 'turbidity', label: 'River turbidity',  swatchClass: 'legend-swatch line', color: '#C4926B' },
  { key: 'reserves',  label: 'Forest reserve',   swatchClass: 'legend-swatch poly', color: '#1A4030' },
]

const visibleItems = computed(() =>
  LEGEND_ITEMS.filter(item => props.layers[item.key])
)
</script>

<template>
  <div
    v-if="visibleItems.length > 0"
    class="map-legend"
  >
    <div class="legend-title">
      Legend
    </div>
    <div
      v-for="item in visibleItems"
      :key="item.key"
      class="legend-row"
    >
      <div
        class="legend-swatch"
        :class="item.swatchClass"
        :style="item.color ? { background: item.color } : {}"
      />
      {{ item.label }}
    </div>
  </div>
</template>
