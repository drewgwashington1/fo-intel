import { defineStore } from 'pinia'

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    periodDays: 30,
    loading: false,
    error: null as string | null,

    // Organic
    organicOverview: null as any,
    organicTimeline: [] as any[],
    organicTopQueries: [] as any[],
    organicTopPages: [] as any[],
    organicDevices: [] as any[],
    organicLoaded: false,

    // Overview
    overviewLoaded: false,

    // Insights
    insights: null as any,
    insightsLoading: false,
    insightsLoaded: false,

  }),

  actions: {
    setPeriod(days: number) {
      if (days !== this.periodDays) {
        this.periodDays = days
        // Period changed — invalidate all caches
        this.organicLoaded = false
        this.overviewLoaded = false
        this.insightsLoaded = false
      }
    },

    async fetchOrganic(brand: string = 'all', tag: string = 'all', force = false) {
      if (this.organicLoaded && !force) return
      const { get } = useApi()
      const days = this.periodDays
      const brandParam = brand === 'all' ? undefined : brand
      const tagParam = tag === 'all' ? undefined : tag
      const params = { days, brand: brandParam, tag: tagParam }
      const results = await Promise.allSettled([
        get('/dashboard/organic/overview', params),
        get('/dashboard/organic/timeline', { days: Math.max(days, 90) }),
        get('/dashboard/organic/top-queries', { ...params, limit: 25 }),
        get('/dashboard/organic/top-pages', params),
        get('/dashboard/organic/devices', params),
      ])
      const val = (r: PromiseSettledResult<any>) => r.status === 'fulfilled' ? r.value : null
      if (val(results[0])) this.organicOverview = val(results[0])
      if (val(results[1])) this.organicTimeline = val(results[1])
      if (val(results[2])) this.organicTopQueries = val(results[2])
      if (val(results[3])) this.organicTopPages = val(results[3])
      if (val(results[4])) this.organicDevices = val(results[4])
      this.organicLoaded = true
    },

    async fetchOverview(force = false) {
      if (this.overviewLoaded && !force) return
      this.loading = true
      this.error = null
      try {
        await this.fetchOrganic('all', 'all', force)
        this.overviewLoaded = true
      } catch (e: any) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    async fetchInsights(force = false) {
      if (this.insightsLoaded && !force) return
      const { get } = useApi()
      this.insightsLoading = true
      try {
        this.insights = await get('/dashboard/insights', { days: this.periodDays })
        this.insightsLoaded = true
      } catch (e: any) {
        this.error = e.message
      } finally {
        this.insightsLoading = false
      }
    },

    async fetchAll(force = false) {
      this.loading = true
      this.error = null
      try {
        await this.fetchOrganic('all', 'all', force)
      } catch (e: any) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
  },
})
