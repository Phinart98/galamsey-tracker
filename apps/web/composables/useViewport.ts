export function useViewport() {
  const isMobile = ref(false)
  const isTablet = ref(false)

  if (import.meta.client) {
    const mq768  = window.matchMedia('(max-width: 768px)')
    const mq1024 = window.matchMedia('(min-width: 769px) and (max-width: 1024px)')

    const sync = () => {
      isMobile.value = mq768.matches
      isTablet.value = mq1024.matches
    }

    sync()
    mq768.addEventListener('change', sync)
    mq1024.addEventListener('change', sync)

    onUnmounted(() => {
      mq768.removeEventListener('change', sync)
      mq1024.removeEventListener('change', sync)
    })
  }

  const isDesktop = computed(() => !isMobile.value && !isTablet.value)

  return { isMobile, isTablet, isDesktop }
}
