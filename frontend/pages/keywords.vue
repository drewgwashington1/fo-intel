<script setup lang="ts">
const { get } = useApi()

const subTabs = [
  { key: 'ideas', label: 'Ideas' },
  { key: 'gaps', label: 'Content Gaps' },
] as const

type SubTab = typeof subTabs[number]['key']
const activeTab = ref<SubTab>('ideas')

// Data
const ideas = ref<any[]>([])
const loading = ref(false)
const seedInput = ref('')

// Sorting for ideas
const ideaSortCol = ref('volume')
const ideaSortAsc = ref(false)

function toggleIdeaSort(col: string) {
  if (ideaSortCol.value === col) { ideaSortAsc.value = !ideaSortAsc.value }
  else { ideaSortCol.value = col; ideaSortAsc.value = false }
}

function sortArrow(active: boolean, asc: boolean) {
  if (!active) return ''
  return asc ? '\u2191' : '\u2193'
}

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

// Data loading
async function loadIdeas() {
  loading.value = true
  try {
    const seeds = seedInput.value || undefined
    ideas.value = await get('/dashboard/keywords/ideas', { seeds, limit: 50 })
  } catch { ideas.value = [] }
  loading.value = false
}

onMounted(() => loadIdeas())
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-semibold text-gray-900">Keywords Explorer</h1>
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

    <!-- ===== TAB: Ideas ===== -->
    <template v-if="activeTab === 'ideas'">
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

    <!-- ===== TAB: Content Gaps (placeholder) ===== -->
    <template v-else-if="activeTab === 'gaps'">
      <div class="bg-surface-card rounded-xl border border-surface-border p-12 text-center">
        <svg class="w-12 h-12 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" stroke-width="1" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
        <p class="text-sm font-medium text-gray-900 mb-1">Content Gaps</p>
        <p class="text-xs text-gray-400">Coming soon — this view will surface keywords competitors rank for that you don't.</p>
      </div>
    </template>

    <!-- Loading overlay -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-fo-action"></div>
    </div>
  </div>
</template>
