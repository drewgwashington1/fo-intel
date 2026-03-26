<script setup lang="ts">
import { Line, Bar } from 'vue-chartjs'

const store = useDashboardStore()
const { get } = useApi()

const periods = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
]

const subTabs = [
  { key: 'visibility', label: 'Visibility' },
  { key: 'citations', label: 'Citations' },
  { key: 'competitors', label: 'Competitors' },
] as const

type SubTab = typeof subTabs[number]['key']
const activeTab = ref<SubTab>('visibility')

const tabTitles: Record<SubTab, string> = {
  visibility: 'AI Visibility',
  citations: 'Citations',
  competitors: 'Competitors',
}

const citationTimeline = ref<any[]>([])
const topics = ref<any[]>([])
const prompts = ref<any[]>([])
const citedUrls = ref<any[]>([])

async function loadAll() {
  await store.fetchAI()
  const days = store.periodDays
  const [ct, tp, pr, cu] = await Promise.all([
    get('/dashboard/ai/citation-timeline', { days }),
    get('/dashboard/ai/topics', { days }),
    get('/dashboard/ai/prompts', { days }),
    get('/dashboard/ai/cited-urls', { days }),
  ])
  citationTimeline.value = ct
  topics.value = tp
  prompts.value = pr
  citedUrls.value = cu
}

async function setPeriod(days: number) {
  store.setPeriod(days)
  await loadAll()
}

onMounted(() => loadAll())

/* ── Helpers ── */
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

function truncateUrl(url: string, max = 60) {
  if (!url) return '—'
  const clean = url.replace(/^https?:\/\/(www\.)?/, '')
  return clean.length > max ? clean.slice(0, max) + '...' : clean
}

/* ── Platform colors ── */
const platformColors: Record<string, string> = {
  'ChatGPT': '#10A37F',
  'Perplexity': '#5B9FE4',
  'Google Gemini': '#FBBC04',
  'Google AI Mode': '#EA4335',
  'Google AI Overviews': '#34A853',
  'Microsoft Copilot': '#00BCF2',
  'Meta AI': '#0668E1',
  'Grok': '#1DA1F2',
}

const competitorColors: Record<string, string> = {
  'hiya.com': '#F44444',
  'numeracle.com': '#F5A623',
  'transunion.com': '#5B9FE4',
  'vonage.com': '#10A37F',
  'twilio.com': '#D97706',
}

/* ── Sorted platforms by visibility ── */
const sortedPlatforms = computed(() => {
  if (!store.aiPlatforms?.length) return []
  return [...store.aiPlatforms].sort((a: any, b: any) => Number(b.avg_visibility) - Number(a.avg_visibility))
})

/* ── Visibility Trend Chart ── */
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
        borderColor: platformColors[platform as string] || '#8B95A5',
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.3,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index' as const, intersect: false },
      plugins: {
        legend: {
          position: 'bottom' as const,
          labels: { color: '#8B95A5', usePointStyle: true, pointStyle: 'circle', padding: 16, font: { size: 11 } },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#6B7280', font: { size: 10 }, maxTicksLimit: 12 } },
        y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6B7280', font: { size: 10 } } },
      },
    },
  }
})

/* ── Citation Trend Chart (stacked bar) ── */
const citationChart = computed(() => {
  const data = citationTimeline.value
  if (!data?.length) return null
  return {
    data: {
      labels: data.map((d: any) => new Date(d.data_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
      datasets: [
        { label: 'Direct', data: data.map((d: any) => d.direct), backgroundColor: '#3B6BF5', stack: 'ct', borderRadius: 2 },
        { label: 'Indirect', data: data.map((d: any) => d.indirect), backgroundColor: '#5B9FE4', stack: 'ct', borderRadius: 2 },
        { label: 'Mention', data: data.map((d: any) => d.mention), backgroundColor: '#8B95A5', stack: 'ct', borderRadius: 2 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom' as const,
          labels: { color: '#8B95A5', usePointStyle: true, pointStyle: 'circle', padding: 16, font: { size: 11 } },
        },
      },
      scales: {
        x: { stacked: true, grid: { display: false }, ticks: { color: '#6B7280', font: { size: 10 }, maxTicksLimit: 12 } },
        y: { stacked: true, grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6B7280', font: { size: 10 } } },
      },
    },
  }
})

/* ── Citation KPIs ── */
const citationTotalCount = computed(() => {
  const data = citationTimeline.value
  if (!data?.length) return 0
  return data.reduce((sum: number, d: any) => sum + (d.citations || 0), 0)
})

const citationTrend = computed(() => {
  const data = citationTimeline.value
  if (!data?.length || data.length < 2) return { direction: 'flat', pct: 0 }
  const half = Math.floor(data.length / 2)
  const firstHalf = data.slice(0, half).reduce((s: number, d: any) => s + (d.citations || 0), 0)
  const secondHalf = data.slice(half).reduce((s: number, d: any) => s + (d.citations || 0), 0)
  if (!firstHalf) return { direction: 'up', pct: 100 }
  const pct = ((secondHalf - firstHalf) / firstHalf) * 100
  return { direction: pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat', pct }
})

const topCitedUrl = computed(() => {
  if (!store.aiTopCited?.length) return '—'
  return truncateUrl(store.aiTopCited[0].cited_url, 40)
})

/* ── Competitor SOV comparison (horizontal bar) ── */
const competitorSovChart = computed(() => {
  const comps = store.aiCompetitors
  const overview = store.aiOverview
  if (!comps?.length || !overview) return null

  const foSov = Number(overview.avg_sov) * 100
  const labels = ['First Orion', ...comps.map((c: any) => c.competitor_domain)]
  const values = [foSov, ...comps.map((c: any) => Number(c.avg_sov) * 100)]
  const colors = ['#3B6BF5', ...comps.map((c: any) => competitorColors[c.competitor_domain] || '#8B95A5')]

  return {
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderRadius: 4,
        barThickness: 28,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y' as const,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx: any) => `SOV: ${ctx.raw.toFixed(1)}%`,
          },
        },
      },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6B7280', font: { size: 10 }, callback: (v: any) => `${v}%` } },
        y: { grid: { display: false }, ticks: { color: '#E5E7EB', font: { size: 11, weight: '500' } } },
      },
    },
  }
})

/* ── SOV by Category Chart ── */
const sovCategoryChart = computed(() => {
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
    backgroundColor: competitorColors[domain as string] || '#8B95A5',
    borderRadius: 3,
  }))

  return {
    data: {
      labels: categories,
      datasets: [
        { label: 'First Orion', data: foData, backgroundColor: '#3B6BF5', borderRadius: 3 },
        ...compDatasets,
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom' as const,
          labels: { color: '#8B95A5', usePointStyle: true, pointStyle: 'circle', padding: 16, font: { size: 11 } },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#6B7280', font: { size: 10 } } },
        y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6B7280', font: { size: 10 }, callback: (v: any) => `${v}%` }, max: 50 },
      },
    },
  }
})

/* ── Sorted competitors by SOV ── */
const sortedCompetitors = computed(() => {
  if (!store.aiCompetitors?.length) return []
  return [...store.aiCompetitors].sort((a: any, b: any) => Number(b.avg_sov) - Number(a.avg_sov))
})

/* ── Citation sources (citations by platform) ── */
const citationsByPlatform = computed(() => {
  if (!store.aiPlatforms?.length) return []
  return [...store.aiPlatforms]
    .filter((p: any) => p.citations > 0)
    .sort((a: any, b: any) => b.citations - a.citations)
})
</script>

<template>
  <div>
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-2">
        <h1 class="text-xl font-semibold text-white">{{ tabTitles[activeTab] }}</h1>
      </div>
      <div class="flex items-center gap-3">
        <!-- Filter buttons -->
        <div class="flex gap-2">
          <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-400 hover:text-white transition-colors">
            Platform
          </button>
          <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-400 hover:text-white transition-colors">
            All engines
          </button>
          <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-400 hover:text-white transition-colors">
            + Add filter
          </button>
        </div>
        <!-- Period selector -->
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
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4"><div v-for="i in 4" :key="i" class="h-28 bg-surface-card rounded-xl animate-pulse" /></div>
      <div class="h-72 bg-surface-card rounded-xl animate-pulse" />
    </div>

    <!-- ===================================================================== -->
    <!-- TAB 1: VISIBILITY                                                      -->
    <!-- ===================================================================== -->
    <template v-else-if="activeTab === 'visibility' && store.aiOverview">
      <!-- KPI Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">AI Visibility Score</p>
          <div class="flex items-baseline gap-1.5">
            <p class="text-2xl font-bold text-white">{{ Number(store.aiOverview.avg_visibility).toFixed(1) }}</p>
            <p class="text-sm text-gray-500">/100</p>
          </div>
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

      <!-- Platform Scorecards (2x4 grid) -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div
          v-for="(p, idx) in sortedPlatforms" :key="p.platform"
          class="bg-surface-card rounded-xl p-5 border border-surface-border hover:border-gray-600 transition-colors"
        >
          <!-- Rank badge + platform name -->
          <div class="flex items-center gap-2.5 mb-3">
            <div class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ backgroundColor: platformColors[p.platform] || '#8B95A5' }" />
            <span class="text-xs font-medium text-gray-400 uppercase tracking-wide">#{{ idx + 1 }}</span>
          </div>
          <p class="text-sm font-semibold text-white mb-3">{{ p.platform }}</p>

          <!-- Large visibility score -->
          <div class="flex items-baseline gap-1 mb-3">
            <span class="text-3xl font-bold text-white">{{ Number(p.avg_visibility).toFixed(1) }}</span>
            <span class="text-sm text-gray-500">/100</span>
          </div>

          <!-- Progress bar -->
          <div class="w-full h-2 bg-surface rounded-full overflow-hidden mb-3">
            <div
              class="h-full rounded-full transition-all duration-500"
              :style="{ width: `${p.avg_visibility}%`, backgroundColor: platformColors[p.platform] || '#8B95A5' }"
            />
          </div>

          <!-- SOV + Citations -->
          <div class="flex items-center justify-between text-xs text-gray-500">
            <span>SOV: <span class="text-gray-300 font-medium">{{ fmtPct(p.avg_sov) }}</span></span>
            <span>{{ fmtNum(p.citations) }} cites</span>
          </div>
        </div>
      </div>

      <!-- Visibility Trend Chart -->
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h2 class="text-sm font-semibold text-white">Visibility Score by Platform</h2>
            <p class="text-xs text-gray-500 mt-0.5">Tracking across all {{ store.aiPlatforms?.length ?? 0 }} AI engines over time</p>
          </div>
        </div>
        <div class="h-80">
          <Line v-if="visibilityChart" :data="visibilityChart.data" :options="visibilityChart.options" />
          <div v-else class="h-full flex items-center justify-center text-gray-500 text-sm">No timeline data available</div>
        </div>
      </div>

      <!-- Topics & Prompts -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Topics -->
        <div class="bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-white">Top Topics</h2>
            <p class="text-xs text-gray-500 mt-0.5">Categories where FO appears in AI responses</p>
          </div>
          <div class="divide-y divide-surface-border">
            <div v-for="(t, i) in topics" :key="t.topic" class="px-5 py-3 flex items-center justify-between hover:bg-surface-hover transition-colors">
              <div class="flex items-center gap-3 min-w-0">
                <span class="text-xs text-gray-500 w-5">{{ i + 1 }}</span>
                <span class="text-sm text-white truncate">{{ t.topic }}</span>
              </div>
              <div class="flex items-center gap-4 shrink-0">
                <div class="text-right">
                  <div class="w-16 h-1.5 bg-surface rounded-full overflow-hidden">
                    <div class="h-full rounded-full bg-fo-action" :style="{ width: `${t.visibility}%` }" />
                  </div>
                  <span class="text-[10px] text-gray-500">{{ t.visibility }}/100</span>
                </div>
                <span class="text-xs font-medium text-gray-300 w-12 text-right">{{ t.sov }}%</span>
              </div>
            </div>
            <div v-if="!topics.length" class="px-5 py-8 text-center text-gray-500 text-sm">No topic data available</div>
          </div>
        </div>

        <!-- Top Prompts / Queries -->
        <div class="bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-white">Top AI Queries</h2>
            <p class="text-xs text-gray-500 mt-0.5">Actual prompts where FO is mentioned in AI answers</p>
          </div>
          <div class="divide-y divide-surface-border max-h-[500px] overflow-y-auto">
            <div v-for="(p, i) in prompts" :key="p.prompt" class="px-5 py-3 hover:bg-surface-hover transition-colors">
              <div class="flex items-start gap-3">
                <span class="text-xs text-gray-500 mt-0.5 w-5 shrink-0">{{ i + 1 }}</span>
                <div class="min-w-0 flex-1">
                  <p class="text-sm text-white leading-snug">{{ p.prompt }}</p>
                  <div class="flex items-center gap-3 mt-1.5">
                    <span class="text-[10px] px-1.5 py-0.5 rounded font-medium" :class="p.visibility >= 70 ? 'bg-status-up/15 text-status-up' : p.visibility >= 40 ? 'bg-amber/15 text-amber' : 'bg-status-down/15 text-status-down'">
                      vis {{ p.visibility }}
                    </span>
                    <span class="text-[10px] text-gray-500">SOV {{ p.sov }}%</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="!prompts.length" class="px-5 py-8 text-center text-gray-500 text-sm">No prompt data available</div>
          </div>
        </div>
      </div>
    </template>

    <!-- ===================================================================== -->
    <!-- TAB 2: CITATIONS                                                       -->
    <!-- ===================================================================== -->
    <template v-else-if="activeTab === 'citations' && store.aiOverview">
      <!-- Citation KPI Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Total Citations</p>
          <p class="text-2xl font-bold text-white">{{ fmtNum(store.aiOverview.total_citation_records) }}</p>
          <p class="text-xs mt-1 text-gray-500">Across all AI engines</p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Top Cited URL</p>
          <p class="text-sm font-semibold text-fo-action mt-1 truncate" :title="store.aiTopCited?.[0]?.cited_url">{{ topCitedUrl }}</p>
          <p class="text-xs mt-1 text-gray-500">{{ store.aiTopCited?.[0]?.citation_count ?? 0 }} citations</p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Citation Trend</p>
          <div class="flex items-baseline gap-2">
            <p class="text-2xl font-bold" :class="citationTrend.direction === 'up' ? 'text-status-up' : citationTrend.direction === 'down' ? 'text-status-down' : 'text-gray-400'">
              {{ citationTrend.direction === 'up' ? '\u2191' : citationTrend.direction === 'down' ? '\u2193' : '\u2192' }}
            </p>
            <p class="text-sm font-medium" :class="citationTrend.direction === 'up' ? 'text-status-up' : citationTrend.direction === 'down' ? 'text-status-down' : 'text-gray-500'">
              {{ Math.abs(citationTrend.pct).toFixed(1) }}%
            </p>
          </div>
          <p class="text-xs mt-1 text-gray-500">vs first half of period</p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Cited Pages</p>
          <p class="text-2xl font-bold text-white">{{ store.aiTopCited?.length ?? 0 }}</p>
          <p class="text-xs mt-1 text-gray-500">Unique URLs cited</p>
        </div>
      </div>

      <!-- Citation Trend Chart -->
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <div class="mb-4">
          <h2 class="text-sm font-semibold text-white">Citation Trend</h2>
          <p class="text-xs text-gray-500 mt-0.5">Direct, indirect, and mention citations over time</p>
        </div>
        <div class="h-72">
          <Bar v-if="citationChart" :data="citationChart.data" :options="citationChart.options" />
          <div v-else class="h-full flex items-center justify-center text-gray-500 text-sm">No citation timeline data available</div>
        </div>
      </div>

      <!-- Cited URLs from Profound (all domains) -->
      <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
        <div class="px-5 py-4 border-b border-surface-border">
          <h2 class="text-sm font-semibold text-white">Most Cited URLs Across AI Engines</h2>
          <p class="text-xs text-gray-500 mt-0.5">Pages most frequently referenced in AI-generated answers</p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-500 border-b border-surface-border">
                <th class="text-left px-5 py-3 w-8">#</th>
                <th class="text-left px-5 py-3">Cited URL</th>
                <th class="text-right px-5 py-3">Citations</th>
                <th class="text-left px-5 py-3">Owner</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(c, idx) in citedUrls" :key="c.url" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                <td class="px-5 py-3 text-gray-500 text-xs">{{ idx + 1 }}</td>
                <td class="px-5 py-3 font-medium truncate max-w-[400px]" :class="c.url.includes('firstorion') ? 'text-fo-action' : 'text-gray-300'" :title="c.url">{{ c.url }}</td>
                <td class="px-5 py-3 text-right text-white font-bold">{{ fmtNum(c.citations) }}</td>
                <td class="px-5 py-3">
                  <span v-if="c.url.includes('firstorion')" class="inline-flex px-2 py-0.5 rounded text-[10px] font-semibold bg-fo-action/15 text-fo-action">FO</span>
                  <span v-else class="inline-flex px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-500/15 text-gray-400">COMP</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <!-- Top Cited FO Pages (2/3 width) -->
        <div class="lg:col-span-2 bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-white">First Orion Cited Pages</h2>
            <p class="text-xs text-gray-500 mt-0.5">FO pages referenced in AI engine responses</p>
          </div>
          <div class="divide-y divide-surface-border">
            <div v-for="(c, idx) in citedUrls.filter((u: any) => u.url.includes('firstorion'))" :key="c.url" class="px-5 py-3 flex items-center justify-between hover:bg-surface-hover transition-colors">
              <div class="flex items-center gap-3 min-w-0">
                <span class="text-xs text-gray-500 w-5">{{ idx + 1 }}</span>
                <span class="text-sm text-fo-action truncate" :title="c.url">{{ c.url }}</span>
              </div>
              <span class="text-sm font-bold text-white shrink-0 ml-4">{{ fmtNum(c.citations) }}</span>
            </div>
            <div v-if="!citedUrls.filter((u: any) => u.url.includes('firstorion')).length" class="px-5 py-8 text-center text-gray-500 text-sm">No FO citations found</div>
          </div>
        </div>

        <!-- Citation Sources Breakdown (1/3 width) -->
        <div class="bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-white">Citations by Engine</h2>
          </div>
          <div class="p-5 space-y-4">
            <div v-for="p in citationsByPlatform" :key="p.platform" class="flex items-center gap-3">
              <div class="w-2 h-2 rounded-full shrink-0" :style="{ backgroundColor: platformColors[p.platform] || '#8B95A5' }" />
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-xs font-medium text-white">{{ p.platform }}</span>
                  <span class="text-xs text-gray-300 font-medium">{{ fmtNum(p.citations) }}</span>
                </div>
                <div class="w-full h-1.5 bg-surface rounded-full overflow-hidden">
                  <div
                    class="h-full rounded-full transition-all"
                    :style="{
                      width: `${citationsByPlatform.length ? (p.citations / citationsByPlatform[0].citations * 100) : 0}%`,
                      backgroundColor: platformColors[p.platform] || '#8B95A5'
                    }"
                  />
                </div>
              </div>
            </div>
            <div v-if="!citationsByPlatform.length" class="text-center text-gray-500 text-sm py-6">
              No citation data by platform
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ===================================================================== -->
    <!-- TAB 3: COMPETITORS                                                     -->
    <!-- ===================================================================== -->
    <template v-else-if="activeTab === 'competitors' && store.aiOverview">
      <!-- Competitor KPI Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">FO Share of Voice</p>
          <p class="text-2xl font-bold text-fo-action">{{ fmtPct(store.aiOverview.avg_sov) }}</p>
          <p class="text-xs mt-1 text-gray-500">Across all AI engines</p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Competitors Tracked</p>
          <p class="text-2xl font-bold text-white">{{ store.aiCompetitors?.length ?? 0 }}</p>
          <p class="text-xs mt-1 text-gray-500">Active in AI engines</p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Top Competitor</p>
          <p class="text-sm font-semibold text-white mt-1">{{ sortedCompetitors[0]?.competitor_domain ?? '—' }}</p>
          <p class="text-xs mt-1 text-gray-500">SOV: {{ sortedCompetitors[0] ? fmtPct(sortedCompetitors[0].avg_sov) : '—' }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-500 mb-1">SOV Gap (Top Comp)</p>
          <div v-if="sortedCompetitors[0]">
            <p class="text-2xl font-bold" :class="Number(sortedCompetitors[0].avg_sov) > Number(store.aiOverview.avg_sov) ? 'text-status-down' : 'text-status-up'">
              {{ Math.abs((Number(sortedCompetitors[0].avg_sov) - Number(store.aiOverview.avg_sov)) * 100).toFixed(1) }}pts
            </p>
            <p class="text-xs mt-1" :class="Number(sortedCompetitors[0].avg_sov) > Number(store.aiOverview.avg_sov) ? 'text-status-down' : 'text-status-up'">
              {{ Number(sortedCompetitors[0].avg_sov) > Number(store.aiOverview.avg_sov) ? 'FO is behind' : 'FO is ahead' }}
            </p>
          </div>
          <p v-else class="text-2xl font-bold text-gray-500">—</p>
        </div>
      </div>

      <!-- FO vs Competitors SOV Chart -->
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <div class="mb-4">
          <h2 class="text-sm font-semibold text-white">FO vs Competitors — Share of Voice</h2>
          <p class="text-xs text-gray-500 mt-0.5">Average SOV across all AI engine categories</p>
        </div>
        <div class="h-72">
          <Bar v-if="competitorSovChart" :data="competitorSovChart.data" :options="competitorSovChart.options" />
          <div v-else class="h-full flex items-center justify-center text-gray-500 text-sm">No competitor data available</div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Competitor Ranking Table -->
        <div class="bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-white">Competitor Rankings</h2>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-[10px] uppercase tracking-wider text-gray-500 border-b border-surface-border">
                  <th class="text-left px-5 py-3 w-8">#</th>
                  <th class="text-left px-5 py-3">Competitor</th>
                  <th class="text-left px-5 py-3">SOV</th>
                  <th class="text-right px-5 py-3">Citations</th>
                  <th class="text-right px-5 py-3">vs FO</th>
                  <th class="text-right px-5 py-3">Trend</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(c, idx) in sortedCompetitors" :key="c.competitor_domain" class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                  <td class="px-5 py-3 text-gray-500 text-xs font-medium">{{ idx + 1 }}</td>
                  <td class="px-5 py-3">
                    <div class="flex items-center gap-2">
                      <div class="w-2 h-2 rounded-full shrink-0" :style="{ backgroundColor: competitorColors[c.competitor_domain] || '#8B95A5' }" />
                      <span class="text-white font-bold text-sm">{{ c.competitor_domain }}</span>
                    </div>
                  </td>
                  <td class="px-5 py-3">
                    <div class="flex items-center gap-2">
                      <div class="w-16 h-1.5 bg-surface rounded-full overflow-hidden">
                        <div
                          class="h-full rounded-full"
                          :style="{
                            width: `${Math.min(Number(c.avg_sov) * 100 * 3, 100)}%`,
                            backgroundColor: competitorColors[c.competitor_domain] || '#8B95A5'
                          }"
                        />
                      </div>
                      <span class="text-gray-300 text-xs font-medium">{{ fmtPct(c.avg_sov) }}</span>
                    </div>
                  </td>
                  <td class="px-5 py-3 text-right text-gray-300">{{ fmtNum(c.citations) }}</td>
                  <td class="px-5 py-3 text-right">
                    <span
                      class="text-xs font-medium"
                      :class="Number(c.avg_sov) > Number(store.aiOverview.avg_sov) ? 'text-status-down' : 'text-status-up'"
                    >
                      {{ Number(c.avg_sov) > Number(store.aiOverview.avg_sov) ? 'Ahead' : 'Behind' }}
                      {{ Math.abs((Number(c.avg_sov) - Number(store.aiOverview.avg_sov)) * 100).toFixed(1) }}pts
                    </span>
                  </td>
                  <td class="px-5 py-3 text-right text-gray-500 text-xs">—</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- SOV by Category Chart -->
        <div class="bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-white">SOV by Category</h2>
            <p class="text-xs text-gray-500 mt-0.5">First Orion vs competitors across categories</p>
          </div>
          <div class="p-5">
            <div class="h-80">
              <Bar v-if="sovCategoryChart" :data="sovCategoryChart.data" :options="sovCategoryChart.options" />
              <div v-else class="h-full flex items-center justify-center text-gray-500 text-sm">No category data available</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
