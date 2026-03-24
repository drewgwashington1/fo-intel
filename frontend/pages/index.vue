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

const positionDist = ref<any[]>([])
const movements = ref<any>(null)
const countries = ref<any[]>([])
const activeMovementTab = ref('improved')

async function loadAll() {
  await store.fetchOrganic()
  const days = store.periodDays
  const [pd, mv, co] = await Promise.all([
    get('/dashboard/organic/position-distribution', { days }),
    get('/dashboard/organic/movements', { days }),
    get('/dashboard/organic/countries', { days }),
  ])
  positionDist.value = pd
  movements.value = mv
  countries.value = co
}

async function setPeriod(days: number) {
  store.setPeriod(days)
  await loadAll()
}

onMounted(() => loadAll())

const fmtNum = (n: number) => n?.toLocaleString() ?? '—'
const fmtPct = (n: number) => n != null ? `${(n * 100).toFixed(1)}%` : '—'
const fmtPos = (n: number) => n != null ? n.toFixed(1) : '—'

function delta(current: number, previous: number) {
  if (!previous || !current) return { value: 0, pct: 0 }
  const diff = current - previous
  const pct = previous ? (diff / previous) * 100 : 0
  return { value: diff, pct }
}

function deltaClass(d: { pct: number }, invert = false) {
  const positive = invert ? d.pct < 0 : d.pct > 0
  return positive ? 'text-status-up' : d.pct === 0 ? 'text-gray-500' : 'text-status-down'
}

function deltaArrow(d: { pct: number }) {
  return d.pct > 0 ? '\u2191' : d.pct < 0 ? '\u2193' : '\u2192'
}

const timelineChart = computed(() => {
  const data = store.organicTimeline
  if (!data?.length) return null
  return {
    data: {
      labels: data.map((d: any) => new Date(d.data_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
      datasets: [
        {
          label: 'Clicks',
          data: data.map((d: any) => d.clicks),
          borderColor: '#3B6BF5',
          backgroundColor: 'rgba(59,107,245,0.08)',
          fill: true,
          yAxisID: 'y',
        },
        {
          label: 'Impressions',
          data: data.map((d: any) => d.impressions),
          borderColor: '#8B95A5',
          backgroundColor: 'transparent',
          borderDash: [4, 4],
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

const posDistChart = computed(() => {
  const data = positionDist.value
  if (!data?.length) return null
  const labels = data.map((d: any) => new Date(d.data_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }))
  return {
    data: {
      labels,
      datasets: [
        { label: '#1-3', data: data.map((d: any) => d.pos_1_3), backgroundColor: '#1BB981', stack: 'pos' },
        { label: '#4-10', data: data.map((d: any) => d.pos_4_10), backgroundColor: '#3B6BF5', stack: 'pos' },
        { label: '#11-20', data: data.map((d: any) => d.pos_11_20), backgroundColor: '#F5A623', stack: 'pos' },
        { label: '#21-50', data: data.map((d: any) => d.pos_21_50), backgroundColor: '#8B95A5', stack: 'pos' },
        { label: '#51+', data: data.map((d: any) => d.pos_51_plus), backgroundColor: '#F44444', stack: 'pos' },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { stacked: true },
        y: { stacked: true, grid: { display: false } },
      },
    },
  }
})

function downloadCsv() {
  window.open(`${useRuntimeConfig().public.apiBase}/dashboard/organic/export?days=${store.periodDays}`, '_blank')
}

const movementTabs = [
  { key: 'improved', label: 'Improved', color: 'text-status-up' },
  { key: 'declined', label: 'Declined', color: 'text-status-down' },
  { key: 'new', label: 'New', color: 'text-fo-action' },
  { key: 'lost', label: 'Lost', color: 'text-gray-400' },
]
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-white">Organic Performance</h1>
        <p class="text-sm text-gray-500 mt-0.5">Google Search Console &middot; firstorion.com</p>
      </div>
      <div class="flex items-center gap-3">
        <button
          class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-400 hover:text-white transition-colors"
          @click="downloadCsv"
        >
          Export CSV
        </button>
        <div class="flex gap-0.5 bg-surface-card rounded-lg p-1 border border-surface-border">
          <button
            v-for="p in periods" :key="p.days"
            class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            :class="store.periodDays === p.days ? 'bg-fo-action text-white' : 'text-gray-400 hover:text-white'"
            @click="setPeriod(p.days)"
          >{{ p.label }}</button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading" class="space-y-6">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="h-28 bg-surface-card rounded-xl animate-pulse" />
      </div>
      <div class="h-72 bg-surface-card rounded-xl animate-pulse" />
    </div>

    <template v-else-if="store.organicOverview">
      <!-- KPI Cards with Deltas -->
      <div class="grid grid-cols-2 lg:grid-cols-6 gap-4 mb-6">
        <!-- Clicks -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Total Clicks</p>
          <p class="text-2xl font-bold text-white">{{ fmtNum(store.organicOverview.total_clicks) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.total_clicks, store.organicOverview.prev_clicks))">
            {{ deltaArrow(delta(store.organicOverview.total_clicks, store.organicOverview.prev_clicks)) }}
            {{ delta(store.organicOverview.total_clicks, store.organicOverview.prev_clicks).pct.toFixed(1) }}% vs prev
          </p>
        </div>
        <!-- Impressions -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Total Impressions</p>
          <p class="text-2xl font-bold text-white">{{ fmtNum(store.organicOverview.total_impressions) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.total_impressions, store.organicOverview.prev_impressions))">
            {{ deltaArrow(delta(store.organicOverview.total_impressions, store.organicOverview.prev_impressions)) }}
            {{ delta(store.organicOverview.total_impressions, store.organicOverview.prev_impressions).pct.toFixed(1) }}% vs prev
          </p>
        </div>
        <!-- CTR -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Avg CTR</p>
          <p class="text-2xl font-bold text-white">{{ fmtPct(store.organicOverview.avg_ctr) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.avg_ctr, store.organicOverview.prev_ctr))">
            {{ deltaArrow(delta(store.organicOverview.avg_ctr, store.organicOverview.prev_ctr)) }}
            {{ delta(store.organicOverview.avg_ctr, store.organicOverview.prev_ctr).pct.toFixed(1) }}%
          </p>
        </div>
        <!-- Position (inverted — lower is better) -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Avg Position</p>
          <p class="text-2xl font-bold text-white">{{ fmtPos(store.organicOverview.avg_position) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.avg_position, store.organicOverview.prev_position), true)">
            {{ deltaArrow(delta(store.organicOverview.avg_position, store.organicOverview.prev_position)) }}
            {{ Math.abs(delta(store.organicOverview.avg_position, store.organicOverview.prev_position).pct).toFixed(1) }}%
          </p>
        </div>
        <!-- Unique Queries -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Keywords</p>
          <p class="text-2xl font-bold text-white">{{ fmtNum(store.organicOverview.unique_queries) }}</p>
          <p class="text-xs mt-1 text-gray-500">ranking queries</p>
        </div>
        <!-- Unique Pages -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Pages</p>
          <p class="text-2xl font-bold text-white">{{ fmtNum(store.organicOverview.unique_pages) }}</p>
          <p class="text-xs mt-1 text-gray-500">ranking pages</p>
        </div>
      </div>

      <!-- Traffic Timeline Chart -->
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <h2 class="text-sm font-semibold text-white mb-4">Clicks & Impressions Trend</h2>
        <div class="h-64">
          <Line v-if="timelineChart" :data="timelineChart.data" :options="timelineChart.options" />
        </div>
      </div>

      <!-- Position Distribution + Keyword Movements -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Position Distribution -->
        <div class="bg-surface-card rounded-xl border border-surface-border p-5">
          <h2 class="text-sm font-semibold text-white mb-4">Position Distribution</h2>
          <div class="h-56">
            <Bar v-if="posDistChart" :data="posDistChart.data" :options="posDistChart.options" />
          </div>
        </div>

        <!-- Keyword Movements -->
        <div class="bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-white">Keyword Movements</h2>
            <p class="text-xs text-gray-500 mt-0.5">vs previous {{ store.periodDays }}-day period</p>
          </div>
          <!-- Summary badges -->
          <div v-if="movements" class="flex gap-3 px-5 pt-4">
            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-status-up/15 text-status-up">
              {{ movements.summary.improved }} improved
            </span>
            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-status-down/15 text-status-down">
              {{ movements.summary.declined }} declined
            </span>
            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-fo-action/15 text-fo-action">
              {{ movements.summary.new }} new
            </span>
            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-500/15 text-gray-400">
              {{ movements.summary.lost }} lost
            </span>
          </div>
          <!-- Tab nav -->
          <div class="flex gap-1 px-5 pt-3">
            <button
              v-for="tab in movementTabs" :key="tab.key"
              class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
              :class="activeMovementTab === tab.key ? `bg-surface-hover ${tab.color}` : 'text-gray-500 hover:text-gray-300'"
              @click="activeMovementTab = tab.key"
            >{{ tab.label }}</button>
          </div>
          <!-- Movement list -->
          <div v-if="movements" class="p-5 space-y-2 max-h-48 overflow-y-auto">
            <div
              v-for="kw in movements.details[activeMovementTab]?.slice(0, 10)"
              :key="kw.query"
              class="flex items-center justify-between py-1.5 border-b border-surface-border last:border-0"
            >
              <span class="text-sm text-white truncate max-w-[200px]">{{ kw.query }}</span>
              <div class="flex items-center gap-3 text-xs">
                <span v-if="kw.current_position" class="text-gray-400">pos {{ fmtPos(kw.current_position) }}</span>
                <span
                  v-if="kw.position_change && kw.position_change !== 0"
                  :class="kw.position_change > 0 ? 'text-status-up' : 'text-status-down'"
                >
                  {{ kw.position_change > 0 ? '\u2191' : '\u2193' }}{{ Math.abs(kw.position_change).toFixed(1) }}
                </span>
                <span class="text-gray-500">{{ kw.clicks }} clicks</span>
              </div>
            </div>
            <p v-if="!movements.details[activeMovementTab]?.length" class="text-sm text-gray-500">No keywords in this category</p>
          </div>
        </div>
      </div>

      <!-- Top Queries Table -->
      <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
        <div class="px-5 py-4 border-b border-surface-border flex items-center justify-between">
          <h2 class="text-sm font-semibold text-white">Top Queries</h2>
          <span class="text-xs text-gray-500">by clicks &middot; top {{ store.organicTopQueries.length }}</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-500 border-b border-surface-border">
                <th class="text-left px-5 py-3 w-8">#</th>
                <th class="text-left px-5 py-3">Query</th>
                <th class="text-right px-5 py-3">Clicks</th>
                <th class="text-right px-5 py-3">Change</th>
                <th class="text-right px-5 py-3">Impressions</th>
                <th class="text-right px-5 py-3">CTR</th>
                <th class="text-right px-5 py-3">Position</th>
                <th class="text-right px-5 py-3">Pos Change</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(q, i) in store.organicTopQueries"
                :key="q.query"
                class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
              >
                <td class="px-5 py-3 text-gray-500 text-xs">{{ i + 1 }}</td>
                <td class="px-5 py-3 text-white font-medium">{{ q.query }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtNum(q.clicks) }}</td>
                <td class="px-5 py-3 text-right text-xs" :class="q.prev_clicks != null && q.clicks > q.prev_clicks ? 'text-status-up' : q.clicks < (q.prev_clicks || 0) ? 'text-status-down' : 'text-gray-500'">
                  <template v-if="q.prev_clicks != null">
                    {{ q.clicks > q.prev_clicks ? '\u2191' : q.clicks < q.prev_clicks ? '\u2193' : '\u2192' }}
                    {{ Math.abs(q.clicks - q.prev_clicks) }}
                  </template>
                  <template v-else>
                    <span class="text-fo-action">NEW</span>
                  </template>
                </td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtNum(q.impressions) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtPct(q.ctr) }}</td>
                <td class="px-5 py-3 text-right text-gray-300">{{ fmtPos(q.avg_position) }}</td>
                <td class="px-5 py-3 text-right text-xs" :class="q.prev_position != null && q.avg_position < q.prev_position ? 'text-status-up' : q.avg_position > (q.prev_position || 999) ? 'text-status-down' : 'text-gray-500'">
                  <template v-if="q.prev_position != null">
                    {{ q.avg_position < q.prev_position ? '\u2191' : q.avg_position > q.prev_position ? '\u2193' : '\u2192' }}
                    {{ Math.abs(q.avg_position - q.prev_position).toFixed(1) }}
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Bottom: Top Pages + Devices + Countries -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Top Pages -->
        <div class="lg:col-span-2 bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-white">Top Pages</h2>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-[10px] uppercase tracking-wider text-gray-500 border-b border-surface-border">
                  <th class="text-left px-5 py-3">Page</th>
                  <th class="text-right px-5 py-3">Clicks</th>
                  <th class="text-right px-5 py-3">Keywords</th>
                  <th class="text-right px-5 py-3">CTR</th>
                  <th class="text-right px-5 py-3">Position</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="p in store.organicTopPages"
                  :key="p.page"
                  class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                >
                  <td class="px-5 py-3 text-fo-action font-medium truncate max-w-[350px]">{{ p.page }}</td>
                  <td class="px-5 py-3 text-right text-white font-medium">{{ fmtNum(p.clicks) }}</td>
                  <td class="px-5 py-3 text-right text-gray-300">{{ p.keywords }}</td>
                  <td class="px-5 py-3 text-right text-gray-300">{{ fmtPct(p.ctr) }}</td>
                  <td class="px-5 py-3 text-right text-gray-300">{{ fmtPos(p.avg_position) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Device + Country sidebar -->
        <div class="space-y-6">
          <!-- Devices -->
          <div class="bg-surface-card rounded-xl border border-surface-border p-5">
            <h2 class="text-sm font-semibold text-white mb-4">Clicks by Device</h2>
            <div class="space-y-3">
              <div v-for="d in store.organicDevices" :key="d.device">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-sm text-gray-300">{{ d.device }}</span>
                  <div class="flex items-center gap-2">
                    <span class="text-xs text-gray-500">{{ fmtPct(d.ctr) }} CTR</span>
                    <span class="text-sm font-medium text-white">{{ fmtNum(d.clicks) }}</span>
                  </div>
                </div>
                <div class="w-full h-2 bg-surface rounded-full overflow-hidden">
                  <div
                    class="h-full bg-fo-action rounded-full"
                    :style="{ width: `${(d.clicks / Math.max(...store.organicDevices.map((x: any) => x.clicks))) * 100}%` }"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Countries -->
          <div class="bg-surface-card rounded-xl border border-surface-border p-5">
            <h2 class="text-sm font-semibold text-white mb-4">Top Countries</h2>
            <div class="space-y-3">
              <div v-for="c in countries.slice(0, 5)" :key="c.country">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-sm text-gray-300">{{ c.country }}</span>
                  <span class="text-sm font-medium text-white">{{ fmtNum(c.clicks) }}</span>
                </div>
                <div class="w-full h-1.5 bg-surface rounded-full overflow-hidden">
                  <div
                    class="h-full bg-fo-action/60 rounded-full"
                    :style="{ width: countries.length ? `${(c.clicks / Math.max(...countries.map((x: any) => x.clicks))) * 100}%` : '0%' }"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
