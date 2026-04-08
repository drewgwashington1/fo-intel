<script setup lang="ts">
const { get, post } = useApi()
const store = useDashboardStore()
const { init: initAuth, isLoggedIn, logout } = useAuth()
const router = useRouter()

onMounted(() => {
  initAuth()
  if (!isLoggedIn.value) {
    router.replace('/login')
  }
})

const mobileOpen = ref(false)
const refreshing = ref(false)
const refreshResult = ref<{ message: string; success: boolean } | null>(null)

// ── Welcome Walkthrough ──
const showWalkthrough = ref(false)
const walkthroughStep = ref(0)

const walkthroughSteps = [
  {
    title: 'Welcome to FO Intel',
    description: 'Your organic search intelligence platform. FO Intel consolidates organic search data, keyword research, and competitive analysis into one dashboard.',
  },
  {
    title: 'Organic Performance',
    description: 'Track your Google Search Console data — clicks, impressions, CTR, and keyword rankings. Filter by keyword tags and monitor position movements over time.',
  },
  {
    title: 'Keywords Explorer',
    description: 'Research keywords with Google Keyword Planner data — search volume, CPC, competition. Discover keyword ideas and find content gaps where competitors rank but you don\'t.',
  },
  {
    title: 'Insights & Opportunities',
    description: 'Content opportunity engine that surfaces actionable items — keywords to create content for, pages to expand, content to refresh, and competitive gaps to close.',
  },
]

function dismissWalkthrough() {
  showWalkthrough.value = false
  if (import.meta.client) {
    localStorage.setItem('fo_intel_walkthrough_seen', 'true')
  }
}

function nextStep() {
  if (walkthroughStep.value < walkthroughSteps.length - 1) {
    walkthroughStep.value++
  } else {
    dismissWalkthrough()
  }
}

function prevStep() {
  if (walkthroughStep.value > 0) {
    walkthroughStep.value--
  }
}

onMounted(() => {
  if (import.meta.client && !localStorage.getItem('fo_intel_walkthrough_seen')) {
    showWalkthrough.value = true
  }
})

// Competitor management
const showCompPanel = ref(false)
const competitors = ref<any[]>([])
const newCompDomain = ref('')

async function loadCompetitors() {
  competitors.value = await get('/dashboard/tracked-competitors')
}

async function addCompetitor() {
  const domain = newCompDomain.value.trim().toLowerCase()
  if (!domain) return
  await post(`/dashboard/tracked-competitors?domain=${encodeURIComponent(domain)}`)
  newCompDomain.value = ''
  await loadCompetitors()
}

async function removeCompetitor(domain: string) {
  await fetch(`${useRuntimeConfig().public.apiBase}/dashboard/tracked-competitors?domain=${encodeURIComponent(domain)}`, { method: 'DELETE' })
  await loadCompetitors()
}

onMounted(() => loadCompetitors())

const navItems = [
  { label: 'Insights', path: '/insights', icon: 'M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18' },
  { label: 'Organic', path: '/organic', icon: 'M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z' },
  { label: 'Keywords', path: '/keywords', icon: 'M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6' },
  { label: 'Settings', path: '/settings', icon: 'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
]

async function refreshData() {
  refreshing.value = true
  refreshResult.value = null
  try {
    // Single call — backend handles stale detection, ingest, and summary rebuild
    const result = await post('/ingest/refresh')
    const stale = result.stale_pipelines?.length ?? 0

    if (stale > 0) {
      refreshResult.value = { message: `Refreshing ${stale} pipeline${stale > 1 ? 's' : ''} in background...`, success: true }
    } else {
      refreshResult.value = { message: 'All data is fresh', success: true }
    }

    // Force frontend to re-fetch from (now updated) summary cache
    await store.fetchAll(true)
  } catch (e: any) {
    refreshResult.value = { message: `Refresh failed: ${e.message}`, success: false }
  } finally {
    refreshing.value = false
    setTimeout(() => { refreshResult.value = null }, 5000)
  }
}
</script>

<template>
  <!-- Mobile header -->
  <div class="lg:hidden fixed top-0 left-0 right-0 z-50 bg-white border-b border-surface-border px-4 h-14 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <div class="w-8 h-8 rounded-lg bg-fo-action flex items-center justify-center">
        <span class="text-white font-bold text-sm">FO</span>
      </div>
      <span class="text-gray-900 font-semibold text-sm">FO Intel</span>
    </div>
    <div class="flex items-center gap-2">
      <button
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-fo-action text-white disabled:opacity-50"
        :disabled="refreshing"
        @click="refreshData"
      >
        <svg :class="['w-3.5 h-3.5', refreshing && 'animate-spin']" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
        </svg>
        {{ refreshing ? 'Refreshing...' : 'Refresh' }}
      </button>
      <button class="text-gray-500" @click="mobileOpen = !mobileOpen">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        </svg>
      </button>
    </div>
  </div>

  <!-- Sidebar -->
  <aside
    :class="[
      'fixed top-0 left-0 bottom-0 z-40 w-60 bg-white border-r border-surface-border flex flex-col transition-transform',
      mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
    ]"
  >
    <!-- Logo -->
    <div class="h-14 px-4 flex items-center justify-between border-b border-surface-border">
      <div class="flex items-center gap-2">
        <div class="w-8 h-8 rounded-lg bg-fo-action flex items-center justify-center">
          <span class="text-white font-bold text-sm">FO</span>
        </div>
        <div>
          <div class="text-gray-900 font-semibold text-sm leading-tight">FO Intel</div>
          <div class="text-gray-400 text-[10px] uppercase tracking-wider">Search Intelligence</div>
        </div>
      </div>
    </div>

    <!-- Nav -->
    <nav class="flex-1 py-4 px-2 space-y-1">
      <template v-for="item in navItems" :key="item.path">
        <NuxtLink
          :to="item.path"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors"
          :class="(item.path === '/' ? $route.path === '/' : $route.path.startsWith(item.path))
            ? 'bg-fo-action/10 text-fo-action'
            : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'"
          @click="mobileOpen = false"
        >
          <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon" />
          </svg>
          {{ item.label }}
        </NuxtLink>
      </template>
    </nav>

    <!-- Competitors -->
    <div class="border-t border-surface-border p-3">
      <button
        class="w-full flex items-center justify-between px-2 py-1.5 text-[10px] uppercase tracking-wider text-gray-400 hover:text-gray-700"
        @click="showCompPanel = !showCompPanel"
      >
        Competitors ({{ competitors.length }})
        <svg :class="['w-3 h-3 transition-transform', showCompPanel && 'rotate-180']" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <div v-if="showCompPanel" class="mt-2 space-y-2">
        <div v-for="c in competitors" :key="c.domain" class="flex items-center justify-between px-2 py-1">
          <span class="text-xs text-gray-700 truncate">{{ c.domain }}</span>
          <button class="text-gray-400 hover:text-status-down transition-colors" @click="removeCompetitor(c.domain)">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div class="flex items-center gap-1">
          <input
            v-model="newCompDomain"
            type="text"
            placeholder="domain.com"
            class="flex-1 px-2 py-1.5 text-xs rounded border border-surface-border bg-surface focus:outline-none focus:border-fo-action"
            @keydown.enter="addCompetitor"
          />
          <button
            class="px-2 py-1.5 rounded text-xs font-medium bg-fo-action text-white hover:bg-fo-blue transition-colors"
            @click="addCompetitor"
          >Add</button>
        </div>
      </div>
    </div>

    <!-- Refresh button at bottom -->
    <div class="border-t border-surface-border p-3">
      <button
        class="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors bg-fo-action text-white hover:bg-fo-blue disabled:opacity-50"
        :disabled="refreshing"
        @click="refreshData"
      >
        <svg :class="['w-4 h-4', refreshing && 'animate-spin']" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
        </svg>
        {{ refreshing ? 'Refreshing...' : 'Refresh Data' }}
      </button>
      <button
        class="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors mt-2"
        @click="logout(); router.replace('/login')"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
        </svg>
        Sign out
      </button>
    </div>
  </aside>

  <!-- Toast -->
  <Transition
    enter-active-class="transition ease-out duration-200"
    enter-from-class="opacity-0 translate-y-2"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition ease-in duration-150"
    leave-from-class="opacity-100 translate-y-0"
    leave-to-class="opacity-0 translate-y-2"
  >
    <div
      v-if="refreshResult"
      class="fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium"
      :class="refreshResult.success ? 'bg-green-600 text-white' : 'bg-red-600 text-white'"
    >
      {{ refreshResult.message }}
    </div>
  </Transition>

  <!-- Overlay -->
  <div v-if="mobileOpen" class="fixed inset-0 z-30 bg-black/30 lg:hidden" @click="mobileOpen = false" />

  <!-- Main content -->
  <main class="lg:pl-60 pt-14 lg:pt-0 min-h-screen bg-surface">
    <div class="p-6">
      <slot />
    </div>
  </main>

  <!-- Welcome Walkthrough Modal -->
  <Teleport to="body">
    <div v-if="showWalkthrough" class="fixed inset-0 z-[100] flex items-center justify-center">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/40" @click="dismissWalkthrough" />
      <!-- Modal card -->
      <div class="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        <!-- Progress bar -->
        <div class="h-1 bg-gray-100">
          <div
            class="h-full bg-fo-action transition-all duration-300"
            :style="{ width: `${((walkthroughStep + 1) / walkthroughSteps.length) * 100}%` }"
          />
        </div>

        <!-- Content -->
        <div class="p-8">
          <!-- Step indicator -->
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-3">
            Step {{ walkthroughStep + 1 }} of {{ walkthroughSteps.length }}
          </p>

          <!-- Icon -->
          <div class="w-12 h-12 rounded-xl bg-fo-action/10 flex items-center justify-center mb-4">
            <div class="w-7 h-7 rounded-lg bg-fo-action flex items-center justify-center">
              <span class="text-white font-bold text-xs">FO</span>
            </div>
          </div>

          <h2 class="text-lg font-bold text-gray-900 mb-2">{{ walkthroughSteps[walkthroughStep].title }}</h2>
          <p class="text-sm text-gray-500 leading-relaxed">{{ walkthroughSteps[walkthroughStep].description }}</p>
        </div>

        <!-- Footer -->
        <div class="px-8 pb-6 flex items-center justify-between">
          <button
            class="text-sm text-gray-400 hover:text-gray-700 transition-colors"
            @click="dismissWalkthrough"
          >Skip</button>

          <div class="flex items-center gap-3">
            <button
              v-if="walkthroughStep > 0"
              class="px-4 py-2 rounded-lg text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors"
              @click="prevStep"
            >Back</button>
            <button
              class="px-5 py-2 rounded-lg text-sm font-medium bg-fo-action text-white hover:bg-fo-blue transition-colors"
              @click="nextStep"
            >{{ walkthroughStep === walkthroughSteps.length - 1 ? 'Done' : 'Next' }}</button>
          </div>
        </div>

        <!-- Step dots -->
        <div class="flex justify-center gap-1.5 pb-4">
          <div
            v-for="(_, i) in walkthroughSteps"
            :key="i"
            class="w-1.5 h-1.5 rounded-full transition-colors"
            :class="i === walkthroughStep ? 'bg-fo-action' : i < walkthroughStep ? 'bg-fo-action/40' : 'bg-gray-200'"
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>
