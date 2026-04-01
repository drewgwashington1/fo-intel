<script setup lang="ts">
import { Line, Bar } from 'vue-chartjs'

const store = useDashboardStore()
const { get, post, del, patch } = useApi()

const activeTab = ref<'keywords' | 'pages' | 'competitors'>('keywords')
const periods = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
  { label: '1Y', days: 365 },
]

// ── Tags (dynamic keyword groups) ───────────────────────────────
const activeCategory = ref<'all' | 'branded' | 'non-branded'>('non-branded')
const activeTag = ref('all')
const tags = ref<{ list_name: string; term_count: number }[]>([])
const tagTerms = ref<Record<string, any[]>>({})  // tag_name -> [{id, term, category}]
const showTermsPanel = ref(false)
const newTerm = ref('')
const selectedTag = ref('general')
const selectedCategory = ref<'branded' | 'non-branded'>('non-branded')
const newTagName = ref('')
const showNewTagInput = ref(false)
const bulkMode = ref(false)
const bulkTerms = ref('')
const bulkAdding = ref(false)
const bulkResult = ref<string | null>(null)
const rebuildStatus = ref<string | null>(null)

const allKeywords = computed(() => {
  const all: any[] = []
  for (const tag of tags.value) {
    for (const t of (tagTerms.value[tag.list_name] || [])) {
      all.push({ ...t, list_name: tag.list_name })
    }
  }
  return all
})
const totalTrackedKeywords = computed(() => allKeywords.value.length)
const hasTrackedKeywords = computed(() => totalTrackedKeywords.value > 0)
const brandedCount = computed(() => allKeywords.value.filter(k => k.category === 'branded').length)
const nonBrandedCount = computed(() => allKeywords.value.filter(k => k.category === 'non-branded').length)

// Map queries to their keyword tag & category for display in the table
const queryTagMap = computed(() => {
  const map: Record<string, { tag: string; category: string }> = {}
  for (const tag of tags.value) {
    for (const t of (tagTerms.value[tag.list_name] || [])) {
      // Store the term -> tag/category mapping
      map[t.term.toLowerCase()] = { tag: tag.list_name, category: t.category || 'non-branded' }
    }
  }
  return map
})

function getQueryMeta(query: string) {
  const q = query?.toLowerCase() || ''
  // Direct match first
  if (queryTagMap.value[q]) return queryTagMap.value[q]
  // Partial match — check if any tracked term appears in the query
  for (const [term, meta] of Object.entries(queryTagMap.value)) {
    if (q.includes(term)) return meta
  }
  return null
}

const positionDist = ref<any[]>([])
const movements = ref<any>(null)
const countries = ref<any[]>([])
const organicCompetitors = ref<any[]>([])

const trackedCompDomains = [
  { domain: 'hiya.com', textColor: 'text-emerald-600', dotColor: 'bg-emerald-500' },
  { domain: 'numeracle.com', textColor: 'text-purple-600', dotColor: 'bg-purple-500' },
  { domain: 'transunion.com', textColor: 'text-amber-600', dotColor: 'bg-amber-500' },
  { domain: 'freecallerregistry.com', textColor: 'text-pink-600', dotColor: 'bg-pink-500' },
  { domain: 'tnsi.com', textColor: 'text-cyan-600', dotColor: 'bg-cyan-500' },
]
const trackedCompSet = new Set(trackedCompDomains.map(c => c.domain))

function compData(domain: string) {
  return organicCompetitors.value.find(c => c.domain === domain)
}

const BUBBLE_COLORS = [
  '59, 130, 246',   // blue
  '16, 185, 129',   // emerald
  '168, 85, 247',   // purple
  '245, 158, 11',   // amber
  '236, 72, 153',   // pink
  '6, 182, 212',    // cyan
  '239, 68, 68',    // red
  '99, 102, 241',   // indigo
  '234, 179, 8',    // yellow
  '244, 63, 94',    // rose
  '20, 184, 166',   // teal
  '139, 92, 246',   // violet
]
function bubbleColor(i: number, alpha: number) {
  return `rgba(${BUBBLE_COLORS[i % BUBBLE_COLORS.length]}, ${alpha})`
}
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

async function afterKeywordChange() {
  rebuildStatus.value = 'Recomputing organic data for your keywords...'
  await loadTags()
  // Backend background task rebuilds keyword maps + summaries (~3-8s)
  // Poll until summaries are refreshed, then reload dashboard
  let attempts = 0
  const poll = setInterval(async () => {
    attempts++
    if (attempts >= 6) {
      clearInterval(poll)
      rebuildStatus.value = 'Refreshing dashboard...'
      await loadAll(true)
      rebuildStatus.value = null
    } else if (attempts === 1) {
      rebuildStatus.value = 'Matching keywords to search queries...'
    } else if (attempts === 3) {
      rebuildStatus.value = 'Rebuilding organic summaries...'
    }
  }, 2000)
  // Also try an early refresh at 5s
  setTimeout(async () => {
    await loadAll(true)
    if (rebuildStatus.value) {
      rebuildStatus.value = 'Data updated. Final cleanup...'
      setTimeout(() => { rebuildStatus.value = null }, 1500)
    }
    clearInterval(poll)
  }, 6000)
}

async function loadTags() {
  tags.value = await get('/dashboard/keyword-tags')
  // Ensure 'general' tag always exists in the dropdown
  if (!tags.value.find(t => t.list_name === 'general')) {
    tags.value.unshift({ list_name: 'general', term_count: 0 })
  }
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
  await post(`/dashboard/keyword-lists/${selectedTag.value}?term=${encodeURIComponent(term)}&category=${selectedCategory.value}`)
  newTerm.value = ''
  afterKeywordChange()
}

async function addBulkTerms() {
  const lines = bulkTerms.value.split('\n').map(l => l.trim()).filter(Boolean)
  if (!lines.length) return
  bulkAdding.value = true
  bulkResult.value = null
  const termsCopy = [...lines]
  bulkTerms.value = ''
  post(`/dashboard/keyword-lists/${selectedTag.value}/bulk?category=${selectedCategory.value}`, termsCopy)
    .then((res: any) => {
      bulkResult.value = `Added ${res.added_count} keywords${res.skipped_count ? `, ${res.skipped_count} skipped` : ''}`
      afterKeywordChange()
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
  await del(`/dashboard/keyword-lists/${tagName}`, { term })
  afterKeywordChange()
}

async function toggleCategory(keywordId: number, currentCategory: string) {
  const newCat = currentCategory === 'branded' ? 'non-branded' : 'branded'
  await patch(`/dashboard/keywords/${keywordId}/category`, { category: newCat })
  afterKeywordChange()
}

async function createTag() {
  const name = newTagName.value.trim().toLowerCase().replace(/\s+/g, '-')
  if (!name) return
  showNewTagInput.value = false
  newTagName.value = ''
  selectedTag.value = name
  if (!tags.value.find(t => t.list_name === name)) {
    tags.value.push({ list_name: name, term_count: 0 })
    tagTerms.value[name] = []
  }
}

async function deleteTag(tagName: string) {
  await del(`/dashboard/keyword-tags/${tagName}`)
  if (activeTag.value === tagName) activeTag.value = 'all'
  if (selectedTag.value === tagName) selectedTag.value = 'general'
  await loadTags()
}

const extraLoaded = ref(false)

async function loadAll(force = false) {
  const brandParam = activeCategory.value === 'all' ? undefined : activeCategory.value
  const tagParam = activeTag.value === 'all' ? undefined : activeTag.value
  await store.fetchOrganic(activeCategory.value, activeTag.value, force)
  if (!extraLoaded.value || force) {
    const days = store.periodDays
    const results = await Promise.allSettled([
      get('/dashboard/organic/position-distribution', { days, brand: brandParam, tag: tagParam }),
      get('/dashboard/organic/movements', { days, brand: brandParam, tag: tagParam }),
      get('/dashboard/organic/countries', { days, brand: brandParam, tag: tagParam }),
      get('/dashboard/organic/competitors', { days: 90 }),
    ])
    const val = (r: PromiseSettledResult<any>) => r.status === 'fulfilled' ? r.value : null
    if (val(results[0])) positionDist.value = val(results[0])
    if (val(results[1])) movements.value = val(results[1])
    if (val(results[2])) countries.value = val(results[2])
    if (val(results[3])) organicCompetitors.value = val(results[3])
    extraLoaded.value = true
  }
}

async function setPeriod(days: number) {
  store.setPeriod(days)
  extraLoaded.value = false
  await loadAll()
}

async function setCategory(cat: 'all' | 'branded' | 'non-branded') {
  activeCategory.value = cat
  await loadAll(true)
}

async function setTag(tag: string) {
  activeTag.value = tag
  extraLoaded.value = false
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
  if (!url) return '—'
  try {
    const u = new URL(url.startsWith('http') ? url : `https://${url}`)
    const path = u.pathname === '/' ? '/' : u.pathname
    return path.length > max ? path.slice(0, max) + '...' : path
  } catch {
    return url.length > max ? url.slice(0, max) + '...' : url
  }
}

const movementTabs = [
  { key: 'improved', label: 'Improved', color: 'text-status-up', tooltip: 'Keywords that moved to a better (lower) position vs previous period' },
  { key: 'declined', label: 'Declined', color: 'text-status-down', tooltip: 'Keywords that dropped to a worse (higher) position vs previous period' },
  { key: 'new', label: 'New', color: 'text-fo-action', tooltip: 'Keywords that started ranking for the first time this period' },
  { key: 'lost', label: 'Lost', color: 'text-gray-400', tooltip: 'Keywords that stopped ranking entirely this period' },
]
</script>

<template>
  <div>
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-0">
      <div class="flex items-center gap-3">
        <h1 class="text-xl font-semibold text-gray-900">{{ tabTitle }}</h1>
      </div>
      <div class="flex items-center gap-3">
        <!-- Branded / Non-branded category filter -->
        <div class="flex gap-0.5 bg-surface-card rounded-lg p-1 border border-surface-border">
          <button
            class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            :class="activeCategory === 'all' ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-900'"
            @click="setCategory('all')"
          >All</button>
          <button
            class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            :class="activeCategory === 'non-branded' ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-900'"
            @click="setCategory('non-branded')"
          >Non-branded ({{ nonBrandedCount }})</button>
          <button
            class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            :class="activeCategory === 'branded' ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-900'"
            @click="setCategory('branded')"
          >Branded ({{ brandedCount }})</button>
        </div>
        <!-- Tag filter dropdown -->
        <select
          v-if="tags.length > 1"
          :value="activeTag"
          class="px-3 py-1.5 rounded-lg text-xs font-medium border border-surface-border bg-surface-card text-gray-700 focus:outline-none focus:border-fo-action"
          @change="setTag(($event.target as HTMLSelectElement).value)"
        >
          <option value="all">All tags</option>
          <option v-for="t in tags" :key="t.list_name" :value="t.list_name">{{ t.list_name }} ({{ t.term_count }})</option>
        </select>
        <button
          class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
          :class="showTermsPanel ? 'bg-gray-900 text-white' : 'bg-surface-card border border-surface-border text-gray-500 hover:text-gray-900'"
          @click="showTermsPanel = !showTermsPanel"
        >
          Manage Keywords ({{ totalTrackedKeywords }})
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

    <!-- Keyword Management Panel -->
    <div v-if="showTermsPanel" class="bg-surface-card rounded-xl border border-surface-border p-4 mb-4">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h3 class="text-sm font-semibold text-gray-900">Manage Keywords</h3>
          <p class="text-xs text-gray-400 mt-0.5">Add keywords, classify as branded/non-branded, and organize with tags.</p>
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

      <!-- Add keywords -->
      <div class="flex items-center gap-2 mb-2">
        <input
          v-if="!bulkMode"
          v-model="newTerm"
          type="text"
          placeholder="Add a keyword or phrase"
          class="flex-1 px-3 py-2 text-sm rounded-lg border border-surface-border bg-surface focus:outline-none focus:border-fo-action"
          @keydown.enter="addTerm"
        />
        <!-- Category selector (branded / non-branded) -->
        <div class="flex gap-0.5 bg-surface rounded-lg p-0.5 border border-surface-border">
          <button
            class="px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-colors"
            :class="selectedCategory === 'non-branded' ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-900'"
            @click="selectedCategory = 'non-branded'"
          >Non-branded</button>
          <button
            class="px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-colors"
            :class="selectedCategory === 'branded' ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-900'"
            @click="selectedCategory = 'branded'"
          >Branded</button>
        </div>
        <!-- Tag selector -->
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

      <!-- Tag groups with category badges -->
      <div class="space-y-4 mt-4">
        <div v-for="(tag, idx) in tags" :key="tag.list_name">
          <div class="flex items-center justify-between mb-2">
            <p class="text-[10px] uppercase tracking-wider text-gray-400">{{ tag.list_name }} ({{ tagTerms[tag.list_name]?.length || 0 }})</p>
            <button
              v-if="tag.list_name !== 'general'"
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
              <button
                class="px-1.5 py-0.5 rounded-full text-[9px] font-semibold uppercase transition-colors"
                :class="t.category === 'branded' ? 'bg-amber-200 text-amber-700 hover:bg-amber-300' : 'bg-gray-200 text-gray-500 hover:bg-gray-300'"
                :title="'Click to toggle — currently ' + t.category"
                @click="toggleCategory(t.id, t.category)"
              >{{ t.category === 'branded' ? 'B' : 'NB' }}</button>
              <button :class="[tagColor(idx).close, 'hover:text-status-down transition-colors']" @click="removeTerm(tag.list_name, t.term)">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </span>
            <span v-if="!tagTerms[tag.list_name]?.length" class="text-xs text-gray-400">No keywords in this tag yet.</span>
          </div>
        </div>
        <div v-if="!tags.length" class="text-xs text-gray-400">No tags created yet.</div>
      </div>
    </div>

    <!-- Rebuild status banner -->
    <div v-if="rebuildStatus" class="flex items-center gap-3 px-4 py-3 mb-4 rounded-xl border border-fo-action/20 bg-fo-action/5">
      <svg class="w-4 h-4 text-fo-action animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <p class="text-sm text-fo-action font-medium">{{ rebuildStatus }}</p>
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
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Total clicks from organic Google search results during this period">Total Clicks</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.organicOverview.total_clicks) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.total_clicks, store.organicOverview.prev_clicks))">
            {{ deltaArrow(delta(store.organicOverview.total_clicks, store.organicOverview.prev_clicks)) }}
            {{ delta(store.organicOverview.total_clicks, store.organicOverview.prev_clicks).pct.toFixed(1) }}% vs prev
          </p>
        </div>
        <!-- Impressions -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Number of times your pages appeared in Google search results">Total Impressions</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.organicOverview.total_impressions) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.total_impressions, store.organicOverview.prev_impressions))">
            {{ deltaArrow(delta(store.organicOverview.total_impressions, store.organicOverview.prev_impressions)) }}
            {{ delta(store.organicOverview.total_impressions, store.organicOverview.prev_impressions).pct.toFixed(1) }}% vs prev
          </p>
        </div>
        <!-- CTR -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Click-through rate — clicks divided by impressions">Avg CTR</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtPct(store.organicOverview.avg_ctr) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.avg_ctr, store.organicOverview.prev_ctr))">
            {{ deltaArrow(delta(store.organicOverview.avg_ctr, store.organicOverview.prev_ctr)) }}
            {{ delta(store.organicOverview.avg_ctr, store.organicOverview.prev_ctr).pct.toFixed(1) }}%
          </p>
        </div>
        <!-- Position (inverted) -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Weighted average position in Google search results (lower is better)">Avg Position</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtPos(store.organicOverview.avg_position) }}</p>
          <p class="text-xs mt-1" :class="deltaClass(delta(store.organicOverview.avg_position, store.organicOverview.prev_position), true)">
            {{ deltaArrow(delta(store.organicOverview.avg_position, store.organicOverview.prev_position)) }}
            {{ Math.abs(delta(store.organicOverview.avg_position, store.organicOverview.prev_position).pct).toFixed(1) }}%
          </p>
        </div>
        <!-- Keywords -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Total unique search queries your site ranks for">Keywords</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.organicOverview.unique_queries) }}</p>
          <p class="text-xs mt-1 text-gray-400">ranking queries</p>
        </div>
        <!-- Pages -->
        <div class="bg-surface-card rounded-xl p-5 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1" title="Total unique pages on your site that rank in Google search">Pages</p>
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
                <th class="text-left px-5 py-3 w-8" title="Row number">#</th>
                <th class="text-left px-5 py-3" title="Search query that triggered your page in Google results">Keyword</th>
                <th class="text-center px-5 py-3" title="Branded or non-branded classification from your keyword lists">Category</th>
                <th class="text-center px-5 py-3" title="Keyword tag group from your keyword lists">Tag</th>
                <th class="text-right px-5 py-3" title="Estimated monthly search volume based on impressions">Volume</th>
                <th class="text-center px-5 py-3 w-20" title="Keyword difficulty — how competitive this keyword is based on position">KD</th>
                <th class="text-right px-5 py-3" title="Number of clicks received from this keyword">Traffic</th>
                <th class="text-right px-5 py-3" title="Click change compared to previous period">Change</th>
                <th class="text-right px-5 py-3" title="Average ranking position in Google search results (lower is better)">Position</th>
                <th class="text-right px-5 py-3" title="Position change compared to previous period (up arrow = improved)">Pos Change</th>
                <th class="text-left px-5 py-3" title="Landing page URL that ranks for this keyword">URL</th>
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
                <td class="px-5 py-3 text-center">
                  <span
                    v-if="getQueryMeta(q.query)"
                    class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase"
                    :class="getQueryMeta(q.query)?.category === 'branded' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-500'"
                  >{{ getQueryMeta(q.query)?.category === 'branded' ? 'B' : 'NB' }}</span>
                  <span v-else class="text-gray-300 text-xs">—</span>
                </td>
                <td class="px-5 py-3 text-center">
                  <span
                    v-if="getQueryMeta(q.query)"
                    class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium bg-fo-action/10 text-fo-action"
                  >{{ getQueryMeta(q.query)?.tag }}</span>
                  <span v-else class="text-gray-300 text-xs">—</span>
                </td>
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
          <h2 class="text-sm font-semibold text-gray-900 mb-4" title="How your keywords are distributed across Google search result positions over time">Position Distribution</h2>
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
              :title="tab.tooltip"
              @click="activeMovementTab = tab.key"
            >{{ tab.label }}</button>
          </div>
          <!-- Movement list -->
          <div v-if="movements" class="p-5 space-y-0 max-h-80 overflow-y-auto">
            <div
              v-for="kw in movements.details[activeMovementTab]?.slice(0, 15)"
              :key="kw.query"
              class="flex items-center justify-between py-2.5 border-b border-surface-border last:border-0 gap-4"
            >
              <span class="text-sm text-gray-900 min-w-0 break-words" :title="kw.query">{{ kw.query }}</span>
              <div class="flex items-center gap-3 text-xs shrink-0">
                <span v-if="kw.current_pos != null" class="text-gray-500 font-medium">pos {{ Math.round(kw.current_pos) }}</span>
                <span
                  v-if="kw.prev_pos != null && kw.current_pos != null"
                  class="inline-flex items-center gap-0.5 font-semibold"
                  :class="kw.current_pos < kw.prev_pos ? 'text-status-up' : kw.current_pos > kw.prev_pos ? 'text-status-down' : 'text-gray-400'"
                >
                  {{ kw.current_pos < kw.prev_pos ? '\u2191' : kw.current_pos > kw.prev_pos ? '\u2193' : '\u2192' }}{{ Math.round(Math.abs(kw.current_pos - kw.prev_pos)) }}
                </span>
                <span v-else-if="kw.prev_pos != null && kw.current_pos == null" class="text-gray-400 font-medium">was {{ Math.round(kw.prev_pos) }}</span>
                <span class="text-gray-400">{{ kw.current_clicks ?? 0 }} clicks</span>
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
    <template v-else-if="activeTab === 'pages'">
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
    <template v-else-if="activeTab === 'competitors'">
      <!-- Tracked competitor chips -->
      <div class="flex flex-wrap items-center gap-2 mb-6">
        <span class="text-[10px] uppercase tracking-wider text-gray-400 mr-1">Tracked:</span>
        <span
          v-for="(comp, i) in trackedCompDomains"
          :key="comp.domain"
          class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border border-surface-border bg-surface-card"
          :class="comp.textColor"
        >
          <span class="w-2 h-2 rounded-full" :class="comp.dotColor" />
          {{ comp.domain }}
          <span v-if="compData(comp.domain)" class="text-gray-400 font-normal">{{ compData(comp.domain)?.common_keywords }} kw</span>
        </span>
      </div>

      <!-- Bubble chart — competitor keyword overlap visualization -->
      <div v-if="organicCompetitors.length" class="bg-surface-card rounded-xl border border-surface-border p-5 mb-6">
        <h2 class="text-sm font-semibold text-gray-900 mb-2">Keyword Overlap</h2>
        <p class="text-xs text-gray-400 mb-4">Bubble size = common keywords, position = avg SERP ranking</p>
        <div class="relative h-72 rounded-lg bg-surface/50 border border-surface-border overflow-hidden">
          <!-- Y-axis labels -->
          <div class="absolute left-2 top-2 text-[9px] text-gray-400">Top 3</div>
          <div class="absolute left-2 top-1/2 -translate-y-1/2 text-[9px] text-gray-400">Top 10</div>
          <div class="absolute left-2 bottom-2 text-[9px] text-gray-400">50+</div>
          <!-- Grid lines -->
          <div class="absolute left-8 right-0 top-[33%] border-t border-dashed border-gray-200" />
          <div class="absolute left-8 right-0 top-[66%] border-t border-dashed border-gray-200" />
          <!-- Bubbles -->
          <div
            v-for="(comp, i) in organicCompetitors.filter(c => c.common_keywords > 0)"
            :key="comp.domain"
            class="absolute rounded-full flex items-center justify-center transition-all duration-300 cursor-default"
            :class="comp.is_self ? 'border-2 border-fo-action ring-2 ring-fo-action/20' : 'border-2'"
            :style="{
              width: Math.max(50, Math.min(140, comp.common_keywords * 2.5)) + 'px',
              height: Math.max(50, Math.min(140, comp.common_keywords * 2.5)) + 'px',
              top: Math.min(80, Math.max(5, (comp.avg_position / 60) * 80)) + '%',
              left: (12 + (i % 5) * 16 + (i >= 5 ? 8 : 0)) + '%',
              backgroundColor: comp.is_self ? 'rgba(245,166,35,0.15)' : bubbleColor(i, 0.12),
              borderColor: comp.is_self ? '#F5A623' : bubbleColor(i, 0.5),
            }"
            :title="`${comp.domain}: ${comp.common_keywords} keywords, avg pos ${comp.avg_position}`"
          >
            <div class="text-center px-1">
              <span class="text-[9px] font-semibold leading-tight block" :style="{ color: comp.is_self ? '#F5A623' : bubbleColor(i, 1) }">
                {{ comp.domain.replace('.com', '').replace('.org', '') }}
              </span>
              <span class="text-[8px] opacity-60 block" :style="{ color: comp.is_self ? '#F5A623' : bubbleColor(i, 1) }">
                {{ comp.common_keywords }} kw
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Top competing domains table -->
      <div v-if="organicCompetitors.length" class="bg-surface-card rounded-xl border border-surface-border mb-6">
        <div class="px-5 py-4 border-b border-surface-border">
          <h2 class="text-sm font-semibold text-gray-900">Competing domains</h2>
          <p class="text-xs text-gray-400 mt-0.5">Domains ranking for the same keywords as firstorion.com (from SERP data)</p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider text-gray-400 border-b border-surface-border">
                <th class="text-left px-5 py-3 w-8" title="Rank by keyword overlap">#</th>
                <th class="text-left px-5 py-3" title="Competitor domain">Domain</th>
                <th class="text-center px-5 py-3 w-16" title="Tracked competitor">Tracked</th>
                <th class="text-right px-5 py-3" title="Number of keywords this domain ranks for that you also rank for">Common Keywords</th>
                <th class="text-right px-5 py-3" title="Percentage of your keywords this competitor also ranks for">Overlap</th>
                <th class="text-right px-5 py-3" title="Average ranking position for common keywords">Avg Position</th>
                <th class="text-right px-5 py-3" title="Keywords where competitor ranks in top 3">Top 3</th>
                <th class="text-right px-5 py-3" title="Keywords where competitor ranks in top 10">Top 10</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(comp, i) in organicCompetitors"
                :key="comp.domain"
                class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                :class="comp.is_self ? 'bg-fo-action/5 border-l-2 border-l-fo-action' : ''"
              >
                <td class="px-5 py-3 text-gray-400 text-xs">{{ comp.is_self ? '' : i + 1 }}</td>
                <td class="px-5 py-3">
                  <div class="flex items-center gap-2">
                    <span class="text-gray-900 font-medium text-xs">{{ comp.domain }}</span>
                    <span v-if="comp.is_self" class="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-fo-action/15 text-fo-action">YOU</span>
                  </div>
                </td>
                <td class="px-5 py-3 text-center">
                  <span v-if="!comp.is_self" class="inline-flex w-4 h-4 items-center justify-center rounded-full bg-fo-action/15 text-fo-action text-[10px]">&#10003;</span>
                </td>
                <td class="px-5 py-3 text-right text-gray-700 font-medium">{{ comp.common_keywords }}</td>
                <td class="px-5 py-3 text-right">
                  <span class="text-xs font-medium" :class="comp.overlap_pct > 30 ? 'text-status-down' : comp.overlap_pct > 10 ? 'text-amber-600' : 'text-gray-500'">
                    {{ comp.overlap_pct }}%
                  </span>
                </td>
                <td class="px-5 py-3 text-right">
                  <span
                    class="inline-flex items-center justify-center px-2 py-0.5 rounded text-xs font-semibold"
                    :class="[positionColor(comp.avg_position), positionBgColor(comp.avg_position)]"
                  >{{ fmtPos(comp.avg_position) }}</span>
                </td>
                <td class="px-5 py-3 text-right text-status-up text-xs font-medium">{{ comp.top3 }}</td>
                <td class="px-5 py-3 text-right text-fo-action text-xs font-medium">{{ comp.top10 }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="bg-surface-card rounded-xl border border-surface-border p-12 text-center mb-6">
        <svg class="w-12 h-12 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" stroke-width="1" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
        </svg>
        <p class="text-sm text-gray-500 mb-1">No SERP competitor data yet</p>
        <p class="text-xs text-gray-400">Run a Serper SERP sweep from the Settings page to discover which domains compete for your keywords.</p>
      </div>
    </template>
  </div>
</template>
