export default [
  {
    ignores: ['.nuxt/**', '.output/**', 'dist/**', 'node_modules/**'],
  },
  {
    files: ['**/*.{js,ts,vue}'],
    rules: {
      'no-console': 'warn',
      'no-debugger': 'error',
    },
  },
]
