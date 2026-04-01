const token = ref<string | null>(null)
const user = ref<{ email: string; role: string } | null>(null)

export function useAuth() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase as string

  function init() {
    if (import.meta.client) {
      token.value = localStorage.getItem('fo_intel_token')
    }
  }

  const isLoggedIn = computed(() => !!token.value)

  async function login(email: string, password: string): Promise<boolean> {
    const res = await fetch(`${base}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) return false
    const data = await res.json()
    token.value = data.access_token
    if (import.meta.client) {
      localStorage.setItem('fo_intel_token', data.access_token)
    }
    return true
  }

  function logout() {
    token.value = null
    user.value = null
    if (import.meta.client) {
      localStorage.removeItem('fo_intel_token')
    }
  }

  function getToken(): string | null {
    return token.value
  }

  return { init, isLoggedIn, login, logout, getToken, token, user }
}
