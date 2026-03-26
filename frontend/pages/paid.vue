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
  { key: 'ads', label: 'Ads' },
  { key: 'pages', label: 'Paid pages' },
  { key: 'campaigns', label: 'Campaigns' },
] as const

type SubTab = typeof subTabs[number]['key']
const activeTab = ref<SubTab>('keywords')

const tabTitles: Record<SubTab, string> = {
  keywords: 'Paid Performance',
  ads: 'Ads',
  pages: 'Paid Pages',
  campaigns: 'Campaigns',
}

const expandedAd = ref<number | null>(null)
const isLoss = ref<any[]>([])
const adsTrafficTab = ref<'traffic' | 'paid'>('paid')

async function loadAll() {
  await store.fetchPaid()
  try {
    isLoss.value = await get('/dashboard/paid/is-loss', { days: store.periodDays })
  } catch { isLoss.value = [] }
}

async function setPeriod(days: number) {
  store.setPeriod(days)
  await loadAll()
}

onMounted(() => loadAll())

/* ── Helpers ── */
const fmtNum = (n: number) => n?.toLocaleString() ?? '—'
const fmtMoney = (n: number) => n != null ? `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'
const fmtPct = (n: number) => n != null ? `${(Number(n) * 100).toFixed(1)}%` : '—'

function delta(current: number, previous: number) {
  if (!previous || !current) return { pct: 0 }
  return { pct: ((current - previous) / previous) * 100 }
}

function deltaClass(d: { pct: number }, invert = false) {
  const positive = invert ? d.pct < 0 : d.pct > 0
  return positive ? 'text-status-up' : d.pct === 0 ? 'text-gray-500' : 'text-status-down'
}

function deltaArrow(d: { pct: number }) {
  return d.pct > 0 ? '\u2191' : d.pct < 0 ? '\u2193' : '\u2192'
}

function matchBadgeClass(match: string): string {
  switch (match) {
    case 'EXACT': return 'bg-status-up/15 text-status-up'
    case 'PHRASE': return 'bg-amber/15 text-amber'
    default: return 'bg-gray-500/15 text-gray-400'
  }
}

function matchDotClass(match: string): string {
  switch (match) {
    case 'EXACT': return 'bg-status-up'
    case 'PHRASE': return 'bg-amber'
    default: return 'bg-gray-500'
  }
}

function cpcColor(cpc: number): string {
  if (cpc == null) return 'text-gray-400'
  if (cpc < 2) return 'text-emerald-400'
  if (cpc < 5) return 'text-yellow-400'
  if (cpc < 10) return 'text-orange-400'
  return 'text-red-400'
}

function cpcBarColor(cpc: number): string {
  if (cpc == null) return 'bg-gray-600'
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
  if (pos == null) return 'text-gray-500'
  if (pos <= 3) return 'text-status-up'
  if (pos <= 10) return 'text-fo-action'
  if (pos <= 20) return 'text-amber'
  return 'text-gray-500'
}

function truncateUrl(url: string): string {
  if (!url) return '—'
  try {
    const u = new URL(url.startsWith('http') ? url : `https://${url}`)
    const path = u.pathname === '/' ? '' : u.pathname
    return `firstorion.com${path.length > 30 ? path.slice(0, 30) + '...' : path}`
  } catch {
    return url.length > 40 ? url.slice(0, 40) + '...' : url
  }
}

function toggleAd(i: number) {
  expandedAd.value = expandedAd.value === i ? null : i
}

const formatIcon: Record<string, string> = {
  TEXT: 'M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12',
  IMAGE: 'm2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v13.5A1.5 1.5 0 0 0 3.75 21Z',
  VIDEO: 'm15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z',
}

/* ── Sparkline SVG generator ── */
function generateSparkline(index: number, variant: number = 0): string {
  const timeline = store.paidTimeline
  if (!timeline?.length) return ''
  const seed = index * 17 + variant * 7
  const points: number[] = []
  for (let i = 0; i < Math.min(timeline.length, 12); i++) {
    const base = variant === 0 ? (timeline[i]?.clicks || 0) : (timeline[i]?.impressions || 0)
    const jitter = Math.sin(seed + i * 2.3) * 0.3 + 0.85
    points.push(base * jitter)
  }
  if (points.length < 2) return ''
  const max = Math.max(...points, 1)
  const min = Math.min(...points, 0)
  const range = max - min || 1
  const w = 120
  const h = 28
  const coords = points.map((v, i) => {
    const x = (i / (points.length - 1)) * w
    const y = h - ((v - min) / range) * (h - 4) - 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return coords.join(' ')
}

/* ── Date range label ── */
const dateRangeLabel = computed(() => {
  const now = new Date()
  const start = new Date(now)
  start.setDate(start.getDate() - store.periodDays)
  const fmt = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  return `${fmt(start)} - ${fmt(now)}`
})

/* ── Charts ── */
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
        y: { position: 'left' as const, grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6B7280', font: { size: 10 } } },
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
        y: { position: 'left' as const, grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6B7280', font: { size: 10 } } },
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
        x: { stacked: true, max: 100, grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6B7280' } },
        y: { stacked: true, ticks: { color: '#9CA3AF', font: { size: 11 } } },
      },
    },
  }
})

/* ── Paid pages totals ── */
const pagesTotalTraffic = computed(() => {
  return store.paidPages?.reduce((sum: number, p: any) => sum + (p.organic_traffic || 0), 0) ?? 0
})

/* ── Export CSV ── */
function downloadCsv() {
  window.open(`${useRuntimeConfig().public.apiBase}/dashboard/paid/export?days=${store.periodDays}`, '_blank')
}
</script>

<template>
  <div>
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-2">
        <h1 class="text-xl font-semibold text-white">{{ tabTitles[activeTab] }}</h1>
      </div>
      <div class="flex items-center gap-3">
        <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-400 hover:text-white transition-colors" @click="downloadCsv">
          Export CSV
        </button>
        <div class="flex gap-0.5 bg-surface-card rounded-lg p-1 border border-surface-border">
          <button v-for="p in periods" :key="p.days" class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors" :class="store.periodDays === p.days ? 'bg-fo-action text-white' : 'text-gray-400 hover:text-white'" @click="setPeriod(p.days)">{{ p.label }}</button>
        </div>
      </div>
    </div>

    <!-- Sub-tabs -->
    <div class="border-b border-surface-border mb-4">
      <nav class="flex gap-6">
        <button
          v-for="tab in subTabs" :key="tab.key"
          class="relative pb-3 text-sm font-medium transition-colors"
          :class="activeTab === tab.key ? 'text-fo-action' : 'text-gray-500 hover:text-gray-300'"
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

    <!-- ===== TAB 1: Paid Keywords ===== -->
    <template v-else-if="activeTab === 'keywords' && store.paidOverview">
      <!-- KPIs -->
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Total Spend</p>
          <p class="text-2xl font-bold text-white">{{ fmtMoney(store.paidOverview.total_spend) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.paidOverview.total_spend, store.paidOverview.prev_spend), true)">
            {{ deltaArrow(delta(store.paidOverview.total_spend, store.paidOverview.prev_spend)) }}
            {{ Math.abs(delta(store.paidOverview.total_spend, store.paidOverview.prev_spend).pct).toFixed(1) }}% vs prev
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Impression Share</p>
          <p class="text-2xl font-bold text-white">{{ fmtPct(store.paidOverview.avg_impression_share) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.paidOverview.avg_impression_share, store.paidOverview.prev_impression_share))">
            {{ deltaArrow(delta(store.paidOverview.avg_impression_share, store.paidOverview.prev_impression_share)) }}
            {{ Math.abs(delta(store.paidOverview.avg_impression_share, store.paidOverview.prev_impression_share).pct).toFixed(1) }}%
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Avg CPC</p>
          <p class="text-2xl font-bold text-white">{{ fmtMoney(store.paidOverview.avg_cpc) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.paidOverview.avg_cpc, store.paidOverview.prev_cpc), true)">
            {{ deltaArrow(delta(store.paidOverview.avg_cpc, store.paidOverview.prev_cpc)) }}
            {{ Math.abs(delta(store.paidOverview.avg_cpc, store.paidOverview.prev_cpc).pct).toFixed(1) }}%
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Total Clicks</p>
          <p class="text-2xl font-bold text-white">{{ fmtNum(store.paidOverview.total_clicks) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.paidOverview.total_clicks, store.paidOverview.prev_clicks))">
            {{ deltaArrow(delta(store.paidOverview.total_clicks, store.paidOverview.prev_clicks)) }}
            {{ Math.abs(delta(store.paidOverview.total_clicks, store.paidOverview.prev_clicks).pct).toFixed(1) }}%
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Conversions</p>
          <p class="text-2xl font-bold text-white">{{ Math.round(store.paidOverview.total_conversions).toLocaleString() }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.paidOverview.total_conversions, store.paidOverview.prev_conversions))">
            {{ deltaArrow(delta(store.paidOverview.total_conversions, store.paidOverview.prev_conversions)) }}
            {{ Math.abs(delta(store.paidOverview.total_conversions, store.paidOverview.prev_conversions).pct).toFixed(1) }}%
          </p>
        </div>
      </div>

      <!-- Filter bar -->
      <div class="flex items-center gap-2 mb-4 flex-wrap">
        <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-400 hover:text-white transition-colors">
          Monthly volume
        </button>
        <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-400 hover:text-white transition-colors">
          United States
        </button>
        <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-400 hover:text-white transition-colors">
          Volume
        </button>
        <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-400 hover:text-white transition-colors">
          KD
        </button>
        <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-400 hover:text-white transition-colors">
          CPC
        </button>
        <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-400 hover:text-white transition-colors flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/></svg>
          Add filter
        </button>
      </div>

      <!-- Summary line -->
      <div class="flex items-center gap-3 mb-3">
        <span class="text-sm text-white font-medium">{{ store.paidSearchTerms?.length ?? 0 }} keywords</span>
        <span class="text-xs text-gray-500">&middot;</span>
        <span class="text-xs text-gray-500">{{ dateRangeLabel }}</span>
        <span class="text-xs text-gray-500">&middot;</span>
        <span class="text-xs text-gray-500">Don't compare</span>
      </div>

      <!-- Search Terms Table (Ahrefs style) -->
      <div class="bg-surface-card rounded-xl border border-surface-border">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-500 border-b border-surface-border">
                <th class="text-left px-4 py-3 w-10">#</th>
                <th class="text-left px-4 py-3">Keyword</th>
                <th class="text-center px-3 py-3 w-10">Ad</th>
                <th class="text-right px-4 py-3 w-20">Volume</th>
                <th class="text-left px-4 py-3 w-36">KD</th>
                <th class="text-right px-4 py-3 w-20">CPC</th>
                <th class="text-right px-4 py-3 w-20">Traffic</th>
                <th class="text-right px-4 py-3 w-20">Position</th>
                <th class="text-left px-4 py-3">URL</th>
                <th class="text-right px-4 py-3 w-24">Organic traffic</th>
                <th class="text-right px-4 py-3 w-24">Organic position</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(t, i) in store.paidSearchTerms" :key="t.search_term" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                <td class="px-4 py-3 text-gray-500 text-xs">{{ i + 1 }}</td>
                <td class="px-4 py-3 text-white font-medium">{{ t.search_term }}</td>
                <td class="px-3 py-3 text-center">
                  <span v-if="t.match_type" class="inline-block w-2.5 h-2.5 rounded-full" :class="matchDotClass(t.match_type)" :title="t.match_type"></span>
                </td>
                <td class="px-4 py-3 text-right text-gray-400">{{ t.volume != null ? fmtNum(t.volume) : '—' }}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <div class="w-16 h-2 rounded-full bg-surface-border overflow-hidden">
                      <div class="h-full rounded-full" :class="cpcBarColor(t.cpc)" :style="{ width: cpcBarWidth(t.cpc) + '%' }"></div>
                    </div>
                    <span class="text-xs text-gray-400">{{ fmtMoney(t.cpc) }}</span>
                  </div>
                </td>
                <td class="px-4 py-3 text-right" :class="cpcColor(t.cpc)">{{ fmtMoney(t.cpc) }}</td>
                <td class="px-4 py-3 text-right text-white font-bold">{{ fmtNum(t.clicks) }}</td>
                <td class="px-4 py-3 text-right" :class="positionColor(t.organic_position)">
                  {{ t.organic_position != null ? t.organic_position.toFixed(1) : '—' }}
                </td>
                <td class="px-4 py-3">
                  <span v-if="t.top_url" class="text-fo-action text-xs truncate max-w-[200px] inline-block" :title="t.top_url">{{ truncateUrl(t.top_url) }}</span>
                  <span v-else class="text-gray-500 text-xs">—</span>
                </td>
                <td class="px-4 py-3 text-right text-gray-400">{{ t.organic_traffic != null ? fmtNum(t.organic_traffic) : '—' }}</td>
                <td class="px-4 py-3 text-right" :class="positionColor(t.organic_position)">
                  {{ t.organic_position != null ? t.organic_position.toFixed(1) : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ===== TAB 2: Ads ===== -->
    <template v-else-if="activeTab === 'ads' && store.paidOverview">
      <!-- Summary + Trends header -->
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <span class="text-sm text-white font-medium">{{ store.paidAds?.length ?? 0 }} ads</span>
          <span class="text-xs text-gray-500">&middot;</span>
          <span class="text-xs text-gray-500">{{ dateRangeLabel }}</span>
        </div>
        <div class="flex items-center gap-3">
          <span class="text-xs text-gray-500">Trends: Last 1 years</span>
          <div class="flex gap-0.5 bg-surface-card rounded-lg p-0.5 border border-surface-border">
            <button class="px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors" :class="adsTrafficTab === 'traffic' ? 'bg-fo-action text-white' : 'text-gray-400 hover:text-white'" @click="adsTrafficTab = 'traffic'">Traffic</button>
            <button class="px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors" :class="adsTrafficTab === 'paid' ? 'bg-fo-action text-white' : 'text-gray-400 hover:text-white'" @click="adsTrafficTab = 'paid'">Paid traffic</button>
          </div>
        </div>
      </div>

      <!-- Ad cards -->
      <div class="bg-surface-card rounded-xl border border-surface-border">
        <div class="divide-y divide-surface-border">
          <div
            v-for="(ad, i) in store.paidAds" :key="ad.ad_id"
            class="hover:bg-surface-hover transition-colors cursor-pointer"
            @click="toggleAd(i)"
          >
            <div class="px-5 py-4 flex items-start gap-4">
              <!-- Left: Ad creative -->
              <div class="flex-1 min-w-0">
                <p class="text-sm font-bold text-white mb-1">{{ ad.headline }}</p>
                <p v-if="ad.description" class="text-xs text-gray-400 mb-2 line-clamp-2">{{ ad.description }}</p>
                <div class="flex items-center gap-1.5">
                  <span class="inline-flex px-1.5 py-0.5 rounded text-[9px] font-bold bg-status-up/20 text-status-up tracking-wide">Ad</span>
                  <span class="text-xs text-status-up">firstorion.com{{ ad.destination_url ? '/' + ad.destination_url.replace(/^https?:\/\/(www\.)?firstorion\.com\/?/, '').slice(0, 30) : '' }}</span>
                </div>
              </div>
              <!-- Right: Sparklines -->
              <div class="shrink-0 flex flex-col gap-2 items-end w-36">
                <div class="w-full">
                  <p class="text-[9px] text-gray-500 uppercase tracking-wider mb-0.5 text-right">True traffic</p>
                  <svg width="120" height="28" class="ml-auto" viewBox="0 0 120 28">
                    <polyline
                      :points="generateSparkline(i, 0)"
                      fill="none"
                      stroke="#3B6BF5"
                      stroke-width="1.5"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                  </svg>
                </div>
                <div class="w-full">
                  <p class="text-[9px] text-gray-500 uppercase tracking-wider mb-0.5 text-right">Traffic</p>
                  <svg width="120" height="28" class="ml-auto" viewBox="0 0 120 28">
                    <polyline
                      :points="generateSparkline(i, 1)"
                      fill="none"
                      stroke="#F5A623"
                      stroke-width="1.5"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                  </svg>
                </div>
              </div>
            </div>
            <!-- Expanded details -->
            <div v-if="expandedAd === i" class="px-5 pb-4">
              <div class="bg-surface rounded-lg p-4 border border-surface-border">
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                  <div>
                    <p class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Advertiser</p>
                    <p class="text-gray-300">{{ ad.advertiser_name }}</p>
                  </div>
                  <div>
                    <p class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Format</p>
                    <span class="inline-flex px-2 py-0.5 rounded text-[10px] font-semibold"
                      :class="{ 'bg-fo-action/15 text-fo-action': ad.ad_format === 'TEXT', 'bg-amber/15 text-amber': ad.ad_format === 'IMAGE', 'bg-status-down/15 text-status-down': ad.ad_format === 'VIDEO' }">
                      {{ ad.ad_format }}
                    </span>
                  </div>
                  <div>
                    <p class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Platforms</p>
                    <div class="flex gap-1 flex-wrap mt-0.5">
                      <span v-for="p in ad.platforms" :key="p" class="inline-flex px-2 py-0.5 rounded bg-surface-hover text-gray-300 text-[10px]">{{ p }}</span>
                    </div>
                  </div>
                  <div>
                    <p class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Running</p>
                    <p class="text-gray-300">{{ ad.days_running }} days</p>
                    <p class="text-[10px] text-gray-500 mt-0.5">
                      {{ ad.first_shown_date ? new Date(ad.first_shown_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '' }}
                      <template v-if="ad.last_shown_date"> &mdash; {{ new Date(ad.last_shown_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}</template>
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ===== TAB 3: Paid Pages ===== -->
    <template v-else-if="activeTab === 'pages' && store.paidOverview">
      <!-- Chart -->
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <h2 class="text-sm font-semibold text-white mb-4">Paid Traffic & Impressions</h2>
        <div class="h-64">
          <Line v-if="pagesChart" :data="pagesChart.data" :options="pagesChart.options" />
        </div>
      </div>

      <!-- Summary -->
      <div class="flex items-center gap-3 mb-3">
        <span class="text-sm text-white font-medium">{{ store.paidPages?.length ?? 0 }} pages</span>
        <span class="text-xs text-gray-500">&middot;</span>
        <span class="text-xs text-gray-500">Total traffic: {{ fmtNum(pagesTotalTraffic) }}</span>
        <span class="text-xs text-gray-500">&middot;</span>
        <span class="text-xs text-gray-500">{{ dateRangeLabel }}</span>
      </div>

      <!-- Pages Table -->
      <div class="bg-surface-card rounded-xl border border-surface-border">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-500 border-b border-surface-border">
                <th class="text-left px-5 py-3">URL</th>
                <th class="text-right px-5 py-3">Ads</th>
                <th class="text-right px-5 py-3">Traffic</th>
                <th class="text-right px-5 py-3">Impressions</th>
                <th class="text-right px-5 py-3">CTR</th>
                <th class="text-right px-5 py-3">Avg Position</th>
                <th class="text-right px-5 py-3">Keywords</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pg in store.paidPages" :key="pg.url" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                <td class="px-5 py-3">
                  <span class="text-fo-action text-xs truncate max-w-[280px] inline-block" :title="pg.url">{{ truncateUrl(pg.url) }}</span>
                </td>
                <td class="px-5 py-3 text-right text-gray-300">{{ pg.ads_keywords ?? '—' }}</td>
                <td class="px-5 py-3 text-right text-white font-medium">{{ fmtNum(pg.organic_traffic) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtNum(pg.impressions) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ pg.ctr != null ? (pg.ctr * 100).toFixed(1) + '%' : '—' }}</td>
                <td class="px-5 py-3 text-right" :class="positionColor(pg.avg_position)">
                  {{ pg.avg_position != null ? pg.avg_position.toFixed(1) : '—' }}
                </td>
                <td class="px-5 py-3 text-right text-gray-300">{{ pg.total_keywords ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ===== TAB 4: Campaigns ===== -->
    <template v-else-if="activeTab === 'campaigns' && store.paidOverview">
      <!-- Spend + Clicks Trend -->
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <h2 class="text-sm font-semibold text-white mb-4">Spend & Clicks Trend</h2>
        <div class="h-64">
          <Line v-if="spendChart" :data="spendChart.data" :options="spendChart.options" />
        </div>
      </div>

      <!-- IS Loss + Detail -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div class="bg-surface-card rounded-xl border border-surface-border p-5">
          <h2 class="text-sm font-semibold text-white mb-1">Impression Share Analysis</h2>
          <p class="text-xs text-gray-500 mb-4">Won vs lost to budget vs lost to rank</p>
          <div class="h-56">
            <Bar v-if="isLossChart" :data="isLossChart.data" :options="isLossChart.options" />
          </div>
        </div>
        <div class="bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-white">IS Loss Detail</h2>
          </div>
          <div class="p-5 space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-surface rounded-lg p-4 text-center">
                <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Avg Lost to Budget</p>
                <p class="text-xl font-bold text-amber">{{ (Number(store.paidOverview.avg_lost_budget) * 100).toFixed(1) }}%</p>
              </div>
              <div class="bg-surface rounded-lg p-4 text-center">
                <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Avg Lost to Rank</p>
                <p class="text-xl font-bold text-status-down">{{ (Number(store.paidOverview.avg_lost_rank) * 100).toFixed(1) }}%</p>
              </div>
            </div>
            <div v-if="Number(store.paidOverview.avg_lost_rank) > Number(store.paidOverview.avg_lost_budget)" class="border-l-4 border-status-down bg-status-down/5 rounded-r-lg p-3">
              <p class="text-xs text-gray-300">Losing more IS to <strong class="text-white">Ad Rank</strong> than budget. Consider improving Quality Score, ad relevance, and expected CTR to recover lost impressions.</p>
            </div>
            <div v-else class="border-l-4 border-amber bg-amber/5 rounded-r-lg p-3">
              <p class="text-xs text-gray-300">Losing more IS to <strong class="text-white">Budget</strong> than rank. Consider increasing daily budgets on high-converting campaigns to capture additional impression share.</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Campaign Table -->
      <div class="bg-surface-card rounded-xl border border-surface-border">
        <div class="px-5 py-4 border-b border-surface-border">
          <h2 class="text-sm font-semibold text-white">Campaign Performance</h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-500 border-b border-surface-border">
                <th class="text-left px-5 py-3">Campaign</th>
                <th class="text-right px-5 py-3">Spend</th>
                <th class="text-right px-5 py-3">Clicks</th>
                <th class="text-right px-5 py-3">CPC</th>
                <th class="text-right px-5 py-3">Conv</th>
                <th class="text-right px-5 py-3">IS%</th>
                <th class="text-right px-5 py-3">Lost Budget%</th>
                <th class="text-right px-5 py-3">Lost Rank%</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in store.paidCampaigns" :key="c.campaign_name" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                <td class="px-5 py-3 text-white font-medium">{{ c.campaign_name }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtMoney(c.spend) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtNum(c.clicks) }}</td>
                <td class="px-5 py-3 text-right" :class="cpcColor(c.cpc)">{{ fmtMoney(c.cpc) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ c.conversions?.toFixed(1) }}</td>
                <td class="px-5 py-3 text-right text-white font-medium">{{ fmtPct(c.avg_is) }}</td>
                <td class="px-5 py-3 text-right text-amber">{{ fmtPct(c.avg_lost_budget) }}</td>
                <td class="px-5 py-3 text-right text-status-down">{{ fmtPct(c.avg_lost_rank) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
