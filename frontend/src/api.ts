export type JsonRecord = Record<string, unknown>

export type ApiErrorContext = {
  endpoint: string
  status?: number
  method: string
  run_id?: string
  module_id?: string
  source_id?: string
  evidence_id?: string
}

export class ApiClientError extends Error {
  context: ApiErrorContext
  payload: unknown

  constructor(message: string, context: ApiErrorContext, payload: unknown = null) {
    super(message)
    this.name = 'ApiClientError'
    this.context = context
    this.payload = payload
  }
}

export type AuditReport = {
  phase: string
  title: string
  filename: string
  path: string
  relative_path: string
  file_url: string
  size_bytes: number
  updated_at: number
}

export type AuditReports = {
  status: string
  count: number
  reports: AuditReport[]
}

export type P45Dashboard = JsonRecord & {
  status: string
  final_view?: string
  final_view_cn?: string
  legacy_core_view?: string
  decision_card?: JsonRecord
  btc_trend_cockpit?: JsonRecord
  btc_timescale_judge?: JsonRecord
  aggregation_audit?: JsonRecord
  horizon_views?: Record<string, JsonRecord>
  contract_validation?: JsonRecord
  data_quality?: JsonRecord
  radar_module_count?: number
  metric_evidence_count?: number
  radar_modules?: JsonRecord[]
  run_lineage?: JsonRecord
  llm?: JsonRecord
  audit_reports?: AuditReports
}

export type P45Overview = JsonRecord & {
  status: string
  final_view?: string
  final_view_cn?: string
  decision_card?: JsonRecord
  btc_trend_cockpit?: JsonRecord
  btc_timescale_judge?: JsonRecord
  aggregation_audit?: JsonRecord
  horizon_views?: Record<string, JsonRecord>
  run_lineage?: JsonRecord
}

export type P45RadarModules = JsonRecord & {
  status: string
  count?: number
  modules?: JsonRecord[]
  radar_modules?: JsonRecord[]
}

export type P45Articles = JsonRecord & {
  status: string
  final_view?: string
  research_article?: JsonRecord
  publish_article?: JsonRecord
  llm_research?: JsonRecord
  analyst_articles?: JsonRecord[]
  llm_analyst_articles?: JsonRecord[]
}

export type P45ArticleHistory = JsonRecord & {
  status: string
  count?: number
  items?: JsonRecord[]
}

export type P45Invalidation = JsonRecord & {
  status: string
  final_view?: string
  validation_state?: string
  validation_reason?: string
  current_thesis?: JsonRecord
  scores?: JsonRecord
  btc_response?: JsonRecord
  module_evidence_matrix?: JsonRecord[]
  rule_groups?: JsonRecord
  triggered_rules?: JsonRecord[]
  armed_rules?: JsonRecord[]
  blocked_rules?: JsonRecord[]
  timeline?: JsonRecord[]
  invalidation_rules: JsonRecord[]
  confirmation_rules: JsonRecord[]
}

export type P45Evidence = JsonRecord & {
  status: string
  count?: number
  items?: JsonRecord[]
}

export type P45Runs = JsonRecord & {
  status: string
  latest?: JsonRecord
  stages?: JsonRecord[]
  audit_reports?: AuditReports
}

export type P45RunJob = JsonRecord & {
  status: string
  job_run_id?: string
  current_stage?: string
  execution_profile?: string
  decision_ready?: boolean
  deterministic_ready_at?: string
  llm_enabled?: boolean
  llm_status?: string
  run_lineage?: JsonRecord
  stages?: JsonRecord[]
  result?: JsonRecord
}

export type P45Settings = JsonRecord & {
  status: string
  app?: JsonRecord
  run_defaults?: JsonRecord
  llm?: JsonRecord
}

export type EventWindowPayload = JsonRecord & {
  status: string
  event_window?: JsonRecord
  active_event?: JsonRecord
  state?: JsonRecord
  overlay?: JsonRecord
  daemon?: JsonRecord
  items?: JsonRecord[]
  count?: number
}

export type RadarRuntimePayload = JsonRecord & {
  status: string
  daemon?: JsonRecord
  runtime?: JsonRecord
  modules?: JsonRecord[]
  count?: number
}

function queryString(params: Record<string, string | number | boolean | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  return search.size ? `?${search}` : ''
}

function extractErrorMessage(payload: unknown, fallback: string) {
  if (payload && typeof payload === 'object') {
    const record = payload as JsonRecord
    const error = record.error as JsonRecord | undefined
    return String(error?.message ?? record.message ?? record.detail ?? fallback)
  }
  return fallback
}

async function parseJsonResponse<T>(
  response: Response,
  context: ApiErrorContext,
): Promise<T> {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiClientError(
      extractErrorMessage(payload, `Failed to load ${context.endpoint}`),
      { ...context, status: response.status },
      payload,
    )
  }
  return payload as T
}

async function requestJson<T>(
  method: string,
  endpoint: string,
  context: Partial<ApiErrorContext> = {},
  body?: unknown,
): Promise<T> {
  const response = await fetch(endpoint, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return parseJsonResponse<T>(response, { endpoint, method, ...context })
}

async function getJson<T>(endpoint: string, context: Partial<ApiErrorContext> = {}): Promise<T> {
  return requestJson<T>('GET', endpoint, context)
}

async function postJson<T>(endpoint: string, context: Partial<ApiErrorContext> = {}): Promise<T> {
  return requestJson<T>('POST', endpoint, context)
}

async function postJsonBody<T>(
  endpoint: string,
  body: unknown,
  context: Partial<ApiErrorContext> = {},
): Promise<T> {
  return requestJson<T>('POST', endpoint, context, body)
}

export const api = {
  getP45DashboardLatest: () => getJson<P45Dashboard>('/api/p45/dashboard/latest'),
  getP45OverviewLatest: () => getJson<P45Overview>('/api/p45/overview/latest'),
  getP45RadarModulesLatest: () => getJson<P45RadarModules>('/api/p45/radar-modules/latest'),
  getP45RadarModule: (moduleId: string) =>
    getJson<JsonRecord>(`/api/p45/radar-modules/${encodeURIComponent(moduleId)}`, {
      module_id: moduleId,
    }),
  getP45Evidence: (params: { module_id?: string; metric_id?: string; limit?: number } = {}) => {
    return getJson<P45Evidence>(
      `/api/p45/evidence${queryString(params)}`,
      params.module_id ? { module_id: params.module_id } : {},
    )
  },
  getP45EvidenceItem: (
    evidenceId: string,
    params: { final_run_id?: string; pack_id?: string; allow_stale_fallback?: boolean } = {},
  ) =>
    getJson<JsonRecord>(
      `/api/p45/evidence/${encodeURIComponent(evidenceId)}${queryString({
        final_run_id: params.final_run_id,
        pack_id: params.pack_id,
        allow_stale_fallback: params.allow_stale_fallback ? 'true' : undefined,
      })}`,
      {
        evidence_id: evidenceId,
      },
    ),
  getP45ArticlesLatest: () => getJson<P45Articles>('/api/p45/articles/latest'),
  getP45ArticleHistory: (limit = 20) =>
    getJson<P45ArticleHistory>(`/api/p45/articles/history${queryString({ limit })}`),
  getP45AnalystsLatest: () => getJson<JsonRecord>('/api/p45/analysts/latest'),
  getP45LlmLatest: () => getJson<JsonRecord>('/api/p45/llm/latest'),
  getP45InvalidationLatest: () => getJson<P45Invalidation>('/api/p45/invalidation/latest'),
  getEventWindowLatest: () => getJson<EventWindowPayload>('/api/event-window/latest'),
  getEventWindowActive: () => getJson<EventWindowPayload>('/api/event-window/active'),
  getEventWindowTimeline: (limit = 200) =>
    getJson<EventWindowPayload>(`/api/event-window/timeline${queryString({ limit })}`),
  getEventWindowCalendar: (limit = 100) =>
    getJson<EventWindowPayload>(`/api/event-window/calendar${queryString({ limit })}`),
  getEventWindowAlerts: (limit = 100) =>
    getJson<EventWindowPayload>(`/api/event-window/alerts${queryString({ limit })}`),
  getEventWindowDaemonStatus: () => getJson<EventWindowPayload>('/api/event-window/daemon/status'),
  getEventWindowDaemonHealth: () => getJson<EventWindowPayload>('/api/event-window/daemon/health'),
  getEventWindowSourceStatus: () =>
    getJson<EventWindowPayload>('/api/event-window/sources/status'),
  getEventWindowSourceFetches: (limit = 100) =>
    getJson<EventWindowPayload>(`/api/event-window/sources/fetches${queryString({ limit })}`),
  runEventWindowOnce: () => postJson<EventWindowPayload>('/api/event-window/run-once'),
  runEventWindowAuditBundle: () => postJson<EventWindowPayload>('/api/event-window/audit-bundle/run'),
  getEventWindowAuditBundleLatest: () =>
    getJson<EventWindowPayload>('/api/event-window/audit-bundle/latest'),
  getRadarRuntimeDaemonStatus: () => getJson<RadarRuntimePayload>('/api/radar-runtime/daemon/status'),
  getRadarRuntimeDaemonHealth: () => getJson<RadarRuntimePayload>('/api/radar-runtime/daemon/health'),
  getRadarRuntimeModulesLatest: () => getJson<RadarRuntimePayload>('/api/radar-runtime/modules/latest'),
  getRadarRuntimeCockpitLatest: () => getJson<RadarRuntimePayload>('/api/radar-runtime/cockpit/latest'),
  runRadarRuntimeOnce: () => postJson<RadarRuntimePayload>('/api/radar-runtime/run-once'),
  pauseRadarRuntimeDaemon: () => postJson<RadarRuntimePayload>('/api/radar-runtime/daemon/pause'),
  resumeRadarRuntimeDaemon: () => postJson<RadarRuntimePayload>('/api/radar-runtime/daemon/resume'),
  pauseEventWindowDaemon: () => postJson<EventWindowPayload>('/api/event-window/daemon/pause'),
  resumeEventWindowDaemon: () => postJson<EventWindowPayload>('/api/event-window/daemon/resume'),
  getDataQualityLatest: () => getJson<JsonRecord>('/api/data-quality/latest'),
  getP3AlertsLatest: () => getJson<JsonRecord>('/api/p3/alerts/latest'),
  getP3EventsLatest: () => getJson<JsonRecord>('/api/p3/events/latest'),
  getSourceDetail: (sourceId: string) =>
    getJson<JsonRecord>(`/api/sources/${encodeURIComponent(sourceId)}`, { source_id: sourceId }),
  getSourceAuthState: (sourceId: string) =>
    getJson<JsonRecord>(`/api/sources/${encodeURIComponent(sourceId)}/auth-state`, { source_id: sourceId }),
  openSourceVerifyWindow: (sourceId: string) =>
    postJson<JsonRecord>(`/api/sources/${encodeURIComponent(sourceId)}/open-verify-window`, { source_id: sourceId }),
  retrySourceCollect: (sourceId: string) =>
    postJson<JsonRecord>(`/api/sources/${encodeURIComponent(sourceId)}/retry-collect`, { source_id: sourceId }),
  getSourceLastCapture: (sourceId: string) =>
    getJson<JsonRecord>(`/api/sources/${encodeURIComponent(sourceId)}/last-capture`, { source_id: sourceId }),
  getP45RunsLatest: () => getJson<P45Runs>('/api/p45/runs/latest'),
  getRun: (runId: string) =>
    getJson<JsonRecord>(`/api/runs/${encodeURIComponent(runId)}`, { run_id: runId }),
  getRunAuditReports: (runId: string) =>
    getJson<AuditReports>(`/api/runs/${encodeURIComponent(runId)}/audit-reports`, {
      run_id: runId,
    }),
  getP45History: (finalRunId: string) =>
    getJson<JsonRecord>(`/api/p45/history/${encodeURIComponent(finalRunId)}`, {
      run_id: finalRunId,
    }),
  getP45AuditReportsLatest: () => getJson<AuditReports>('/api/p45/audit-reports/latest'),
  getSettings: () => getJson<P45Settings>('/api/settings'),
  getSettingsAudit: (limit = 20) =>
    getJson<JsonRecord>(`/api/settings/audit${queryString({ limit })}`),
  updateSettingsEnv: (updates: Record<string, string>) =>
    postJsonBody<JsonRecord>('/api/settings/env', { updates }),
  getProviderHealth: () => getJson<JsonRecord>('/api/settings/providers/health'),
  testProviderHealth: (providerId: string) =>
    postJson<JsonRecord>(`/api/settings/providers/${encodeURIComponent(providerId)}/test`),
  testAllProviderHealth: () => postJson<JsonRecord>('/api/settings/providers/health/test-all'),
  startP45FullWithLlmJob: (
    params: {
      run_mode?: string
      runtime_mode?: string
      llm_runtime_mode?: string
      execution_profile?: string
      skip_llm?: boolean
      skip_research_llm?: boolean
      skip_analyst_llm?: boolean
    } = {},
  ) =>
    postJson<P45RunJob>(
      `/api/p45/run-full-with-llm/jobs${queryString({
        run_mode: params.run_mode ?? 'live',
        runtime_mode: params.runtime_mode ?? 'deterministic',
        llm_runtime_mode: params.llm_runtime_mode ?? 'llm',
        execution_profile: params.execution_profile,
        skip_llm: params.skip_llm,
        skip_research_llm: params.skip_research_llm,
        skip_analyst_llm: params.skip_analyst_llm,
      })}`,
    ),
  getP45FullWithLlmJob: (jobRunId: string) =>
    getJson<P45RunJob>(`/api/p45/run-full-with-llm/jobs/${encodeURIComponent(jobRunId)}`, {
      run_id: jobRunId,
    }),
  getP45FullWithLlmLatestJob: () => getJson<P45RunJob>('/api/p45/run-full-with-llm/jobs/latest'),
  runP45FullWithLlm: (
    params: {
      run_mode?: string
      runtime_mode?: string
      llm_runtime_mode?: string
    } = {},
  ) =>
    postJson<JsonRecord>(
      `/api/p45/run-full-with-llm${queryString({
        run_mode: params.run_mode ?? 'live',
        runtime_mode: params.runtime_mode ?? 'deterministic',
        llm_runtime_mode: params.llm_runtime_mode ?? 'llm',
      })}`,
    ),
}
