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
const activeCategory = ref<'all' | 'branded' | 'non-branded'>('all')
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
  await patch(`/dashboard/keywords/${keywordId}/category?category=${newCat}`)
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

// ── Organic Competitors computeds ────────────────────────────────
const activeCompetitors = computed(() => organicCompetitors.value.filter((c: any) => !c.is_self))

const compTotalShared = computed(() => {
  const seen = new Set<string>()
  let total = 0
  for (const c of activeCompetitors.value) {
    total += c.common_keywords || 0
  }
  return total
})

const compAvgYourPos = computed(() => {
  const withData = activeCompetitors.value.filter((c: any) => c.fo_avg_position > 0)
  if (!withData.length) return 0
  return withData.reduce((sum: number, c: any) => sum + c.fo_avg_position, 0) / withData.length
})

const compOverallWinRate = computed(() => {
  const totalWins = activeCompetitors.value.reduce((s: number, c: any) => s + (c.fo_wins || 0), 0)
  const totalLosses = activeCompetitors.value.reduce((s: number, c: any) => s + (c.competitor_wins || 0), 0)
  const total = totalWins + totalLosses
  return total > 0 ? Math.round((totalWins / total) * 100) : 0
})

function compWinPct(comp: any) {
  const total = (comp.fo_wins || 0) + (comp.competitor_wins || 0)
  return total > 0 ? Math.round((comp.fo_wins / total) * 100) : 50
}

// Per-competitor keyword expansion
const expandedCompetitors = ref<Record<string, boolean>>({})
const compKeywords = ref<Record<string, any[]>>({})
const compKeywordsLoading = ref<Record<string, boolean>>({})

async function toggleCompExpand(domain: string) {
  expandedCompetitors.value[domain] = !expandedCompetitors.value[domain]
  // Load keywords on first expand
  if (expandedCompetitors.value[domain] && !compKeywords.value[domain]) {
    compKeywordsLoading.value[domain] = true
    try {
      compKeywords.value[domain] = await get('/dashboard/organic/competitors/keywords', { domain, days: 90 })
    } catch { compKeywords.value[domain] = [] }
    compKeywordsLoading.value[domain] = false
  }
}

// ── Top Pages expand + views ─────────────────────────────────────
const pageViews = [
  { key: 'all', label: 'All Pages' },
  { key: 'growing', label: 'Growing' },
  { key: 'declining', label: 'Declining' },
  { key: 'opportunities', label: 'Opportunities' },
] as const
const pageView = ref<string>('all')
const expandedPages = ref<Record<string, boolean>>({})
const pageKeywords = ref<Record<string, any[]>>({})
const pageKeywordsLoading = ref<Record<string, boolean>>({})

const growingPages = computed(() =>
  (store.organicTopPages || []).filter((p: any) => p.prev_clicks != null && p.clicks > p.prev_clicks).length
)
const opportunityPages = computed(() =>
  (store.organicTopPages || []).filter((p: any) => (p.keywords || 0) >= 5 && (p.clicks || 0) < 10).length
)

const filteredSortedPages = computed(() => {
  let data = sortedPages.value
  if (pageView.value === 'growing') {
    data = data.filter((p: any) => p.prev_clicks != null && p.clicks > p.prev_clicks)
  } else if (pageView.value === 'declining') {
    data = data.filter((p: any) => p.prev_clicks != null && p.clicks < p.prev_clicks)
  } else if (pageView.value === 'opportunities') {
    data = data.filter((p: any) => (p.keywords || 0) >= 5 && (p.clicks || 0) < 10)
  }
  return data
})

async function togglePageExpand(page: string) {
  expandedPages.value[page] = !expandedPages.value[page]
  if (expandedPages.value[page] && !pageKeywords.value[page]) {
    pageKeywordsLoading.value[page] = true
    try {
      const brandParam = activeCategory.value === 'all' ? undefined : activeCategory.value
      const tagParam = activeTag.value === 'all' ? undefined : activeTag.value
      pageKeywords.value[page] = await get('/dashboard/organic/page-keywords', {
        page, days: store.periodDays, brand: brandParam, tag: tagParam
      })
    } catch { pageKeywords.value[page] = [] }
    pageKeywordsLoading.value[page] = false
  }
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


// ── Sorting ────────────────────────────────────────────────────
const querySortCol = ref('clicks')
const querySortAsc = ref(false)
const pageSortCol = ref('clicks')
const pageSortAsc = ref(false)

function toggleQuerySort(col: string) {
  if (querySortCol.value === col) {
    querySortAsc.value = !querySortAsc.value
  } else {
    querySortCol.value = col
    querySortAsc.value = col === 'position' // position defaults ascending
  }
}

function togglePageSort(col: string) {
  if (pageSortCol.value === col) {
    pageSortAsc.value = !pageSortAsc.value
  } else {
    pageSortCol.value = col
    pageSortAsc.value = col === 'position' // position defaults ascending
  }
}

const sortedQueries = computed(() => {
  const data = [...(store.organicTopQueries || [])]
  const col = querySortCol.value
  const asc = querySortAsc.value
  data.sort((a: any, b: any) => {
    let va = col === 'query' ? (a.query || '') : (Number(a[col === 'traffic' ? 'clicks' : col === 'change' ? 'clicks' : col]) || 0)
    let vb = col === 'query' ? (b.query || '') : (Number(b[col === 'traffic' ? 'clicks' : col === 'change' ? 'clicks' : col]) || 0)
    if (col === 'change') {
      va = (a.clicks || 0) - (a.prev_clicks || 0)
      vb = (b.clicks || 0) - (b.prev_clicks || 0)
    }
    if (col === 'position') {
      va = a.avg_position || 999
      vb = b.avg_position || 999
    }
    if (typeof va === 'string') return asc ? va.localeCompare(vb as string) : (vb as string).localeCompare(va)
    return asc ? (va as number) - (vb as number) : (vb as number) - (va as number)
  })
  return data
})

const sortedPages = computed(() => {
  const data = [...(store.organicTopPages || [])]
  const col = pageSortCol.value
  const asc = pageSortAsc.value
  data.sort((a: any, b: any) => {
    let va: any, vb: any
    if (col === 'url') { va = a.page || ''; vb = b.page || '' }
    else if (col === 'position') { va = a.avg_position || 999; vb = b.avg_position || 999 }
    else if (col === 'change') { va = (a.clicks || 0) - (a.prev_clicks || 0); vb = (b.clicks || 0) - (b.prev_clicks || 0) }
    else { va = Number(a[col]) || 0; vb = Number(b[col]) || 0 }
    if (typeof va === 'string') return asc ? va.localeCompare(vb) : vb.localeCompare(va)
    return asc ? va - vb : vb - va
  })
  return data
})

function sortIcon(active: boolean, asc: boolean) {
  if (!active) return ''
  return asc ? '\u2191' : '\u2193'
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
              <tr class="text-[10px] uppercase tracking-wider border-b border-surface-border">
                <th class="text-left px-5 py-3 w-8 text-gray-400" title="Row number">#</th>
                <th @click="toggleQuerySort('query')" class="text-left px-5 py-3 cursor-pointer select-none" :class="querySortCol === 'query' ? 'text-fo-action' : 'text-gray-400'" title="Search query">Keyword {{ sortIcon(querySortCol === 'query', querySortAsc) }}</th>
                <th class="text-center px-5 py-3 text-gray-400" title="Branded or non-branded classification">Category</th>
                <th class="text-center px-5 py-3 text-gray-400" title="Keyword tag group">Tag</th>
                <th @click="toggleQuerySort('impressions')" class="text-right px-5 py-3 cursor-pointer select-none" :class="querySortCol === 'impressions' ? 'text-fo-action' : 'text-gray-400'" title="Estimated monthly search volume">Volume {{ sortIcon(querySortCol === 'impressions', querySortAsc) }}</th>
                <th class="text-center px-5 py-3 w-20 text-gray-400" title="Keyword difficulty">KD</th>
                <th @click="toggleQuerySort('clicks')" class="text-right px-5 py-3 cursor-pointer select-none" :class="querySortCol === 'clicks' ? 'text-fo-action' : 'text-gray-400'" title="Number of clicks">Traffic {{ sortIcon(querySortCol === 'clicks', querySortAsc) }}</th>
                <th @click="toggleQuerySort('change')" class="text-right px-5 py-3 cursor-pointer select-none" :class="querySortCol === 'change' ? 'text-fo-action' : 'text-gray-400'" title="Click change">Change {{ sortIcon(querySortCol === 'change', querySortAsc) }}</th>
                <th @click="toggleQuerySort('position')" class="text-right px-5 py-3 cursor-pointer select-none" :class="querySortCol === 'position' ? 'text-fo-action' : 'text-gray-400'" title="Average ranking position">Position {{ sortIcon(querySortCol === 'position', querySortAsc) }}</th>
                <th class="text-right px-5 py-3 text-gray-400" title="Position change compared to previous period">Pos Change</th>
                <th class="text-left px-5 py-3 text-gray-400" title="Landing page URL">URL</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(q, i) in sortedQueries"
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
              v-for="kw in movements.details?.[activeMovementTab]?.slice(0, 15)"
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
      <!-- Summary KPIs -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Pages Ranking</p>
          <p class="text-2xl font-bold text-gray-900">{{ totalPages }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Total Traffic</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(totalPageTraffic) }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Growing Pages</p>
          <p class="text-2xl font-bold text-status-up">{{ growingPages }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Opportunities</p>
          <p class="text-2xl font-bold text-fo-action">{{ opportunityPages }}</p>
          <p class="text-[10px] text-gray-400 mt-0.5">5+ keywords, low clicks</p>
        </div>
      </div>

      <!-- View toggle -->
      <div class="flex items-center gap-2 mb-4">
        <button
          v-for="v in pageViews" :key="v.key"
          @click="pageView = v.key"
          class="px-3 py-1.5 text-[10px] font-medium rounded-md transition-colors"
          :class="pageView === v.key ? 'bg-fo-action text-white' : 'text-gray-500 hover:text-gray-700 bg-surface-card border border-surface-border'"
        >{{ v.label }}</button>
      </div>

      <!-- Pages table with expandable rows -->
      <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-[10px] uppercase tracking-wider border-b border-surface-border">
                <th class="w-8 px-3 py-3"></th>
                <th @click="togglePageSort('url')" class="text-left px-4 py-3 cursor-pointer select-none" :class="pageSortCol === 'url' ? 'text-fo-action' : 'text-gray-400'">Page {{ sortIcon(pageSortCol === 'url', pageSortAsc) }}</th>
                <th @click="togglePageSort('clicks')" class="text-right px-4 py-3 cursor-pointer select-none" :class="pageSortCol === 'clicks' ? 'text-fo-action' : 'text-gray-400'">Traffic {{ sortIcon(pageSortCol === 'clicks', pageSortAsc) }}</th>
                <th @click="togglePageSort('change')" class="text-right px-4 py-3 cursor-pointer select-none" :class="pageSortCol === 'change' ? 'text-fo-action' : 'text-gray-400'">Change {{ sortIcon(pageSortCol === 'change', pageSortAsc) }}</th>
                <th @click="togglePageSort('keywords')" class="text-right px-4 py-3 cursor-pointer select-none" :class="pageSortCol === 'keywords' ? 'text-fo-action' : 'text-gray-400'">Keywords {{ sortIcon(pageSortCol === 'keywords', pageSortAsc) }}</th>
                <th @click="togglePageSort('position')" class="text-right px-4 py-3 cursor-pointer select-none" :class="pageSortCol === 'position' ? 'text-fo-action' : 'text-gray-400'">Position {{ sortIcon(pageSortCol === 'position', pageSortAsc) }}</th>
                <th @click="togglePageSort('ctr')" class="text-right px-4 py-3 cursor-pointer select-none" :class="pageSortCol === 'ctr' ? 'text-fo-action' : 'text-gray-400'">CTR {{ sortIcon(pageSortCol === 'ctr', pageSortAsc) }}</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(p, i) in filteredSortedPages" :key="p.page">
                <!-- Page row -->
                <tr
                  class="border-b border-surface-border hover:bg-surface-hover transition-colors cursor-pointer"
                  @click="togglePageExpand(p.page)"
                >
                  <td class="px-3 py-3 text-center">
                    <svg
                      class="w-3.5 h-3.5 text-gray-400 transition-transform inline-block"
                      :class="expandedPages[p.page] ? 'rotate-180' : ''"
                      fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                    </svg>
                  </td>
                  <td class="px-4 py-3" :title="p.page">
                    <a
                      :href="p.page"
                      target="_blank"
                      @click.stop
                      class="text-fo-action font-medium text-xs hover:underline truncate block max-w-[400px]"
                    >{{ truncateUrl(p.page) }}</a>
                  </td>
                  <td class="px-4 py-3 text-right text-gray-900 font-medium text-xs">{{ fmtNum(p.clicks) }}</td>
                  <td class="px-4 py-3 text-right">
                    <span
                      v-if="p.prev_clicks != null && p.prev_clicks > 0"
                      class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold"
                      :class="p.clicks >= p.prev_clicks ? 'bg-status-up/15 text-status-up' : 'bg-status-down/15 text-status-down'"
                    >
                      {{ p.clicks > p.prev_clicks ? '\u2191' : p.clicks < p.prev_clicks ? '\u2193' : '\u2192' }}
                      {{ p.clicks >= p.prev_clicks ? '+' : '' }}{{ ((p.clicks - p.prev_clicks) / p.prev_clicks * 100).toFixed(0) }}%
                    </span>
                    <span v-else class="text-[10px] text-gray-400">new</span>
                  </td>
                  <td class="px-4 py-3 text-right text-xs text-gray-700">{{ p.keywords ?? '—' }}</td>
                  <td class="px-4 py-3 text-right">
                    <span
                      class="inline-flex items-center justify-center px-2 py-0.5 rounded text-xs font-semibold"
                      :class="[positionColor(p.avg_position), positionBgColor(p.avg_position)]"
                    >{{ fmtPos(p.avg_position) }}</span>
                  </td>
                  <td class="px-4 py-3 text-right text-xs text-gray-700">{{ fmtPct(p.ctr) }}</td>
                </tr>

                <!-- Expanded keyword detail -->
                <tr v-if="expandedPages[p.page]" class="bg-gray-50/50">
                  <td colspan="7" class="px-0 py-0">
                    <!-- Loading -->
                    <div v-if="pageKeywordsLoading[p.page]" class="flex justify-center py-6">
                      <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-fo-action"></div>
                    </div>

                    <!-- Keyword sub-table -->
                    <div v-else-if="pageKeywords[p.page]?.length" class="px-8 py-3">
                      <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-2">Keywords driving this page</p>
                      <table class="w-full text-xs">
                        <thead>
                          <tr class="text-[10px] uppercase tracking-wider text-gray-400 border-b border-surface-border">
                            <th class="text-left py-2 pr-4">Keyword</th>
                            <th class="text-right py-2 px-3">Clicks</th>
                            <th class="text-right py-2 px-3">Change</th>
                            <th class="text-right py-2 px-3">Impressions</th>
                            <th class="text-right py-2 px-3">Position</th>
                            <th class="text-right py-2 pl-3">CTR</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr
                            v-for="kw in pageKeywords[p.page]"
                            :key="kw.keyword"
                            class="border-b border-surface-border/50 last:border-0"
                          >
                            <td class="py-2 pr-4 text-gray-900 font-medium">{{ kw.keyword }}</td>
                            <td class="py-2 px-3 text-right text-gray-900">{{ fmtNum(kw.clicks) }}</td>
                            <td class="py-2 px-3 text-right">
                              <span
                                v-if="kw.prev_clicks != null"
                                class="text-[10px] font-semibold"
                                :class="kw.clicks > kw.prev_clicks ? 'text-status-up' : kw.clicks < kw.prev_clicks ? 'text-status-down' : 'text-gray-400'"
                              >
                                {{ kw.clicks > kw.prev_clicks ? '\u2191' : kw.clicks < kw.prev_clicks ? '\u2193' : '\u2192' }}
                                {{ kw.prev_clicks > 0 ? ((kw.clicks - kw.prev_clicks) / kw.prev_clicks * 100).toFixed(0) + '%' : 'new' }}
                              </span>
                              <span v-else class="text-gray-400">—</span>
                            </td>
                            <td class="py-2 px-3 text-right text-gray-500">{{ fmtNum(kw.impressions) }}</td>
                            <td class="py-2 px-3 text-right">
                              <span class="font-semibold" :class="positionColor(kw.position)">{{ kw.position || '—' }}</span>
                              <span
                                v-if="kw.prev_position != null && kw.prev_position > 0"
                                class="ml-1 text-[10px]"
                                :class="kw.position < kw.prev_position ? 'text-status-up' : kw.position > kw.prev_position ? 'text-status-down' : 'text-gray-400'"
                              >{{ kw.position < kw.prev_position ? '\u2191' : kw.position > kw.prev_position ? '\u2193' : '' }}{{ kw.position !== kw.prev_position ? Math.abs(kw.position - kw.prev_position) : '' }}</span>
                            </td>
                            <td class="py-2 pl-3 text-right text-gray-500">{{ fmtPct(kw.ctr) }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    <!-- No keywords -->
                    <div v-else class="px-8 py-4">
                      <p class="text-xs text-gray-400">No keyword data for this page.</p>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ============================================ -->
    <!-- TAB 3: Organic Competitors -->
    <!-- ============================================ -->
    <template v-else-if="activeTab === 'competitors'">
      <template v-if="activeCompetitors.length">
        <!-- Summary row -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
            <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Competitors Tracked</p>
            <p class="text-2xl font-bold text-gray-900">{{ activeCompetitors.length }}</p>
          </div>
          <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
            <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Total Shared Keywords</p>
            <p class="text-2xl font-bold text-gray-900">{{ fmtNum(compTotalShared) }}</p>
          </div>
          <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
            <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Your Avg Position</p>
            <p class="text-2xl font-bold" :class="positionColor(compAvgYourPos)">{{ fmtPos(compAvgYourPos) }}</p>
          </div>
          <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
            <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Overall Win Rate</p>
            <p class="text-2xl font-bold" :class="compOverallWinRate >= 50 ? 'text-status-up' : 'text-status-down'">{{ compOverallWinRate }}%</p>
          </div>
        </div>

        <!-- Per-competitor cards -->
        <div class="space-y-4">
          <div
            v-for="comp in activeCompetitors"
            :key="comp.domain"
            class="bg-surface-card rounded-xl border border-surface-border overflow-hidden"
          >
            <!-- Card header — clickable to expand -->
            <button
              @click="toggleCompExpand(comp.domain)"
              class="w-full px-5 py-4 flex items-center justify-between hover:bg-surface-hover transition-colors"
            >
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center">
                  <span class="text-xs font-bold text-gray-500 uppercase">{{ comp.domain.charAt(0) }}</span>
                </div>
                <div class="text-left">
                  <h3 class="text-sm font-semibold text-gray-900">{{ comp.domain }}</h3>
                  <p class="text-[10px] text-gray-400">{{ comp.common_keywords }} shared keywords</p>
                </div>
              </div>
              <div class="flex items-center gap-4">
                <!-- Quick stats inline -->
                <div v-if="comp.common_keywords > 0" class="hidden sm:flex items-center gap-4">
                  <div class="text-right">
                    <p class="text-[10px] text-gray-400">You</p>
                    <span class="text-sm font-bold" :class="positionColor(comp.fo_avg_position)">{{ fmtPos(comp.fo_avg_position) }}</span>
                  </div>
                  <span class="text-gray-300 text-xs">vs</span>
                  <div class="text-left">
                    <p class="text-[10px] text-gray-400">Them</p>
                    <span class="text-sm font-bold" :class="positionColor(comp.avg_position)">{{ fmtPos(comp.avg_position) }}</span>
                  </div>
                  <div class="flex items-center h-2 rounded-full overflow-hidden w-16 bg-gray-100 ml-2">
                    <div class="h-full bg-fo-action" :style="{ width: compWinPct(comp) + '%' }" />
                    <div class="h-full bg-gray-400" :style="{ width: (100 - compWinPct(comp)) + '%' }" />
                  </div>
                  <span class="text-[10px] font-semibold" :class="comp.fo_wins >= comp.competitor_wins ? 'text-status-up' : 'text-status-down'">
                    {{ comp.fo_wins }}-{{ comp.competitor_wins }}
                  </span>
                </div>
                <!-- Expand chevron -->
                <svg
                  class="w-4 h-4 text-gray-400 transition-transform"
                  :class="expandedCompetitors[comp.domain] ? 'rotate-180' : ''"
                  fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                </svg>
              </div>
            </button>

            <!-- Expanded keyword table -->
            <div v-if="expandedCompetitors[comp.domain]" class="border-t border-surface-border">
              <!-- Loading state -->
              <div v-if="compKeywordsLoading[comp.domain]" class="flex justify-center py-8">
                <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-fo-action"></div>
              </div>

              <!-- Keyword table -->
              <div v-else-if="compKeywords[comp.domain]?.length" class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="text-[10px] uppercase tracking-wider text-gray-400 border-b border-surface-border">
                      <th class="text-left px-5 py-3">Keyword</th>
                      <th class="text-center px-4 py-3">Your Pos</th>
                      <th class="text-center px-4 py-3">Their Pos</th>
                      <th class="text-center px-4 py-3">Winner</th>
                      <th class="text-right px-4 py-3">Clicks</th>
                      <th class="text-right px-5 py-3">Impressions</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="kw in compKeywords[comp.domain]"
                      :key="kw.keyword"
                      class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                    >
                      <td class="px-5 py-2.5">
                        <span class="text-xs text-gray-900 font-medium">{{ kw.keyword }}</span>
                      </td>
                      <td class="px-4 py-2.5 text-center">
                        <span
                          class="inline-flex items-center justify-center px-2 py-0.5 rounded text-xs font-semibold"
                          :class="[positionColor(kw.your_position), positionBgColor(kw.your_position)]"
                        >{{ kw.your_position || '--' }}</span>
                      </td>
                      <td class="px-4 py-2.5 text-center">
                        <span
                          class="inline-flex items-center justify-center px-2 py-0.5 rounded text-xs font-semibold"
                          :class="[positionColor(kw.their_position), positionBgColor(kw.their_position)]"
                        >{{ kw.their_position || '--' }}</span>
                      </td>
                      <td class="px-4 py-2.5 text-center">
                        <span
                          class="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                          :class="kw.winner === 'you' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-50 text-red-500'"
                        >{{ kw.winner === 'you' ? 'You' : 'Them' }}</span>
                      </td>
                      <td class="px-4 py-2.5 text-right text-xs text-gray-900">{{ fmtNum(kw.clicks) }}</td>
                      <td class="px-5 py-2.5 text-right text-xs text-gray-500">{{ fmtNum(kw.impressions) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- No keywords -->
              <div v-else class="p-6 text-center">
                <p class="text-xs text-gray-400">No shared keyword data yet. Run a Serper sweep to discover overlap.</p>
              </div>
            </div>
          </div>
        </div>
      </template>

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
