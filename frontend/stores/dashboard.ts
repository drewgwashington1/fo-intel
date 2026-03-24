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

    // Paid
    paidOverview: null as any,
    paidCampaigns: [] as any[],
    paidSearchTerms: [] as any[],
    paidTimeline: [] as any[],

    // AI
    aiOverview: null as any,
    aiPlatforms: [] as any[],
    aiCompetitors: [] as any[],
    aiTopCited: [] as any[],
    aiTimeline: [] as any[],
    aiSovComparison: null as any,

    // Competitor Ads
    compOverview: null as any,
    compByDomain: [] as any[],
    compLongestRunning: [] as any[],
    compNewThisWeek: [] as any[],
    compFormats: [] as any[],
  }),

  actions: {
    setPeriod(days: number) {
      this.periodDays = days
    },

    async fetchOrganic() {
      const { get } = useApi()
      const days = this.periodDays
      const [overview, timeline, topQueries, topPages, devices] = await Promise.all([
        get('/dashboard/organic/overview', { days }),
        get('/dashboard/organic/timeline', { days: Math.max(days, 90) }),
        get('/dashboard/organic/top-queries', { days }),
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
      const [overview, campaigns, searchTerms, timeline] = await Promise.all([
        get('/dashboard/paid/overview', { days }),
        get('/dashboard/paid/campaigns', { days }),
        get('/dashboard/paid/search-terms', { days }),
        get('/dashboard/paid/timeline', { days: Math.max(days, 90) }),
      ])
      this.paidOverview = overview
      this.paidCampaigns = campaigns
      this.paidSearchTerms = searchTerms
      this.paidTimeline = timeline
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
