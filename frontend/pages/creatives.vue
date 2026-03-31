<script setup lang="ts">
const store = useDashboardStore()

const periodOptions = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
]
const selectedPeriod = ref(periodOptions[1])

const tabs = ['FO Creatives', 'By Campaign', 'Top Headlines', 'Competitor Ads']
const activeTab = ref('FO Creatives')

async function loadCreatives() {
  store.setPeriod(selectedPeriod.value.days)
  await Promise.all([store.fetchCreatives(), store.fetchCompetitors()])
}
async function setPeriod(opt: typeof periodOptions[0]) {
  selectedPeriod.value = opt
  await loadCreatives()
}
onMounted(() => loadCreatives())

const fmtNum = (n: number) => n?.toLocaleString() ?? '--'
const fmtPct = (n: number) => n != null ? `${(n * 100).toFixed(1)}%` : '--'
const fmtDollar = (n: number) => n != null ? `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '--'

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

function ctrColor(ctr: number): string {
  if (ctr >= 0.08) return 'text-status-up'
  if (ctr >= 0.04) return 'text-amber'
  return 'text-status-down'
}

function convColor(rate: number): string {
  if (rate >= 0.10) return 'text-status-up'
  if (rate >= 0.05) return 'text-amber'
  return 'text-gray-700'
}

// Compute average CTR and conv rate across all creatives for performance comparison
const avgCtr = computed(() => {
  const ads = store.creativesPerformance
  if (!ads?.length) return 0
  const totalClicks = ads.reduce((s: number, a: any) => s + (a.clicks || 0), 0)
  const totalImpr = ads.reduce((s: number, a: any) => s + (a.impressions || 0), 0)
  return totalImpr > 0 ? totalClicks / totalImpr : 0
})
const avgConvRate = computed(() => {
  const ads = store.creativesPerformance
  if (!ads?.length) return 0
  const totalConv = ads.reduce((s: number, a: any) => s + (a.conversions || 0), 0)
  const totalClicks = ads.reduce((s: number, a: any) => s + (a.clicks || 0), 0)
  return totalClicks > 0 ? totalConv / totalClicks : 0
})

function performanceSignal(ad: any): { label: string; class: string } {
  const ctr = ad.ctr || 0
  const conv = ad.conv_rate || 0
  const ctrRatio = avgCtr.value > 0 ? ctr / avgCtr.value : 1
  const convRatio = avgConvRate.value > 0 ? conv / avgConvRate.value : 1

  if (ctrRatio >= 1.3 && convRatio >= 1.2) return { label: 'Strong', class: 'bg-status-up/15 text-status-up' }
  if (ctrRatio >= 1.1 || convRatio >= 1.1) return { label: 'Good', class: 'bg-fo-action/15 text-fo-action' }
  if (ctrRatio < 0.7 || convRatio < 0.5) return { label: 'Needs Work', class: 'bg-status-down/15 text-status-down' }
  return { label: 'Average', class: 'bg-gray-100 text-gray-500' }
}

function adIdentifier(ad: any): string {
  if (ad.ad_group_name) return ad.ad_group_name
  if (ad.headline_1) return ad.headline_1
  return `Ad #${ad.ad_id}`
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-gray-900">Ad Creative Performance</h1>
        <p class="text-sm text-gray-400 mt-1">FO ad creative metrics from Google Ads + competitor ad monitoring</p>
      </div>
      <div class="flex items-center gap-3">
        <!-- Period -->
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
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 bg-surface-card rounded-lg p-1 border border-surface-border mb-6 w-fit">
      <button
        v-for="tab in tabs"
        :key="tab"
        class="px-4 py-1.5 rounded-md text-xs font-medium transition-colors"
        :class="activeTab === tab ? 'bg-fo-action text-white' : 'text-gray-500 hover:text-gray-900'"
        @click="activeTab = tab"
      >{{ tab }}</button>
    </div>

    <!-- Loading -->
    <div v-if="store.creativesLoading" class="space-y-4">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="h-24 bg-surface-card rounded-xl border border-surface-border animate-pulse" />
      </div>
      <div class="h-64 bg-surface-card rounded-xl border border-surface-border animate-pulse" />
    </div>

    <template v-else>
      <!-- KPI Cards -->
      <div v-if="store.creativesOverview" class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Active Creatives</p>
          <p class="text-2xl font-bold text-gray-900">{{ store.creativesOverview.total_creatives }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Total Clicks</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(store.creativesOverview.total_clicks) }}</p>
          <p v-if="store.creativesOverview.prev_clicks" class="text-xs mt-0.5"
            :class="deltaClass(delta(store.creativesOverview.total_clicks, store.creativesOverview.prev_clicks))">
            {{ deltaArrow(delta(store.creativesOverview.total_clicks, store.creativesOverview.prev_clicks)) }}
            {{ Math.abs(delta(store.creativesOverview.total_clicks, store.creativesOverview.prev_clicks).pct).toFixed(1) }}%
          </p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Avg Click Rate</p>
          <p class="text-2xl font-bold" :class="ctrColor(store.creativesOverview.avg_ctr)">{{ fmtPct(store.creativesOverview.avg_ctr) }}</p>
        </div>
        <div class="bg-surface-card rounded-xl p-4 border border-surface-border">
          <p class="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Conversions</p>
          <p class="text-2xl font-bold text-gray-900">{{ fmtNum(Math.round(store.creativesOverview.total_conversions)) }}</p>
        </div>
      </div>

      <!-- Tab: FO Creatives -->
      <div v-if="activeTab === 'FO Creatives'">
        <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
          <div class="px-5 py-3 border-b border-surface-border">
            <h3 class="text-sm font-semibold text-gray-900">Ad Creative Performance</h3>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-surface-border">
                  <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Ad / Campaign</th>
                  <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Type</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Clicks</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Click Rate</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Conversions</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Conv Rate</th>
                  <th class="text-center px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Performance</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(ad, i) in store.creativesPerformance"
                  :key="ad.ad_id"
                  class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                >
                  <td class="px-4 py-3">
                    <div class="max-w-sm">
                      <p class="text-sm font-medium text-gray-900 truncate">{{ adIdentifier(ad) }}</p>
                      <p class="text-xs text-gray-500 truncate mt-0.5">{{ ad.campaign_name }}</p>
                      <p class="text-[10px] text-gray-400 mt-0.5">ID: {{ ad.ad_id }}</p>
                    </div>
                  </td>
                  <td class="px-4 py-3">
                    <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">{{ ad.campaign_type || ad.ad_type }}</span>
                  </td>
                  <td class="px-4 py-3 text-right font-medium text-gray-900">{{ fmtNum(ad.clicks) }}</td>
                  <td class="px-4 py-3 text-right font-medium" :class="ctrColor(ad.ctr)">{{ fmtPct(ad.ctr) }}</td>
                  <td class="px-4 py-3 text-right font-medium text-gray-900">{{ Math.round(ad.conversions || 0) }}</td>
                  <td class="px-4 py-3 text-right" :class="convColor(ad.conv_rate)">{{ fmtPct(ad.conv_rate) }}</td>
                  <td class="px-4 py-3 text-center">
                    <span class="text-[10px] font-semibold px-2 py-1 rounded-full" :class="performanceSignal(ad).class">
                      {{ performanceSignal(ad).label }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="!store.creativesPerformance?.length" class="p-8 text-center">
            <p class="text-sm text-gray-500">No creative performance data. Run the Ad Creatives pipeline first.</p>
          </div>
        </div>
      </div>

      <!-- Tab: By Campaign -->
      <div v-if="activeTab === 'By Campaign'">
        <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
          <div class="px-5 py-3 border-b border-surface-border">
            <h3 class="text-sm font-semibold text-gray-900">Creative Performance by Campaign</h3>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-surface-border">
                  <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Campaign</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Creatives</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Clicks</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Click Rate</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Conversions</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Conv Rate</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="c in store.creativesByCampaign"
                  :key="c.campaign_name"
                  class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                >
                  <td class="px-4 py-3 font-medium text-gray-900">{{ c.campaign_name }}</td>
                  <td class="px-4 py-3 text-right text-gray-700">{{ c.creatives }}</td>
                  <td class="px-4 py-3 text-right font-medium text-gray-900">{{ fmtNum(c.clicks) }}</td>
                  <td class="px-4 py-3 text-right" :class="ctrColor(c.ctr)">{{ fmtPct(c.ctr) }}</td>
                  <td class="px-4 py-3 text-right font-medium text-gray-900">{{ Math.round(c.conversions || 0) }}</td>
                  <td class="px-4 py-3 text-right" :class="convColor(c.conv_rate)">{{ fmtPct(c.conv_rate) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Tab: Top Headlines -->
      <div v-if="activeTab === 'Top Headlines'">
        <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
          <div class="px-5 py-3 border-b border-surface-border">
            <h3 class="text-sm font-semibold text-gray-900">Headline Performance Ranking</h3>
            <p class="text-xs text-gray-400 mt-0.5">Which headlines drive the most clicks and conversions</p>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-surface-border">
                  <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium w-8">#</th>
                  <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Headline</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Ads</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Impr</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Clicks</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">CTR</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Conv</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Conv Rate</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(h, i) in store.creativesTopHeadlines"
                  :key="h.headline_1"
                  class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                >
                  <td class="px-4 py-3 text-gray-400 text-xs">{{ i + 1 }}</td>
                  <td class="px-4 py-3 font-medium text-gray-900">{{ h.headline_1 }}</td>
                  <td class="px-4 py-3 text-right text-gray-500">{{ h.used_in_ads }}</td>
                  <td class="px-4 py-3 text-right text-gray-700">{{ fmtNum(h.impressions) }}</td>
                  <td class="px-4 py-3 text-right font-medium text-gray-900">{{ fmtNum(h.clicks) }}</td>
                  <td class="px-4 py-3 text-right" :class="ctrColor(h.ctr)">{{ fmtPct(h.ctr) }}</td>
                  <td class="px-4 py-3 text-right font-medium text-gray-900">{{ h.conversions?.toFixed(1) }}</td>
                  <td class="px-4 py-3 text-right" :class="convColor(h.conv_rate)">{{ fmtPct(h.conv_rate) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Tab: Competitor Ads -->
      <div v-if="activeTab === 'Competitor Ads'">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <!-- Active ads by domain -->
          <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
            <div class="px-5 py-3 border-b border-surface-border">
              <h3 class="text-sm font-semibold text-gray-900">Active Ads by Competitor</h3>
            </div>
            <div class="p-4 space-y-3">
              <div
                v-for="d in store.compByDomain"
                :key="d.competitor_domain"
                class="flex items-center justify-between"
              >
                <div>
                  <p class="text-sm font-medium text-gray-900">{{ d.competitor_domain }}</p>
                  <p class="text-xs text-gray-400">{{ d.advertiser_name }}</p>
                </div>
                <div class="flex items-center gap-3">
                  <span class="text-sm font-semibold text-gray-900">{{ d.active_ads }}</span>
                  <span class="text-xs text-gray-400">/ {{ d.total_ads }} total</span>
                </div>
              </div>
            </div>
          </div>

          <!-- New this week -->
          <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
            <div class="px-5 py-3 border-b border-surface-border">
              <h3 class="text-sm font-semibold text-gray-900">New Ads This Week</h3>
            </div>
            <div class="divide-y divide-surface-border">
              <div
                v-for="ad in store.compNewThisWeek?.slice(0, 8)"
                :key="ad.headline + ad.competitor_domain"
                class="px-4 py-3"
              >
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-xs font-medium text-fo-action">{{ ad.competitor_domain }}</span>
                  <span class="text-[10px] text-gray-400">{{ ad.ad_format }}</span>
                </div>
                <p class="text-sm text-gray-900">{{ ad.headline }}</p>
                <p class="text-xs text-gray-500 mt-0.5 line-clamp-1">{{ ad.description }}</p>
              </div>
              <div v-if="!store.compNewThisWeek?.length" class="p-4 text-center text-sm text-gray-400">
                No new competitor ads this week
              </div>
            </div>
          </div>
        </div>

        <!-- Longest running -->
        <div class="bg-surface-card rounded-xl border border-surface-border overflow-hidden">
          <div class="px-5 py-3 border-b border-surface-border">
            <h3 class="text-sm font-semibold text-gray-900">Longest-Running Competitor Ads</h3>
            <p class="text-xs text-gray-400 mt-0.5">Ads active 60+ days — likely strong performers</p>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-surface-border">
                  <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Competitor</th>
                  <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Headline</th>
                  <th class="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Format</th>
                  <th class="text-right px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400 font-medium">Days</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="ad in store.compLongestRunning?.slice(0, 10)"
                  :key="ad.headline + ad.competitor_domain"
                  class="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors"
                >
                  <td class="px-4 py-3 text-sm text-fo-action">{{ ad.competitor_domain }}</td>
                  <td class="px-4 py-3">
                    <p class="text-sm text-gray-900 truncate max-w-md">{{ ad.headline }}</p>
                  </td>
                  <td class="px-4 py-3 text-xs text-gray-500">{{ ad.ad_format }}</td>
                  <td class="px-4 py-3 text-right font-semibold text-gray-900">{{ ad.days_running }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
