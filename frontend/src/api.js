export class ApiClientError extends Error {
    context;
    payload;
    constructor(message, context, payload = null) {
        super(message);
        this.name = 'ApiClientError';
        this.context = context;
        this.payload = payload;
    }
}
function queryString(params) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== '')
            search.set(key, String(value));
    }
    return search.size ? `?${search}` : '';
}
function extractErrorMessage(payload, fallback) {
    if (payload && typeof payload === 'object') {
        const record = payload;
        const error = record.error;
        return String(error?.message ?? record.message ?? record.detail ?? fallback);
    }
    return fallback;
}
async function parseJsonResponse(response, context) {
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
        throw new ApiClientError(extractErrorMessage(payload, `Failed to load ${context.endpoint}`), { ...context, status: response.status }, payload);
    }
    return payload;
}
async function requestJson(method, endpoint, context = {}, body) {
    const response = await fetch(endpoint, {
        method,
        headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
    });
    return parseJsonResponse(response, { endpoint, method, ...context });
}
async function getJson(endpoint, context = {}) {
    return requestJson('GET', endpoint, context);
}
async function postJson(endpoint, context = {}) {
    return requestJson('POST', endpoint, context);
}
async function postJsonBody(endpoint, body, context = {}) {
    return requestJson('POST', endpoint, context, body);
}
export const api = {
    getP45DashboardLatest: () => getJson('/api/p45/dashboard/latest'),
    getP45OverviewLatest: () => getJson('/api/p45/overview/latest'),
    getP45RadarModulesLatest: () => getJson('/api/p45/radar-modules/latest'),
    getP45RadarModule: (moduleId) => getJson(`/api/p45/radar-modules/${encodeURIComponent(moduleId)}`, {
        module_id: moduleId,
    }),
    getP45Evidence: (params = {}) => {
        return getJson(`/api/p45/evidence${queryString(params)}`, params.module_id ? { module_id: params.module_id } : {});
    },
    getP45EvidenceItem: (evidenceId, params = {}) => getJson(`/api/p45/evidence/${encodeURIComponent(evidenceId)}${queryString({
        final_run_id: params.final_run_id,
        pack_id: params.pack_id,
        allow_stale_fallback: params.allow_stale_fallback ? 'true' : undefined,
    })}`, {
        evidence_id: evidenceId,
    }),
    getP45ArticlesLatest: () => getJson('/api/p45/articles/latest'),
    getP45ArticleHistory: (limit = 20) => getJson(`/api/p45/articles/history${queryString({ limit })}`),
    getP45AnalystsLatest: () => getJson('/api/p45/analysts/latest'),
    getP45LlmLatest: () => getJson('/api/p45/llm/latest'),
    getP45InvalidationLatest: () => getJson('/api/p45/invalidation/latest'),
    getEventWindowLatest: () => getJson('/api/event-window/latest'),
    getEventWindowActive: () => getJson('/api/event-window/active'),
    getEventWindowTimeline: (limit = 200) => getJson(`/api/event-window/timeline${queryString({ limit })}`),
    getEventWindowCalendar: (limit = 100) => getJson(`/api/event-window/calendar${queryString({ limit })}`),
    getEventWindowAlerts: (limit = 100) => getJson(`/api/event-window/alerts${queryString({ limit })}`),
    getEventWindowDaemonStatus: () => getJson('/api/event-window/daemon/status'),
    getEventWindowDaemonHealth: () => getJson('/api/event-window/daemon/health'),
    getEventWindowSourceStatus: () => getJson('/api/event-window/sources/status'),
    getEventWindowSourceFetches: (limit = 100) => getJson(`/api/event-window/sources/fetches${queryString({ limit })}`),
    runEventWindowOnce: () => postJson('/api/event-window/run-once'),
    runEventWindowAuditBundle: () => postJson('/api/event-window/audit-bundle/run'),
    getEventWindowAuditBundleLatest: () => getJson('/api/event-window/audit-bundle/latest'),
    getRadarRuntimeDaemonStatus: () => getJson('/api/radar-runtime/daemon/status'),
    getRadarRuntimeDaemonHealth: () => getJson('/api/radar-runtime/daemon/health'),
    getRadarRuntimeModulesLatest: () => getJson('/api/radar-runtime/modules/latest'),
    getRadarRuntimeCockpitLatest: () => getJson('/api/radar-runtime/cockpit/latest'),
    runRadarRuntimeOnce: () => postJson('/api/radar-runtime/run-once'),
    pauseRadarRuntimeDaemon: () => postJson('/api/radar-runtime/daemon/pause'),
    resumeRadarRuntimeDaemon: () => postJson('/api/radar-runtime/daemon/resume'),
    pauseEventWindowDaemon: () => postJson('/api/event-window/daemon/pause'),
    resumeEventWindowDaemon: () => postJson('/api/event-window/daemon/resume'),
    getDataQualityLatest: () => getJson('/api/data-quality/latest'),
    getP3AlertsLatest: () => getJson('/api/p3/alerts/latest'),
    getP3EventsLatest: () => getJson('/api/p3/events/latest'),
    getSourceDetail: (sourceId) => getJson(`/api/sources/${encodeURIComponent(sourceId)}`, { source_id: sourceId }),
    getSourceAuthState: (sourceId) => getJson(`/api/sources/${encodeURIComponent(sourceId)}/auth-state`, { source_id: sourceId }),
    openSourceVerifyWindow: (sourceId) => postJson(`/api/sources/${encodeURIComponent(sourceId)}/open-verify-window`, { source_id: sourceId }),
    retrySourceCollect: (sourceId) => postJson(`/api/sources/${encodeURIComponent(sourceId)}/retry-collect`, { source_id: sourceId }),
    getSourceLastCapture: (sourceId) => getJson(`/api/sources/${encodeURIComponent(sourceId)}/last-capture`, { source_id: sourceId }),
    getP45RunsLatest: () => getJson('/api/p45/runs/latest'),
    getRun: (runId) => getJson(`/api/runs/${encodeURIComponent(runId)}`, { run_id: runId }),
    getRunAuditReports: (runId) => getJson(`/api/runs/${encodeURIComponent(runId)}/audit-reports`, {
        run_id: runId,
    }),
    getP45History: (finalRunId) => getJson(`/api/p45/history/${encodeURIComponent(finalRunId)}`, {
        run_id: finalRunId,
    }),
    getP45AuditReportsLatest: () => getJson('/api/p45/audit-reports/latest'),
    getSettings: () => getJson('/api/settings'),
    getSettingsAudit: (limit = 20) => getJson(`/api/settings/audit${queryString({ limit })}`),
    updateSettingsEnv: (updates) => postJsonBody('/api/settings/env', { updates }),
    getProviderHealth: () => getJson('/api/settings/providers/health'),
    testProviderHealth: (providerId) => postJson(`/api/settings/providers/${encodeURIComponent(providerId)}/test`),
    testAllProviderHealth: () => postJson('/api/settings/providers/health/test-all'),
    startP45FullWithLlmJob: (params = {}) => postJson(`/api/p45/run-full-with-llm/jobs${queryString({
        run_mode: params.run_mode ?? 'live',
        runtime_mode: params.runtime_mode ?? 'deterministic',
        llm_runtime_mode: params.llm_runtime_mode ?? 'llm',
        execution_profile: params.execution_profile,
        skip_llm: params.skip_llm,
        skip_research_llm: params.skip_research_llm,
        skip_analyst_llm: params.skip_analyst_llm,
    })}`),
    getP45FullWithLlmJob: (jobRunId) => getJson(`/api/p45/run-full-with-llm/jobs/${encodeURIComponent(jobRunId)}`, {
        run_id: jobRunId,
    }),
    getP45FullWithLlmLatestJob: () => getJson('/api/p45/run-full-with-llm/jobs/latest'),
    runP45FullWithLlm: (params = {}) => postJson(`/api/p45/run-full-with-llm${queryString({
        run_mode: params.run_mode ?? 'live',
        runtime_mode: params.runtime_mode ?? 'deterministic',
        llm_runtime_mode: params.llm_runtime_mode ?? 'llm',
    })}`),
};
