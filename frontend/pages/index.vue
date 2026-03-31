<script setup lang="ts">
const store = useDashboardStore()

const periodOptions = [
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 90 days', days: 90 },
  { label: 'Last 365 days', days: 365 },
]
const selectedPeriod = ref(periodOptions[1])
const periodOpen = ref(false)

const fmtDollar = (n: number) => n != null ? `$${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '--'

async function loadOverview() {
  store.setPeriod(selectedPeriod.value.days)
  await store.fetchOverview()
}

async function selectPeriod(opt: typeof periodOptions[0]) {
  selectedPeriod.value = opt
  periodOpen.value = false
  await loadOverview()
}

onMounted(() => loadOverview())

const fmtNum = (n: number) => n?.toLocaleString() ?? '--'
const fmtPos = (n: number) => n != null ? String(Math.round(n)) : '--'
const fmtPct = (n: number) => n != null ? `${(n * 100).toFixed(1)}%` : '--'

function delta(current: number, previous: number) {
  if (!previous || !current) return { value: 0, pct: 0 }
  const diff = current - previous
  const pct = previous ? (diff / previous) * 100 : 0
  return { value: diff, pct }
}

function deltaClass(d: { pct: number }, invert = false) {
  const positive = invert ? d.pct < 0 : d.pct > 0
  return positive ? 'text-status-up' : d.pct === 0 ? 'text-gray-400' : 'text-status-down'
}

function deltaArrow(d: { pct: number }) {
  return d.pct > 0 ? '\u2191' : d.pct < 0 ? '\u2193' : '\u2192'
}

// Build sparkline SVG points from timeline data
function sparklinePoints(data: any[], key: string, width = 80, height = 28): string {
  if (!data?.length) return ''
  const values = data.map((d: any) => d[key] ?? 0)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  return values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width
      const y = height - ((v - min) / range) * height
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

// Metric cards configuration
const metricCards = computed(() => {
  const org = store.organicOverview
  const paid = store.paidOverview
  const ai = store.aiOverview
  const comp = store.compOverview

  return [
    {
      label: 'Organic Clicks',
      value: org ? fmtNum(org.total_clicks) : '--',
      delta: org ? delta(org.total_clicks, org.prev_clicks) : null,
      invert: false,
      sparkData: store.organicTimeline,
      sparkKey: 'clicks',
      color: '#16A34A',
    },
    {
      label: 'Avg Position',
      value: org ? fmtPos(org.avg_position) : '--',
      delta: org ? delta(org.avg_position, org.prev_position) : null,
      invert: true,
      sparkData: store.organicTimeline,
      sparkKey: 'avg_position',
      color: '#3B6BF5',
    },
    {
      label: 'Paid Clicks',
      value: paid ? fmtNum(paid.total_clicks) : '--',
      delta: paid ? delta(paid.total_clicks, paid.prev_clicks) : null,
      invert: false,
      sparkData: store.paidTimeline,
      sparkKey: 'clicks',
      color: '#3B6BF5',
    },
    {
      label: 'Ad Spend',
      value: paid ? fmtDollar(paid.total_spend) : '--',
      delta: paid ? delta(paid.total_spend, paid.prev_spend) : null,
      invert: true,
      sparkData: store.paidTimeline,
      sparkKey: 'spend',
      color: '#D97706',
    },
    {
      label: 'AI Visibility',
      value: ai ? fmtPct(ai.avg_visibility) : '--',
      delta: ai ? delta(ai.avg_visibility, ai.prev_visibility) : null,
      invert: false,
      sparkData: store.aiTimeline,
      sparkKey: 'avg_visibility',
      color: '#8B5CF6',
    },
    {
      label: 'Competitor Ads',
      value: comp ? fmtNum(comp.active_ads) : '--',
      delta: null,
      invert: false,
      sparkData: [],
      sparkKey: '',
      color: '#DC2626',
    },
  ]
})

// Quick access cards
const quickAccessCards = computed(() => {
  const org = store.organicOverview
  const paid = store.paidOverview
  const ai = store.aiOverview
  const comp = store.compOverview

  return [
    {
      title: 'Organic Performance',
      icon: 'M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z',
      stat: org ? `${fmtNum(org.total_clicks)} clicks` : '--',
      sub: org ? `${fmtNum(org.total_impressions)} impressions` : '',
      link: '/organic',
      color: 'bg-fo-action/10 text-fo-action',
      borderColor: 'hover:border-fo-action/30',
    },
    {
      title: 'Paid Performance',
      icon: 'M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
      stat: paid ? `$${fmtNum(paid.total_spend)}` : '--',
      sub: paid ? `${fmtNum(paid.total_clicks)} clicks` : '',
      link: '/paid',
      color: 'bg-status-up/10 text-status-up',
      borderColor: 'hover:border-status-up/30',
    },
    {
      title: 'AI Visibility',
      icon: 'M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z',
      stat: ai ? `${fmtPct(ai.avg_visibility)} avg` : '--',
      sub: ai ? `${ai.total_citations ?? 0} citations` : '',
      link: '/ai',
      color: 'bg-purple-500/10 text-purple-400',
      borderColor: 'hover:border-purple-500/30',
    },
    {
      title: 'Competitor Ads',
      icon: 'M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605',
      stat: comp ? `${fmtNum(comp.active_ads)} active` : '--',
      sub: comp ? `${comp.domains_tracked ?? 5} competitors` : '',
      link: '/competitors',
      color: 'bg-status-down/10 text-status-down',
      borderColor: 'hover:border-status-down/30',
    },
  ]
})
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-gray-900">Overview</h1>
        <p class="text-sm text-gray-400 mt-0.5">firstorion.com performance summary</p>
      </div>
      <!-- Period dropdown -->
      <div class="relative">
        <button
          class="flex items-center gap-2 px-4 py-2 bg-surface-card rounded-lg border border-surface-border text-sm text-gray-700 hover:text-gray-900 transition-colors"
          @click="periodOpen = !periodOpen"
        >
          {{ selectedPeriod.label }}
          <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        <div
          v-if="periodOpen"
          class="absolute right-0 top-full mt-1 w-48 bg-surface-card border border-surface-border rounded-lg shadow-xl z-50 py-1"
        >
          <button
            v-for="opt in periodOptions"
            :key="opt.days"
            class="w-full text-left px-4 py-2 text-sm transition-colors"
            :class="selectedPeriod.days === opt.days ? 'text-fo-action bg-fo-action/10' : 'text-gray-700 hover:bg-surface-hover hover:text-gray-900'"
            @click="selectPeriod(opt)"
          >{{ opt.label }}</button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading" class="space-y-6">
      <div class="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <div v-for="i in 6" :key="i" class="h-32 bg-surface-card rounded-xl border border-surface-border animate-pulse" />
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="h-40 bg-surface-card rounded-xl border border-surface-border animate-pulse" />
      </div>
    </div>

    <template v-else>
      <!-- Metric Cards Row -->
      <div class="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
        <div
          v-for="(card, idx) in metricCards"
          :key="idx"
          class="bg-surface-card rounded-xl p-4 border border-surface-border overflow-hidden"
        >
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">{{ card.label }}</p>
          <p class="text-xl font-bold text-gray-900 truncate">{{ card.value }}</p>
          <p
            v-if="card.delta"
            class="text-xs mt-0.5"
            :class="deltaClass(card.delta, card.invert)"
          >
            {{ deltaArrow(card.delta) }}
            {{ Math.abs(card.delta.pct).toFixed(1) }}%
          </p>
          <p v-else class="text-xs mt-0.5 text-gray-400">current period</p>
          <!-- Sparkline below value -->
          <svg
            v-if="card.sparkData?.length > 1"
            class="w-full h-6 mt-2"
            viewBox="0 0 80 24"
            preserveAspectRatio="none"
          >
            <polyline
              :points="sparklinePoints(card.sparkData, card.sparkKey, 80, 24)"
              fill="none"
              :stroke="card.color"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </div>
      </div>

      <!-- Quick Access Grid -->
      <div class="mb-4">
        <h3 class="text-sm font-semibold text-gray-900 mb-4">Dashboards</h3>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <NuxtLink
          v-for="(card, idx) in quickAccessCards"
          :key="idx"
          :to="card.link"
          class="group bg-surface-card rounded-xl border border-surface-border p-5 transition-all duration-200"
          :class="card.borderColor"
        >
          <div class="flex items-start justify-between mb-4">
            <div :class="card.color" class="w-10 h-10 rounded-lg flex items-center justify-center">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" :d="card.icon" />
              </svg>
            </div>
            <svg
              class="w-4 h-4 text-gray-400 group-hover:text-gray-500 transition-colors"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
          <h4 class="text-sm font-semibold text-gray-900 mb-1">{{ card.title }}</h4>
          <p class="text-lg font-bold text-gray-900 mb-0.5">{{ card.stat }}</p>
          <p class="text-xs text-gray-400">{{ card.sub }}</p>
          <p class="text-xs text-fo-action mt-3 group-hover:underline">View Dashboard &rarr;</p>
        </NuxtLink>
      </div>
    </template>
  </div>
</template>
