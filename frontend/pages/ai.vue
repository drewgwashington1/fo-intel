<script setup lang="ts">
import { Line, Bar } from 'vue-chartjs'

const store = useDashboardStore()
const { get } = useApi()

const periods = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
]

const citationTimeline = ref<any[]>([])

async function loadAll() {
  await store.fetchAI()
  citationTimeline.value = await get('/dashboard/ai/citation-timeline', { days: store.periodDays })
}

async function setPeriod(days: number) {
  store.setPeriod(days)
  await loadAll()
}

onMounted(() => loadAll())

const fmtNum = (n: number) => n?.toLocaleString() ?? '—'
const fmtPct = (n: number) => n != null ? `${(Number(n) * 100).toFixed(1)}%` : '—'

function delta(current: number, previous: number) {
  if (!previous || !current) return { pct: 0 }
  return { pct: ((current - previous) / previous) * 100 }
}

function deltaClass(d: { pct: number }) {
  return d.pct > 0 ? 'text-status-up' : d.pct < 0 ? 'text-status-down' : 'text-gray-500'
}

function deltaArrow(d: { pct: number }) {
  return d.pct > 0 ? '\u2191' : d.pct < 0 ? '\u2193' : '\u2192'
}

const platformColors: Record<string, string> = {
  ChatGPT: '#10A37F',
  Perplexity: '#5B9FE4',
  Gemini: '#FBBC04',
  Claude: '#D97706',
  'Google AI': '#EA4335',
}

const visibilityChart = computed(() => {
  const data = store.aiTimeline
  if (!data?.length) return null

  const platforms = [...new Set(data.map((d: any) => d.platform))]
  const dates = [...new Set(data.map((d: any) => d.data_date))].sort()
  const labels = dates.map(d => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }))

  return {
    data: {
      labels,
      datasets: platforms.map(platform => ({
        label: platform,
        data: dates.map(date => {
          const row = data.find((d: any) => d.data_date === date && d.platform === platform)
          return row?.visibility ?? null
        }),
        borderColor: platformColors[platform] || '#8B95A5',
        backgroundColor: 'transparent',
        borderWidth: 2,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index' as const, intersect: false },
      scales: {
        y: { min: 0, max: 100, grid: { display: false } },
      },
    },
  }
})

const citationChart = computed(() => {
  const data = citationTimeline.value
  if (!data?.length) return null
  return {
    data: {
      labels: data.map((d: any) => new Date(d.data_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
      datasets: [
        { label: 'Direct', data: data.map((d: any) => d.direct), backgroundColor: '#3B6BF5', stack: 'ct' },
        { label: 'Indirect', data: data.map((d: any) => d.indirect), backgroundColor: '#5B9FE4', stack: 'ct' },
        { label: 'Mention', data: data.map((d: any) => d.mention), backgroundColor: '#8B95A5', stack: 'ct' },
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

const sovBarChart = computed(() => {
  const comp = store.aiSovComparison
  if (!comp?.fo?.length) return null

  const categories = [...new Set(comp.fo.map((r: any) => r.category_name))]
  const foData = categories.map((cat: string) => {
    const row = comp.fo.find((r: any) => r.category_name === cat)
    return row ? Number(row.fo_sov) * 100 : 0
  })

  const competitors = [...new Set(comp.competitors.map((r: any) => r.competitor_domain))]
  const compDatasets = competitors.map((domain: string) => ({
    label: domain,
    data: categories.map((cat: string) => {
      const row = comp.competitors.find((r: any) => r.category_name === cat && r.competitor_domain === domain)
      return row ? Number(row.comp_sov) * 100 : 0
    }),
    backgroundColor: {
      'hiya.com': '#F44444',
      'numeracle.com': '#F5A623',
      'transunion.com': '#5B9FE4',
      'freecallerregistry.com': '#8B95A5',
      'tnsi.com': '#D97706',
    }[domain] || '#8B95A5',
  }))

  return {
    data: {
      labels: categories,
      datasets: [
        { label: 'First Orion', data: foData, backgroundColor: '#3B6BF5' },
        ...compDatasets,
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y' as const,
      scales: {
        x: { grid: { display: false }, max: 50 },
      },
      plugins: {
        legend: { position: 'bottom' as const },
      },
    },
  }
})
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-white">AI Visibility</h1>
        <p class="text-sm text-gray-500 mt-0.5">Profound API &middot; AI engine share of voice, citations & benchmarks</p>
      </div>
      <div class="flex gap-0.5 bg-surface-card rounded-lg p-1 border border-surface-border">
        <button v-for="p in periods" :key="p.days" class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors" :class="store.periodDays === p.days ? 'bg-fo-action text-white' : 'text-gray-400 hover:text-white'" @click="setPeriod(p.days)">{{ p.label }}</button>
      </div>
    </div>

    <div v-if="store.loading" class="space-y-6">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4"><div v-for="i in 4" :key="i" class="h-28 bg-surface-card rounded-xl animate-pulse" /></div>
    </div>

    <template v-else-if="store.aiOverview">
      <!-- KPIs -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">AI Visibility Score</p>
          <p class="text-2xl font-bold text-white">{{ store.aiOverview.avg_visibility }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.aiOverview.avg_visibility, store.aiOverview.prev_visibility))">
            {{ deltaArrow(delta(store.aiOverview.avg_visibility, store.aiOverview.prev_visibility)) }}
            {{ Math.abs(delta(store.aiOverview.avg_visibility, store.aiOverview.prev_visibility).pct).toFixed(1) }}% vs prev
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Avg Share of Voice</p>
          <p class="text-2xl font-bold text-white">{{ fmtPct(store.aiOverview.avg_sov) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.aiOverview.avg_sov, store.aiOverview.prev_sov))">
            {{ deltaArrow(delta(store.aiOverview.avg_sov, store.aiOverview.prev_sov)) }}
            {{ Math.abs(delta(store.aiOverview.avg_sov, store.aiOverview.prev_sov).pct).toFixed(1) }}%
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Total Citations</p>
          <p class="text-2xl font-bold text-white">{{ fmtNum(store.aiOverview.total_citation_records) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.aiOverview.total_citations, store.aiOverview.prev_citations))">
            {{ deltaArrow(delta(store.aiOverview.total_citations, store.aiOverview.prev_citations)) }}
            {{ Math.abs(delta(store.aiOverview.total_citations, store.aiOverview.prev_citations).pct).toFixed(1) }}%
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Platforms Tracked</p>
          <p class="text-2xl font-bold text-white">{{ store.aiPlatforms?.length ?? 0 }}</p>
          <p class="text-xs mt-1 text-gray-500">AI engines monitored</p>
        </div>
      </div>

      <!-- Visibility Trend Chart -->
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <h2 class="text-sm font-semibold text-white mb-4">Visibility Score by Platform</h2>
        <div class="h-64">
          <Line v-if="visibilityChart" :data="visibilityChart.data" :options="visibilityChart.options" />
        </div>
      </div>

      <!-- SOV Comparison + Citation Trend -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- SOV Bar Chart -->
        <div class="bg-surface-card rounded-xl border border-surface-border p-5">
          <h2 class="text-sm font-semibold text-white mb-1">Share of Voice by Category</h2>
          <p class="text-xs text-gray-500 mb-4">First Orion vs competitors across AI engines</p>
          <div class="h-72">
            <Bar v-if="sovBarChart" :data="sovBarChart.data" :options="sovBarChart.options" />
          </div>
        </div>

        <!-- Citation Trend -->
        <div class="bg-surface-card rounded-xl border border-surface-border p-5">
          <h2 class="text-sm font-semibold text-white mb-1">Citation Trend</h2>
          <p class="text-xs text-gray-500 mb-4">Direct, indirect, and mention citations over time</p>
          <div class="h-72">
            <Bar v-if="citationChart" :data="citationChart.data" :options="citationChart.options" />
          </div>
        </div>
      </div>

      <!-- Platform Breakdown + Competitor SOV -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Platform cards -->
        <div class="bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-white">Platform Breakdown</h2>
          </div>
          <div class="p-5 space-y-4">
            <div v-for="p in store.aiPlatforms" :key="p.platform" class="flex items-center gap-4">
              <div class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ backgroundColor: platformColors[p.platform] || '#8B95A5' }" />
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-sm font-medium text-white">{{ p.platform }}</span>
                  <span class="text-sm text-gray-300">{{ p.avg_visibility }}/100</span>
                </div>
                <div class="w-full h-1.5 bg-surface rounded-full overflow-hidden">
                  <div class="h-full rounded-full transition-all" :style="{ width: `${p.avg_visibility}%`, backgroundColor: platformColors[p.platform] || '#8B95A5' }" />
                </div>
                <div class="flex items-center gap-3 mt-1 text-xs text-gray-500">
                  <span>SOV: {{ fmtPct(p.avg_sov) }}</span>
                  <span>{{ p.citations }} citations</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Competitor SOV Table -->
        <div class="bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-white">Competitor Share of Voice</h2>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-[10px] uppercase tracking-wider text-gray-500 border-b border-surface-border">
                  <th class="text-left px-5 py-3">Competitor</th>
                  <th class="text-right px-5 py-3">SOV</th>
                  <th class="text-right px-5 py-3">Citations</th>
                  <th class="text-right px-5 py-3">vs FO</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in store.aiCompetitors" :key="c.competitor_domain" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                  <td class="px-5 py-3 text-white font-medium">{{ c.competitor_domain }}</td>
                  <td class="px-5 py-3 text-right text-gray-300">{{ fmtPct(c.avg_sov) }}</td>
                  <td class="px-5 py-3 text-right text-gray-300">{{ fmtNum(c.citations) }}</td>
                  <td class="px-5 py-3 text-right text-xs" :class="Number(c.avg_sov) > Number(store.aiOverview.avg_sov) ? 'text-status-down' : 'text-status-up'">
                    {{ Number(c.avg_sov) > Number(store.aiOverview.avg_sov) ? 'Ahead' : 'Behind' }}
                    {{ Math.abs((Number(c.avg_sov) - Number(store.aiOverview.avg_sov)) * 100).toFixed(1) }}pts
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Top Cited Pages -->
      <div class="bg-surface-card rounded-xl border border-surface-border">
        <div class="px-5 py-4 border-b border-surface-border">
          <h2 class="text-sm font-semibold text-white">Top Cited Pages</h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-500 border-b border-surface-border">
                <th class="text-left px-5 py-3">Cited URL</th>
                <th class="text-right px-5 py-3">Citations</th>
                <th class="text-right px-5 py-3">Sentiment</th>
                <th class="text-right px-5 py-3">Positive %</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in store.aiTopCited" :key="c.cited_url" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                <td class="px-5 py-3 text-fo-action font-medium truncate max-w-[400px]">{{ c.cited_url }}</td>
                <td class="px-5 py-3 text-right text-white font-medium">{{ c.citation_count }}</td>
                <td class="px-5 py-3 text-right">
                  <div class="inline-flex gap-1.5">
                    <span class="text-status-up text-xs">{{ c.positive }}+</span>
                    <span class="text-gray-500 text-xs">{{ c.neutral }}~</span>
                    <span class="text-status-down text-xs">{{ c.negative }}-</span>
                  </div>
                </td>
                <td class="px-5 py-3 text-right">
                  <span class="text-xs font-medium" :class="Number(c.positive_pct) >= 50 ? 'text-status-up' : 'text-status-down'">
                    {{ c.positive_pct }}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
