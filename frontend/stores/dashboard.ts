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

    // Paid (Google Ads API + Transparency Center)
    paidOverview: null as any,
    paidCampaigns: [] as any[],
    paidSearchTerms: [] as any[],
    paidAds: [] as any[],
    paidPages: [] as any[],
    paidTimeline: [] as any[],
    paidAdFormats: [] as any[],

    // AI
    aiOverview: null as any,
    aiPlatforms: [] as any[],
    aiCompetitors: [] as any[],
    aiTopCited: [] as any[],
    aiTimeline: [] as any[],
    aiSovComparison: null as any,

    // Overview
    overviewLoaded: false,

    // Competitor Ads
    compOverview: null as any,
    compByDomain: [] as any[],
    compLongestRunning: [] as any[],
    compNewThisWeek: [] as any[],
    compFormats: [] as any[],

    // Insights
    insights: null as any,
    insightsLoading: false,

    // Creatives
    creativesOverview: null as any,
    creativesPerformance: [] as any[],
    creativesTimeline: [] as any[],
    creativesByCampaign: [] as any[],
    creativesTopHeadlines: [] as any[],
    creativesLoading: false,
  }),

  actions: {
    setPeriod(days: number) {
      this.periodDays = days
    },

    async fetchOrganic(brand: string = 'non-branded') {
      const { get } = useApi()
      const days = this.periodDays
      const brandParam = brand === 'all' ? undefined : brand
      const [overview, timeline, topQueries, topPages, devices] = await Promise.all([
        get('/dashboard/organic/overview', { days, brand: brandParam }),
        get('/dashboard/organic/timeline', { days: Math.max(days, 90) }),
        get('/dashboard/organic/top-queries', { days, brand: brandParam }),
        get('/dashboard/organic/top-pages', { days }),
        get('/dashboard/organic/devices', { days }),
      ])
      this.organicOverview = overview
      this.organicTimeline = timeline
      this.organicTopQueries = topQueries
      this.organicTopPages = topPages
      this.organicDevices = devices
    },

    async fetchPaid() {
      const { get } = useApi()
      const days = this.periodDays
      const [overview, campaigns, searchTerms, ads, pages, timeline, adFormats] = await Promise.all([
        get('/dashboard/paid/overview', { days }),
        get('/dashboard/paid/campaigns', { days }),
        get('/dashboard/paid/search-terms', { days }),
        get('/dashboard/paid/ads'),
        get('/dashboard/paid/pages', { days }),
        get('/dashboard/paid/timeline', { days: Math.max(days, 90) }),
        get('/dashboard/paid/ad-formats'),
      ])
      this.paidOverview = overview
      this.paidCampaigns = campaigns
      this.paidSearchTerms = searchTerms
      this.paidAds = ads
      this.paidPages = pages
      this.paidTimeline = timeline
      this.paidAdFormats = adFormats
    },

    async fetchAI() {
      const { get } = useApi()
      const days = this.periodDays
      const [overview, platforms, competitors, topCited, timeline, sovComparison] =
        await Promise.all([
          get('/dashboard/ai/overview', { days }),
          get('/dashboard/ai/platforms', { days }),
          get('/dashboard/ai/competitors', { days }),
          get('/dashboard/ai/top-cited', { days }),
          get('/dashboard/ai/timeline', { days: 60 }),
          get('/dashboard/ai/sov-comparison', { days }),
        ])
      this.aiOverview = overview
      this.aiPlatforms = platforms
      this.aiCompetitors = competitors
      this.aiTopCited = topCited
      this.aiTimeline = timeline
      this.aiSovComparison = sovComparison
    },

    async fetchCompetitors() {
      const { get } = useApi()
      const [overview, byDomain, longestRunning, newThisWeek, formats] =
        await Promise.all([
          get('/dashboard/competitors/overview'),
          get('/dashboard/competitors/by-domain'),
          get('/dashboard/competitors/longest-running'),
          get('/dashboard/competitors/new-this-week'),
          get('/dashboard/competitors/formats'),
        ])
      this.compOverview = overview
      this.compByDomain = byDomain
      this.compLongestRunning = longestRunning
      this.compNewThisWeek = newThisWeek
      this.compFormats = formats
    },

    async fetchOverview() {
      this.loading = true
      this.error = null
      try {
        await Promise.all([
          this.fetchOrganic(),
          this.fetchPaid(),
          this.fetchAI(),
          this.fetchCompetitors(),
        ])
        this.overviewLoaded = true
      } catch (e: any) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    async fetchInsights() {
      const { get } = useApi()
      this.insightsLoading = true
      try {
        this.insights = await get('/dashboard/insights', { days: this.periodDays })
      } catch (e: any) {
        this.error = e.message
      } finally {
        this.insightsLoading = false
      }
    },

    async fetchCreatives() {
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
      } catch (e: any) {
        this.error = e.message
      } finally {
        this.creativesLoading = false
      }
    },

    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        await Promise.all([
          this.fetchOrganic(),
          this.fetchPaid(),
          this.fetchAI(),
          this.fetchCompetitors(),
        ])
      } catch (e: any) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
  },
})
