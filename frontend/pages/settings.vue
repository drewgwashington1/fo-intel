<script setup lang="ts">
const { get, post, del } = useApi()

// ── Pipeline Status ──
const pipelines = ref<any[]>([])
const pipelineRunning = ref<Record<string, boolean>>({})
const pipelineResult = ref<Record<string, string>>({})

async function loadPipelines() {
  pipelines.value = await get('/dashboard/pipeline-status')
}

async function runPipeline(name: string, endpoint: string) {
  pipelineRunning.value[name] = true
  pipelineResult.value[name] = ''
  try {
    const res = await post(endpoint)
    pipelineResult.value[name] = `Done — ${res.rows_ingested ?? res.rows ?? 0} rows`
    await loadPipelines()
  } catch (e: any) {
    pipelineResult.value[name] = `Failed: ${e.message}`
  } finally {
    pipelineRunning.value[name] = false
    setTimeout(() => { pipelineResult.value[name] = '' }, 5000)
  }
}

async function runSerperSweep() {
  pipelineRunning.value['serper'] = true
  pipelineResult.value['serper'] = ''
  try {
    const res = await post('/ingest/serper-sweep')
    pipelineResult.value['serper'] = `${res.keywords_queried ?? 0} keywords queried, ${res.paid_ads_found ?? 0} ads found, ${res.credits_remaining ?? '?'} credits left`
    await loadPipelines()
  } catch (e: any) {
    pipelineResult.value['serper'] = `Failed: ${e.message}`
  } finally {
    pipelineRunning.value['serper'] = false
    setTimeout(() => { pipelineResult.value['serper'] = '' }, 8000)
  }
}

async function backfillSerpOrganics() {
  pipelineRunning.value['backfill'] = true
  pipelineResult.value['backfill'] = ''
  try {
    const res = await get('/dashboard/organic/competitors/backfill')
    pipelineResult.value['backfill'] = `Backfilled ${res.backfilled ?? 0} organic SERP results`
  } catch (e: any) {
    pipelineResult.value['backfill'] = `Failed: ${e.message}`
  } finally {
    pipelineRunning.value['backfill'] = false
    setTimeout(() => { pipelineResult.value['backfill'] = '' }, 5000)
  }
}

// ── Tracked Competitors ──
const competitors = ref<any[]>([])
const newCompDomain = ref('')

async function loadCompetitors() {
  competitors.value = await get('/dashboard/tracked-competitors')
}

async function addCompetitor() {
  const domain = newCompDomain.value.trim().toLowerCase()
  if (!domain) return
  await post(`/dashboard/tracked-competitors?domain=${encodeURIComponent(domain)}`)
  newCompDomain.value = ''
  await loadCompetitors()
}

async function removeCompetitor(domain: string) {
  await del('/dashboard/tracked-competitors', { domain })
  await loadCompetitors()
}

// ── User Management ──
const users = ref<any[]>([])
const newUserEmail = ref('')
const newUserPassword = ref('')
const newUserRole = ref('viewer')
const changingPassword = ref<Record<number, boolean>>({})
const newPasswords = ref<Record<number, string>>({})

async function loadUsers() {
  try {
    users.value = await get('/auth/users')
  } catch {}
}

async function addUser() {
  const email = newUserEmail.value.trim()
  const password = newUserPassword.value
  if (!email || !password) return
  try {
    await post('/auth/users', { email, password, role: newUserRole.value })
    newUserEmail.value = ''
    newUserPassword.value = ''
    newUserRole.value = 'viewer'
    await loadUsers()
  } catch (e: any) {
    alert(e.message)
  }
}

async function deleteUser(id: number) {
  if (!confirm('Remove this user?')) return
  try {
    await del(`/auth/users/${id}`)
    await loadUsers()
  } catch (e: any) {
    alert(e.message)
  }
}

async function changePassword(id: number) {
  const pw = newPasswords.value[id]
  if (!pw) return
  try {
    const { patch } = useApi()
    await patch(`/auth/users/${id}/password`, { password: pw })
    newPasswords.value[id] = ''
    changingPassword.value[id] = false
  } catch (e: any) {
    alert(e.message)
  }
}

// ── Cache Management ──
const cacheClearing = ref(false)

async function clearCache() {
  cacheClearing.value = true
  try {
    await post('/ingest/refresh')
  } catch {}
  cacheClearing.value = false
}

onMounted(() => {
  loadPipelines()
  loadCompetitors()
  loadUsers()
})

const pipelineConfig = [
  { name: 'gsc', label: 'GSC Organic', endpoint: '/ingest/gsc?days=30', description: 'Google Search Console — organic impressions, clicks, CTR, position', schedule: 'Daily 3:00 AM CT' },
  { name: 'ads', label: 'Google Ads', endpoint: '/ingest/ads?days=30', description: 'Google Ads API — paid performance, spend, CPC, impression share', schedule: 'Daily 3:30 AM CT' },
  { name: 'profound', label: 'AI Visibility', endpoint: '/ingest/profound?days=30', description: 'Profound API — AI engine share of voice, citations, benchmarks', schedule: 'Daily 4:00 AM CT' },
  { name: 'transparency', label: 'Competitor Ads', endpoint: '/ingest/transparency', description: 'Google Ads Transparency Center — competitor ad creatives', schedule: 'Weekly Sunday 6:00 AM CT' },
]

function fmtDate(d: string) {
  if (!d) return 'Never'
  return new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function pipelineStatus(name: string) {
  return pipelines.value.find((p: any) => p.pipeline_name === name)
}
</script>

<template>
  <div>
    <h1 class="text-xl font-semibold text-gray-900 mb-6">Settings</h1>

    <!-- Data Pipelines -->
    <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
      <div class="px-5 py-4 border-b border-surface-border">
        <h2 class="text-sm font-semibold text-gray-900">Data Pipelines</h2>
        <p class="text-xs text-gray-400 mt-0.5">Manually trigger data ingestion pipelines</p>
      </div>
      <div class="divide-y divide-surface-border">
        <div v-for="p in pipelineConfig" :key="p.name" class="px-5 py-4 flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-gray-900">{{ p.label }}</p>
            <p class="text-xs text-gray-400 mt-0.5">{{ p.description }}</p>
            <div class="flex items-center gap-3 mt-1">
              <span class="text-[10px] text-gray-400">Schedule: {{ p.schedule }}</span>
              <span v-if="pipelineStatus(p.name)" class="text-[10px] text-gray-400">
                Last run: {{ fmtDate(pipelineStatus(p.name)?.last_run_at) }}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <span v-if="pipelineResult[p.name]" class="text-xs" :class="pipelineResult[p.name]?.startsWith('Failed') ? 'text-status-down' : 'text-status-up'">
              {{ pipelineResult[p.name] }}
            </span>
            <button
              class="px-4 py-2 rounded-lg text-xs font-medium bg-fo-action text-white hover:bg-fo-blue transition-colors disabled:opacity-50"
              :disabled="pipelineRunning[p.name]"
              @click="runPipeline(p.name, p.endpoint)"
            >
              <span v-if="pipelineRunning[p.name]">Running...</span>
              <span v-else>Run Now</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- SERP Analysis -->
    <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
      <div class="px-5 py-4 border-b border-surface-border">
        <h2 class="text-sm font-semibold text-gray-900">SERP Competitor Analysis</h2>
        <p class="text-xs text-gray-400 mt-0.5">Query Google SERPs via Serper.dev to discover competitor organic rankings</p>
      </div>
      <div class="px-5 py-4 space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-gray-900">Run Serper Sweep</p>
            <p class="text-xs text-gray-400 mt-0.5">Queries your top GSC keywords against Google SERPs to find who else ranks for them. Uses 1 credit per keyword (2,500 total).</p>
          </div>
          <div class="flex items-center gap-3">
            <span v-if="pipelineResult['serper']" class="text-xs text-status-up max-w-[300px] text-right">{{ pipelineResult['serper'] }}</span>
            <button
              class="px-4 py-2 rounded-lg text-xs font-medium bg-fo-action text-white hover:bg-fo-blue transition-colors disabled:opacity-50"
              :disabled="pipelineRunning['serper']"
              @click="runSerperSweep"
            >
              <span v-if="pipelineRunning['serper']">Sweeping...</span>
              <span v-else>Run Sweep</span>
            </button>
          </div>
        </div>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-gray-900">Backfill Organic Results</p>
            <p class="text-xs text-gray-400 mt-0.5">Extract organic rankings from existing SERP cache. Run once after enabling organic competitor tracking.</p>
          </div>
          <div class="flex items-center gap-3">
            <span v-if="pipelineResult['backfill']" class="text-xs text-status-up">{{ pipelineResult['backfill'] }}</span>
            <button
              class="px-4 py-2 rounded-lg text-xs font-medium bg-surface border border-surface-border text-gray-700 hover:bg-gray-100 transition-colors disabled:opacity-50"
              :disabled="pipelineRunning['backfill']"
              @click="backfillSerpOrganics"
            >
              <span v-if="pipelineRunning['backfill']">Backfilling...</span>
              <span v-else>Backfill</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Tracked Competitors -->
    <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
      <div class="px-5 py-4 border-b border-surface-border">
        <h2 class="text-sm font-semibold text-gray-900">Tracked Competitors</h2>
        <p class="text-xs text-gray-400 mt-0.5">Domains to prioritize in competitor analysis across all pages</p>
      </div>
      <div class="px-5 py-4">
        <div class="space-y-2 mb-4">
          <div v-for="c in competitors" :key="c.domain" class="flex items-center justify-between py-2 px-3 rounded-lg bg-surface">
            <div>
              <span class="text-sm text-gray-900 font-medium">{{ c.domain }}</span>
              <span v-if="c.display_name && c.display_name !== c.domain" class="text-xs text-gray-400 ml-2">{{ c.display_name }}</span>
            </div>
            <button
              class="text-gray-400 hover:text-status-down transition-colors p-1"
              @click="removeCompetitor(c.domain)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div v-if="!competitors.length" class="text-xs text-gray-400 py-2">No competitors tracked yet.</div>
        </div>
        <div class="flex items-center gap-2">
          <input
            v-model="newCompDomain"
            type="text"
            placeholder="Add domain (e.g. competitor.com)"
            class="flex-1 px-3 py-2 text-sm rounded-lg border border-surface-border bg-surface focus:outline-none focus:border-fo-action"
            @keydown.enter="addCompetitor"
          />
          <button
            class="px-4 py-2 rounded-lg text-xs font-medium bg-fo-action text-white hover:bg-fo-blue transition-colors"
            @click="addCompetitor"
          >Add</button>
        </div>
      </div>
    </div>

    <!-- User Management -->
    <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
      <div class="px-5 py-4 border-b border-surface-border">
        <h2 class="text-sm font-semibold text-gray-900">User Management</h2>
        <p class="text-xs text-gray-400 mt-0.5">Manage who can access this dashboard</p>
      </div>
      <div class="px-5 py-4">
        <div class="space-y-2 mb-4">
          <div v-for="u in users" :key="u.id" class="flex items-center justify-between py-2.5 px-3 rounded-lg bg-surface">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-full bg-fo-action/15 flex items-center justify-center">
                <span class="text-fo-action text-xs font-semibold">{{ u.email.charAt(0).toUpperCase() }}</span>
              </div>
              <div>
                <span class="text-sm text-gray-900 font-medium">{{ u.email }}</span>
                <span class="text-[10px] uppercase tracking-wider text-gray-400 ml-2 px-1.5 py-0.5 rounded bg-gray-100">{{ u.role }}</span>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <template v-if="changingPassword[u.id]">
                <input
                  v-model="newPasswords[u.id]"
                  type="password"
                  placeholder="New password"
                  class="w-40 px-2 py-1.5 text-xs rounded-lg border border-surface-border bg-surface focus:outline-none focus:border-fo-action"
                  @keydown.enter="changePassword(u.id)"
                />
                <button
                  class="text-xs text-fo-action hover:underline"
                  @click="changePassword(u.id)"
                >Save</button>
                <button
                  class="text-xs text-gray-400 hover:text-gray-600"
                  @click="changingPassword[u.id] = false; newPasswords[u.id] = ''"
                >Cancel</button>
              </template>
              <template v-else>
                <button
                  class="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                  @click="changingPassword[u.id] = true"
                >Change password</button>
                <button
                  class="text-gray-400 hover:text-status-down transition-colors p-1"
                  @click="deleteUser(u.id)"
                  title="Remove user"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </template>
            </div>
          </div>
          <div v-if="!users.length" class="text-xs text-gray-400 py-2">No users configured.</div>
        </div>
        <!-- Add user form -->
        <div class="flex items-center gap-2 pt-2 border-t border-surface-border">
          <input
            v-model="newUserEmail"
            type="email"
            placeholder="Email"
            class="flex-1 px-3 py-2 text-sm rounded-lg border border-surface-border bg-surface focus:outline-none focus:border-fo-action"
          />
          <input
            v-model="newUserPassword"
            type="password"
            placeholder="Password"
            class="w-40 px-3 py-2 text-sm rounded-lg border border-surface-border bg-surface focus:outline-none focus:border-fo-action"
          />
          <select
            v-model="newUserRole"
            class="px-3 py-2 text-sm rounded-lg border border-surface-border bg-surface focus:outline-none focus:border-fo-action"
          >
            <option value="viewer">Viewer</option>
            <option value="admin">Admin</option>
          </select>
          <button
            class="px-4 py-2 rounded-lg text-xs font-medium bg-fo-action text-white hover:bg-fo-blue transition-colors"
            @click="addUser"
          >Add User</button>
        </div>
      </div>
    </div>

    <!-- Cache Management -->
    <div class="bg-surface-card rounded-xl border border-surface-border mb-6">
      <div class="px-5 py-4 border-b border-surface-border">
        <h2 class="text-sm font-semibold text-gray-900">Cache Management</h2>
        <p class="text-xs text-gray-400 mt-0.5">Force rebuild all dashboard summaries from raw data</p>
      </div>
      <div class="px-5 py-4 flex items-center justify-between">
        <p class="text-sm text-gray-700">Clear summary cache and rebuild all dashboard data</p>
        <button
          class="px-4 py-2 rounded-lg text-xs font-medium bg-surface border border-surface-border text-gray-700 hover:bg-gray-100 transition-colors disabled:opacity-50"
          :disabled="cacheClearing"
          @click="clearCache"
        >
          <span v-if="cacheClearing">Rebuilding...</span>
          <span v-else>Rebuild Cache</span>
        </button>
      </div>
    </div>
  </div>
</template>
