<script setup lang="ts">
const store = useDashboardStore()

const periodOptions = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
]

const categories = [
  { key: 'all', label: 'All' },
  { key: 'organic', label: 'Organic' },
  { key: 'paid', label: 'Paid' },
  { key: 'ai_visibility', label: 'AI Visibility' },
  { key: 'competitor', label: 'Competitor' },
  { key: 'cross_channel', label: 'Cross-Channel' },
]

const priorities = ['all', 'high', 'medium', 'low'] as const

const activeCategory = ref('all')
const activePriority = ref<string>('all')
const selectedPeriod = ref(periodOptions[1])

async function loadInsights() {
  store.setPeriod(selectedPeriod.value.days)
  await store.fetchInsights()
}

async function setPeriod(opt: typeof periodOptions[0]) {
  selectedPeriod.value = opt
  await loadInsights()
}

onMounted(() => loadInsights())

const summary = computed(() => store.insights?.summary)

const filteredInsights = computed(() => {
  if (!store.insights?.insights) return []
  return store.insights.insights.filter((i: any) => {
    if (activeCategory.value !== 'all' && i.category !== activeCategory.value) return false
    if (activePriority.value !== 'all' && i.priority !== activePriority.value) return false
    return true
  })
})

function categoryCount(key: string): number {
  if (!summary.value) return 0
  if (key === 'all') return summary.value.total
  return summary.value.by_category?.[key] ?? 0
}

function priorityCount(key: string): number {
  if (!summary.value) return 0
  if (key === 'all') return summary.value.total
  return summary.value[key] ?? 0
}

function categoryColor(cat: string): string {
  const map: Record<string, string> = {
    organic: 'bg-status-up/15 text-status-up',
    paid: 'bg-fo-action/15 text-fo-action',
    ai_visibility: 'bg-purple-500/15 text-purple-600',
    competitor: 'bg-status-down/15 text-status-down',
    cross_channel: 'bg-amber/15 text-amber',
  }
  return map[cat] || 'bg-gray-500/15 text-gray-400'
}

function categoryLabel(cat: string): string {
  const map: Record<string, string> = {
    organic: 'Organic',
    paid: 'Paid',
    ai_visibility: 'AI Visibility',
    competitor: 'Competitor',
    cross_channel: 'Cross-Channel',
  }
  return map[cat] || cat
}

function priorityColor(p: string): string {
  const map: Record<string, string> = {
    high: 'bg-status-down/15 text-status-down',
    medium: 'bg-amber/15 text-amber',
    low: 'bg-gray-500/15 text-gray-400',
  }
  return map[p] || 'bg-gray-500/15 text-gray-400'
}

function priorityBorder(p: string): string {
  const map: Record<string, string> = {
    high: 'border-l-status-down',
    medium: 'border-l-amber',
    low: 'border-l-gray-300',
  }
  return map[p] || 'border-l-gray-300'
}

function typeIcon(type: string): string {
  const map: Record<string, string> = {
    page2_keywords: 'M3 4.5h14.25M3 9h9.75M3 13.5h9.75m4.5-4.5v12m0 0l-3.75-3.75M17.25 21L21 17.25',
    low_ctr_winners: 'M15.042 21.672L13.684 16.6m0 0l-2.51 2.225.569-9.47 5.227 7.917-3.286-.672zM12 2.25V4.5m5.834.166l-1.591 1.591M20.25 10.5H18M7.757 14.743l-1.59 1.59M6 10.5H3.75m4.007-4.243l-1.59-1.59',
    declining_keywords: 'M2.25 6L9 12.75l4.286-4.286a11.948 11.948 0 014.306 6.43l.776 2.898M2.25 6h6m-6 0v6',
    new_keyword_opportunities: 'M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z',
    organic_paid_overlap: 'M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5',
    impression_share_recovery: 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z',
    high_cpc_keywords: 'M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    competitor_paid_gaps: 'M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3',
    platform_gaps: 'M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z',
    competitor_overtaking: 'M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941',
    uncited_content: 'M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z',
    negative_sentiment: 'M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z',
    new_competitor_campaigns: 'M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 01-2.25 2.25M16.5 7.5V18a2.25 2.25 0 002.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 002.25 2.25h13.5',
    long_running_ads: 'M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z',
    competitor_keyword_overlap: 'M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z',
    ai_without_organic: 'M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z',
    organic_without_ai: 'M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244',
  }
  return map[type] || 'M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z'
}

// Format metric values for display — plain English labels, no jargon
function metricEntries(insight: any): Array<{ label: string; value: string }> {
  const m = insight.metric
  if (!m) return []
  const entries: Array<{ label: string; value: string }> = []

  // Position metrics
  if (m.position != null) entries.push({ label: 'Position', value: `#${m.position}` })
  if (m['current position'] != null) entries.push({ label: 'Now', value: `#${m['current position']}` })
  if (m['previous position'] != null) entries.push({ label: 'Was', value: `#${m['previous position']}` })
  if (m['positions lost'] != null) entries.push({ label: 'Dropped', value: `${m['positions lost']} spots` })
  if (m['organic position'] != null && m['organic position'] > 0) entries.push({ label: 'Organic Rank', value: `#${m['organic position']}` })

  // Volume metrics
  if (m['times shown'] != null) entries.push({ label: 'Shown', value: m['times shown'].toLocaleString() })
  if (m.clicks != null) entries.push({ label: 'Clicks', value: m.clicks.toLocaleString() })
  if (m['organic clicks'] != null) entries.push({ label: 'Organic Clicks', value: m['organic clicks'].toLocaleString() })
  if (m['paid clicks'] != null) entries.push({ label: 'Paid Clicks', value: m['paid clicks'].toLocaleString() })

  // Rate metrics
  if (m['click rate'] != null) entries.push({ label: 'Click Rate', value: `${(m['click rate'] * 100).toFixed(1)}%` })
  if (m['average click rate'] != null) entries.push({ label: 'Average', value: `${(m['average click rate'] * 100).toFixed(1)}%` })

  // Paid metrics (no dollar amounts)
  if (m.conversions != null) entries.push({ label: 'Conversions', value: String(Math.round(m.conversions)) })
  if (m['impression share'] != null) entries.push({ label: 'Ad Visibility', value: `${(m['impression share'] * 100).toFixed(0)}%` })
  if (m['lost to budget'] != null) entries.push({ label: 'Lost (Budget)', value: `${(m['lost to budget'] * 100).toFixed(0)}%` })
  if (m['lost to rank'] != null) entries.push({ label: 'Lost (Rank)', value: `${(m['lost to rank'] * 100).toFixed(0)}%` })

  // AI metrics
  if (m.visibility != null) entries.push({ label: 'Visibility', value: `${m.visibility}%` })
  if (m.benchmark != null) entries.push({ label: 'Average', value: `${m.benchmark.toFixed(1)}%` })
  if (m.citations != null) entries.push({ label: 'AI Citations', value: String(m.citations) })

  // Competitor metrics
  if (m['competitor count'] != null) entries.push({ label: 'Competitors', value: String(m['competitor count']) })
  if (m['new ads'] != null) entries.push({ label: 'New Ads', value: String(m['new ads']) })
  if (m['days running'] != null) entries.push({ label: 'Days Running', value: String(m['days running']) })
  if (m['advertiser count'] != null) entries.push({ label: 'Advertisers', value: String(m['advertiser count']) })

  // Fallback: render any key we haven't handled
  return entries.slice(0, 4)
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-gray-900">Insights & Opportunities</h1>
        <p class="text-sm text-gray-400 mt-1">Cross-channel analysis surfacing actionable opportunities</p>
      </div>
      <!-- Period selector -->
      <div class="flex items-center gap-1 bg-surface-card rounded-lg p-1 border border-surface-border">
        <button
          v-for="opt in periodOptions"
          :key="opt.days"
          class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
          :class="selectedPeriod.days === opt.days ? 'bg-fo-action text-white' : 'text-gray-500 hover:text-gray-900'"
          @click="setPeriod(opt)"
        >{{ opt.label }}</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.insightsLoading" class="space-y-4">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="h-24 bg-surface-card rounded-xl border border-surface-border animate-pulse" />
      </div>
      <div v-for="i in 5" :key="i" class="h-32 bg-surface-card rounded-xl border border-surface-border animate-pulse" />
    </div>

    <template v-else-if="summary">
      <!-- Summary Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Total Insights</p>
          <p class="text-2xl font-bold text-gray-900">{{ summary.total }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">High Priority</p>
          <div class="flex items-baseline gap-2">
            <p class="text-2xl font-bold text-status-down">{{ summary.high }}</p>
            <p class="text-xs text-gray-400">need attention</p>
          </div>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Medium Priority</p>
          <div class="flex items-baseline gap-2">
            <p class="text-2xl font-bold text-amber">{{ summary.medium }}</p>
            <p class="text-xs text-gray-400">worth reviewing</p>
          </div>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Low Priority</p>
          <div class="flex items-baseline gap-2">
            <p class="text-2xl font-bold text-gray-400">{{ summary.low }}</p>
            <p class="text-xs text-gray-400">monitor</p>
          </div>
        </div>
      </div>

      <!-- Category Tabs -->
      <div class="flex items-center gap-4 mb-4">
        <div class="flex gap-1 bg-surface-card rounded-lg p-1 border border-surface-border overflow-x-auto">
          <button
            v-for="cat in categories"
            :key="cat.key"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap"
            :class="activeCategory === cat.key ? 'bg-fo-action text-white' : 'text-gray-500 hover:text-gray-900'"
            @click="activeCategory = cat.key"
          >
            {{ cat.label }}
            <span
              class="px-1.5 py-0.5 rounded-full text-[10px]"
              :class="activeCategory === cat.key ? 'bg-white/20' : 'bg-surface-hover'"
            >{{ categoryCount(cat.key) }}</span>
          </button>
        </div>

        <!-- Priority filter -->
        <div class="flex gap-1 bg-surface-card rounded-lg p-1 border border-surface-border">
          <button
            v-for="p in priorities"
            :key="p"
            class="px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors capitalize"
            :class="activePriority === p ? 'bg-fo-action text-white' : 'text-gray-500 hover:text-gray-900'"
            @click="activePriority = p"
          >{{ p }} <span v-if="p !== 'all'" class="text-[10px] opacity-70">({{ priorityCount(p) }})</span></button>
        </div>
      </div>

      <!-- Insights List -->
      <div v-if="filteredInsights.length" class="space-y-3">
        <div
          v-for="insight in filteredInsights"
          :key="insight.id"
          class="bg-surface-card rounded-xl border border-surface-border p-5 border-l-4 transition-colors hover:bg-surface-hover"
          :class="priorityBorder(insight.priority)"
        >
          <div class="flex items-start gap-4">
            <!-- Icon -->
            <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" :class="categoryColor(insight.category)">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" :d="typeIcon(insight.type)" />
              </svg>
            </div>

            <div class="flex-1 min-w-0">
              <!-- Top row: badges + title -->
              <div class="flex items-center gap-2 mb-1.5 flex-wrap">
                <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider" :class="categoryColor(insight.category)">
                  {{ categoryLabel(insight.category) }}
                </span>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider" :class="priorityColor(insight.priority)">
                  {{ insight.priority }}
                </span>
              </div>

              <h3 class="text-sm font-semibold text-gray-900 mb-1">{{ insight.title }}</h3>
              <p class="text-xs text-gray-500 leading-relaxed mb-3">{{ insight.description }}</p>

              <!-- Metrics row -->
              <div v-if="metricEntries(insight).length" class="flex items-center gap-4 mb-3 flex-wrap">
                <div v-for="(entry, i) in metricEntries(insight)" :key="i" class="flex items-center gap-1.5">
                  <span class="text-[10px] uppercase tracking-wider text-gray-400">{{ entry.label }}</span>
                  <span class="text-xs font-semibold text-gray-700">{{ entry.value }}</span>
                </div>
              </div>

              <!-- Action recommendation -->
              <div class="flex items-start gap-2 bg-gray-50 rounded-lg px-3 py-2">
                <svg class="w-4 h-4 text-fo-action flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
                </svg>
                <p class="text-xs text-gray-500">{{ insight.action }}</p>
              </div>

              <!-- Affected entity -->
              <div v-if="insight.affected_entity" class="mt-2">
                <span class="text-[10px] text-gray-400">
                  {{ insight.affected_entity }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="bg-surface-card rounded-xl border border-surface-border p-12 text-center">
        <svg class="w-12 h-12 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" stroke-width="1" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
        </svg>
        <p class="text-sm text-gray-500 mb-1">No insights match the current filters</p>
        <p class="text-xs text-gray-400">Try adjusting the category or priority filter</p>
      </div>
    </template>

    <!-- No data state -->
    <div v-else class="bg-surface-card rounded-xl border border-surface-border p-12 text-center">
      <svg class="w-12 h-12 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" stroke-width="1" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
      </svg>
      <p class="text-sm text-gray-500 mb-1">No insight data available</p>
      <p class="text-xs text-gray-400">Run the data pipelines first to generate insights</p>
    </div>
  </div>
</template>
