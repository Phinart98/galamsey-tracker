export type ThemeMode = 'system' | 'light' | 'dark'

const THEME_MODES = ['system', 'light', 'dark'] as const
const STORAGE_KEY = 'galamsey-theme'

const isThemeMode = (v: string): v is ThemeMode =>
  (THEME_MODES as readonly string[]).includes(v)

export const useTheme = () => {
  const mode = useState<ThemeMode>('theme-mode', () => 'system')

  // Single MediaQueryList instance shared by resolvedTheme and the change listener.
  // null on the server (import.meta.client is a compile-time constant per build target).
  const mq = import.meta.client
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null

  const resolvedTheme = computed<'light' | 'dark'>(() => {
    if (mode.value !== 'system') return mode.value
    return mq?.matches ? 'dark' : 'light'
  })

  const applyTheme = () => {
    if (!mq) return
    const next = resolvedTheme.value
    const html = document.documentElement
    if (html.classList.contains(next)) return
    html.classList.remove('light', 'dark')
    html.classList.add(next)
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
