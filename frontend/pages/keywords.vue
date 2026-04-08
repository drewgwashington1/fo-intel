<script setup lang="ts">
const store = useDashboardStore()
const { get } = useApi()

const periods = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
  { label: '1Y', days: 365 },
]

const subTabs = [
  { key: 'all', label: 'All Keywords' },
  { key: 'ideas', label: 'Ideas' },
  { key: 'gaps', label: 'Content Gaps' },
] as const

type SubTab = typeof subTabs[number]['key']
const activeTab = ref<SubTab>('all')

// Data
const overview = ref<any>(null)
const keywords = ref<any[]>([])
const ideas = ref<any[]>([])
const gaps = ref<any[]>([])
const loading = ref(false)
const sortBy = ref('volume')
const searchFilter = ref('')
const seedInput = ref('')

// Sorting for gaps and ideas
const gapSortCol = ref('volume')
const gapSortAsc = ref(false)
const ideaSortCol = ref('volume')
const ideaSortAsc = ref(false)

function toggleGapSort(col: string) {
  if (gapSortCol.value === col) { gapSortAsc.value = !gapSortAsc.value }
  else { gapSortCol.value = col; gapSortAsc.value = false }
}

function toggleIdeaSort(col: string) {
  if (ideaSortCol.value === col) { ideaSortAsc.value = !ideaSortAsc.value }
  else { ideaSortCol.value = col; ideaSortAsc.value = false }
}

function sortArrow(active: boolean, asc: boolean) {
  if (!active) return ''
  return asc ? '\u2191' : '\u2193'
}

// Filtered keywords
const filteredKeywords = computed(() => {
  if (!searchFilter.value) return keywords.value
  const q = searchFilter.value.toLowerCase()
  return keywords.value.filter((k: any) => k.keyword?.toLowerCase().includes(q))
})

const filteredGaps = computed(() => {
  let data = gaps.value
  if (searchFilter.value) {
    const q = searchFilter.value.toLowerCase()
    data = data.filter((g: any) => g.keyword?.toLowerCase().includes(q))
  }
  const col = gapSortCol.value
  const asc = gapSortAsc.value
  return [...data].sort((a: any, b: any) => {
    let va = col === 'keyword' ? (a.keyword || '') : (Number(a[col === 'competitors' ? 'competitor_count' : col === 'best_rank' ? 'best_competitor_position' : col]) || 0)
    let vb = col === 'keyword' ? (b.keyword || '') : (Number(b[col === 'competitors' ? 'competitor_count' : col === 'best_rank' ? 'best_competitor_position' : col]) || 0)
    if (typeof va === 'string') return asc ? va.localeCompare(vb as string) : (vb as string).localeCompare(va)
    return asc ? (va as number) - (vb as number) : (vb as number) - (va as number)
  })
})

const sortedIdeas = computed(() => {
  const col = ideaSortCol.value
  const asc = ideaSortAsc.value
  return [...ideas.value].sort((a: any, b: any) => {
    let va = col === 'keyword' ? (a.keyword || '') : (Number(a[col]) || 0)
    let vb = col === 'keyword' ? (b.keyword || '') : (Number(b[col]) || 0)
    if (typeof va === 'string') return asc ? va.localeCompare(vb as string) : (vb as string).localeCompare(va)
    return asc ? (va as number) - (vb as number) : (vb as number) - (va as number)
  })
})

// Helpers
const fmtNum = (n: number) => n?.toLocaleString() ?? '--'
const fmtMoney = (n: number) => n != null ? `$${Number(n).toFixed(2)}` : '--'

function competitionClass(comp: string): string {
  if (comp === 'HIGH') return 'bg-red-100 text-red-600'
  if (comp === 'MEDIUM') return 'bg-amber-100 text-amber-700'
  if (comp === 'LOW') return 'bg-emerald-100 text-emerald-700'
  return 'bg-gray-100 text-gray-500'
}

function positionColor(pos: number): string {
  if (pos == null || pos === 0) return 'text-gray-400'
  if (pos <= 3) return 'text-status-up'
  if (pos <= 10) return 'text-fo-action'
  if (pos <= 20) return 'text-amber'
  return 'text-gray-400'
}

function volumeBar(vol: number): number {
  if (!vol) return 0
  const max = Math.max(...keywords.value.map((k: any) => k.volume || 0), 1)
  return Math.min(100, (vol / max) * 100)
}

// Data loading
async function loadAll(force = false) {
  loading.value = true
  try {
    const days = store.periodDays
    const [ov, kw] = await Promise.all([
      get('/dashboard/keywords/overview', { days }),
      get('/dashboard/keywords/list', { days, limit: 200, sort: sortBy.value }),
    ])
    overview.value = ov
    keywords.value = kw
  } catch { }
  loading.value = false
}

async function loadIdeas() {
  loading.value = true
  try {
    const seeds = seedInput.value || undefined
    ideas.value = await get('/dashboard/keywords/ideas', { seeds, limit: 50 })
  } catch { ideas.value = [] }
  loading.value = false
}

async function loadGaps() {
  loading.value = true
  try {
    gaps.value = await get('/dashboard/keywords/gaps', { days: store.periodDays, limit: 100 })
  } catch { gaps.value = [] }
  loading.value = false
}

async function setPeriod(days: number) {
  store.setPeriod(days)
  await loadAll(true)
  if (activeTab.value === 'gaps') await loadGaps()
}

async function changeSort(col: string) {
  sortBy.value = col
  await loadAll(true)
}

watch(activeTab, (tab) => {
  if (tab === 'ideas' && !ideas.value.length) loadIdeas()
  if (tab === 'gaps' && !gaps.value.length) loadGaps()
})

onMounted(() => loadAll())
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-semibold text-gray-900">Keywords Explorer</h1>
      <div class="flex gap-1 bg-surface-card rounded-lg border border-surface-border p-0.5">
        <button
          v-for="p in periods" :key="p.days"
          @click="setPeriod(p.days)"
          class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors"
          :class="store.periodDays === p.days ? 'bg-fo-action text-white' : 'text-gray-500 hover:text-gray-700'"
        >{{ p.label }}</button>
      </div>
    </div>

    <!-- KPI Cards -->
    <div v-if="overview" class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
        <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Tracked Keywords</p>
        <p class="text-2xl font-bold text-gray-900">{{ fmtNum(overview.total_keywords) }}</p>
      </div>
      <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
        <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Avg Monthly Volume</p>
        <p class="text-2xl font-bold text-gray-900">{{ fmtNum(overview.avg_volume) }}</p>
      </div>
      <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
        <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Low Competition</p>
        <p class="text-2xl font-bold text-status-up">{{ fmtNum(overview.low_competition) }}</p>
      </div>
      <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
        <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Avg CPC</p>
        <p class="text-2xl font-bold text-gray-900">{{ fmtMoney(overview.avg_cpc) }}</p>
      </div>
    </div>

    <!-- Sub-tabs -->
    <div class="flex gap-1 mb-4 bg-surface-card rounded-lg border border-surface-border p-0.5 w-fit">
      <button
        v-for="tab in subTabs" :key="tab.key"
        @click="activeTab = tab.key"
        class="px-4 py-2 text-xs font-medium rounded-md transition-colors"
        :class="activeTab === tab.key ? 'bg-fo-action text-white' : 'text-gray-500 hover:text-gray-700'"
      >{{ tab.label }}</button>
    </div>

    <!-- Search filter -->
    <div class="flex items-center gap-3 mb-4">
      <input
        v-model="searchFilter"
        type="text"
        placeholder="Filter keywords..."
        class="px-3 py-2 text-xs rounded-lg border border-surface-border bg-surface-card focus:outline-none focus:border-fo-action w-64"
      />
      <span v-if="activeTab === 'all'" class="text-xs text-gray-400">{{ filteredKeywords.length }} keywords</span>
      <span v-if="activeTab === 'gaps'" class="text-xs text-gray-400">{{ filteredGaps.length }} gaps</span>
    </div>

    <!-- ===== TAB: All Keywords ===== -->
    <template v-if="activeTab === 'all'">
      <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-surface-border">
                <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Keyword</th>
                <th @click="changeSort('volume')" class="text-right px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer" :class="sortBy === 'volume' ? 'text-fo-action' : 'text-gray-400'">Volume</th>
                <th @click="changeSort('competition')" class="text-center px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer" :class="sortBy === 'competition' ? 'text-fo-action' : 'text-gray-400'">Competition</th>
                <th @click="changeSort('cpc')" class="text-right px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer" :class="sortBy === 'cpc' ? 'text-fo-action' : 'text-gray-400'">CPC Range</th>
                <th @click="changeSort('position')" class="text-center px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer" :class="sortBy === 'position' ? 'text-fo-action' : 'text-gray-400'">Position</th>
                <th @click="changeSort('clicks')" class="text-right px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer" :class="sortBy === 'clicks' ? 'text-fo-action' : 'text-gray-400'">Clicks</th>
                <th @click="changeSort('impressions')" class="text-right px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer" :class="sortBy === 'impressions' ? 'text-fo-action' : 'text-gray-400'">Impressions</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="kw in filteredKeywords" :key="kw.keyword"
                class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
              >
                <td class="px-4 py-3">
                  <p class="text-sm text-gray-900 font-medium">{{ kw.keyword }}</p>
                  <p v-if="kw.top_page" class="text-[10px] text-gray-400 truncate max-w-xs">{{ kw.top_page }}</p>
                </td>
                <td class="px-4 py-3 text-right">
                  <div class="flex items-center justify-end gap-2">
                    <div class="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div class="h-full bg-fo-action rounded-full" :style="{ width: volumeBar(kw.volume) + '%' }"></div>
                    </div>
                    <span class="text-sm font-medium text-gray-900 w-12 text-right">{{ fmtNum(kw.volume) }}</span>
                  </div>
                </td>
                <td class="px-4 py-3 text-center">
                  <span v-if="kw.competition" class="text-[10px] font-semibold px-2 py-0.5 rounded-full" :class="competitionClass(kw.competition)">{{ kw.competition }}</span>
                  <span v-else class="text-xs text-gray-400">--</span>
                </td>
                <td class="px-4 py-3 text-right text-xs text-gray-600">
                  <template v-if="kw.low_cpc || kw.high_cpc">{{ fmtMoney(kw.low_cpc) }} - {{ fmtMoney(kw.high_cpc) }}</template>
                  <template v-else>--</template>
                </td>
                <td class="px-4 py-3 text-center">
                  <span class="text-sm font-bold" :class="positionColor(kw.avg_position)">
                    {{ kw.avg_position ? Math.round(kw.avg_position) : '--' }}
                  </span>
                </td>
                <td class="px-4 py-3 text-right text-sm text-gray-900">{{ fmtNum(kw.clicks) }}</td>
                <td class="px-4 py-3 text-right text-sm text-gray-500">{{ fmtNum(kw.impressions) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!filteredKeywords.length && !loading" class="p-8 text-center">
          <p class="text-sm text-gray-500">No keyword data. Run the Keyword Planner pipeline from Settings.</p>
        </div>
      </div>
    </template>

    <!-- ===== TAB: Ideas ===== -->
    <template v-else-if="activeTab === 'ideas'">
      <div class="flex items-center gap-3 mb-4">
        <input
          v-model="seedInput"
          type="text"
          placeholder="Enter seed keywords (comma-separated) or leave blank for auto"
          class="px-3 py-2 text-xs rounded-lg border border-surface-border bg-surface-card focus:outline-none focus:border-fo-action flex-1"
        />
        <button
          @click="loadIdeas"
          class="px-4 py-2 text-xs font-medium text-white bg-fo-action rounded-lg hover:bg-fo-action/90 transition-colors"
        >Generate Ideas</button>
      </div>

      <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-surface-border">
                <th @click="toggleIdeaSort('keyword')" class="text-left px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none" :class="ideaSortCol === 'keyword' ? 'text-fo-action' : 'text-gray-400'">Suggested Keyword {{ sortArrow(ideaSortCol === 'keyword', ideaSortAsc) }}</th>
                <th @click="toggleIdeaSort('volume')" class="text-right px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none" :class="ideaSortCol === 'volume' ? 'text-fo-action' : 'text-gray-400'">Volume {{ sortArrow(ideaSortCol === 'volume', ideaSortAsc) }}</th>
                <th @click="toggleIdeaSort('competition')" class="text-center px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none" :class="ideaSortCol === 'competition' ? 'text-fo-action' : 'text-gray-400'">Competition {{ sortArrow(ideaSortCol === 'competition', ideaSortAsc) }}</th>
                <th @click="toggleIdeaSort('high_cpc')" class="text-right px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none" :class="ideaSortCol === 'high_cpc' ? 'text-fo-action' : 'text-gray-400'">CPC Range {{ sortArrow(ideaSortCol === 'high_cpc', ideaSortAsc) }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="idea in sortedIdeas" :key="idea.keyword"
                class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
              >
                <td class="px-4 py-3">
                  <p class="text-sm text-gray-900 font-medium">{{ idea.keyword }}</p>
                  <p v-if="idea.seed_keyword" class="text-[10px] text-gray-400">seed: {{ idea.seed_keyword }}</p>
                </td>
                <td class="px-4 py-3 text-right text-sm font-medium text-gray-900">{{ fmtNum(idea.volume) }}</td>
                <td class="px-4 py-3 text-center">
                  <span v-if="idea.competition" class="text-[10px] font-semibold px-2 py-0.5 rounded-full" :class="competitionClass(idea.competition)">{{ idea.competition }}</span>
                  <span v-else class="text-xs text-gray-400">--</span>
                </td>
                <td class="px-4 py-3 text-right text-xs text-gray-600">
                  <template v-if="idea.low_cpc || idea.high_cpc">{{ fmtMoney(idea.low_cpc) }} - {{ fmtMoney(idea.high_cpc) }}</template>
                  <template v-else>--</template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!ideas.length && !loading" class="p-8 text-center">
          <p class="text-sm text-gray-500">Click "Generate Ideas" to get keyword suggestions from Google Keyword Planner.</p>
        </div>
      </div>
    </template>

    <!-- ===== TAB: Content Gaps ===== -->
    <template v-else-if="activeTab === 'gaps'">
      <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-surface-border">
                <th @click="toggleGapSort('keyword')" class="text-left px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none" :class="gapSortCol === 'keyword' ? 'text-fo-action' : 'text-gray-400'">Keyword {{ sortArrow(gapSortCol === 'keyword', gapSortAsc) }}</th>
                <th @click="toggleGapSort('volume')" class="text-right px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none" :class="gapSortCol === 'volume' ? 'text-fo-action' : 'text-gray-400'">Volume {{ sortArrow(gapSortCol === 'volume', gapSortAsc) }}</th>
                <th @click="toggleGapSort('competition')" class="text-center px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none" :class="gapSortCol === 'competition' ? 'text-fo-action' : 'text-gray-400'">Competition {{ sortArrow(gapSortCol === 'competition', gapSortAsc) }}</th>
                <th @click="toggleGapSort('cpc')" class="text-right px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none" :class="gapSortCol === 'cpc' ? 'text-fo-action' : 'text-gray-400'">CPC {{ sortArrow(gapSortCol === 'cpc', gapSortAsc) }}</th>
                <th @click="toggleGapSort('competitors')" class="text-center px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none" :class="gapSortCol === 'competitors' ? 'text-fo-action' : 'text-gray-400'">Competitors {{ sortArrow(gapSortCol === 'competitors', gapSortAsc) }}</th>
                <th @click="toggleGapSort('best_rank')" class="text-center px-4 py-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none" :class="gapSortCol === 'best_rank' ? 'text-fo-action' : 'text-gray-400'">Best Rank {{ sortArrow(gapSortCol === 'best_rank', gapSortAsc) }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="gap in filteredGaps" :key="gap.keyword"
                class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
              >
                <td class="px-4 py-3">
                  <p class="text-sm text-gray-900 font-medium">{{ gap.keyword }}</p>
                  <p class="text-[10px] text-gray-400 truncate max-w-xs">{{ gap.competitor_domains?.join(', ') }}</p>
                </td>
                <td class="px-4 py-3 text-right text-sm font-medium text-gray-900">{{ gap.volume ? fmtNum(gap.volume) : '--' }}</td>
                <td class="px-4 py-3 text-center">
                  <span v-if="gap.competition" class="text-[10px] font-semibold px-2 py-0.5 rounded-full" :class="competitionClass(gap.competition)">{{ gap.competition }}</span>
                  <span v-else class="text-xs text-gray-400">--</span>
                </td>
                <td class="px-4 py-3 text-right text-xs text-gray-600">{{ gap.cpc ? fmtMoney(gap.cpc) : '--' }}</td>
                <td class="px-4 py-3 text-center">
                  <span class="text-sm font-bold text-fo-action">{{ gap.competitor_count }}</span>
                </td>
                <td class="px-4 py-3 text-center">
                  <span class="text-sm font-bold" :class="positionColor(gap.best_competitor_position)">
                    #{{ gap.best_competitor_position }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!filteredGaps.length && !loading" class="p-8 text-center">
          <p class="text-sm text-gray-500">No content gaps found. Run a Serper sweep to discover competitor rankings, then run Keyword Planner for volume data.</p>
        </div>
      </div>
    </template>

    <!-- Loading overlay -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-fo-action"></div>
    </div>
  </div>
</template>
