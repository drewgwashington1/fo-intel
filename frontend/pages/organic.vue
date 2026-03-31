<script setup lang="ts">
import { Line, Bar } from 'vue-chartjs'

const store = useDashboardStore()
const { get, post } = useApi()

const activeTab = ref<'keywords' | 'pages' | 'competitors'>('keywords')
const periods = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
  { label: '1Y', days: 365 },
]

// ── Tags (dynamic keyword groups) ───────────────────────────────
const activeTag = ref('non-branded')
const tags = ref<{ list_name: string; term_count: number }[]>([])
const tagTerms = ref<Record<string, any[]>>({})  // tag_name -> [{id, term}]
const showTermsPanel = ref(false)
const newTerm = ref('')
const selectedTag = ref('non-branded')
const newTagName = ref('')
const showNewTagInput = ref(false)
const bulkMode = ref(false)
const bulkTerms = ref('')
const bulkAdding = ref(false)
const bulkResult = ref<string | null>(null)

const totalTrackedKeywords = computed(() => tags.value.reduce((s, t) => s + t.term_count, 0))
const hasTrackedKeywords = computed(() => totalTrackedKeywords.value > 0)

const positionDist = ref<any[]>([])
const movements = ref<any>(null)
const countries = ref<any[]>([])
const activeMovementTab = ref('improved')

const TAG_COLORS = [
  { bg: 'bg-fo-action/10', text: 'text-fo-action', close: 'text-fo-action/50' },
  { bg: 'bg-purple-100', text: 'text-purple-600', close: 'text-purple-400' },
  { bg: 'bg-amber-100', text: 'text-amber-700', close: 'text-amber-400' },
  { bg: 'bg-emerald-100', text: 'text-emerald-700', close: 'text-emerald-400' },
  { bg: 'bg-pink-100', text: 'text-pink-600', close: 'text-pink-400' },
  { bg: 'bg-gray-100', text: 'text-gray-600', close: 'text-gray-400' },
]
function tagColor(idx: number) { return TAG_COLORS[idx % TAG_COLORS.length] }

async function loadTags() {
  tags.value = await get('/dashboard/keyword-tags')
  // Load terms for each tag
  const termLoads = tags.value.map(t => get(`/dashboard/keyword-lists/${t.list_name}`))
  const results = await Promise.allSettled(termLoads)
  const newTerms: Record<string, any[]> = {}
  tags.value.forEach((t, i) => {
    newTerms[t.list_name] = results[i].status === 'fulfilled' ? (results[i] as any).value : []
  })
  tagTerms.value = newTerms
}

async function addTerm() {
  const term = newTerm.value.trim()
  if (!term) return
  await post(`/dashboard/keyword-lists/${selectedTag.value}?term=${encodeURIComponent(term)}`)
  newTerm.value = ''
  await loadTags()
}

async function addBulkTerms() {
  const lines = bulkTerms.value.split('\n').map(l => l.trim()).filter(Boolean)
  if (!lines.length) return
  bulkAdding.value = true
  bulkResult.value = null
  bulkTerms.value = ''
  post(`/dashboard/keyword-lists/${selectedTag.value}/bulk`, lines)
    .then((res: any) => {
      bulkResult.value = `Added ${res.added_count} keywords${res.skipped_count ? `, ${res.skipped_count} skipped` : ''}`
      loadTags()
      setTimeout(() => { bulkResult.value = null }, 4000)
    })
    .catch(() => {
      bulkResult.value = 'Failed to add keywords'
      setTimeout(() => { bulkResult.value = null }, 4000)
    })
    .finally(() => { bulkAdding.value = false })
  bulkMode.value = false
}

async function removeTerm(tagName: string, term: string) {
  await fetch(`${useRuntimeConfig().public.apiBase}/dashboard/keyword-lists/${tagName}?term=${encodeURIComponent(term)}`, { method: 'DELETE' })
  await loadTags()
}

async function createTag() {
  const name = newTagName.value.trim().toLowerCase().replace(/\s+/g, '-')
  if (!name) return
  showNewTagInput.value = false
  newTagName.value = ''
  // Create tag by adding a placeholder (the tag exists once it has terms)
  // Just set it as selected so user can add terms to it
  selectedTag.value = name
  if (!tags.value.find(t => t.list_name === name)) {
    tags.value.push({ list_name: name, term_count: 0 })
    tagTerms.value[name] = []
  }
}

async function deleteTag(tagName: string) {
  await fetch(`${useRuntimeConfig().public.apiBase}/dashboard/keyword-tags/${tagName}`, { method: 'DELETE' })
  if (activeTag.value === tagName) activeTag.value = 'non-branded'
  if (selectedTag.value === tagName) selectedTag.value = 'non-branded'
  await loadTags()
}

const extraLoaded = ref(false)

async function loadAll(force = false) {
  await store.fetchOrganic(activeTag.value, force)
  if (!extraLoaded.value || force) {
    const days = store.periodDays
    const results = await Promise.allSettled([
      get('/dashboard/organic/position-distribution', { days }),
      get('/dashboard/organic/movements', { days }),
      get('/dashboard/organic/countries', { days }),
    ])
    const val = (r: PromiseSettledResult<any>) => r.status === 'fulfilled' ? r.value : null
    if (val(results[0])) positionDist.value = val(results[0])
    if (val(results[1])) movements.value = val(results[1])
    if (val(results[2])) countries.value = val(results[2])
    extraLoaded.value = true
  }
}

async function setPeriod(days: number) {
  store.setPeriod(days)
  extraLoaded.value = false
  await loadAll()
}

async function setTag(tag: string) {
  activeTag.value = tag
  await loadAll(true)
}

onMounted(() => { loadTags().then(() => loadAll()) })

const fmtNum = (n: number) => n?.toLocaleString() ?? '—'
const fmtPct = (n: number) => n != null ? `${(n * 100).toFixed(1)}%` : '—'
const fmtPos = (n: number) => n != null ? String(Math.round(n)) : '—'

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

function positionColor(pos: number) {
  if (pos <= 3) return 'text-status-up'
  if (pos <= 10) return 'text-fo-action'
  if (pos <= 20) return 'text-amber'
  return 'text-gray-400'
}

function positionBgColor(pos: number) {
  if (pos <= 3) return 'bg-status-up/15'
  if (pos <= 10) return 'bg-fo-action/15'
  if (pos <= 20) return 'bg-amber/15'
  return 'bg-gray-500/15'
}

function kdBarColor(pos: number) {
  if (pos <= 3) return 'bg-emerald-500'
  if (pos <= 10) return 'bg-blue-500'
  if (pos <= 20) return 'bg-amber-500'
  return 'bg-red-500'
}

function kdBarWidth(pos: number) {
  // Position 1 = full width, higher positions = thinner
  const clamped = Math.min(Math.max(pos, 1), 100)
  const pct = Math.max(100 - (clamped - 1) * 1.5, 8)
  return `${pct}%`
}

const competitorDomains = [
  { domain: 'firstorion.com', color: 'bg-fo-action', textColor: 'text-fo-action', dotColor: 'bg-fo-action' },
  { domain: 'hiya.com', color: 'bg-emerald-500', textColor: 'text-emerald-400', dotColor: 'bg-emerald-500' },
  { domain: 'numeracle.com', color: 'bg-purple-500', textColor: 'text-purple-400', dotColor: 'bg-purple-500' },
  { domain: 'transunion.com', color: 'bg-amber-500', textColor: 'text-amber-400', dotColor: 'bg-amber-500' },
  { domain: 'freecallerregistry.com', color: 'bg-pink-500', textColor: 'text-pink-400', dotColor: 'bg-pink-500' },
  { domain: 'tnsi.com', color: 'bg-cyan-500', textColor: 'text-cyan-400', dotColor: 'bg-cyan-500' },
]

const tabTitle = computed(() => {
  if (activeTab.value === 'pages') return 'Top pages'
  if (activeTab.value === 'competitors') return 'Organic competitors'
  return 'Organic keywords'
})

const subTabs = [
  { key: 'keywords' as const, label: 'Organic keywords' },
  { key: 'pages' as const, label: 'Top pages' },
  { key: 'competitors' as const, label: 'Organic competitors' },
]


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
          borderColor: '#F5A623',
          backgroundColor: 'rgba(245,166,35,0.08)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 2,
          yAxisID: 'y',
        },
        {
          label: 'Impressions',
          data: data.map((d: any) => d.impressions),
          borderColor: '#8B95A5',
          backgroundColor: 'transparent',
          borderDash: [4, 4],
          tension: 0.3,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 1.5,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index' as const, intersect: false },
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#8B95A5', font: { size: 10 }, maxTicksLimit: 12 },
        },
        y: {
          position: 'left' as const,
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#8B95A5', font: { size: 10 } },
        },
        y1: {
          position: 'right' as const,
          grid: { drawOnChartArea: false },
          ticks: { color: '#8B95A5', font: { size: 10 } },
        },
      },
    },
  }
})

const topPagesChart = computed(() => {
  const data = store.organicTimeline
  if (!data?.length) return null
  return {
    data: {
      labels: data.map((d: any) => new Date(d.data_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
      datasets: [
        {
          label: 'Organic traffic',
          data: data.map((d: any) => d.clicks),
          borderColor: '#F5A623',
          backgroundColor: 'rgba(245,166,35,0.08)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 2,
          yAxisID: 'y',
        },
        {
          label: 'Impressions',
          data: data.map((d: any) => d.impressions),
          borderColor: '#3B6BF5',
          backgroundColor: 'rgba(59,107,245,0.06)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 2,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index' as const, intersect: false },
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#8B95A5', font: { size: 10 }, maxTicksLimit: 12 },
        },
        y: {
          position: 'left' as const,
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#8B95A5', font: { size: 10 } },
        },
        y1: {
          position: 'right' as const,
          grid: { drawOnChartArea: false },
          ticks: { color: '#8B95A5', font: { size: 10 } },
        },
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
      plugins: {
        legend: {
          position: 'bottom' as const,
          labels: { color: '#8B95A5', font: { size: 10 }, boxWidth: 12, padding: 16 },
        },
      },
      scales: {
        x: { stacked: true, grid: { display: false }, ticks: { color: '#8B95A5', font: { size: 10 } } },
        y: { stacked: true, grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#8B95A5', font: { size: 10 } } },
      },
    },
  }
})

const totalPages = computed(() => store.organicTopPages?.length ?? 0)
const totalPageTraffic = computed(() => store.organicTopPages?.reduce((acc: number, p: any) => acc + (p.clicks || 0), 0) ?? 0)

const dateRange = computed(() => {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - store.periodDays)
  const fmt = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  return `${fmt(start)} - ${fmt(end)}`
})

function downloadCsv() {
  window.open(`${useRuntimeConfig().public.apiBase}/dashboard/organic/export?days=${store.periodDays}`, '_blank')
}

function truncateUrl(url: string, max = 60) {
  if (url.length <= max) return url
  return url.slice(0, max) + '...'
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
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-0">
      <div class="flex items-center gap-3">
        <h1 class="text-xl font-semibold text-gray-900">{{ tabTitle }}</h1>
        <button class="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700 transition-colors">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4M12 8h.01" />
          </svg>
          How to use
        </button>
      </div>
      <div class="flex items-center gap-3">
        <!-- Tag filter -->
        <div class="flex gap-0.5 bg-surface-card rounded-lg p-1 border border-surface-border flex-wrap">
          <button
            class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            :class="activeTag === 'all' ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-900'"
            @click="setTag('all')"
          >All</button>
          <button
            v-for="t in tags" :key="t.list_name"
            class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            :class="activeTag === t.list_name ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-900'"
            @click="setTag(t.list_name)"
          >{{ t.list_name }} ({{ t.term_count }})</button>
        </div>
        <button
          class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
          :class="showTermsPanel ? 'bg-gray-900 text-white' : 'bg-surface-card border border-surface-border text-gray-500 hover:text-gray-900'"
          @click="showTermsPanel = !showTermsPanel"
        >
          Tags ({{ tags.length }})
        </button>
        <button
          class="px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-card border border-surface-border text-gray-500 hover:text-gray-900 transition-colors"
          @click="downloadCsv"
        >
          Export CSV
        </button>
        <div class="flex gap-0.5 bg-surface-card rounded-lg p-1 border border-surface-border">
          <button
            v-for="p in periods" :key="p.days"
            class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            :class="store.periodDays === p.days ? 'bg-fo-action text-white' : 'text-gray-500 hover:text-gray-900'"
            @click="setPeriod(p.days)"
          >{{ p.label }}</button>
        </div>
      </div>
    </div>

    <!-- Keyword Tags Panel -->
    <div v-if="showTermsPanel" class="bg-surface-card rounded-xl border border-surface-border p-4 mb-4">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h3 class="text-sm font-semibold text-gray-900">Keyword Tags</h3>
          <p class="text-xs text-gray-400 mt-0.5">Group keywords by tag to filter organic data. Like Ahrefs keyword groups.</p>
        </div>
        <button
          v-if="!showNewTagInput"
          class="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-fo-action text-white hover:bg-fo-blue transition-colors"
          @click="showNewTagInput = true"
        >
          <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/></svg>
          New Tag
        </button>
        <div v-else class="flex items-center gap-2">
          <input
            v-model="newTagName"
            type="text"
            placeholder="Tag name (e.g. product, support)"
            class="px-3 py-1.5 text-xs rounded-lg border border-surface-border bg-surface focus:outline-none focus:border-fo-action w-48"
            @keydown.enter="createTag"
          />
          <button class="px-3 py-1.5 rounded-lg text-xs font-medium bg-fo-action text-white" @click="createTag">Create</button>
          <button class="px-2 py-1.5 text-xs text-gray-400 hover:text-gray-700" @click="showNewTagInput = false">Cancel</button>
        </div>
      </div>

      <!-- Add keywords to tag -->
      <div class="flex items-center gap-2 mb-2">
        <input
          v-if="!bulkMode"
          v-model="newTerm"
          type="text"
          placeholder="Add a keyword or phrase"
          class="flex-1 px-3 py-2 text-sm rounded-lg border border-surface-border bg-surface focus:outline-none focus:border-fo-action"
          @keydown.enter="addTerm"
        />
        <select
          v-model="selectedTag"
          class="px-3 py-2 text-xs rounded-lg border border-surface-border bg-surface focus:outline-none focus:border-fo-action"
        >
          <option v-for="t in tags" :key="t.list_name" :value="t.list_name">{{ t.list_name }}</option>
        </select>
        <button
          v-if="!bulkMode"
          class="px-4 py-2 rounded-lg text-xs font-medium bg-fo-action text-white hover:bg-fo-blue transition-colors"
          @click="addTerm"
        >Add</button>
        <button
          class="px-3 py-2 rounded-lg text-xs font-medium transition-colors"
          :class="bulkMode ? 'bg-gray-900 text-white' : 'bg-surface border border-surface-border text-gray-500 hover:text-gray-900'"
          @click="bulkMode = !bulkMode"
        >{{ bulkMode ? 'Single' : 'Bulk' }}</button>
      </div>

      <!-- Bulk add -->
      <div v-if="bulkMode" class="mb-4">
        <textarea
          v-model="bulkTerms"
          rows="5"
          placeholder="Paste keywords here, one per line"
          class="w-full px-3 py-2 text-sm rounded-lg border border-surface-border bg-surface focus:outline-none focus:border-fo-action resize-y font-mono"
        />
        <div class="flex items-center justify-between mt-2">
          <p class="text-xs text-gray-400">{{ bulkTerms.split('\n').filter(l => l.trim()).length }} keywords</p>
          <button
            class="px-4 py-2 rounded-lg text-xs font-medium bg-fo-action text-white hover:bg-fo-blue transition-colors disabled:opacity-50"
            :disabled="bulkAdding || !bulkTerms.trim()"
            @click="addBulkTerms"
          >
            <span v-if="bulkAdding">Adding...</span>
            <span v-else>Add All</span>
          </button>
        </div>
      </div>

      <!-- Bulk result toast -->
      <div v-if="bulkResult" class="mb-3 px-3 py-2 rounded-lg text-xs font-medium bg-fo-action/10 text-fo-action">
        {{ bulkResult }}
      </div>

      <!-- Tag groups -->
      <div class="space-y-4 mt-4">
        <div v-for="(tag, idx) in tags" :key="tag.list_name">
          <div class="flex items-center justify-between mb-2">
            <p class="text-[10px] uppercase tracking-wider text-gray-400">{{ tag.list_name }} ({{ tagTerms[tag.list_name]?.length || 0 }})</p>
            <button
              v-if="tag.list_name !== 'branded' && tag.list_name !== 'non-branded'"
              class="text-[10px] text-gray-400 hover:text-status-down transition-colors"
              @click="deleteTag(tag.list_name)"
            >Delete tag</button>
          </div>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="t in tagTerms[tag.list_name]"
              :key="t.id"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm"
              :class="[tagColor(idx).bg, tagColor(idx).text]"
            >
              {{ t.term }}
              <button :class="[tagColor(idx).close, 'hover:text-status-down transition-colors']" @click="removeTerm(tag.list_name, t.term)">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </span>
            <span v-if="!tagTerms[tag.list_name]?.length" class="text-xs text-gray-400">No keywords in this tag yet.</span>
          </div>
        </div>
        <div v-if="!tags.length" class="text-xs text-gray-400">No tags created. Click "New Tag" to get started.</div>
      </div>
    </div>

    <!-- Empty state when no keywords tracked -->
    <div v-if="!hasTrackedKeywords && !store.loading" class="bg-surface-card rounded-xl border border-surface-border p-12 text-center mb-4">
      <svg class="w-12 h-12 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" stroke-width="1" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
      <p class="text-sm text-gray-500 mb-1">No keywords tracked yet</p>
      <p class="text-xs text-gray-400 mb-4">Add keywords to start seeing organic performance data</p>
      <button
        class="px-4 py-2 rounded-lg text-sm font-medium bg-fo-action text-white hover:bg-fo-blue transition-colors"
        @click="showTermsPanel = true"
      >Add Keywords</button>
    </div>

    <!-- Sub-tabs bar -->
    <div class="border-b border-surface-border mt-4 mb-0">
      <div class="flex gap-0">
        <button
          v-for="tab in subTabs" :key="tab.key"
          class="relative px-5 py-3 text-sm font-medium transition-colors"
          :class="activeTab === tab.key
            ? 'text-fo-action'
            : 'text-gray-400 hover:text-gray-700'"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span
            v-if="activeTab === tab.key"
            class="absolute bottom-0 left-0 right-0 h-0.5 bg-fo-action rounded-t"
          />
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading" class="space-y-6">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="h-28 bg-surface-card rounded-xl animate-pulse" />
      </div>
      <div class="h-72 bg-surface-card rounded-xl animate-pulse" />
    </div>

    <!-- ============================================ -->
    <!-- TAB 1: Organic Keywords -->
    <!-- ============================================ -->
    <template v-else-if="store.organicOverview && activeTab === 'keywords'">
      <!-- KPI Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-6 gap-4 mb-6">
        <!-- Clicks -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Total Clicks</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.organicOverview.total_clicks) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.total_clicks, store.organicOverview.prev_clicks))">
            {{ deltaArrow(delta(store.organicOverview.total_clicks, store.organicOverview.prev_clicks)) }}
            {{ delta(store.organicOverview.total_clicks, store.organicOverview.prev_clicks).pct.toFixed(1) }}% vs prev
          </p>
        </div>
        <!-- Impressions -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Total Impressions</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.organicOverview.total_impressions) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.total_impressions, store.organicOverview.prev_impressions))">
            {{ deltaArrow(delta(store.organicOverview.total_impressions, store.organicOverview.prev_impressions)) }}
            {{ delta(store.organicOverview.total_impressions, store.organicOverview.prev_impressions).pct.toFixed(1) }}% vs prev
          </p>
        </div>
        <!-- CTR -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Avg CTR</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtPct(store.organicOverview.avg_ctr) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.avg_ctr, store.organicOverview.prev_ctr))">
            {{ deltaArrow(delta(store.organicOverview.avg_ctr, store.organicOverview.prev_ctr)) }}
            {{ delta(store.organicOverview.avg_ctr, store.organicOverview.prev_ctr).pct.toFixed(1) }}%
          </p>
        </div>
        <!-- Position (inverted) -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Avg Position</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtPos(store.organicOverview.avg_position) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.avg_position, store.organicOverview.prev_position), true)">
            {{ deltaArrow(delta(store.organicOverview.avg_position, store.organicOverview.prev_position)) }}
            {{ Math.abs(delta(store.organicOverview.avg_position, store.organicOverview.prev_position).pct).toFixed(1) }}%
          </p>
        </div>
        <!-- Keywords -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Keywords</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.organicOverview.unique_queries) }}</p>
          <p class="text-xs mt-1 text-gray-400">ranking queries</p>
        </div>
        <!-- Pages -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Pages</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.organicOverview.unique_pages) }}</p>
          <p class="text-xs mt-1 text-gray-400">ranking pages</p>
        </div>
      </div>

      <!-- Timeline Chart -->
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-gray-900">Clicks & Impressions Trend</h2>
          <div class="flex items-center gap-4">
            <span class="flex items-center gap-1.5 text-xs text-gray-400">
              <span class="w-3 h-0.5 bg-amber rounded-full inline-block" /> Clicks
            </span>
            <span class="flex items-center gap-1.5 text-xs text-gray-400">
              <span class="w-3 h-0.5 bg-gray-500 rounded-full inline-block border-dashed" style="border-top: 1px dashed #8B95A5; background: transparent;" /> Impressions
            </span>
          </div>
        </div>
        <div class="h-64">
          <Line v-if="timelineChart" :data="timelineChart.data" :options="timelineChart.options" />
        </div>
      </div>

      <!-- Keywords Table -->
      <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
        <div class="px-5 py-4 border-b border-surface-border flex items-center justify-between">
          <h2 class="text-sm font-semibold text-gray-900">Keywords</h2>
          <span class="text-xs text-gray-400">{{ store.organicTopQueries.length }} keywords</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-400 border-b border-surface-border">
                <th class="text-left px-5 py-3 w-8">#</th>
                <th class="text-left px-5 py-3">Keyword</th>
                <th class="text-right px-5 py-3">Volume</th>
                <th class="text-center px-5 py-3 w-20">KD</th>
                <th class="text-right px-5 py-3">Traffic</th>
                <th class="text-right px-5 py-3">Change</th>
                <th class="text-right px-5 py-3">Position</th>
                <th class="text-right px-5 py-3">Pos Change</th>
                <th class="text-left px-5 py-3">URL</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(q, i) in store.organicTopQueries"
                :key="q.query"
                class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
              >
                <td class="px-5 py-3 text-gray-400 text-xs">{{ i + 1 }}</td>
                <td class="px-5 py-3 text-gray-900 font-medium">{{ q.query }}</td>
                <td class="px-5 py-3 text-right text-gray-500 text-xs">
                  {{ fmtNum(Math.round((q.impressions || 0) / Math.max(store.periodDays / 30, 1))) }}
                </td>
                <td class="px-5 py-3">
                  <div class="flex items-center justify-center">
                    <div class="w-14 h-2 bg-surface rounded-full overflow-hidden">
                      <div
                        class="h-full rounded-full"
                        :class="kdBarColor(q.avg_position)"
                        :style="{ width: kdBarWidth(q.avg_position) }"
                      />
                    </div>
                  </div>
                </td>
                <td class="px-5 py-3 text-right text-gray-700 font-medium">{{ fmtNum(q.clicks) }}</td>
                <td class="px-5 py-3 text-right text-xs" :class="q.prev_clicks != null && q.clicks > q.prev_clicks ? 'text-status-up' : q.clicks < (q.prev_clicks || 0) ? 'text-status-down' : 'text-gray-400'">
                  <template v-if="q.prev_clicks != null">
                    <span class="inline-flex items-center gap-0.5">
                      {{ q.clicks > q.prev_clicks ? '\u2191' : q.clicks < q.prev_clicks ? '\u2193' : '\u2192' }}
                      {{ Math.abs(q.clicks - q.prev_clicks) }}
                    </span>
                  </template>
                  <template v-else>
                    <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-fo-action/15 text-fo-action">NEW</span>
                  </template>
                </td>
                <td class="px-5 py-3 text-right">
                  <span
                    class="inline-flex items-center justify-center px-2 py-0.5 rounded text-xs font-semibold"
                    :class="[positionColor(q.avg_position), positionBgColor(q.avg_position)]"
                  >
                    {{ fmtPos(q.avg_position) }}
                  </span>
                </td>
                <td class="px-5 py-3 text-right text-xs" :class="q.prev_position != null && q.avg_position < q.prev_position ? 'text-status-up' : q.avg_position > (q.prev_position || 999) ? 'text-status-down' : 'text-gray-400'">
                  <template v-if="q.prev_position != null">
                    {{ q.avg_position < q.prev_position ? '\u2191' : q.avg_position > q.prev_position ? '\u2193' : '\u2192' }}
                    {{ Math.round(Math.abs(q.avg_position - q.prev_position)) }}
                  </template>
                </td>
                <td class="px-5 py-3 text-left text-fo-action text-xs truncate max-w-[200px]" :title="q.page || ''">
                  {{ q.page ? truncateUrl(q.page, 40) : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Position Distribution + Keyword Movements -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Position Distribution -->
        <div class="bg-surface-card rounded-xl border border-surface-border p-5">
          <h2 class="text-sm font-semibold text-gray-900 mb-4">Position Distribution</h2>
          <div class="h-56">
            <Bar v-if="posDistChart" :data="posDistChart.data" :options="posDistChart.options" />
          </div>
        </div>

        <!-- Keyword Movements -->
        <div class="bg-surface-card rounded-xl border border-surface-border">
          <div class="px-5 py-4 border-b border-surface-border">
            <h2 class="text-sm font-semibold text-gray-900">Keyword Movements</h2>
            <p class="text-xs text-gray-400 mt-0.5">vs previous {{ store.periodDays }}-day period</p>
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
              :class="activeMovementTab === tab.key ? `bg-surface-hover ${tab.color}` : 'text-gray-400 hover:text-gray-700'"
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
              <span class="text-sm text-gray-900 truncate max-w-[200px]">{{ kw.query }}</span>
              <div class="flex items-center gap-3 text-xs">
                <span v-if="kw.current_position" class="text-gray-500">pos {{ Math.round(kw.current_position) }}</span>
                <span
                  v-if="kw.position_change && kw.position_change !== 0"
                  :class="kw.position_change > 0 ? 'text-status-up' : 'text-status-down'"
                >
                  {{ kw.position_change > 0 ? '\u2191' : '\u2193' }}{{ Math.round(Math.abs(kw.position_change)) }}
                </span>
                <span class="text-gray-400">{{ kw.clicks }} clicks</span>
              </div>
            </div>
            <p v-if="!movements.details[activeMovementTab]?.length" class="text-sm text-gray-400">No keywords in this category</p>
          </div>
        </div>
      </div>
    </template>

    <!-- ============================================ -->
    <!-- TAB 2: Top Pages -->
    <!-- ============================================ -->
    <template v-else-if="store.organicOverview && activeTab === 'pages'">
      <!-- Chart -->
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h2 class="text-sm font-semibold text-gray-900">Organic traffic by page</h2>
            <p class="text-xs text-gray-400 mt-1">{{ dateRange }}</p>
          </div>
          <div class="flex items-center gap-4">
            <span class="flex items-center gap-1.5 text-xs text-gray-400">
              <span class="w-3 h-0.5 bg-amber rounded-full inline-block" /> Organic traffic
            </span>
            <span class="flex items-center gap-1.5 text-xs text-gray-400">
              <span class="w-3 h-0.5 bg-fo-action rounded-full inline-block" /> Impressions
            </span>
          </div>
        </div>
        <div class="h-64">
          <Line v-if="topPagesChart" :data="topPagesChart.data" :options="topPagesChart.options" />
        </div>
      </div>

      <!-- Summary bar -->
      <div class="flex items-center gap-4 mb-4 px-1">
        <span class="text-sm text-gray-500">
          <span class="text-gray-900 font-semibold">{{ totalPages }}</span> pages
        </span>
        <span class="text-surface-border">|</span>
        <span class="text-sm text-gray-500">
          Total traffic: <span class="text-gray-900 font-semibold">{{ fmtNum(totalPageTraffic) }}</span>
        </span>
        <span class="text-surface-border">|</span>
        <span class="text-xs text-gray-400">{{ dateRange }}</span>
      </div>

      <!-- Pages Table -->
      <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-400 border-b border-surface-border">
                <th class="text-left px-5 py-3 w-8">#</th>
                <th class="text-left px-5 py-3">URL</th>
                <th class="text-left px-5 py-3">Top keyword</th>
                <th class="text-right px-5 py-3">Traffic</th>
                <th class="text-right px-5 py-3">Traffic %</th>
                <th class="text-right px-5 py-3">Change</th>
                <th class="text-right px-5 py-3">Keywords</th>
                <th class="text-right px-5 py-3">CTR</th>
                <th class="text-right px-5 py-3">Position</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(p, i) in store.organicTopPages"
                :key="p.page"
                class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors group"
              >
                <td class="px-5 py-3 text-gray-400 text-xs">{{ i + 1 }}</td>
                <td class="px-5 py-3" :title="p.page">
                  <a
                    :href="p.page"
                    target="_blank"
                    class="text-fo-action font-medium text-xs hover:underline truncate block max-w-[400px]"
                  >
                    {{ truncateUrl(p.page) }}
                  </a>
                </td>
                <td class="px-5 py-3 text-left text-gray-400 text-xs">—</td>
                <td class="px-5 py-3 text-right text-gray-900 font-medium">{{ fmtNum(p.clicks) }}</td>
                <td class="px-5 py-3 text-right text-xs">
                  <span
                    v-if="p.prev_clicks != null && p.prev_clicks > 0"
                    class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold"
                    :class="p.clicks >= p.prev_clicks ? 'bg-status-up/15 text-status-up' : 'bg-status-down/15 text-status-down'"
                  >
                    {{ p.clicks >= p.prev_clicks ? '+' : '' }}{{ ((p.clicks - p.prev_clicks) / p.prev_clicks * 100).toFixed(0) }}%
                  </span>
                  <span v-else class="text-gray-400">—</span>
                </td>
                <td class="px-5 py-3 text-right text-xs" :class="p.prev_clicks != null && p.clicks > p.prev_clicks ? 'text-status-up' : p.clicks < (p.prev_clicks || 0) ? 'text-status-down' : 'text-gray-400'">
                  <template v-if="p.prev_clicks != null">
                    <span class="inline-flex items-center gap-0.5">
                      {{ p.clicks > p.prev_clicks ? '\u2191' : p.clicks < p.prev_clicks ? '\u2193' : '\u2192' }}
                      {{ Math.abs(p.clicks - p.prev_clicks) }}
                    </span>
                  </template>
                  <template v-else>
                    <span class="text-gray-500">—</span>
                  </template>
                </td>
                <td class="px-5 py-3 text-right text-gray-700">{{ p.keywords ?? '—' }}</td>
                <td class="px-5 py-3 text-right text-gray-700">{{ fmtPct(p.ctr) }}</td>
                <td class="px-5 py-3 text-right">
                  <span
                    class="inline-flex items-center justify-center px-2 py-0.5 rounded text-xs font-semibold"
                    :class="[positionColor(p.avg_position), positionBgColor(p.avg_position)]"
                  >
                    {{ fmtPos(p.avg_position) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ============================================ -->
    <!-- TAB 3: Organic Competitors -->
    <!-- ============================================ -->
    <template v-else-if="store.organicOverview && activeTab === 'competitors'">
      <!-- Competitor domain chips -->
      <div class="flex flex-wrap items-center gap-2 mb-6">
        <span
          v-for="comp in competitorDomains"
          :key="comp.domain"
          class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border border-surface-border bg-surface-card hover:bg-surface-hover transition-colors cursor-default"
          :class="comp.textColor"
        >
          <span class="w-2 h-2 rounded-full" :class="comp.dotColor" />
          {{ comp.domain }}
        </span>
      </div>

      <!-- Bubble chart placeholder -->
      <div class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <h2 class="text-sm font-semibold text-gray-900 mb-2">Competing Domains</h2>
        <p class="text-xs text-gray-400 mb-4">Keyword overlap and traffic share visualization</p>
        <div class="h-80 rounded-lg border border-dashed border-surface-border bg-surface/50 flex flex-col items-center justify-center gap-3">
          <!-- Decorative bubble scatter -->
          <div class="relative w-full h-full">
            <div class="absolute top-[20%] left-[15%] w-24 h-24 rounded-full bg-fo-action/10 border border-fo-action/20 flex items-center justify-center">
              <span class="text-[10px] text-fo-action/60 font-medium">firstorion.com</span>
            </div>
            <div class="absolute top-[30%] left-[45%] w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
              <span class="text-[10px] text-emerald-400/60 font-medium">hiya.com</span>
            </div>
            <div class="absolute top-[15%] right-[20%] w-14 h-14 rounded-full bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
              <span class="text-[10px] text-purple-400/60 font-medium">numeracle</span>
            </div>
            <div class="absolute bottom-[25%] left-[30%] w-20 h-20 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
              <span class="text-[10px] text-amber-400/60 font-medium">transunion</span>
            </div>
            <div class="absolute bottom-[20%] right-[25%] w-12 h-12 rounded-full bg-pink-500/10 border border-pink-500/20 flex items-center justify-center">
              <span class="text-[9px] text-pink-400/60 font-medium">fcr</span>
            </div>
            <div class="absolute top-[55%] right-[40%] w-10 h-10 rounded-full bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
              <span class="text-[9px] text-cyan-400/60 font-medium">tnsi</span>
            </div>
            <!-- Center message -->
            <div class="absolute inset-0 flex items-center justify-center">
              <span class="text-xs text-gray-400 bg-surface-card/80 px-3 py-1.5 rounded-lg border border-surface-border">
                Competitor analysis powered by SERP data
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Top competing domains table -->
      <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
        <div class="px-5 py-4 border-b border-surface-border">
          <h2 class="text-sm font-semibold text-gray-900">Top competing domains</h2>
          <p class="text-xs text-gray-400 mt-0.5">Domains competing for the same organic keywords</p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-400 border-b border-surface-border">
                <th class="text-left px-5 py-3 w-8">#</th>
                <th class="text-left px-5 py-3">Domain</th>
                <th class="text-right px-5 py-3">Keywords</th>
                <th class="text-right px-5 py-3">Common</th>
                <th class="text-right px-5 py-3">Share</th>
                <th class="text-right px-5 py-3">Traffic</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(comp, i) in competitorDomains.slice(1)"
                :key="comp.domain"
                class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
              >
                <td class="px-5 py-3 text-gray-400 text-xs">{{ i + 1 }}</td>
                <td class="px-5 py-3">
                  <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full" :class="comp.dotColor" />
                    <span class="text-gray-900 font-medium text-xs">{{ comp.domain }}</span>
                  </div>
                </td>
                <td class="px-5 py-3 text-right text-gray-400 text-xs">&mdash;</td>
                <td class="px-5 py-3 text-right text-gray-400 text-xs">&mdash;</td>
                <td class="px-5 py-3 text-right text-gray-400 text-xs">&mdash;</td>
                <td class="px-5 py-3 text-right text-gray-400 text-xs">&mdash;</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
