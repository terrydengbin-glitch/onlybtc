import { computed, reactive } from 'vue';
import { ApiClientError, api, } from './api';
const ACTIVE_RUN_JOB_KEY = 'onlybtc:p45:active-run-job-id';
const LLM_RUN_ENABLED_KEY = 'onlybtc:p45:llm-run-enabled';
let runJobPollTimer = null;
let refreshLatestAfterJob = null;
let lastDecisionReadyRefreshJobId = '';
let deferredLatestLoadTimer = null;
let eventSource = null;
const state = reactive({
    dashboard: null,
    overview: null,
    radarModulesPayload: null,
    articles: null,
    articleHistory: null,
    invalidation: null,
    runs: null,
    auditReports: null,
    dataQuality: null,
    evidence: null,
    analysts: null,
    llm: null,
    settings: null,
    alerts: null,
    events: null,
    eventWindow: null,
    eventWindowTimeline: null,
    eventWindowCalendar: null,
    eventWindowAlerts: null,
    eventWindowDaemon: null,
    eventWindowSources: null,
    eventWindowSourceFetches: null,
    eventWindowRunOnceResult: null,
    eventWindowAuditBundle: null,
    radarRuntimeDaemon: null,
    radarRuntimeCockpit: null,
    radarRuntimeModules: null,
    radarRuntimeRunOnceResult: null,
    selectedRadarDetail: null,
    selectedEvidenceDetail: null,
    selectedSourceDetail: null,
    selectedSourceAuthState: null,
    selectedSourceLastCapture: null,
    selectedSourceActionResult: null,
    selectedHistory: null,
    selectedRun: null,
    activeRunJob: null,
    activeRunJobId: '',
    eventStreamStatus: 'idle',
    eventStreamLastEvent: null,
    llmRunEnabled: window.localStorage.getItem(LLM_RUN_ENABLED_KEY) !== 'false',
    routeContext: {
        final_run_id: '',
        pack_id: '',
        module_id: '',
        evidence_id: '',
        source_id: '',
        analyst_id: '',
        isHistorical: false,
    },
    loading: false,
    running: false,
    error: null,
    errors: [],
    runResult: null,
});
function getErrorMessage(err) {
    if (err instanceof ApiClientError)
        return err.message;
    return err instanceof Error ? err.message : 'Unknown error';
}
function trackError(err) {
    state.error = getErrorMessage(err);
    if (err instanceof ApiClientError) {
        state.errors = [err.context, ...state.errors].slice(0, 8);
    }
}
function rememberEndpointError(err) {
    if (err instanceof ApiClientError) {
        const duplicate = state.errors.some((item) => item.endpoint === err.context.endpoint &&
            item.status === err.context.status &&
            item.method === err.context.method);
        state.errors = duplicate ? state.errors : [err.context, ...state.errors].slice(0, 8);
    }
    else {
        state.errors = [{ endpoint: 'refreshLatest', method: 'GET' }, ...state.errors].slice(0, 8);
    }
    return getErrorMessage(err);
}
function forgetEndpointError(endpoint, method = 'GET') {
    state.errors = state.errors.filter((item) => item.endpoint !== endpoint || item.method !== method);
}
function listFromPayload(payload, fallback) {
    return payload?.modules ?? payload?.radar_modules ?? fallback ?? [];
}
function parseEvidenceScope(evidenceId, modules) {
    for (const module of modules) {
        const moduleId = String(module.radar_module ?? module.module_id ?? '');
        if (!moduleId)
            continue;
        const marker = `-${moduleId}-`;
        const markerIndex = evidenceId.indexOf(marker);
        if (markerIndex < 0)
            continue;
        return {
            module_id: moduleId,
            metric_id: evidenceId.slice(markerIndex + marker.length),
        };
    }
    const fallbackMatch = evidenceId.match(/^p3-score-p3-[^-]+-[^-]+-([a-z0-9_]+)-(.+)$/i);
    return fallbackMatch ? { module_id: fallbackMatch[1], metric_id: fallbackMatch[2] } : null;
}
function syncRunContext() {
    const lineage = (state.dashboard?.run_lineage ?? state.overview?.run_lineage ?? state.runs?.latest ?? {});
    const finalRunId = String(lineage.final_run_id ?? state.dashboard?.final_run_id ?? '');
    const packId = String(lineage.pack_id ?? state.dashboard?.pack_id ?? '');
    if (!state.routeContext.isHistorical && finalRunId) {
        state.routeContext.final_run_id = finalRunId;
    }
    if (!state.routeContext.isHistorical && packId) {
        state.routeContext.pack_id = packId;
    }
}
function isTerminalRunJob(job) {
    const status = String(job?.status ?? '').toLowerCase();
    return ['completed', 'completed_with_llm_errors', 'failed', 'cancelled'].includes(status);
}
function assignRunJob(job) {
    state.activeRunJob = job;
    state.activeRunJobId = String(job?.job_run_id ?? job?.run_id ?? '');
    if (state.activeRunJobId && !isTerminalRunJob(job)) {
        window.localStorage.setItem(ACTIVE_RUN_JOB_KEY, state.activeRunJobId);
    }
    const lineage = (job?.run_lineage ?? {});
    if (job) {
        state.runs = {
            ...job,
            latest: lineage,
            stages: job.stages ?? [],
        };
    }
    state.running = Boolean(job && !isTerminalRunJob(job));
    if (job && isTerminalRunJob(job)) {
        window.localStorage.removeItem(ACTIVE_RUN_JOB_KEY);
    }
}
function scheduleRunJobPoll(jobRunId) {
    if (runJobPollTimer)
        window.clearTimeout(runJobPollTimer);
    runJobPollTimer = window.setTimeout(() => {
        void pollRunJob(jobRunId);
    }, 2500);
}
async function pollRunJob(jobRunId) {
    if (!jobRunId)
        return null;
    try {
        const job = await api.getP45FullWithLlmJob(jobRunId);
        assignRunJob(job);
        if (job?.decision_ready && lastDecisionReadyRefreshJobId !== jobRunId) {
            lastDecisionReadyRefreshJobId = jobRunId;
            await refreshLatestAfterJob?.();
        }
        if (!isTerminalRunJob(job)) {
            scheduleRunJobPoll(jobRunId);
        }
        else {
            await refreshLatestAfterJob?.();
        }
        return job;
    }
    catch (err) {
        rememberEndpointError(err);
        scheduleRunJobPoll(jobRunId);
        return null;
    }
}
function handleEventStreamMessage(event) {
    try {
        const payload = JSON.parse(event.data);
        state.eventStreamLastEvent = payload;
        state.eventStreamStatus = 'connected';
        const job = payload.job;
        if (job && job.status && job.status !== 'missing') {
            assignRunJob(job);
            const jobRunId = String(job.job_run_id ?? job.run_id ?? '');
            if (jobRunId && job.decision_ready && lastDecisionReadyRefreshJobId !== jobRunId) {
                lastDecisionReadyRefreshJobId = jobRunId;
                void refreshLatestAfterJob?.();
            }
        }
    }
    catch (err) {
        rememberEndpointError(err);
    }
}
function startEventStream() {
    if (state.routeContext.isHistorical)
        return;
    if (eventSource)
        return;
    state.eventStreamStatus = 'connecting';
    eventSource = new EventSource('/api/events');
    eventSource.addEventListener('p45_run_update', handleEventStreamMessage);
    eventSource.onopen = () => {
        state.eventStreamStatus = 'connected';
        forgetEndpointError('/api/events', 'GET');
    };
    eventSource.onerror = () => {
        state.eventStreamStatus = 'reconnecting';
        rememberEndpointError(new ApiClientError('SSE stream disconnected', {
            endpoint: '/api/events',
            method: 'GET',
            status: 0,
        }));
    };
}
function stopEventStream() {
    if (!eventSource)
        return;
    eventSource.removeEventListener('p45_run_update', handleEventStreamMessage);
    eventSource.close();
    eventSource = null;
    state.eventStreamStatus = 'idle';
}
function assignLatestPayload(key, value) {
    switch (key) {
        case 'dashboard':
            state.dashboard = value;
            break;
        case 'overview':
            state.overview = value;
            break;
        case 'radarModulesPayload':
            state.radarModulesPayload = value;
            break;
        case 'articles':
            state.articles = value;
            break;
        case 'articleHistory':
            state.articleHistory = value;
            break;
        case 'invalidation':
            state.invalidation = value;
            break;
        case 'runs':
            state.runs = value;
            break;
        case 'auditReports':
            state.auditReports = value;
            break;
        case 'dataQuality':
            state.dataQuality = value;
            break;
        case 'alerts':
            state.alerts = value;
            break;
        case 'events':
            state.events = value;
            break;
        case 'eventWindow':
            state.eventWindow = value;
            break;
        case 'eventWindowTimeline':
            state.eventWindowTimeline = value;
            break;
        case 'eventWindowCalendar':
            state.eventWindowCalendar = value;
            break;
        case 'eventWindowAlerts':
            state.eventWindowAlerts = value;
            break;
        case 'eventWindowDaemon':
            state.eventWindowDaemon = value;
            break;
        case 'eventWindowSources':
            state.eventWindowSources = value;
            break;
        case 'eventWindowSourceFetches':
            state.eventWindowSourceFetches = value;
            break;
        case 'radarRuntimeDaemon':
            state.radarRuntimeDaemon = value;
            break;
        case 'radarRuntimeCockpit':
            state.radarRuntimeCockpit = value;
            break;
        case 'radarRuntimeModules':
            state.radarRuntimeModules = value;
            break;
        case 'settings':
            state.settings = value;
            break;
        case 'evidence':
            state.evidence = value;
            break;
        case 'analysts':
            state.analysts = value;
            break;
        case 'llm':
            state.llm = value;
            break;
    }
}
export function useOnlybtcStore() {
    const runLineage = computed(() => state.dashboard?.run_lineage ?? state.overview?.run_lineage ?? state.runs?.latest ?? {});
    const finalRunId = computed(() => String(runLineage.value.final_run_id ?? ''));
    const radarModules = computed(() => listFromPayload(state.radarModulesPayload, state.dashboard?.radar_modules));
    const reports = computed(() => state.auditReports?.reports ?? state.dashboard?.audit_reports?.reports ?? []);
    const hasEndpointErrors = computed(() => state.errors.length > 0);
    async function refreshLatest() {
        if (state.routeContext.isHistorical)
            return;
        startEventStream();
        state.loading = true;
        state.error = null;
        try {
            const loaders = [
                { key: 'dashboard', request: api.getP45DashboardLatest, critical: true, endpoint: '/api/p45/dashboard/latest' },
                { key: 'overview', request: api.getP45OverviewLatest, critical: true, endpoint: '/api/p45/overview/latest' },
                { key: 'articles', request: api.getP45ArticlesLatest, endpoint: '/api/p45/articles/latest' },
                { key: 'articleHistory', request: () => api.getP45ArticleHistory(30), endpoint: '/api/p45/articles/history?limit=30' },
                { key: 'invalidation', request: api.getP45InvalidationLatest, endpoint: '/api/p45/invalidation/latest' },
                { key: 'runs', request: api.getP45RunsLatest, endpoint: '/api/p45/runs/latest' },
                { key: 'auditReports', request: api.getP45AuditReportsLatest, endpoint: '/api/p45/audit-reports/latest' },
                { key: 'dataQuality', request: api.getDataQualityLatest, endpoint: '/api/data-quality/latest' },
                { key: 'alerts', request: api.getP3AlertsLatest, endpoint: '/api/p3/alerts/latest' },
                { key: 'events', request: api.getP3EventsLatest, endpoint: '/api/p3/events/latest' },
                { key: 'eventWindow', request: api.getEventWindowLatest, endpoint: '/api/event-window/latest' },
                { key: 'eventWindowTimeline', request: () => api.getEventWindowTimeline(100), endpoint: '/api/event-window/timeline?limit=100' },
                { key: 'eventWindowCalendar', request: () => api.getEventWindowCalendar(30), endpoint: '/api/event-window/calendar?limit=30' },
                { key: 'eventWindowAlerts', request: () => api.getEventWindowAlerts(30), endpoint: '/api/event-window/alerts?limit=30' },
                { key: 'eventWindowDaemon', request: api.getEventWindowDaemonStatus, endpoint: '/api/event-window/daemon/status' },
                { key: 'eventWindowSources', request: api.getEventWindowSourceStatus, endpoint: '/api/event-window/sources/status' },
                { key: 'eventWindowSourceFetches', request: () => api.getEventWindowSourceFetches(40), endpoint: '/api/event-window/sources/fetches?limit=40' },
                { key: 'radarRuntimeDaemon', request: api.getRadarRuntimeDaemonStatus, endpoint: '/api/radar-runtime/daemon/status' },
                { key: 'radarRuntimeCockpit', request: api.getRadarRuntimeCockpitLatest, endpoint: '/api/radar-runtime/cockpit/latest' },
                { key: 'settings', request: api.getSettings, endpoint: '/api/settings' },
                { key: 'evidence', request: () => api.getP45Evidence({ limit: 200 }), critical: true, endpoint: '/api/p45/evidence?limit=200' },
                { key: 'analysts', request: api.getP45AnalystsLatest, endpoint: '/api/p45/analysts/latest' },
                { key: 'llm', request: api.getP45LlmLatest, endpoint: '/api/p45/llm/latest' },
            ];
            const deferredLoaders = [
                { key: 'radarModulesPayload', request: api.getP45RadarModulesLatest, endpoint: '/api/p45/radar-modules/latest' },
                { key: 'radarRuntimeModules', request: api.getRadarRuntimeModulesLatest, endpoint: '/api/radar-runtime/modules/latest' },
            ];
            const criticalFailures = [];
            const runLoader = async (loader) => {
                try {
                    assignLatestPayload(loader.key, await loader.request());
                    if (loader.endpoint)
                        forgetEndpointError(loader.endpoint, loader.method);
                    syncRunContext();
                    if (state.activeRunJob && !isTerminalRunJob(state.activeRunJob)) {
                        assignRunJob(state.activeRunJob);
                    }
                }
                catch (err) {
                    const message = rememberEndpointError(err);
                    if (loader.critical)
                        criticalFailures.push(message);
                }
            };
            const dashboardLoader = loaders.find((loader) => loader.key === 'dashboard');
            if (dashboardLoader)
                await runLoader(dashboardLoader);
            if (!state.dashboard) {
                const overviewLoader = loaders.find((loader) => loader.key === 'overview');
                if (overviewLoader)
                    await runLoader(overviewLoader);
            }
            void Promise.allSettled(loaders
                .filter((loader) => loader.key !== 'dashboard')
                .map(runLoader)).then(() => {
                const hasSettledCoreState = Boolean(state.dashboard || state.overview || state.radarModulesPayload || state.evidence);
                if (criticalFailures.length && !hasSettledCoreState) {
                    state.error = `核心数据加载失败：${criticalFailures[0]}`;
                }
                syncRunContext();
                if (state.activeRunJob && !isTerminalRunJob(state.activeRunJob)) {
                    assignRunJob(state.activeRunJob);
                }
            });
            const hasCoreState = Boolean(state.dashboard || state.overview || state.radarModulesPayload || state.evidence);
            if (criticalFailures.length && !hasCoreState) {
                state.error = `核心数据加载失败：${criticalFailures[0]}`;
            }
            syncRunContext();
            if (state.activeRunJob && !isTerminalRunJob(state.activeRunJob)) {
                assignRunJob(state.activeRunJob);
            }
            if (deferredLatestLoadTimer)
                window.clearTimeout(deferredLatestLoadTimer);
            deferredLatestLoadTimer = window.setTimeout(() => {
                void Promise.allSettled(deferredLoaders.map(async (loader) => {
                    try {
                        assignLatestPayload(loader.key, await loader.request());
                        if (loader.endpoint)
                            forgetEndpointError(loader.endpoint, loader.method);
                    }
                    catch (err) {
                        rememberEndpointError(err);
                    }
                }));
            }, 1200);
        }
        catch (err) {
            trackError(err);
        }
        finally {
            state.loading = false;
        }
    }
    refreshLatestAfterJob = refreshLatest;
    function setLlmRunEnabled(value) {
        state.llmRunEnabled = value;
        window.localStorage.setItem(LLM_RUN_ENABLED_KEY, value ? 'true' : 'false');
    }
    async function runFullChain(options = {}) {
        state.running = true;
        state.error = null;
        try {
            const llmEnabled = options.llmEnabled ?? state.llmRunEnabled;
            setLlmRunEnabled(llmEnabled);
            lastDecisionReadyRefreshJobId = '';
            const job = await api.startP45FullWithLlmJob({
                execution_profile: llmEnabled ? 'full_with_llm' : 'fast_deterministic',
                skip_llm: !llmEnabled,
            });
            state.runResult = job;
            assignRunJob(job);
            const jobRunId = String(job.job_run_id ?? job.run_id ?? '');
            if (jobRunId)
                scheduleRunJobPoll(jobRunId);
        }
        catch (err) {
            trackError(err);
            state.running = false;
            window.localStorage.removeItem(ACTIVE_RUN_JOB_KEY);
        }
        finally {
            if (!state.activeRunJobId)
                state.running = false;
        }
    }
    async function resumeActiveRunJob() {
        const storedJobRunId = window.localStorage.getItem(ACTIVE_RUN_JOB_KEY) ?? '';
        try {
            const job = storedJobRunId
                ? await api.getP45FullWithLlmJob(storedJobRunId)
                : await api.getP45FullWithLlmLatestJob();
            if (!job || job.status === 'missing')
                return null;
            assignRunJob(job);
            const jobRunId = String(job.job_run_id ?? job.run_id ?? '');
            if (jobRunId && !isTerminalRunJob(job))
                scheduleRunJobPoll(jobRunId);
            return job;
        }
        catch (err) {
            rememberEndpointError(err);
            window.localStorage.removeItem(ACTIVE_RUN_JOB_KEY);
            return null;
        }
    }
    async function loadRadarDetail(moduleId) {
        state.routeContext.module_id = moduleId;
        state.selectedRadarDetail = await api.getP45RadarModule(moduleId).catch((err) => {
            trackError(err);
            return null;
        });
        return state.selectedRadarDetail;
    }
    async function loadEvidenceDetail(evidenceId) {
        state.routeContext.evidence_id = evidenceId;
        try {
            state.selectedEvidenceDetail = await api.getP45EvidenceItem(evidenceId, {
                final_run_id: state.routeContext.final_run_id,
                pack_id: state.routeContext.pack_id,
                allow_stale_fallback: true,
            });
            const resolved = state.selectedEvidenceDetail?.resolution;
            const resolvedId = String(resolved?.resolved_evidence_id ?? '');
            if (resolvedId && resolvedId !== evidenceId) {
                state.routeContext.evidence_id = resolvedId;
            }
            return state.selectedEvidenceDetail;
        }
        catch (err) {
            if (err instanceof ApiClientError && err.context.status === 404) {
                const modules = listFromPayload(state.radarModulesPayload, state.dashboard?.radar_modules);
                const scope = parseEvidenceScope(evidenceId, modules);
                if (scope) {
                    const cached = (state.evidence?.items ?? []).find((item) => String(item.radar_module ?? item.module_id) === scope.module_id &&
                        String(item.metric_id) === scope.metric_id);
                    const payload = cached
                        ? { run_lineage: state.dashboard?.run_lineage ?? state.overview?.run_lineage ?? {}, evidence: cached }
                        : await api.getP45Evidence({ module_id: scope.module_id, metric_id: scope.metric_id, limit: 1 }).catch(() => null);
                    const item = cached ?? payload?.items?.[0];
                    if (item?.evidence_id) {
                        state.routeContext.evidence_id = String(item.evidence_id);
                        state.selectedEvidenceDetail = {
                            run_lineage: payload?.run_lineage ?? state.dashboard?.run_lineage ?? {},
                            evidence: item,
                            resolved_from_stale_evidence_id: evidenceId,
                        };
                        return state.selectedEvidenceDetail;
                    }
                }
            }
            trackError(err);
            state.selectedEvidenceDetail = null;
        }
        return state.selectedEvidenceDetail;
    }
    async function loadSourceDetail(sourceId) {
        state.routeContext.source_id = sourceId;
        state.selectedSourceDetail = await api.getSourceDetail(sourceId).catch((err) => {
            trackError(err);
            return null;
        });
        state.selectedSourceAuthState = await api.getSourceAuthState(sourceId).catch(() => null);
        state.selectedSourceLastCapture = await api.getSourceLastCapture(sourceId).catch(() => null);
        return state.selectedSourceDetail;
    }
    async function openSourceVerifyWindow(sourceId) {
        const result = await api.openSourceVerifyWindow(sourceId).catch((err) => {
            trackError(err);
            return null;
        });
        if (result) {
            state.selectedSourceAuthState = result;
            state.selectedSourceActionResult = result;
        }
        return result;
    }
    async function retrySourceCollect(sourceId) {
        const result = await api.retrySourceCollect(sourceId).catch((err) => {
            trackError(err);
            return null;
        });
        if (result) {
            state.selectedSourceLastCapture = result;
            state.selectedSourceActionResult = result;
        }
        return result;
    }
    async function loadSourceLastCapture(sourceId) {
        const result = await api.getSourceLastCapture(sourceId).catch((err) => {
            trackError(err);
            return null;
        });
        if (result) {
            state.selectedSourceLastCapture = result;
            state.selectedSourceActionResult = result;
        }
        return result;
    }
    async function loadHistory(finalRunId) {
        state.routeContext.isHistorical = true;
        stopEventStream();
        state.routeContext.final_run_id = finalRunId;
        state.routeContext.pack_id = '';
        state.selectedHistory = await api.getP45History(finalRunId).catch((err) => {
            trackError(err);
            return null;
        });
        return state.selectedHistory;
    }
    async function pauseEventWindowDaemon() {
        const result = await api.pauseEventWindowDaemon().catch((err) => {
            trackError(err);
            return null;
        });
        if (result)
            state.eventWindowDaemon = result;
        return result;
    }
    async function resumeEventWindowDaemon() {
        const result = await api.resumeEventWindowDaemon().catch((err) => {
            trackError(err);
            return null;
        });
        if (result) {
            state.eventWindowDaemon = result;
            await refreshLatest();
        }
        return result;
    }
    async function refreshEventWindowLatest() {
        if (state.routeContext.isHistorical)
            return null;
        const loaders = [
            { key: 'eventWindow', request: api.getEventWindowLatest, endpoint: '/api/event-window/latest' },
            { key: 'eventWindowTimeline', request: () => api.getEventWindowTimeline(100), endpoint: '/api/event-window/timeline?limit=100' },
            { key: 'eventWindowCalendar', request: () => api.getEventWindowCalendar(30), endpoint: '/api/event-window/calendar?limit=30' },
            { key: 'eventWindowAlerts', request: () => api.getEventWindowAlerts(30), endpoint: '/api/event-window/alerts?limit=30' },
            { key: 'eventWindowDaemon', request: api.getEventWindowDaemonStatus, endpoint: '/api/event-window/daemon/status' },
            { key: 'eventWindowSources', request: api.getEventWindowSourceStatus, endpoint: '/api/event-window/sources/status' },
            { key: 'eventWindowSourceFetches', request: () => api.getEventWindowSourceFetches(40), endpoint: '/api/event-window/sources/fetches?limit=40' },
        ];
        const results = await Promise.allSettled(loaders.map(async (loader) => ({
            key: loader.key,
            value: await loader.request(),
        })));
        for (const result of results) {
            if (result.status === 'fulfilled') {
                assignLatestPayload(result.value.key, result.value.value);
                const loader = loaders[results.indexOf(result)];
                if (loader?.endpoint)
                    forgetEndpointError(loader.endpoint, loader.method);
            }
            else {
                rememberEndpointError(result.reason);
            }
        }
        return state.eventWindow;
    }
    async function runEventWindowOnce() {
        const result = await api.runEventWindowOnce().catch((err) => {
            trackError(err);
            return null;
        });
        if (result) {
            state.eventWindowRunOnceResult = result;
            state.eventWindow = {
                status: 'ok',
                event_window: result.event_window,
            };
            state.eventWindowDaemon = {
                status: 'ok',
                daemon: result.daemon,
            };
            await refreshLatest();
        }
        return result;
    }
    async function runEventWindowAuditBundle() {
        const result = await api.runEventWindowAuditBundle().catch((err) => {
            trackError(err);
            return null;
        });
        if (result) {
            state.eventWindowAuditBundle = result;
        }
        return result;
    }
    async function runRadarRuntimeOnce() {
        const result = await api.runRadarRuntimeOnce().catch((err) => {
            trackError(err);
            return null;
        });
        if (result) {
            state.radarRuntimeRunOnceResult = result;
            await refreshLatest();
        }
        return result;
    }
    async function pauseRadarRuntimeDaemon() {
        const result = await api.pauseRadarRuntimeDaemon().catch((err) => {
            trackError(err);
            return null;
        });
        if (result)
            state.radarRuntimeDaemon = result;
        return result;
    }
    async function resumeRadarRuntimeDaemon() {
        const result = await api.resumeRadarRuntimeDaemon().catch((err) => {
            trackError(err);
            return null;
        });
        if (result) {
            state.radarRuntimeDaemon = result;
            await refreshLatest();
        }
        return result;
    }
    function exitHistoryMode() {
        state.routeContext.isHistorical = false;
        state.selectedHistory = null;
        syncRunContext();
        startEventStream();
    }
    return {
        state,
        finalRunId,
        radarModules,
        reports,
        runLineage,
        hasEndpointErrors,
        refreshLatest,
        setLlmRunEnabled,
        runFullChain,
        resumeActiveRunJob,
        loadRadarDetail,
        loadEvidenceDetail,
        loadSourceDetail,
        openSourceVerifyWindow,
        retrySourceCollect,
        loadSourceLastCapture,
        loadHistory,
        pauseEventWindowDaemon,
        resumeEventWindowDaemon,
        refreshEventWindowLatest,
        runEventWindowOnce,
        runEventWindowAuditBundle,
        runRadarRuntimeOnce,
        pauseRadarRuntimeDaemon,
        resumeRadarRuntimeDaemon,
        startEventStream,
        stopEventStream,
        exitHistoryMode,
    };
}
