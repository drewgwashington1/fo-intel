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

    // Paid (Google Ads API + Transparency Center)
    paidOverview: null as any,
    paidCampaigns: [] as any[],
    paidSearchTerms: [] as any[],
    paidAds: [] as any[],
    paidPages: [] as any[],
    paidTimeline: [] as any[],
    paidAdFormats: [] as any[],
    paidLoaded: false,

    // AI
    aiOverview: null as any,
    aiPlatforms: [] as any[],
    aiCompetitors: [] as any[],
    aiTopCited: [] as any[],
    aiTimeline: [] as any[],
    aiSovComparison: null as any,
    aiLoaded: false,

    // Overview
    overviewLoaded: false,

    // Competitor Ads
    compOverview: null as any,
    compByDomain: [] as any[],
    compLongestRunning: [] as any[],
    compNewThisWeek: [] as any[],
    compFormats: [] as any[],
    compLoaded: false,

    // Insights
    insights: null as any,
    insightsLoading: false,
    insightsLoaded: false,

    // Creatives
    creativesOverview: null as any,
    creativesPerformance: [] as any[],
    creativesTimeline: [] as any[],
    creativesByCampaign: [] as any[],
    creativesTopHeadlines: [] as any[],
    creativesLoading: false,
    creativesLoaded: false,
  }),

  actions: {
    setPeriod(days: number) {
      if (days !== this.periodDays) {
        this.periodDays = days
        // Period changed — invalidate all caches
        this.organicLoaded = false
        this.paidLoaded = false
        this.aiLoaded = false
        this.compLoaded = false
        this.overviewLoaded = false
        this.insightsLoaded = false
        this.creativesLoaded = false
      }
    },

    async fetchOrganic(brand: string = 'non-branded', tag: string = 'all', force = false) {
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

    async fetchPaid(force = false) {
      if (this.paidLoaded && !force) return
      const { get } = useApi()
      const days = this.periodDays
      const results = await Promise.allSettled([
        get('/dashboard/paid/overview', { days }),
        get('/dashboard/paid/campaigns', { days }),
        get('/dashboard/paid/search-terms', { days }),
        get('/dashboard/paid/ads'),
        get('/dashboard/paid/pages', { days }),
        get('/dashboard/paid/timeline', { days: Math.max(days, 90) }),
        get('/dashboard/paid/ad-formats'),
      ])
      const val = (r: PromiseSettledResult<any>) => r.status === 'fulfilled' ? r.value : null
      if (val(results[0])) this.paidOverview = val(results[0])
      if (val(results[1])) this.paidCampaigns = val(results[1])
      if (val(results[2])) this.paidSearchTerms = val(results[2])
      if (val(results[3])) this.paidAds = val(results[3])
      if (val(results[4])) this.paidPages = val(results[4])
      if (val(results[5])) this.paidTimeline = val(results[5])
      if (val(results[6])) this.paidAdFormats = val(results[6])
      this.paidLoaded = true
    },

    async fetchAI(force = false) {
      if (this.aiLoaded && !force) return
      const { get } = useApi()
      const days = this.periodDays
      const results = await Promise.allSettled([
        get('/dashboard/ai/overview', { days }),
        get('/dashboard/ai/platforms', { days }),
        get('/dashboard/ai/competitors', { days }),
        get('/dashboard/ai/top-cited', { days }),
        get('/dashboard/ai/timeline', { days: 60 }),
        get('/dashboard/ai/sov-comparison', { days }),
      ])
      const val = (r: PromiseSettledResult<any>) => r.status === 'fulfilled' ? r.value : null
      if (val(results[0])) this.aiOverview = val(results[0])
      if (val(results[1])) this.aiPlatforms = val(results[1])
      if (val(results[2])) this.aiCompetitors = val(results[2])
      if (val(results[3])) this.aiTopCited = val(results[3])
      if (val(results[4])) this.aiTimeline = val(results[4])
      if (val(results[5])) this.aiSovComparison = val(results[5])
      this.aiLoaded = true
    },

    async fetchCompetitors(force = false) {
      if (this.compLoaded && !force) return
      const { get } = useApi()
      const results = await Promise.allSettled([
        get('/dashboard/competitors/overview'),
        get('/dashboard/competitors/by-domain'),
        get('/dashboard/competitors/longest-running'),
        get('/dashboard/competitors/new-this-week'),
        get('/dashboard/competitors/formats'),
      ])
      const val = (r: PromiseSettledResult<any>) => r.status === 'fulfilled' ? r.value : null
      if (val(results[0])) this.compOverview = val(results[0])
      if (val(results[1])) this.compByDomain = val(results[1])
      if (val(results[2])) this.compLongestRunning = val(results[2])
      if (val(results[3])) this.compNewThisWeek = val(results[3])
      if (val(results[4])) this.compFormats = val(results[4])
      this.compLoaded = true
    },

    async fetchOverview(force = false) {
      if (this.overviewLoaded && !force) return
      this.loading = true
      this.error = null
      try {
        await Promise.allSettled([
          this.fetchOrganic('non-branded', force),
          this.fetchPaid(force),
          this.fetchAI(force),
          this.fetchCompetitors(force),
        ])
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

    async fetchCreatives(force = false) {
      if (this.creativesLoaded && !force) return
      const { get } = useApi()
      const days = this.periodDays
      this.creativesLoading = true
      try {
        const [overview, performance, timeline, byCampaign, topHeadlines] = await Promise.all([
          get('/dashboard/creatives/overview', { days }),
          get('/dashboard/creatives/performance', { days }),
          get('/dashboard/creatives/timeline', { days: Math.max(days, 30) }),
          get('/dashboard/creatives/by-campaign', { days }),
          get('/dashboard/creatives/top-headlines', { days }),
        ])
        this.creativesOverview = overview
        this.creativesPerformance = performance
        this.creativesTimeline = timeline
        this.creativesByCampaign = byCampaign
        this.creativesTopHeadlines = topHeadlines
        this.creativesLoaded = true
      } catch (e: any) {
        this.error = e.message
      } finally {
        this.creativesLoading = false
      }
    },

    async fetchAll(force = false) {
      this.loading = true
      this.error = null
      try {
        await Promise.allSettled([
          this.fetchOrganic('non-branded', force),
          this.fetchPaid(force),
          this.fetchAI(force),
          this.fetchCompetitors(force),
        ])
      } catch (e: any) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
  },
})
