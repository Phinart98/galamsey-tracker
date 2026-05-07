export type ThemeMode = 'system' | 'light' | 'dark'

const THEME_MODES = ['system', 'light', 'dark'] as const
const STORAGE_KEY = 'galamsey-theme'

const isThemeMode = (v: string): v is ThemeMode =>
  (THEME_MODES as readonly string[]).includes(v)

// Module-level so all useTheme() callers share one MQ object and one OS listener.
const mq = import.meta.client
  ? window.matchMedia('(prefers-color-scheme: dark)')
  : null

export const useTheme = () => {
  const mode = useState<ThemeMode>('theme-mode', () => 'system')

  const resolvedTheme = computed<'light' | 'dark'>(() => {
    if (mode.value !== 'system') return mode.value
    return mq?.matches ? 'dark' : 'light'
  })

  const applyTheme = () => {
    if (!mq) return
    // Read mq.matches directly — Vue cannot track a plain DOM property, so the
    // computed resolvedTheme is stale when the OS scheme changes at runtime.
    const next: 'light' | 'dark' = mode.value !== 'system'
      ? mode.value
      : (mq.matches ? 'dark' : 'light')
    const html = document.documentElement
    if (html.classList.contains(next) && html.getAttribute('data-theme') === next) return
    html.classList.remove('light', 'dark')
    html.classList.add(next)
    html.setAttribute('data-theme', next)
  }

  const setMode = (next: ThemeMode) => {
    mode.value = next
    if (import.meta.client) {
      localStorage.setItem(STORAGE_KEY, next)
      applyTheme()
    }
  }

  onMounted(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && isThemeMode(stored)) mode.value = stored
    applyTheme()

    if (!mq) return
    const onSchemeChange = () => { if (mode.value === 'system') applyTheme() }
    mq.addEventListener('change', onSchemeChange)
    onUnmounted(() => mq.removeEventListener('change', onSchemeChange))
  })

  return { mode: readonly(mode), resolvedTheme, setMode }
}
