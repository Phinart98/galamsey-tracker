// Tiny wrapper around $fetch that injects the runtime API base URL.
// Usage:
//   const api = useApi()
//   const data = await api<RegionSparkline[]>('/alerts/by-region', { query: { from, to } })

export const useApi = () => {
  const { public: { apiBaseUrl } } = useRuntimeConfig()
  return <T>(path: string, opts: Parameters<typeof $fetch>[1] = {}) =>
    $fetch<T>(path, { baseURL: apiBaseUrl, ...opts })
}
