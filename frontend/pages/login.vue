<script setup lang="ts">
definePageMeta({ layout: false })

const { login, isLoggedIn, init } = useAuth()
const router = useRouter()

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

onMounted(() => {
  init()
  if (isLoggedIn.value) router.replace('/')
})

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    const success = await login(email.value, password.value)
    if (success) {
      router.replace('/')
    } else {
      error.value = 'Invalid email or password'
    }
  } catch {
    error.value = 'Login failed — check your connection'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <div class="w-full max-w-sm">
      <!-- Logo -->
      <div class="text-center mb-8">
        <div class="w-14 h-14 rounded-xl bg-fo-action flex items-center justify-center mx-auto mb-3">
          <span class="text-white font-bold text-xl">FO</span>
        </div>
        <h1 class="text-xl font-semibold text-gray-900">FO Intel</h1>
        <p class="text-sm text-gray-400 mt-1">Search Intelligence Platform</p>
      </div>

      <!-- Login form -->
      <div class="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <form @submit.prevent="handleLogin" class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1.5">Email</label>
            <input
              v-model="email"
              type="email"
              required
              autocomplete="email"
              class="w-full px-3 py-2.5 text-sm rounded-lg border border-gray-200 focus:outline-none focus:border-fo-action focus:ring-1 focus:ring-fo-action/20"
              placeholder="you@firstorion.com"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1.5">Password</label>
            <input
              v-model="password"
              type="password"
              required
              autocomplete="current-password"
              class="w-full px-3 py-2.5 text-sm rounded-lg border border-gray-200 focus:outline-none focus:border-fo-action focus:ring-1 focus:ring-fo-action/20"
              placeholder="Enter password"
            />
          </div>

          <div v-if="error" class="px-3 py-2 rounded-lg bg-red-50 text-red-600 text-xs font-medium">
            {{ error }}
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full py-2.5 rounded-lg text-sm font-medium bg-fo-action text-white hover:bg-fo-blue transition-colors disabled:opacity-50"
          >
            {{ loading ? 'Signing in...' : 'Sign in' }}
          </button>
        </form>
      </div>

      <p class="text-center text-xs text-gray-400 mt-6">First Orion Internal Tool</p>
    </div>
  </div>
</template>
