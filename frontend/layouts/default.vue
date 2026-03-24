<script setup lang="ts">
const { post } = useApi()

const mobileOpen = ref(false)
const pipelines = ref<Record<string, boolean>>({
  gsc: false,
  ads: false,
  profound: false,
  transparency: false,
})

const navItems = [
  { label: 'Organic', path: '/', icon: 'M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z' },
  { label: 'Paid', path: '/paid', icon: 'M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z' },
  { label: 'AI Visibility', path: '/ai', icon: 'M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z' },
  { label: 'Competitor Ads', path: '/competitors', icon: 'M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5' },
]

async function runPipeline(key: string, path: string) {
  pipelines.value[key] = true
  try {
    await post(path)
  } catch (e) {
    console.error(`Pipeline ${key} failed:`, e)
  } finally {
    pipelines.value[key] = false
  }
}
</script>

<template>
  <!-- Mobile header -->
  <div class="lg:hidden fixed top-0 left-0 right-0 z-50 bg-surface-card border-b border-surface-border px-4 h-14 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <div class="w-8 h-8 rounded-lg bg-fo-action flex items-center justify-center">
        <span class="text-white font-bold text-sm">FO</span>
      </div>
      <span class="text-white font-semibold text-sm">FO Intel</span>
    </div>
    <button class="text-gray-400" @click="mobileOpen = !mobileOpen">
      <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
      </svg>
    </button>
  </div>

  <!-- Sidebar -->
  <aside
    :class="[
      'fixed top-0 left-0 bottom-0 z-40 w-60 bg-surface-card border-r border-surface-border flex flex-col transition-transform',
      mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
    ]"
  >
    <!-- Logo -->
    <div class="h-14 px-4 flex items-center gap-2 border-b border-surface-border">
      <div class="w-8 h-8 rounded-lg bg-fo-action flex items-center justify-center">
        <span class="text-white font-bold text-sm">FO</span>
      </div>
      <div>
        <div class="text-white font-semibold text-sm leading-tight">FO Intel</div>
        <div class="text-gray-500 text-[10px] uppercase tracking-wider">Search Intelligence</div>
      </div>
    </div>

    <!-- Nav -->
    <nav class="flex-1 py-4 px-2 space-y-1">
      <NuxtLink
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors"
        :class="$route.path === item.path
          ? 'bg-fo-action/10 text-fo-action'
          : 'text-gray-400 hover:text-white hover:bg-surface-hover'"
        @click="mobileOpen = false"
      >
        <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon" />
        </svg>
        {{ item.label }}
      </NuxtLink>
    </nav>

    <!-- Pipeline buttons -->
    <div class="border-t border-surface-border p-3 space-y-2">
      <p class="text-[10px] uppercase tracking-wider text-gray-500 px-1 mb-2">Pipelines</p>
      <button
        v-for="(label, key) in { gsc: 'GSC Organic', ads: 'Google Ads', profound: 'AI Visibility', transparency: 'Competitor Ads' }"
        :key="key"
        class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors bg-surface-hover text-gray-300 hover:text-white disabled:opacity-50"
        :disabled="pipelines[key]"
        @click="runPipeline(key, `/ingest/${key === 'transparency' ? 'transparency' : key}?days=30`)"
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

  <!-- Overlay -->
  <div v-if="mobileOpen" class="fixed inset-0 z-30 bg-black/50 lg:hidden" @click="mobileOpen = false" />

  <!-- Main content -->
  <main class="lg:pl-60 pt-14 lg:pt-0 min-h-screen bg-surface">
    <div class="p-6">
      <slot />
    </div>
  </main>
</template>
