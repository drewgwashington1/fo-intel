<script setup lang="ts">
import { Bar } from 'vue-chartjs'

const store = useDashboardStore()
const { get } = useApi()

const platformDist = ref<any[]>([])
const expandedAd = ref<number | null>(null)

async function loadAll() {
  await store.fetchCompetitors()
  platformDist.value = await get('/dashboard/competitors/platform-distribution')
}

onMounted(() => loadAll())

const fmtNum = (n: number) => n?.toLocaleString() ?? '—'

function toggleAd(index: number) {
  expandedAd.value = expandedAd.value === index ? null : index
}

const domainChart = computed(() => {
  const data = store.compByDomain
  if (!data?.length) return null
  return {
    data: {
      labels: data.map((d: any) => d.competitor_domain),
      datasets: [
        { label: 'Active Ads', data: data.map((d: any) => d.active_ads), backgroundColor: '#3B6BF5' },
        { label: 'Inactive', data: data.map((d: any) => (d.total_ads - d.active_ads)), backgroundColor: '#8B95A5' },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y' as const,
      scales: {
        x: { stacked: true, grid: { display: false } },
        y: { stacked: true },
      },
    },
  }
})

const platformChart = computed(() => {
  const data = platformDist.value
  if (!data?.length) return null

  const domains = [...new Set(data.map((d: any) => d.competitor_domain))]
  const platforms = [...new Set(data.map((d: any) => d.platform))]
  const colors: Record<string, string> = { Search: '#3B6BF5', YouTube: '#F44444', Display: '#F5A623' }

  return {
    data: {
      labels: domains,
      datasets: platforms.map(platform => ({
        label: platform,
        data: domains.map(domain => {
          const row = data.find((d: any) => d.competitor_domain === domain && d.platform === platform)
          return row?.count ?? 0
        }),
        backgroundColor: colors[platform] || '#8B95A5',
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: { grid: { display: false } },
      },
    },
  }
})

const formatIcon: Record<string, string> = {
  TEXT: 'M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12',
  IMAGE: 'm2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v13.5A1.5 1.5 0 0 0 3.75 21Z',
  VIDEO: 'm15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z',
}
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-xl font-semibold text-white">Competitor Ads</h1>
      <p class="text-sm text-gray-500 mt-0.5">Google Ads Transparency Center &middot; competitor ad creative intelligence</p>
    </div>

    <div v-if="store.loading" class="space-y-6">
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-4"><div v-for="i in 5" :key="i" class="h-28 bg-surface-card rounded-xl animate-pulse" /></div>
    </div>

    <template v-else-if="store.compOverview">
      <!-- KPIs -->
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Active Ads</p>
          <p class="text-2xl font-bold text-white">{{ fmtNum(store.compOverview.active_ads) }}</p>
          <p class="text-xs mt-1 text-gray-500">across {{ store.compOverview.competitors_tracked }} competitors</p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Total Tracked</p>
          <p class="text-2xl font-bold text-white">{{ fmtNum(store.compOverview.total_ads) }}</p>
          <p class="text-xs mt-1 text-gray-500">all time</p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Longest Running</p>
          <p class="text-2xl font-bold text-status-up">{{ store.compOverview.longest_running ?? '—' }}<span class="text-sm font-normal text-gray-500 ml-1">days</span></p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Avg Run Time</p>
          <p class="text-2xl font-bold text-white">{{ store.compOverview.avg_days_running ?? '—' }}<span class="text-sm font-normal text-gray-500 ml-1">days</span></p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">New This Week</p>
          <p class="text-2xl font-bold text-amber">{{ fmtNum(store.compOverview.new_this_week) }}</p>
          <p class="text-xs mt-1 text-gray-500">launched in last 7 days</p>
        </div>
      </div>

      <!-- Charts: Ads by Domain + Platform Distribution -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div class="bg-surface-card rounded-xl border border-surface-border p-5">
          <h2 class="text-sm font-semibold text-white mb-4">Ads by Competitor</h2>
          <div class="h-56">
            <Bar v-if="domainChart" :data="domainChart.data" :options="domainChart.options" />
          </div>
        </div>

        <div class="bg-surface-card rounded-xl border border-surface-border p-5">
          <h2 class="text-sm font-semibold text-white mb-4">Platform Distribution</h2>
          <div class="h-56">
            <Bar v-if="platformChart" :data="platformChart.data" :options="platformChart.options" />
          </div>
        </div>
      </div>

      <!-- Competitor Breakdown Cards -->
      <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
        <div class="px-5 py-4 border-b border-surface-border">
          <h2 class="text-sm font-semibold text-white">Competitor Overview</h2>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 p-5">
          <div v-for="d in store.compByDomain" :key="d.competitor_domain" class="bg-surface rounded-lg p-4 border border-surface-border">
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm font-semibold text-white">{{ d.competitor_domain }}</span>
              <span class="text-[10px] uppercase tracking-wider text-gray-500">{{ d.advertiser_name }}</span>
            </div>
            <div class="grid grid-cols-3 gap-2 text-center">
              <div>
                <p class="text-lg font-bold text-fo-action">{{ d.active_ads }}</p>
                <p class="text-[10px] text-gray-500">Active</p>
              </div>
              <div>
                <p class="text-lg font-bold text-white">{{ d.max_days_running }}</p>
                <p class="text-[10px] text-gray-500">Max Days</p>
              </div>
              <div>
                <p class="text-lg font-bold text-gray-400">{{ d.avg_days_running }}</p>
                <p class="text-[10px] text-gray-500">Avg Days</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Ad Creative Cards — Longest Running -->
      <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
        <div class="px-5 py-4 border-b border-surface-border">
          <h2 class="text-sm font-semibold text-white">Top Performing Creatives</h2>
          <p class="text-xs text-gray-500 mt-0.5">Longest-running active ads &mdash; likely their best performers</p>
        </div>
        <div class="divide-y divide-surface-border">
          <div
            v-for="(ad, i) in store.compLongestRunning"
            :key="i"
            class="hover:bg-surface-hover transition-colors cursor-pointer"
            @click="toggleAd(i)"
          >
            <div class="px-5 py-4 flex items-start gap-4">
              <!-- Format icon -->
              <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                :class="{ 'bg-fo-action/10': ad.ad_format === 'TEXT', 'bg-amber/10': ad.ad_format === 'IMAGE', 'bg-status-down/10': ad.ad_format === 'VIDEO' }">
                <svg class="w-5 h-5" :class="{ 'text-fo-action': ad.ad_format === 'TEXT', 'text-amber': ad.ad_format === 'IMAGE', 'text-status-down': ad.ad_format === 'VIDEO' }"
                  fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" :d="formatIcon[ad.ad_format] || formatIcon.TEXT" />
                </svg>
              </div>

              <!-- Content -->
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-xs text-gray-500">{{ ad.competitor_domain }}</span>
                  <span class="inline-flex px-2 py-0.5 rounded text-[10px] font-semibold uppercase"
                    :class="{ 'bg-fo-action/15 text-fo-action': ad.ad_format === 'TEXT', 'bg-amber/15 text-amber': ad.ad_format === 'IMAGE', 'bg-status-down/15 text-status-down': ad.ad_format === 'VIDEO' }">
                    {{ ad.ad_format }}
                  </span>
                  <span v-if="ad.days_running >= 60" class="inline-flex px-2 py-0.5 rounded text-[10px] font-semibold bg-status-up/15 text-status-up">
                    TOP PERFORMER
                  </span>
                </div>
                <p class="text-sm font-medium text-white mb-0.5">{{ ad.headline }}</p>
                <p class="text-xs text-gray-500">{{ ad.days_running }} days &middot; since {{ new Date(ad.first_shown_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}</p>
              </div>

              <!-- Days badge -->
              <div class="text-right shrink-0">
                <span class="text-lg font-bold" :class="ad.days_running >= 60 ? 'text-status-up' : 'text-white'">{{ ad.days_running }}</span>
                <p class="text-[10px] text-gray-500">days</p>
              </div>
            </div>

            <!-- Expanded detail -->
            <div v-if="expandedAd === i" class="px-5 pb-4 ml-14">
              <div class="bg-surface rounded-lg p-4 border border-surface-border">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div>
                    <p class="text-gray-500 uppercase tracking-wider mb-1">Description</p>
                    <p class="text-gray-300">{{ ad.description }}</p>
                  </div>
                  <div>
                    <p class="text-gray-500 uppercase tracking-wider mb-1">Landing Page</p>
                    <p class="text-fo-action truncate">{{ ad.destination_url }}</p>
                  </div>
                  <div>
                    <p class="text-gray-500 uppercase tracking-wider mb-1">Platforms</p>
                    <div class="flex gap-1.5 mt-0.5">
                      <span v-for="p in ad.platforms" :key="p" class="inline-flex px-2 py-0.5 rounded bg-surface-hover text-gray-300 text-[10px]">{{ p }}</span>
                    </div>
                  </div>
                  <div>
                    <p class="text-gray-500 uppercase tracking-wider mb-1">Advertiser</p>
                    <p class="text-gray-300">{{ ad.advertiser_name }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- New This Week -->
      <div v-if="store.compNewThisWeek?.length" class="bg-surface-card rounded-xl border border-surface-border mb-6">
        <div class="px-5 py-4 border-b border-surface-border flex items-center gap-2">
          <h2 class="text-sm font-semibold text-white">New Ads This Week</h2>
          <span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber/15 text-amber">{{ store.compNewThisWeek.length }}</span>
        </div>
        <div class="divide-y divide-surface-border">
          <div v-for="ad in store.compNewThisWeek" :key="ad.headline" class="px-5 py-3 flex items-center gap-4">
            <svg class="w-4 h-4 shrink-0" :class="{ 'text-fo-action': ad.ad_format === 'TEXT', 'text-amber': ad.ad_format === 'IMAGE', 'text-status-down': ad.ad_format === 'VIDEO' }"
              fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" :d="formatIcon[ad.ad_format] || formatIcon.TEXT" />
            </svg>
            <div class="flex-1 min-w-0">
              <p class="text-sm text-white truncate">{{ ad.headline }}</p>
              <p class="text-xs text-gray-500">{{ ad.competitor_domain }} &middot; {{ ad.ad_format }}</p>
            </div>
            <span class="text-xs text-gray-500 shrink-0">{{ new Date(ad.first_shown_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) }}</span>
          </div>
        </div>
      </div>

      <!-- Insight Callout -->
      <div class="border-l-4 border-fo-action bg-surface-card rounded-r-xl p-5">
        <p class="text-[11px] uppercase tracking-wider text-gray-500 mb-2">Insight</p>
        <p class="text-sm text-white">
          <template v-if="store.compLongestRunning?.[0]">
            {{ store.compLongestRunning[0].competitor_domain }}'s longest-running creative has been active for
            <strong class="text-status-up">{{ store.compLongestRunning[0].days_running }} days</strong>,
            targeting "{{ store.compLongestRunning[0].headline }}".
            Ads running 60+ days are almost certainly profitable — study these for messaging patterns and CTAs.
          </template>
          <template v-if="store.compNewThisWeek?.length">
            {{ store.compNewThisWeek.length }} new ads detected this week across
            {{ [...new Set(store.compNewThisWeek.map((a: any) => a.competitor_domain))].length }} competitors.
          </template>
        </p>
      </div>
    </template>
  </div>
</template>
