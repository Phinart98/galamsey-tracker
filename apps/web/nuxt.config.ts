export default defineNuxtConfig({
  modules: [
    '@nuxtjs/tailwindcss',
    '@nuxtjs/google-fonts',
    'nuxt-maplibre',
  ],

  googleFonts: {
    families: {
      Fraunces: {
        axes: {
          opsz: [9, 144],
          wght: [300, 900],
          SOFT: [0, 100],
        },
      },
      'Public Sans': [300, 400, 500, 700],
      'JetBrains Mono': [400, 500],
    },
    display: 'swap',
    preconnect: true,
  },

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
    typeCheck: true,
  },

  devtools: { enabled: true },

  compatibilityDate: '2025-01-01',
})
