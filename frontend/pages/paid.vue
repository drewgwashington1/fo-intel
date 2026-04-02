<script setup lang="ts">
import { Line, Bar } from 'vue-chartjs'

const store = useDashboardStore()
const { get } = useApi()

const periods = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
  { label: '1Y', days: 365 },
]

const subTabs = [
  { key: 'keywords', label: 'Paid keywords' },
  { key: 'pages', label: 'Paid pages' },
  { key: 'campaigns', label: 'Campaigns' },
  { key: 'creatives', label: 'Creatives' },
  { key: 'competitor-ads', label: 'Competitor Ads' },
] as const

type SubTab = typeof subTabs[number]['key']
const activeTab = ref<SubTab>('keywords')

const tabTitles: Record<string, string> = {
  keywords: 'Paid Performance',
  pages: 'Paid Pages',
  campaigns: 'Campaigns',
  creatives: 'Ad Creative Performance',
  'competitor-ads': 'Competitor Ad Intelligence',
}

const expandedAd = ref<number | null>(null)
const isLoss = ref<any[]>([])

// Creatives sub-tabs
const creativeTabs = ['FO Creatives', 'By Campaign'] as const

// Competitor ads filter
const selectedCompetitor = ref('all')
const competitorDomains = computed(() => {
  const domains = new Set<string>()
  for (const ad of store.compLongestRunning || []) {
    if (ad.competitor_domain) domains.add(ad.competitor_domain)
  }
  return ['all', ...Array.from(domains).sort()]
})
const filteredCompAds = computed(() => {
  const ads = store.compLongestRunning || []
  if (selectedCompetitor.value === 'all') return ads
  return ads.filter((a: any) => a.competitor_domain === selectedCompetitor.value)
})
const activeCreativeTab = ref<string>('FO Creatives')


const isLossLoaded = ref(false)

async function loadAll(force = false) {
  await Promise.allSettled([
    store.fetchPaid(force),
    store.fetchCreatives(force),
    store.fetchCompetitors(force),
  ])
  if (!isLossLoaded.value || force) {
    try {
      isLoss.value = await get('/dashboard/paid/is-loss', { days: store.periodDays })
      isLossLoaded.value = true
    } catch { isLoss.value = [] }
  }
}

async function setPeriod(days: number) {
  store.setPeriod(days)
  isLossLoaded.value = false
  await loadAll(true)
}

onMounted(() => loadAll())

/* ---- Helpers ---- */
const fmtNum = (n: number) => n?.toLocaleString() ?? '--'
const fmtMoney = (n: number) => n != null ? `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '--'
const fmtPct = (n: number) => n != null ? `${(Number(n) * 100).toFixed(1)}%` : '--'

function delta(current: number, previous: number) {
  if (!previous || !current) return { pct: 0 }
  return { pct: ((current - previous) / previous) * 100 }
}

function deltaClass(d: { pct: number }, invert = false) {
  const positive = invert ? d.pct < 0 : d.pct > 0
  return positive ? 'text-status-up' : d.pct === 0 ? 'text-gray-400' : 'text-status-down'
}

function deltaArrow(d: { pct: number }) {
  return d.pct > 0 ? '\u2191' : d.pct < 0 ? '\u2193' : '\u2192'
}

function matchDotClass(match: string): string {
  switch (match) {
    case 'EXACT': return 'bg-status-up'
    case 'PHRASE': return 'bg-amber'
    default: return 'bg-gray-500'
  }
}

function cpcColor(cpc: number): string {
  if (cpc == null) return 'text-gray-500'
  if (cpc < 2) return 'text-emerald-500'
  if (cpc < 5) return 'text-yellow-500'
  if (cpc < 10) return 'text-orange-500'
  return 'text-red-500'
}

function cpcBarColor(cpc: number): string {
  if (cpc == null) return 'bg-gray-400'
  if (cpc < 2) return 'bg-emerald-400'
  if (cpc < 5) return 'bg-yellow-400'
  if (cpc < 10) return 'bg-orange-400'
  return 'bg-red-400'
}

function cpcBarWidth(cpc: number): number {
  if (cpc == null) return 0
  return Math.min(100, (cpc / 15) * 100)
}

function positionColor(pos: number): string {
  if (pos == null) return 'text-gray-400'
  if (pos <= 3) return 'text-status-up'
  if (pos <= 10) return 'text-fo-action'
  if (pos <= 20) return 'text-amber'
  return 'text-gray-400'
}

function truncateUrl(url: string): string {
  if (!url) return '--'
  try {
    const u = new URL(url.startsWith('http') ? url : `https://${url}`)
    const path = u.pathname === '/' ? '/' : u.pathname
    return path.length > 40 ? path.slice(0, 40) + '...' : path
  } catch {
    return url.length > 40 ? url.slice(0, 40) + '...' : url
  }
}

function toggleAd(i: number) {
  expandedAd.value = expandedAd.value === i ? null : i
}

/* ---- Creatives helpers ---- */
function ctrColor(ctr: number): string {
  if (ctr >= 0.08) return 'text-status-up'
  if (ctr >= 0.04) return 'text-amber'
  return 'text-status-down'
}

function convColor(rate: number): string {
  if (rate >= 0.10) return 'text-status-up'
  if (rate >= 0.05) return 'text-amber'
  return 'text-gray-700'
}

const avgCtr = computed(() => {
  const ads = store.creativesPerformance
  if (!ads?.length) return 0
  const totalClicks = ads.reduce((s: number, a: any) => s + (a.clicks || 0), 0)
  const totalImpr = ads.reduce((s: number, a: any) => s + (a.impressions || 0), 0)
  return totalImpr > 0 ? totalClicks / totalImpr : 0
})
const avgConvRate = computed(() => {
  const ads = store.creativesPerformance
  if (!ads?.length) return 0
  const totalConv = ads.reduce((s: number, a: any) => s + (a.conversions || 0), 0)
  const totalClicks = ads.reduce((s: number, a: any) => s + (a.clicks || 0), 0)
  return totalClicks > 0 ? totalConv / totalClicks : 0
})

function performanceSignal(ad: any): { label: string; class: string } {
  const ctr = ad.ctr || 0
  const conv = ad.conv_rate || 0
  const ctrRatio = avgCtr.value > 0 ? ctr / avgCtr.value : 1
  const convRatio = avgConvRate.value > 0 ? conv / avgConvRate.value : 1

  if (ctrRatio >= 1.3 && convRatio >= 1.2) return { label: 'Strong', class: 'bg-status-up/15 text-status-up' }
  if (ctrRatio >= 1.1 || convRatio >= 1.1) return { label: 'Good', class: 'bg-fo-action/15 text-fo-action' }
  if (ctrRatio < 0.7 || convRatio < 0.5) return { label: 'Needs Work', class: 'bg-status-down/15 text-status-down' }
  return { label: 'Average', class: 'bg-gray-100 text-gray-500' }
}

const campaignTypeLabel: Record<string, string> = {
  SEARCH: 'Search',
  DEMAND_GEN: 'DemandGen',
  PERFORMANCE_MAX: 'PMax',
  DISPLAY: 'Display',
  VIDEO: 'Video',
  SHOPPING: 'Shopping',
}

function adIdentifier(ad: any): string {
  const typeLabel = campaignTypeLabel[ad.campaign_type] || ad.campaign_type || ad.ad_type || 'Ad'
  // Find variation number within this campaign
  const campaignAds = store.creativesPerformance?.filter((a: any) => a.campaign_name === ad.campaign_name) || []
  const idx = campaignAds.findIndex((a: any) => a.ad_id === ad.ad_id) + 1
  return `${typeLabel} #${idx || ad.ad_id}`
}

/* ---- Competitor helpers ---- */
const formatIcon: Record<string, string> = {
  TEXT: 'M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12',
  IMAGE: 'm2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v13.5A1.5 1.5 0 0 0 3.75 21Z',
  VIDEO: 'm15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z',
}

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

/* ---- Date range ---- */
const dateRangeLabel = computed(() => {
  const now = new Date()
  const start = new Date(now)
  start.setDate(start.getDate() - store.periodDays)
  const fmt = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  return `${fmt(start)} - ${fmt(now)}`
})

/* ---- Charts ---- */
const spendChart = computed(() => {
  const data = store.paidTimeline
  if (!data?.length) return null
  return {
    data: {
      labels: data.map((d: any) => new Date(d.data_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
      datasets: [
        {
          label: 'Spend ($)',
          data: data.map((d: any) => d.spend),
          borderColor: '#3B6BF5',
          backgroundColor: 'rgba(59,107,245,0.08)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2,
          yAxisID: 'y',
        },
        {
          label: 'Clicks',
          data: data.map((d: any) => d.clicks),
          borderColor: '#1BB981',
          backgroundColor: 'transparent',
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index' as const, intersect: false },
      plugins: { legend: { labels: { color: '#9CA3AF', boxWidth: 12, padding: 16 } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#6B7280', font: { size: 10 } } },
        y: { position: 'left' as const, grid: { color: 'rgba(0,0,0,0.06)' }, ticks: { color: '#6B7280', font: { size: 10 } } },
        y1: { position: 'right' as const, grid: { drawOnChartArea: false }, ticks: { color: '#6B7280', font: { size: 10 } } },
      },
    },
  }
})

const pagesChart = computed(() => {
  const data = store.paidTimeline
  if (!data?.length) return null
  return {
    data: {
      labels: data.map((d: any) => new Date(d.data_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
      datasets: [
        {
          label: 'Paid Traffic',
          data: data.map((d: any) => d.clicks),
          borderColor: '#F5A623',
          backgroundColor: 'rgba(245,166,35,0.08)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2,
          yAxisID: 'y',
        },
        {
          label: 'Impressions',
          data: data.map((d: any) => d.impressions),
          borderColor: '#3B6BF5',
          backgroundColor: 'transparent',
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index' as const, intersect: false },
      plugins: { legend: { labels: { color: '#9CA3AF', boxWidth: 12, padding: 16 } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#6B7280', font: { size: 10 } } },
        y: { position: 'left' as const, grid: { color: 'rgba(0,0,0,0.06)' }, ticks: { color: '#6B7280', font: { size: 10 } } },
        y1: { position: 'right' as const, grid: { drawOnChartArea: false }, ticks: { color: '#6B7280', font: { size: 10 } } },
      },
    },
  }
})

const isLossChart = computed(() => {
  if (!isLoss.value?.length) return null
  return {
    data: {
      labels: isLoss.value.map((d: any) => d.campaign_name),
      datasets: [
        { label: 'IS Won %', data: isLoss.value.map((d: any) => d.is_pct), backgroundColor: '#1BB981' },
        { label: 'Lost to Budget %', data: isLoss.value.map((d: any) => d.lost_budget_pct), backgroundColor: '#F5A623' },
        { label: 'Lost to Rank %', data: isLoss.value.map((d: any) => d.lost_rank_pct), backgroundColor: '#F44444' },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y' as const,
      plugins: { legend: { labels: { color: '#9CA3AF', boxWidth: 12, padding: 16 } } },
      scales: {
        x: { stacked: true, max: 100, grid: { color: 'rgba(0,0,0,0.06)' }, ticks: { color: '#6B7280' } },
        y: { stacked: true, ticks: { color: '#9CA3AF', font: { size: 11 } } },
      },
    },
  }
})

const pagesTotalTraffic = computed(() => {
  return store.paidPages?.reduce((sum: number, p: any) => sum + (p.organic_traffic || 0), 0) ?? 0
})

function downloadCsv() {
  window.open(`${useRuntimeConfig().public.apiBase}/dashboard/paid/export?days=${store.periodDays}`, '_blank')
}
</script>

<template>
  <div>
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-2">
        <h1 class="text-xl font-semibold text-gray-900">{{ tabTitles[activeTab] }}</h1>
      </div>
      <div class="flex items-center gap-3">
        <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-500 hover:text-gray-900 transition-colors" @click="downloadCsv">
          Export CSV
        </button>
        <div class="flex gap-0.5 bg-surface-card rounded-lg p-1 border border-surface-border">
          <button v-for="p in periods" :key="p.days" class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors" :class="store.periodDays === p.days ? 'bg-fo-action text-white' : 'text-gray-500 hover:text-gray-900'" @click="setPeriod(p.days)">{{ p.label }}</button>
        </div>
      </div>
    </div>

    <!-- Sub-tabs -->
    <div class="border-b border-surface-border mb-4">
      <nav class="flex gap-6">
        <button
          v-for="tab in subTabs" :key="tab.key"
          class="relative pb-3 text-sm font-medium transition-colors"
          :class="activeTab === tab.key ? 'text-fo-action' : 'text-gray-400 hover:text-gray-700'"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span v-if="activeTab === tab.key" class="absolute bottom-0 left-0 right-0 h-0.5 bg-fo-action rounded-full" />
        </button>
      </nav>
    </div>

    <!-- Loading -->
    <div v-if="store.loading" class="space-y-6">
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-4"><div v-for="i in 5" :key="i" class="h-28 bg-surface-card rounded-xl animate-pulse" /></div>
      <div class="h-72 bg-surface-card rounded-xl animate-pulse" />
    </div>

    <!-- ===== TAB: Paid Keywords ===== -->
    <template v-else-if="activeTab === 'keywords' && store.paidOverview">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Percentage of eligible impressions your ads received">Impression Share</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtPct(store.paidOverview.avg_impression_share) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.paidOverview.avg_impression_share, store.paidOverview.prev_impression_share))">
            {{ deltaArrow(delta(store.paidOverview.avg_impression_share, store.paidOverview.prev_impression_share)) }}
            {{ Math.abs(delta(store.paidOverview.avg_impression_share, store.paidOverview.prev_impression_share).pct).toFixed(1) }}%
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Average cost per click across all paid campaigns">Avg CPC</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtMoney(store.paidOverview.avg_cpc) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.paidOverview.avg_cpc, store.paidOverview.prev_cpc), true)">
            {{ deltaArrow(delta(store.paidOverview.avg_cpc, store.paidOverview.prev_cpc)) }}
            {{ Math.abs(delta(store.paidOverview.avg_cpc, store.paidOverview.prev_cpc).pct).toFixed(1) }}%
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Total clicks received from paid search ads">Total Clicks</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.paidOverview.total_clicks) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.paidOverview.total_clicks, store.paidOverview.prev_clicks))">
            {{ deltaArrow(delta(store.paidOverview.total_clicks, store.paidOverview.prev_clicks)) }}
            {{ Math.abs(delta(store.paidOverview.total_clicks, store.paidOverview.prev_clicks).pct).toFixed(1) }}%
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Actions completed after clicking your ad (form fills, calls, etc.)">Conversions</p>
          <p class="text-2xl font-bold text-gray-900">{{ Math.round(store.paidOverview.total_conversions).toLocaleString() }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.paidOverview.total_conversions, store.paidOverview.prev_conversions))">
            {{ deltaArrow(delta(store.paidOverview.total_conversions, store.paidOverview.prev_conversions)) }}
            {{ Math.abs(delta(store.paidOverview.total_conversions, store.paidOverview.prev_conversions).pct).toFixed(1) }}%
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3 mb-3">
        <span class="text-sm text-gray-900 font-medium">{{ store.paidSearchTerms?.length ?? 0 }} keywords</span>
        <span class="text-xs text-gray-400">&middot;</span>
        <span class="text-xs text-gray-400">{{ dateRangeLabel }}</span>
      </div>

      <div class="bg-surface-card rounded-xl border border-surface-border">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-400 border-b border-surface-border">
                <th class="text-left px-4 py-3 w-10" title="Row number">#</th>
                <th class="text-left px-4 py-3" title="Search term that triggered your paid ad">Keyword</th>
                <th class="text-center px-3 py-3 w-10" title="Ad match type — Exact, Phrase, or Broad">Ad</th>
                <th class="text-right px-4 py-3 w-20" title="Estimated monthly search volume">Volume</th>
                <th class="text-left px-4 py-3 w-36" title="Cost per click — amount paid each time someone clicks your ad">CPC</th>
                <th class="text-right px-4 py-3 w-20" title="Number of clicks from this search term">Traffic</th>
                <th class="text-right px-4 py-3 w-20" title="Average ad position for this keyword">Position</th>
                <th class="text-left px-4 py-3" title="Landing page URL for this search term">URL</th>
                <th class="text-right px-4 py-3 w-24" title="Organic (non-paid) clicks for the same keyword">Organic traffic</th>
                <th class="text-right px-4 py-3 w-24" title="Organic ranking position for the same keyword">Organic position</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(t, i) in store.paidSearchTerms" :key="t.search_term" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                <td class="px-4 py-3 text-gray-400 text-xs">{{ i + 1 }}</td>
                <td class="px-4 py-3 text-gray-900 font-medium">{{ t.search_term }}</td>
                <td class="px-3 py-3 text-center">
                  <span v-if="t.match_type" class="inline-block w-2.5 h-2.5 rounded-full" :class="matchDotClass(t.match_type)" :title="t.match_type"></span>
                </td>
                <td class="px-4 py-3 text-right text-gray-500">{{ t.volume != null ? fmtNum(t.volume) : '--' }}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <div class="w-16 h-2 rounded-full bg-surface-border overflow-hidden">
                      <div class="h-full rounded-full" :class="cpcBarColor(t.cpc)" :style="{ width: cpcBarWidth(t.cpc) + '%' }"></div>
                    </div>
                    <span class="text-xs" :class="cpcColor(t.cpc)">{{ fmtMoney(t.cpc) }}</span>
                  </div>
                </td>
                <td class="px-4 py-3 text-right text-gray-900 font-bold">{{ fmtNum(t.clicks) }}</td>
                <td class="px-4 py-3 text-right" :class="positionColor(t.organic_position)">
                  {{ t.organic_position != null ? Math.round(t.organic_position) : '--' }}
                </td>
                <td class="px-4 py-3">
                  <span v-if="t.top_url" class="text-fo-action text-xs truncate max-w-[200px] inline-block" :title="t.top_url">{{ truncateUrl(t.top_url) }}</span>
                  <span v-else class="text-gray-400 text-xs">--</span>
                </td>
                <td class="px-4 py-3 text-right text-gray-500">{{ t.organic_traffic != null ? fmtNum(t.organic_traffic) : '--' }}</td>
                <td class="px-4 py-3 text-right" :class="positionColor(t.organic_position)">
                  {{ t.organic_position != null ? Math.round(t.organic_position) : '--' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ===== TAB: Paid Pages ===== -->
    <template v-else-if="activeTab === 'pages' && store.paidOverview">
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <h2 class="text-sm font-semibold text-gray-900 mb-4">Paid Traffic & Impressions</h2>
        <div class="h-64">
          <Line v-if="pagesChart" :data="pagesChart.data" :options="pagesChart.options" />
        </div>
      </div>

      <div class="flex items-center gap-3 mb-3">
        <span class="text-sm text-gray-900 font-medium">{{ store.paidPages?.length ?? 0 }} pages</span>
        <span class="text-xs text-gray-400">&middot;</span>
        <span class="text-xs text-gray-400">Total traffic: {{ fmtNum(pagesTotalTraffic) }}</span>
        <span class="text-xs text-gray-400">&middot;</span>
        <span class="text-xs text-gray-400">{{ dateRangeLabel }}</span>
      </div>

      <div class="bg-surface-card rounded-xl border border-surface-border">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-400 border-b border-surface-border">
                <th class="text-left px-5 py-3" title="Landing page URL receiving paid traffic">URL</th>
                <th class="text-right px-5 py-3" title="Organic clicks on pages that also have paid search terms">Organic Clicks</th>
                <th class="text-right px-5 py-3" title="Number of times ads linking to this page were shown">Impressions</th>
                <th class="text-right px-5 py-3" title="Click-through rate — clicks divided by impressions">CTR</th>
                <th class="text-right px-5 py-3" title="Average ad position for this landing page">Avg Position</th>
                <th class="text-right px-5 py-3" title="Number of unique keywords driving paid traffic to this page">Keywords</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pg in store.paidPages" :key="pg.url" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                <td class="px-5 py-3">
                  <span class="text-fo-action text-xs truncate max-w-[280px] inline-block" :title="pg.url">{{ truncateUrl(pg.url) }}</span>
                </td>
                <td class="px-5 py-3 text-right text-gray-900 font-medium">{{ fmtNum(pg.organic_traffic) }}</td>
                <td class="px-5 py-3 text-right text-gray-700">{{ fmtNum(pg.impressions) }}</td>
                <td class="px-5 py-3 text-right text-gray-700">{{ pg.ctr != null ? (pg.ctr * 100).toFixed(1) + '%' : '--' }}</td>
                <td class="px-5 py-3 text-right" :class="positionColor(pg.avg_position)">
                  {{ pg.avg_position != null ? Math.round(pg.avg_position) : '--' }}
                </td>
                <td class="px-5 py-3 text-right text-gray-700">{{ pg.total_keywords ?? '--' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ===== TAB: Campaigns ===== -->
    <template v-else-if="activeTab === 'campaigns' && store.paidOverview">
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <h2 class="text-sm font-semibold text-gray-900 mb-4">Spend & Clicks Trend</h2>
        <div class="h-64">
          <Line v-if="spendChart" :data="spendChart.data" :options="spendChart.options" />
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div class="bg-surface-card rounded-xl border border-surface-border p-5">
          <h2 class="text-sm font-semibold text-gray-900 mb-1">Impression Share Analysis</h2>
          <p class="text-xs text-gray-400 mb-4">Won vs lost to budget vs lost to rank</p>
          <div class="h-56">
            <Bar v-if="isLossChart" :data="isLossChart.data" :options="isLossChart.options" />
          </div>
        </div>
        <div class="bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-gray-900">IS Loss Detail</h2>
          </div>
          <div class="p-5 space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-surface rounded-lg p-4 text-center">
                <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Average percentage of impressions lost due to insufficient daily budget">Avg Lost to Budget</p>
                <p class="text-xl font-bold text-amber">{{ (Number(store.paidOverview.avg_lost_budget) * 100).toFixed(1) }}%</p>
              </div>
              <div class="bg-surface rounded-lg p-4 text-center">
                <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Average percentage of impressions lost due to low ad rank or quality score">Avg Lost to Rank</p>
                <p class="text-xl font-bold text-status-down">{{ (Number(store.paidOverview.avg_lost_rank) * 100).toFixed(1) }}%</p>
              </div>
            </div>
            <div v-if="Number(store.paidOverview.avg_lost_rank) > Number(store.paidOverview.avg_lost_budget)" class="border-l-4 border-status-down bg-status-down/5 rounded-r-lg p-3">
              <p class="text-xs text-gray-700">Losing more IS to <strong class="text-gray-900">Ad Rank</strong> than budget. Consider improving Quality Score, ad relevance, and expected CTR to recover lost impressions.</p>
            </div>
            <div v-else class="border-l-4 border-amber bg-amber/5 rounded-r-lg p-3">
              <p class="text-xs text-gray-700">Losing more IS to <strong class="text-gray-900">Budget</strong> than rank. Consider increasing daily budgets on high-converting campaigns to capture additional impression share.</p>
            </div>
          </div>
        </div>
      </div>

      <div class="bg-surface-card rounded-xl border border-surface-border">
        <div class="px-5 py-4 border-b border-surface-border">
          <h2 class="text-sm font-semibold text-gray-900">Campaign Performance</h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-400 border-b border-surface-border">
                <th class="text-left px-5 py-3" title="Google Ads campaign name">Campaign</th>
                <th class="text-right px-5 py-3" title="Total spend for this campaign">Spend</th>
                <th class="text-right px-5 py-3" title="Total clicks received">Clicks</th>
                <th class="text-right px-5 py-3" title="Average cost per click">CPC</th>
                <th class="text-right px-5 py-3" title="Actions completed after clicking your ad (form fills, calls, etc.)">Conv</th>
                <th class="text-right px-5 py-3" title="Percentage of eligible impressions your ads received">IS%</th>
                <th class="text-right px-5 py-3" title="Percentage of impressions lost because of insufficient budget">Lost Budget%</th>
                <th class="text-right px-5 py-3" title="Percentage of impressions lost because of low ad rank or quality score">Lost Rank%</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in store.paidCampaigns" :key="c.campaign_name" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                <td class="px-5 py-3 text-gray-900 font-medium">{{ c.campaign_name }}</td>
                <td class="px-5 py-3 text-right text-gray-700">{{ fmtMoney(c.spend) }}</td>
                <td class="px-5 py-3 text-right text-gray-700">{{ fmtNum(c.clicks) }}</td>
                <td class="px-5 py-3 text-right" :class="cpcColor(c.cpc)">{{ fmtMoney(c.cpc) }}</td>
                <td class="px-5 py-3 text-right text-gray-700">{{ c.conversions?.toFixed(1) }}</td>
                <td class="px-5 py-3 text-right text-gray-900 font-medium">{{ fmtPct(c.avg_is) }}</td>
                <td class="px-5 py-3 text-right text-amber">{{ fmtPct(c.avg_lost_budget) }}</td>
                <td class="px-5 py-3 text-right text-status-down">{{ fmtPct(c.avg_lost_rank) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ===== TAB: Creatives ===== -->
    <template v-else-if="activeTab === 'creatives'">
      <!-- Creatives KPI Cards -->
      <div v-if="store.creativesOverview" class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Number of ad creatives currently running">Active Creatives</p>
          <p class="text-2xl font-bold text-gray-900">{{ store.creativesOverview.total_creatives }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Total clicks across all ad creatives">Total Clicks</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.creativesOverview.total_clicks) }}</p>
          <p v-if="store.creativesOverview.prev_clicks" class="text-xs mt-0.5"
            :class="deltaClass(delta(store.creativesOverview.total_clicks, store.creativesOverview.prev_clicks))">
            {{ deltaArrow(delta(store.creativesOverview.total_clicks, store.creativesOverview.prev_clicks)) }}
            {{ Math.abs(delta(store.creativesOverview.total_clicks, store.creativesOverview.prev_clicks).pct).toFixed(1) }}%
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Average click-through rate across all ad creatives">Avg Click Rate</p>
          <p class="text-2xl font-bold" :class="ctrColor(store.creativesOverview.avg_ctr)">{{ fmtPct(store.creativesOverview.avg_ctr) }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Total conversions across all ad creatives">Conversions</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(Math.round(store.creativesOverview.total_conversions)) }}</p>
        </div>
      </div>

      <!-- Creatives sub-tabs -->
      <div class="flex gap-1 bg-surface-card rounded-lg p-1 border border-surface-border mb-6 w-fit">
        <button
          v-for="tab in creativeTabs"
          :key="tab"
          class="px-4 py-1.5 rounded-md text-xs font-medium transition-colors"
          :class="activeCreativeTab === tab ? 'bg-fo-action text-white' : 'text-gray-500 hover:text-gray-900'"
          @click="activeCreativeTab = tab"
        >{{ tab }}</button>
      </div>

      <div v-if="store.creativesLoading" class="h-64 bg-surface-card rounded-xl border border-surface-border animate-pulse" />

      <template v-else>
        <!-- FO Creatives -->
        <div v-if="activeCreativeTab === 'FO Creatives'">
          <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
            <div class="px-5 py-3 border-b border-surface-border">
              <h3 class="text-sm font-semibold text-gray-900">Ad Creative Performance</h3>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-surface-border">
                    <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Ad creative identifier and parent campaign">Ad / Campaign</th>
                    <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Campaign type (Search, DemandGen, PMax, etc.)">Type</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Total clicks this ad creative received">Clicks</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Click-through rate — clicks divided by impressions">Click Rate</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Actions completed after clicking this ad">Conversions</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Conversion rate — conversions divided by clicks">Conv Rate</th>
                    <th class="text-center px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Performance signal based on CTR and conversion rate vs average (Strong, Good, Average, Needs Work)">Performance</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="ad in store.creativesPerformance"
                    :key="ad.ad_id"
                    class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                  >
                    <td class="px-4 py-3">
                      <div class="max-w-sm">
                        <p class="text-sm font-medium text-gray-900 truncate">{{ adIdentifier(ad) }}</p>
                        <p class="text-xs text-gray-500 truncate mt-0.5">{{ ad.campaign_name }}</p>
                        <p class="text-[10px] text-gray-400 mt-0.5">ID: {{ ad.ad_id }}</p>
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">{{ ad.campaign_type || ad.ad_type }}</span>
                    </td>
                    <td class="px-4 py-3 text-right font-medium text-gray-900">{{ fmtNum(ad.clicks) }}</td>
                    <td class="px-4 py-3 text-right font-medium" :class="ctrColor(ad.ctr)">{{ fmtPct(ad.ctr) }}</td>
                    <td class="px-4 py-3 text-right font-medium text-gray-900">{{ Math.round(ad.conversions || 0) }}</td>
                    <td class="px-4 py-3 text-right" :class="convColor(ad.conv_rate)">{{ fmtPct(ad.conv_rate) }}</td>
                    <td class="px-4 py-3 text-center">
                      <span class="text-[10px] font-semibold px-2 py-1 rounded-full" :class="performanceSignal(ad).class">
                        {{ performanceSignal(ad).label }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="!store.creativesPerformance?.length" class="p-8 text-center">
              <p class="text-sm text-gray-500">No creative performance data. Run the Ad Creatives pipeline first.</p>
            </div>
          </div>
        </div>

        <!-- By Campaign -->
        <div v-if="activeCreativeTab === 'By Campaign'">
          <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
            <div class="px-5 py-3 border-b border-surface-border">
              <h3 class="text-sm font-semibold text-gray-900">Creative Performance by Campaign</h3>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-surface-border">
                    <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Google Ads campaign name">Campaign</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Number of ad creatives in this campaign">Creatives</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Total clicks across all creatives in this campaign">Clicks</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Click-through rate — clicks divided by impressions">Click Rate</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Total conversions from this campaign's creatives">Conversions</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium" title="Conversion rate — conversions divided by clicks">Conv Rate</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="c in store.creativesByCampaign"
                    :key="c.campaign_name"
                    class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                  >
                    <td class="px-4 py-3 font-medium text-gray-900">{{ c.campaign_name }}</td>
                    <td class="px-4 py-3 text-right text-gray-700">{{ c.creatives }}</td>
                    <td class="px-4 py-3 text-right font-medium text-gray-900">{{ fmtNum(c.clicks) }}</td>
                    <td class="px-4 py-3 text-right" :class="ctrColor(c.ctr)">{{ fmtPct(c.ctr) }}</td>
                    <td class="px-4 py-3 text-right font-medium text-gray-900">{{ Math.round(c.conversions || 0) }}</td>
                    <td class="px-4 py-3 text-right" :class="convColor(c.conv_rate)">{{ fmtPct(c.conv_rate) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Top Headlines -->
        <div v-if="activeCreativeTab === 'Top Headlines'">
          <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
            <div class="px-5 py-3 border-b border-surface-border">
              <h3 class="text-sm font-semibold text-gray-900">Headline Performance Ranking</h3>
              <p class="text-xs text-gray-400 mt-0.5">Which headlines drive the most clicks and conversions</p>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-surface-border">
                    <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium w-8">#</th>
                    <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Headline</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Ads</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Impr</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Clicks</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">CTR</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Conv</th>
                    <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Conv Rate</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(h, i) in store.creativesTopHeadlines"
                    :key="h.headline_1"
                    class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                  >
                    <td class="px-4 py-3 text-gray-400 text-xs">{{ i + 1 }}</td>
                    <td class="px-4 py-3 font-medium text-gray-900">{{ h.headline_1 }}</td>
                    <td class="px-4 py-3 text-right text-gray-500">{{ h.used_in_ads }}</td>
                    <td class="px-4 py-3 text-right text-gray-700">{{ fmtNum(h.impressions) }}</td>
                    <td class="px-4 py-3 text-right font-medium text-gray-900">{{ fmtNum(h.clicks) }}</td>
                    <td class="px-4 py-3 text-right" :class="ctrColor(h.ctr)">{{ fmtPct(h.ctr) }}</td>
                    <td class="px-4 py-3 text-right font-medium text-gray-900">{{ h.conversions?.toFixed(1) }}</td>
                    <td class="px-4 py-3 text-right" :class="convColor(h.conv_rate)">{{ fmtPct(h.conv_rate) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- ===== TAB: Competitor Ads ===== -->
    <template v-else-if="activeTab === 'competitor-ads'">
      <!-- Competitor KPIs -->
      <div v-if="store.compOverview" class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Number of competitor domains being monitored">Competitors Tracked</p>
          <p class="text-2xl font-bold text-gray-900">{{ store.compOverview.competitors_tracked }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Total currently running ads across all tracked competitors">Active Ads</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.compOverview.active_ads) }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Competitor ads first detected in the last 7 days">New This Week</p>
          <p class="text-2xl font-bold text-amber">{{ fmtNum(store.compOverview.new_this_week) }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Duration of the longest continuously running competitor ad">Longest Running</p>
          <p class="text-2xl font-bold text-status-up">{{ store.compOverview.longest_running ?? '--' }} <span class="text-sm font-normal text-gray-400">days</span></p>
        </div>
      </div>

      <!-- Competitor filter -->
      <div class="flex items-center gap-3 mb-4">
        <select
          v-model="selectedCompetitor"
          class="px-3 py-2 text-xs rounded-lg border border-surface-border bg-surface-card focus:outline-none focus:border-fo-action"
        >
          <option v-for="d in competitorDomains" :key="d" :value="d">
            {{ d === 'all' ? 'All Competitors' : d }}
          </option>
        </select>
        <span class="text-xs text-gray-400">{{ filteredCompAds.length }} ads</span>
      </div>

      <!-- Competitor ads table -->
      <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-surface-border">
                <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Competitor</th>
                <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Ad Copy</th>
                <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Landing Page</th>
                <th class="text-center px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Type</th>
                <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Started</th>
                <th class="text-center px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="ad in filteredCompAds"
                :key="ad.headline + ad.competitor_domain"
                class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
              >
                <td class="px-4 py-3">
                  <span class="text-sm font-medium text-fo-action">{{ ad.competitor_domain }}</span>
                </td>
                <td class="px-4 py-3 max-w-md">
                  <p class="text-sm text-gray-900 font-medium">{{ ad.headline }}</p>
                  <p v-if="ad.description" class="text-xs text-gray-500 mt-0.5 line-clamp-2">{{ ad.description }}</p>
                </td>
                <td class="px-4 py-3">
                  <span v-if="ad.destination_url" class="text-xs text-fo-action truncate max-w-[200px] inline-block" :title="ad.destination_url">{{ ad.destination_url }}</span>
                  <span v-else class="text-xs text-gray-400">--</span>
                </td>
                <td class="px-4 py-3 text-center">
                  <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">{{ ad.ad_format }}</span>
                </td>
                <td class="px-4 py-3 text-xs text-gray-500">
                  {{ ad.first_shown_date ? new Date(ad.first_shown_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '--' }}
                </td>
                <td class="px-4 py-3 text-center">
                  <span class="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    :class="ad.is_active ? 'bg-status-up/15 text-status-up' : 'bg-gray-100 text-gray-400'"
                  >{{ ad.is_active ? 'Live' : 'Ended' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!filteredCompAds?.length" class="p-8 text-center">
          <p class="text-sm text-gray-500">No competitor ads data. Run the Competitor Ads pipeline.</p>
        </div>
      </div>
    </template>
  </div>
</template>
