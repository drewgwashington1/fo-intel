export function useApi() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase as string

  function _authHeaders(): Record<string, string> {
    const headers: Record<string, string> = {}
    if (import.meta.client) {
      const token = localStorage.getItem('fo_intel_token')
      if (token) headers['Authorization'] = `Bearer ${token}`
    }
    return headers
  }

  async function get<T = any>(path: string, params?: Record<string, any>): Promise<T> {
    const url = new URL(`${base}${path}`)
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
      })
    }
    const res = await fetch(url.toString(), {
      headers: _authHeaders(),
      signal: AbortSignal.timeout(15000),
    })
    if (res.status === 401 && import.meta.client) {
      localStorage.removeItem('fo_intel_token')
      window.location.href = '/login'
    }
    if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
    return res.json()
  }

  async function post<T = any>(path: string, body?: any): Promise<T> {
    const res = await fetch(`${base}${path}`, {
      method: 'POST',
      headers: { ...(_authHeaders()), ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(30000),
    })
    if (res.status === 401 && import.meta.client) {
      localStorage.removeItem('fo_intel_token')
      window.location.href = '/login'
    }
    if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
    return res.json()
  }

  return { get, post }
}
