export function useApi() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase as string

  async function get<T = any>(path: string, params?: Record<string, any>): Promise<T> {
    const url = new URL(`${base}${path}`)
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
      })
    }
    const res = await fetch(url.toString(), { signal: AbortSignal.timeout(15000) })
    if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
    return res.json()
  }

  async function post<T = any>(path: string, body?: any): Promise<T> {
    const res = await fetch(`${base}${path}`, {
      method: 'POST',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(30000),
    })
    if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
    return res.json()
  }

  return { get, post }
}
