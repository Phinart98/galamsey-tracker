export default defineNuxtConfig({
  components: {
    dirs: [{ path: '~/components', pathPrefix: false }],
  },

  app: {
    head: {
      meta: [
        // viewport-fit=cover: extends layout into iPhone notch/safe-area so the
        // rail handle doesn't sit under the home-bar gesture area (paired with
        // padding-bottom: env(safe-area-inset-bottom) in main.css)
        { name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' },
      ],
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        // @nuxtjs/google-fonts cannot produce the correct variable-font URL for Fraunces
        // (axes object serialises as "[object Object]"). Direct link is more reliable.
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..900&family=Public+Sans:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500&display=swap',
        },
      ],
    },
  },

  modules: [
    '@nuxtjs/tailwindcss',
    'nuxt-maplibre',
  ],

  css: ['~/assets/css/main.css'],

  // Nuxt 3 runtime config: empty strings are overridden at deploy time by
  // NUXT_* env vars (private) or NUXT_PUBLIC_* env vars (public/client-side).
  // Never use process.env here — it bakes the build-time value into the bundle.
  runtimeConfig: {
    supabaseServiceRoleKey: '',  // NUXT_SUPABASE_SERVICE_ROLE_KEY
    public: {
      supabaseUrl: '',           // NUXT_PUBLIC_SUPABASE_URL
      supabaseAnonKey: '',       // NUXT_PUBLIC_SUPABASE_ANON_KEY
      apiBaseUrl: 'http://localhost:8000',     // NUXT_PUBLIC_API_BASE_URL
      martinBaseUrl: 'http://localhost:3001',  // NUXT_PUBLIC_MARTIN_BASE_URL
      titilerBaseUrl: 'http://localhost:8080', // NUXT_PUBLIC_TITILER_BASE_URL
      r2PublicUrl: '',           // NUXT_PUBLIC_CLOUDFLARE_R2_PUBLIC_URL
    },
  },

  nitro: {
    preset: 'vercel',
  },

  typescript: {
    strict: true,
    typeCheck: false,  // run separately via `pnpm typecheck` / vue-tsc
  },

  devtools: { enabled: true },

  compatibilityDate: '2025-01-01',

  // $development block: merged only when NODE_ENV === 'development'.
  // Nitro serves the HTML page (not Vite), so vite.server.headers doesn't help.
  // Sending no-store on all dev routes prevents the browser from caching the
  // SSR HTML with stale Vite chunk URLs, which causes a blank screen on Ctrl+R.
  $development: {
    routeRules: {
      '/**': { headers: { 'cache-control': 'no-store' } },
    },
  },
})
