<script setup lang="ts">
const open = ref(false)
</script>

<template>
  <div class="methodology-disclosure">
    <button
      class="methodology-toggle"
      :aria-expanded="open"
      @click="open = !open"
    >
      <span>How these alerts are made</span>
      <span
        class="methodology-chev"
        :class="{ open }"
      >&rsaquo;</span>
    </button>

    <div
      v-if="open"
      class="methodology-body"
    >
      <p>
        The GFW Integrated Alerts layer combines four independent satellite
        detectors. An alert is more likely to be real galamsey when more than
        one detector sees it.
      </p>

      <dl class="methodology-list">
        <dt>RADD</dt>
        <dd>
          10 m radar from Sentinel-1, weekly.
          Sees through cloud, so it works in Ghana's wet season when optical
          sensors are blind.
        </dd>

        <dt>GLAD-L</dt>
        <dd>
          30 m optical from Landsat, weekly.
          The longest-running record in the bundle: continuous since 2001.
          Best for trends across years.
        </dd>

        <dt>GLAD-S2</dt>
        <dd>
          10 m optical from Sentinel-2.
          Sharpest spatial detail when the sky is clear; the first to flag
          fresh cuts in the dry season.
        </dd>

        <dt>DIST-ALERT</dt>
        <dd>
          30 m harmonised Landsat 8 + Sentinel-2 from NASA.
          Detects vegetation loss against a long-baseline normal,
          so it spots gradual disturbance the others miss.
        </dd>
      </dl>

      <p class="methodology-cite">
        Source:
        <a
          href="https://www.globalforestwatch.org/blog/data-and-tools/integrated-deforestation-alerts/"
          target="_blank"
          rel="noopener"
        >Global Forest Watch &mdash; Integrated Deforestation Alerts</a>.
        Pipeline: weekly cron pulls Ghana-bbox alerts from the GFW Data API
        and stores them in PostGIS, served as Mapbox Vector Tiles via Martin.
      </p>
    </div>
  </div>
</template>

<style scoped>
.methodology-disclosure {
  margin: 8px 20px 0;
  padding-top: 8px;
  border-top: 1px dashed var(--hairline);
  font-size: 11px;
  color: var(--rail-text-muted);
}
.methodology-toggle {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  background: none;
  border: 0;
  color: var(--rail-text);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
}
.methodology-toggle:hover { color: var(--laterite); }
.methodology-chev {
  display: inline-block;
  transition: transform 160ms ease;
}
.methodology-chev.open { transform: rotate(90deg); }
.methodology-body {
  padding: 8px 0 4px;
  line-height: 1.45;
}
.methodology-body p { margin: 0 0 8px; }
.methodology-list { margin: 0 0 8px; }
.methodology-list dt {
  font-weight: 600;
  color: var(--rail-text);
  margin-top: 6px;
}
.methodology-list dd {
  margin: 2px 0 0;
  padding-left: 0;
}
.methodology-cite { font-size: 10px; opacity: 0.85; }
.methodology-cite a { color: var(--laterite); text-decoration: underline; }
</style>
