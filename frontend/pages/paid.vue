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

const isLoss = ref<any[]>([])

async function loadAll() {
  await store.fetchPaid()
  isLoss.value = await get('/dashboard/paid/is-loss', { days: store.periodDays })
}

async function setPeriod(days: number) {
  store.setPeriod(days)
  await loadAll()
}

onMounted(() => loadAll())

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
          yAxisID: 'y',
        },
        {
          label: 'Clicks',
          data: data.map((d: any) => d.clicks),
          borderColor: '#1BB981',
          backgroundColor: 'transparent',
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index' as const, intersect: false },
      scales: {
        y: { position: 'left' as const, grid: { display: false } },
        y1: { position: 'right' as const, grid: { drawOnChartArea: false } },
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
      scales: {
        x: { stacked: true, max: 100, grid: { display: false } },
        y: { stacked: true },
      },
    },
  }
})

function downloadCsv() {
  window.open(`${useRuntimeConfig().public.apiBase}/dashboard/paid/export?days=${store.periodDays}`, '_blank')
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-white">Paid Performance</h1>
        <p class="text-sm text-gray-500 mt-0.5">Google Ads &middot; campaign & search term metrics</p>
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

    <div v-if="store.loading" class="space-y-6">
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-4"><div v-for="i in 5" :key="i" class="h-28 bg-surface-card rounded-xl animate-pulse" /></div>
      <div class="h-72 bg-surface-card rounded-xl animate-pulse" />
    </div>

    <template v-else-if="store.paidOverview">
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

      <!-- Spend + Clicks Trend -->
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <h2 class="text-sm font-semibold text-white mb-4">Spend & Clicks Trend</h2>
        <div class="h-64">
          <Line v-if="spendChart" :data="spendChart.data" :options="spendChart.options" />
        </div>
      </div>

      <!-- IS Loss + Campaign Breakdown -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- IS Loss Chart -->
        <div class="bg-surface-card rounded-xl border border-surface-border p-5">
          <h2 class="text-sm font-semibold text-white mb-1">Impression Share Analysis</h2>
          <p class="text-xs text-gray-500 mb-4">Won vs lost to budget vs lost to rank, by campaign</p>
          <div class="h-56">
            <Bar v-if="isLossChart" :data="isLossChart.data" :options="isLossChart.options" />
          </div>
        </div>

        <!-- IS Loss numbers -->
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
            <!-- Insight callout -->
            <div v-if="Number(store.paidOverview.avg_lost_rank) > Number(store.paidOverview.avg_lost_budget)" class="border-l-4 border-status-down bg-status-down/5 rounded-r-lg p-3">
              <p class="text-xs text-gray-300">Losing more IS to <strong class="text-white">Ad Rank</strong> than budget. Consider improving Quality Score through better ad relevance and landing page experience.</p>
            </div>
            <div v-else class="border-l-4 border-amber bg-amber/5 rounded-r-lg p-3">
              <p class="text-xs text-gray-300">Losing more IS to <strong class="text-white">Budget</strong> than rank. Consider increasing daily budgets on top-performing campaigns.</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Campaign Table -->
      <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
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
                <th class="text-right px-5 py-3">IS</th>
                <th class="text-right px-5 py-3">Lost Budget</th>
                <th class="text-right px-5 py-3">Lost Rank</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in store.paidCampaigns" :key="c.campaign_name" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                <td class="px-5 py-3 text-white font-medium">{{ c.campaign_name }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtMoney(c.spend) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtNum(c.clicks) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtMoney(c.cpc) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ c.conversions?.toFixed(1) }}</td>
                <td class="px-5 py-3 text-right text-white font-medium">{{ fmtPct(c.avg_is) }}</td>
                <td class="px-5 py-3 text-right text-amber">{{ fmtPct(c.avg_lost_budget) }}</td>
                <td class="px-5 py-3 text-right text-status-down">{{ fmtPct(c.avg_lost_rank) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Search Terms -->
      <div class="bg-surface-card rounded-xl border border-surface-border">
        <div class="px-5 py-4 border-b border-surface-border flex items-center justify-between">
          <h2 class="text-sm font-semibold text-white">Top Search Terms</h2>
          <span class="text-xs text-gray-500">actual queries triggering ads</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-500 border-b border-surface-border">
                <th class="text-left px-5 py-3">#</th>
                <th class="text-left px-5 py-3">Search Term</th>
                <th class="text-left px-5 py-3">Match</th>
                <th class="text-right px-5 py-3">Clicks</th>
                <th class="text-right px-5 py-3">CPC</th>
                <th class="text-right px-5 py-3">Cost</th>
                <th class="text-right px-5 py-3">Conv</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(t, i) in store.paidSearchTerms" :key="t.search_term" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                <td class="px-5 py-3 text-gray-500 text-xs">{{ i + 1 }}</td>
                <td class="px-5 py-3 text-white font-medium">{{ t.search_term }}</td>
                <td class="px-5 py-3">
                  <span class="inline-flex px-2 py-0.5 rounded text-[10px] font-semibold uppercase"
                    :class="{ 'bg-fo-action/15 text-fo-action': t.match_type === 'EXACT', 'bg-amber/15 text-amber': t.match_type === 'PHRASE', 'bg-gray-500/15 text-gray-400': t.match_type === 'BROAD' }">
                    {{ t.match_type }}
                  </span>
                </td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtNum(t.clicks) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtMoney(t.cpc) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtMoney(t.cost) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ t.conversions?.toFixed(1) ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
