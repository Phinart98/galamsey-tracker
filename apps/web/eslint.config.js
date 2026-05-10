import tsParser from '@typescript-eslint/parser'
import tsPlugin from '@typescript-eslint/eslint-plugin'
import pluginVue from 'eslint-plugin-vue'

export default [
  {
    ignores: ['.nuxt/**', '.output/**', '.vercel/**', 'node_modules/**', 'dist/**'],
  },

  // Vue SFCs — use plugin's built-in flat config (handles parser automatically)
  ...pluginVue.configs['flat/recommended'],

  // Override parser for <script lang="ts"> blocks
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: { parser: tsParser },
    },
    plugins: { '@typescript-eslint': tsPlugin },
    rules: {
      'vue/multi-word-component-names': 'off',  // pages/index.vue is single-word
      'vue/no-v-html': 'off',
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },

  // TypeScript source files
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tsParser,
      parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
    },
    plugins: { '@typescript-eslint': tsPlugin },
    rules: {
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
]
