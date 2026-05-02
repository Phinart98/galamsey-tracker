<script setup lang="ts">
useTheme()
</script>

<template>
  <div class="flex h-screen bg-surface-canvas text-surface-fg overflow-hidden">
    <!-- Left rail -->
    <aside class="w-rail flex-shrink-0 bg-surface-rail border-r border-surface-line flex flex-col overflow-y-auto">
      <p class="p-6 text-surface-muted text-sm font-sans">Map dashboard coming in Phase 1.</p>
    </aside>

    <!-- Map canvas -->
    <main class="flex-1 relative bg-surface-canvas">
      <p class="absolute inset-0 flex items-center justify-center text-surface-muted font-display text-2xl tracking-widest uppercase">
        GALAMSEY TRACKER
      </p>
    </main>
  </div>
</template>
