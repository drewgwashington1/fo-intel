<script setup lang="ts">
const { post } = useApi()
const store = useDashboardStore()

const mobileOpen = ref(false)
const pipelineResult = ref<{ message: string; success: boolean } | null>(null)
const pipelines = ref<Record<string, boolean>>({
  gsc: false,
  ads: false,
  profound: false,
  transparency: false,
  serper: false,
  creatives: false,
  methodology: false,
})

const navItems = [
  { label: 'Overview', path: '/', icon: 'M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z' },
  { label: 'Insights', path: '/insights', icon: 'M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18' },
  { label: 'Organic', path: '/organic', icon: 'M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z' },
  { label: 'Paid', path: '/paid', icon: 'M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z', children: [
    { label: 'Creatives', path: '/creatives' },
    { label: 'Competitor Ads', path: '/competitors' },
  ]},
  { label: 'AI Visibility', path: '/ai', icon: 'M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z' },
]

async function runPipeline(key: string, path: string) {
  pipelines.value[key] = true
  pipelineResult.value = null
  try {
    const result = await post(path)
    const count = result.rows_inserted ?? result.ads_inserted ?? result.days_processed ?? 0
    const skipped = result.days_skipped ?? 0
    const label = key.toUpperCase()
    if (count > 0) {
      pipelineResult.value = { message: `${label}: ${count} rows ingested`, success: true }
    } else if (skipped > 0) {
      pipelineResult.value = { message: `${label}: Already up to date (${skipped} days cached)`, success: true }
    } else {
      pipelineResult.value = { message: `${label}: Complete — ${result.total_scraped ?? 0} processed`, success: true }
    }

    // Refresh the relevant dashboard data so charts update immediately
    const refreshMap: Record<string, () => Promise<void>> = {
      gsc: () => store.fetchOrganic(),
      ads: () => store.fetchPaid(),
      creatives: () => store.fetchCreatives(),
      profound: () => store.fetchAI(),
      transparency: () => store.fetchCompetitors(),
    }
    if (refreshMap[key]) await refreshMap[key]()
  } catch (e: any) {
    console.error(`Pipeline ${key} failed:`, e)
    pipelineResult.value = { message: `${key.toUpperCase()} failed: ${e.message}`, success: false }
  } finally {
    pipelines.value[key] = false
    setTimeout(() => { pipelineResult.value = null }, 5000)
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
    <button class="text-gray-500" @click="mobileOpen = !mobileOpen">
      <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
      </svg>
    </button>
  </div>

  <!-- Sidebar -->
  <aside
    :class="[
      'fixed top-0 left-0 bottom-0 z-40 w-60 bg-white border-r border-surface-border flex flex-col transition-transform',
      mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
    ]"
  >
    <!-- Logo -->
    <div class="h-14 px-4 flex items-center gap-2 border-b border-surface-border">
      <div class="w-8 h-8 rounded-lg bg-fo-action flex items-center justify-center">
        <span class="text-white font-bold text-sm">FO</span>
      </div>
      <div>
        <div class="text-gray-900 font-semibold text-sm leading-tight">FO Intel</div>
        <div class="text-gray-400 text-[10px] uppercase tracking-wider">Search Intelligence</div>
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
        <!-- Sub-items -->
        <template v-if="item.children">
          <NuxtLink
            v-for="child in item.children"
            :key="child.path"
            :to="child.path"
            class="flex items-center gap-3 pl-11 pr-3 py-2 rounded-lg text-sm transition-colors"
            :class="$route.path === child.path
              ? 'text-fo-action font-medium'
              : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'"
            @click="mobileOpen = false"
          >
            {{ child.label }}
          </NuxtLink>
        </template>
      </template>
    </nav>

    <!-- Pipeline buttons -->
    <div class="border-t border-surface-border p-3 space-y-2">
      <p class="text-[10px] uppercase tracking-wider text-gray-400 px-1 mb-2">Pipelines</p>
      <button
        v-for="(label, key) in { gsc: 'GSC Organic', ads: 'Google Ads', creatives: 'Ad Creatives', profound: 'AI Visibility', transparency: 'Competitor Ads', serper: 'SERP Sweep', methodology: 'Methodology Refresh' }"
        :key="key"
        class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors bg-gray-50 text-gray-600 hover:text-gray-900 hover:bg-gray-100 disabled:opacity-50"
        :disabled="pipelines[key]"
        @click="runPipeline(key, `/ingest/${key === 'transparency' ? 'transparency' : key === 'serper' ? 'serper-sweep' : key === 'methodology' ? 'methodology-refresh' : key === 'creatives' ? 'creatives' : key}?days=30`)"
      >
        <svg v-if="pipelines[key]" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
        </svg>
        {{ label }}
      </button>
    </div>
  </aside>

  <!-- Pipeline toast -->
  <Transition
    enter-active-class="transition ease-out duration-200"
    enter-from-class="opacity-0 translate-y-2"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition ease-in duration-150"
    leave-from-class="opacity-100 translate-y-0"
    leave-to-class="opacity-0 translate-y-2"
  >
    <div
      v-if="pipelineResult"
      class="fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium"
      :class="pipelineResult.success ? 'bg-green-600 text-white' : 'bg-red-600 text-white'"
    >
      {{ pipelineResult.message }}
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
</template>
