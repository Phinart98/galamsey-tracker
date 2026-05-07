<script setup lang="ts">
import type { HotspotId } from '~/types/dashboard'
import { DETAIL_DATA } from '~/composables/useSyntheticData'

const props = defineProps<{
  hotspotId: HotspotId | null
}>()

const emit = defineEmits<{ close: [] }>()

const detail = computed(() => props.hotspotId ? DETAIL_DATA[props.hotspotId] : null)
</script>

<template>
  <Transition name="panel-slide">
    <div
      v-if="hotspotId && detail"
      class="detail-panel"
    >
      <!-- Header -->
      <div class="detail-header">
        <div class="flex-1">
          <div class="detail-aoi-label">
            Area of Concern
          </div>
          <div class="detail-title">
            {{ detail.title }}
          </div>
        </div>
        <button
          class="detail-close"
          aria-label="Close panel"
          @click="emit('close')"
        >
          &times;
        </button>
      </div>

      <div class="detail-body">
        <!-- Satellite placeholder -->
        <div class="detail-img-placeholder">
          SAR / NDVI COMPOSITE
        </div>

        <!-- Stats -->
        <div class="detail-stat-row">
          <div class="detail-stat">
            <div class="detail-stat-num">
              {{ detail.alerts }}
            </div>
            <div class="detail-stat-lbl">
              Alerts / 30d
            </div>
          </div>
          <div class="detail-stat">
            <div class="detail-stat-num">
              {{ detail.excavators }}
            </div>
            <div class="detail-stat-lbl">
              Excavators
            </div>
          </div>
          <div class="detail-stat">
            <div class="detail-stat-num">
              {{ detail.rivers }}
            </div>
            <div class="detail-stat-lbl">
              River segs.
            </div>
          </div>
        </div>

        <!-- Description -->
        <p
          class="text-[12px] leading-relaxed mb-4"
          style="color: var(--rail-text-muted)"
        >
          {{ detail.description }}
        </p>

        <!-- Recent incidents -->
        <div class="detail-section-lbl">
          Recent incidents
        </div>
        <div
          v-for="inc in detail.incidents"
          :key="inc.id"
          class="detail-alert-row"
        >
          <div class="alert-id">
            {{ inc.id }}
          </div>
          <div class="alert-desc">
            {{ inc.desc }}
          </div>
          <div class="alert-date">
            {{ inc.date }}
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
