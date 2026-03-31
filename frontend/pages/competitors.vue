<script setup lang="ts">
const store = useDashboardStore()
const { get } = useApi()

const expandedAd = ref<number | null>(null)
const activeView = ref('overview')

async function loadAll() {
  await store.fetchCompetitors()
}

onMounted(() => loadAll())

const fmtNum = (n: number) => n?.toLocaleString() ?? '--'

function toggleAd(index: number) {
  expandedAd.value = expandedAd.value === index ? null : index
}

// Group new ads by competitor for actionable view
const newAdsByCompetitor = computed(() => {
  const ads = store.compNewThisWeek || []
  const grouped: Record<string, any[]> = {}
  for (const ad of ads) {
    if (!grouped[ad.competitor_domain]) grouped[ad.competitor_domain] = []
    grouped[ad.competitor_domain].push(ad)
  }
  return Object.entries(grouped)
    .map(([domain, ads]) => ({ domain, ads, count: ads.length }))
    .sort((a, b) => b.count - a.count)
})

// Identify competitors with most activity change
const competitorSummaries = computed(() => {
  const domains = store.compByDomain || []
  return domains.map((d: any) => {
    const longestAds = (store.compLongestRunning || []).filter((a: any) => a.competitor_domain === d.competitor_domain)
    const newAds = (store.compNewThisWeek || []).filter((a: any) => a.competitor_domain === d.competitor_domain)
    return {
      ...d,
      topAds: longestAds.slice(0, 3),
      newCount: newAds.length,
      isAggressive: d.active_ads >= 5 || newAds.length >= 3,
    }
  })
})

const formatIcon: Record<string, string> = {
  TEXT: 'M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12',
  IMAGE: 'm2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v13.5A1.5 1.5 0 0 0 3.75 21Z',
  VIDEO: 'm15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z',
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-gray-900">Competitor Ad Intelligence</h1>
        <p class="text-sm text-gray-400 mt-0.5">What competitors are running and how long it's been live</p>
      </div>
      <div class="flex gap-1 bg-surface-card rounded-lg p-1 border border-surface-border">
        <button
          v-for="v in [{ key: 'overview', label: 'By Competitor' }, { key: 'new', label: 'New This Week' }, { key: 'proven', label: 'Proven Ads' }]"
          :key="v.key"
          class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
          :class="activeView === v.key ? 'bg-fo-action text-white' : 'text-gray-500 hover:text-gray-900'"
          @click="activeView = v.key"
        >{{ v.label }}</button>
      </div>
    </div>

    <div v-if="store.loading" class="space-y-4">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="h-24 bg-surface-card rounded-xl border border-surface-border animate-pulse" />
      </div>
    </div>

    <template v-else-if="store.compOverview">
      <!-- KPIs -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Competitors Tracked</p>
          <p class="text-2xl font-bold text-gray-900">{{ store.compOverview.competitors_tracked }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Active Ads</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.compOverview.active_ads) }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">New This Week</p>
          <p class="text-2xl font-bold text-amber">{{ fmtNum(store.compOverview.new_this_week) }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Longest Running</p>
          <p class="text-2xl font-bold text-status-up">{{ store.compOverview.longest_running ?? '--' }} <span class="text-sm font-normal text-gray-400">days</span></p>
        </div>
      </div>

      <!-- View: By Competitor -->
      <div v-if="activeView === 'overview'" class="space-y-4">
        <div
          v-for="comp in competitorSummaries"
          :key="comp.competitor_domain"
          class="bg-surface-card rounded-xl border border-surface-border overflow-hidden"
        >
          <div class="px-5 py-4 flex items-center justify-between">
            <div class="flex items-center gap-3">
              <span class="text-sm font-semibold text-gray-900">{{ comp.competitor_domain }}</span>
              <span v-if="comp.isAggressive" class="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-status-down/15 text-status-down">HIGH ACTIVITY</span>
              <span v-if="comp.newCount > 0" class="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber/15 text-amber">{{ comp.newCount }} NEW</span>
            </div>
            <div class="flex items-center gap-4 text-sm">
              <span class="text-gray-900 font-medium">{{ comp.active_ads }} active</span>
              <span class="text-gray-400">{{ comp.total_ads }} total</span>
              <span class="text-gray-400">avg {{ comp.avg_days_running }} days</span>
            </div>
          </div>
          <!-- Top ads for this competitor -->
          <div v-if="comp.topAds.length" class="border-t border-surface-border divide-y divide-surface-border">
            <div v-for="ad in comp.topAds" :key="ad.headline" class="px-5 py-3 flex items-center gap-3">
              <svg class="w-4 h-4 text-gray-400 shrink-0" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" :d="formatIcon[ad.ad_format] || formatIcon.TEXT" />
              </svg>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-gray-900 truncate">{{ ad.headline }}</p>
                <p class="text-xs text-gray-400 truncate">{{ ad.description?.slice(0, 80) }}</p>
              </div>
              <div class="text-right shrink-0">
                <span class="text-sm font-medium" :class="ad.days_running >= 90 ? 'text-status-up' : 'text-gray-700'">{{ ad.days_running }}d</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- View: New This Week -->
      <div v-if="activeView === 'new'">
        <div v-if="newAdsByCompetitor.length" class="space-y-4">
          <div v-for="group in newAdsByCompetitor" :key="group.domain" class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
            <div class="px-5 py-3 border-b border-surface-border flex items-center justify-between">
              <span class="text-sm font-semibold text-gray-900">{{ group.domain }}</span>
              <span class="text-xs text-amber font-medium">{{ group.count }} new ad{{ group.count > 1 ? 's' : '' }}</span>
            </div>
            <div class="divide-y divide-surface-border">
              <div v-for="ad in group.ads" :key="ad.headline" class="px-5 py-3">
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">{{ ad.ad_format }}</span>
                  <span class="text-xs text-gray-400">{{ new Date(ad.first_shown_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) }}</span>
                </div>
                <p class="text-sm font-medium text-gray-900">{{ ad.headline }}</p>
                <p v-if="ad.description" class="text-xs text-gray-500 mt-0.5">{{ ad.description }}</p>
                <p v-if="ad.destination_url" class="text-xs text-fo-action mt-1 truncate">{{ ad.destination_url }}</p>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="bg-surface-card rounded-xl border border-surface-border p-8 text-center">
          <p class="text-sm text-gray-500">No new competitor ads detected this week.</p>
        </div>
      </div>

      <!-- View: Proven Ads (60+ days) -->
      <div v-if="activeView === 'proven'">
        <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
          <div class="px-5 py-3 border-b border-surface-border">
            <h3 class="text-sm font-semibold text-gray-900">Ads Running 60+ Days</h3>
            <p class="text-xs text-gray-400 mt-0.5">Long-running ads indicate strong performance for these competitors</p>
          </div>
          <div class="divide-y divide-surface-border">
            <div
              v-for="(ad, i) in store.compLongestRunning"
              :key="i"
              class="hover:bg-surface-hover transition-colors cursor-pointer"
              @click="toggleAd(i)"
            >
              <div class="px-5 py-4 flex items-start gap-4">
                <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                  :class="{ 'bg-fo-action/10': ad.ad_format === 'TEXT', 'bg-amber/10': ad.ad_format === 'IMAGE', 'bg-status-down/10': ad.ad_format === 'VIDEO' }">
                  <svg class="w-5 h-5" :class="{ 'text-fo-action': ad.ad_format === 'TEXT', 'text-amber': ad.ad_format === 'IMAGE', 'text-status-down': ad.ad_format === 'VIDEO' }"
                    fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" :d="formatIcon[ad.ad_format] || formatIcon.TEXT" />
                  </svg>
                </div>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 mb-1">
                    <span class="text-sm font-medium text-fo-action">{{ ad.competitor_domain }}</span>
                    <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">{{ ad.ad_format }}</span>
                  </div>
                  <p class="text-sm text-gray-900">{{ ad.headline }}</p>
                  <p class="text-xs text-gray-400 mt-1">Running since {{ new Date(ad.first_shown_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}</p>
                </div>
                <div class="text-right shrink-0">
                  <span class="text-lg font-bold text-status-up">{{ ad.days_running }}</span>
                  <p class="text-[10px] text-gray-400">days</p>
                </div>
              </div>
              <div v-if="expandedAd === i" class="px-5 pb-4 ml-14">
                <div class="bg-surface rounded-lg p-4 border border-surface-border text-xs space-y-2">
                  <div v-if="ad.description">
                    <p class="text-gray-400 uppercase tracking-wider mb-1">Ad Copy</p>
                    <p class="text-gray-700">{{ ad.description }}</p>
                  </div>
                  <div v-if="ad.destination_url">
                    <p class="text-gray-400 uppercase tracking-wider mb-1">Landing Page</p>
                    <p class="text-fo-action">{{ ad.destination_url }}</p>
                  </div>
                  <div v-if="ad.platforms?.length">
                    <p class="text-gray-400 uppercase tracking-wider mb-1">Platforms</p>
                    <div class="flex gap-1.5">
                      <span v-for="p in ad.platforms" :key="p" class="px-2 py-0.5 rounded bg-surface-hover text-gray-700 text-[10px]">{{ p }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
