import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { api } from './api';
import { useOnlybtcStore } from './store';
const pages = [
    { id: 'topology', label: '拓扑' },
    { id: 'eventWatchtower', label: '事件' },
    { id: 'radar', label: '雷达' },
    { id: 'evidence', label: '证据' },
    { id: 'alerts', label: '预警' },
    { id: 'quality', label: '质检' },
    { id: 'logs', label: '日志' },
    { id: 'history', label: '回放' },
    { id: 'settings', label: '设置' },
];
const validPageIds = new Set([
    ...pages.map((page) => page.id),
    'overview',
    'article',
    'invalidation',
    'source',
    'conflict',
]);
const store = useOnlybtcStore();
const state = store.state;
const activePage = ref('topology');
const drawerOpen = ref(true);
const pageFullscreen = ref(false);
const selectedModuleId = ref('');
const selectedEvidenceId = ref('');
const selectedSourceId = ref('');
const selectedRadarMetricId = ref('');
const evidenceModuleFilter = ref('all');
const evidenceBucketFilter = ref('all');
const settingsTab = ref('llm');
const settingsKeyInputs = reactive({});
const settingsKeySaving = ref('');
const settingsProviderTesting = ref('');
const settingsKeyMessage = ref('');
const settingsKeyError = ref('');
const selectedEventLlmAnalysisId = ref('');
const topologyRef = ref(null);
const btcRef = ref(null);
const radarLayout = reactive({});
const dragging = ref(null);
const eventAlertDragging = ref(null);
const eventAlertPosition = ref(null);
const eventAlertMutedUntil = ref(0);
const eventAlertNowMs = ref(Date.now());
const eventFloatingAlertHovered = ref(false);
const eventWatchtowerTab = ref('live');
const dismissedCriticalAlertKey = ref('');
const eventWindowAckKeys = ref([]);
const eventWindowHiddenKeys = ref([]);
const suppressNextEventAlertClick = ref(false);
const suppressNextNodeClick = ref(false);
const radarDefaultLoading = ref(false);
let syncingRoute = false;
let eventAlertClockTimer;
let eventWindowLiveTimer;
let eventWindowLiveRefreshInFlight = false;
const RADAR_LAYOUT_KEY = 'onlybtc:p5:radar-layout:v1';
const EVENT_ALERT_POSITION_KEY = 'onlybtc:p5:event-alert-position:v1';
const EVENT_ALERT_MUTE_KEY = 'onlybtc:p5:event-alert-muted-until:v1';
const EVENT_WINDOW_ACK_KEY = 'onlybtc:event-window:ack:v1';
const EVENT_WINDOW_HIDDEN_KEY = 'onlybtc:event-window:hidden:v1';
const EVENT_WINDOW_CRITICAL_DISMISS_KEY = 'onlybtc:event-window:critical-dismiss:v1';
const defaultLayoutPoints = [
    { x: 13, y: 22 },
    { x: 31, y: 13 },
    { x: 69, y: 12 },
    { x: 87, y: 25 },
    { x: 9, y: 48 },
    { x: 91, y: 55 },
    { x: 13, y: 78 },
    { x: 31, y: 87 },
    { x: 69, y: 90 },
    { x: 87, y: 85 },
    { x: 24, y: 36 },
    { x: 88, y: 40 },
    { x: 24, y: 64 },
    { x: 88, y: 70 },
];
const decision = computed(() => state.dashboard?.decision_card ?? {});
const btcCockpit = computed(() => (state.dashboard?.btc_trend_cockpit ?? state.overview?.btc_trend_cockpit ?? {}));
const radarRuntimePayload = computed(() => (state.radarRuntimeCockpit?.runtime ?? state.dashboard?.radar_runtime ?? {}));
const radarRuntimeDaemon = computed(() => (state.radarRuntimeDaemon?.daemon ?? {}));
const radarRuntimeHealth = computed(() => (radarRuntimePayload.value.health ?? state.dashboard?.radar_runtime_health ?? {}));
const radarRuntimeCockpit = computed(() => (radarRuntimePayload.value.btc_runtime_cockpit ?? state.dashboard?.btc_runtime_cockpit ?? {}));
const btcTimescaleJudge = computed(() => (state.dashboard?.btc_timescale_judge ?? state.overview?.btc_timescale_judge ?? {}));
const directTrendApi = computed(() => (state.dashboard?.direct_trend_api ?? state.overview?.direct_trend_api ?? {}));
const hasCockpit = computed(() => text(btcCockpit.value.schema_version, '') === 'p45.btc_trend_cockpit.v2');
const aggregation = computed(() => state.dashboard?.aggregation_audit ?? {});
const contract = computed(() => state.dashboard?.contract_validation ?? {});
const dataQuality = computed(() => state.dashboard?.data_quality ?? {});
const llm = computed(() => state.dashboard?.llm ?? {});
const horizons = computed(() => {
    return ['4h', '1d', '3d', '7d'].map((key) => [key, normalizeTimescaleHorizon(key)]);
});
const invalidationRules = computed(() => state.invalidation?.invalidation_rules ?? []);
const confirmationRules = computed(() => state.invalidation?.confirmation_rules ?? []);
const alerts = computed(() => state.alerts?.alerts ?? []);
const events = computed(() => state.events?.events ?? []);
const eventWatchtowerPayload = computed(() => (state.eventWindow?.event_window ?? state.dashboard?.event_window_v3 ?? {}));
const eventWindowState = computed(() => (eventWatchtowerPayload.value.state ?? {}));
const eventWindowOverlay = computed(() => (eventWatchtowerPayload.value.overlay ?? {}));
const eventWindowActive = computed(() => (eventWatchtowerPayload.value.active_event ?? {}));
const eventWindowDaemon = computed(() => (state.eventWindowDaemon?.daemon ?? eventWatchtowerPayload.value.daemon ?? {}));
const eventWindowTimeline = computed(() => (state.eventWindowTimeline?.items ?? []));
const eventWindowCalendar = computed(() => (state.eventWindowCalendar?.items ?? eventWatchtowerPayload.value.calendar_items ?? []));
const eventCalendarMiniWeekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const eventCalendarMiniAnchor = computed(() => {
    const candidates = [
        eventWindowActive.value.release_time_utc,
        eventWindowActive.value.release_time,
        eventWindowActive.value.event_time,
        ...eventWindowCalendar.value.flatMap((event) => [event.release_time_utc, event.release_time, event.event_time, event.date]),
    ];
    for (const candidate of candidates) {
        const parsed = parseEventDate(candidate);
        if (parsed)
            return parsed;
    }
    return new Date();
});
const eventCalendarMiniMonthLabel = computed(() => eventCalendarMiniAnchor.value.toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' }));
const eventCalendarMiniDays = computed(() => {
    const anchor = eventCalendarMiniAnchor.value;
    const year = anchor.getUTCFullYear();
    const month = anchor.getUTCMonth();
    const firstDay = new Date(Date.UTC(year, month, 1));
    const dayCount = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
    const byDay = new Map();
    for (const event of eventWindowCalendar.value) {
        const parsed = parseEventDate(event.release_time_utc ?? event.release_time ?? event.event_time ?? event.date);
        if (!parsed || parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month)
            continue;
        const day = parsed.getUTCDate();
        byDay.set(day, [...(byDay.get(day) ?? []), event]);
    }
    const activeId = text(eventWindowActive.value.event_id, '');
    const cells = [];
    for (let index = 0; index < firstDay.getUTCDay(); index += 1) {
        cells.push({
            key: `blank-${year}-${month}-${index}`,
            day: null,
            events: [],
            primary: {},
            labels: [],
            tone: 'quality',
            isBlank: true,
            isActive: false,
        });
    }
    for (let day = 1; day <= dayCount; day += 1) {
        const events = [...(byDay.get(day) ?? [])].sort((a, b) => eventImportanceRank(b) - eventImportanceRank(a));
        const primary = events[0] ?? {};
        cells.push({
            key: `${year}-${month + 1}-${day}`,
            day,
            events,
            primary,
            labels: events.map((event) => eventShortLabel(event)).filter(Boolean).slice(0, 2),
            tone: eventCalendarTone(primary),
            isBlank: false,
            isActive: Boolean(activeId && events.some((event) => text(event.event_id, '') === activeId)),
        });
    }
    return cells;
});
const eventWindowAlerts = computed(() => (state.eventWindowAlerts?.items ?? eventWatchtowerPayload.value.alerts ?? []));
const eventWindowSourceStatus = computed(() => (state.eventWindowSources ?? {}));
const eventWindowSourceSummary = computed(() => (eventWindowSourceStatus.value.summary ?? {}));
const eventWindowSources = computed(() => (eventWindowSourceStatus.value.sources ?? []));
const eventWindowSourceFetches = computed(() => (state.eventWindowSourceFetches?.items ?? []));
const eventWindowSourceQuality = computed(() => (eventWatchtowerPayload.value.data_quality?.source_quality ?? {}));
const eventWindowProviderConfidence = computed(() => (eventWatchtowerPayload.value.data_quality?.provider_confidence ?? {}));
const eventWindowProviderTierCounts = computed(() => (eventWindowProviderConfidence.value.provider_tier_counts ?? {}));
const eventWindowExpectation = computed(() => (eventWatchtowerPayload.value.expectation_monitor ?? {}));
const eventWindowPredictionOdds = computed(() => (eventWindowExpectation.value.prediction_market_odds ?? {}));
const eventWindowSecondaryMesh = computed(() => (eventWindowExpectation.value.secondary_calendar_mesh ?? {}));
const eventWindowDisabledCapabilities = computed(() => [
    ...(eventWindowSourceQuality.value.disabled_capabilities ?? []),
    ...(eventWindowProviderConfidence.value.disabled_capabilities ?? []),
].filter((value, index, arr) => arr.indexOf(value) === index));
const eventWindowSourceMode = computed(() => text(eventWindowSourceQuality.value.overall_source_mode
    ?? eventWindowProviderConfidence.value.lineage_mode
    ?? eventWindowSourceSummary.value.overall_source_mode
    ?? eventWatchtowerPayload.value.data_quality?.overall_source_mode, 'unknown'));
const eventWindowCalendarFallbackNotice = computed(() => {
    const blockedProvider = text(eventWindowActive.value.blocked_provider, '');
    const provider = text(eventWindowActive.value.provider, '');
    const tier = text(eventWindowActive.value.source_tier, '');
    if (!blockedProvider && eventWindowActive.value.fallback_used !== true)
        return '';
    if (tier === 'official_mirror')
        return `BLS official blocked, using mirror source ${provider || 'official_mirror'}`;
    if (tier === 'secondary_calendar')
        return `BLS official blocked, using secondary source ${provider || 'secondary_calendar'}`;
    if (tier === 'manual_override')
        return `BLS official blocked, using manual override ${provider || 'manual_override'}`;
    return `BLS official blocked, using fallback source ${provider || tier || 'unknown'}`;
});
const eventWindowSourceCounts = computed(() => ({
    live: Number(eventWindowSourceSummary.value.live_source_count ?? eventWindowSourceQuality.value.live_source_count ?? 0),
    partial: Number(eventWindowSourceSummary.value.partial_source_count ?? eventWindowSourceQuality.value.partial_source_count ?? 0),
    fallback: Number(eventWindowSourceSummary.value.fallback_source_count ?? eventWindowSourceQuality.value.fallback_source_count ?? 0),
    failed: Number(eventWindowSourceSummary.value.failed_source_count ?? eventWindowSourceQuality.value.failed_source_count ?? 0),
}));
const eventWindowShockLane = computed(() => (eventWatchtowerPayload.value.shock_fast_lane ?? {}));
const eventWindowShockLlmAnalysis = computed(() => (eventWindowShockLane.value.llm_analysis ?? {}));
const eventWindowMarketProbe = computed(() => {
    const direct = eventWatchtowerPayload.value.market_probe ?? null;
    if (direct && Object.keys(direct).length)
        return direct;
    const probes = eventWatchtowerPayload.value.market_probes ?? [];
    return (probes[0] ?? {});
});
const eventWindowMarketReturns = computed(() => (eventWindowMarketProbe.value.returns ?? {}));
const eventWindowMarketReturnZ = computed(() => (eventWindowMarketProbe.value.return_zscores ?? {}));
const eventWindowMarketReturnRows = computed(() => ['5m', '15m', '1h', '4h', '24h'].map((window) => ({
    window,
    value: eventWindowMarketReturns.value[window],
    z: eventWindowMarketReturnZ.value[window],
})));
const eventWindowShockEvidence = computed(() => (eventWindowShockLane.value.evidence ?? {}));
const eventWindowDaemonStaleReasons = computed(() => asList(eventWindowDaemon.value.stale_reasons).map((item) => text(item)));
const eventWindowDaemonHealthState = computed(() => text(eventWindowDaemon.value.health_state ?? eventWindowDaemon.value.status, 'unknown'));
const eventWindowSummaryAlert = computed(() => eventWindowAlerts.value[0] ?? {});
const eventWindowSummaryTitle = computed(() => {
    const shockDetected = Boolean(eventWindowShockLane.value.shock_detected);
    if (shockDetected)
        return `Shock lane · ${text(eventWindowShockLane.value.shock_type, 'unknown')}`;
    return text(eventWindowActive.value.title, 'Event Watchtower active');
});
const eventWindowSummarySubtitle = computed(() => {
    const stateName = text(eventWindowState.value.event_window_state, 'calendar_monitor');
    const phase = text(eventWindowActive.value.phase, 'calendar_awareness');
    const modifier = text(eventWindowOverlay.value.trade_permission_modifier, 'none');
    return `${stateName} · ${phase} · overlay ${modifier}`;
});
const eventWindowSummaryDetail = computed(() => {
    const level = text(eventWindowState.value.emergency_level, 'none');
    const trust = text(eventWindowOverlay.value.ordinary_radar_trust, 'normal');
    const daemon = text(eventWindowDaemon.value.status, 'running');
    return `Emergency ${level}; radar trust ${trust}; daemon ${daemon}.`;
});
const eventWindowSummaryAction = computed(() => {
    const modifier = text(eventWindowOverlay.value.trade_permission_modifier, 'none');
    if (modifier === 'event_lock')
        return 'event lock · avoid new position';
    if (modifier === 'watch_only')
        return 'watch only · wait for validation';
    if (modifier === 'reduce_size')
        return 'reduce size · monitor source drift';
    return 'normal monitoring';
});
const eventWindowReasonCodes = computed(() => asList(eventWindowState.value.reason_codes).map((item) => text(item)).slice(0, 5));
const eventWindowPostReaction = computed(() => (eventWatchtowerPayload.value.post_event_reaction ?? {}));
const eventWindowSpeechMonitor = computed(() => (eventWatchtowerPayload.value.fed_speech_monitor ?? {}));
const eventWindowLlmAnalyses = computed(() => (eventWatchtowerPayload.value.llm_analyses ?? []));
const eventWindowPrimaryLlmAnalysis = computed(() => {
    const analyses = [...eventWindowLlmAnalyses.value];
    if (!analyses.length)
        return {};
    const relevanceRank = { high: 3, medium: 2, low: 1 };
    return analyses.sort((a, b) => {
        const relA = relevanceRank[text(a.policy_relevance, 'low').toLowerCase()] ?? 0;
        const relB = relevanceRank[text(b.policy_relevance, 'low').toLowerCase()] ?? 0;
        if (relA !== relB)
            return relB - relA;
        return Number(b.tone_confidence ?? b.confidence ?? 0) - Number(a.tone_confidence ?? a.confidence ?? 0);
    })[0];
});
const selectedEventLlmAnalysis = computed(() => {
    const id = text(selectedEventLlmAnalysisId.value, '');
    if (id) {
        const match = eventWindowLlmAnalyses.value.find((item) => text(item.analysis_id, '') === id);
        if (match)
            return match;
    }
    return eventWindowPrimaryLlmAnalysis.value;
});
const eventWindowDirectScoreImpact = computed(() => text(eventWatchtowerPayload.value.direct_score_impact, 'false'));
const eventWindowScheduler = computed(() => (eventWindowDaemon.value.source_cadence ?? {}));
const eventWindowNextDueSources = computed(() => asList(eventWindowDaemon.value.next_due_sources).map((item) => text(item)).slice(0, 6));
const eventWindowPersistedScheduler = computed(() => (eventWindowDaemon.value.persisted_scheduler_state ?? []));
const eventWindowLastRunOnce = computed(() => (state.eventWindowRunOnceResult ?? {}));
const eventWindowAuditBundle = computed(() => (state.eventWindowAuditBundle?.audit_bundle ?? {}));
const eventWindowAuditBundleReports = computed(() => (eventWindowAuditBundle.value.reports ?? []));
const eventWindowAuditFileMeta = computed(() => (eventWindowAuditBundle.value.report_file_meta ?? []));
const eventWindowAuditRegression = computed(() => (eventWindowAuditBundle.value.regression_report ?? {}));
const eventWindowOverlayForbiddenKeys = computed(() => asList(eventWindowOverlay.value.forbidden_keys
    ?? eventWindowOverlay.value.forbidden_content_keys
    ?? eventWatchtowerPayload.value.forbidden_keys
    ?? eventWatchtowerPayload.value.forbidden_content_keys).map((item) => text(item)));
const eventWindowLlmViolations = computed(() => asList(selectedEventLlmAnalysis.value.violations ?? selectedEventLlmAnalysis.value.boundary_violations).map((item) => text(item)));
const eventWindowAuditReportLinks = computed(() => {
    const defaults = [
        {
            report: 'Source Audit',
            title: 'Source Audit',
            filename: 'event-window-source-audit-report.html',
            relative_path: 'reports/event-window-source-audit-report.html',
        },
        {
            report: 'State / Overlay / LLM Audit',
            title: 'State / Overlay / LLM Audit',
            filename: 'event-window-state-overlay-llm-audit-report.html',
            relative_path: 'reports/event-window-state-overlay-llm-audit-report.html',
        },
        {
            report: 'Shock Fast Lane Audit',
            title: 'Shock Fast Lane Audit',
            filename: 'event-window-shock-fast-lane-audit-report.html',
            relative_path: 'reports/event-window-shock-fast-lane-audit-report.html',
        },
    ];
    return defaults.map((report) => {
        const filename = text(report.filename, '');
        const meta = eventWindowAuditFileMeta.value.find((item) => text(item.path, '').includes(filename)) ??
            eventWindowAuditBundleReports.value.find((item) => text(item.html_path ?? item.path, '').includes(filename)) ??
            {};
        return { ...report, ...meta, filename, relative_path: text(meta.path ?? meta.html_path ?? report.relative_path, text(report.relative_path, '')) };
    });
});
const eventWatchtowerTabs = [
    { id: 'live', label: 'Live' },
    { id: 'calendar', label: 'Calendar' },
    { id: 'timeline', label: 'Timeline' },
    { id: 'speeches', label: 'Speeches' },
    { id: 'shock', label: 'Shock Lane' },
    { id: 'audit', label: 'Audit' },
    { id: 'history', label: 'History' },
];
const eventWindowVisibilityKey = computed(() => [
    text(eventWatchtowerPayload.value.snapshot_id, ''),
    text(eventWindowState.value.valid_until, ''),
    text(eventWindowState.value.event_window_state, ''),
    text(eventWindowState.value.emergency_level, ''),
].join('|'));
const eventCriticalAlertKey = computed(() => [
    text(eventWatchtowerPayload.value.snapshot_id, ''),
    text(eventWindowState.value.valid_until, ''),
    text(eventWindowState.value.event_window_state, ''),
    text(eventWindowState.value.emergency_level, ''),
    text(eventWindowOverlay.value.trade_permission_modifier, ''),
].join('|'));
const eventCurrentAlertAcked = computed(() => eventWindowAckKeys.value.includes(eventWindowVisibilityKey.value));
const eventCurrentAlertHidden = computed(() => eventWindowHiddenKeys.value.includes(eventWindowVisibilityKey.value));
const eventCriticalLikeActive = computed(() => {
    const level = text(eventWindowState.value.emergency_level, 'none').toLowerCase();
    const modifier = text(eventWindowOverlay.value.trade_permission_modifier, 'none').toLowerCase();
    return level === 'critical' || ['event_lock', 'avoid_new_position'].includes(modifier);
});
const eventCriticalOverlayActive = computed(() => {
    return eventCriticalLikeActive.value;
});
const showEventCriticalOverlay = computed(() => eventCriticalOverlayActive.value && dismissedCriticalAlertKey.value !== eventCriticalAlertKey.value);
const eventCriticalMockOverlayEnabled = computed(() => {
    if (!import.meta.env.DEV || typeof window === 'undefined')
        return false;
    return new URLSearchParams(window.location.search).get('event_mock') === 'critical';
});
const showEventCriticalMockOverlay = computed(() => eventCriticalMockOverlayEnabled.value && !showEventCriticalOverlay.value);
const eventFloatingAlertMuted = computed(() => eventAlertNowMs.value < eventAlertMutedUntil.value);
const eventFloatingAlertEligible = computed(() => {
    const level = text(eventWindowState.value.emergency_level, 'none').toLowerCase();
    return level === 'high' && !eventCriticalOverlayActive.value && !eventCurrentAlertHidden.value;
});
const showEventFloatingAlert = computed(() => !eventCurrentAlertHidden.value &&
    (eventFloatingAlertEligible.value || eventFloatingAlertHovered.value || Boolean(eventAlertDragging.value)));
const eventFloatingTitle = computed(() => `EVENT WATCH · ${text(eventWindowState.value.emergency_level, 'high').toUpperCase()}`);
const eventFloatingSubtitle = computed(() => {
    const eventType = text(eventWindowActive.value.event_type, 'event');
    const timeToEvent = daysText(Number(eventWindowActive.value.time_to_event_sec ?? 0) / 86400);
    const trust = text(eventWindowOverlay.value.ordinary_radar_trust, 'reduced');
    return `${eventType} in T-${timeToEvent} · radar trust ${trust}`;
});
const eventFloatingMessage = computed(() => {
    const codes = eventWindowReasonCodes.value;
    if (codes.some((code) => code.includes('inflation') || code.includes('nowcast'))) {
        return 'Inflation upside risk is building before release. Ordinary radar trend continuation is downgraded until release + 30m.';
    }
    if (codes.some((code) => code.includes('drawdown') || code.includes('market_dislocation'))) {
        return 'BTC market shock is being monitored. Ordinary radar trend continuation is downgraded until the shock is absorbed or confirmed.';
    }
    return `${text(eventWindowActive.value.title, 'Event risk')} is active. Ordinary radar trend continuation is downgraded until Event Watch validates the risk window.`;
});
const eventFloatingAlertStyle = computed(() => {
    const pos = eventAlertPosition.value;
    if (!pos)
        return {};
    return {
        left: `${pos.x}px`,
        top: `${pos.y}px`,
    };
});
const stages = computed(() => state.runs?.stages ?? []);
const auditReports = computed(() => store.reports.value);
const latestRun = computed(() => (state.runs?.latest ?? store.runLineage.value ?? {}));
const frozenFinalLineage = computed(() => {
    if (state.routeContext.isHistorical && state.selectedHistory?.run_lineage) {
        return state.selectedHistory.run_lineage;
    }
    return (state.dashboard?.run_lineage ?? store.runLineage.value ?? latestRun.value ?? {});
});
const frozenFinalCreatedAt = computed(() => firstPresent(frozenFinalLineage.value.created_at, state.dashboard?.created_at, state.dashboard?.updated_at));
const liveRuntimeFreshness = computed(() => ({
    snapshot_id: firstPresent(radarRuntimeHealth.value.snapshot_id, radarRuntimeDaemon.value.last_snapshot_id, radarRuntimePayload.value.snapshot_id),
    health_state: firstPresent(radarRuntimeHealth.value.health_state, radarRuntimeDaemon.value.health_state, radarRuntimeDaemon.value.status),
    runtime_fresh: firstPresent(radarRuntimeHealth.value.runtime_fresh, radarRuntimeDaemon.value.runtime_fresh),
    source_fresh: firstPresent(radarRuntimeHealth.value.source_fresh, radarRuntimeDaemon.value.source_fresh),
    source_freshness_state: firstPresent(radarRuntimeHealth.value.source_freshness_state, radarRuntimeDaemon.value.source_freshness_state),
    fresh_module_count: radarRuntimeHealth.value.fresh_module_count,
    expected_module_count: radarRuntimeHealth.value.expected_module_count,
    last_tick_age_sec: radarRuntimeDaemon.value.last_tick_age_sec,
}));
const runExecutionProfile = computed(() => text(state.activeRunJob?.execution_profile ??
    state.runResult?.execution_profile ??
    latestRun.value.execution_profile, state.llmRunEnabled ? 'full_with_llm' : 'fast_deterministic'));
const runLlmEnabled = computed(() => {
    const job = (state.activeRunJob ?? state.runResult ?? {});
    if (typeof job.llm_enabled === 'boolean')
        return job.llm_enabled;
    return runExecutionProfile.value !== 'fast_deterministic' && state.llmRunEnabled;
});
const runChainLabel = computed(() => runLlmEnabled.value ? 'P1 -> P2 -> P3 -> P4.5 -> LLM' : 'P1 -> P2 -> P3 -> P4.5');
const runWarnings = computed(() => (state.runs?.warnings ?? []));
const runErrors = computed(() => (state.runs?.errors ?? []));
const pipelineDefs = [
    { key: 'p1', code: 'P1', label: 'Collect', match: ['p1', 'collect'], runKey: 'collect_run_id' },
    { key: 'p2', code: 'P2', label: 'Radar', match: ['p2', 'radar'], runKey: 'p2_radar_run_id' },
    { key: 'p3', code: 'P3', label: 'Scoring', match: ['p3', 'scoring'], runKey: 'p3_run_id' },
    { key: 'p45', code: 'P4.5', label: 'Final Pack', match: ['p45', 'p4.5', 'final'], runKey: 'final_run_id' },
    { key: 'llm', code: 'LLM', label: 'Analyst', match: ['llm_analyst', 'llm analyst', 'analyst', 'llm'], runKey: 'llm_analyst_run_id' },
];
const runLineageEntries = computed(() => {
    const preferredOrder = [
        'collect_run_id',
        'p2_radar_run_id',
        'p3_run_id',
        'pack_id',
        'article_run_id',
        'final_run_id',
        'llm_research_run_id',
        'llm_analyst_run_id',
    ];
    const entries = preferredOrder
        .filter((key) => latestRun.value[key])
        .map((key) => ({ key, value: latestRun.value[key] }));
    for (const [key, value] of Object.entries(latestRun.value)) {
        if (preferredOrder.includes(key) || value === undefined || value === null || typeof value === 'object')
            continue;
        if (String(key).endsWith('_run_id') || key === 'runtime_mode' || key === 'created_at')
            entries.push({ key, value });
    }
    return entries;
});
const settingsLlm = computed(() => state.settings?.llm ?? {});
const settingsPayload = computed(() => (state.settings ?? {}));
const settingsApp = computed(() => (settingsPayload.value.app ?? {}));
const settingsRunDefaults = computed(() => (settingsPayload.value.run_defaults ?? {}));
const settingsLlmRouting = computed(() => (settingsPayload.value.llm_routing ?? {}));
const settingsLlmRuntimeDefaults = computed(() => (settingsLlmRouting.value.runtime_defaults ?? {}));
const settingsLlmProviders = computed(() => (settingsLlmRouting.value.providers ?? []));
const settingsLlmRoutes = computed(() => (settingsLlmRouting.value.p4_agent_routes ?? []));
const settingsLlmAvailableCount = computed(() => (settingsLlmRouting.value.available_providers ?? []).length);
const settingsAudit = computed(() => (settingsPayload.value.settings_audit ?? {}));
const settingsAuditEvents = computed(() => (settingsAudit.value.events ?? []));
const settingsWarnings = computed(() => (settingsPayload.value.warnings ?? []));
const settingsErrors = computed(() => (settingsPayload.value.errors ?? []));
const settingsProviderRows = computed(() => (settingsPayload.value.providers?.providers ?? []));
const settingsProviderHealthRows = computed(() => (settingsPayload.value.provider_health?.items ?? []));
const settingsProviderHealthById = computed(() => {
    const byId = {};
    for (const row of settingsProviderHealthRows.value)
        byId[text(row.provider_id)] = row;
    return byId;
});
const settingsTabs = [
    { id: 'llm', label: 'LLM Providers' },
    { id: 'keys', label: 'API Keys' },
    { id: 'data', label: 'Data Sources' },
    { id: 'radar', label: 'Radar & Alerts' },
    { id: 'run', label: 'Run Once' },
    { id: 'publish', label: 'Publish' },
    { id: 'storage', label: 'Storage' },
    { id: 'system', label: 'System' },
];
const settingsKeyRows = computed(() => {
    if (settingsProviderRows.value.length) {
        return settingsProviderRows.value
            .filter((row) => row.env_key)
            .map((row) => ({
            providerId: text(row.provider_id),
            key: text(row.env_key),
            enabled: row.configured === true,
            provider: text(row.name ?? row.provider_id),
            scope: text(row.category ?? row.status_policy),
            masked: text(row.masked_value, ''),
            status: text(row.status, row.configured === true ? 'configured' : 'disabled'),
            supportsTest: row.supports_test === true,
            health: settingsProviderHealthById.value[text(row.provider_id)] ?? {},
        }));
    }
    return [
        { providerId: 'deepseek', key: 'ONLYBTC_DEEPSEEK_API_KEY', enabled: settingsLlm.value.has_deepseek_key === true, provider: 'DeepSeek', scope: 'P4.5 research / analyst', masked: '', status: 'legacy', supportsTest: true, health: {} },
        { providerId: 'openai', key: 'ONLYBTC_OPENAI_API_KEY', enabled: settingsLlm.value.has_openai_key === true, provider: 'OpenAI', scope: 'fallback / validation', masked: '', status: 'legacy', supportsTest: true, health: {} },
        { providerId: 'qwen', key: 'ONLYBTC_QWEN_API_KEY', enabled: settingsLlm.value.has_qwen_key === true, provider: 'Qwen', scope: 'legacy optional', masked: '', status: 'legacy', supportsTest: true, health: {} },
        { providerId: 'volcano', key: 'ONLYBTC_VOLCANO_API_KEY', enabled: settingsLlm.value.has_volcano_key === true, provider: 'Volcano', scope: 'legacy optional', masked: '', status: 'legacy', supportsTest: true, health: {} },
        { providerId: 'kimi', key: 'ONLYBTC_KIMI_API_KEY', enabled: settingsLlm.value.has_kimi_key === true, provider: 'Kimi', scope: 'legacy optional', masked: '', status: 'legacy', supportsTest: true, health: {} },
    ];
});
const sourceHealth = computed(() => state.dataQuality?.source_health ?? {});
const qualityPayload = computed(() => (state.dataQuality?.data_quality ?? dataQuality.value ?? {}));
const metricCountAudit = computed(() => (state.dataQuality?.metric_count_audit ??
    qualityPayload.value.metric_count_audit ??
    {}));
const qualityContract = computed(() => (state.dataQuality?.contract_validation ?? contract.value ?? {}));
const qualityFreshnessCheck = computed(() => (qualityContract.value.freshness_check ?? {}));
const qualityWarnings = computed(() => (qualityContract.value.warnings ?? []));
const qualityChecks = computed(() => (qualityContract.value.checks ?? {}));
const sourceStatusCounts = computed(() => (sourceHealth.value.status_counts ?? {}));
const recentSourceRows = computed(() => (sourceHealth.value.recent_failed_sources ?? []).slice(0, 18));
const currentRunWarningRows = computed(() => (sourceHealth.value.current_run_warning_sources ?? []).slice(0, 8));
const historyFailedRows = computed(() => (sourceHealth.value.history_recent_failed_sources ?? []).slice(0, 12));
const evidenceItems = computed(() => state.evidence?.items ?? []);
const selectedSourceDetail = computed(() => (state.selectedSourceDetail ?? {}));
const selectedSourceAuthState = computed(() => (state.selectedSourceAuthState ?? {}));
const selectedSourceLastCapture = computed(() => (state.selectedSourceLastCapture ?? {}));
const selectedSourceActionResult = computed(() => (state.selectedSourceActionResult ?? {}));
const selectedSourceProfile = computed(() => (selectedSourceDetail.value.source ?? {}));
const selectedSourceMetadata = computed(() => (selectedSourceProfile.value.metadata ?? {}));
const selectedSourceFreshnessPolicy = computed(() => (selectedSourceMetadata.value.freshness_policy ?? {}));
const selectedSourceRuns = computed(() => (selectedSourceDetail.value.runs ?? []));
const selectedSourceRawObservations = computed(() => (selectedSourceDetail.value.raw_observations ?? []));
const selectedSourceMetrics = computed(() => (selectedSourceDetail.value.metrics ?? []));
const latestSourceRun = computed(() => selectedSourceRuns.value[0] ?? {});
const selectedSourceEvidence = computed(() => evidenceItems.value.filter((item) => String(item.source_id ?? '') === selectedSourceId.value));
const semiAutoSources = computed(() => {
    const known = [
        {
            source_id: 'bitbo-sth-lth-realized-price',
            automation_mode: 'semi_automated',
            requires_human_verified_profile: true,
            manual_reauth_required: false,
            profile_dir: 'cache/playwright-bitbo-profile',
            auth_state: 'unknown',
            last_verified_at: selectedSourceAuthState.value.last_verified_at,
            last_error: selectedSourceAuthState.value.last_error,
            affected_metrics: ['sth_cost_basis', 'lth_cost_basis'],
            radar_modules: ['onchain_valuation'],
        },
    ];
    const fromSourceRows = recentSourceRows.value
        .filter((row) => isSemiAutomatedSource(row))
        .map((row) => ({ ...row, automation_mode: row.automation_mode ?? 'semi_automated', auth_state: sourceAuthState(row) }));
    const byId = new Map();
    for (const row of [...known, ...fromSourceRows])
        byId.set(sourceId(row), row);
    return [...byId.values()];
});
const selectedSourceModules = computed(() => {
    const modules = new Set(selectedSourceEvidence.value.map((item) => text(item.radar_module, 'module')));
    return [...modules];
});
const selectedManualSource = computed(() => {
    const existing = semiAutoSources.value.find((row) => text(row.source_id) === selectedSourceId.value);
    return {
        ...(existing ?? {}),
        ...selectedSourceProfile.value,
        ...selectedSourceAuthState.value,
        source_id: selectedSourceId.value || text(existing?.source_id ?? selectedSourceProfile.value.source_id),
    };
});
const analystArticles = computed(() => state.articles?.llm_analyst_articles ?? []);
const selectedRadarModule = computed(() => state.selectedRadarDetail?.module ?? {});
const selectedRadarMetrics = computed(() => state.selectedRadarDetail?.metrics ?? []);
const selectedRadarMetric = computed(() => {
    const preferred = selectedRadarMetrics.value.find((metric) => text(metric.metric_id) === selectedRadarMetricId.value);
    return (preferred ?? selectedRadarMetrics.value[0] ?? {});
});
const selectedRadarTopMetrics = computed(() => selectedRadarMetrics.value
    .filter((metric) => metric.available !== false)
    .map((metric, index) => ({ metric, index }))
    .sort((left, right) => {
    const scoreDelta = radarMetricStrength(right.metric) - radarMetricStrength(left.metric);
    if (Math.abs(scoreDelta) > 0.000001)
        return scoreDelta;
    return Number(right.metric.quality_score ?? 0) - Number(left.metric.quality_score ?? 0);
})
    .slice(0, 10)
    .map(({ metric }) => metric));
const selectedRadarMetricStats = computed(() => {
    let support = 0;
    let pressure = 0;
    let mixed = 0;
    let quality = 0;
    for (const metric of selectedRadarMetrics.value) {
        const klass = radarMetricClass(metric);
        if (metric.fallback_used || metric.is_stale || metric.available === false)
            quality += 1;
        else if (['bull', 'bullish', 'positive'].includes(klass))
            support += 1;
        else if (['bear', 'bearish', 'negative'].includes(klass))
            pressure += 1;
        else
            mixed += 1;
    }
    return { support, pressure, mixed, quality };
});
const analystFallback = [
    { analyst_id: 'Macro Analyst', status: 'waiting', title: 'evidence pending' },
    { analyst_id: 'Liquidity Analyst', status: 'waiting', title: 'evidence pending' },
    { analyst_id: 'Microstructure Analyst', status: 'waiting', title: 'evidence pending' },
    { analyst_id: 'On-chain Analyst', status: 'waiting', title: 'evidence pending' },
];
const sourceSummary = computed(() => {
    const sourceIds = new Set(evidenceItems.value.map((item) => String(item.source_id ?? 'unknown')));
    return [...sourceIds].slice(0, 12);
});
const duplicateGroups = computed(() => {
    const groups = new Map();
    for (const item of evidenceItems.value) {
        const group = String(item.duplicate_group_id ?? item.metric_id ?? 'unknown');
        groups.set(group, [...(groups.get(group) ?? []), item]);
    }
    return [...groups.entries()]
        .filter(([, items]) => items.length > 1)
        .slice(0, 20)
        .map(([group, items]) => ({ group, items }));
});
const rawSourceConflicts = computed(() => {
    const dashboardConflicts = state.dashboard?.conflicting_evidence?.source_conflicts ?? [];
    const evidenceConflicts = state.evidence?.conflicting_evidence?.source_conflicts ?? [];
    const qualityConflicts = state.dataQuality?.conflicting_evidence?.source_conflicts ?? [];
    return [...asList(dashboardConflicts), ...asList(evidenceConflicts), ...asList(qualityConflicts)];
});
const multiSourceConflictRows = computed(() => {
    const rows = [];
    for (const item of rawSourceConflicts.value) {
        rows.push({ ...item, conflict_origin: 'source_conflict' });
    }
    for (const group of duplicateGroups.value) {
        const sources = [...new Set(group.items.map((item) => text(item.source_id)).filter((item) => item !== '-'))];
        if (sources.length <= 1 && group.items.length <= 1)
            continue;
        const selected = group.items.find((item) => item.role === 'primary_signal' || item.evidence_tier === 'primary') ?? group.items[0];
        rows.push({
            conflict_origin: 'duplicate_group',
            metric_id: selected.metric_id ?? group.group,
            radar_module: selected.radar_module,
            selected_source: selected.source_id,
            candidate_sources: sources,
            source_resolution: selected.source_resolution ?? selected.source_resolution_status ?? 'duplicate_group_weight_cap',
            conflict_type: 'definition_conflict',
            severity: sources.length > 1 ? 'medium' : 'low',
            selected_reason: `duplicate_group_id=${group.group}; effective score uses duplicate_adjustment and module weight`,
            evidence_id: selected.evidence_id,
            quality_score: selected.quality_score,
            metric_score: selected.metric_score,
            metric_effective_score: selected.metric_effective_score,
            fallback_used: selected.fallback_used,
            fallback_reason: selected.fallback_reason,
            items: group.items,
        });
    }
    for (const item of evidenceItems.value.filter((entry) => entry.fallback_used === true || entry.fallback_reason)) {
        rows.push({
            conflict_origin: 'fallback_resolution',
            metric_id: item.metric_id,
            radar_module: item.radar_module,
            selected_source: item.source_id,
            fallback_source: item.fallback_source_id ?? item.fallback_source,
            candidate_sources: [item.source_id, item.fallback_source_id ?? item.fallback_source].filter(Boolean),
            source_resolution: item.source_resolution ?? item.source_resolution_status ?? 'fallback_used',
            conflict_type: 'update_lag',
            severity: 'medium',
            selected_reason: item.fallback_reason ?? 'fallback used; selected source remains auditable',
            evidence_id: item.evidence_id,
            quality_score: item.quality_score,
            metric_score: item.metric_score,
            metric_effective_score: item.metric_effective_score,
            fallback_used: item.fallback_used,
            fallback_reason: item.fallback_reason,
        });
    }
    const seen = new Set();
    return rows.filter((row) => {
        const key = `${text(row.metric_id)}|${text(row.selected_source ?? row.source_id)}|${text(row.conflict_origin)}`;
        if (seen.has(key))
            return false;
        seen.add(key);
        return true;
    });
});
const conflictStats = computed(() => ({
    total: multiSourceConflictRows.value.length,
    high: multiSourceConflictRows.value.filter((row) => conflictSeverityClass(row) === 'bear').length,
    fallback: multiSourceConflictRows.value.filter((row) => row.fallback_used === true || row.fallback_reason).length,
    definition: multiSourceConflictRows.value.filter((row) => text(row.conflict_type).includes('definition')).length,
}));
const evidenceRunLineage = computed(() => (state.evidence?.run_lineage ?? store.runLineage.value ?? {}));
const selectedEvidence = computed(() => (state.selectedEvidenceDetail?.evidence ?? {}));
const selectedEvidenceHistory = computed(() => (selectedEvidence.value.history_context ?? {}));
const evidenceModules = computed(() => {
    const modules = new Set();
    for (const item of evidenceItems.value) {
        const moduleId = String(item.radar_module ?? item.module_id ?? '');
        if (moduleId)
            modules.add(moduleId);
    }
    return [...modules].sort();
});
const evidenceBuckets = computed(() => {
    const buckets = new Set();
    for (const item of evidenceItems.value) {
        const bucket = String(item.score_bucket ?? item.direction ?? '');
        if (bucket)
            buckets.add(bucket);
    }
    return [...buckets].sort();
});
const filteredEvidenceItems = computed(() => evidenceItems.value.filter((item) => {
    const moduleId = String(item.radar_module ?? item.module_id ?? '');
    const bucket = String(item.score_bucket ?? item.direction ?? '');
    return ((evidenceModuleFilter.value === 'all' || moduleId === evidenceModuleFilter.value) &&
        (evidenceBucketFilter.value === 'all' || bucket === evidenceBucketFilter.value));
}));
const evidenceStats = computed(() => {
    const stats = {
        total: evidenceItems.value.length,
        positive: 0,
        negative: 0,
        zero: 0,
        stale: 0,
        fallback: 0,
        unavailable: 0,
    };
    for (const item of evidenceItems.value) {
        const bucket = String(item.score_bucket ?? '').toLowerCase();
        const direction = String(item.direction ?? '').toLowerCase();
        if (bucket.includes('positive') || direction.includes('bull'))
            stats.positive += 1;
        else if (bucket.includes('negative') || direction.includes('bear'))
            stats.negative += 1;
        else
            stats.zero += 1;
        if (item.is_stale === true || String(item.freshness_status ?? '').includes('stale'))
            stats.stale += 1;
        if (item.fallback_used === true || item.fallback_reason)
            stats.fallback += 1;
        if (item.available === false)
            stats.unavailable += 1;
    }
    return stats;
});
const topologyModules = computed(() => store.radarModules.value.slice(0, 14).map((module, index) => ({
    module,
    index,
    direction: moduleDisplayState(module),
})));
const dynamicLinks = computed(() => topologyModules.value.map((node) => {
    const moduleId = moduleName(node.module);
    const point = displayNodePoint(moduleId, node.index);
    const kind = directionClass(node.direction);
    const depth = nodeDepth(point);
    return {
        moduleId,
        kind,
        path: linkPath(point),
        opacity: depth.opacity,
        strokeWidth: depth.strokeWidth,
    };
}));
const decisionReasons = computed(() => {
    if (hasCockpit.value) {
        const summary = (btcCockpit.value.ui_summary ?? {});
        return [
            summary.fast_read,
            summary.confirmation_read,
            summary.why_not_strong,
            summary.next_trigger,
        ].filter(Boolean).slice(0, 4);
    }
    const reasons = decision.value.why_not_strong;
    const list = Array.isArray(reasons) ? reasons : [];
    const fallback = [
        decision.value.conclusion_sentence,
        'Short-term support and medium-term pressure coexist; direction consensus is not strong enough.',
        'Zero-score metrics are high, so strength cannot be upgraded to a strong one-sided view.',
        invalidationRules.value[0]?.title ?? confirmationRules.value[0]?.title,
    ];
    return [...list, ...fallback].filter(Boolean).slice(0, 4);
});
const finalViewText = computed(() => hasCockpit.value
    ? text(btcCockpit.value.headline_state, 'neutral')
    : state.dashboard?.final_view_cn ?? state.dashboard?.final_view ?? '-');
const tradePermissionText = computed(() => text(btcCockpit.value.trade_permission ?? decision.value.trade_permission, 'watch_only'));
const cockpitUiSummary = computed(() => (btcCockpit.value.ui_summary ?? {}));
const cockpitHorizon = computed(() => (btcCockpit.value.horizon ?? {}));
const hasRuntimeCockpit = computed(() => text(radarRuntimeCockpit.value.schema_version, '') === 'p45.radar_runtime_cockpit.v2');
const runtimeCockpitScores = computed(() => (radarRuntimeCockpit.value.scores ?? {}));
const cockpitSummaryText = computed(() => {
    if (!hasCockpit.value)
        return text(decision.value.conclusion_sentence, 'Waiting for P4.5 decision card');
    return text(cockpitUiSummary.value.fast_read, `${text(btcCockpit.value.headline_state, 'neutral')} · ${text(btcCockpit.value.trend_quality, 'unconfirmed')}`);
});
const cockpitScores = computed(() => (btcCockpit.value.scores ?? {}));
const cockpitFastScore = computed(() => {
    const raw = Number(hasRuntimeCockpit.value
        ? runtimeCockpitScores.value.fast_net_score ?? radarRuntimeCockpit.value.fast_net_score ?? 0
        : cockpitScores.value.fast_net_score ?? 0);
    if (!Number.isFinite(raw))
        return '0.00';
    return `${raw >= 0 ? '+' : ''}${raw.toFixed(2)}`;
});
const cockpitReadoutLabel = computed(() => (hasRuntimeCockpit.value ? 'Runtime fast' : 'Fast layer'));
const cockpitFastDirection = computed(() => hasRuntimeCockpit.value
    ? signedDirection(Number(runtimeCockpitScores.value.fast_net_score ?? radarRuntimeCockpit.value.fast_net_score ?? 0))
    : text(cockpitHorizon.value['4h']?.direction ?? btcCockpit.value.btc_direction, 'neutral'));
const cockpitFastStage = computed(() => hasRuntimeCockpit.value
    ? text(radarRuntimeCockpit.value.headline_stage, 'nowcast')
    : text(cockpitHorizon.value['4h']?.stage ?? btcCockpit.value.trend_phase, 'none'));
const cockpitPressureText = computed(() => text(cockpitUiSummary.value.main_pressure, 'No dominant pressure module.'));
const cockpitSupportText = computed(() => text(cockpitUiSummary.value.main_support, 'No dominant support module.'));
const cockpitConflictText = computed(() => text(cockpitUiSummary.value.why_not_strong, 'Waiting for acceptance or conflict resolution.'));
const primaryCockpitTrigger = computed(() => {
    const triggers = btcCockpit.value.next_confirmation_triggers;
    return Array.isArray(triggers) ? text(triggers[0], '等待确认条件') : primaryConfirmationTitle.value;
});
const primaryCockpitInvalidation = computed(() => {
    const triggers = btcCockpit.value.next_invalidation_triggers;
    return Array.isArray(triggers) ? text(triggers[0], '等待反证条件') : primaryInvalidationTitle.value;
});
const dataQualityLabel = computed(() => text(dataQuality.value.data_quality_level ??
    dataQuality.value.quality_level ??
    dataQuality.value.status ??
    contract.value.status, 'quality'));
const contractStatus = computed(() => text(contract.value.status, 'unknown'));
const alertLevel = computed(() => String(alerts.value[0]?.level ?? 'watch').toLowerCase());
const alertRunLineage = computed(() => (state.alerts?.run_lineage ?? store.runLineage.value ?? {}));
const alertStats = computed(() => {
    const stats = {
        total: alerts.value.length,
        critical: 0,
        warning: 0,
        info: 0,
        cooling: 0,
        active: 0,
        evidence: 0,
    };
    for (const alert of alerts.value) {
        const level = String(alert.level ?? '').toLowerCase();
        const status = String(alert.state ?? '').toLowerCase();
        if (level.includes('critical') || level.includes('high'))
            stats.critical += 1;
        else if (level.includes('warning') || level.includes('watch'))
            stats.warning += 1;
        else
            stats.info += 1;
        if (status.includes('cool'))
            stats.cooling += 1;
        else
            stats.active += 1;
        const evidenceCount = Number(alert.evidence_count ?? 0);
        if (Number.isFinite(evidenceCount))
            stats.evidence += evidenceCount;
    }
    return stats;
});
const qualityScoreText = computed(() => {
    const score = Number(qualityPayload.value.avg_metric_quality ?? dataQuality.value.avg_metric_quality ?? dataQuality.value.quality_score);
    if (!Number.isFinite(score))
        return '-';
    return score.toFixed(4);
});
const qualityBoundaryText = computed(() => {
    const availableMissing = Number(qualityFreshnessCheck.value.available_metric_missing_freshness_count ?? 0);
    const unavailableMissing = Number(qualityFreshnessCheck.value.unavailable_metric_missing_freshness_count ?? qualityPayload.value.missing_freshness_count ?? 0);
    if (availableMissing > 0)
        return `${availableMissing} available metrics missing freshness; review before publishing.`;
    if (unavailableMissing > 0)
        return `${unavailableMissing} unavailable metrics missing freshness; treated as warning, not a blocking failure.`;
    return 'Available metrics have required freshness fields.';
});
const sourceHealthScopeText = computed(() => {
    const currentFailed = Number(sourceHealth.value.current_run_failed_count ?? 0);
    const currentWarning = Number(sourceHealth.value.current_run_warning_count ?? 0);
    const historyFailed = Number(sourceHealth.value.history_recent_failed_count ?? 0);
    return `current run failures ${currentFailed} · current warnings ${currentWarning} · history failures ${historyFailed}`;
});
const metricCountAuditText = computed(() => text(metricCountAudit.value.count_explanation, 'P1 counts collected metrics; P4.5 counts scored evidence records used by the report contract.'));
const alertSummaryText = computed(() => {
    if (!alerts.value.length)
        return 'No active alerts in this run; continue monitoring invalidation and confirmation rules.';
    const top = alerts.value[0];
    return `${text(top.level, 'watch')} · ${text(top.state, 'active')} · ${text(top.summary, 'Waiting for alert summary')}`;
});
const scorePercent = computed(() => {
    const raw = hasCockpit.value ? btcCockpit.value.confidence_score : decision.value.confidence ?? aggregation.value.confidence ?? 0;
    const confidence = Number(raw);
    if (!Number.isFinite(confidence))
        return '0%';
    const percent = confidence > 1 ? confidence : confidence * 100;
    return `${Math.max(0, Math.min(100, Math.round(percent)))}%`;
});
const scoreRingStyle = computed(() => {
    const raw = hasCockpit.value ? btcCockpit.value.confidence_score : decision.value.confidence ?? aggregation.value.confidence ?? 0;
    const confidence = Number(raw);
    const value = confidence > 1 ? confidence : confidence * 100;
    const percent = Math.max(0, Math.min(100, Number.isFinite(value) ? Math.round(value) : 0));
    return { '--score-percent': `${percent}%` };
});
const btcNodeClass = computed(() => {
    const classes = [directionClass(hasCockpit.value ? btcCockpit.value.headline_state : state.dashboard?.final_view)];
    const contractBad = !['passed', 'ok', 'pass'].includes(contractStatus.value.toLowerCase());
    const qualityBad = ['bad', 'failed', 'critical'].some((item) => dataQualityLabel.value.toLowerCase().includes(item));
    if (alertLevel.value.includes('critical'))
        classes.push('pulse-critical');
    else if (alertLevel.value.includes('high') || alertLevel.value.includes('warning'))
        classes.push('pulse-warning');
    if (contractBad || qualityBad)
        classes.push('pulse-quality');
    return classes;
});
const primaryInvalidationTitle = computed(() => text(invalidationRules.value[0]?.title, '等待反证条件'));
const primaryConfirmationTitle = computed(() => text(confirmationRules.value[0]?.title, '等待确认条件'));
const topAlert = computed(() => alerts.value[0]);
const eventWindowRows = computed(() => events.value
    .map((row) => ({
    row,
    payload: (row.payload ?? {}),
    daysUntil: Number((row.payload ?? {}).days_until ?? row.value ?? Number.POSITIVE_INFINITY),
}))
    .sort((left, right) => left.daysUntil - right.daysUntil));
const halvingStats = computed(() => ({
    days: metricValue('btc_halving_estimated_days'),
    height: metricValue('btc_block_height'),
    blocks: metricValue('btc_halving_blocks_remaining'),
}));
const runningStageText = computed(() => {
    if (state.running)
        return `running · ${runChainLabel.value}`;
    const failed = stages.value.find((stage) => String(stage.status ?? '').toLowerCase().includes('fail'));
    if (failed)
        return `failed · ${text(failed.label ?? failed.stage_id)}`;
    const degraded = stages.value.find((stage) => String(stage.status ?? '').toLowerCase().includes('error'));
    if (degraded)
        return `degraded · ${text(degraded.label ?? degraded.stage_id)}`;
    return `ready · ${stages.value.length || 0} stages`;
});
const runHealthClass = computed(() => {
    if (state.running)
        return 'mixed';
    if (stages.value.some((stage) => String(stage.status ?? '').toLowerCase().includes('fail')))
        return 'bear';
    if (stages.value.some((stage) => String(stage.status ?? '').toLowerCase().includes('error')))
        return 'quality';
    return 'bull';
});
const pipelineNodes = computed(() => {
    const nodes = pipelineDefs.map((definition, index) => {
        const stage = findPipelineStage(definition.match);
        const stateName = pipelineStageState(stage, index);
        return {
            ...definition,
            index,
            stage,
            state: stateName,
            icon: pipelineStateIcon(stateName),
            runId: pipelineRunId(definition.runKey, stage),
            report: stage ? stageReport(stage) : {},
        };
    });
    return nodes;
});
const pipelineActive = computed(() => state.running || pipelineNodes.value.some((node) => node.state === 'active'));
const pipelineProgressPercent = computed(() => {
    if (!pipelineNodes.value.length)
        return 0;
    if (!stages.value.length && !pipelineActive.value)
        return 0;
    const progressStates = new Set(['done', 'degraded', 'failed', 'active']);
    const furthestIndex = pipelineNodes.value.reduce((maxIndex, node) => {
        return progressStates.has(node.state) ? Math.max(maxIndex, node.index) : maxIndex;
    }, -1);
    if (furthestIndex < 0)
        return 0;
    const maxUnits = Math.max(1, pipelineNodes.value.length - 1);
    const maxLineWidth = 80;
    return clamp((furthestIndex / maxUnits) * maxLineWidth, 0, maxLineWidth);
});
const pipelineProgressStyle = computed(() => ({ '--pipeline-progress': `${pipelineProgressPercent.value}%` }));
const pipelineHeartbeatText = computed(() => (pipelineActive.value ? 'audit stream active' : 'audit stream idle'));
const analystCards = computed(() => {
    const cards = analystArticles.value.length ? analystArticles.value : analystFallback;
    return cards.slice(0, 4);
});
const articleRunLineage = computed(() => {
    if (state.routeContext.isHistorical && state.selectedHistory?.run_lineage) {
        return state.selectedHistory.run_lineage;
    }
    return (state.articles?.run_lineage ?? store.runLineage.value ?? {});
});
const articleFinalPayload = computed(() => {
    if (state.routeContext.isHistorical && state.selectedHistory?.final) {
        return state.selectedHistory.final;
    }
    return {};
});
const articleResearch = computed(() => (articleFinalPayload.value.research_article ??
    state.articles?.research_article ??
    {}));
const articlePublish = computed(() => (articleFinalPayload.value.publish_article ??
    state.articles?.publish_article ??
    {}));
const articleLlmResearch = computed(() => (state.articles?.llm_research ?? {}));
const articleAnalystRows = computed(() => {
    const llmRows = state.articles?.llm_analyst_articles ?? [];
    const deterministicRows = state.articles?.analyst_articles ?? [];
    return (llmRows.length ? llmRows : deterministicRows).slice(0, 4);
});
const articleHistoryRows = computed(() => {
    const rows = (state.articleHistory?.items ?? []).slice(0, 20);
    if (rows.length)
        return rows;
    const latest = (state.runs?.latest ?? {});
    return latest.final_run_id ? [latest] : [];
});
const historyPayload = computed(() => (state.selectedHistory ?? {}));
const historyFinal = computed(() => (historyPayload.value.final ?? {}));
const historyDecision = computed(() => (historyFinal.value.decision_card ?? {}));
const historyAggregation = computed(() => (historyFinal.value.aggregation_audit ?? {}));
const historyLineage = computed(() => (historyPayload.value.run_lineage ?? {}));
const historyReports = computed(() => (historyPayload.value.audit_reports?.reports ?? []));
const historyResearch = computed(() => (historyFinal.value.research_article ?? {}));
const historyPublish = computed(() => (historyFinal.value.publish_article ?? {}));
const historyLlm = computed(() => (historyPayload.value.llm_research ?? {}));
const historyAnalysts = computed(() => (historyPayload.value.analyst_articles ?? historyFinal.value.analyst_articles ?? []).slice(0, 4));
const historyLineageEntries = computed(() => Object.entries(historyLineage.value)
    .filter(([, value]) => value !== undefined && value !== null && typeof value !== 'object')
    .map(([key, value]) => ({ key, value })));
const articleStatusText = computed(() => {
    const publishStatus = articlePublish.value.safe_to_publish === true ? 'published' : 'draft';
    const fallback = articleFinalPayload.value.fallback_used === true ? 'fallback generated' : publishStatus;
    return text(articleFinalPayload.value.article_status ?? articlePublish.value.status ?? fallback, publishStatus);
});
const articleRuntimeMode = computed(() => text(articleFinalPayload.value.runtime_mode ??
    articleLlmResearch.value.runtime_mode ??
    articleRunLineage.value.runtime_mode, 'deterministic'));
const articleEvidenceCitations = computed(() => {
    const ids = new Set();
    collectEvidenceIds(articleResearch.value, ids);
    collectEvidenceIds(articlePublish.value, ids);
    collectEvidenceIds(articleLlmResearch.value, ids);
    for (const item of articleAnalystRows.value)
        collectEvidenceIds(item, ids);
    return [...ids].slice(0, 36).map((id) => {
        const evidence = evidenceItems.value.find((item) => String(item.evidence_id ?? '') === id);
        return { id, evidence };
    });
});
const overviewSupportDrivers = computed(() => asList(aggregation.value.support_drivers).slice(0, 8));
const overviewPressureDrivers = computed(() => asList(aggregation.value.pressure_drivers).slice(0, 8));
const overviewScoreComponents = computed(() => (aggregation.value.score_components ?? {}));
const overviewScoreNormalization = computed(() => (aggregation.value.score_normalization ?? {}));
const overviewRunLineage = computed(() => (state.overview?.run_lineage ?? store.runLineage.value ?? {}));
const overviewDataBoundary = computed(() => {
    const article = state.overview?.research_article ?? {};
    return asList(article.data_boundary).map((item) => text(item)).slice(0, 6);
});
const overviewWatchRows = computed(() => [
    ...invalidationRules.value.slice(0, 3).map((rule) => ({ kind: 'invalidation', rule })),
    ...confirmationRules.value.slice(0, 2).map((rule) => ({ kind: 'confirmation', rule })),
]);
const invalidationRunLineage = computed(() => (state.invalidation?.run_lineage ?? store.runLineage.value ?? {}));
const invalidationWorkbench = computed(() => (state.invalidation ?? {}));
const hasInvalidationWorkbench = computed(() => text(invalidationWorkbench.value.schema_version, '') === 'p45.invalidation_workbench.v2');
const workbenchCurrentThesis = computed(() => (invalidationWorkbench.value.current_thesis ?? {}));
const workbenchScores = computed(() => (invalidationWorkbench.value.scores ?? {}));
const workbenchBtcResponse = computed(() => (invalidationWorkbench.value.btc_response ?? {}));
const workbenchPriceAcceptance = computed(() => (workbenchBtcResponse.value.price_acceptance ?? {}));
const workbenchResidual = computed(() => (workbenchBtcResponse.value.residual ?? {}));
const workbenchMicroResponse = computed(() => (workbenchBtcResponse.value.micro_response ?? {}));
const workbenchRuleGroups = computed(() => (invalidationWorkbench.value.rule_groups ?? {}));
const workbenchEvidenceMatrix = computed(() => asList(invalidationWorkbench.value.module_evidence_matrix).slice(0, 30));
const workbenchTimeline = computed(() => asList(invalidationWorkbench.value.timeline).slice(0, 20));
const workbenchTriggeredRules = computed(() => asList(invalidationWorkbench.value.triggered_rules).slice(0, 8));
const workbenchArmedRules = computed(() => asList(invalidationWorkbench.value.armed_rules).slice(0, 8));
const workbenchBlockedRules = computed(() => asList(invalidationWorkbench.value.blocked_rules).slice(0, 8));
const workbenchConfirmationLane = computed(() => [
    ...asList(workbenchRuleGroups.value.confirm_current_view),
    ...asList(workbenchRuleGroups.value.upgrade_scenarios),
]);
const workbenchInvalidationLane = computed(() => [
    ...asList(workbenchRuleGroups.value.refute_current_view),
    ...asList(workbenchRuleGroups.value.break_neutral_scenarios),
    ...asList(workbenchRuleGroups.value.downgrade_scenarios),
]);
const invalidationStats = computed(() => ({
    invalidation: invalidationRules.value.length,
    confirmation: confirmationRules.value.length,
    finalView: text(workbenchCurrentThesis.value.btc_direction ?? state.invalidation?.final_view ?? state.dashboard?.final_view, 'watch'),
    horizonCount: horizons.value.length,
}));
const fullscreenPages = new Set(['evidence', 'article', 'quality', 'logs', 'history', 'source', 'radar']);
const pageTitle = computed(() => {
    const labels = {
        topology: 'Dashboard',
        eventWatchtower: 'Event Watchtower',
        overview: 'BTC Overview',
        radar: 'Radar Detail',
        evidence: 'Evidence',
        article: 'Article',
        alerts: 'Alerts',
        invalidation: 'Invalidation',
        quality: 'Data Quality',
        source: 'Source Detail',
        conflict: 'Conflict',
        logs: 'Run Logs',
        history: 'History Replay',
        settings: 'Settings',
    };
    return labels[activePage.value] ?? 'Dashboard';
});
const routeModeLabel = computed(() => (state.routeContext.isHistorical ? 'history replay' : 'latest run'));
const pageShellClass = computed(() => ({
    'drawer-closed': !drawerOpen.value,
    'page-fullscreen': pageFullscreen.value,
}));
onMounted(async () => {
    applyRouteFromUrl();
    loadRadarLayout();
    loadEventAlertPosition();
    loadEventAlertMute();
    loadEventWindowVisibilityState();
    eventAlertClockTimer = window.setInterval(() => {
        eventAlertNowMs.value = Date.now();
    }, 1000);
    eventWindowLiveTimer = window.setInterval(() => {
        void refreshEventWindowLive();
    }, 15000);
    window.addEventListener('keydown', handleGlobalKeydown);
    window.addEventListener('popstate', applyRouteFromUrl);
    await store.refreshLatest();
    const restoredJob = await store.resumeActiveRunJob();
    if (restoredJob && state.running)
        activePage.value = 'logs';
    await hydrateRouteSelection();
    await ensureDefaultRadarDetail();
    await nextTick();
});
watch(activePage, async (page) => {
    if (!syncingRoute)
        syncRouteToUrl();
    if (page === 'radar')
        await ensureDefaultRadarDetail();
    if (page === 'eventWatchtower')
        await refreshEventWindowLive();
});
function signedDirection(score) {
    if (!Number.isFinite(score) || Math.abs(score) < 0.1)
        return 'neutral';
    return score > 0 ? 'bullish' : 'bearish';
}
watch(() => ({
    final: state.routeContext.final_run_id,
    pack: state.routeContext.pack_id,
    module: state.routeContext.module_id,
    evidence: state.routeContext.evidence_id,
    source: state.routeContext.source_id,
    analyst: state.routeContext.analyst_id,
    historical: state.routeContext.isHistorical,
    fullscreen: pageFullscreen.value,
}), () => {
    if (!syncingRoute)
        syncRouteToUrl();
});
onBeforeUnmount(() => {
    stopDrag();
    if (eventAlertClockTimer)
        window.clearInterval(eventAlertClockTimer);
    if (eventWindowLiveTimer)
        window.clearInterval(eventWindowLiveTimer);
    window.removeEventListener('keydown', handleGlobalKeydown);
    window.removeEventListener('popstate', applyRouteFromUrl);
});
async function refreshEventWindowLive() {
    if (eventWindowLiveRefreshInFlight || state.routeContext.isHistorical)
        return;
    eventWindowLiveRefreshInFlight = true;
    try {
        await store.refreshEventWindowLatest();
    }
    finally {
        eventWindowLiveRefreshInFlight = false;
    }
}
function text(value, fallback = '-') {
    if (value === null || value === undefined || value === '')
        return fallback;
    if (typeof value === 'number')
        return Number.isInteger(value) ? `${value}` : value.toFixed(4);
    if (Array.isArray(value))
        return value.join(', ');
    if (typeof value === 'object')
        return JSON.stringify(value);
    return repairMojibake(String(value));
}
function parseEventDate(value) {
    const raw = text(value, '').trim();
    if (!raw)
        return null;
    const dateOnly = raw.match(/^\d{4}-\d{2}-\d{2}/)?.[0];
    const parsed = new Date(raw);
    if (Number.isFinite(parsed.getTime()))
        return parsed;
    if (dateOnly) {
        const normalized = new Date(`${dateOnly}T00:00:00Z`);
        if (Number.isFinite(normalized.getTime()))
            return normalized;
    }
    return null;
}
function eventShortLabel(event) {
    const eventType = text(event.event_type ?? event.type ?? event.category, 'event').toUpperCase();
    if (eventType.includes('FOMC'))
        return 'FOMC';
    if (eventType.includes('NFP') || eventType.includes('PAYROLL'))
        return 'NFP';
    if (eventType.includes('PCE'))
        return 'PCE';
    if (eventType.includes('CPI'))
        return 'CPI';
    if (eventType.includes('SPEECH'))
        return 'FED';
    return eventType.replace(/[^A-Z0-9]/g, '').slice(0, 4) || 'EVT';
}
function eventImportanceRank(event) {
    const value = text(event.importance ?? event.impact ?? event.level, '').toLowerCase();
    if (['critical', 'red', 'high'].some((key) => value.includes(key)))
        return 3;
    if (['medium', 'yellow', 'watch', 'mixed'].some((key) => value.includes(key)))
        return 2;
    if (['low', 'normal'].some((key) => value.includes(key)))
        return 1;
    return 0;
}
function eventCalendarTone(event) {
    const rank = eventImportanceRank(event);
    if (rank >= 3)
        return 'bear';
    if (rank === 2)
        return 'mixed';
    if (rank === 1)
        return 'bull';
    return 'quality';
}
function maskedSecret(enabled) {
    return enabled ? 'configured · ********' : 'not configured';
}
function hasSettingsKeyDraft(key) {
    return Boolean(String(settingsKeyInputs[String(key ?? '')] ?? '').trim());
}
function settingsKeyRowClass(row) {
    if (row.enabled)
        return 'bull';
    if (row.status === 'missing_required' || row.status === 'provider_locked')
        return 'mixed';
    return 'neutral';
}
async function saveSettingsKey(row) {
    const key = String(row.key ?? '');
    const value = String(settingsKeyInputs[key] ?? '').trim();
    if (!key || !value) {
        settingsKeyError.value = 'Enter a key before saving.';
        settingsKeyMessage.value = '';
        return;
    }
    settingsKeySaving.value = key;
    settingsKeyError.value = '';
    settingsKeyMessage.value = '';
    try {
        await api.updateSettingsEnv({ [key]: value });
        settingsKeyInputs[key] = '';
        settingsKeyMessage.value = `${row.provider} saved · settings reloaded`;
        await store.refreshLatest();
    }
    catch (err) {
        settingsKeyError.value = err instanceof Error ? err.message : 'Failed to save settings.';
    }
    finally {
        settingsKeySaving.value = '';
    }
}
function providerHealthStatus(row) {
    return text(row.health.status, 'untested');
}
function providerHealthMeta(row) {
    const testedAt = text(row.health.last_tested_at, '');
    const latency = row.health.latency_ms === null || row.health.latency_ms === undefined ? '' : `${row.health.latency_ms}ms`;
    const error = text(row.health.error_message, '');
    return [latency, testedAt ? timestampText(testedAt) : '', error].filter(Boolean).join(' · ') || 'not tested';
}
async function testSettingsProvider(row) {
    if (!row.supportsTest) {
        settingsKeyError.value = `${row.provider} health test is not integrated yet.`;
        settingsKeyMessage.value = '';
        return;
    }
    settingsProviderTesting.value = row.providerId;
    settingsKeyError.value = '';
    settingsKeyMessage.value = '';
    try {
        const result = await api.testProviderHealth(row.providerId);
        settingsKeyMessage.value = `${row.provider} test ${text(result.status, 'completed')}`;
        await store.refreshLatest();
    }
    catch (err) {
        settingsKeyError.value = err instanceof Error ? err.message : 'Provider test failed.';
    }
    finally {
        settingsProviderTesting.value = '';
    }
}
function settingSourceLabel(value, fallback = '.env / default') {
    return value === null || value === undefined || value === '' ? 'default' : fallback;
}
function repairMojibake(value) {
    if (!/[ÃÂâåçèéïã¼½¿]/.test(value))
        return value;
    if ([...value].some((char) => char.charCodeAt(0) > 255))
        return value;
    try {
        const bytes = Uint8Array.from([...value].map((char) => char.charCodeAt(0)));
        const decoded = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
        return decoded.includes('\uFFFD') ? value : decoded;
    }
    catch {
        return value;
    }
}
function navigateTo(page, options = {}) {
    if (page === 'evidence' && !options.keepEvidenceDetail) {
        closeEvidenceDetail();
    }
    activePage.value = page;
}
async function goDashboard() {
    pageFullscreen.value = false;
    drawerOpen.value = true;
    if (state.routeContext.isHistorical) {
        store.exitHistoryMode();
        state.routeContext.module_id = '';
        state.routeContext.evidence_id = '';
        state.routeContext.source_id = '';
        state.routeContext.analyst_id = '';
        await store.refreshLatest();
    }
    activePage.value = 'topology';
}
function closeDetailPage() {
    if (activePage.value === 'evidence' && state.selectedEvidenceDetail) {
        closeEvidenceDetail();
        return;
    }
    goDashboard();
}
function togglePageFullscreen() {
    if (!fullscreenPages.has(activePage.value))
        return;
    pageFullscreen.value = !pageFullscreen.value;
    if (pageFullscreen.value)
        drawerOpen.value = false;
}
function syncRouteToUrl() {
    const params = new URLSearchParams();
    if (activePage.value !== 'topology')
        params.set('page', activePage.value);
    if (state.routeContext.final_run_id)
        params.set('final_run_id', state.routeContext.final_run_id);
    if (state.routeContext.pack_id)
        params.set('pack_id', state.routeContext.pack_id);
    if (state.routeContext.module_id)
        params.set('module_id', state.routeContext.module_id);
    if (state.routeContext.evidence_id)
        params.set('evidence_id', state.routeContext.evidence_id);
    if (state.routeContext.source_id)
        params.set('source_id', state.routeContext.source_id);
    if (state.routeContext.analyst_id)
        params.set('analyst_id', state.routeContext.analyst_id);
    if (state.routeContext.isHistorical)
        params.set('mode', 'history');
    if (pageFullscreen.value)
        params.set('fullscreen', '1');
    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`;
    if (nextUrl !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
        window.history.replaceState({}, '', nextUrl);
    }
}
function applyRouteFromUrl() {
    syncingRoute = true;
    try {
        const params = new URLSearchParams(window.location.search);
        const requestedPage = params.get('page');
        if (requestedPage && validPageIds.has(requestedPage))
            activePage.value = requestedPage;
        state.routeContext.final_run_id = params.get('final_run_id') ?? state.routeContext.final_run_id;
        state.routeContext.pack_id = params.get('pack_id') ?? state.routeContext.pack_id;
        state.routeContext.module_id = params.get('module_id') ?? state.routeContext.module_id;
        state.routeContext.evidence_id = params.get('evidence_id') ?? state.routeContext.evidence_id;
        state.routeContext.source_id = params.get('source_id') ?? state.routeContext.source_id;
        state.routeContext.analyst_id = params.get('analyst_id') ?? state.routeContext.analyst_id;
        const historyCapablePage = ['history', 'article'].includes(String(requestedPage ?? activePage.value));
        state.routeContext.isHistorical = params.get('mode') === 'history' && historyCapablePage;
        pageFullscreen.value = params.get('fullscreen') === '1';
        drawerOpen.value = !pageFullscreen.value;
    }
    finally {
        syncingRoute = false;
    }
}
async function hydrateRouteSelection() {
    const context = state.routeContext;
    if (context.isHistorical && context.final_run_id)
        await store.loadHistory(context.final_run_id);
    if (context.module_id) {
        selectedModuleId.value = context.module_id;
        await store.loadRadarDetail(context.module_id);
    }
    if (context.evidence_id) {
        selectedEvidenceId.value = context.evidence_id;
        await store.loadEvidenceDetail(context.evidence_id);
    }
    else if (activePage.value === 'evidence') {
        closeEvidenceDetail();
    }
    if (context.source_id) {
        selectedSourceId.value = context.source_id;
        await store.loadSourceDetail(context.source_id);
    }
}
function articleText(value, fallback = '-') {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
        const row = value;
        return text(row.body ?? row.article ?? row.executive_summary ?? row.summary ?? row.title, fallback);
    }
    return text(value, fallback);
}
function articleParagraphs(value, fallback = '-') {
    return articleText(value, fallback)
        .split(/\n+/)
        .map((line) => line.replace(/^#{1,4}\s*/, '').trim())
        .filter(Boolean)
        .slice(0, 18);
}
function collectEvidenceIds(value, ids) {
    if (!value)
        return;
    if (typeof value === 'string') {
        for (const match of value.matchAll(/p3-score-[A-Za-z0-9_-]+(?:-[A-Za-z0-9_]+)*/g)) {
            ids.add(match[0]);
        }
        return;
    }
    if (Array.isArray(value)) {
        for (const item of value)
            collectEvidenceIds(item, ids);
        return;
    }
    if (typeof value === 'object') {
        for (const item of Object.values(value))
            collectEvidenceIds(item, ids);
    }
}
function articleTitle(article, fallback = 'P4.5 Research Article') {
    return text(article.title ?? article.headline, fallback);
}
function citationLabel(id, evidence) {
    return text(evidence?.metric_id ?? id.split('-').slice(-1)[0], id);
}
function citationMeta(evidence) {
    if (!evidence)
        return 'pending detail';
    return `${text(evidence.radar_module)} · score ${text(evidence.metric_effective_score ?? evidence.metric_score)} · ${text(evidence.source_id)}`;
}
function evidenceTitle(item) {
    return text(item.metric_name ?? metricLabel(item.metric_id), text(item.metric_id, 'metric'));
}
function evidenceBrief(item) {
    return readableMetricText(item.p45_metric_brief ?? item.metric_explanation ?? item.score_reason ?? item.metric_id);
}
function evidenceDisplayDirection(item) {
    return item.metric_self_direction ?? item.direction;
}
function evidenceDirectionLabel(item) {
    const selfDirection = item.metric_self_direction;
    const compositeState = item.module_composite_state;
    if (selfDirection && compositeState) {
        return `self ${text(selfDirection)}`;
    }
    return text(evidenceDisplayDirection(item));
}
function evidenceCompositeLine(item) {
    if (!item.module_composite_state && item.module_composite_score == null)
        return '';
    return `composite ${text(item.module_composite_state)} · ${text(item.module_composite_direction)} · contribution ${text(item.kline_composite_contribution)}`;
}
function evidenceOneLine(item) {
    const summary = evidenceBrief(item);
    if (!summary || summary === '-')
        return '等待指标说明';
    return summary
        .replace(/\s+/g, ' ')
        .replace(/语义规则=.*$/u, '')
        .trim();
}
function evidenceScoreLine(item) {
    return `score ${text(item.metric_score)} · effective ${text(item.metric_effective_score)} · q ${text(item.quality_score)}`;
}
function evidenceFreshnessLine(item) {
    const status = item.freshness_display_status ?? item.freshness_status ?? item.business_recency_status;
    const note = item.freshness_display_note ? ` | ${text(item.freshness_display_note)}` : '';
    return `${text(status)} | fresh ${text(item.freshness_minutes)}m | stale after ${text(item.stale_after_minutes)}m${note}`;
}
function evidenceSourceLine(item) {
    return `${text(item.source_id)} | ${text(item.source_run_id ?? item.collect_run_id)}`;
}
function evidenceHorizonLine(item) {
    return `${text(item.horizon_tags)} | duplicate ${text(item.duplicate_group_id)} | module weight ${text(item.module_weight)}`;
}
function evidenceBadges(item) {
    const badges = [text(item.run_mode, 'live'), text(item.role, 'signal')];
    if (item.fallback_used === true || item.fallback_reason)
        badges.push('fallback');
    if (item.is_stale === true || String(item.freshness_status ?? '').includes('stale'))
        badges.push('stale');
    if (item.available === false)
        badges.push('unavailable');
    if (item.evidence_tier)
        badges.push(text(item.evidence_tier));
    return badges.filter(Boolean).slice(0, 5);
}
function evidenceBadgeClass(value) {
    const badge = String(value ?? '').toLowerCase();
    if (badge.includes('fallback') || badge.includes('stale') || badge.includes('quality'))
        return 'quality';
    if (badge.includes('unavailable') || badge.includes('negative'))
        return 'bear';
    if (badge.includes('live') || badge.includes('exact'))
        return 'bull';
    return 'neutral';
}
function evidenceWeightLine(item) {
    return `freshness ${text(item.freshness_weight)} | horizon ${text(item.horizon_weight)} | duplicate ${text(item.duplicate_adjustment)} | weight ${text(item.weight)}`;
}
function openArticleCitation(id) {
    activePage.value = 'evidence';
    void openEvidenceDetail(id);
}
async function openArticleSnapshot(row) {
    const finalRunId = String(row.final_run_id ?? '');
    if (!finalRunId)
        return;
    await store.loadHistory(finalRunId);
    activePage.value = 'article';
}
async function openHistorySnapshot(row) {
    const finalRunId = String(row.final_run_id ?? row.run_id ?? '');
    if (!finalRunId)
        return;
    await store.loadHistory(finalRunId);
    activePage.value = 'history';
}
function exitArticleHistory() {
    store.exitHistoryMode();
    void store.refreshLatest();
}
function exitHistoryReplay() {
    store.exitHistoryMode();
    void store.refreshLatest();
}
function historyValidityText() {
    return 'Replay uses Signal Validity / Alert Validity / Confidence Calibration. It does not score call accuracy.';
}
function articleSnapshotClass(row) {
    return directionClass(row.final_view ?? row.article_status ?? row.contract_status);
}
function articleSnapshotStatus(row) {
    return `${text(row.article_status, 'snapshot')} · ${text(row.final_view_cn ?? row.final_view, 'final_view')}`;
}
function driverReason(driver) {
    return readableMetricText(driver.reason ?? driver.summary ?? driver.metric_id);
}
function driverContribution(driver) {
    return text(driver.weighted_contribution ?? driver.contribution ?? driver.metric_effective_score);
}
async function openMetricEvidence(metricId) {
    const id = driverMetricId(metricId);
    const evidence = evidenceItems.value.find((item) => String(item.metric_id ?? '') === id);
    if (evidence?.evidence_id) {
        await openEvidenceDetail(String(evidence.evidence_id));
        return;
    }
    activePage.value = 'evidence';
}
function normalizationText() {
    const normalization = overviewScoreNormalization.value;
    const explanation = readableMetricText(normalization.explanation);
    if (explanation)
        return explanation;
    return 'Directional score is normalized by module weight, data quality, freshness, horizon and duplicate adjustment.';
}
function componentPercent(value) {
    const num = Number(value);
    if (!Number.isFinite(num))
        return text(value);
    return `${Math.round(num * 100)}%`;
}
function ruleSummary(rule) {
    return `${text(rule.horizon)} · ${text(ruleAction(rule))} · ${readableMetricText(rule.reason)}`;
}
function metricValue(metricId) {
    const item = evidenceItems.value.find((entry) => String(entry.metric_id ?? '') === metricId);
    return item?.value ?? item?.current_value;
}
function firstText(value, fallback = '-') {
    if (Array.isArray(value))
        return text(value[0], fallback);
    return text(value, fallback);
}
function daysText(value) {
    const num = Number(value);
    if (!Number.isFinite(num))
        return '-';
    if (Math.abs(num) < 1)
        return `${(num * 24).toFixed(1)}h`;
    return `${num.toFixed(1)}d`;
}
function compactNumber(value) {
    const num = Number(value);
    if (!Number.isFinite(num))
        return text(value);
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(num);
}
function eventPayload(row) {
    return (row.payload ?? {});
}
function eventType(row) {
    const payload = eventPayload(row);
    return text(payload.event_type ?? payload.type ?? row.feature_id, 'event');
}
function eventName(row) {
    const payload = eventPayload(row);
    return text(payload.event_name ?? payload.name ?? payload.event_type, eventType(row));
}
function eventWindow(row) {
    const payload = eventPayload(row);
    return text(payload.window ?? payload.event_phase, 'watch');
}
function eventLlmToneClass(value) {
    const tone = text(value, '').toLowerCase();
    if (tone.includes('hawk'))
        return 'mixed';
    if (tone.includes('dov'))
        return 'bull';
    if (tone.includes('not_policy'))
        return 'quality';
    if (tone.includes('ambiguous') || tone.includes('data') || tone.includes('balanced'))
        return 'blue';
    return '';
}
function sourceModeTone(value) {
    const mode = text(value, '').toLowerCase();
    if (mode.includes('blocked') || mode.includes('failed') || mode.includes('degraded'))
        return 'bear';
    if (mode.includes('partial_live') || mode.includes('functional'))
        return 'bull';
    if (mode.includes('partial') || mode.includes('fallback') || mode.includes('proxy'))
        return 'mixed';
    if (mode.includes('live'))
        return 'bull';
    return 'quality';
}
function daemonHealthTone(value) {
    const mode = text(value, '').toLowerCase();
    if (mode.includes('failed'))
        return 'bear';
    if (mode.includes('stale'))
        return 'mixed';
    if (mode.includes('degraded'))
        return 'warning';
    if (mode.includes('paused'))
        return 'quality';
    if (mode.includes('healthy') || mode.includes('running'))
        return 'bull';
    return 'quality';
}
function eventAuditStatusTone(value) {
    const status = text(value, '').toLowerCase();
    if (status.includes('pass') || status.includes('true') || status.includes('ok'))
        return 'bull';
    if (status.includes('stale') || status.includes('partial') || status.includes('pending'))
        return 'mixed';
    if (status.includes('fail') || status.includes('false') || status.includes('missing'))
        return 'bear';
    return 'quality';
}
function eventLlmConfidence(item) {
    return text(item.tone_confidence ?? item.confidence ?? item.confidence_score, '-');
}
function eventLlmSummary(item) {
    return text(item.summary_cn ?? item.summary_zh ?? item.summary ?? item.reason_cn ?? item.reason, '暂无 LLM 中文摘要。');
}
function eventLlmBoundaryPass(item) {
    if (typeof item.boundary_pass === 'boolean')
        return item.boundary_pass;
    if (typeof item.boundary === 'boolean')
        return item.boundary;
    return text(eventWindowDirectScoreImpact.value, 'false') === 'false';
}
function eventAction(row) {
    const payload = eventPayload(row);
    return firstText(payload.window_action ?? payload.action ?? payload.publish_impact, 'monitor');
}
function eventSourceStatus(row) {
    const payload = eventPayload(row);
    const trace = (payload.source_trace ?? {});
    return text(payload.source_resolution_status ?? trace.source_resolution_status ?? trace.event_source, 'source');
}
function eventDailyWatch(row) {
    const payload = eventPayload(row);
    const daily = (payload.daily_watch ?? {});
    const active = daily.active === true ? 'daily watch' : 'monitor';
    return `${active} · ${text(daily.change_summary, 'no new change')}`;
}
function eventQuality(row) {
    const payload = eventPayload(row);
    return text(payload.quality_score ?? payload.quality);
}
function alertTone(value) {
    const level = String(value ?? '').toLowerCase();
    if (level.includes('critical'))
        return 'bear';
    if (level.includes('high'))
        return 'mixed';
    if (level.includes('warning') || level.includes('watch'))
        return 'mixed';
    if (level.includes('info'))
        return 'neutral';
    return 'quality';
}
function cooldownText(value) {
    if (!value)
        return 'no cooldown';
    const date = new Date(String(value));
    if (Number.isNaN(date.getTime()))
        return text(value);
    return `cooldown until ${date.toLocaleString()}`;
}
function ruleAction(rule) {
    const action = rule.action_if_triggered;
    if (action && typeof action === 'object' && !Array.isArray(action)) {
        const row = action;
        return `${text(row.from, 'current')} -> ${text(row.to, 'watch')}`;
    }
    return text(action, 'watch');
}
function ruleConditions(rule) {
    const conditions = Array.isArray(rule.conditions) ? rule.conditions : [];
    const expression = conditions
        .map((condition) => `${text(condition.metric_id)}.${text(condition.field, 'value')} ${text(condition.op, '=')} ${text(condition.value)}`)
        .join(` ${text(rule.operator, 'AND')} `);
    return expression || 'waiting for structured conditions';
}
function ruleMetricIds(rule) {
    const ids = Array.isArray(rule.metric_ids) ? rule.metric_ids : [];
    if (ids.length)
        return ids.map((id) => String(id)).filter(Boolean);
    const conditions = Array.isArray(rule.conditions) ? rule.conditions : [];
    return [...new Set(conditions.map((condition) => String(condition.metric_id ?? '')).filter(Boolean))];
}
function metricEvidence(metricId) {
    const id = String(metricId ?? '');
    return evidenceItems.value.find((item) => String(item.metric_id ?? '') === id);
}
function ruleConditionStatus(condition) {
    const evidence = metricEvidence(condition.metric_id);
    const field = String(condition.field ?? 'value');
    const current = Number(evidence?.[field] ?? evidence?.metric_score ?? evidence?.value);
    const threshold = Number(condition.value);
    const op = String(condition.op ?? '');
    if (!Number.isFinite(current) || !Number.isFinite(threshold))
        return 'waiting';
    if (op === '>')
        return current > threshold ? 'met' : 'not met';
    if (op === '>=')
        return current >= threshold ? 'met' : 'not met';
    if (op === '<')
        return current < threshold ? 'met' : 'not met';
    if (op === '<=')
        return current <= threshold ? 'met' : 'not met';
    if (op === '==')
        return current === threshold ? 'met' : 'not met';
    return 'watch';
}
function ruleProgress(rule) {
    const conditions = Array.isArray(rule.conditions) ? rule.conditions : [];
    if (!conditions.length)
        return 'waiting conditions';
    const met = conditions.filter((condition) => ruleConditionStatus(condition) === 'met').length;
    return `${met}/${conditions.length} conditions met`;
}
function sourceStatusClass(value) {
    const status = String(value ?? '').toLowerCase();
    if (status.includes('challenge') || status.includes('captcha') || status.includes('reauth') || status.includes('manual'))
        return 'mixed';
    if (status.includes('healthy') || status.includes('ok'))
        return 'bull';
    if (status.includes('archived') || status.includes('fallback'))
        return 'quality';
    if (status.includes('fail') || status.includes('error'))
        return 'bear';
    return 'neutral';
}
function sourceMeaning(value) {
    const status = String(value ?? '').toLowerCase();
    if (status.includes('403') || status.includes('forbidden'))
        return '可能被官方站点或页面防护拦截，需要 fallback 或人工验证。';
    if (status.includes('actual'))
        return '业务数据可能尚未发布，不能简单视为采集失败。';
    if (status.includes('challenge') || status.includes('captcha') || status.includes('human'))
        return '需要人工验证或半自动重新授权。';
    if (status.includes('timeout'))
        return '页面加载超时，优先检查网络、页面结构或 Playwright 等待策略。';
    if (status.includes('fallback'))
        return '当前链路存在 fallback，可审计但需要区分主源与替代源。';
    if (status.includes('healthy') || status.includes('fresh'))
        return '主源当前可用，freshness 与业务时效仍需结合判断。';
    return '按 source status、freshness policy 和 downstream evidence 共同判断。';
}
function freshnessPolicyRows(policy) {
    return Object.entries(policy).map(([key, value]) => ({ key, value }));
}
function sourceId(row) {
    return text(row.source_id ?? row.id ?? row.source, 'unknown-source');
}
function sourceAuthState(row) {
    const content = JSON.stringify(row).toLowerCase();
    if (row.auth_state)
        return text(row.auth_state);
    if (row.manual_reauth_required || content.includes('manual_reauth_required'))
        return 'required';
    if (row.requires_human_verified_profile || content.includes('human challenge') || content.includes('captcha'))
        return 'required';
    if (content.includes('valid') || content.includes('verified'))
        return 'valid';
    return 'unknown';
}
function sourceAutomationMode(row) {
    if (row.automation_mode)
        return text(row.automation_mode);
    if (isSemiAutomatedSource(row))
        return 'semi_automated';
    return 'auto';
}
function sourceProfileDir(row) {
    const metadata = row.metadata ?? {};
    return text(row.profile_dir ?? metadata.profile_dir, sourceId(row).includes('bitbo') ? 'cache/playwright-bitbo-profile' : '-');
}
function sourceLastVerified(row) {
    const metadata = row.metadata ?? {};
    return row.last_verified_at ?? metadata.last_verified_at ?? row.verified_at ?? '-';
}
function isSemiAutomatedSource(row) {
    const content = JSON.stringify(row).toLowerCase();
    const id = sourceId(row).toLowerCase();
    return (id.includes('bitbo') ||
        id.includes('sth-lth') ||
        Boolean(row.requires_human_verified_profile) ||
        Boolean(row.manual_reauth_required) ||
        content.includes('human challenge') ||
        content.includes('captcha') ||
        content.includes('precondition required') ||
        content.includes('reauth'));
}
function sourceManualSummary(row) {
    const auth = sourceAuthState(row);
    if (auth === 'required')
        return '需要人工验证一次，验证后的浏览器 profile 会继续服务自动采集。';
    if (auth === 'valid')
        return '人工验证 profile 当前可用，后续可自动重试采集。';
    return '等待后端 auth-state，若遇到 Human Challenge 可从这里打开验证窗口。';
}
function sourceActionStatus(result) {
    if (!Object.keys(result).length)
        return 'No manual action has been triggered in this view.';
    return text(result.status ?? result.auth_state ?? result.message ?? result.error, 'action result received');
}
function sourceRunDuration(run) {
    const started = new Date(String(run.started_at ?? ''));
    const completed = new Date(String(run.completed_at ?? ''));
    if (!Number.isNaN(started.getTime()) && !Number.isNaN(completed.getTime())) {
        return `${Math.max(0, completed.getTime() - started.getTime())} ms`;
    }
    return text(run.latency_ms, 'latency pending');
}
function metricValueText(metric) {
    return `${text(metric.metric_id)} = ${text(metric.value)} · q ${text(metric.quality_score)}`;
}
function qualityCheckRows(limit = 18) {
    return Object.entries(qualityChecks.value)
        .map(([key, value]) => ({ key, value }))
        .slice(0, limit);
}
function warningSummary(warning) {
    return `${text(warning.code, 'warning')} · count ${text(warning.count, '-')}`;
}
function alertUpdatedText(value) {
    if (!value)
        return 'updated time pending';
    const date = new Date(String(value));
    if (Number.isNaN(date.getTime()))
        return text(value);
    return `updated ${date.toLocaleString()}`;
}
function openAlertEvidence(alert) {
    const level = String(alert.level ?? '').toLowerCase();
    evidenceModuleFilter.value = 'all';
    if (level.includes('critical') || level.includes('high') || level.includes('warning')) {
        evidenceBucketFilter.value = 'negative';
    }
    else {
        evidenceBucketFilter.value = 'all';
    }
    activePage.value = 'evidence';
}
function openAlertRunLogs(alert) {
    const runId = String(alert.run_id ?? '');
    if (runId)
        state.routeContext.final_run_id = String(alertRunLineage.value.final_run_id ?? state.routeContext.final_run_id);
    activePage.value = 'logs';
}
function statusClass(value) {
    const status = String(value ?? '').toLowerCase();
    if (status.includes('context') || status.includes('discounted'))
        return 'quality';
    if (status.includes('confirmed') || status.includes('triggered') || status.includes('accepted'))
        return 'bull';
    if (status.includes('refuted') || status.includes('rejected') || status.includes('blocked'))
        return 'bear';
    if (status.includes('conflict') || status.includes('armed') || status.includes('arming') || status.includes('watch'))
        return 'mixed';
    if (status.includes('stale') || status.includes('missing') || status.includes('expired'))
        return 'quality';
    if (status.includes('completed') && status.includes('error'))
        return 'quality';
    if (status.includes('complete') || status.includes('ok') || status.includes('pass'))
        return 'bull';
    if (status.includes('running') || status.includes('pending'))
        return 'mixed';
    if (status.includes('fail') || status.includes('error'))
        return 'bear';
    return 'neutral';
}
function normalizedStageText(stage) {
    return `${stage.stage_id ?? ''} ${stage.phase ?? ''} ${stage.label ?? ''}`.toLowerCase();
}
function findPipelineStage(matchers) {
    const normalizedMatchers = matchers.map((item) => item.toLowerCase());
    return stages.value.find((stage) => {
        const content = normalizedStageText(stage);
        return normalizedMatchers.some((matcher) => content.includes(matcher));
    });
}
function completedLike(stage) {
    const status = String(stage?.status ?? '').toLowerCase();
    return status.includes('complete') || status.includes('ok') || status.includes('pass') || status.includes('skipped');
}
function pipelineActiveIndex() {
    if (!state.running)
        return -1;
    const firstOpen = pipelineDefs.findIndex((definition) => !completedLike(findPipelineStage(definition.match)));
    return firstOpen >= 0 ? firstOpen : pipelineDefs.length - 1;
}
function pipelineStageState(stage, index) {
    const status = String(stage?.status ?? '').toLowerCase();
    if (status.includes('fail'))
        return 'failed';
    if (status.includes('completed_with_llm_errors') || (status.includes('completed') && status.includes('error')))
        return 'degraded';
    if (state.running && index === pipelineActiveIndex())
        return 'active';
    if (status.includes('running') || status.includes('pending'))
        return 'active';
    if (completedLike(stage))
        return 'done';
    if (status.includes('error'))
        return 'degraded';
    return 'waiting';
}
function pipelineStateIcon(stateName) {
    if (stateName === 'done')
        return '✓';
    if (stateName === 'active')
        return '◌';
    if (stateName === 'degraded')
        return '!';
    if (stateName === 'failed')
        return '×';
    return '·';
}
function pipelineRunId(runKey, stage) {
    return text(stage?.run_id ?? latestRun.value[runKey] ?? store.runLineage.value?.[runKey], 'pending');
}
function shortRunId(value) {
    const id = text(value, 'pending');
    return id.length > 22 ? `${id.slice(0, 20)}...` : id;
}
function openPipelineStage(node) {
    const report = (node.report ?? {});
    if (report.file_url || report.relative_path || report.filename)
        openReport(report);
}
function stageNote(stage) {
    const status = String(stage.status ?? '').toLowerCase();
    if (status.includes('skipped'))
        return 'Stage skipped by run execution profile; deterministic decision remains available.';
    if (status.includes('completed') && status.includes('error'))
        return '非阻塞降级: LLM appendix has degradation; main artifacts remain auditable.';
    if (status.includes('complete'))
        return 'Stage completed and artifacts are included in this run lineage.';
    if (status.includes('running'))
        return 'Stage is running; waiting for backend status refresh.';
    if (status.includes('fail'))
        return text(stage.error ?? stage.message, 'Stage failed; check backend logs.');
    return text(stage.message ?? stage.note, 'Waiting for stage status.');
}
function stageId(stage) {
    return text(stage.stage_id ?? stage.phase ?? stage.label, 'stage');
}
function stageScope(stage) {
    const parts = [
        stage.source_id ? `source ${text(stage.source_id)}` : '',
        stage.module_id ? `module ${text(stage.module_id)}` : '',
        stage.metric_id ? `metric ${text(stage.metric_id)}` : '',
        stage.error_code ? `error ${text(stage.error_code)}` : '',
    ].filter(Boolean);
    return parts.length ? parts.join(' · ') : 'scope included when backend reports source/module/metric';
}
function stageArtifactLabel(stage) {
    const report = stageReport(stage);
    if (report.relative_path || report.filename || report.file_url)
        return reportTitle(report);
    const id = stageId(stage);
    if (id.includes('p1'))
        return 'P1 数据采集审计';
    if (id.includes('p2'))
        return 'P2 Radar 质检报告';
    if (id.includes('p3'))
        return 'P3 算法审计报告';
    if (id.includes('llm'))
        return 'P4.5 研究报告 · LLM appendix';
    if (id.includes('p45'))
        return 'P4.5 研究报告';
    return 'artifact pending';
}
function stageNeedsManualAction(stage) {
    const content = JSON.stringify(stage).toLowerCase();
    return (content.includes('human challenge') ||
        content.includes('captcha') ||
        content.includes('manual_reauth_required') ||
        content.includes('precondition required') ||
        content.includes('reauth'));
}
function stageManualSourceId(stage) {
    return text(stage.source_id ?? stage.blocked_source_id ?? stage.manual_source_id, 'bitbo-sth-lth-realized-price');
}
function stageUpdatedText(stage) {
    return timestampText(stage.updated_at ?? stage.completed_at ?? stage.created_at);
}
function reportTitle(report) {
    const phase = String(report.phase ?? '').toLowerCase();
    const filename = String(report.filename ?? report.relative_path ?? '');
    if (phase === 'p1' || filename.includes('p1-'))
        return 'P1 数据采集审计';
    if (phase === 'p2' || filename.includes('p2-'))
        return 'P2 Radar 质检报告';
    if (phase === 'p3' || filename.includes('p3-'))
        return 'P3 算法审计报告';
    if (phase === 'p45' || filename.includes('p45-'))
        return 'P4.5 研究报告';
    return text(report.title ?? report.phase ?? report.filename, 'Audit Report');
}
function reportSize(value) {
    const size = Number(value);
    if (!Number.isFinite(size))
        return '-';
    if (size > 1024 * 1024)
        return `${(size / 1024 / 1024).toFixed(1)} MB`;
    if (size > 1024)
        return `${(size / 1024).toFixed(1)} KB`;
    return `${size} B`;
}
function reportHref(report) {
    const relativePath = String(report.relative_path ?? report.filename ?? '');
    if (relativePath) {
        const parts = relativePath.replace(/\\/g, '/').split('/').filter(Boolean);
        const reportsIndex = parts.findIndex((part) => part === 'reports');
        const reportParts = reportsIndex >= 0 ? parts.slice(reportsIndex + 1) : parts;
        if (reportParts.length) {
            const backendOrigin = window.location.port === '8118' ? window.location.origin : `${window.location.protocol}//${window.location.hostname}:8118`;
            return `${backendOrigin}/reports/${reportParts.map((part) => encodeURIComponent(part)).join('/')}`;
        }
    }
    return String(report.file_url ?? '');
}
function openReport(report) {
    const url = reportHref(report);
    if (url)
        window.open(url, '_blank', 'noopener,noreferrer');
}
function stageReport(stage) {
    return (stage.audit_report ?? {});
}
function reportUpdatedText(report) {
    return timestampText(report.updated_at ?? report.created_at);
}
function timestampText(value) {
    if (!value)
        return 'time pending';
    if (typeof value === 'number')
        return new Date(value * 1000).toLocaleString();
    const date = new Date(String(value));
    if (Number.isNaN(date.getTime()))
        return text(value);
    return date.toLocaleString();
}
function issueText(issue) {
    if (typeof issue === 'string')
        return issue;
    return text(issue.message ?? issue.detail ?? issue.code ?? issue.error ?? issue);
}
function conflictSeverityClass(row) {
    const severity = String(row.severity ?? row.conflict_severity ?? row.level ?? '').toLowerCase();
    const type = String(row.conflict_type ?? row.source_resolution ?? '').toLowerCase();
    if (severity.includes('high') || severity.includes('critical') || type.includes('value_conflict'))
        return 'bear';
    if (severity.includes('medium') || type.includes('update_lag') || row.fallback_used === true)
        return 'mixed';
    if (type.includes('definition') || type.includes('duplicate'))
        return 'quality';
    return 'neutral';
}
function conflictTypeLabel(row) {
    const type = text(row.conflict_type ?? row.conflict_origin ?? row.source_resolution, 'source_conflict');
    if (type.includes('definition'))
        return '口径差异';
    if (type.includes('update'))
        return '更新时间差异';
    if (type.includes('value'))
        return '数值冲突';
    if (type.includes('fallback'))
        return 'Fallback 仲裁';
    if (type.includes('duplicate'))
        return '重复影响降权';
    return type;
}
function conflictSourceList(row) {
    const candidates = [
        ...asList(row.candidate_sources),
        ...asList(row.candidates).map((item) => (typeof item === 'object' ? item.source_id : item)),
        row.conflicting_source,
        row.fallback_source,
        row.cross_check_source,
    ];
    return [...new Set(candidates.map((item) => text(item)).filter((item) => item !== '-'))];
}
function conflictSelectedSource(row) {
    return text(row.selected_source ?? row.primary_source ?? row.source_id, 'selected source pending');
}
function conflictReason(row) {
    return text(row.selected_reason ??
        row.resolution_reason ??
        row.fallback_reason ??
        row.source_resolution ??
        'Selected by priority, freshness, quality and downstream scoring policy.');
}
function conflictImpactText(row) {
    const score = text(row.metric_effective_score ?? row.downstream_metric_effective_score ?? row.metric_score);
    const evidenceId = text(row.evidence_id ?? row.downstream_evidence_id, 'pending evidence');
    const boundary = conflictSeverityClass(row) === 'bear' ? '可能影响方向，需要校准源优先级。' : '作为 data boundary 展示，不直接视为采集失败。';
    return `${boundary} downstream score=${score}; evidence=${evidenceId}.`;
}
function conflictMetricId(row) {
    return text(row.metric_id ?? row.feature_id ?? row.group, 'metric');
}
function conflictEvidenceId(row) {
    return text(row.evidence_id ?? row.downstream_evidence_id, '');
}
async function openConflictEvidence(row) {
    const evidenceId = conflictEvidenceId(row);
    if (evidenceId)
        await openEvidenceDetail(evidenceId);
}
async function openConflictRadar(row) {
    const moduleId = text(row.radar_module ?? row.module_id, '');
    if (moduleId)
        await openRadarDetail(moduleId);
}
function directionClass(value) {
    const direction = String(value ?? '').toLowerCase();
    if (direction.includes('bearish_but_improving') ||
        direction.includes('bullish_but_weakening') ||
        direction.includes('neutral_wait_confirm') ||
        direction.includes('neutral_mixed') ||
        direction.includes('rebound_unconfirmed') ||
        direction.includes('conflict') ||
        direction.includes('balanced') ||
        direction.includes('improving') ||
        direction.includes('vol_') ||
        direction.includes('pinning') ||
        direction.includes('protection_bid') ||
        direction.includes('tail_risk') ||
        direction.includes('large_expiry') ||
        direction.includes('event_caution') ||
        direction.includes('event_hard_lock') ||
        direction.includes('event_post_digest') ||
        direction.includes('event_risk_locked')) {
        return 'mixed';
    }
    if (direction.includes('event_neutral'))
        return 'neutral';
    if (direction.includes('bull'))
        return 'bull';
    if (direction.includes('bear'))
        return 'bear';
    if (direction.includes('quality') || direction.includes('fallback'))
        return 'quality';
    if (direction.includes('mixed') || direction.includes('watch'))
        return 'mixed';
    return 'neutral';
}
function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}
function moduleLayoutKey(moduleId) {
    return moduleId || 'module';
}
function defaultPoint(index) {
    return defaultLayoutPoints[index] ?? { x: 50, y: 50 };
}
function nodePoint(moduleId, index) {
    return radarLayout[moduleLayoutKey(moduleId)] ?? defaultPoint(index);
}
function repelByActiveNode(moduleId, index, basePoint) {
    const drag = dragging.value;
    if (!drag || drag.moduleId === moduleLayoutKey(moduleId) || !drag.moved)
        return basePoint;
    const activePoint = radarLayout[drag.moduleId];
    if (!activePoint)
        return basePoint;
    const dx = basePoint.x - activePoint.x;
    const dy = basePoint.y - activePoint.y;
    const distance = Math.hypot(dx, dy);
    const influenceRadius = 28;
    if (distance >= influenceRadius)
        return basePoint;
    const unitX = distance > 0.1 ? dx / distance : basePoint.x >= 50 ? 1 : -1;
    const unitY = distance > 0.1 ? dy / distance : basePoint.y >= 50 ? 1 : -1;
    const btcDx = basePoint.x - 50;
    const btcDy = basePoint.y - 50;
    const btcDistance = Math.max(1, Math.hypot(btcDx, btcDy));
    const awayFromBtcX = btcDx / btcDistance;
    const awayFromBtcY = btcDy / btcDistance;
    const strength = ((influenceRadius - distance) / influenceRadius) * 9;
    const defaultBase = defaultPoint(index);
    return {
        x: clamp(basePoint.x + (unitX * 0.72 + awayFromBtcX * 0.28) * strength, defaultBase.x - 10, defaultBase.x + 10),
        y: clamp(basePoint.y + (unitY * 0.72 + awayFromBtcY * 0.28) * strength, defaultBase.y - 10, defaultBase.y + 10),
    };
}
function displayNodePoint(moduleId, index) {
    const point = nodePoint(moduleId, index);
    return repelByActiveNode(moduleId, index, point);
}
function nodeDistanceRatio(point) {
    const dx = point.x - 50;
    const dy = point.y - 50;
    return clamp(Math.hypot(dx, dy) / 58, 0, 1);
}
function nodeDepth(point) {
    const ratio = nodeDistanceRatio(point);
    return {
        scale: clamp(1.1 - ratio * 0.3, 0.78, 1.08),
        opacity: clamp(1 - ratio * 0.28, 0.62, 0.98),
        strokeWidth: clamp(4.2 - ratio * 2, 1.8, 3.6),
    };
}
function linkPath(point) {
    const startX = point.x * 10;
    const startY = point.y * 6.2;
    const endX = 500;
    const endY = 310;
    const bend = 0.42;
    const controlX = startX + (endX - startX) * bend;
    const controlY = startY + (endY - startY) * bend;
    return `M${startX.toFixed(1)} ${startY.toFixed(1)} Q${controlX.toFixed(1)} ${controlY.toFixed(1)} ${endX} ${endY}`;
}
function nodeStyle(moduleId, index) {
    const point = displayNodePoint(moduleId, index);
    const depth = nodeDepth(point);
    return {
        left: `${point.x}%`,
        top: `${point.y}%`,
        '--node-scale': depth.scale.toFixed(3),
        '--node-opacity': depth.opacity.toFixed(3),
    };
}
function nodeClass(node) {
    return [directionClass(node.direction), dragging.value?.moduleId === moduleLayoutKey(moduleName(node.module)) ? 'dragging' : ''];
}
const DISPLAY_STATE_PRIORITY = [
    'macro_trend_state',
    'crypto_breadth_state',
    'dollar_liquidity_state',
    'options_short_term_state',
    'btc_short_term_state',
    'event_short_term_state',
    'trade_structure_state',
    'onchain_valuation_state',
    'signal_stage',
    'fund_flow_state',
    'long_short_squeeze_risk',
    'crowding_state',
    'top_positioning_state',
    'positioning_state',
    'display_state',
    'trend_state',
    'module_state',
    'module_effective_direction',
    'module_direction',
];
const MEANINGFUL_MODULE_STATES = new Set([
    'bearish_but_improving',
    'bullish_but_weakening',
    'neutral_wait_confirm',
    'neutral_mixed',
    'bearish_pressure',
    'risk_on_confirmed',
    'bullish_confirmation',
    'bearish_confirmation',
    'rebound_unconfirmed',
    'breakdown_risk',
    'breakdown_confirmed',
    'false_breakout_risk',
    'bearish_but_absorbed',
    'event_neutral',
    'event_caution',
    'event_hard_lock',
    'event_post_digest',
    'event_risk_locked',
    'conflict_no_trade',
    'mixed_watch',
    'not_crowded',
    'long_crowded',
    'short_crowded',
    'overheated',
    'squeeze_risk',
    'top_long_skew',
    'top_short_skew',
    'top_extreme_long',
    'top_extreme_short',
    'long_skew',
    'short_skew',
    'extreme_long',
    'extreme_short',
    'long_squeeze_risk',
    'short_squeeze_risk',
    'buy_pressure_unconfirmed',
    'sell_pressure_unconfirmed',
    'absorption_or_trapped_long',
    'sell_absorption_or_trapped_short',
    'buy_pressure_rejected',
    'sell_pressure_rejected',
    'short_squeeze_chase_risk',
    'long_flush_panic_risk',
    'long_flush_absorbed',
    'squeeze_failed',
    'price_up_confirmed',
    'price_down_confirmed',
    'short_covering_bounce',
    'long_crowding_downside',
    'overheated_upside',
    'deleveraging_downside',
    'short_squeeze_potential',
    'vol_expansion_risk',
    'pinning_likely',
    'downside_protection_bid',
    'tail_risk_elevated',
    'large_expiry_near',
    'pinning_before_expiry_vol_after',
    'vol_expansion_risk_with_structure_resistance',
    'vol_compression',
    'vol_neutral',
    'data_quality_degraded',
    'btc_broad_confirmed_uptrend',
    'narrow_btc_rally_fragile',
    'btc_defensive_leadership',
    'alt_beta_rotation',
    'breadth_bearish_divergence',
    'broad_risk_off',
    'risk_off_but_breadth_improving',
    'alt_chase_overheat',
    'macro_trend_confirmed_bullish',
    'macro_tailwind_but_btc_lagging',
    'macro_headwind_confirmed_bearish',
    'btc_resisting_macro_headwind',
    'macro_shock_risk',
    'macro_mixed',
    'macro_neutral',
    'liquidity_tailwind_confirmed',
    'liquidity_tailwind_rejected',
    'liquidity_headwind_confirmed',
    'btc_internal_strength_against_liquidity_headwind',
    'funding_stress_override',
    'liquidity_mixed',
    'liquidity_neutral',
    'etf_demand_accelerating',
    'etf_demand_confirmed',
    'etf_demand_fading',
    'etf_outflow_warning',
    'etf_outflow_confirmed',
    'stablecoin_liquidity_tailwind',
    'stablecoin_liquidity_drain',
    'supply_squeeze_support',
    'exchange_supply_pressure',
    'exchange_flow_untrusted',
    'btc_accepting_flow_tailwind',
    'btc_rejecting_flow_tailwind',
    'btc_resisting_flow_headwind',
    'fund_flow_neutral',
    'sth_retest_warning',
    'sth_reclaim_fast',
    'sth_reclaim_confirmed',
    'sth_rejection_fast',
    'sth_breakdown_confirmed',
    'sopr_recovery_fast',
    'sopr_recovery_confirmed',
    'profit_taking_warning',
    'sopr_loss_realization',
    'realized_cap_inflow_confirmed',
    'realized_cap_drain_warning',
    'btc_accepting_onchain_tailwind',
    'btc_rejecting_onchain_tailwind',
    'btc_resisting_onchain_headwind',
    'overheated_distribution_warning',
    'euphoria_top_risk',
    'onchain_neutral',
    'early_warning',
    'fast_signal',
    'confirmed_signal',
    'invalidated',
]);
function isMeaningfulCompositeState(value) {
    const state = String(value ?? '').toLowerCase();
    if (!state || state === 'null' || state === 'undefined')
        return false;
    return (MEANINGFUL_MODULE_STATES.has(state) ||
        state.includes('_but_') ||
        state.includes('_wait_') ||
        state.includes('_pressure') ||
        state.includes('_crowded') ||
        state.includes('_skew') ||
        state.includes('_risk') ||
        state.includes('_confirmed') ||
        state.includes('_warning') ||
        state.includes('_rejecting_') ||
        state.includes('_resisting_') ||
        state.includes('_fading') ||
        state.includes('_untrusted'));
}
function moduleDisplayState(module) {
    for (const key of DISPLAY_STATE_PRIORITY) {
        const value = module[key];
        if ((key === 'fund_flow_state' ||
            key === 'onchain_valuation_state' ||
            key === 'signal_stage' ||
            key === 'macro_trend_state' ||
            key === 'crypto_breadth_state' ||
            key === 'dollar_liquidity_state' ||
            key === 'options_short_term_state' ||
            key === 'btc_short_term_state' ||
            key === 'event_short_term_state' ||
            key === 'trade_structure_state' ||
            key === 'display_state' ||
            key === 'trend_state' ||
            key === 'module_state' ||
            key === 'long_short_squeeze_risk' ||
            key === 'crowding_state' ||
            key === 'top_positioning_state' ||
            key === 'positioning_state') &&
            isMeaningfulCompositeState(value)) {
            return String(value);
        }
        if (key === 'module_effective_direction' || key === 'module_direction') {
            return String(value ?? 'neutral');
        }
    }
    return 'neutral';
}
function moduleDisplayLabel(module) {
    const state = moduleDisplayState(module).toLowerCase();
    const labels = {
        bearish_but_improving: '偏空但改善 / bearish but improving',
        bullish_but_weakening: '偏多但转弱 / bullish but weakening',
        neutral_wait_confirm: '等待确认 / wait confirm',
        neutral_mixed: '多空分歧 / mixed',
        bearish_pressure: '偏空压力 / bearish pressure',
        risk_on_confirmed: '风险偏好确认 / risk-on',
        bullish_confirmation: '偏多确认 / bullish confirmed',
        bearish_confirmation: '偏空确认 / bearish confirmed',
        rebound_unconfirmed: '反弹待确认 / rebound unconfirmed',
        breakdown_risk: '破位风险 / breakdown risk',
        breakdown_confirmed: '破位确认 / breakdown confirmed',
        false_breakout_risk: '假突破风险 / false breakout',
        bearish_but_absorbed: '下跌有承接 / absorbed pressure',
        event_neutral: '事件窗口中性 / event neutral',
        event_caution: '事件谨慎窗口 / event caution',
        event_hard_lock: '事件硬锁定 / event hard lock',
        event_post_digest: '事件落地消化 / post-event digest',
        event_risk_locked: '事件锁定 / event locked',
        conflict_no_trade: '信号冲突 / no trade',
        mixed_watch: '分歧观察 / mixed watch',
        not_crowded: '拥挤风险低 / not crowded',
        long_crowded: '多头拥挤 / long crowded',
        short_crowded: '空头拥挤 / short crowded',
        overheated: '过热 / overheated',
        squeeze_risk: '挤压风险 / squeeze risk',
        top_long_skew: '大户偏多 / top long skew',
        top_short_skew: '大户偏空 / top short skew',
        top_extreme_long: '大户极端偏多 / top extreme long',
        top_extreme_short: '大户极端偏空 / top extreme short',
        long_skew: '多头偏斜 / long skew',
        short_skew: '空头偏斜 / short skew',
        extreme_long: '极端偏多 / extreme long',
        extreme_short: '极端偏空 / extreme short',
        long_squeeze_risk: '多头拥挤风险 / long squeeze risk',
        short_squeeze_risk: '空头挤压风险 / short squeeze risk',
        buy_pressure_unconfirmed: '主动买盘待确认 / buy pressure unconfirmed',
        sell_pressure_unconfirmed: '主动卖盘待确认 / sell pressure unconfirmed',
        absorption_or_trapped_long: '买盘被吸收 / trapped long',
        sell_absorption_or_trapped_short: '卖盘被承接 / trapped short',
        buy_pressure_rejected: '买压被拒绝 / buy rejected',
        sell_pressure_rejected: '卖压被拒绝 / sell rejected',
        short_squeeze_chase_risk: '空头挤压追涨风险 / squeeze chase',
        long_flush_panic_risk: '多头清算风险 / long flush',
        long_flush_absorbed: '多头清算被吸收 / flush absorbed',
        squeeze_failed: '挤压失败 / squeeze failed',
        price_up_confirmed: '短线偏多确认 / price up confirmed',
        price_down_confirmed: '短线偏空确认 / price down confirmed',
        short_covering_bounce: '空头回补反弹 / short covering bounce',
        long_crowding_downside: '多头拥挤下行 / crowded longs downside',
        overheated_upside: '上行过热 / overheated upside',
        deleveraging_downside: 'leverage reset downside',
        short_squeeze_potential: '潜在逼空 / squeeze potential',
        vol_expansion_risk: '波动扩张风险 / volatility expansion risk',
        pinning_likely: '到期钉住概率上升 / pinning likely',
        downside_protection_bid: '下方保护需求升温 / downside protection bid',
        tail_risk_elevated: '尾部风险升温 / tail risk elevated',
        large_expiry_near: '大额到期临近 / large expiry near',
        pinning_before_expiry_vol_after: '到期前钉住、到期后波动 / pin before expiry, vol after',
        vol_expansion_risk_with_structure_resistance: '波动扩张伴结构阻力 / vol expansion with structure resistance',
        vol_compression: '波动压缩 / volatility compression',
        vol_neutral: '期权结构中性 / options neutral',
        data_quality_degraded: '数据质量降级 / data degraded',
        btc_broad_confirmed_uptrend: 'BTC趋势获市场宽度确认 / broad confirmed uptrend',
        narrow_btc_rally_fragile: 'BTC独涨但宽度脆弱 / narrow BTC rally',
        btc_defensive_leadership: 'BTC防御性领涨 / defensive BTC leadership',
        alt_beta_rotation: 'Alt风险扩散接力 / alt beta rotation',
        breadth_bearish_divergence: '宽度看空背离 / breadth bearish divergence',
        broad_risk_off: '全市场风险收缩 / broad risk-off',
        risk_off_but_breadth_improving: '风险环境内宽度修复 / breadth improving',
        alt_chase_overheat: 'Alt追涨过热 / alt chase overheat',
        macro_trend_confirmed_bullish: '宏观确认 BTC 上行 / macro confirmed uptrend',
        macro_tailwind_but_btc_lagging: '宏观顺风但 BTC 滞后 / tailwind not absorbed',
        macro_headwind_confirmed_bearish: '宏观逆风确认下行 / macro confirmed downside',
        btc_resisting_macro_headwind: 'BTC 抗住宏观逆风 / resisting macro headwind',
        macro_shock_risk: '宏观冲击风险 / macro shock risk',
        macro_mixed: '宏观信号混合 / macro mixed',
        macro_neutral: '宏观中性 / macro neutral',
        liquidity_tailwind_confirmed: '美元流动性顺风被确认 / liquidity tailwind confirmed',
        liquidity_tailwind_rejected: '美元流动性顺风被拒绝 / liquidity tailwind rejected',
        liquidity_headwind_confirmed: '美元流动性逆风被确认 / liquidity headwind confirmed',
        btc_internal_strength_against_liquidity_headwind: 'BTC 抗住流动性逆风 / BTC resists liquidity headwind',
        funding_stress_override: '融资压力优先 / funding stress override',
        liquidity_mixed: '美元流动性混合 / liquidity mixed',
        liquidity_neutral: '美元流动性中性 / liquidity neutral',
    };
    return labels[state] ?? text(state || (module.module_effective_direction ?? module.module_direction), 'watch');
}
function moduleDisplayShortLabel(module) {
    const state = moduleDisplayState(module).toLowerCase();
    const labels = {
        bearish_but_improving: '偏空改善',
        bullish_but_weakening: '偏多转弱',
        neutral_wait_confirm: '待确认',
        neutral_mixed: '多空分歧',
        bearish_pressure: '偏空压力',
        risk_on_confirmed: '风险确认',
        bullish_confirmation: '偏多确认',
        bearish_confirmation: '偏空确认',
        rebound_unconfirmed: '反弹待确',
        breakdown_risk: '破位风险',
        breakdown_confirmed: '破位确认',
        false_breakout_risk: '假突破',
        bearish_but_absorbed: '下跌承接',
        event_neutral: '事件中性',
        event_caution: '事件谨慎',
        event_hard_lock: '事件锁定',
        event_post_digest: '事件消化',
        event_risk_locked: '事件锁定',
        conflict_no_trade: '信号冲突',
        mixed_watch: '分歧观察',
        not_crowded: '低拥挤',
        long_crowded: '多头拥挤',
        short_crowded: '空头拥挤',
        overheated: '过热',
        squeeze_risk: '挤压风险',
        top_long_skew: '大户偏多',
        top_short_skew: '大户偏空',
        top_extreme_long: '大户极多',
        top_extreme_short: '大户极空',
        long_skew: '多头偏斜',
        short_skew: '空头偏斜',
        extreme_long: '极端偏多',
        extreme_short: '极端偏空',
        long_squeeze_risk: '多头拥挤',
        short_squeeze_risk: '空头挤压',
        buy_pressure_unconfirmed: '买盘待确',
        sell_pressure_unconfirmed: '卖盘待确',
        absorption_or_trapped_long: '买盘吸收',
        sell_absorption_or_trapped_short: '卖盘承接',
        buy_pressure_rejected: '买压拒绝',
        sell_pressure_rejected: '卖压拒绝',
        short_squeeze_chase_risk: '挤压追涨',
        long_flush_panic_risk: '多头清算',
        long_flush_absorbed: '清算吸收',
        squeeze_failed: '挤压失败',
        price_up_confirmed: '偏多确认',
        price_down_confirmed: '偏空确认',
        short_covering_bounce: '回补反弹',
        long_crowding_downside: '拥挤下行',
        overheated_upside: '上行过热',
        deleveraging_downside: 'leverage reset down',
        short_squeeze_potential: '潜在逼空',
        vol_expansion_risk: '波动扩张风险',
        pinning_likely: '钉住概率上升',
        downside_protection_bid: '下方保护升温',
        tail_risk_elevated: '尾部风险升温',
        large_expiry_near: '大额到期临近',
        pinning_before_expiry_vol_after: '到期前钉住/后波动',
        vol_expansion_risk_with_structure_resistance: '波动扩张伴结构阻力',
        vol_compression: '波动压缩',
        vol_neutral: '期权结构中性',
        data_quality_degraded: '期权数据降级',
        btc_broad_confirmed_uptrend: '宽度确认',
        narrow_btc_rally_fragile: '独涨脆弱',
        btc_defensive_leadership: 'BTC防御强',
        alt_beta_rotation: 'Alt接力',
        breadth_bearish_divergence: '宽度背离',
        broad_risk_off: '全面收缩',
        risk_off_but_breadth_improving: '宽度修复',
        alt_chase_overheat: 'Alt过热',
        macro_trend_confirmed_bullish: '宏观确认',
        macro_tailwind_but_btc_lagging: '顺风滞后',
        macro_headwind_confirmed_bearish: '逆风确认',
        btc_resisting_macro_headwind: 'BTC抗逆风',
        macro_shock_risk: '宏观冲击',
        macro_mixed: '宏观混合',
        macro_neutral: '宏观中性',
        liquidity_tailwind_confirmed: '流动性顺风',
        liquidity_tailwind_rejected: '顺风被拒',
        liquidity_headwind_confirmed: '流动性逆风',
        btc_internal_strength_against_liquidity_headwind: 'BTC抗逆风',
        funding_stress_override: '融资压力',
        liquidity_mixed: '流动性混合',
        liquidity_neutral: '流动性中性',
        etf_demand_accelerating: 'ETF需求加速',
        etf_demand_confirmed: 'ETF需求确认',
        etf_demand_fading: 'ETF需求转弱',
        etf_outflow_warning: 'ETF流出预警',
        etf_outflow_confirmed: 'ETF流出确认',
        stablecoin_liquidity_tailwind: '稳定币背景支持',
        stablecoin_liquidity_drain: '稳定币流动性收缩',
        supply_squeeze_support: '可交易供给偏紧',
        exchange_supply_pressure: '交易所供给压力',
        exchange_flow_untrusted: '交易所流向降权',
        btc_accepting_flow_tailwind: 'BTC接受顺风',
        btc_rejecting_flow_tailwind: 'BTC拒绝资金顺风',
        btc_resisting_flow_headwind: 'BTC抵抗资金逆风',
        fund_flow_neutral: '资金流中性',
    };
    return labels[state] ?? text(state || (module.module_effective_direction ?? module.module_direction), 'watch');
}
function moduleDisplayClass(module) {
    const composite = moduleCompositeTone(module);
    if (composite !== 'legacy')
        return composite;
    const state = moduleDisplayState(module).toLowerCase();
    if ([
        'buy_pressure_unconfirmed',
        'sell_pressure_unconfirmed',
        'short_squeeze_chase_risk',
        'long_flush_absorbed',
        'squeeze_failed',
        'vol_expansion_risk',
        'pinning_likely',
        'downside_protection_bid',
        'tail_risk_elevated',
        'large_expiry_near',
        'pinning_before_expiry_vol_after',
        'vol_expansion_risk_with_structure_resistance',
        'vol_compression',
        'vol_neutral',
        'data_quality_degraded',
        'event_caution',
        'event_hard_lock',
        'event_post_digest',
        'event_risk_locked',
        'narrow_btc_rally_fragile',
        'btc_defensive_leadership',
        'breadth_bearish_divergence',
        'risk_off_but_breadth_improving',
        'alt_chase_overheat',
        'macro_tailwind_but_btc_lagging',
        'btc_resisting_macro_headwind',
        'macro_shock_risk',
        'macro_mixed',
        'liquidity_tailwind_rejected',
        'btc_internal_strength_against_liquidity_headwind',
        'funding_stress_override',
        'liquidity_mixed',
        'etf_demand_fading',
        'etf_outflow_warning',
        'exchange_flow_untrusted',
    ].includes(state)) {
        return 'mixed';
    }
    if (state === 'event_neutral') {
        return 'neutral';
    }
    if (['absorption_or_trapped_long', 'buy_pressure_rejected', 'long_flush_panic_risk'].includes(state)) {
        return 'bear';
    }
    if (['sell_absorption_or_trapped_short', 'sell_pressure_rejected'].includes(state)) {
        return 'bull';
    }
    if (['price_up_confirmed', 'short_covering_bounce', 'overheated_upside', 'short_squeeze_potential'].includes(state)) {
        return 'bull';
    }
    if (['price_down_confirmed', 'long_crowding_downside', 'deleveraging_downside'].includes(state)) {
        return 'bear';
    }
    if (['btc_broad_confirmed_uptrend', 'alt_beta_rotation'].includes(state)) {
        return 'bull';
    }
    if (state === 'macro_trend_confirmed_bullish') {
        return 'bull';
    }
    if (state === 'liquidity_tailwind_confirmed') {
        return 'bull';
    }
    if (['etf_demand_accelerating', 'etf_demand_confirmed', 'stablecoin_liquidity_tailwind', 'supply_squeeze_support', 'btc_accepting_flow_tailwind', 'btc_resisting_flow_headwind'].includes(state)) {
        return 'bull';
    }
    if (['broad_risk_off', 'macro_headwind_confirmed_bearish', 'liquidity_headwind_confirmed', 'etf_outflow_confirmed', 'stablecoin_liquidity_drain', 'exchange_supply_pressure', 'btc_rejecting_flow_tailwind'].includes(state)) {
        return 'bear';
    }
    if (['macro_neutral', 'liquidity_neutral', 'fund_flow_neutral'].includes(state)) {
        return 'neutral';
    }
    if (state === 'bearish_confirmation') {
        return 'bear';
    }
    return directionClass(state);
}
function moduleCompositeTone(module) {
    const score = Number(module.module_effective_score ?? module.module_score ?? 0);
    const stage = text(module.signal_stage ?? module.stage, '').toLowerCase();
    const effectiveDirection = text(module.module_effective_direction ?? module.effective_direction, '').toLowerCase();
    const rawDirection = text(module.module_direction ?? module.direction, '').toLowerCase();
    const implication = text(module.btc_implication, '').toLowerCase();
    const state = moduleDisplayState(module).toLowerCase();
    const supportCount = asList(module.support_drivers).length;
    const pressureCount = asList(module.pressure_drivers).length;
    const conflictCount = asList(module.conflict_drivers).length;
    const qualityCount = asList(module.data_quality_flags).length;
    const freshness = text(module.freshness_state ?? module.participation_policy, '').toLowerCase();
    const hasQualityIssue = qualityCount > 0 ||
        freshness.includes('stale') ||
        freshness.includes('blocked') ||
        freshness.includes('fallback') ||
        state.includes('data_quality');
    if (hasQualityIssue)
        return 'quality';
    if (conflictCount > 0 || effectiveDirection.includes('conflict') || rawDirection.includes('conflict'))
        return 'mixed';
    const isWarningStage = stage.includes('early_warning') || stage.includes('fast_signal') || stage.includes('watch');
    const isConfirmedStage = stage.includes('confirmed');
    const pressureLeads = pressureCount > supportCount;
    const supportLeads = supportCount > pressureCount;
    const bearishAccepted = effectiveDirection.includes('bearish') || rawDirection.includes('bearish');
    const bullishAccepted = effectiveDirection.includes('bullish') || rawDirection.includes('bullish');
    const fragilePressure = implication.includes('fragile') ||
        implication.includes('rejected') ||
        implication.includes('weak') ||
        state.includes('fragility') ||
        state.includes('warning') ||
        state.includes('pressure');
    if (isConfirmedStage && bearishAccepted && score <= -0.08)
        return 'bear';
    if (isConfirmedStage && bullishAccepted && score >= 0.08)
        return 'bull';
    if (isWarningStage && pressureLeads)
        return 'mixed';
    if (isWarningStage && supportLeads && score >= 0.08)
        return 'bull';
    if (isWarningStage && supportLeads)
        return 'mixed';
    if (pressureLeads && (score <= -0.08 || fragilePressure))
        return 'mixed';
    if (supportLeads && score >= 0.10)
        return 'bull';
    if (score <= -0.18 && pressureCount > 0)
        return 'bear';
    if (score >= 0.18 && supportCount > 0)
        return 'bull';
    if (Math.abs(score) < 0.08 && !pressureLeads && !supportLeads)
        return 'neutral';
    return 'legacy';
}
function moduleName(module) {
    return String(module.radar_module ?? module.module_id ?? 'module');
}
function shortModuleName(module) {
    return moduleName(module)
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase())
        .slice(0, 28);
}
function moduleMeta(module) {
    return moduleReadableSummary(module);
}
function moduleById(moduleId) {
    return store.radarModules.value.find((module) => moduleName(module) === moduleId) ?? {};
}
function defaultRadarModuleId() {
    const modules = store.radarModules.value;
    return moduleName(modules.find((module) => moduleName(module) === 'macro_radar') ?? modules[0] ?? {});
}
async function ensureDefaultRadarDetail() {
    if (activePage.value !== 'radar' || radarDefaultLoading.value || state.selectedRadarDetail)
        return;
    const moduleId = defaultRadarModuleId();
    if (!moduleId || moduleId === 'module')
        return;
    radarDefaultLoading.value = true;
    try {
        await openRadarDetail(moduleId);
    }
    finally {
        radarDefaultLoading.value = false;
    }
}
function radarScopeMetrics() {
    return selectedRadarMetrics.value.slice(0, 18);
}
function radarMetricStrength(metric) {
    return Math.abs(Number(metric.metric_effective_score ?? metric.metric_score ?? 0));
}
function radarMetricRail(side) {
    return selectedRadarTopMetrics.value.filter((_, index) => (side === 'left' ? index % 2 === 0 : index % 2 === 1));
}
function radarMetricBarWidth(metric) {
    const score = radarMetricStrength(metric);
    const width = Math.max(8, Math.min(100, (score / 0.1) * 100));
    return `${width}%`;
}
function radarMetricCompactMeta(metric) {
    const direction = text(metric.direction ?? metric.semantic_direction ?? metric.metric_direction, 'context');
    const score = text(metric.metric_effective_score ?? metric.metric_score);
    return `${direction} · score ${score}`;
}
function radarMetricAngle(index, total) {
    const count = Math.max(total, 1);
    return -90 + (360 / count) * index;
}
function radarMetricRadius(metric) {
    const score = Math.abs(Number(metric.metric_effective_score ?? metric.metric_score ?? 0));
    const normalized = Math.min(1, score / 0.1);
    return 34 + (1 - normalized) * 22;
}
function radarMetricPoint(metric, index, total) {
    const angle = (radarMetricAngle(index, total) * Math.PI) / 180;
    const radius = radarMetricRadius(metric);
    return {
        x: 50 + Math.cos(angle) * radius,
        y: 50 + Math.sin(angle) * radius,
    };
}
function radarSafePoint(metric, index, total) {
    const point = radarMetricPoint(metric, index, total);
    return {
        x: Math.max(8, Math.min(92, point.x)),
        y: Math.max(12, Math.min(88, point.y)),
    };
}
function radarNodeStyle(metric, index, total) {
    const point = radarSafePoint(metric, index, total);
    const quality = Number(metric.quality_score ?? 0.78);
    const scale = Math.max(0.78, Math.min(0.98, 0.7 + quality * 0.22));
    return {
        left: `${point.x}%`,
        top: `${point.y}%`,
        '--metric-scale': scale.toFixed(3),
    };
}
function radarLinkPath(metric, index, total) {
    const safePoint = radarSafePoint(metric, index, total);
    const dx = safePoint.x - 50;
    const dy = safePoint.y - 50;
    const distance = Math.max(1, Math.sqrt(dx * dx + dy * dy));
    const ux = dx / distance;
    const uy = dy / distance;
    const startOffset = 13;
    const endOffset = 3.6;
    const startX = 50 + ux * startOffset;
    const startY = 50 + uy * startOffset;
    const endX = safePoint.x - ux * endOffset;
    const endY = safePoint.y - uy * endOffset;
    return `M${(startX * 10).toFixed(1)} ${(startY * 6.4).toFixed(1)} L${(endX * 10).toFixed(1)} ${(endY * 6.4).toFixed(1)}`;
}
function radarMetricClass(metric) {
    if (metric.fallback_used || metric.is_stale || metric.available === false)
        return 'quality';
    return directionClass(metric.direction ?? metric.score_bucket);
}
function radarMetricWidth(metric) {
    const score = Math.abs(Number(metric.metric_effective_score ?? metric.metric_score ?? 0));
    return Math.max(1.4, Math.min(5.5, 1.8 + score * 42));
}
function radarMetricSummary(metric) {
    if (metric.price_response_state || metric.flow_price_efficiency_state || metric.price_response_source) {
        return `Price response ${text(metric.price_response_state, 'unknown')} · efficiency ${text(metric.flow_price_efficiency_state, 'unknown')} · source ${text(metric.price_response_source, 'unknown')}. This is a confirmation layer, not a standalone bullish/bearish trigger.`;
    }
    return readableMetricText(metric.p45_metric_brief ?? metric.metric_explanation ?? metric.score_reason ?? metric.metric_id);
}
function radarMetricValueScoreLine(metric) {
    const value = metric.value ?? metric.current_value;
    const score = metric.metric_effective_score ?? metric.metric_score;
    return `value ${text(value)} · score ${text(score)}`;
}
function hasTradeStructureStates(module) {
    return moduleName(module) === 'trade_structure_flow' && Boolean(module.trade_structure_flow_v23 ||
        module.signal_stage ||
        module.multi_horizon ||
        module.scores ||
        module.trade_structure_state ||
        module.aggressive_flow_state ||
        module.price_response_state ||
        module.liquidation_state ||
        module.mempool_pressure_state ||
        module.stablecoin_liquidity_state);
}
function tradeStructureStateRows(module) {
    const contract = tradeStructureFlowContract(module);
    return [
        ['stage', contract.signal_stage],
        ['state', contract.trade_structure_state],
        ['BTC', contract.btc_implication],
        ['aggressive', module.aggressive_flow_state],
        ['price', module.price_response_state],
        ['liquidation', module.liquidation_state],
        ['mempool', module.mempool_pressure_state],
        ['stablecoin', module.stablecoin_liquidity_state],
    ].filter((item) => item[1] != null && item[1] !== '');
}
function asRow(value) {
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}
function isBtcTotalStateModule(module) {
    return moduleName(module) === 'btc_total_state';
}
function isDerivativesCrowdingModule(module) {
    return moduleName(module) === 'derivatives_crowding';
}
function isTradeStructureFlowModule(module) {
    return moduleName(module) === 'trade_structure_flow';
}
function derivativesCrowdingContract(module) {
    const contract = asRow(module.derivatives_crowding_v25);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    return {
        semantic_profile_version: pick('semantic_profile_version'),
        module_direction: pick('module_direction'),
        module_score: pick('module_score'),
        confidence_score: pick('confidence_score'),
        signal_stage: pick('signal_stage'),
        derivatives_state: pick('derivatives_state') ?? pick('crowding_state') ?? pick('trend_state'),
        btc_implication: pick('btc_implication'),
        trend_prior: asRow(pick('trend_prior')),
        scores: asRow(pick('scores')),
        states: asRow(pick('states')),
        support_drivers: asList(pick('support_drivers')),
        pressure_drivers: asList(pick('pressure_drivers')),
        conflict_drivers: asList(pick('conflict_drivers')),
        early_warning_flags: asList(pick('early_warning_flags')),
        data_quality_flags: asList(pick('data_quality_flags')),
        proxy_flags: asList(pick('proxy_flags')),
        invalidation_conditions: asList(pick('invalidation_conditions')),
        summary: pick('display_summary') ?? pick('summary') ?? pick('trend_state_reason'),
    };
}
function derivativesCrowdingLayerCards(module) {
    const contract = derivativesCrowdingContract(module);
    const funding = asRow(contract.states.funding);
    const oi = asRow(contract.states.open_interest);
    const positioning = asRow(contract.states.positioning);
    const liquidation = asRow(contract.states.liquidation);
    const response = asRow(contract.states.btc_response);
    const residual = asRow(contract.states.trend_acceptance);
    return [
        {
            key: 'stage',
            title: 'Trend Acceptance',
            state: contract.signal_stage,
            meta: `state ${text(contract.derivatives_state, 'derivatives_neutral')} · BTC ${text(contract.btc_implication, 'neutral')}`,
            note: 'Derivatives pressure becomes direction only when BTC response, trend prior and standardized residual agree.',
            rows: [
                ['module_direction', contract.module_direction],
                ['module_score', contract.module_score],
                ['confidence_score', contract.confidence_score],
                ['semantic_profile_version', contract.semantic_profile_version],
            ],
        },
        {
            key: 'prior',
            title: 'Trend Prior',
            state: contract.trend_prior.btc_trend_state,
            meta: `strength ${text(contract.trend_prior.trend_strength_z)} · confidence ${text(contract.trend_prior.trend_confidence)}`,
            note: 'The same OI or funding impulse means different things in uptrend, downtrend, range and transition regimes.',
            rows: [
                ['trend_age_bars', contract.trend_prior.trend_age_bars],
                ['volatility_regime', contract.trend_prior.volatility_regime],
                ['btc_response_z_15m', response.btc_response_z_15m],
                ['btc_response_z_1h', response.btc_response_z_1h],
                ['btc_response_z_4h', response.btc_response_z_4h],
            ],
        },
        {
            key: 'scores',
            title: 'Scores',
            state: contract.module_direction,
            meta: `accept ${text(contract.scores.trend_acceptance_score)} · fragile ${text(contract.scores.crowding_fragility_score)} · squeeze ${text(contract.scores.squeeze_risk_score)}`,
            note: 'Crowding fragility is risk pressure. It is not automatically bearish unless price rejects the leveraged trend.',
            rows: [
                ['btc_acceptance_score', contract.scores.btc_acceptance_score],
                ['oi_participation_score', contract.scores.oi_participation_score],
                ['funding_basis_score', contract.scores.funding_basis_score],
                ['positioning_skew_score', contract.scores.positioning_skew_score],
                ['liquidation_response_score', contract.scores.liquidation_response_score],
                ['residual_confirmation_score', contract.scores.residual_confirmation_score],
            ],
        },
        {
            key: 'structure',
            title: 'Funding / OI / Positioning',
            state: oi.oi_participation_type,
            meta: `funding z ${text(funding.funding_rate_8h_equiv_z)} · OI z ${text(oi.oi_impulse_z_1h)} · retail ${text(positioning.retail_crowding_score)}`,
            note: 'Funding, OI and long/short ratios describe leverage participation and crowding, not standalone BTC direction.',
            rows: [
                ['predicted_funding_z', funding.predicted_funding_z],
                ['basis_acceptance_score', funding.basis_acceptance_score],
                ['oi_price_efficiency', oi.oi_price_efficiency],
                ['top_vs_global_positioning_gap_z', positioning.top_vs_global_positioning_gap_z],
                ['smart_money_divergence_score', positioning.smart_money_divergence_score],
            ],
        },
        {
            key: 'liquidation',
            title: 'Liquidation Response',
            state: contract.btc_implication,
            meta: `impulse ${text(liquidation.liquidation_impulse_z_15m)} · follow ${text(liquidation.liquidation_followthrough_score)} · absorb ${text(liquidation.liquidation_absorption_score)}`,
            note: 'Liquidation spikes need follow-through or absorption evidence. Snapshot-only streams are treated with lower confidence.',
            rows: [
                ['derivatives_pressure_z', residual.derivatives_pressure_z],
                ['expected_return_z', residual.derivatives_expected_return_z],
                ['derivatives_residual_z', residual.derivatives_residual_z],
                ['flags', contract.data_quality_flags.slice(0, 2).join(' | ')],
                ['proxy', contract.proxy_flags.slice(0, 2).join(' | ')],
            ],
        },
    ];
}
function isOptionsVolatilityModule(module) {
    return moduleName(module) === 'options_volatility';
}
function isEventPolicyModule(module) {
    return moduleName(module) === 'event_policy';
}
function isCryptoBreadthModule(module) {
    return moduleName(module) === 'crypto_breadth';
}
function isMacroRadarModule(module) {
    return moduleName(module) === 'macro_radar';
}
function isDollarLiquidityModule(module) {
    return moduleName(module) === 'dollar_liquidity';
}
function isTreasuryCreditModule(module) {
    return moduleName(module) === 'treasury_credit';
}
function isFundFlowModule(module) {
    return moduleName(module) === 'fund_flow';
}
function isBtcAdoptionModule(module) {
    return moduleName(module) === 'btc_adoption';
}
function isAsiaRiskModule(module) {
    return moduleName(module) === 'asia_risk';
}
function isKlineOrderflowModule(module) {
    return moduleName(module) === 'kline_orderflow';
}
function isOnchainValuationModule(module) {
    return moduleName(module) === 'onchain_valuation';
}
function derivativesCrowdingScopeText() {
    return 'Funding / OI here describe derivatives crowding, leverage heat and squeeze risk. BTC Total State reads them only with price_state as a composite short-term input.';
}
function btcTotalContract(module) {
    const contract = asRow(module.btc_total_state_v2);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    return {
        btc_short_term_state: pick('btc_short_term_state'),
        price_state: asRow(pick('price_state')),
        perp_state: asRow(pick('perp_state')),
        cycle_context: asRow(pick('cycle_context')),
        audit_context: asRow(pick('audit_context')),
        context_notes: asList(pick('context_notes')),
        audit_notes: asList(pick('audit_notes')),
    };
}
function btcTotalLayerCards(module) {
    const contract = btcTotalContract(module);
    const price = contract.price_state;
    const perp = contract.perp_state;
    const cycle = contract.cycle_context;
    const audit = contract.audit_context;
    return [
        {
            key: 'direction',
            title: '短线方向',
            state: contract.btc_short_term_state ?? module.module_effective_direction ?? module.module_direction,
            meta: `price ${text(price.state, 'missing')} · strength ${text(price.strength, 'unknown')}`,
            note: 'price_state + perp_state composite',
            rows: btcTotalBasisRows(price.basis),
        },
        {
            key: 'perp',
            title: '合约确认',
            state: perp.state,
            meta: `confirmation ${text(perp.confirmation)} · risk ${text(perp.risk_state)}`,
            note: 'Funding / OI confirm price state; neither is a standalone direction trigger.',
            rows: btcTotalBasisRows(perp.basis),
        },
        {
            key: 'cycle',
            title: '周期背景',
            state: cycle.state,
            meta: 'context only · no 24h direction weight',
            note: text(contract.context_notes[0], 'Halving is cycle background only.'),
            rows: btcTotalBasisRows(cycle.basis),
        },
        {
            key: 'audit',
            title: '数据审计',
            state: audit.state,
            meta: 'sync audit · no direction weight',
            note: text(contract.audit_notes[0], 'Block height checks data sync only.'),
            rows: btcTotalBasisRows(audit.basis),
        },
    ];
}
function btcTotalBasisRows(value) {
    const basis = asRow(value);
    return Object.entries(basis)
        .filter(([, entry]) => entry !== null && entry !== undefined && entry !== '')
        .slice(0, 4);
}
function optionsVolatilityContract(module) {
    const contract = asRow(module.options_volatility_v21);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    return {
        options_short_term_state: pick('options_short_term_state'),
        risk_score: pick('risk_score'),
        confidence_adjustment: pick('confidence_adjustment'),
        trade_permission_hint: pick('trade_permission_hint'),
        volatility_regime: asRow(pick('volatility_regime')),
        protection_demand: asRow(pick('protection_demand')),
        tail_risk: asRow(pick('tail_risk')),
        expiry_pressure: asRow(pick('expiry_pressure')),
        pinning_structure: asRow(pick('pinning_structure')),
        data_quality: asRow(pick('data_quality')),
        context_notes: asList(pick('context_notes')),
    };
}
function optionsVolatilityLayerCards(module) {
    const contract = optionsVolatilityContract(module);
    return [
        {
            key: 'volatility',
            title: 'Volatility Pricing',
            state: contract.volatility_regime.state,
            meta: `risk ${text(contract.risk_score)} · confidence ${text(contract.confidence_adjustment)}`,
            note: 'IV/RV pricing and change describe volatility regime, not direction.',
            rows: btcTotalBasisRows(contract.volatility_regime.basis),
        },
        {
            key: 'protection',
            title: 'Protection Demand',
            state: contract.protection_demand.state,
            meta: `hint ${text(contract.trade_permission_hint, 'normal')}`,
            note: 'Put-call and skew show hedging or chase demand, not standalone bearish/bullish.',
            rows: btcTotalBasisRows(contract.protection_demand.basis),
        },
        {
            key: 'tail',
            title: 'Tail Risk',
            state: contract.tail_risk.state,
            meta: `data ${text(contract.data_quality.state, 'usable')}`,
            note: 'Skew strength prices tail risk and should adjust risk mode.',
            rows: btcTotalBasisRows(contract.tail_risk.basis),
        },
        {
            key: 'expiry',
            title: 'Expiry Pressure',
            state: contract.expiry_pressure.state,
            meta: 'expiry context · no direction vote',
            note: 'Large nearby expiry may distort or release volatility.',
            rows: btcTotalBasisRows(contract.expiry_pressure.basis),
        },
        {
            key: 'pinning',
            title: 'Pinning Structure',
            state: contract.pinning_structure.state,
            meta: 'max pain / gamma wall',
            note: 'Near walls can reduce breakout confidence before expiry.',
            rows: btcTotalBasisRows(contract.pinning_structure.basis),
        },
    ];
}
function eventPolicyDefaultTradeGate() {
    return {
        allow_new_position: true,
        allow_add_position: true,
        allow_breakout_entry: true,
        allow_market_entry: true,
        position_size_multiplier: 1,
        require_wait_until_ts: null,
        reason_code: 'EVENT_NEUTRAL',
    };
}
function eventPolicyContract(module) {
    const contract = asRow(module.event_policy_v21);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    return {
        event_short_term_state: pick('event_short_term_state') ?? pick('trend_state'),
        event_window_phase: pick('event_window_phase'),
        event_risk_lock_level: pick('event_risk_lock_level') ?? pick('event_lock_level'),
        dominant_event_type: pick('dominant_event_type'),
        nearest_event_type: pick('nearest_event_type'),
        nearest_event_hours: pick('nearest_event_hours'),
        nearest_event_ts: pick('nearest_event_ts'),
        risk_score: pick('risk_score'),
        confidence_adjustment: pick('confidence_adjustment'),
        penalty_channel: pick('penalty_channel'),
        trade_gate: { ...eventPolicyDefaultTradeGate(), ...asRow(pick('trade_gate')) },
        risk_drivers: asList(pick('risk_drivers')),
        context_notes: asList(pick('context_notes')),
        summary: pick('summary') ?? pick('trend_state_reason'),
    };
}
function boolGateText(value) {
    return value === false ? 'blocked' : 'allowed';
}
function eventPolicyGateRows(gate) {
    return [
        ['new position', boolGateText(gate.allow_new_position)],
        ['add position', boolGateText(gate.allow_add_position)],
        ['breakout entry', boolGateText(gate.allow_breakout_entry)],
        ['market entry', boolGateText(gate.allow_market_entry)],
        ['size multiplier', gate.position_size_multiplier],
        ['reason', gate.reason_code],
    ].filter(([, value]) => value !== null && value !== undefined && value !== '');
}
function eventPolicyLayerCards(module) {
    const contract = eventPolicyContract(module);
    const gate = contract.trade_gate;
    return [
        {
            key: 'window',
            title: '事件窗口',
            state: contract.event_short_term_state ?? 'event_neutral',
            meta: `phase ${text(contract.event_window_phase, 'neutral')} · lock ${text(contract.event_risk_lock_level, 'none')}`,
            note: text(contract.summary, 'No active event gate is restricting trade permission.'),
            rows: [
                ['dominant', contract.dominant_event_type ?? 'none'],
                ['nearest', contract.nearest_event_type ?? 'none'],
                ['hours', contract.nearest_event_hours ?? 'n/a'],
                ['ts', contract.nearest_event_ts ?? 'n/a'],
            ],
        },
        {
            key: 'gate',
            title: '交易门控',
            state: gate.reason_code ?? 'EVENT_NEUTRAL',
            meta: `size ${text(gate.position_size_multiplier, '1')} · breakout ${boolGateText(gate.allow_breakout_entry)}`,
            note: 'Trade gate is executable permission context, not a BTC direction vote.',
            rows: eventPolicyGateRows(gate),
        },
        {
            key: 'risk',
            title: '风险锁定',
            state: contract.event_risk_lock_level ?? 'none',
            meta: `risk ${text(contract.risk_score, '0')} · confidence ${text(contract.confidence_adjustment, '0')}`,
            note: `penalty ${text(contract.penalty_channel, 'event_timing_only')}`,
            rows: [
                ['risk_score', contract.risk_score ?? 0],
                ['confidence_adjustment', contract.confidence_adjustment ?? 0],
                ['penalty_channel', contract.penalty_channel ?? 'event_timing_only'],
            ],
        },
        {
            key: 'context',
            title: '上下文说明',
            state: contract.risk_drivers.length ? `${contract.risk_drivers.length} risk drivers` : 'context only',
            meta: 'not directional alpha',
            note: text(contract.context_notes[0], 'Event timing changes trade permission, not final direction.'),
            rows: contract.context_notes.slice(0, 4).map((note, index) => [`note ${index + 1}`, note]),
        },
    ];
}
function cryptoBreadthContract(module) {
    const contract = asRow(module.crypto_breadth_v3);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    return {
        crypto_breadth_state: pick('crypto_breadth_state'),
        btc_implication: pick('btc_implication'),
        module_direction: pick('module_direction'),
        module_score: pick('module_score'),
        risk_score: pick('risk_score'),
        confidence_adjustment: pick('confidence_adjustment'),
        btc_trend_anchor: asRow(pick('btc_trend_anchor')),
        breadth_participation: asRow(pick('breadth_participation')),
        market_cap_diffusion: asRow(pick('market_cap_diffusion')),
        btc_vs_alt_leadership: asRow(pick('btc_vs_alt_leadership')),
        sector_risk_appetite: asRow(pick('sector_risk_appetite')),
        breadth_quality: asRow(pick('breadth_quality')),
        support_drivers: asList(pick('support_drivers')),
        pressure_drivers: asList(pick('pressure_drivers')),
        risk_drivers: asList(pick('risk_drivers')),
        context_notes: asList(pick('context_notes')),
        summary: pick('summary') ?? pick('display_summary') ?? pick('trend_state_reason'),
    };
}
function cryptoBreadthLayerCards(module) {
    const contract = cryptoBreadthContract(module);
    return [
        {
            key: 'btc-anchor',
            title: 'BTC Trend Anchor',
            state: contract.btc_trend_anchor.state,
            meta: `score ${text(contract.btc_trend_anchor.score)} · implication ${text(contract.btc_implication, 'neutral')}`,
            note: 'BTC own trend is the anchor; breadth only confirms or refutes its quality.',
            rows: btcTotalBasisRows(contract.btc_trend_anchor.basis),
        },
        {
            key: 'breadth',
            title: 'Top50 Breadth',
            state: contract.breadth_participation.state,
            meta: `support ${text(contract.support_drivers.length)} · pressure ${text(contract.pressure_drivers.length)}`,
            note: 'Advance ratio, A/D slope and equal-vs-cap return show whether participation is broad.',
            rows: btcTotalBasisRows(contract.breadth_participation.basis),
        },
        {
            key: 'diffusion',
            title: 'Market Cap Diffusion',
            state: contract.market_cap_diffusion.state,
            meta: `direction ${text(contract.module_direction)} · score ${text(contract.module_score)}`,
            note: 'TOTAL/TOTAL2 relative movement detects BTC-only rallies versus broader crypto expansion.',
            rows: btcTotalBasisRows(contract.market_cap_diffusion.basis),
        },
        {
            key: 'leadership',
            title: 'BTC vs Alt Leadership',
            state: contract.btc_vs_alt_leadership.state,
            meta: 'BTC.D / ETHBTC / stablecoin leadership',
            note: 'Dominance and ETHBTC are interpreted together with BTC trend and market breadth.',
            rows: btcTotalBasisRows(contract.btc_vs_alt_leadership.basis),
        },
        {
            key: 'sector',
            title: 'Sector Risk Appetite',
            state: contract.sector_risk_appetite.state,
            meta: `risk ${text(contract.risk_score)} · confidence ${text(contract.confidence_adjustment)}`,
            note: 'Sector heat supports risk-on only when it is not just concentrated overheat.',
            rows: btcTotalBasisRows(contract.sector_risk_appetite.basis),
        },
        {
            key: 'quality',
            title: 'Breadth Quality',
            state: contract.breadth_quality.state,
            meta: contract.risk_drivers.length ? `${contract.risk_drivers.length} risk drivers` : 'quality check',
            note: 'Divergence, concentration and overheat penalties prevent blind bullish scoring.',
            rows: btcTotalBasisRows(contract.breadth_quality.basis),
        },
    ];
}
function macroRadarContract(module) {
    const contract = asRow(module.macro_radar_v3);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    return {
        macro_trend_state: pick('macro_trend_state'),
        btc_implication: pick('btc_implication'),
        module_direction: pick('module_direction'),
        module_score: pick('module_score'),
        risk_score: pick('risk_score'),
        confidence_adjustment: pick('confidence_adjustment'),
        equity_beta: asRow(pick('equity_beta')),
        rates_pressure: asRow(pick('rates_pressure')),
        dollar_pressure: asRow(pick('dollar_pressure')),
        volatility_stress: asRow(pick('volatility_stress')),
        financial_stress: asRow(pick('financial_stress')),
        commodity_context: asRow(pick('commodity_context')),
        macro_impulse: asRow(pick('macro_impulse')),
        btc_relative_confirmation: asRow(pick('btc_relative_confirmation')),
        event_window: asRow(pick('event_window')),
        support_drivers: asList(pick('support_drivers')),
        pressure_drivers: asList(pick('pressure_drivers')),
        risk_drivers: asList(pick('risk_drivers')),
        invalidation_conditions: asList(pick('invalidation_conditions')),
        context_notes: asList(pick('context_notes')),
        summary: pick('summary') ?? pick('display_summary') ?? pick('trend_state_reason'),
    };
}
function macroRadarLayerCards(module) {
    const contract = macroRadarContract(module);
    const btcRelativeMissingReason = contract.btc_relative_confirmation.missing_reason;
    return [
        {
            key: 'equity',
            title: 'Equity Beta',
            state: contract.equity_beta.state,
            meta: `score ${text(contract.equity_beta.score)} · breadth ${text(asRow(contract.equity_beta.basis).equity_breadth_score)}`,
            note: 'Equity beta tells whether risk assets confirm BTC trend; it is not a standalone BTC call.',
            rows: btcTotalBasisRows(contract.equity_beta.basis),
        },
        {
            key: 'rates',
            title: 'Rates Pressure',
            state: contract.rates_pressure.state,
            meta: `risk ${text(contract.rates_pressure.risk_score)} · score ${text(contract.rates_pressure.score)}`,
            note: 'US2Y/US10Y/real yield changes describe financial-condition pressure on BTC beta.',
            rows: btcTotalBasisRows(contract.rates_pressure.basis),
        },
        {
            key: 'dollar',
            title: 'Dollar Pressure',
            state: contract.dollar_pressure.state,
            meta: `score ${text(contract.dollar_pressure.score)}`,
            note: 'DXY impulse is interpreted with rates, volatility and BTC residual.',
            rows: btcTotalBasisRows(contract.dollar_pressure.basis),
        },
        {
            key: 'volatility',
            title: 'Volatility Stress',
            state: contract.volatility_stress.state,
            meta: `risk ${text(contract.volatility_stress.risk_score)} · score ${text(contract.volatility_stress.score)}`,
            note: 'VIX primarily adjusts risk and breakout confidence, not direct direction.',
            rows: btcTotalBasisRows(contract.volatility_stress.basis),
        },
        {
            key: 'stress',
            title: 'Financial Stress',
            state: contract.financial_stress.state,
            meta: `risk ${text(contract.financial_stress.risk_score)} · score ${text(contract.financial_stress.score)}`,
            note: 'OFR FSI captures broad financial stress context.',
            rows: btcTotalBasisRows(contract.financial_stress.basis),
        },
        {
            key: 'commodity',
            title: 'Commodity Context',
            state: contract.commodity_context.state,
            meta: `score ${text(contract.commodity_context.score)}`,
            note: 'Gold and oil are context layers; they do not independently flip BTC direction.',
            rows: btcTotalBasisRows(contract.commodity_context.basis),
        },
        {
            key: 'impulse',
            title: 'Macro Impulse',
            state: contract.macro_impulse.state,
            meta: `risk drivers ${text(contract.risk_drivers.length)} · confidence ${text(contract.confidence_adjustment)}`,
            note: 'Fast cross-asset shocks can raise risk mode before the environment score fully changes.',
            rows: btcTotalBasisRows(contract.macro_impulse.basis),
        },
        {
            key: 'btc-relative',
            title: 'BTC Relative Confirmation',
            state: contract.btc_relative_confirmation.state,
            meta: btcRelativeMissingReason
                ? `missing ${text(btcRelativeMissingReason)}`
                : `residual ${text(contract.btc_relative_confirmation.btc_beta_residual)} · BTC ${text(contract.btc_implication, 'neutral')}`,
            note: 'BTC residual decides whether macro tailwind/headwind is absorbed, rejected or resisted.',
            rows: btcTotalBasisRows(contract.btc_relative_confirmation.basis),
        },
    ];
}
function dollarLiquidityContract(module) {
    const contract = asRow(module.dollar_liquidity_v21);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    return {
        dollar_liquidity_state: pick('dollar_liquidity_state'),
        module_direction: pick('module_direction'),
        module_score: pick('module_score'),
        risk_score: pick('risk_score'),
        confidence_score: pick('confidence_score') ?? pick('confidence_adjustment'),
        data_freshness: asRow(pick('data_freshness')),
        liquidity_level: asRow(pick('liquidity_level')),
        liquidity_impulse: asRow(pick('liquidity_impulse')),
        reserve_buffer: asRow(pick('reserve_buffer')),
        liquidity_drain_pressure: asRow(pick('liquidity_drain_pressure')),
        repo_funding_pressure: asRow(pick('repo_funding_pressure')),
        btc_response_confirmation: asRow(pick('btc_response_confirmation')),
        regime_state: asRow(pick('regime_state')),
        support_drivers: asList(pick('support_drivers')),
        pressure_drivers: asList(pick('pressure_drivers')),
        risk_drivers: asList(pick('risk_drivers')),
        context_notes: asList(pick('context_notes')),
        summary: pick('summary') ?? pick('display_summary') ?? pick('trend_state_reason'),
    };
}
function dollarLiquidityLayerCards(module) {
    const contract = dollarLiquidityContract(module);
    return [
        {
            key: 'freshness',
            title: 'Data Freshness',
            state: contract.data_freshness.is_stale ? 'stale' : 'fresh',
            meta: `weekly ${text(contract.data_freshness.weekly_macro_asof, 'n/a')} · daily ${text(contract.data_freshness.daily_funding_asof, 'n/a')}`,
            note: 'Weekly Fed data, daily funding data and BTC response are read on separate clocks.',
            rows: btcTotalBasisRows(contract.data_freshness),
        },
        {
            key: 'level',
            title: 'Liquidity Level',
            state: contract.liquidity_level.rrp_depleted ? 'rrp_depleted' : 'liquidity_level',
            meta: `net ${text(contract.liquidity_level.net_liquidity_proxy_bil)} bil`,
            note: 'Net liquidity level is context; marginal impulse and BTC response decide confirmation.',
            rows: btcTotalBasisRows(contract.liquidity_level),
        },
        {
            key: 'impulse',
            title: 'Liquidity Impulse',
            state: contract.liquidity_impulse.state,
            meta: `1w ${text(contract.liquidity_impulse.net_liquidity_change_1w_bil)} bil · z ${text(contract.liquidity_impulse.liquidity_impulse_z)}`,
            note: 'Impulse captures the marginal change, acceleration and surprise of USD liquidity.',
            rows: btcTotalBasisRows(contract.liquidity_impulse),
        },
        {
            key: 'reserve',
            title: 'Reserve Buffer',
            state: contract.reserve_buffer.state,
            meta: `change ${text(contract.reserve_buffer.reserve_change_1w_bil)} bil`,
            note: 'Bank reserve changes show whether the liquidity buffer is improving or draining.',
            rows: btcTotalBasisRows(contract.reserve_buffer),
        },
        {
            key: 'drain',
            title: 'TGA / RRP Drain',
            state: contract.liquidity_drain_pressure.state,
            meta: `TGA ${text(contract.liquidity_drain_pressure.tga_change_1w_bil)} bil · RRP ${text(contract.liquidity_level.on_rrp_bil)} bil`,
            note: 'TGA drain can support liquidity; depleted RRP means the old release buffer is limited.',
            rows: btcTotalBasisRows(contract.liquidity_drain_pressure),
        },
        {
            key: 'funding',
            title: 'Repo Funding Pressure',
            state: contract.repo_funding_pressure.state,
            meta: `SOFR-IORB ${text(contract.repo_funding_pressure.sofr_iorb_spread_bps)} bps · stress ${text(contract.repo_funding_pressure.funding_stress_z)}`,
            note: 'SOFR is interpreted versus IORB and stress z-score, not as a standalone BTC direction signal.',
            rows: btcTotalBasisRows(contract.repo_funding_pressure),
        },
        {
            key: 'btc-response',
            title: 'BTC Response Confirmation',
            state: contract.btc_response_confirmation.state,
            meta: `5d ${text(contract.btc_response_confirmation.btc_5d_return)} · residual ${text(contract.btc_response_confirmation.btc_vs_liquidity_residual)}`,
            note: 'BTC response decides whether liquidity tailwind/headwind is absorbed, rejected or resisted.',
            rows: btcTotalBasisRows(contract.btc_response_confirmation),
        },
        {
            key: 'regime',
            title: 'Regime State',
            state: contract.dollar_liquidity_state ?? contract.regime_state.state,
            meta: `direction ${text(contract.module_direction)} · score ${text(contract.module_score)} · risk ${text(contract.risk_score)}`,
            note: text(contract.summary, 'Dollar Liquidity confirms or refutes BTC trend through USD liquidity and funding conditions.'),
            rows: [
                ['confidence', contract.confidence_score],
                ['support drivers', contract.support_drivers.length],
                ['pressure drivers', contract.pressure_drivers.length],
                ['risk drivers', contract.risk_drivers.length],
            ],
        },
    ];
}
function treasuryCreditContract(module) {
    const contract = asRow(module.treasury_credit_v21);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    const states = asRow(pick('states'));
    return {
        treasury_credit_state: pick('treasury_credit_state'),
        btc_implication: pick('btc_implication'),
        module_direction: pick('module_direction'),
        module_score: pick('module_score'),
        risk_score: pick('risk_score'),
        confidence_adjustment: pick('confidence_adjustment'),
        timeframe: asRow(pick('timeframe')),
        states,
        policy_rate_pressure: asRow(states.policy_rate_pressure),
        real_yield_pressure: asRow(states.real_yield_pressure),
        duration_term_pressure: asRow(states.duration_term_pressure),
        curve_regime: asRow(states.curve_regime),
        inflation_mix: asRow(states.inflation_mix),
        credit_stress: asRow(states.credit_stress),
        btc_response_confirmation: asRow(states.btc_response_confirmation),
        support_drivers: asList(pick('support_drivers')),
        pressure_drivers: asList(pick('pressure_drivers')),
        risk_drivers: asList(pick('risk_drivers')),
        early_warning_flags: asList(pick('early_warning_flags')),
        data_quality_flags: asList(pick('data_quality_flags')),
        context_notes: asList(pick('context_notes')),
        summary: pick('summary') ?? pick('display_summary') ?? pick('trend_state_reason'),
    };
}
function treasuryCreditLayerCards(module) {
    const contract = treasuryCreditContract(module);
    return [
        {
            key: 'policy',
            title: 'Policy Rate Pressure',
            state: contract.policy_rate_pressure.state,
            meta: `score ${text(contract.policy_rate_pressure.score)} · risk ${text(contract.policy_rate_pressure.risk_score)}`,
            note: '2Y changes show policy-rate repricing. Level alone is not a BTC direction signal.',
            rows: btcTotalBasisRows(contract.policy_rate_pressure.basis),
        },
        {
            key: 'real-yield',
            title: 'Real Yield Pressure',
            state: contract.real_yield_pressure.state,
            meta: `score ${text(contract.real_yield_pressure.score)} · risk ${text(contract.real_yield_pressure.risk_score)}`,
            note: 'Real yield changes capture actual discount-rate pressure on high beta risk assets.',
            rows: btcTotalBasisRows(contract.real_yield_pressure.basis),
        },
        {
            key: 'duration',
            title: 'Duration / Term Pressure',
            state: contract.duration_term_pressure.state,
            meta: `score ${text(contract.duration_term_pressure.score)} · risk ${text(contract.duration_term_pressure.risk_score)}`,
            note: '10Y/30Y moves are separated from policy pressure and treated as duration/term-premium context.',
            rows: btcTotalBasisRows(contract.duration_term_pressure.basis),
        },
        {
            key: 'curve',
            title: 'Curve Regime',
            state: contract.curve_regime.state,
            meta: `score ${text(contract.curve_regime.score)} · 2s10s ${text(asRow(contract.curve_regime.basis).yield_curve_2s10s_bps)} bps`,
            note: 'Curve moves distinguish policy pressure, reflation, and growth-scare bond rallies.',
            rows: btcTotalBasisRows(contract.curve_regime.basis),
        },
        {
            key: 'inflation',
            title: 'Inflation Mix',
            state: contract.inflation_mix.state,
            meta: `score ${text(contract.inflation_mix.score)}`,
            note: '10Y up is not always bearish: breakeven-led reflation differs from real-rate tightening.',
            rows: btcTotalBasisRows(contract.inflation_mix.basis),
        },
        {
            key: 'credit',
            title: 'Credit Stress',
            state: contract.credit_stress.state,
            meta: `risk ${text(contract.credit_stress.risk_score)} · warnings ${text(contract.early_warning_flags.length)}`,
            note: 'HY OAS speed and z-score are early warning inputs, not standalone BTC short calls.',
            rows: btcTotalBasisRows(contract.credit_stress.basis),
        },
        {
            key: 'btc-response',
            title: 'BTC Response Confirmation',
            state: contract.btc_response_confirmation.state,
            meta: `BTC ${text(contract.btc_implication, 'neutral')} · residual ${text(asRow(contract.btc_response_confirmation.basis).btc_residual_24h)}`,
            note: 'BTC residual decides whether rates/credit tailwind or headwind is absorbed, rejected, or resisted.',
            rows: btcTotalBasisRows(contract.btc_response_confirmation.basis),
        },
    ];
}
function fundFlowContract(module) {
    const contract = asRow(module.fund_flow_v22);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    const states = asRow(pick('states'));
    const scores = asRow(pick('scores'));
    return {
        fund_flow_state: pick('fund_flow_state'),
        btc_implication: pick('btc_implication'),
        module_direction: pick('module_direction'),
        module_score: pick('module_score'),
        risk_score: pick('risk_score'),
        confidence_score: pick('confidence_score'),
        scores,
        states,
        etf_demand: asRow(states.etf_demand),
        stablecoin_liquidity: asRow(states.stablecoin_liquidity),
        exchange_supply: asRow(states.exchange_supply),
        btc_response_confirmation: asRow(states.btc_response_confirmation),
        support_drivers: asList(pick('support_drivers')),
        pressure_drivers: asList(pick('pressure_drivers')),
        early_warning_flags: asList(pick('early_warning_flags')),
        data_quality_flags: asList(pick('data_quality_flags')),
        summary: pick('summary') ?? pick('display_summary') ?? pick('trend_state_reason'),
    };
}
function fundFlowLayerCards(module) {
    const contract = fundFlowContract(module);
    return [
        {
            key: 'etf',
            title: 'ETF Demand',
            state: contract.etf_demand.state,
            meta: `score ${text(contract.scores.etf_demand_score)} · 3d ${text(contract.etf_demand.flow_3d_usd)}`,
            note: 'ETF flow is marginal demand pressure. It becomes trend confirmation only when BTC accepts it.',
            rows: [
                ['flow_1d_z', contract.etf_demand.flow_1d_z],
                ['flow_3d_usd', contract.etf_demand.flow_3d_usd],
                ['flow_7d_usd', contract.etf_demand.flow_7d_usd],
                ['inflow_streak_days', contract.etf_demand.inflow_streak_days],
                ['outflow_streak_days', contract.etf_demand.outflow_streak_days],
                ['flow_acceleration_3d', contract.etf_demand.flow_acceleration_3d],
            ],
        },
        {
            key: 'stablecoin',
            title: 'Stablecoin Liquidity',
            state: contract.stablecoin_liquidity.state,
            meta: `score ${text(contract.scores.stablecoin_liquidity_score)} · ssr z ${text(contract.stablecoin_liquidity.ssr_z_180d)}`,
            note: 'Stablecoin growth is liquidity background, not a standalone strong BTC buy signal.',
            rows: [
                ['mcap_change_7d', contract.stablecoin_liquidity.mcap_change_7d],
                ['mcap_change_30d', contract.stablecoin_liquidity.mcap_change_30d],
                ['ssr_z_180d', contract.stablecoin_liquidity.ssr_z_180d],
            ],
        },
        {
            key: 'exchange',
            title: 'Exchange Supply',
            state: contract.exchange_supply.state,
            meta: `score ${text(contract.scores.exchange_supply_score)} · z ${text(contract.exchange_supply.btc_exchange_netflow_z_60d)}`,
            note: 'Exchange netflow is supply context and is downgraded when internal-transfer risk is high.',
            rows: [
                ['btc_exchange_netflow_1d', contract.exchange_supply.btc_exchange_netflow_1d],
                ['btc_exchange_netflow_7d', contract.exchange_supply.btc_exchange_netflow_7d],
                ['btc_exchange_netflow_z_60d', contract.exchange_supply.btc_exchange_netflow_z_60d],
                ['large_single_transfer_flag', contract.exchange_supply.large_single_transfer_flag],
                ['exchange_flow_confirmed', contract.exchange_supply.exchange_flow_confirmed],
            ],
        },
        {
            key: 'btc-response',
            title: 'BTC Response',
            state: contract.btc_response_confirmation.state,
            meta: `score ${text(contract.scores.btc_response_score)} · residual z ${text(contract.btc_response_confirmation.residual_z_60d)}`,
            note: 'BTC response is the veto layer: accepting, rejecting or resisting the fund-flow setup.',
            rows: [
                ['btc_return_4h', contract.btc_response_confirmation.btc_return_4h],
                ['btc_return_24h', contract.btc_response_confirmation.btc_return_24h],
                ['expected_return_24h', contract.btc_response_confirmation.expected_return_24h],
                ['residual_24h', contract.btc_response_confirmation.residual_24h],
                ['residual_z_60d', contract.btc_response_confirmation.residual_z_60d],
            ],
        },
    ];
}
function onchainValuationContract(module) {
    const contract = asRow(module.onchain_valuation_v22);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    const states = asRow(pick('states'));
    const scores = asRow(pick('scores'));
    return {
        onchain_valuation_state: pick('onchain_valuation_state'),
        signal_stage: pick('signal_stage'),
        btc_implication: pick('btc_implication'),
        module_direction: pick('module_direction'),
        module_bias: pick('module_bias'),
        module_score: pick('module_score'),
        trend_delta_score: pick('trend_delta_score'),
        regime_score: pick('regime_score'),
        confidence_score: pick('confidence_score'),
        scores,
        states,
        key_levels: asRow(pick('key_levels')),
        valuation_regime: asRow(states.valuation_regime),
        cost_basis: asRow(states.cost_basis),
        profit_realization: asRow(states.profit_realization),
        btc_response_confirmation: asRow(states.btc_response_confirmation),
        support_drivers: asList(pick('support_drivers')),
        pressure_drivers: asList(pick('pressure_drivers')),
        early_warning_flags: asList(pick('early_warning_flags')),
        proxy_flags: asList(pick('proxy_flags')),
        data_quality_flags: asList(pick('data_quality_flags')),
        invalidation_conditions: asList(pick('invalidation_conditions')),
        summary: pick('summary') ?? pick('display_summary') ?? pick('trend_state_reason'),
    };
}
function onchainValuationLayerCards(module) {
    const contract = onchainValuationContract(module);
    return [
        {
            key: 'regime',
            title: 'Regime Background',
            state: contract.module_bias,
            meta: `regime ${text(contract.regime_score)} · valuation ${text(contract.scores.valuation_regime_score)}`,
            note: 'MVRV/NUPL describe slow valuation regime. They do not confirm short-term BTC direction alone.',
            rows: [
                ['mvrv_zscore', contract.valuation_regime.mvrv_zscore],
                ['mvrv_ratio', contract.valuation_regime.mvrv_ratio],
                ['nupl', contract.valuation_regime.nupl],
                ['realized_cap_trend_score', contract.scores.realized_cap_trend_score],
            ],
        },
        {
            key: 'trend-delta',
            title: 'Trend Delta',
            state: contract.signal_stage,
            meta: `trend ${text(contract.trend_delta_score)} · state ${text(contract.onchain_valuation_state, 'onchain_neutral')}`,
            note: 'Trend delta is driven by BTC response, cost-basis reaction, SOPR delta and realized-cap impulse.',
            rows: [
                ['btc_response_score', contract.scores.btc_response_score],
                ['cost_basis_reaction_score', contract.scores.cost_basis_reaction_score],
                ['profit_realization_delta_score', contract.scores.profit_realization_delta_score],
                ['realized_cap_impulse_score', contract.scores.realized_cap_impulse_score],
            ],
        },
        {
            key: 'key-levels',
            title: 'Cost Basis Levels',
            state: contract.cost_basis.state,
            meta: `STH band ${text(contract.cost_basis.sth_band_pct)} · distance ${text(contract.cost_basis.btc_vs_sth_cost_basis_pct)}`,
            note: 'STH reclaim/rejection uses a dynamic volatility band, not a fixed 2% threshold.',
            rows: [
                ['realized_price', contract.key_levels.realized_price],
                ['sth_cost_basis', contract.key_levels.sth_cost_basis],
                ['sth_upper_band', contract.key_levels.sth_upper_band],
                ['sth_lower_band', contract.key_levels.sth_lower_band],
                ['lth_cost_basis', contract.key_levels.lth_cost_basis],
            ],
        },
        {
            key: 'profit',
            title: 'SOPR / Profit Realization',
            state: contract.profit_realization.state,
            meta: `SOPR ${text(contract.profit_realization.sopr)} · z ${text(contract.profit_realization.sopr_z_90d)}`,
            note: 'SOPR crossing 1 is a fast signal until price response and residual confirm it.',
            rows: [
                ['sopr_cross_1_direction', contract.profit_realization.sopr_cross_1_direction],
                ['sopr_above_1_streak_days', contract.profit_realization.sopr_above_1_streak_days],
                ['sopr_below_1_streak_days', contract.profit_realization.sopr_below_1_streak_days],
                ['btc_implication', contract.btc_implication],
            ],
        },
        {
            key: 'btc-response',
            title: 'BTC Response',
            state: contract.btc_response_confirmation.state,
            meta: `residual z ${text(contract.btc_response_confirmation.residual_z_90d)} · expected ${text(contract.btc_response_confirmation.expected_return_24h)}`,
            note: 'BTC residual decides whether on-chain tailwind/headwind is accepted, rejected or resisted.',
            rows: [
                ['btc_return_4h', contract.btc_response_confirmation.btc_return_4h],
                ['btc_return_24h', contract.btc_response_confirmation.btc_return_24h],
                ['btc_return_3d', contract.btc_response_confirmation.btc_return_3d],
                ['residual_24h', contract.btc_response_confirmation.residual_24h],
            ],
        },
        {
            key: 'governance',
            title: 'Proxy / Invalidation',
            state: contract.proxy_flags.length ? 'proxy_context' : 'exact_or_derived',
            meta: `proxy ${text(contract.proxy_flags.length)} · invalidation ${text(contract.invalidation_conditions.length)}`,
            note: 'Tier-3 miner/whale proxies are context only and cannot trigger confirmed signals.',
            rows: [
                ['proxy_flags', contract.proxy_flags.join(', ')],
                ['data_quality_flags', contract.data_quality_flags.join(', ')],
                ['early_warning_flags', contract.early_warning_flags.join(', ')],
                ['invalidation', contract.invalidation_conditions.slice(0, 2).join(' | ')],
            ],
        },
    ];
}
function btcAdoptionContract(module) {
    const contract = asRow(module.btc_adoption_v23);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    const states = asRow(pick('states'));
    const scores = asRow(pick('scores'));
    return {
        btc_adoption_state: pick('btc_adoption_state'),
        signal_stage: pick('signal_stage'),
        btc_implication: pick('btc_implication'),
        module_direction: pick('module_direction'),
        module_score: pick('module_score'),
        confidence_score: pick('confidence_score'),
        scores,
        states,
        activity: asRow(states.activity),
        settlement: asRow(states.settlement),
        fee_mempool: asRow(states.fee_mempool),
        security: asRow(states.security),
        lightning: asRow(states.lightning),
        btc_response_confirmation: asRow(states.btc_response_confirmation),
        support_drivers: asList(pick('support_drivers')),
        pressure_drivers: asList(pick('pressure_drivers')),
        conflict_drivers: asList(pick('conflict_drivers')),
        early_warning_flags: asList(pick('early_warning_flags')),
        proxy_flags: asList(pick('proxy_flags')),
        data_quality_flags: asList(pick('data_quality_flags')),
        invalidation_conditions: asList(pick('invalidation_conditions')),
        summary: pick('summary') ?? pick('display_summary') ?? pick('trend_state_reason'),
    };
}
function btcAdoptionLayerCards(module) {
    const contract = btcAdoptionContract(module);
    return [
        {
            key: 'fast',
            title: 'Fast Layer',
            state: contract.signal_stage,
            meta: `fast ${text(contract.scores.fast_trend_score)} · BTC ${text(contract.scores.btc_response_score)}`,
            note: 'Fast layer captures 0h-24h fee/mempool pressure, short activity impulse and BTC response.',
            rows: [
                ['btc_response_score', contract.scores.btc_response_score],
                ['fee_mempool_score', contract.scores.fee_mempool_score],
                ['activity_state', contract.activity.state],
                ['fee_state', contract.fee_mempool.state],
            ],
        },
        {
            key: 'core',
            title: 'Core Confirmation',
            state: contract.settlement.state,
            meta: `core ${text(contract.scores.core_confirmation_score)} · settlement ${text(contract.scores.settlement_demand_score)}`,
            note: 'Core layer confirms whether chain usage is real economic settlement, not just raw address or tx count noise.',
            rows: [
                ['activity_quality_score', contract.scores.activity_quality_score],
                ['settlement_demand_score', contract.scores.settlement_demand_score],
                ['nvt_proxy_change_7d', contract.settlement.nvt_proxy_change_7d],
                ['transfer_volume_adjusted_usd_z_60d', contract.settlement.transfer_volume_adjusted_usd_z_60d],
            ],
        },
        {
            key: 'regime',
            title: 'Regime Context',
            state: contract.security.state,
            meta: `regime ${text(contract.scores.regime_context_score)} · L2 ${text(contract.scores.l2_adoption_score)}`,
            note: 'Hashrate, hashprice and Lightning are regime context; they do not confirm short-term direction alone.',
            rows: [
                ['network_security_score', contract.scores.network_security_score],
                ['miner_pressure_score', contract.scores.miner_pressure_score],
                ['lightning_state', contract.lightning.state],
                ['hashprice_z_90d', contract.security.hashprice_z_90d],
            ],
        },
        {
            key: 'btc-response',
            title: 'BTC Response',
            state: contract.btc_response_confirmation.state,
            meta: `residual z ${text(contract.btc_response_confirmation.residual_z_90d)} · expected ${text(contract.btc_response_confirmation.expected_return_24h)}`,
            note: 'BTC response decides whether adoption tailwind is accepted, rejected or resisted.',
            rows: [
                ['btc_return_4h', contract.btc_response_confirmation.btc_return_4h],
                ['btc_return_24h', contract.btc_response_confirmation.btc_return_24h],
                ['btc_return_3d', contract.btc_response_confirmation.btc_return_3d],
                ['residual_24h', contract.btc_response_confirmation.residual_24h],
            ],
        },
        {
            key: 'governance',
            title: 'Proxy / Invalidation',
            state: contract.proxy_flags.length ? 'proxy_context' : 'quality_checked',
            meta: `proxy ${text(contract.proxy_flags.length)} · invalidation ${text(contract.invalidation_conditions.length)}`,
            note: 'Raw address counts and unavailable entity-adjusted sources are shown as proxy/data-quality boundaries.',
            rows: [
                ['proxy_flags', contract.proxy_flags.join(', ')],
                ['data_quality_flags', contract.data_quality_flags.join(', ')],
                ['conflict_drivers', contract.conflict_drivers.join(', ')],
                ['invalidation', contract.invalidation_conditions.slice(0, 2).join(' | ')],
            ],
        },
    ];
}
function asiaRiskContract(module) {
    const contract = asRow(module.asia_risk_v23);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    const states = asRow(pick('states'));
    const scores = asRow(pick('scores'));
    const btcResponse = asRow(pick('btc_response'));
    return {
        asia_risk_state: pick('asia_risk_state'),
        signal_stage: pick('signal_stage'),
        btc_implication: pick('btc_implication'),
        module_direction: pick('module_direction'),
        module_score: pick('module_score'),
        module_score_signed: pick('module_score_signed'),
        confidence_score: pick('confidence_score'),
        scores,
        states,
        btc_response: btcResponse,
        jpy_carry: asRow(states.jpy_carry),
        cnh_pressure: asRow(states.cnh_pressure),
        asia_equities: asRow(states.asia_equities),
        korea_premium: asRow(states.korea_premium),
        hk_etf_flow: asRow(states.hk_etf_flow),
        btc_response_confirmation: asRow(states.btc_response_confirmation),
        support_drivers: asList(pick('support_drivers')),
        pressure_drivers: asList(pick('pressure_drivers')),
        conflict_drivers: asList(pick('conflict_drivers')),
        early_warning_flags: asList(pick('early_warning_flags')),
        proxy_flags: asList(pick('proxy_flags')),
        data_quality_flags: asList(pick('data_quality_flags')),
        invalidation_conditions: asList(pick('invalidation_conditions')),
        summary: pick('summary') ?? pick('display_summary') ?? pick('trend_state_reason'),
    };
}
function asiaRiskLayerCards(module) {
    const contract = asiaRiskContract(module);
    return [
        {
            key: 'session',
            title: 'Asia Session Trend',
            state: contract.signal_stage,
            meta: `score ${text(contract.scores.asia_session_trend_score)} · residual z ${text(contract.btc_response.asia_risk_residual_z_90d)}`,
            note: 'BTC Asia-session return, VWAP distance and range position decide whether regional pressure is accepted or rejected.',
            rows: [
                ['return_4h_z', contract.btc_response.asia_session_btc_return_4h_z],
                ['return_8h_z', contract.btc_response.asia_session_btc_return_8h_z],
                ['vwap_distance_z', contract.btc_response.asia_session_vwap_distance_z],
                ['range_position', contract.btc_response.asia_session_range_position],
                ['high_break_flag', contract.btc_response.high_break_flag],
                ['low_break_flag', contract.btc_response.low_break_flag],
            ],
        },
        {
            key: 'risk',
            title: 'Risk-off Pressure',
            state: contract.asia_risk_state,
            meta: `risk ${text(contract.scores.risk_off_pressure_score)} · JPY ${text(contract.scores.jpy_carry_unwind_pressure)}`,
            note: 'Risk pressure is intensity only. It becomes bearish only when BTC Asia-session response confirms downside.',
            rows: [
                ['risk_off_pressure_score', contract.scores.risk_off_pressure_score],
                ['jpy_carry_unwind_pressure', contract.scores.jpy_carry_unwind_pressure],
                ['cnh_devaluation_pressure', contract.scores.cnh_devaluation_pressure],
                ['asia_equity_downside_pressure', contract.scores.asia_equity_downside_pressure],
            ],
        },
        {
            key: 'demand',
            title: 'Regional Demand',
            state: contract.korea_premium.state,
            meta: `demand ${text(contract.scores.regional_demand_score)} · HK ETF ${text(contract.hk_etf_flow.hk_btc_etf_flow_5d_z)}`,
            note: 'Korea premium and HK ETF flow are regional demand context. Extreme premium is stress/FOMO, not automatic bullish confirmation.',
            rows: [
                ['regional_demand_score', contract.scores.regional_demand_score],
                ['korea_premium_state', contract.korea_premium.state],
                ['korea_premium_z_90d', contract.korea_premium.korea_premium_z_90d],
                ['hk_btc_etf_flow_1d_z', contract.hk_etf_flow.hk_btc_etf_flow_1d_z],
                ['hk_btc_etf_flow_5d_z', contract.hk_etf_flow.hk_btc_etf_flow_5d_z],
            ],
        },
        {
            key: 'btc-response',
            title: 'BTC Response',
            state: contract.btc_response_confirmation.state,
            meta: `response ${text(contract.scores.btc_response_score)} · BTC ${text(contract.btc_implication, 'neutral')}`,
            note: 'BTC response is the veto layer: resisting Asia risk, rejecting Asia tailwind, or confirming risk-off.',
            rows: [
                ['btc_response_score', contract.scores.btc_response_score],
                ['expected_return_24h', contract.btc_response.expected_return_24h],
                ['residual_24h', contract.btc_response.residual_24h],
                ['asia_risk_residual_z_90d', contract.btc_response.asia_risk_residual_z_90d],
                ['invalidation', contract.invalidation_conditions.slice(0, 2).join(' | ')],
            ],
        },
    ];
}
function klineOrderflowContract(module) {
    const contract = asRow(module.kline_orderflow_v22);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    const scores = asRow(pick('scores'));
    const keyLevels = asRow(pick('key_levels'));
    const drivers = asRow(pick('drivers'));
    return {
        semantic_profile_version: pick('semantic_profile_version'),
        module_direction: pick('module_direction'),
        module_score: pick('module_score'),
        trend_sensitivity_score: pick('trend_sensitivity_score'),
        trend_reliability_score: pick('trend_reliability_score'),
        confidence_score: pick('confidence_score'),
        signal_stage: pick('signal_stage'),
        volatility_regime: pick('volatility_regime'),
        kline_orderflow_state: pick('kline_orderflow_state') ?? pick('trend_state'),
        btc_implication: pick('btc_implication'),
        scores,
        key_levels: keyLevels,
        drivers,
        support_drivers: asList(pick('support_drivers') ?? drivers.support_drivers),
        pressure_drivers: asList(pick('pressure_drivers') ?? drivers.pressure_drivers),
        conflict_drivers: asList(pick('conflict_drivers') ?? drivers.conflict_drivers),
        early_warning_flags: asList(pick('early_warning_flags') ?? drivers.early_warning_flags),
        rejection_flags: asList(pick('rejection_flags') ?? drivers.rejection_flags),
        data_quality_flags: asList(pick('data_quality_flags') ?? drivers.data_quality_flags),
        invalidation_conditions: asList(pick('invalidation_conditions')),
        summary: pick('display_summary') ?? pick('summary') ?? pick('trend_state_reason'),
    };
}
function klineOrderflowLayerCards(module) {
    const contract = klineOrderflowContract(module);
    return [
        {
            key: 'stage',
            title: 'Signal Stage',
            state: contract.signal_stage,
            meta: `state ${text(contract.kline_orderflow_state, 'neutral')} · vol ${text(contract.volatility_regime, 'normal_vol')}`,
            note: 'Fast warnings and confirmed signals are separated. High-vol regimes raise the confirmation bar.',
            rows: [
                ['btc_implication', contract.btc_implication],
                ['module_direction', contract.module_direction],
                ['module_score', contract.module_score],
                ['confidence_score', contract.confidence_score],
            ],
        },
        {
            key: 'scores',
            title: 'Trend Scores',
            state: contract.module_direction,
            meta: `sensitivity ${text(contract.trend_sensitivity_score)} · reliability ${text(contract.trend_reliability_score)}`,
            note: 'Sensitivity detects a short-term shift; reliability decides whether price structure, flow acceptance, VWAP and residual confirm.',
            rows: [
                ['price_structure_score', contract.scores.price_structure_score],
                ['flow_price_acceptance_score', contract.scores.flow_price_acceptance_score],
                ['vwap_acceptance_score', contract.scores.vwap_acceptance_score],
                ['residual_confirmation_score', contract.scores.residual_confirmation_score],
            ],
        },
        {
            key: 'flow',
            title: 'Flow Acceptance',
            state: contract.btc_implication,
            meta: `aggressor ${text(contract.scores.aggressor_flow_score)} · penalty ${text(contract.scores.contradiction_penalty)}`,
            note: 'Taker flow is directional only when price accepts it. Absorption and exhaustion are explicit rejection states.',
            rows: [
                ['aggressor_flow_score', contract.scores.aggressor_flow_score],
                ['volume_confirmation_score', contract.scores.volume_confirmation_score],
                ['false_breakout_score', contract.scores.false_breakout_score],
                ['false_breakdown_score', contract.scores.false_breakdown_score],
                ['rejection_flags', contract.rejection_flags.slice(0, 2).join(' | ')],
            ],
        },
        {
            key: 'levels',
            title: 'VWAP & Range',
            state: contract.volatility_regime,
            meta: `VWAP ${text(contract.key_levels.vwap_1h)} · local ${text(contract.key_levels.local_range_high_1h)}/${text(contract.key_levels.local_range_low_1h)}`,
            note: 'VWAP crosses and range breaks need duration, follow-through and residual confirmation before becoming confirmed trend signals.',
            rows: [
                ['vwap_15m', contract.key_levels.vwap_15m],
                ['vwap_1h', contract.key_levels.vwap_1h],
                ['micro_range_high_15m', contract.key_levels.micro_range_high_15m],
                ['micro_range_low_15m', contract.key_levels.micro_range_low_15m],
                ['major_range_high_4h', contract.key_levels.major_range_high_4h],
                ['major_range_low_4h', contract.key_levels.major_range_low_4h],
            ],
        },
    ];
}
function tradeStructureFlowContract(module) {
    const contract = asRow(module.trade_structure_flow_v23);
    const profile = asRow(module.module_semantic_profile);
    const pick = (key) => module[key] ?? contract[key] ?? profile[key];
    const scores = asRow(pick('scores'));
    const states = asRow(pick('states'));
    const multiHorizon = asRow(pick('multi_horizon'));
    return {
        semantic_profile_version: pick('semantic_profile_version'),
        module_direction: pick('module_direction'),
        module_score: pick('module_score'),
        confidence_score: pick('confidence_score'),
        signal_stage: pick('signal_stage'),
        trade_structure_state: pick('trade_structure_state') ?? pick('trend_state'),
        btc_implication: pick('btc_implication'),
        scores,
        multi_horizon: multiHorizon,
        states,
        support_drivers: asList(pick('support_drivers')),
        pressure_drivers: asList(pick('pressure_drivers')),
        conflict_drivers: asList(pick('conflict_drivers')),
        early_warning_flags: asList(pick('early_warning_flags')),
        data_quality_flags: asList(pick('data_quality_flags')),
        proxy_flags: asList(pick('proxy_flags')),
        invalidation_conditions: asList(pick('invalidation_conditions')),
        summary: pick('display_summary') ?? pick('summary') ?? pick('trend_state_reason'),
    };
}
function tradeStructureFlowLayerCards(module) {
    const contract = tradeStructureFlowContract(module);
    const horizon5m = asRow(contract.multi_horizon['5m']);
    const horizon15m = asRow(contract.multi_horizon['15m']);
    const horizon1h = asRow(contract.multi_horizon['1h']);
    const liquidity = asRow(contract.states.liquidity);
    const aggressive = asRow(contract.states.aggressive_flow);
    const leverage = asRow(contract.states.leverage);
    const liquidation = asRow(contract.states.liquidation);
    const residual = asRow(contract.states.residual);
    return [
        {
            key: 'stage',
            title: 'Signal Stage',
            state: contract.signal_stage,
            meta: `state ${text(contract.trade_structure_state, 'trade_structure_neutral')} · BTC ${text(contract.btc_implication, 'neutral')}`,
            note: 'Structure pressure is separated from BTC direction. Confirmed signals need price acceptance and standardized residual alignment.',
            rows: [
                ['module_direction', contract.module_direction],
                ['module_score', contract.module_score],
                ['confidence_score', contract.confidence_score],
                ['semantic_profile_version', contract.semantic_profile_version],
            ],
        },
        {
            key: 'horizon',
            title: 'Multi Horizon',
            state: text(horizon15m.direction ?? contract.module_direction, 'neutral'),
            meta: `5m ${text(horizon5m.direction, 'neutral')} · 15m ${text(horizon15m.direction, 'neutral')} · 1h ${text(horizon1h.direction, 'neutral')}`,
            note: '5m is fast sensing, 15m is tactical confirmation, and 1h is the reliability anchor.',
            rows: [
                ['5m_score', horizon5m.score],
                ['5m_price_acceptance', horizon5m.price_acceptance],
                ['15m_score', horizon15m.score],
                ['15m_price_acceptance', horizon15m.price_acceptance],
                ['1h_score', horizon1h.score],
                ['1h_price_acceptance', horizon1h.price_acceptance],
            ],
        },
        {
            key: 'flow',
            title: 'Liquidity & Flow',
            state: text(aggressive.state ?? liquidity.state, 'missing'),
            meta: `flow ${text(contract.scores.aggressive_flow_score)} · liquidity ${text(contract.scores.liquidity_directional_score)}`,
            note: 'Aggressive buy/sell flow is directional only after BTC price accepts it. Thin liquidity alone remains a warning.',
            rows: [
                ['price_acceptance_score', contract.scores.price_acceptance_score],
                ['aggressive_flow_score', contract.scores.aggressive_flow_score],
                ['liquidity_directional_score', contract.scores.liquidity_directional_score],
                ['flow_delta_z_5m', aggressive.flow_delta_z_5m],
                ['flow_delta_z_15m', aggressive.flow_delta_z_15m],
                ['depth_thinning_z_15m', liquidity.depth_thinning_z_15m],
            ],
        },
        {
            key: 'leverage',
            title: 'Leverage & Residual',
            state: text(liquidation.state ?? leverage.state ?? residual.state, 'missing'),
            meta: `residual ${text(contract.scores.residual_confirmation_score)} · liquidation ${text(contract.scores.liquidation_response_score)}`,
            note: 'Funding, OI and liquidation spikes are context unless BTC response and residual confirm follow-through or absorption.',
            rows: [
                ['spot_perp_quality_score', contract.scores.spot_perp_quality_score],
                ['leverage_structure_score', contract.scores.leverage_structure_score],
                ['liquidation_response_score', contract.scores.liquidation_response_score],
                ['trade_structure_residual_z', residual.trade_structure_residual_z],
                ['expected_return_z', residual.expected_return_z],
                ['proxy_flags', contract.proxy_flags.slice(0, 2).join(' | ')],
            ],
        },
    ];
}
function radarMetricQualityLine(metric) {
    const freshness = metric.is_stale ? 'stale' : text(metric.freshness_status ?? metric.business_recency_status, 'fresh');
    const fallback = metric.fallback_used ? 'fallback' : 'primary';
    return `${freshness} · ${fallback} · q ${text(metric.quality_score)}`;
}
function selectRadarMetric(metric) {
    selectedRadarMetricId.value = text(metric.metric_id);
}
async function openSelectedRadarEvidence(metric) {
    const evidenceId = String(metric.evidence_id ?? '');
    if (evidenceId) {
        await openEvidenceDetail(evidenceId);
        return;
    }
    await openMetricEvidence(metric.metric_id);
}
function directionText(value) {
    const direction = String(value ?? '').toLowerCase();
    if (direction.includes('bull'))
        return 'bullish';
    if (direction.includes('bear'))
        return 'bearish';
    if (direction.includes('mixed'))
        return 'mixed';
    if (direction.includes('neutral'))
        return 'neutral';
    return 'watch';
}
function moduleReadableSummary(module) {
    const explanation = module.module_explanation ?? module.module_summary;
    if (explanation)
        return text(explanation);
    const id = moduleName(module);
    const state = moduleDisplayState(module);
    const direction = directionText(state);
    const positive = Number(module.positive_metric_count ?? 0);
    const negative = Number(module.negative_metric_count ?? 0);
    const unavailable = Number(module.unavailable_metric_count ?? 0);
    const split = positive > 0 && negative > 0 ? ', with internal signal disagreement' : '';
    const boundary = unavailable > 0 ? ', with unavailable metrics as data boundary' : '';
    if (id === 'fund_flow' && String(module.fund_flow_state ?? '').toLowerCase() === 'bearish_but_improving') {
        return 'Fund flow is bearish but improving: ETF/stablecoin pressure remains, while exchange balance contraction provides marginal support.';
    }
    if (id === 'fund_flow') {
        const contract = fundFlowContract(module);
        return `Fund flow: ${text(contract.fund_flow_state, 'fund_flow_neutral')}; BTC implication ${text(contract.btc_implication, 'neutral')}; ETF ${text(contract.etf_demand.state, 'missing')}; exchange ${text(contract.exchange_supply.state, 'missing')}; BTC response ${text(contract.btc_response_confirmation.state, 'missing')}. This module confirms or refutes whether BTC accepts fund-flow tailwinds or headwinds.`;
    }
    if (id === 'onchain_valuation') {
        const contract = onchainValuationContract(module);
        return `On-chain valuation: ${text(contract.onchain_valuation_state, 'onchain_neutral')}; stage ${text(contract.signal_stage, 'none')}; bias ${text(contract.module_bias, 'neutral')}; BTC ${text(contract.btc_implication, 'neutral')}. Slow regime and fast trend-delta are separated, with STH cost basis, SOPR and residual used for confirmation.`;
    }
    if (id === 'btc_adoption') {
        const contract = btcAdoptionContract(module);
        return `BTC adoption: ${text(contract.btc_adoption_state, 'btc_adoption_neutral')}; stage ${text(contract.signal_stage, 'none')}; BTC ${text(contract.btc_implication, 'neutral')}. Fast, core and regime layers separate real settlement confirmation from raw activity, fee noise, hashrate and Lightning context.`;
    }
    if (id === 'asia_risk') {
        const contract = asiaRiskContract(module);
        return `Asia risk: ${text(contract.asia_risk_state, 'asia_risk_neutral')}; stage ${text(contract.signal_stage, 'none')}; BTC ${text(contract.btc_implication, 'neutral')}. Risk pressure is context until Asia-session BTC response, VWAP/range and residual confirm or reject it.`;
    }
    if (id === 'kline_orderflow') {
        const contract = klineOrderflowContract(module);
        return `Kline orderflow: ${text(contract.kline_orderflow_state, 'neutral')}; stage ${text(contract.signal_stage, 'none')}; BTC ${text(contract.btc_implication, 'neutral')}. Active taker flow is directional only when price structure, VWAP acceptance and residual confirm it.`;
    }
    if (id === 'kline_orderflow' && String(module.trend_state ?? '').toLowerCase() === 'neutral_wait_confirm') {
        return 'Kline orderflow is waiting for confirmation: short-term scores lean positive, but the composite structure is not confirmed yet.';
    }
    if (id === 'derivatives_crowding') {
        const contract = derivativesCrowdingContract(module);
        if (contract.semantic_profile_version === 'p3.c60.derivatives_crowding.v2.5' || module.derivatives_crowding_v25) {
            return `Derivatives crowding: ${text(contract.derivatives_state, 'derivatives_neutral')}; stage ${text(contract.signal_stage, 'none')}; BTC ${text(contract.btc_implication, 'neutral')}. Direction is confirmed only when BTC response, trend prior and standardized residual accept the leveraged structure.`;
        }
        const crowding = text(module.crowding_state, 'unknown');
        const heat = text(module.leverage_heat_state, 'unknown');
        const positioning = text(module.top_positioning_state ?? module.positioning_state, 'balanced');
        const squeeze = text(module.long_short_squeeze_risk, 'none');
        return `Derivatives crowding: ${crowding}; leverage heat ${heat}; positioning ${positioning}; squeeze risk ${squeeze}. Funding/OI are derivatives risk inputs here, not BTC Total State direction drivers.`;
    }
    if (id === 'trade_structure_flow') {
        const contract = tradeStructureFlowContract(module);
        if (contract.semantic_profile_version === 'p3.c58.trade_structure_flow.v2.3' || module.trade_structure_flow_v23) {
            return `Trade structure flow: ${text(contract.trade_structure_state, 'trade_structure_neutral')}; stage ${text(contract.signal_stage, 'none')}; BTC ${text(contract.btc_implication, 'neutral')}. Direction is confirmed only when microstructure pressure, multi-horizon price acceptance and standardized residual align.`;
        }
        if (module.trade_structure_summary)
            return text(module.trade_structure_summary);
        const state = text(module.trade_structure_state, 'mixed_structure');
        const aggressive = text(module.aggressive_flow_state, 'unknown');
        const price = text(module.price_response_state, 'unknown');
        const risk = text(module.risk_state, 'normal_context');
        return `Trade structure: ${state}; aggressive flow ${aggressive}; price response ${price}; risk ${risk}. Taker pressure is not a trend confirmation by itself.`;
    }
    if (id === 'btc_total_state') {
        const contract = btcTotalContract(module);
        const price = asRow(contract.price_state);
        const perp = asRow(contract.perp_state);
        return `BTC total state: ${text(contract.btc_short_term_state, direction)}; price ${text(price.state, 'missing')}; perp ${text(perp.state, 'missing')}. Halving and block height are context/audit only.`;
    }
    if (id === 'options_volatility') {
        const contract = optionsVolatilityContract(module);
        return `Options structure: ${text(contract.options_short_term_state, 'vol_neutral')}; risk ${text(contract.risk_score)}; trade hint ${text(contract.trade_permission_hint, 'normal')}. This module adjusts risk and confidence, not final direction.`;
    }
    if (id === 'event_policy') {
        const contract = eventPolicyContract(module);
        const gate = contract.trade_gate;
        return `Event gate: ${text(contract.event_short_term_state, 'event_neutral')}; phase ${text(contract.event_window_phase, 'neutral')}; lock ${text(contract.event_risk_lock_level, 'none')}; reason ${text(gate.reason_code, 'EVENT_NEUTRAL')}. This module controls trade permission, not final direction.`;
    }
    if (id === 'crypto_breadth') {
        const contract = cryptoBreadthContract(module);
        return `Crypto breadth: ${text(contract.crypto_breadth_state, 'neutral_wait_confirm')}; BTC implication ${text(contract.btc_implication, 'neutral')}; breadth ${text(contract.breadth_participation.state, 'missing')}; diffusion ${text(contract.market_cap_diffusion.state, 'missing')}. This module confirms or refutes BTC trend quality.`;
    }
    if (id === 'macro_radar') {
        const contract = macroRadarContract(module);
        return `Macro radar: ${text(contract.macro_trend_state, 'macro_neutral')}; BTC implication ${text(contract.btc_implication, 'neutral')}; rates ${text(contract.rates_pressure.state, 'missing')}; impulse ${text(contract.macro_impulse.state, 'missing')}; BTC relative ${text(contract.btc_relative_confirmation.state, 'missing')}. This module confirms or refutes BTC trend quality through macro context.`;
    }
    if (id === 'dollar_liquidity') {
        const contract = dollarLiquidityContract(module);
        return `Dollar liquidity: ${text(contract.dollar_liquidity_state, 'liquidity_neutral')}; impulse ${text(contract.liquidity_impulse.state, 'missing')}; repo funding ${text(contract.repo_funding_pressure.state, 'missing')}; BTC response ${text(contract.btc_response_confirmation.state, 'missing')}. This module confirms or refutes BTC trend through USD liquidity and funding conditions.`;
    }
    if (id === 'treasury_credit') {
        const contract = treasuryCreditContract(module);
        return `Treasury credit: ${text(contract.treasury_credit_state, 'treasury_credit_neutral')}; BTC implication ${text(contract.btc_implication, 'neutral')}; real yield ${text(contract.real_yield_pressure.state, 'missing')}; credit ${text(contract.credit_stress.state, 'missing')}; BTC response ${text(contract.btc_response_confirmation.state, 'missing')}. This module confirms or refutes BTC trend through rates, curve and credit stress.`;
    }
    const templates = {
        macro_radar: `Macro radar is ${direction}${split}${boundary}.`,
        treasury_credit: `Treasury Credit confirms or refutes BTC trend through rates and credit stress.`,
        asia_risk: `Asia risk confirms or refutes BTC trend through Asia-session response, regional risk pressure and local crypto demand.`,
        event_policy: `Event policy is a trade-permission gate, not a directional signal.`,
        dollar_liquidity: `Dollar liquidity is ${direction}, affecting BTC marginal funding conditions.`,
        fund_flow: `Fund flow is ${direction}${split}, confirming or refuting whether BTC accepts ETF, stablecoin and exchange-supply signals.`,
        crypto_breadth: `Crypto breadth is ${direction}, reflecting sector participation.`,
        kline_orderflow: `Short-term price and order flow are ${direction}, reflecting immediate absorption.`,
        derivatives_crowding: `Derivatives crowding is ${direction}, useful for overheating or deleveraging risk.`,
        trade_structure_flow: `Trade structure and flow are ${direction}${split}.`,
        options_volatility: `Options volatility is risk and expiry structure context, reflecting tail risk pricing without voting on direction.`,
        btc_total_state: `BTC total state is ${direction}, combining price_state and perp_state.`,
        btc_adoption: `BTC adoption is ${direction}${split}${boundary}.`,
        onchain_valuation: `On-chain valuation is ${direction}${boundary}, watching valuation and holder pressure.`,
    };
    return templates[id] ?? `${shortModuleName(module)} is ${direction}${split}${boundary}.`;
}
function moduleAuditMeta(module) {
    const positive = text(module.positive_metric_count, '0');
    const negative = text(module.negative_metric_count, '0');
    const zero = text(module.zero_metric_count, '0');
    const unavailable = text(module.unavailable_metric_count, '0');
    const quality = text(module.module_quality_score ?? module.quality_score);
    return `q=${quality} · +${positive}/-${negative} · 0=${zero} · NA=${unavailable}`;
}
function loadRadarLayout() {
    const raw = window.localStorage.getItem(RADAR_LAYOUT_KEY);
    if (!raw)
        return;
    try {
        const parsed = JSON.parse(raw);
        for (const [moduleId, point] of Object.entries(parsed)) {
            if (Number.isFinite(point?.x) && Number.isFinite(point?.y)) {
                radarLayout[moduleId] = { x: clamp(point.x, 4, 96), y: clamp(point.y, 8, 92) };
            }
        }
    }
    catch {
        window.localStorage.removeItem(RADAR_LAYOUT_KEY);
    }
}
function saveRadarLayout() {
    window.localStorage.setItem(RADAR_LAYOUT_KEY, JSON.stringify(radarLayout));
}
function resetRadarLayout() {
    for (const key of Object.keys(radarLayout))
        delete radarLayout[key];
    window.localStorage.removeItem(RADAR_LAYOUT_KEY);
}
function handleBtcMove(event) {
    const target = event.currentTarget;
    const rect = target.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const px = x / rect.width - 0.5;
    const py = y / rect.height - 0.5;
    const rotateY = px * 10;
    const rotateX = -py * 8;
    const shadowX = -px * 28;
    const shadowY = 22 + Math.abs(py) * 10 - py * 10;
    const shadowScaleX = 1.05 + Math.abs(px) * 0.24;
    const shadowScaleY = 0.78 - Math.abs(py) * 0.16;
    const shadowBlur = 22 + (0.5 - Math.min(0.5, Math.hypot(px, py))) * 20;
    const shadowOpacity = 0.22 + Math.min(0.18, Math.hypot(px, py) * 0.24);
    target.style.setProperty('--btc-rx', `${rotateX.toFixed(2)}deg`);
    target.style.setProperty('--btc-ry', `${rotateY.toFixed(2)}deg`);
    target.style.setProperty('--btc-shadow-x', `${shadowX.toFixed(1)}px`);
    target.style.setProperty('--btc-shadow-y', `${shadowY.toFixed(1)}px`);
    target.style.setProperty('--btc-shadow-scale-x', shadowScaleX.toFixed(3));
    target.style.setProperty('--btc-shadow-scale-y', shadowScaleY.toFixed(3));
    target.style.setProperty('--btc-shadow-blur', `${shadowBlur.toFixed(1)}px`);
    target.style.setProperty('--btc-shadow-opacity', shadowOpacity.toFixed(3));
}
function resetBtcTilt(event) {
    const target = event.currentTarget;
    target.style.setProperty('--btc-rx', '0deg');
    target.style.setProperty('--btc-ry', '0deg');
    target.style.setProperty('--btc-shadow-x', '0px');
    target.style.setProperty('--btc-shadow-y', '26px');
    target.style.setProperty('--btc-shadow-scale-x', '1');
    target.style.setProperty('--btc-shadow-scale-y', '0.82');
    target.style.setProperty('--btc-shadow-blur', '34px');
    target.style.setProperty('--btc-shadow-opacity', '0.18');
}
function handleRadarNodeMove(event) {
    if (dragging.value || window.matchMedia('(max-width: 1100px)').matches)
        return;
    const target = event.currentTarget;
    const rect = target.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const rotateY = (x / rect.width - 0.5) * 8;
    const rotateX = (0.5 - y / rect.height) * 6;
    target.style.setProperty('--node-rx', `${rotateX.toFixed(2)}deg`);
    target.style.setProperty('--node-ry', `${rotateY.toFixed(2)}deg`);
}
function resetRadarNodeTilt(event) {
    const target = event.currentTarget;
    target.style.setProperty('--node-rx', '0deg');
    target.style.setProperty('--node-ry', '0deg');
}
function clampAwayFromBtc(x, y, target) {
    const topology = topologyRef.value;
    const btc = btcRef.value;
    if (!topology || !btc)
        return { x, y };
    const topologyRect = topology.getBoundingClientRect();
    const btcRect = btc.getBoundingClientRect();
    const nodeRect = target.getBoundingClientRect();
    const padding = 12;
    const nodeHalfW = nodeRect.width / 2;
    const nodeHalfH = nodeRect.height / 2;
    const minX = nodeHalfW;
    const maxX = topologyRect.width - nodeHalfW;
    const minY = 96 + nodeHalfH;
    const maxY = topologyRect.height - nodeHalfH;
    let px = clamp((x / 100) * topologyRect.width, minX, maxX);
    let py = clamp((y / 100) * topologyRect.height, minY, maxY);
    const btcCenterX = btcRect.left - topologyRect.left + btcRect.width / 2;
    const btcCenterY = btcRect.top - topologyRect.top + btcRect.height / 2;
    const halfW = btcRect.width / 2 + nodeHalfW + padding;
    const halfH = btcRect.height / 2 + nodeHalfH + padding;
    const dx = px - btcCenterX;
    const dy = py - btcCenterY;
    if (Math.abs(dx) < halfW && Math.abs(dy) < halfH) {
        if (Math.abs(dx) < 0.1 && Math.abs(dy) < 0.1) {
            py = btcCenterY - halfH;
        }
        else {
            const tx = Math.abs(dx) > 0.1 ? halfW / Math.abs(dx) : Number.POSITIVE_INFINITY;
            const ty = Math.abs(dy) > 0.1 ? halfH / Math.abs(dy) : Number.POSITIVE_INFINITY;
            const t = Math.min(tx, ty);
            px = btcCenterX + dx * t;
            py = btcCenterY + dy * t;
        }
    }
    px = clamp(px, minX, maxX);
    py = clamp(py, minY, maxY);
    return {
        x: (px / topologyRect.width) * 100,
        y: (py / topologyRect.height) * 100,
    };
}
function updateDraggedPoint(event) {
    const drag = dragging.value;
    const topology = topologyRef.value;
    if (!drag || !topology)
        return;
    const rect = topology.getBoundingClientRect();
    const rawX = ((event.clientX - rect.left) / rect.width) * 100;
    const rawY = ((event.clientY - rect.top) / rect.height) * 100;
    radarLayout[drag.moduleId] = clampAwayFromBtc(rawX, rawY, drag.target);
}
function startDrag(event, moduleId) {
    if (window.matchMedia('(max-width: 1100px)').matches)
        return;
    const target = event.currentTarget;
    target.style.setProperty('--node-rx', '0deg');
    target.style.setProperty('--node-ry', '0deg');
    dragging.value = {
        moduleId: moduleLayoutKey(moduleId),
        pointerId: event.pointerId,
        target,
        startClientX: event.clientX,
        startClientY: event.clientY,
        moved: false,
    };
    target.setPointerCapture(event.pointerId);
    document.body.classList.add('dragging-radar-node');
}
function dragNode(event) {
    const drag = dragging.value;
    if (!drag || drag.pointerId !== event.pointerId)
        return;
    const distance = Math.hypot(event.clientX - drag.startClientX, event.clientY - drag.startClientY);
    if (!drag.moved && distance < 4)
        return;
    drag.moved = true;
    updateDraggedPoint(event);
}
function stopDrag(event) {
    const drag = dragging.value;
    if (!drag)
        return;
    if (event && drag.pointerId !== event.pointerId)
        return;
    try {
        if (event)
            drag.target.releasePointerCapture(event.pointerId);
    }
    catch {
        // Pointer capture can be released by the browser if the pointer leaves the window.
    }
    if (drag.moved) {
        for (const node of topologyModules.value) {
            const moduleId = moduleLayoutKey(moduleName(node.module));
            const point = displayNodePoint(moduleId, node.index);
            radarLayout[moduleId] = { x: clamp(point.x, 4, 96), y: clamp(point.y, 8, 92) };
        }
        saveRadarLayout();
        suppressNextNodeClick.value = true;
        window.setTimeout(() => {
            suppressNextNodeClick.value = false;
        }, 0);
    }
    dragging.value = null;
    document.body.classList.remove('dragging-radar-node');
}
function loadEventAlertPosition() {
    try {
        const raw = window.localStorage.getItem(EVENT_ALERT_POSITION_KEY);
        if (!raw)
            return;
        const parsed = JSON.parse(raw);
        if (Number.isFinite(parsed.x) && Number.isFinite(parsed.y)) {
            eventAlertPosition.value = {
                x: clamp(Number(parsed.x), 8, Math.max(window.innerWidth - 220, 8)),
                y: clamp(Number(parsed.y), 58, Math.max(window.innerHeight - 120, 58)),
            };
        }
    }
    catch {
        eventAlertPosition.value = null;
    }
}
function saveEventAlertPosition() {
    if (!eventAlertPosition.value) {
        window.localStorage.removeItem(EVENT_ALERT_POSITION_KEY);
        return;
    }
    window.localStorage.setItem(EVENT_ALERT_POSITION_KEY, JSON.stringify(eventAlertPosition.value));
}
function loadEventAlertMute() {
    try {
        const raw = window.localStorage.getItem(EVENT_ALERT_MUTE_KEY);
        const until = raw ? Number(raw) : 0;
        eventAlertMutedUntil.value = Number.isFinite(until) ? until : 0;
    }
    catch {
        eventAlertMutedUntil.value = 0;
    }
}
function readStorageList(storage, key) {
    try {
        const parsed = JSON.parse(storage.getItem(key) || '[]');
        if (!Array.isArray(parsed))
            return [];
        return parsed.map((item) => text(item, '')).filter(Boolean);
    }
    catch {
        return [];
    }
}
function writeStorageList(storage, key, values) {
    storage.setItem(key, JSON.stringify([...new Set(values.filter(Boolean))]));
}
function loadEventWindowVisibilityState() {
    eventWindowAckKeys.value = readStorageList(window.localStorage, EVENT_WINDOW_ACK_KEY);
    eventWindowHiddenKeys.value = readStorageList(window.sessionStorage, EVENT_WINDOW_HIDDEN_KEY);
    dismissedCriticalAlertKey.value = text(window.sessionStorage.getItem(EVENT_WINDOW_CRITICAL_DISMISS_KEY), '');
}
function saveEventWindowAckKeys() {
    try {
        writeStorageList(window.localStorage, EVENT_WINDOW_ACK_KEY, eventWindowAckKeys.value);
    }
    catch {
        // Ack is local UI state only; Event Window payload remains authoritative.
    }
}
function saveEventWindowHiddenKeys() {
    try {
        writeStorageList(window.sessionStorage, EVENT_WINDOW_HIDDEN_KEY, eventWindowHiddenKeys.value);
    }
    catch {
        // Hidden alerts are optional frontend visibility state.
    }
}
function ackCurrentEventAlert() {
    const key = eventWindowVisibilityKey.value;
    if (!key || key === '|||')
        return;
    eventWindowAckKeys.value = [...new Set([...eventWindowAckKeys.value, key])];
    saveEventWindowAckKeys();
}
function hideCurrentEventAlertForSession() {
    const key = eventWindowVisibilityKey.value;
    if (!key || key === '|||')
        return;
    eventWindowHiddenKeys.value = [...new Set([...eventWindowHiddenKeys.value, key])];
    eventFloatingAlertHovered.value = false;
    saveEventWindowHiddenKeys();
}
function dismissEventFloatingAlertSession(event) {
    event?.stopPropagation();
    hideCurrentEventAlertForSession();
}
function clearVisibleNonCriticalEventAlerts() {
    if (eventCriticalLikeActive.value)
        return;
    hideCurrentEventAlertForSession();
}
function restoreEventWindowHiddenAlerts() {
    eventWindowHiddenKeys.value = [];
    dismissedCriticalAlertKey.value = '';
    eventAlertMutedUntil.value = 0;
    eventAlertNowMs.value = Date.now();
    saveEventWindowHiddenKeys();
    try {
        window.localStorage.removeItem(EVENT_ALERT_MUTE_KEY);
        window.sessionStorage.removeItem(EVENT_WINDOW_CRITICAL_DISMISS_KEY);
    }
    catch {
        // Optional local mute cleanup.
    }
}
function muteEventFloatingAlert(minutes = 15) {
    const until = Date.now() + minutes * 60 * 1000;
    eventAlertMutedUntil.value = until;
    eventAlertNowMs.value = Date.now();
    try {
        window.localStorage.setItem(EVENT_ALERT_MUTE_KEY, String(until));
    }
    catch {
        // Local mute is optional; live Event Watchtower state remains visible on the page.
    }
}
function expandEventFloatingAlert(event) {
    if (suppressNextEventAlertClick.value) {
        event.preventDefault();
        return;
    }
    if (!eventFloatingAlertMuted.value)
        return;
    eventAlertMutedUntil.value = 0;
    eventAlertNowMs.value = Date.now();
    try {
        window.localStorage.removeItem(EVENT_ALERT_MUTE_KEY);
    }
    catch {
        // Optional local state cleanup.
    }
}
function setEventFloatingAlertHover(value) {
    eventFloatingAlertHovered.value = value;
}
function resetEventAlertPosition() {
    eventAlertPosition.value = null;
    saveEventAlertPosition();
}
function startEventAlertDrag(event) {
    const target = event.currentTarget;
    const rect = target.getBoundingClientRect();
    eventAlertPosition.value = {
        x: rect.left,
        y: rect.top,
    };
    eventAlertDragging.value = {
        pointerId: event.pointerId,
        target,
        offsetX: event.clientX - rect.left,
        offsetY: event.clientY - rect.top,
        startClientX: event.clientX,
        startClientY: event.clientY,
        moved: false,
    };
    target.setPointerCapture(event.pointerId);
    document.body.classList.add('dragging-event-alert');
}
function dragEventAlert(event) {
    const drag = eventAlertDragging.value;
    if (!drag || drag.pointerId !== event.pointerId)
        return;
    const distance = Math.hypot(event.clientX - drag.startClientX, event.clientY - drag.startClientY);
    if (!drag.moved && distance < 4)
        return;
    drag.moved = true;
    const width = drag.target.offsetWidth || 460;
    const height = drag.target.offsetHeight || 92;
    eventAlertPosition.value = {
        x: clamp(event.clientX - drag.offsetX, 8, Math.max(window.innerWidth - width - 8, 8)),
        y: clamp(event.clientY - drag.offsetY, 58, Math.max(window.innerHeight - height - 8, 58)),
    };
}
function stopEventAlertDrag(event) {
    const drag = eventAlertDragging.value;
    if (!drag)
        return;
    if (event && drag.pointerId !== event.pointerId)
        return;
    try {
        if (event)
            drag.target.releasePointerCapture(event.pointerId);
    }
    catch {
        // Pointer capture may already be released.
    }
    if (drag.moved) {
        saveEventAlertPosition();
        suppressNextEventAlertClick.value = true;
        window.setTimeout(() => {
            suppressNextEventAlertClick.value = false;
        }, 0);
    }
    eventAlertDragging.value = null;
    document.body.classList.remove('dragging-event-alert');
}
function openEventWatchtowerFromAlert(event) {
    if (suppressNextEventAlertClick.value) {
        event.preventDefault();
        return;
    }
    activePage.value = 'eventWatchtower';
}
function dismissEventCriticalOverlay() {
    dismissedCriticalAlertKey.value = eventCriticalAlertKey.value;
    try {
        window.sessionStorage.setItem(EVENT_WINDOW_CRITICAL_DISMISS_KEY, dismissedCriticalAlertKey.value);
    }
    catch {
        // Critical dismiss is session-only visibility; live Event Window state remains visible.
    }
}
async function openRadarNode(event, moduleId) {
    if (suppressNextNodeClick.value) {
        event.preventDefault();
        return;
    }
    await openRadarDetail(moduleId);
}
function horizonLabel(key) {
    if (key === 'h24' || key === '24h' || key === '1d')
        return '24h';
    if (key === 'd3' || key === '3d')
        return '3d';
    if (key === 'd7' || key === '7d')
        return '7d';
    return key;
}
function horizonFullLabel(key) {
    if (key === '4h')
        return '4h 变盘侦测';
    if (key === '1d' || key === 'h24' || key === '24h')
        return '1d / 24h 短线趋势';
    if (key === '3d' || key === 'd3')
        return '3d 资金 / 宏观确认';
    if (key === '7d' || key === 'd7')
        return '7d Regime 背景';
    return key;
}
function horizonDirection(key) {
    return normalizeTimescaleHorizon(key).direction;
}
function horizonPairDirection(left, right) {
    const leftDirection = text(horizonDirection(left), '-');
    const rightDirection = text(horizonDirection(right), '-');
    return `${horizonLabel(left)} ${leftDirection} · ${horizonLabel(right)} ${rightDirection}`;
}
function normalizeTimescaleHorizon(key) {
    const source = timescaleHorizonSource(key);
    const score = firstPresent(source.direct_trend_direction_score, source.direction_score, source.effective_score, source.score);
    const trust = firstPresent(source.direct_trend_trust_score, source.trust_score, source.confidence_score, source.confidence);
    const acceptance = firstPresent(source.direct_trend_acceptance_score, source.acceptance_score);
    const display = firstPresent(source.direct_trend_display_score, source.display_score);
    const radarContext = asRow(source.radar_context);
    const eventTrust = asRow(source.event_trust);
    const eventCap = firstPresent(source.event_trust_cap, eventTrust.event_trust_cap);
    const direction = firstPresent(source.direction, Number.isFinite(Number(score)) ? signedDirection(Number(score)) : undefined);
    return {
        ...source,
        key,
        direction,
        direction_score: score,
        direct_trend_direction_score: score,
        trust_score: trust,
        direct_trend_trust_score: trust,
        acceptance_score: acceptance,
        direct_trend_acceptance_score: acceptance,
        display_score: display,
        direct_trend_display_score: display,
        radar_context: {
            ...radarContext,
            bias: firstPresent(source.radar_context_bias, radarContext.bias),
            status: firstPresent(source.radar_context_status, radarContext.status),
        },
        event_trust: {
            ...eventTrust,
            event_trust_cap: eventCap,
        },
        source_fresh: firstPresent(source.source_fresh, directTrendApi.value.source_fresh, btcTimescaleJudge.value.source_fresh),
        runtime_fresh: firstPresent(source.runtime_fresh, directTrendApi.value.runtime_fresh),
        fallback_used: Boolean(source.fallback_used ?? directTrendApi.value.fallback_used),
        fallback_reason: firstPresent(source.fallback_reason, directTrendApi.value.fallback_reason),
    };
}
function timescaleHorizonSource(key) {
    const judgeHorizons = asRow(btcTimescaleJudge.value.horizons);
    const apiHorizons = asRow(directTrendApi.value.horizons);
    const views = (state.dashboard?.horizon_views ?? state.overview?.horizon_views ?? {});
    const legacyKeys = key === '1d'
        ? ['1d', '24h', 'h24']
        : key === '3d'
            ? ['3d', 'd3']
            : key === '7d'
                ? ['7d', 'd7']
                : [key];
    for (const candidate of [key, ...legacyKeys]) {
        const value = judgeHorizons[candidate] ?? apiHorizons[candidate] ?? views[candidate];
        if (value && typeof value === 'object' && !Array.isArray(value))
            return value;
    }
    return { fallback_used: true, fallback_reason: 'waiting_for_timescale_payload' };
}
function firstPresent(...values) {
    return values.find((value) => value !== undefined && value !== null && value !== '');
}
const metricLabelMap = {
    btc_1h_volume: '1h volume',
    btc_1h_close: '1h close',
    btc_1h_low: '1h low',
    btc_1h_high: '1h high',
    btc_funding_rate: 'BTC funding',
    taker_buy_sell_ratio: 'taker buy/sell ratio',
    exchange_balance_delta_1d_proxy: 'exchange balance delta',
    exchange_spot_volume: 'spot volume',
    stablecoin_buying_power_proxy: 'stablecoin buying power',
    mempool_blocks_to_clear: 'mempool blocks to clear',
    mempool_tx_count: 'mempool transaction count',
    sofr: 'SOFR',
    hy_spread: 'HY OAS',
    ig_oas: 'IG OAS',
    real_yield_10y: '10Y real yield',
    treasury_10y: '10Y treasury yield',
    treasury_2y: '2Y treasury yield',
    treasury_2y_change_1d_bps: '2Y 1d change',
    treasury_10y_change_1d_bps: '10Y 1d change',
    real_yield_10y_change_1d_bps: 'real yield 1d change',
    hy_oas_change_5d_bps: 'HY OAS 5d change',
    btc_residual_24h: 'BTC residual 24h',
    transfer_volume_adjusted_usd: 'adjusted transfer volume',
    top50_strength: 'Top50 breadth',
    ofr_fsi: 'OFR FSI',
    mvrv_zscore: 'MVRV Z-Score',
    active_addresses: 'active addresses',
    stablecoin_supply: 'stablecoin supply',
    bank_reserves: 'bank reserves',
    btc_price: 'BTC price',
};
function metricLabel(metricId) {
    const id = driverMetricId(metricId);
    if (!id)
        return '-';
    return metricLabelMap[id] ?? id.replace(/_/g, ' ');
}
function driverMetricId(value) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
        const row = value;
        return String(row.metric_id ?? row.id ?? row.name ?? '');
    }
    return String(value ?? '');
}
function readableMetricText(value) {
    let output = text(value, '');
    const ids = Object.keys(metricLabelMap).sort((left, right) => right.length - left.length);
    for (const id of ids) {
        output = output.split(id).join(metricLabelMap[id]);
    }
    return output;
}
function asList(value) {
    if (Array.isArray(value))
        return value.filter((item) => item !== null && item !== undefined && item !== '');
    if (value === null || value === undefined || value === '')
        return [];
    return [value];
}
function compactList(value, fallback = '-') {
    const items = asList(value).map((item) => text(item)).filter(Boolean);
    return items.length ? items.slice(0, 4).join(', ') : fallback;
}
function marketReturnPct(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric))
        return '-';
    const sign = numeric > 0 ? '+' : '';
    return `${sign}${(numeric * 100).toFixed(2)}%`;
}
function marketReturnTone(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric))
        return 'quality';
    if (numeric <= -0.01)
        return 'bear';
    if (numeric < -0.003)
        return 'mixed';
    if (numeric >= 0.01)
        return 'bull';
    return 'quality';
}
function metricChips(value, limit = 5) {
    return asList(value)
        .map((item) => driverMetricId(item))
        .filter((item, index, array) => array.indexOf(item) === index)
        .slice(0, limit);
}
function horizonConfidence(item) {
    const value = item.direct_trend_trust_score ?? item.trust_score ?? item.confidence_score ?? item.confidence;
    if (typeof value === 'number')
        return value.toFixed(2);
    return text(value);
}
function horizonAcceptance(item) {
    const acceptance = (item.acceptance ?? {});
    const value = item.direct_trend_acceptance_score ?? item.acceptance_score;
    if (typeof value === 'number')
        return value.toFixed(2);
    return text(acceptance.state, '');
}
function horizonScore(item) {
    const value = item.direct_trend_direction_score ?? item.direction_score ?? item.effective_score ?? item.score;
    if (typeof value === 'number')
        return value.toFixed(2);
    return text(value);
}
function horizonDisplayScore(item) {
    const value = item.direct_trend_display_score ?? item.display_score;
    if (typeof value === 'number')
        return value.toFixed(2);
    return text(value);
}
function horizonSummary(key, item) {
    const reason = readableMetricText(item.reason);
    if (reason)
        return reason;
    const summary = readableMetricText(item.summary);
    if (summary)
        return summary;
    const interpretation = readableMetricText(item.interpretation);
    if (interpretation)
        return interpretation;
    const direction = directionText(item.direction);
    const support = metricChips(item.support_drivers, 3).map(metricLabel).join(', ');
    const pressure = metricChips(item.pressure_drivers, 3).map(metricLabel).join(', ');
    const supportText = support ? `support from ${support}` : 'support drivers need confirmation';
    const pressureText = pressure ? `pressure from ${pressure}` : 'pressure drivers are not dominant';
    return `${horizonFullLabel(key)} is ${direction}; ${supportText}; ${pressureText}.`;
}
function horizonTone(item) {
    if (item.source_fresh === false || item.source_fresh === 'stale')
        return 'quality';
    const score = Number(item.direct_trend_direction_score ?? item.direction_score ?? item.effective_score ?? item.score);
    if (Number.isFinite(score)) {
        if (score >= 15)
            return 'bull';
        if (score <= -15)
            return 'bear';
        if (Math.abs(score) >= 5)
            return 'mixed';
        return 'neutral';
    }
    return directionClass(item.direction);
}
function horizonCardClasses(item) {
    const classes = [horizonTone(item)];
    const trust = Number(item.direct_trend_trust_score ?? item.trust_score ?? item.confidence_score ?? item.confidence);
    if (Number.isFinite(trust) && trust < 55)
        classes.push('low-trust');
    if (item.fallback_used === true || item.fallback_reason)
        classes.push('fallback');
    if (horizonWarning(item))
        classes.push('warning');
    return classes;
}
function horizonFreshnessBadges(item) {
    const badges = [
        `runtime ${text(item.runtime_fresh, 'unknown')}`,
        `source ${text(item.source_fresh, 'unknown')}`,
    ];
    if (item.fallback_used === true || item.fallback_reason)
        badges.push('fallback');
    if (horizonWarning(item))
        badges.push('event warning');
    return badges;
}
function horizonWarning(item) {
    const flags = asList(item.semantic_flags).map((flag) => String(flag).toLowerCase());
    const state = String(item.state ?? '').toLowerCase();
    const reason = String(item.reason ?? '').toLowerCase();
    return [...flags, state, reason].some((value) => value.includes('volatility_shock') || value.includes('event_distorted'));
}
function horizonRadarContext(item) {
    const context = asRow(item.radar_context);
    const status = text(context.status, 'waiting');
    const bias = text(context.bias, '0');
    return `${status} · bias ${bias}`;
}
function horizonEventTrustCap(item) {
    const eventTrust = asRow(item.event_trust);
    return text(eventTrust.event_trust_cap ?? item.event_trust_cap, 'not capped');
}
function horizonEventPhase(item) {
    const flags = asList(item.semantic_flags).map((flag) => String(flag).toLowerCase());
    const known = ['pre_event', 'post_event_unconfirmed', 'post_event_accepted', 'shock_absorbed', 'event_distorted', 'volatility_shock'];
    const matched = known.find((phase) => flags.some((flag) => flag.includes(phase)));
    if (matched)
        return matched;
    const eventTrust = asRow(item.event_trust);
    return text(eventTrust.phase ??
        eventTrust.event_phase ??
        eventWindowState.value.event_phase ??
        eventWindowState.value.event_window_state, 'calendar_monitor');
}
function horizonBtcAcceptance(item) {
    const state = asRow(item.acceptance).state;
    const score = item.direct_trend_acceptance_score ?? item.acceptance_score;
    if (state)
        return `${text(state)} · ${text(score)}`;
    return text(score, 'waiting');
}
function horizonDirectEvidenceText(item, limit = 3) {
    const evidence = asRow(item.direct_evidence);
    const rows = [];
    for (const [group, metrics] of Object.entries(evidence)) {
        const groupRows = asRow(metrics);
        const topMetric = Object.entries(groupRows)
            .map(([metricId, payload]) => ({ metricId, payload: asRow(payload) }))
            .sort((left, right) => Math.abs(Number(right.payload.score ?? 0)) - Math.abs(Number(left.payload.score ?? 0)))[0];
        if (topMetric) {
            const semantic = topMetric.payload.semantic_state ? ` · ${text(topMetric.payload.semantic_state)}` : '';
            rows.push(`${metricLabel(topMetric.metricId)} ${text(topMetric.payload.score)}${semantic}`);
        }
        else if (Object.keys(groupRows).length === 0 && ['price_structure', 'orderflow_acceptance', 'btc_residual_cross_asset'].includes(group)) {
            rows.push(`${group.replace(/_/g, ' ')} pending`);
        }
        if (rows.length >= limit)
            break;
    }
    return rows.length ? rows.join(' · ') : 'direct evidence pending';
}
function horizonConfirmationRules(item, limit = 2) {
    const rules = asList(item.next_confirmation).map((rule) => readableMetricText(rule));
    if (rules.length)
        return rules.slice(0, limit);
    return horizonWatchRules(item, limit);
}
function horizonInvalidationRules(item, limit = 2) {
    const rules = asList(item.invalidation).map((rule) => readableMetricText(rule));
    if (rules.length)
        return rules.slice(0, limit);
    return asList(item.next_invalidation_triggers).map((rule) => readableMetricText(rule)).slice(0, limit);
}
function horizonEvidenceChips(item, bucket, limit = 3) {
    const evidence = (item.evidence ?? {});
    return asList(evidence[bucket])
        .map((entry) => {
        if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
            const row = entry;
            return String(row.module_id ?? row.metric_id ?? row.name ?? '');
        }
        return String(entry ?? '');
    })
        .filter((entry, index, array) => entry && array.indexOf(entry) === index)
        .slice(0, limit);
}
function horizonWatchRules(item, limit = 4) {
    const confirmations = asList(item.next_confirmation_triggers).map((rule) => readableMetricText(rule));
    const invalidations = asList(item.next_invalidation_triggers).map((rule) => readableMetricText(rule));
    const v2Rules = [...confirmations, ...invalidations];
    if (v2Rules.length)
        return v2Rules.slice(0, limit);
    const rules = asList(item.watch_rules).map((rule) => readableMetricText(rule));
    if (rules.length)
        return rules.slice(0, limit);
    const drivers = [...metricChips(item.support_drivers, 2), ...metricChips(item.pressure_drivers, 2)];
    return drivers.slice(0, limit).map((driver) => `Watch whether ${metricLabel(driver)} continues the current direction`);
}
async function runAndOpenLogs() {
    if (state.routeContext.isHistorical) {
        store.exitHistoryMode();
        await store.refreshLatest();
    }
    navigateTo('logs');
    await store.runFullChain({ llmEnabled: state.llmRunEnabled });
}
async function toggleFullscreen() {
    if (document.fullscreenElement) {
        await document.exitFullscreen();
    }
    else {
        await document.documentElement.requestFullscreen();
    }
}
async function openRadarDetail(moduleId) {
    navigateTo('radar');
    selectedModuleId.value = moduleId;
    await store.loadRadarDetail(moduleId);
    selectedRadarMetricId.value = text(selectedRadarMetrics.value[0]?.metric_id, '');
}
async function openEvidenceDetail(evidenceId) {
    navigateTo('evidence', { keepEvidenceDetail: true });
    selectedEvidenceId.value = evidenceId;
    await store.loadEvidenceDetail(evidenceId);
    selectedEvidenceId.value = state.routeContext.evidence_id || evidenceId;
}
function closeEvidenceDetail() {
    selectedEvidenceId.value = '';
    state.selectedEvidenceDetail = null;
    state.routeContext.evidence_id = '';
}
function handleGlobalKeydown(event) {
    if (event.key === 'Escape' && activePage.value === 'evidence' && state.selectedEvidenceDetail) {
        closeEvidenceDetail();
    }
}
async function openSourceDetail(sourceId) {
    navigateTo('source');
    selectedSourceId.value = sourceId;
    await store.loadSourceDetail(sourceId);
}
async function openVerifyWindowForSource(sourceIdValue) {
    const result = await store.openSourceVerifyWindow(sourceIdValue);
    const url = String(result?.url ?? result?.verify_url ?? '');
    if (url)
        window.open(url, '_blank', 'noopener,noreferrer');
}
async function retryCollectForSource(sourceIdValue) {
    await store.retrySourceCollect(sourceIdValue);
    await store.refreshLatest();
}
async function viewLastCaptureForSource(sourceIdValue) {
    await store.loadSourceLastCapture(sourceIdValue);
    selectedSourceId.value = sourceIdValue;
    navigateTo('source');
}
async function openSourceEvidenceItem(item) {
    const evidenceId = String(item.evidence_id ?? '');
    if (evidenceId) {
        await openEvidenceDetail(evidenceId);
        return;
    }
    await openMetricEvidence(item.metric_id);
}
function openAuditReports() {
    navigateTo('logs');
}
function openLlmAppendix() {
    navigateTo('article');
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.main, __VLS_intrinsicElements.main)({
    ...{ class: "shell" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({
    ...{ class: "topbar" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "brand" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "brand-mark" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "ticker" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
(__VLS_ctx.text(__VLS_ctx.state.dashboard?.btc_price, ''));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "pill" },
    ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.state.dashboard?.final_view)) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "dot" },
});
(__VLS_ctx.state.dashboard?.final_view_cn ?? __VLS_ctx.state.dashboard?.final_view ?? '-');
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "pill mixed" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "dot mixed" },
});
(__VLS_ctx.text(__VLS_ctx.alerts[0]?.level, 'watch'));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "pill bull" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "dot bull" },
});
(__VLS_ctx.text(__VLS_ctx.contract.status, '-'));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "pill mixed" },
    title: "Frozen P4.5 final lineage; not the live radar heartbeat",
});
(__VLS_ctx.shortRunId(__VLS_ctx.frozenFinalLineage.final_run_id));
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.navigateTo('logs');
        } },
    ...{ class: "pill run-state-pill" },
    ...{ class: (__VLS_ctx.runHealthClass) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "dot" },
});
(__VLS_ctx.runningStageText);
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.store.runRadarRuntimeOnce();
        } },
    ...{ class: "pill run-state-pill" },
    ...{ class: (__VLS_ctx.statusClass(__VLS_ctx.liveRuntimeFreshness.health_state)) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "dot" },
});
(__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.health_state, 'runtime'));
(__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.fresh_module_count, '0'));
(__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.expected_module_count, '14'));
(__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.source_freshness_state, 'unknown'));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "updated" },
});
(__VLS_ctx.text(__VLS_ctx.frozenFinalCreatedAt, '-'));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "pill quality" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "dot quality" },
});
(__VLS_ctx.text(__VLS_ctx.dataQuality.avg_metric_quality ?? __VLS_ctx.dataQuality.quality_score));
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.store.setLlmRunEnabled(!__VLS_ctx.state.llmRunEnabled);
        } },
    ...{ class: "llm-run-toggle" },
    ...{ class: ({ active: __VLS_ctx.state.llmRunEnabled }) },
    title: (__VLS_ctx.state.llmRunEnabled ? 'LLM on: P4.5 结论先出，LLM 文章后台补全' : 'Fast only: 本轮只跑到 P4.5 deterministic final'),
});
(__VLS_ctx.state.llmRunEnabled ? 'LLM on' : 'Fast only');
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.runAndOpenLogs) },
    ...{ class: "primary" },
    disabled: (__VLS_ctx.state.running),
});
(__VLS_ctx.state.running ? 'Running' : 'Run Full Chain');
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.openAuditReports) },
    ...{ class: "linklike" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.navigateTo('settings');
        } },
});
if (__VLS_ctx.showEventFloatingAlert) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ onMouseenter: (...[$event]) => {
                if (!(__VLS_ctx.showEventFloatingAlert))
                    return;
                __VLS_ctx.setEventFloatingAlertHover(true);
            } },
        ...{ onMouseleave: (...[$event]) => {
                if (!(__VLS_ctx.showEventFloatingAlert))
                    return;
                __VLS_ctx.setEventFloatingAlertHover(false);
            } },
        ...{ onFocusin: (...[$event]) => {
                if (!(__VLS_ctx.showEventFloatingAlert))
                    return;
                __VLS_ctx.setEventFloatingAlertHover(true);
            } },
        ...{ onFocusout: (...[$event]) => {
                if (!(__VLS_ctx.showEventFloatingAlert))
                    return;
                __VLS_ctx.setEventFloatingAlertHover(false);
            } },
        ...{ onClick: (__VLS_ctx.expandEventFloatingAlert) },
        ...{ onDblclick: (__VLS_ctx.resetEventAlertPosition) },
        ...{ onPointerdown: (__VLS_ctx.startEventAlertDrag) },
        ...{ onPointermove: (__VLS_ctx.dragEventAlert) },
        ...{ onPointerup: (__VLS_ctx.stopEventAlertDrag) },
        ...{ onPointercancel: (__VLS_ctx.stopEventAlertDrag) },
        ...{ class: "event-floating-alert" },
        ...{ class: ([__VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level), { 'is-positioned': __VLS_ctx.eventAlertPosition, 'is-muted': __VLS_ctx.eventFloatingAlertMuted }]) },
        ...{ style: (__VLS_ctx.eventFloatingAlertStyle) },
        title: (__VLS_ctx.eventFloatingAlertMuted ? '点击展开，拖动调整位置，双击归位' : '拖动调整位置，双击归位'),
        role: "status",
        'aria-live': "polite",
    });
    if (__VLS_ctx.eventFloatingAlertMuted) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "event-floating-icon-dot" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.text(__VLS_ctx.eventWindowActive.event_type, 'event'));
        (__VLS_ctx.text(__VLS_ctx.eventWindowState.emergency_level, 'high'));
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.eventFloatingTitle);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.eventFloatingSubtitle);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "event-floating-permission" },
        });
        (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.trade_permission_modifier, 'watch_only'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.eventFloatingMessage);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.footer, __VLS_intrinsicElements.footer)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onPointerdown: () => { } },
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.showEventFloatingAlert))
                        return;
                    if (!!(__VLS_ctx.eventFloatingAlertMuted))
                        return;
                    __VLS_ctx.muteEventFloatingAlert(15);
                } },
            type: "button",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onPointerdown: () => { } },
            ...{ onClick: (__VLS_ctx.dismissEventFloatingAlertSession) },
            type: "button",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onPointerdown: () => { } },
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.showEventFloatingAlert))
                        return;
                    if (!!(__VLS_ctx.eventFloatingAlertMuted))
                        return;
                    __VLS_ctx.activePage = 'eventWatchtower';
                } },
            type: "button",
            ...{ class: "primary" },
        });
    }
}
if (__VLS_ctx.showEventCriticalOverlay) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "event-critical-overlay" },
        role: "dialog",
        'aria-modal': "true",
        'aria-label': "Critical event window alert",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ class: "event-critical-card" },
        ...{ class: (__VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level)) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill bear" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "dot bear" },
    });
    (__VLS_ctx.text(__VLS_ctx.eventWindowState.emergency_level, 'critical'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.dismissEventCriticalOverlay) },
        ...{ class: "event-critical-close" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowActive.title, 'Policy shock watch'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowState.event_window_state, 'unscheduled_shock_confirmed'));
    (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.trade_permission_modifier, 'event_lock'));
    (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.ordinary_radar_trust, 'blocked'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "event-critical-meta" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowState.event_window_state, 'critical'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.trade_permission_modifier, 'event_lock'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.ordinary_radar_trust, 'blocked'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowState.valid_until, '-'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.eventWindowDirectScoreImpact);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.eventWatchtowerPayload.snapshot_id, '-'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "event-critical-reasons" },
    });
    for (const [code] of __VLS_getVForSourceType((__VLS_ctx.eventWindowReasonCodes))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            key: (code),
            ...{ class: "event-chip mixed" },
        });
        (code);
    }
    if (!__VLS_ctx.eventWindowReasonCodes.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "event-chip" },
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.footer, __VLS_intrinsicElements.footer)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.showEventCriticalOverlay))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "primary" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
}
if (__VLS_ctx.showEventCriticalMockOverlay) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "event-critical-overlay event-critical-mock-overlay" },
        role: "dialog",
        'aria-modal': "true",
        'aria-label': "Mock critical event window alert",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ class: "event-critical-card event-critical-mock-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill mixed" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "dot mixed" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "event-chip" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.footer, __VLS_intrinsicElements.footer)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.showEventCriticalMockOverlay))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "primary" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
    ...{ class: "main" },
    ...{ class: (__VLS_ctx.pageShellClass) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.aside, __VLS_intrinsicElements.aside)({
    ...{ class: "rail" },
});
for (const [page] of __VLS_getVForSourceType((__VLS_ctx.pages))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.navigateTo(page.id);
            } },
        key: (page.id),
        ...{ class: "navbtn" },
        ...{ class: ({ active: __VLS_ctx.activePage === page.id }) },
    });
    (page.label);
}
if (!__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(!__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.drawerOpen = true;
            } },
        ...{ class: "drawer-reopen" },
    });
}
if (__VLS_ctx.pageFullscreen) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "fullscreen-toolbar" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.pageTitle);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.state.routeContext.final_run_id ?? __VLS_ctx.store.runLineage.value.final_run_id, 'latest'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.togglePageFullscreen) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.goDashboard) },
    });
}
if (__VLS_ctx.activePage === 'topology') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "canvas" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ref: "topologyRef",
        ...{ class: "topology" },
    });
    /** @type {typeof __VLS_ctx.topologyRef} */ ;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "topology-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.store.radarModules.value.length || 14);
    (__VLS_ctx.state.dashboard?.metric_evidence_count ?? 0);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.resetRadarLayout) },
        ...{ class: "layout-reset" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "legend" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "dot bull" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "dot bear" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "dot mixed" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "dot quality" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        ...{ class: "links" },
        viewBox: "0 0 1000 620",
        preserveAspectRatio: "none",
        'aria-hidden': "true",
    });
    for (const [link] of __VLS_getVForSourceType((__VLS_ctx.dynamicLinks))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
            key: (`link-${link.moduleId}`),
            d: (link.path),
            ...{ class: "link" },
            ...{ class: (link.kind) },
            ...{ style: ({ opacity: link.opacity, strokeWidth: link.strokeWidth }) },
        });
    }
    for (const [node] of __VLS_getVForSourceType((__VLS_ctx.topologyModules))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onPointerdown: (...[$event]) => {
                    if (!(__VLS_ctx.activePage === 'topology'))
                        return;
                    __VLS_ctx.startDrag($event, __VLS_ctx.moduleName(node.module));
                } },
            ...{ onPointermove: (__VLS_ctx.dragNode) },
            ...{ onPointerup: (__VLS_ctx.stopDrag) },
            ...{ onPointercancel: (__VLS_ctx.stopDrag) },
            ...{ onMousemove: (__VLS_ctx.handleRadarNodeMove) },
            ...{ onMouseleave: (__VLS_ctx.resetRadarNodeTilt) },
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.activePage === 'topology'))
                        return;
                    __VLS_ctx.openRadarNode($event, __VLS_ctx.moduleName(node.module));
                } },
            key: (__VLS_ctx.moduleName(node.module)),
            ...{ class: "node" },
            ...{ class: (__VLS_ctx.nodeClass(node)) },
            ...{ style: (__VLS_ctx.nodeStyle(__VLS_ctx.moduleName(node.module), node.index)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "node-tilt" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "node-title" },
        });
        (__VLS_ctx.shortModuleName(node.module));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill compact-state" },
            title: (__VLS_ctx.moduleDisplayLabel(node.module)),
        });
        (__VLS_ctx.moduleDisplayShortLabel(node.module));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "node-meta" },
        });
        (__VLS_ctx.moduleMeta(node.module));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "node-audit" },
        });
        (__VLS_ctx.moduleAuditMeta(node.module));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "node-score" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "bar" },
            ...{ class: (__VLS_ctx.directionClass(node.direction)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ style: ({ width: `${Math.min(92, Math.max(18, Math.abs(Number(node.module.module_effective_score ?? node.module.module_score ?? 0)) * 240))}%` }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(node.module.module_effective_score ?? node.module.module_score));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ onMousemove: (__VLS_ctx.handleBtcMove) },
        ...{ onMouseleave: (__VLS_ctx.resetBtcTilt) },
        ref: "btcRef",
        ...{ class: "btc-node" },
        ...{ class: (__VLS_ctx.btcNodeClass) },
    });
    /** @type {typeof __VLS_ctx.btcRef} */ ;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "btc-dynamic-shadow" },
        'aria-hidden': "true",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "btc-head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "btc-symbol btc-gold-text" },
        'data-text': "BTC",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "state" },
    });
    (__VLS_ctx.finalViewText);
    (__VLS_ctx.tradePermissionText);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "score-ring" },
        ...{ style: (__VLS_ctx.scoreRingStyle) },
    });
    (__VLS_ctx.scorePercent);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "btc-badges" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'quality';
            } },
        ...{ class: "status-chip" },
    });
    (__VLS_ctx.dataQualityLabel);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'logs';
            } },
        ...{ class: "status-chip" },
    });
    (__VLS_ctx.contractStatus);
    if (__VLS_ctx.hasCockpit) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!(__VLS_ctx.hasCockpit))
                        return;
                    __VLS_ctx.activePage = 'overview';
                } },
            ...{ class: "status-chip" },
        });
    }
    if (__VLS_ctx.hasRuntimeCockpit) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!(__VLS_ctx.hasRuntimeCockpit))
                        return;
                    __VLS_ctx.activePage = 'radar';
                } },
            ...{ class: "status-chip" },
        });
        (__VLS_ctx.text(__VLS_ctx.radarRuntimeHealth.health_state, 'fresh'));
    }
    if (__VLS_ctx.hasCockpit) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "cockpit-readout" },
            ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.cockpitFastDirection)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "readout-label" },
        });
        (__VLS_ctx.cockpitReadoutLabel);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.cockpitFastScore);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "readout-chip" },
        });
        (__VLS_ctx.cockpitFastDirection);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.cockpitFastStage);
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "summary-text" },
        });
        (__VLS_ctx.cockpitSummaryText);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "btc-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mini-kv" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.btcCockpit.btc_strength ?? __VLS_ctx.decision.strength_cn ?? __VLS_ctx.decision.strength));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mini-kv" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.btcCockpit.trend_quality ?? __VLS_ctx.decision.risk_mode));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mini-kv" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.cockpitHorizon['4h']?.direction ?? __VLS_ctx.horizonDirection('4h')));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mini-kv horizon-pair" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.cockpitHorizon['24h']?.direction ?? __VLS_ctx.horizonDirection('1d')));
    (__VLS_ctx.text(__VLS_ctx.cockpitHorizon['3d']?.direction ?? __VLS_ctx.horizonDirection('3d')));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "why-strip" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'overview';
            } },
    });
    (__VLS_ctx.cockpitPressureText);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'overview';
            } },
    });
    (__VLS_ctx.cockpitSupportText);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'overview';
            } },
    });
    (__VLS_ctx.cockpitConflictText);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "btc-watch" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'invalidation';
            } },
    });
    (__VLS_ctx.primaryCockpitInvalidation);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'invalidation';
            } },
    });
    (__VLS_ctx.primaryCockpitTrigger);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "btc-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'overview';
            } },
        ...{ class: "pill" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'article';
            } },
        ...{ class: "pill" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.navigateTo('evidence');
            } },
        ...{ class: "pill" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.openLlmAppendix) },
        ...{ class: "pill" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "bottom-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "panel-head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill" },
    });
    (__VLS_ctx.text(__VLS_ctx.btcTimescaleJudge.schema_version, 'horizon_views'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "horizon-row" },
    });
    for (const [[key, item]] of __VLS_getVForSourceType((__VLS_ctx.horizons))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.activePage === 'topology'))
                        return;
                    __VLS_ctx.activePage = 'overview';
                } },
            key: (key),
            ...{ class: "horizon-card" },
            ...{ class: (__VLS_ctx.horizonCardClasses(item)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "horizon-card-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.horizonFullLabel(key));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.directionText(item.direction));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "horizon-badges" },
        });
        for (const [badge] of __VLS_getVForSourceType((__VLS_ctx.horizonFreshnessBadges(item)))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                key: (`${key}-${badge}`),
            });
            (badge);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "horizon-meta" },
        });
        (__VLS_ctx.text(item.state, 'waiting'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "horizon-score-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
        (__VLS_ctx.horizonScore(item));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
        (__VLS_ctx.horizonConfidence(item));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
        (__VLS_ctx.horizonDisplayScore(item));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.horizonSummary(key, item));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "horizon-chain" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.horizonDirectEvidenceText(item));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "horizon-chain" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.horizonRadarContext(item));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "horizon-chain" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.horizonBtcAcceptance(item));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "horizon-chain" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.horizonEventTrustCap(item));
        if (key === '4h' || key === '1d') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "horizon-chain" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.horizonEventPhase(item));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "driver-line" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.horizonConfirmationRules(item, 2)))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                key: (`confirm-${key}-${rule}`),
                title: (rule),
            });
            (rule);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "driver-line pressure" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.horizonInvalidationRules(item, 2)))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                key: (`invalidate-${key}-${rule}`),
                title: (rule),
            });
            (rule);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
        (__VLS_ctx.text(item.fallback_reason, 'v2.2 direct trend payload'));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ class: "panel alert-event-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "panel-head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "pill mixed" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "alert-card event-summary-widget" },
        ...{ class: (__VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level)) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowState.emergency_level, 'none'));
    (__VLS_ctx.text(__VLS_ctx.eventWindowState.event_window_state, 'calendar_monitor'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.eventWindowSummaryTitle);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.eventWindowSummarySubtitle);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
    (__VLS_ctx.eventWindowSummaryDetail);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "event-summary-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "event-summary-kv" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.trade_permission_modifier, 'none'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.eventWindowSummaryAction);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "event-summary-kv" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.ordinary_radar_trust, 'normal'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "event-summary-kv" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.status, 'running'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.collection_mode, 'standalone daemon'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "event-summary-kv" },
        ...{ class: (__VLS_ctx.marketReturnTone(__VLS_ctx.eventWindowMarketReturns['4h'])) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.marketReturnPct(__VLS_ctx.eventWindowMarketReturns['4h']));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.runtime_code_version, 'watchtower runtime'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "event-summary-kv" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.eventWindowSourceMode);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.eventWindowSourceCounts.live);
    (__VLS_ctx.eventWindowSourceCounts.partial);
    (__VLS_ctx.eventWindowSourceCounts.fallback);
    (__VLS_ctx.eventWindowSourceCounts.failed);
    if (__VLS_ctx.eventWindowDisabledCapabilities.length || __VLS_ctx.eventWindowSourceCounts.failed > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "event-source-note" },
        });
        if (__VLS_ctx.eventWindowDisabledCapabilities.length) {
            (__VLS_ctx.eventWindowDisabledCapabilities.slice(0, 5).join(', '));
        }
        else {
        }
        (__VLS_ctx.eventWindowSourceCounts.failed);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "event-summary-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.store.runRadarRuntimeOnce();
            } },
        ...{ class: "event-summary-kv" },
        ...{ class: (__VLS_ctx.statusClass(__VLS_ctx.radarRuntimeDaemon.health_state ?? __VLS_ctx.radarRuntimeDaemon.status)) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.radarRuntimeDaemon.health_state ?? __VLS_ctx.radarRuntimeDaemon.status, 'unknown'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.text(__VLS_ctx.radarRuntimeDaemon.last_tick_age_sec, '-'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'radar';
            } },
        ...{ class: "event-summary-kv" },
        ...{ class: (__VLS_ctx.statusClass(__VLS_ctx.radarRuntimeHealth.health_state)) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.radarRuntimeHealth.fresh_module_count, '0'));
    (__VLS_ctx.text(__VLS_ctx.radarRuntimeHealth.expected_module_count, '14'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.text(__VLS_ctx.radarRuntimeHealth.stale_module_count, '0'));
    (__VLS_ctx.text(__VLS_ctx.radarRuntimeHealth.source_freshness_state, 'unknown'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'overview';
            } },
        ...{ class: "event-summary-kv" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.radarRuntimeCockpit.headline_stage, 'pending'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.text(__VLS_ctx.radarRuntimeCockpit.why_not_confirmed, 'waiting for runtime snapshot'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "watch-list compact" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "watch-row" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowActive.title, 'calendar monitor'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowActive.event_type, 'event'));
    (__VLS_ctx.daysText(Number(__VLS_ctx.eventWindowActive.time_to_event_sec ?? 0) / 86400));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowActive.phase, 'calendar_awareness'));
    (__VLS_ctx.text(__VLS_ctx.eventWindowState.valid_until, '-'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "watch-row" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.shock_type, 'none'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.confirmation_level, 'none'));
    (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.source_count, '0'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.market_dislocation, 'false'));
    (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.btc_microstructure_confirmation, 'false'));
    (__VLS_ctx.text(__VLS_ctx.eventWindowShockEvidence.primary_window, '-'));
    (__VLS_ctx.marketReturnPct(__VLS_ctx.eventWindowShockEvidence.primary_return));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'topology'))
                    return;
                __VLS_ctx.activePage = 'eventWatchtower';
            } },
        ...{ class: "watch-row" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowSummaryAlert.title, 'no active event-window alert'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowSummaryAlert.emergency_level, 'none'));
    (__VLS_ctx.text(__VLS_ctx.eventWindowSummaryAlert.status, 'open'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.text(__VLS_ctx.eventWindowSummaryAlert.summary, 'Event Window is monitoring scheduled and unscheduled risk.'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "halving-strip" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "content-page" },
    });
    if (__VLS_ctx.activePage === 'overview') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel overview-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head event-page-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
            ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.state.dashboard?.final_view)) },
        });
        (__VLS_ctx.finalViewText);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "overview-hero" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.text(__VLS_ctx.decision.conclusion_sentence, 'Waiting for P4.5 decision card'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "overview-kvs" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.decision.strength_cn ?? __VLS_ctx.decision.strength));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.decision.confidence_level ?? __VLS_ctx.decision.confidence));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.tradePermissionText);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "overview-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "overview-state-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.aggregation.directional_score ?? __VLS_ctx.aggregation.final_score_adjusted));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.text(__VLS_ctx.aggregation.raw_net_score ?? __VLS_ctx.overviewScoreComponents.net_score));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.overviewScoreComponents.support_score_abs));
        (__VLS_ctx.text(__VLS_ctx.overviewScoreComponents.pressure_score_abs));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.text(__VLS_ctx.aggregation.disagreement_level));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.componentPercent(__VLS_ctx.overviewScoreComponents.zero_metric_ratio));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.componentPercent(__VLS_ctx.overviewScoreComponents.unavailable_metric_ratio));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.decision.risk_mode, 'balanced'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.text(__VLS_ctx.decision.valid_horizon, '24h_to_3d'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "driver-column-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "driver-panel" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-card-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill bull" },
        });
        (__VLS_ctx.overviewSupportDrivers.length);
        for (const [driver] of __VLS_getVForSourceType((__VLS_ctx.overviewSupportDrivers))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!(__VLS_ctx.activePage === 'overview'))
                            return;
                        __VLS_ctx.openMetricEvidence(driver.metric_id);
                    } },
                key: (`support-driver-${__VLS_ctx.driverMetricId(driver)}`),
                ...{ class: "driver-row" },
                ...{ class: (__VLS_ctx.directionClass(driver.direction)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.metricLabel(driver.metric_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(driver.module));
            (__VLS_ctx.driverContribution(driver));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.driverReason(driver));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "driver-panel pressure" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-card-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill bear" },
        });
        (__VLS_ctx.overviewPressureDrivers.length);
        for (const [driver] of __VLS_getVForSourceType((__VLS_ctx.overviewPressureDrivers))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!(__VLS_ctx.activePage === 'overview'))
                            return;
                        __VLS_ctx.openMetricEvidence(driver.metric_id);
                    } },
                key: (`pressure-driver-${__VLS_ctx.driverMetricId(driver)}`),
                ...{ class: "driver-row" },
                ...{ class: (__VLS_ctx.directionClass(driver.direction)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.metricLabel(driver.metric_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(driver.module));
            (__VLS_ctx.driverContribution(driver));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.driverReason(driver));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "confidence-box" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.normalizationText());
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "module-stats" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.overviewScoreNormalization.normalization_base));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.overviewScoreNormalization.direction_threshold?.neutral_low));
        (__VLS_ctx.text(__VLS_ctx.overviewScoreNormalization.direction_threshold?.neutral_high));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.overviewScoreComponents.confidence_penalty));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.aggregation.data_quality_level));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "watch-list compact" },
        });
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.overviewWatchRows))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!(__VLS_ctx.activePage === 'overview'))
                            return;
                        __VLS_ctx.activePage = 'invalidation';
                    } },
                key: (`${item.kind}-${__VLS_ctx.text(item.rule.rule_id)}`),
                ...{ class: "watch-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (item.kind);
            (__VLS_ctx.text(item.rule.title ?? item.rule.rule_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.ruleSummary(item.rule));
        }
        if (__VLS_ctx.overviewDataBoundary.length) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "data-boundary-strip" },
            });
            for (const [item] of __VLS_getVForSourceType((__VLS_ctx.overviewDataBoundary))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    key: (item),
                });
                (item);
            }
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "overview-lineage-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.overviewRunLineage.collect_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.overviewRunLineage.p2_radar_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.overviewRunLineage.p3_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.overviewRunLineage.final_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "horizon-detail-grid" },
        });
        for (const [[key, item]] of __VLS_getVForSourceType((__VLS_ctx.horizons))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                key: (`detail-${key}`),
                ...{ class: "horizon-detail-card" },
                ...{ class: (__VLS_ctx.horizonCardClasses(item)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "horizon-detail-head" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.horizonFullLabel(key));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.directionText(item.direction));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "horizon-badges" },
            });
            for (const [badge] of __VLS_getVForSourceType((__VLS_ctx.horizonFreshnessBadges(item)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                    key: (`detail-${key}-${badge}`),
                });
                (badge);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "horizon-score-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            (__VLS_ctx.horizonScore(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            (__VLS_ctx.horizonConfidence(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            (__VLS_ctx.horizonDisplayScore(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.text(item.state, 'waiting'));
            (key === '4h' || key === '1d' ? __VLS_ctx.horizonEventPhase(item) : 'context');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.horizonSummary(key, item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "horizon-chain" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.horizonDirectEvidenceText(item, 5));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "horizon-chain" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.horizonRadarContext(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "horizon-chain" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.horizonBtcAcceptance(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "horizon-chain" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.horizonEventTrustCap(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "driver-block" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
            for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.horizonConfirmationRules(item, 5)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    key: (`detail-confirm-${key}-${rule}`),
                    title: (rule),
                });
                (rule);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "driver-block pressure" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
            for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.horizonInvalidationRules(item, 5)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    key: (`detail-invalidate-${key}-${rule}`),
                    title: (rule),
                });
                (rule);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({
                ...{ class: "watch-bullets" },
            });
            for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.horizonWatchRules(item, 5)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
                    key: (`${key}-${rule}`),
                });
                (rule);
            }
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "overview-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        for (const [reason] of __VLS_getVForSourceType((__VLS_ctx.decisionReasons))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                key: (__VLS_ctx.text(reason)),
            });
            (__VLS_ctx.text(reason));
        }
    }
    else if (__VLS_ctx.activePage === 'radar') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel radar-detail-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!(__VLS_ctx.activePage === 'radar'))
                        return;
                    __VLS_ctx.activePage = 'topology';
                } },
            ...{ class: "pill" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!(__VLS_ctx.activePage === 'radar'))
                        return;
                    __VLS_ctx.navigateTo('evidence');
                } },
            ...{ class: "pill" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!(__VLS_ctx.activePage === 'radar'))
                        return;
                    __VLS_ctx.activePage = 'quality';
                } },
            ...{ class: "pill quality" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "radar-module-switch" },
        });
        for (const [module] of __VLS_getVForSourceType((__VLS_ctx.store.radarModules.value))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!(__VLS_ctx.activePage === 'radar'))
                            return;
                        __VLS_ctx.openRadarDetail(__VLS_ctx.moduleName(module));
                    } },
                key: (__VLS_ctx.moduleName(module)),
                ...{ class: ([__VLS_ctx.moduleDisplayClass(module), __VLS_ctx.selectedModuleId === __VLS_ctx.moduleName(module) ? 'active' : '']) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.shortModuleName(module));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.moduleDisplayLabel(module));
            (__VLS_ctx.text(module.module_effective_score ?? module.module_score));
        }
        if (__VLS_ctx.state.selectedRadarDetail) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "radar-scope-layout" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "radar-scope-panel" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "scope-toolbar" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "filters" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill bull" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "dot bull" },
            });
            (__VLS_ctx.selectedRadarMetricStats.support);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill bear" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "dot bear" },
            });
            (__VLS_ctx.selectedRadarMetricStats.pressure);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill mixed" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "dot mixed" },
            });
            (__VLS_ctx.selectedRadarMetricStats.mixed);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill quality" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "dot quality" },
            });
            (__VLS_ctx.selectedRadarMetricStats.quality);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
                ...{ class: "radar-scope-svg" },
                viewBox: "0 0 640 640",
                preserveAspectRatio: "xMidYMid meet",
                'aria-hidden': "true",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.circle)({
                ...{ class: "scope-ring" },
                cx: "320",
                cy: "320",
                r: "96",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.circle)({
                ...{ class: "scope-ring" },
                cx: "320",
                cy: "320",
                r: "176",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.circle)({
                ...{ class: "scope-ring" },
                cx: "320",
                cy: "320",
                r: "256",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.line)({
                ...{ class: "scope-axis" },
                x1: "320",
                y1: "58",
                x2: "320",
                y2: "582",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.line)({
                ...{ class: "scope-axis" },
                x1: "58",
                y1: "320",
                x2: "582",
                y2: "320",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
                ...{ class: "scope-scan" },
                d: "M320 320 L320 58 A262 262 0 0 1 495 126 Z",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "radar-scope-card-rail left" },
                'aria-label': "Top radar metrics left",
            });
            for (const [metric, index] of __VLS_getVForSourceType((__VLS_ctx.radarMetricRail('left')))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!(__VLS_ctx.state.selectedRadarDetail))
                                return;
                            __VLS_ctx.selectRadarMetric(metric);
                        } },
                    key: (`rail-left-${__VLS_ctx.text(metric.evidence_id ?? metric.metric_id)}`),
                    ...{ class: "radar-scope-metric-card" },
                    ...{ class: ([__VLS_ctx.radarMetricClass(metric), __VLS_ctx.selectedRadarMetricId === __VLS_ctx.text(metric.metric_id) ? 'selected' : '']) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "metric-card-head" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.metricLabel(metric.metric_id));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill" },
                });
                (index * 2 + 1);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.radarMetricSummary(metric));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "metric-card-meta" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.radarMetricCompactMeta(metric));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(metric.quality_score));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "metric-score-track" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ style: ({ width: __VLS_ctx.radarMetricBarWidth(metric) }) },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "radar-center-card" },
                ...{ class: (__VLS_ctx.moduleDisplayClass(__VLS_ctx.selectedRadarModule)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.moduleDisplayClass(__VLS_ctx.selectedRadarModule)) },
            });
            (__VLS_ctx.moduleDisplayLabel(__VLS_ctx.selectedRadarModule));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            (__VLS_ctx.text(__VLS_ctx.selectedRadarModule.radar_module ?? __VLS_ctx.selectedModuleId, 'Select Radar Module'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.moduleMeta(__VLS_ctx.selectedRadarModule));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "module-stats" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.selectedRadarModule.module_effective_score ?? __VLS_ctx.selectedRadarModule.module_score));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.selectedRadarModule.module_quality_score));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.selectedRadarMetrics.length));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.selectedRadarModule.module_weight));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "module-stats semantic-stats" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.selectedRadarModule.signal_stage ?? __VLS_ctx.selectedRadarModule.stage, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.asList(__VLS_ctx.selectedRadarModule.support_drivers).length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.asList(__VLS_ctx.selectedRadarModule.pressure_drivers).length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.moduleDisplayClass(__VLS_ctx.selectedRadarModule));
            if (__VLS_ctx.selectedRadarModule.crowding_state || __VLS_ctx.selectedRadarModule.positioning_state || __VLS_ctx.selectedRadarModule.top_positioning_state || __VLS_ctx.selectedRadarModule.long_short_squeeze_risk) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.selectedRadarModule.crowding_state));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.selectedRadarModule.top_positioning_state ?? __VLS_ctx.selectedRadarModule.positioning_state));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.selectedRadarModule.long_short_squeeze_risk));
            }
            if (__VLS_ctx.hasTradeStructureStates(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                for (const [row] of __VLS_getVForSourceType((__VLS_ctx.tradeStructureStateRows(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        key: (`trade-${row[0]}`),
                    });
                    (row[0]);
                    (__VLS_ctx.text(row[1]));
                }
            }
            if (__VLS_ctx.isOptionsVolatilityModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.optionsVolatilityContract(__VLS_ctx.selectedRadarModule).options_short_term_state, 'vol_neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.optionsVolatilityContract(__VLS_ctx.selectedRadarModule).risk_score));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.optionsVolatilityContract(__VLS_ctx.selectedRadarModule).trade_permission_hint, 'normal'));
            }
            if (__VLS_ctx.isEventPolicyModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.eventPolicyContract(__VLS_ctx.selectedRadarModule).event_short_term_state, 'event_neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.eventPolicyContract(__VLS_ctx.selectedRadarModule).event_window_phase, 'neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.eventPolicyContract(__VLS_ctx.selectedRadarModule).trade_gate.reason_code, 'EVENT_NEUTRAL'));
            }
            if (__VLS_ctx.isCryptoBreadthModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.cryptoBreadthContract(__VLS_ctx.selectedRadarModule).crypto_breadth_state, 'neutral_wait_confirm'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.cryptoBreadthContract(__VLS_ctx.selectedRadarModule).btc_implication, 'neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.cryptoBreadthContract(__VLS_ctx.selectedRadarModule).risk_score));
            }
            if (__VLS_ctx.isMacroRadarModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.macroRadarContract(__VLS_ctx.selectedRadarModule).macro_trend_state, 'macro_neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.macroRadarContract(__VLS_ctx.selectedRadarModule).btc_implication, 'neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.macroRadarContract(__VLS_ctx.selectedRadarModule).risk_score));
            }
            if (__VLS_ctx.isDollarLiquidityModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.dollarLiquidityContract(__VLS_ctx.selectedRadarModule).dollar_liquidity_state, 'liquidity_neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.dollarLiquidityContract(__VLS_ctx.selectedRadarModule).repo_funding_pressure.state, 'missing'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.dollarLiquidityContract(__VLS_ctx.selectedRadarModule).btc_response_confirmation.state, 'missing'));
            }
            if (__VLS_ctx.isTreasuryCreditModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.treasuryCreditContract(__VLS_ctx.selectedRadarModule).treasury_credit_state, 'treasury_credit_neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.treasuryCreditContract(__VLS_ctx.selectedRadarModule).credit_stress.state, 'missing'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.treasuryCreditContract(__VLS_ctx.selectedRadarModule).btc_response_confirmation.state, 'missing'));
            }
            if (__VLS_ctx.isFundFlowModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.fundFlowContract(__VLS_ctx.selectedRadarModule).fund_flow_state, 'fund_flow_neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.fundFlowContract(__VLS_ctx.selectedRadarModule).etf_demand.state, 'missing'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.fundFlowContract(__VLS_ctx.selectedRadarModule).btc_response_confirmation.state, 'missing'));
            }
            if (__VLS_ctx.isOnchainValuationModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.onchainValuationContract(__VLS_ctx.selectedRadarModule).signal_stage, 'none'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.onchainValuationContract(__VLS_ctx.selectedRadarModule).module_bias, 'neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.onchainValuationContract(__VLS_ctx.selectedRadarModule).cost_basis.state, 'missing'));
            }
            if (__VLS_ctx.isAsiaRiskModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.asiaRiskContract(__VLS_ctx.selectedRadarModule).signal_stage, 'none'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.asiaRiskContract(__VLS_ctx.selectedRadarModule).asia_risk_state, 'asia_risk_neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.asiaRiskContract(__VLS_ctx.selectedRadarModule).btc_response_confirmation.state, 'missing'));
            }
            if (__VLS_ctx.isKlineOrderflowModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.klineOrderflowContract(__VLS_ctx.selectedRadarModule).signal_stage, 'none'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.klineOrderflowContract(__VLS_ctx.selectedRadarModule).kline_orderflow_state, 'neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.klineOrderflowContract(__VLS_ctx.selectedRadarModule).volatility_regime, 'normal_vol'));
            }
            if (__VLS_ctx.isBtcAdoptionModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "module-stats semantic-stats" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.btcAdoptionContract(__VLS_ctx.selectedRadarModule).signal_stage, 'none'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.btcAdoptionContract(__VLS_ctx.selectedRadarModule).btc_adoption_state, 'btc_adoption_neutral'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(__VLS_ctx.btcAdoptionContract(__VLS_ctx.selectedRadarModule).btc_response_confirmation.state, 'missing'));
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "radar-scope-card-rail right" },
                'aria-label': "Top radar metrics right",
            });
            for (const [metric, index] of __VLS_getVForSourceType((__VLS_ctx.radarMetricRail('right')))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!(__VLS_ctx.state.selectedRadarDetail))
                                return;
                            __VLS_ctx.selectRadarMetric(metric);
                        } },
                    key: (`rail-right-${__VLS_ctx.text(metric.evidence_id ?? metric.metric_id)}`),
                    ...{ class: "radar-scope-metric-card" },
                    ...{ class: ([__VLS_ctx.radarMetricClass(metric), __VLS_ctx.selectedRadarMetricId === __VLS_ctx.text(metric.metric_id) ? 'selected' : '']) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "metric-card-head" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.metricLabel(metric.metric_id));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill" },
                });
                (index * 2 + 2);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.radarMetricSummary(metric));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "metric-card-meta" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.radarMetricCompactMeta(metric));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(metric.quality_score));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "metric-score-track" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ style: ({ width: __VLS_ctx.radarMetricBarWidth(metric) }) },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.aside, __VLS_intrinsicElements.aside)({
                ...{ class: "radar-metric-panel" },
            });
            if (__VLS_ctx.isBtcTotalStateModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.btcTotalLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isBtcTotalStateModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isOptionsVolatilityModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid options-volatility-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.optionsVolatilityLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isOptionsVolatilityModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isEventPolicyModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid event-policy-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.eventPolicyLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isEventPolicyModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isCryptoBreadthModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid crypto-breadth-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.cryptoBreadthLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isCryptoBreadthModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isMacroRadarModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid macro-radar-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.macroRadarLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isMacroRadarModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isDollarLiquidityModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid macro-radar-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.dollarLiquidityLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isDollarLiquidityModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isTreasuryCreditModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid macro-radar-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.treasuryCreditLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isTreasuryCreditModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isFundFlowModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid macro-radar-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.fundFlowLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isFundFlowModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isOnchainValuationModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid macro-radar-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.onchainValuationLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isOnchainValuationModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isBtcAdoptionModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid macro-radar-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.btcAdoptionLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isBtcAdoptionModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isAsiaRiskModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid macro-radar-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.asiaRiskLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isAsiaRiskModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isTradeStructureFlowModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid macro-radar-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.tradeStructureFlowLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isTradeStructureFlowModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isKlineOrderflowModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid macro-radar-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.klineOrderflowLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isKlineOrderflowModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isDerivativesCrowdingModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "btc-total-state-grid macro-radar-grid" },
                });
                for (const [card] of __VLS_getVForSourceType((__VLS_ctx.derivativesCrowdingLayerCards(__VLS_ctx.selectedRadarModule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                        key: (card.key),
                        ...{ class: "btc-total-state-card" },
                        ...{ class: (card.key) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "pill" },
                    });
                    (card.title);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                    (__VLS_ctx.text(card.state, 'missing'));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.meta);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                    (card.note);
                    if (card.rows.length) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({});
                        for (const [[key, value]] of __VLS_getVForSourceType((card.rows))) {
                            (`${card.key}-${key}`);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
                            (key);
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
                            (__VLS_ctx.text(value));
                        }
                    }
                }
            }
            if (__VLS_ctx.isDerivativesCrowdingModule(__VLS_ctx.selectedRadarModule)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.derivativesCrowdingScopeText());
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "detail-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.radarMetricClass(__VLS_ctx.selectedRadarMetric)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            (__VLS_ctx.evidenceTitle(__VLS_ctx.selectedRadarMetric));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.radarMetricSummary(__VLS_ctx.selectedRadarMetric));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "detail-kv-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.value ?? __VLS_ctx.selectedRadarMetric.current_value));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.metric_score));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.metric_effective_score));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.quality_score));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "detail-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.evidenceSourceLine(__VLS_ctx.selectedRadarMetric));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.evidenceFreshnessLine(__VLS_ctx.selectedRadarMetric));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.horizon_tags));
            (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.duplicate_group_id));
            if (__VLS_ctx.selectedRadarMetric.positioning_signal || __VLS_ctx.selectedRadarMetric.crowding_contribution || __VLS_ctx.selectedRadarMetric.positioning_scope) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.positioning_signal));
                (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.crowding_contribution));
                (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.positioning_scope));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.isDerivativesCrowdingModule(__VLS_ctx.selectedRadarModule) && ['btc_funding_rate', 'btc_open_interest'].includes(__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.metric_id))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            }
            if (__VLS_ctx.selectedRadarMetric.price_response_state || __VLS_ctx.selectedRadarMetric.flow_price_efficiency_state || __VLS_ctx.selectedRadarMetric.price_response_source) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.price_response_state));
                (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.price_response_confidence));
                (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.flow_price_efficiency_state));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.price_response_source));
            }
            if (__VLS_ctx.multiSourceConflictRows.some((row) => __VLS_ctx.conflictMetricId(row) === __VLS_ctx.text(__VLS_ctx.selectedRadarMetric.metric_id))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                for (const [row] of __VLS_getVForSourceType((__VLS_ctx.multiSourceConflictRows.filter((item) => __VLS_ctx.conflictMetricId(item) === __VLS_ctx.text(__VLS_ctx.selectedRadarMetric.metric_id)).slice(0, 2)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                        key: (`${__VLS_ctx.conflictMetricId(row)}-${__VLS_ctx.text(row.conflict_origin)}`),
                    });
                    (__VLS_ctx.conflictTypeLabel(row));
                    (__VLS_ctx.conflictSelectedSource(row));
                    (__VLS_ctx.conflictImpactText(row));
                }
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "detail-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "article-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!(__VLS_ctx.state.selectedRadarDetail))
                            return;
                        __VLS_ctx.openSelectedRadarEvidence(__VLS_ctx.selectedRadarMetric);
                    } },
                ...{ class: "small-link" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!(__VLS_ctx.state.selectedRadarDetail))
                            return;
                        __VLS_ctx.openSourceDetail(String(__VLS_ctx.selectedRadarMetric.source_id));
                    } },
                ...{ class: "small-link" },
            });
            if (__VLS_ctx.selectedRadarMetric.fallback_used || __VLS_ctx.selectedRadarMetric.is_stale || __VLS_ctx.selectedRadarMetric.available === false) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                    ...{ class: "detail-section warning" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.fallback_used));
                (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.is_stale));
                (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.available));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(__VLS_ctx.selectedRadarMetric.fallback_reason, 'No fallback reason'));
            }
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "empty-note" },
            });
        }
        if (__VLS_ctx.selectedRadarMetrics.length) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "radar-audit-table" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.selectedRadarMetrics.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "table-scroll" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.table, __VLS_intrinsicElements.table)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.thead, __VLS_intrinsicElements.thead)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.tbody, __VLS_intrinsicElements.tbody)({});
            for (const [metric] of __VLS_getVForSourceType((__VLS_ctx.selectedRadarMetrics))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!(__VLS_ctx.selectedRadarMetrics.length))
                                return;
                            __VLS_ctx.selectRadarMetric(metric);
                        } },
                    key: (__VLS_ctx.text(metric.evidence_id ?? metric.metric_id)),
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
                (__VLS_ctx.metricLabel(metric.metric_id));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
                (__VLS_ctx.text(metric.direction));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
                (__VLS_ctx.text(metric.value ?? metric.current_value));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
                (__VLS_ctx.text(metric.metric_effective_score ?? metric.metric_score));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
                (__VLS_ctx.text(metric.quality_score));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
                (__VLS_ctx.text(metric.source_id));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
                (__VLS_ctx.radarMetricSummary(metric));
            }
        }
    }
    else if (__VLS_ctx.activePage === 'evidence') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel evidence-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.filteredEvidenceItems.length);
        (__VLS_ctx.evidenceStats.total);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill bull" },
        });
        (__VLS_ctx.evidenceStats.positive);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill bear" },
        });
        (__VLS_ctx.evidenceStats.negative);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill neutral" },
        });
        (__VLS_ctx.evidenceStats.zero);
        if (__VLS_ctx.evidenceStats.fallback) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill quality" },
            });
            (__VLS_ctx.evidenceStats.fallback);
        }
        if (__VLS_ctx.evidenceStats.stale) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill quality" },
            });
            (__VLS_ctx.evidenceStats.stale);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "article-meta-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.evidenceRunLineage.collect_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.evidenceRunLineage.p2_radar_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.evidenceRunLineage.p3_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.evidenceRunLineage.pack_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.evidenceRunLineage.final_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.evidenceRunLineage.runtime_mode));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "evidence-toolbar" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
            value: (__VLS_ctx.evidenceModuleFilter),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "all",
        });
        for (const [moduleId] of __VLS_getVForSourceType((__VLS_ctx.evidenceModules))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                key: (moduleId),
                value: (moduleId),
            });
            (moduleId);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
            value: (__VLS_ctx.evidenceBucketFilter),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "all",
        });
        for (const [bucket] of __VLS_getVForSourceType((__VLS_ctx.evidenceBuckets))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                key: (bucket),
                value: (bucket),
            });
            (bucket);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    __VLS_ctx.evidenceModuleFilter = 'all';
                    __VLS_ctx.evidenceBucketFilter = 'all';
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    __VLS_ctx.navigateTo('conflict');
                } },
        });
        (__VLS_ctx.conflictStats.total);
        if (__VLS_ctx.multiSourceConflictRows.length) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "conflict-strip" },
            });
            for (const [row] of __VLS_getVForSourceType((__VLS_ctx.multiSourceConflictRows.slice(0, 3)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!(__VLS_ctx.multiSourceConflictRows.length))
                                return;
                            __VLS_ctx.openConflictEvidence(row);
                        } },
                    key: (`evidence-conflict-${__VLS_ctx.conflictMetricId(row)}-${__VLS_ctx.text(row.conflict_origin)}`),
                    ...{ class: "conflict-mini-card" },
                    ...{ class: (__VLS_ctx.conflictSeverityClass(row)) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.metricLabel(__VLS_ctx.conflictMetricId(row)));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.conflictTypeLabel(row));
                (__VLS_ctx.conflictSelectedSource(row));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.conflictImpactText(row));
            }
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "evidence-layout" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "evidence-list" },
        });
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.filteredEvidenceItems.slice(0, 120)))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        __VLS_ctx.openEvidenceDetail(String(item.evidence_id));
                    } },
                key: (__VLS_ctx.text(item.evidence_id)),
                ...{ class: "evidence-row" },
                ...{ class: ([__VLS_ctx.directionClass(__VLS_ctx.evidenceDisplayDirection(item)), __VLS_ctx.selectedEvidenceId === __VLS_ctx.text(item.evidence_id) ? 'selected' : '']) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "evidence-row-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.evidenceTitle(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (__VLS_ctx.text(item.radar_module));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "evidence-row-body" },
            });
            (__VLS_ctx.evidenceOneLine(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "evidence-row-meta" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({
                ...{ class: "score-chip" },
                ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.evidenceDisplayDirection(item))) },
            });
            (__VLS_ctx.evidenceDirectionLabel(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.evidenceScoreLine(item));
            if (__VLS_ctx.evidenceCompositeLine(item)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.evidenceCompositeLine(item));
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.evidenceFreshnessLine(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "evidence-row-tags" },
            });
            for (const [badge] of __VLS_getVForSourceType((__VLS_ctx.evidenceBadges(item)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                    key: (`${__VLS_ctx.text(item.evidence_id)}-${badge}`),
                    ...{ class: (__VLS_ctx.evidenceBadgeClass(badge)) },
                });
                (badge);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({
                ...{ class: "evidence-source-line" },
            });
            (__VLS_ctx.text(item.radar_module));
            (__VLS_ctx.text(item.source_id));
        }
    }
    else if (__VLS_ctx.activePage === 'article') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel article-page article-page-v2" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
            ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.articleFinalPayload.final_view ?? __VLS_ctx.state.articles?.final_view)) },
        });
        (__VLS_ctx.finalViewText);
        if (__VLS_ctx.state.routeContext.isHistorical) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (__VLS_ctx.exitArticleHistory) },
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.openAuditReports) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "article-meta-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.articleRunLineage.final_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.articleRunLineage.pack_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.articleRunLineage.article_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.articleRunLineage.llm_research_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.articleRuntimeMode);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.articleStatusText);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "article-layout" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "article-card publish-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-card-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        (__VLS_ctx.articleTitle(__VLS_ctx.articlePublish, 'Publish Article'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill bull" },
        });
        (__VLS_ctx.text(__VLS_ctx.articlePublish.publish_type, 'market_view'));
        for (const [line] of __VLS_getVForSourceType((__VLS_ctx.articleParagraphs(__VLS_ctx.articlePublish, '暂无发文正文')))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                key: (`pub-${line}`),
            });
            (line);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-flags" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.articlePublish.safe_to_publish));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.articlePublish.publish_score));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.articlePublish.reject_reason, 'no reject'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "article-card research-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-card-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        (__VLS_ctx.articleTitle(__VLS_ctx.articleResearch, 'Research Article'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill mixed" },
        });
        for (const [line] of __VLS_getVForSourceType((__VLS_ctx.articleParagraphs(__VLS_ctx.articleResearch, __VLS_ctx.articleText(__VLS_ctx.state.articles?.deterministic_article))))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                key: (`research-${line}`),
            });
            (line);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "article-layout secondary" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "article-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-card-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill quality" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "module-stats" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.articleLlmResearch.provider, 'deepseek'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.articleLlmResearch.model, 'model'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.articleLlmResearch.status, 'pending'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.articleLlmResearch.runtime_mode, 'llm'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.articleTitle(__VLS_ctx.articleLlmResearch, 'LLM appendix'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.details, __VLS_intrinsicElements.details)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.summary, __VLS_intrinsicElements.summary)({});
        for (const [line] of __VLS_getVForSourceType((__VLS_ctx.articleParagraphs(__VLS_ctx.articleLlmResearch.article, '暂无 LLM 附录正文')))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                key: (`llm-${line}`),
            });
            (line);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "article-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-card-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.articleAnalystRows.length);
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.articleAnalystRows))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                key: (__VLS_ctx.text(item.analyst_id)),
                ...{ class: "analyst-row" },
                ...{ class: (__VLS_ctx.directionClass(item.direction_view ?? item.status)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(item.analyst_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(item.status));
            (__VLS_ctx.text(item.provider, 'deterministic'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(item.title));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "article-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-card-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.articleEvidenceCitations.length);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "citation-grid" },
        });
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.articleEvidenceCitations))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!(__VLS_ctx.activePage === 'article'))
                            return;
                        __VLS_ctx.openArticleCitation(item.id);
                    } },
                key: (item.id),
                ...{ class: "citation-chip" },
                ...{ class: (__VLS_ctx.directionClass(item.evidence?.direction)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.citationLabel(item.id, item.evidence));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.citationMeta(item.evidence));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "article-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "article-card-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.articleHistoryRows.length);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "history-filter-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.state.routeContext.isHistorical ? 'replay' : 'latest'));
        for (const [row] of __VLS_getVForSourceType((__VLS_ctx.articleHistoryRows))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!(__VLS_ctx.activePage === 'article'))
                            return;
                        __VLS_ctx.openArticleSnapshot(row);
                    } },
                key: (__VLS_ctx.text(row.final_run_id)),
                ...{ class: "snapshot-row" },
                ...{ class: (__VLS_ctx.articleSnapshotClass(row)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(row.title, 'P4.5 Research Article'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.articleSnapshotStatus(row));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            (__VLS_ctx.text(row.final_run_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (__VLS_ctx.text(row.created_at));
        }
    }
    else if (false && __VLS_ctx.activePage === 'article') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel article-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.text(__VLS_ctx.state.articles?.publish_article?.body, '暂无发文正文'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.text(__VLS_ctx.state.articles?.research_article?.executive_summary ?? __VLS_ctx.state.articles?.deterministic_article));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.text(__VLS_ctx.state.articles?.llm_research?.status));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.text(__VLS_ctx.state.articles?.llm_research?.title));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.analystArticles))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                key: (__VLS_ctx.text(item.analyst_id)),
            });
            (__VLS_ctx.text(item.analyst_id));
            (__VLS_ctx.text(item.status));
            (__VLS_ctx.text(item.title));
        }
    }
    else if (__VLS_ctx.activePage === 'eventWatchtower') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel event-watchtower-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head event-page-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
            ...{ class: (__VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level)) },
        });
        (__VLS_ctx.text(__VLS_ctx.eventWindowState.emergency_level, 'none'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    __VLS_ctx.store.runEventWindowOnce();
                } },
            ...{ class: "pill bull" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    __VLS_ctx.store.runEventWindowAuditBundle();
                } },
            ...{ class: "pill" },
        });
        if (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.status) === 'paused_by_user') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.status) === 'paused_by_user'))
                            return;
                        __VLS_ctx.store.resumeEventWindowDaemon();
                    } },
                ...{ class: "pill bull" },
            });
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.status) === 'paused_by_user'))
                            return;
                        __VLS_ctx.store.pauseEventWindowDaemon();
                    } },
                ...{ class: "pill mixed" },
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.nav, __VLS_intrinsicElements.nav)({
            ...{ class: "event-watch-tabs" },
            'aria-label': "Event Watchtower sections",
        });
        for (const [tab] of __VLS_getVForSourceType((__VLS_ctx.eventWatchtowerTabs))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        __VLS_ctx.eventWatchtowerTab = tab.id;
                    } },
                key: (tab.id),
                ...{ class: "event-watch-tab" },
                ...{ class: ({ active: __VLS_ctx.eventWatchtowerTab === tab.id }) },
            });
            (tab.label);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "event-status-strip" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "event-stat-card" },
            ...{ class: (__VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.eventWindowState.emergency_level, 'none'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.eventWindowState.event_window_state, 'calendar_monitor'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "event-stat-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.ordinary_radar_trust, 'normal'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.confidence_cap, 'none'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "event-stat-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.trade_permission_modifier, 'none'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.eventWindowDirectScoreImpact);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "event-stat-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.eventWindowActive.event_type, 'event'));
        (__VLS_ctx.daysText(Number(__VLS_ctx.eventWindowActive.time_to_event_sec ?? 0) / 86400));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.eventWindowActive.title, 'Calendar monitor'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "event-stat-card" },
            ...{ class: (__VLS_ctx.daemonHealthTone(__VLS_ctx.eventWindowDaemonHealthState)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.eventWindowDaemonHealthState);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.last_tick_age_sec ?? __VLS_ctx.eventWindowDaemon.last_snapshot_age_sec, '-'));
        (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.runtime_code_version, 'event_watchtower.v3'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "event-stat-card" },
            ...{ class: (__VLS_ctx.marketReturnTone(__VLS_ctx.eventWindowMarketReturns['1h'])) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.marketReturnPct(__VLS_ctx.eventWindowMarketReturns['1h']));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.market_probe_age_sec ?? __VLS_ctx.eventWindowMarketProbe.freshness_sec, '-'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "event-stat-card" },
            ...{ class: (__VLS_ctx.sourceModeTone(__VLS_ctx.eventWindowSourceMode)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.eventWindowSourceMode);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.eventWindowSourceQuality.functional_live ? 'functional live' : 'capability limited');
        (__VLS_ctx.eventWindowSourceCounts.live);
        (__VLS_ctx.eventWindowSourceCounts.partial);
        (__VLS_ctx.eventWindowSourceCounts.fallback);
        (__VLS_ctx.eventWindowSourceCounts.failed);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "event-visibility-controls" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(__VLS_ctx.eventWatchtowerPayload.snapshot_id, '-'));
        (__VLS_ctx.text(__VLS_ctx.eventWindowState.valid_until, '-'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "event-visibility-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.ackCurrentEventAlert) },
            ...{ class: "event-action-button bull" },
            disabled: (__VLS_ctx.eventCurrentAlertAcked),
        });
        (__VLS_ctx.eventCurrentAlertAcked ? 'Acked' : 'Ack current alert');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.dismissEventFloatingAlertSession) },
            ...{ class: "event-action-button mixed" },
            disabled: (__VLS_ctx.eventCurrentAlertHidden),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.restoreEventWindowHiddenAlerts) },
            ...{ class: "event-action-button" },
            disabled: (!__VLS_ctx.eventWindowHiddenKeys.length && !__VLS_ctx.dismissedCriticalAlertKey && !__VLS_ctx.eventFloatingAlertMuted),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.clearVisibleNonCriticalEventAlerts) },
            ...{ class: "event-action-button" },
            disabled: (__VLS_ctx.eventCriticalLikeActive || __VLS_ctx.eventCurrentAlertHidden),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "event-chip" },
            ...{ class: (__VLS_ctx.eventCurrentAlertAcked ? 'bull' : 'quality') },
        });
        (__VLS_ctx.eventCurrentAlertAcked ? 'yes' : 'no');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "event-chip" },
            ...{ class: (__VLS_ctx.eventCurrentAlertHidden ? 'mixed' : 'quality') },
        });
        (__VLS_ctx.eventCurrentAlertHidden ? 'session' : 'none');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        if (__VLS_ctx.eventWatchtowerTab === 'live') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "event-watchtower-live-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-live-main" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "event-two-panel" },
            });
            if (__VLS_ctx.eventCurrentAlertHidden) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    ...{ class: "event-panel-card event-current-alert event-current-alert-hidden" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill mixed" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                    ...{ class: "event-large-copy" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "event-chip-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "event-chip blue" },
                });
                (__VLS_ctx.text(__VLS_ctx.eventWindowState.event_window_state, 'calendar_monitor'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "event-chip" },
                    ...{ class: (__VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level)) },
                });
                (__VLS_ctx.text(__VLS_ctx.eventWindowState.emergency_level, 'none'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "event-chip" },
                });
                (__VLS_ctx.eventWindowDirectScoreImpact);
            }
            else {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    ...{ class: "event-panel-card event-current-alert" },
                    ...{ class: ([__VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level), { acknowledged: __VLS_ctx.eventCurrentAlertAcked }]) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill" },
                    ...{ class: (__VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level)) },
                });
                (__VLS_ctx.eventCurrentAlertAcked ? 'acked · ' : '');
                (__VLS_ctx.text(__VLS_ctx.eventWindowState.emergency_level, 'none'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                    ...{ class: "event-large-copy" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(__VLS_ctx.eventWindowActive.title, 'Calendar monitor'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.br)({});
                (__VLS_ctx.text(__VLS_ctx.eventWindowSummaryAlert.summary ?? __VLS_ctx.eventWindowSummaryDetail, 'No active high-priority event alert. Ordinary radar trust remains normal.'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "event-chip-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "event-chip blue" },
                });
                (__VLS_ctx.text(__VLS_ctx.eventWindowState.event_window_state, 'calendar_monitor'));
                for (const [code] of __VLS_getVForSourceType((__VLS_ctx.eventWindowReasonCodes.slice(0, 4)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        key: (code),
                        ...{ class: "event-chip mixed" },
                    });
                    (code);
                }
                if (!__VLS_ctx.eventWindowReasonCodes.length) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "event-chip" },
                    });
                }
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "event-chip bull" },
                });
                (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.trade_permission_modifier, 'none'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "event-chip" },
                });
                (__VLS_ctx.text(__VLS_ctx.eventWindowState.valid_until, '-'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "event-chip" },
                });
                (__VLS_ctx.eventWindowDirectScoreImpact);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill blue" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-signal-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowExpectation.expectation_gap, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowExpectation.risk_direction, 'unknown'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({
                ...{ class: "pill mixed" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowExpectation.risk_direction, 'neutral'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-signal-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowExpectation.rate_cut_prob_drift_1d, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowPredictionOdds.status, 'prediction market / proxy'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.rate_probability_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-signal-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowExpectation.expectation_drift_1d, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowSecondaryMesh.status, 'mesh'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-signal-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowExpectation.expectation_drift_3d, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowPredictionOdds.current_odds ?? __VLS_ctx.eventWindowPredictionOdds.odds ?? __VLS_ctx.eventWindowPredictionOdds.rate_cut_probability, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowExpectation.prediction_market_status ?? __VLS_ctx.eventWindowPredictionOdds.status, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "event-two-panel" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-live-list" },
            });
            for (const [event] of __VLS_getVForSourceType((__VLS_ctx.eventWindowCalendar.slice(0, 3)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (__VLS_ctx.text(event.event_id)),
                    ...{ class: "event-live-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.daysText(Number(event.time_to_event_sec ?? __VLS_ctx.eventWindowActive.time_to_event_sec ?? 0) / 86400));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
                (__VLS_ctx.text(event.title, 'Calendar event'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(event.source_tier, 'source'));
                (__VLS_ctx.text(event.event_type, '-'));
                (__VLS_ctx.text(event.phase, 'scheduled'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({
                    ...{ class: "pill" },
                    ...{ class: (__VLS_ctx.alertTone(event.importance)) },
                });
                (__VLS_ctx.text(event.importance, 'monitor'));
            }
            if (!__VLS_ctx.eventWindowCalendar.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "event-empty-state" },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card event-llm-read-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.eventLlmToneClass(__VLS_ctx.selectedEventLlmAnalysis.tone ?? __VLS_ctx.eventWindowSpeechMonitor.tone)) },
            });
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.provider, 'deepseek'));
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.status, 'success'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-llm-kpi-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.tone ?? __VLS_ctx.eventWindowSpeechMonitor.tone, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventLlmConfidence(__VLS_ctx.selectedEventLlmAnalysis));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.policy_relevance ?? __VLS_ctx.eventWindowSpeechMonitor.policy_relevance, 'unknown'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: (__VLS_ctx.eventLlmBoundaryPass(__VLS_ctx.selectedEventLlmAnalysis) ? 'bull' : 'bear') },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventLlmBoundaryPass(__VLS_ctx.selectedEventLlmAnalysis) ? 'pass' : 'guard');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "event-large-copy" },
            });
            (__VLS_ctx.eventLlmSummary(__VLS_ctx.selectedEventLlmAnalysis));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-chip-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip blue" },
            });
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.speaker ?? __VLS_ctx.eventWindowSpeechMonitor.speaker, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.policy_relevance ?? __VLS_ctx.eventWindowSpeechMonitor.policy_relevance, 'unknown'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.eventLlmConfidence(__VLS_ctx.selectedEventLlmAnalysis));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
                ...{ class: (__VLS_ctx.eventLlmToneClass(__VLS_ctx.selectedEventLlmAnalysis.tone ?? __VLS_ctx.eventWindowSpeechMonitor.tone)) },
            });
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.tone ?? __VLS_ctx.eventWindowSpeechMonitor.tone, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.eventWindowDirectScoreImpact);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.eventWindowLlmAnalyses.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            (__VLS_ctx.text(__VLS_ctx.eventWatchtowerPayload.asof_ts, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-stream-list" },
            });
            for (const [item] of __VLS_getVForSourceType((__VLS_ctx.eventWindowTimeline.slice(0, 5)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (`${__VLS_ctx.text(item.type)}-${__VLS_ctx.text(item.ts)}-${__VLS_ctx.text(item.title)}`),
                    ...{ class: "event-stream-item" },
                    ...{ class: (__VLS_ctx.alertTone(item.level)) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(item.ts, '-'));
                (__VLS_ctx.text(item.title, 'event update'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(item.payload?.summary ?? item.payload?.reason_code ?? item.type, '-'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "event-chip" },
                });
                (__VLS_ctx.text(item.level, 'info'));
            }
            if (!__VLS_ctx.eventWindowTimeline.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "event-empty-state" },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card event-control-panel" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.collection_mode, 'standalone_daemon'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-daemon-toolbar" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.eventWatchtowerTab === 'live'))
                            return;
                        __VLS_ctx.store.runEventWindowOnce();
                    } },
                ...{ class: "event-action-button bull" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.eventWatchtowerTab === 'live'))
                            return;
                        __VLS_ctx.store.runEventWindowAuditBundle();
                    } },
                ...{ class: "event-action-button" },
            });
            if (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.status) === 'paused_by_user') {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!(__VLS_ctx.eventWatchtowerTab === 'live'))
                                return;
                            if (!(__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.status) === 'paused_by_user'))
                                return;
                            __VLS_ctx.store.resumeEventWindowDaemon();
                        } },
                    ...{ class: "event-action-button bull" },
                });
            }
            else {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!(__VLS_ctx.eventWatchtowerTab === 'live'))
                                return;
                            if (!!(__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.status) === 'paused_by_user'))
                                return;
                            __VLS_ctx.store.pauseEventWindowDaemon();
                        } },
                    ...{ class: "event-action-button mixed" },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "source-quality-strip" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventWindowDaemonHealthState);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.watchdog?.enabled, 'false'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.last_tick_age_sec, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.market_probe_age_sec, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.scheduler_enabled, 'false'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.cadence_profile, 'balanced'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventWindowNextDueSources.length ? __VLS_ctx.eventWindowNextDueSources.join(', ') : 'none');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowLastRunOnce.snapshot_id, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowAuditBundle.overall_status, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.status_schema_version, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowDaemon.last_snapshot_age_sec, '-'));
            if (__VLS_ctx.eventWindowDaemonStaleReasons.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                    ...{ class: "event-source-note" },
                });
                (__VLS_ctx.eventWindowDaemonStaleReasons.join(', '));
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.aside, __VLS_intrinsicElements.aside)({
                ...{ class: "event-live-side" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.eventWindowShockLane.shock_detected ? __VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level) : 'quality') },
            });
            (__VLS_ctx.eventWindowShockLane.shock_detected ? __VLS_ctx.text(__VLS_ctx.eventWindowShockLane.shock_type, 'shock') : 'none');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "event-large-copy" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.summary, 'No official unscheduled policy shock. source_count below threshold; market stable; BTC move remains within normal event-window volatility.'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-chip-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.confirmation_level, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.source_count, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip bull" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.market_dislocation, 'stable'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.btc_microstructure_confirmation, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.rumor_risk, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip mixed" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockEvidence.primary_window, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockEvidence.primary_return_z, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-market-window-grid" },
            });
            for (const [row] of __VLS_getVForSourceType((__VLS_ctx.eventWindowMarketReturnRows))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    key: (row.window),
                    ...{ class: (__VLS_ctx.marketReturnTone(row.value)) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (row.window);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.marketReturnPct(row.value));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
                (__VLS_ctx.text(row.z, '-'));
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-shock-llm-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.provider, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.status) === 'success' ? 'quality' : 'mixed') },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.status, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.summary_zh, '等待 Shock Fast Lane 生成中文观察。'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.risk_reason_zh, '暂无结构化冲击原因。'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.action_boundary_zh, '只解释事件窗口覆盖层，不改变 BTC 或 radar 分数。'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.boundary_pass, 'pending'));
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.analysis_source, 'live_api'));
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.snapshot_id ?? __VLS_ctx.eventWindowShockLlmAnalysis.source_snapshot_id, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.reaction_state ?? __VLS_ctx.eventWindowPostReaction.followthrough, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.eventWindowPostReaction.event_lock_release_allowed ? 'bull' : 'mixed') },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.event_lock_release_allowed, 'false'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-reaction-list" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-reaction-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            (__VLS_ctx.marketReturnPct(__VLS_ctx.eventWindowPostReaction.btc_return_5m));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.marketReturnTone(__VLS_ctx.eventWindowPostReaction.btc_return_5m)) },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.actual_status, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-reaction-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            (__VLS_ctx.marketReturnPct(__VLS_ctx.eventWindowPostReaction.btc_return_30m));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.eventWindowPostReaction.btc_absorbed_shock ? 'bull' : 'mixed') },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.btc_absorbed_shock, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-reaction-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            (__VLS_ctx.marketReturnPct(__VLS_ctx.eventWindowPostReaction.btc_return_2h));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.marketReturnTone(__VLS_ctx.eventWindowPostReaction.btc_return_2h)) },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.followthrough, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-reaction-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.oi_change, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.funding_rate, '-'));
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.realized_volatility, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.cvd_proxy, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-reaction-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.ofi_proxy, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.event_lock_release_reason, 'post_event_reaction_pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowPostReaction.basis, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.eventCalendarMiniMonthLabel);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-calendar-mini event-calendar-mini-month" },
            });
            for (const [weekday] of __VLS_getVForSourceType((__VLS_ctx.eventCalendarMiniWeekdays))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    key: (weekday),
                    ...{ class: "event-mini-weekday" },
                });
                (weekday);
            }
            for (const [day] of __VLS_getVForSourceType((__VLS_ctx.eventCalendarMiniDays))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    key: (day.key),
                    ...{ class: "event-mini-day" },
                    ...{ class: ([day.tone, { blank: day.isBlank, active: day.isActive, empty: !day.events.length }]) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
                (day.day ?? '');
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (day.labels.length ? day.labels.join('/') : '-');
            }
            if (!__VLS_ctx.eventWindowCalendar.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "event-empty-state" },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card event-summary-widget-large" },
                ...{ class: (__VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level)) },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowState.emergency_level, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "event-large-copy" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowSummarySubtitle, 'Compact summary for existing 预警 / 事件窗口 area.'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-chip-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip mixed" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowActive.event_type, 'event'));
            (__VLS_ctx.daysText(Number(__VLS_ctx.eventWindowActive.time_to_event_sec ?? 0) / 86400));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip blue" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.trade_permission_modifier, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.ordinary_radar_trust, 'normal'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
                ...{ class: (__VLS_ctx.sourceModeTone(__VLS_ctx.eventWindowSourceMode)) },
            });
            (__VLS_ctx.eventWindowSourceMode);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "event-source-note" },
            });
            (__VLS_ctx.eventWindowSourceCounts.live);
            (__VLS_ctx.eventWindowSourceCounts.partial);
            (__VLS_ctx.eventWindowSourceCounts.fallback);
            (__VLS_ctx.eventWindowSourceCounts.failed);
            if (__VLS_ctx.eventWindowDisabledCapabilities.length) {
                (__VLS_ctx.eventWindowDisabledCapabilities.slice(0, 3).join(', '));
            }
            if (__VLS_ctx.eventWindowCalendarFallbackNotice) {
                (__VLS_ctx.eventWindowCalendarFallbackNotice);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ class: "event-action-button bull" },
                disabled: true,
            });
        }
        if (__VLS_ctx.eventWatchtowerTab === 'audit') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "event-audit-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card event-audit-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.sourceModeTone(__VLS_ctx.eventWindowSourceMode)) },
            });
            (__VLS_ctx.eventWindowSourceMode);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-audit-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.eventWatchtowerTab === 'audit'))
                            return;
                        __VLS_ctx.openReport(__VLS_ctx.eventWindowAuditReportLinks[0]);
                    } },
                ...{ class: "event-action-button" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
                ...{ class: (__VLS_ctx.eventAuditStatusTone(__VLS_ctx.eventWindowAuditBundle.overall_status)) },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowAuditBundle.overall_status, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowAuditBundle.snapshot_id ?? __VLS_ctx.eventWatchtowerPayload.snapshot_id, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "source-quality-strip" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventWindowSourceMode);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventWindowSourceCounts.live);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventWindowSourceCounts.partial);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventWindowSourceCounts.fallback);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventWindowSourceCounts.failed);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventWindowDisabledCapabilities.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "provider-mesh-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.calendar_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.actual_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.nowcast_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.consensus_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.fedwatch_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.speech_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.calendar_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.consensus_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.nowcast_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.actual_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.rate_probability_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.prediction_market_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "provider-tier-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.official, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.official_mirror, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.secondary_consensus, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.secondary_calendar, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.prediction_market, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.market_implied_proxy, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.manual_override, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.failed ?? __VLS_ctx.eventWindowProviderTierCounts.missing, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "watch-list compact" },
            });
            for (const [fetch] of __VLS_getVForSourceType((__VLS_ctx.eventWindowSourceFetches.slice(0, 6)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (`audit-${__VLS_ctx.text(fetch.fetch_id)}`),
                    ...{ class: "watch-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(fetch.source_id));
                (__VLS_ctx.text(fetch.status));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(fetch.started_at ?? fetch.last_attempt_at));
                (__VLS_ctx.text(fetch.endpoint_url, '-'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(fetch.error_message || `${__VLS_ctx.text(fetch.parsed_item_count, '0')} parsed`));
            }
            if (!__VLS_ctx.eventWindowSourceFetches.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "event-empty-state" },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "event-source-note" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card event-audit-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level)) },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowState.emergency_level, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-audit-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.eventWatchtowerTab === 'audit'))
                            return;
                        __VLS_ctx.openReport(__VLS_ctx.eventWindowAuditReportLinks[1]);
                    } },
                ...{ class: "event-action-button" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.eventWindowDirectScoreImpact);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
                ...{ class: (__VLS_ctx.eventWindowOverlayForbiddenKeys.length ? 'bear' : 'bull') },
            });
            (__VLS_ctx.eventWindowOverlayForbiddenKeys.length ? __VLS_ctx.eventWindowOverlayForbiddenKeys.join(', ') : 'empty / pass');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "provider-mesh-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowState.event_window_state, 'calendar_monitor'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowState.state_priority, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowState.emergency_level, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowState.valid_until, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.trade_permission_modifier, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.confidence_cap, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.volatility_warning, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.ordinary_radar_trust, 'normal'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-chip-row" },
            });
            for (const [code] of __VLS_getVForSourceType((__VLS_ctx.eventWindowReasonCodes))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    key: (`audit-${code}`),
                    ...{ class: "event-chip mixed" },
                });
                (code);
            }
            if (!__VLS_ctx.eventWindowReasonCodes.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "event-chip" },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-llm-detail-head" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.provider, 'deepseek'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.status, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.tone, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventLlmConfidence(__VLS_ctx.selectedEventLlmAnalysis));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.policy_relevance, 'unknown'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.speaker ?? __VLS_ctx.eventWindowSpeechMonitor.speaker, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.speaker_weight, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: (__VLS_ctx.eventLlmBoundaryPass(__VLS_ctx.selectedEventLlmAnalysis) ? 'bull' : 'bear') },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventLlmBoundaryPass(__VLS_ctx.selectedEventLlmAnalysis));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "event-large-copy" },
            });
            (__VLS_ctx.eventLlmSummary(__VLS_ctx.selectedEventLlmAnalysis));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "event-source-note" },
            });
            (__VLS_ctx.eventWindowLlmViolations.length ? __VLS_ctx.eventWindowLlmViolations.join(', ') : 'none');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card event-audit-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.eventWindowShockLane.shock_detected ? __VLS_ctx.alertTone(__VLS_ctx.eventWindowState.emergency_level) : 'quality') },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.shock_detected, 'false'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-audit-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.eventWatchtowerTab === 'audit'))
                            return;
                        __VLS_ctx.openReport(__VLS_ctx.eventWindowAuditReportLinks[2]);
                    } },
                ...{ class: "event-action-button" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
                ...{ class: (__VLS_ctx.eventAuditStatusTone(__VLS_ctx.eventWindowAuditRegression.overall_status)) },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowAuditRegression.overall_status, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.eventWindowDirectScoreImpact);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "provider-mesh-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.shock_detected, 'false'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.shock_type, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.confirmation_level, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.source_count, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.market_dislocation, 'false'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.btc_microstructure_confirmation, 'false'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.rumor_risk, 'false'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowOverlay.trade_permission_modifier, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-boundary-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: (__VLS_ctx.eventWindowDirectScoreImpact === 'false' ? 'bull' : 'bear') },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: (__VLS_ctx.eventWindowShockLane.rumor_risk && __VLS_ctx.text(__VLS_ctx.eventWindowState.emergency_level) === 'critical' ? 'bear' : 'bull') },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.confirmation_level, '').includes('official') ? 'bull' : 'mixed') },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: (__VLS_ctx.eventWindowShockEvidence.primary_window ? 'bull' : 'mixed') },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: (__VLS_ctx.text(__VLS_ctx.eventWindowAuditRegression.overall_status, 'pending') === 'PASS' ? 'bull' : 'mixed') },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-shock-llm-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.eventAuditStatusTone(__VLS_ctx.eventWindowShockLlmAnalysis.boundary_pass)) },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.boundary_pass, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.summary_zh, '等待 Shock Fast Lane 生成中文观察。'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.risk_reason_zh, '暂无结构化冲击原因。'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLlmAnalysis.action_boundary_zh, '只解释事件窗口覆盖层，不改变 BTC score、radar score 或趋势方向。'));
        }
        if (__VLS_ctx.eventWatchtowerTab === 'history') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "alert-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.sourceModeTone(__VLS_ctx.eventWindowSourceQuality.overall_source_mode)) },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.overall_source_mode, 'partial_live'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "event-source-note" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.confidence_note, 'partial_live is functional for monitoring; missing fields only disable their own calculations.'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-chip-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
                ...{ class: (__VLS_ctx.eventWindowSourceQuality.functional_live ? 'bull' : 'mixed') },
            });
            (__VLS_ctx.eventWindowSourceQuality.functional_live === false ? 'false' : 'true');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
                ...{ class: (__VLS_ctx.eventWindowSourceQuality.blocked ? 'bear' : 'bull') },
            });
            (__VLS_ctx.eventWindowSourceQuality.blocked ? 'true' : 'false');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "source-quality-strip" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.calendar_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.actual_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.nowcast_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.consensus_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.fedwatch_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowSourceQuality.speech_quality, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "event-source-note" },
            });
            if (__VLS_ctx.eventWindowDisabledCapabilities.length) {
                (__VLS_ctx.eventWindowDisabledCapabilities.join(', '));
            }
            else {
            }
        }
        if (__VLS_ctx.eventWatchtowerTab === 'history') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "alert-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.lineage_mode, 'partial_live'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "provider-mesh-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.calendar_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.consensus_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.nowcast_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.actual_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.rate_probability_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderConfidence.prediction_market_confidence, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "provider-tier-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.official, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.official_mirror, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (Number(__VLS_ctx.eventWindowProviderTierCounts.secondary_consensus ?? 0) + Number(__VLS_ctx.eventWindowProviderTierCounts.secondary_calendar ?? 0));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.prediction_market, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowProviderTierCounts.market_implied_proxy, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "event-source-note" },
            });
            (__VLS_ctx.text(__VLS_ctx.eventWindowSecondaryMesh.secondary_calendar_status, 'missing'));
            (__VLS_ctx.text(__VLS_ctx.eventWindowSecondaryMesh.consensus_status, 'missing'));
            (__VLS_ctx.text(__VLS_ctx.eventWindowPredictionOdds.status, 'missing'));
            (__VLS_ctx.text(__VLS_ctx.eventWindowPredictionOdds.market_count, '0'));
        }
        if (__VLS_ctx.eventWatchtowerTab === 'history') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "alert-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.eventWindowSources.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-source-grid" },
            });
            for (const [source] of __VLS_getVForSourceType((__VLS_ctx.eventWindowSources))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (__VLS_ctx.text(source.source_id)),
                    ...{ class: "event-source-item" },
                    ...{ class: (`source-mode-${__VLS_ctx.text(source.source_mode, 'unknown')}`) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(source.source_id));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(source.source_tier, 'tier'));
                (__VLS_ctx.text(source.source_mode, 'unknown'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(source.parsed_item_count, '0'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(source.last_error || source.last_success_at || source.last_attempt_at, '-'));
            }
        }
        if (__VLS_ctx.eventWatchtowerTab === 'history') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "alert-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.eventWindowPersistedScheduler.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-source-grid" },
            });
            for (const [item] of __VLS_getVForSourceType((__VLS_ctx.eventWindowPersistedScheduler))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (__VLS_ctx.text(item.source_group)),
                    ...{ class: "event-source-item" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(item.source_group));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(item.phase, 'normal'));
                (__VLS_ctx.text(item.interval_sec, '-'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(item.last_status, 'pending'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(item.next_due_at, '-'));
                (__VLS_ctx.text(item.last_success_at, '-'));
            }
        }
        if (__VLS_ctx.eventWatchtowerTab === 'history') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "alert-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.eventWindowSourceFetches.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "watch-list compact" },
            });
            for (const [fetch] of __VLS_getVForSourceType((__VLS_ctx.eventWindowSourceFetches.slice(0, 16)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (__VLS_ctx.text(fetch.fetch_id)),
                    ...{ class: "watch-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(fetch.source_id));
                (__VLS_ctx.text(fetch.status));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(fetch.started_at));
                (__VLS_ctx.text(fetch.endpoint_url));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(fetch.error_message || `${__VLS_ctx.text(fetch.parsed_item_count, '0')} parsed`));
            }
        }
        if (__VLS_ctx.eventWatchtowerTab === 'speeches') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "event-watch-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card event-llm-table-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill quality" },
            });
            (__VLS_ctx.eventWindowLlmAnalyses.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-llm-table" },
            });
            for (const [item] of __VLS_getVForSourceType((__VLS_ctx.eventWindowLlmAnalyses))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!(__VLS_ctx.eventWatchtowerTab === 'speeches'))
                                return;
                            __VLS_ctx.selectedEventLlmAnalysisId = __VLS_ctx.text(item.analysis_id);
                        } },
                    key: (__VLS_ctx.text(item.analysis_id)),
                    ...{ class: "event-llm-row" },
                    ...{ class: ({ active: __VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.analysis_id) === __VLS_ctx.text(item.analysis_id) }) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(item.analysis_id).slice(0, 28));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(item.provider, 'deepseek'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(item.status, 'success'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({
                    ...{ class: (__VLS_ctx.eventLlmToneClass(item.tone)) },
                });
                (__VLS_ctx.text(item.tone, 'pending'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.eventLlmConfidence(item));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(item.policy_relevance, 'unknown'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.eventLlmBoundaryPass(item));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.eventLlmSummary(item));
            }
            if (!__VLS_ctx.eventWindowLlmAnalyses.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "event-empty-state" },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "event-panel-card event-llm-detail-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.eventLlmToneClass(__VLS_ctx.selectedEventLlmAnalysis.tone)) },
            });
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.provider, 'deepseek'));
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.status, 'success'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-llm-detail-head" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.tone, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventLlmConfidence(__VLS_ctx.selectedEventLlmAnalysis));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.policy_relevance, 'unknown'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: (__VLS_ctx.eventLlmBoundaryPass(__VLS_ctx.selectedEventLlmAnalysis) ? 'bull' : 'bear') },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventLlmBoundaryPass(__VLS_ctx.selectedEventLlmAnalysis));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "event-large-copy" },
            });
            (__VLS_ctx.eventLlmSummary(__VLS_ctx.selectedEventLlmAnalysis));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-chip-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.text_id, '-'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip" },
            });
            (__VLS_ctx.text(__VLS_ctx.selectedEventLlmAnalysis.analysis_id, '-').slice(0, 32));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "event-chip mixed" },
            });
            (__VLS_ctx.eventWindowDirectScoreImpact);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({
                ...{ class: "event-source-note" },
            });
        }
        if (__VLS_ctx.eventWatchtowerTab === 'shock') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "event-watch-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-watch-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.shock_detected, 'false'));
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.shock_type, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.confirmation_level, 'none'));
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.source_count, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.market_dislocation, 'false'));
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.btc_microstructure_confirmation, 'false'));
            (__VLS_ctx.text(__VLS_ctx.eventWindowShockLane.rumor_risk, 'false'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-watch-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventWindowDirectScoreImpact);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        }
        if (__VLS_ctx.eventWatchtowerTab === 'calendar') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "alert-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.eventWindowCalendar.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "event-grid page-grid" },
            });
            for (const [event] of __VLS_getVForSourceType((__VLS_ctx.eventWindowCalendar))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (__VLS_ctx.text(event.event_id)),
                    ...{ class: "event-card" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(event.event_type));
                (__VLS_ctx.text(event.importance));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(event.title));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(event.release_time ?? event.release_time_utc));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({});
                (__VLS_ctx.text(event.source_tier, 'official'));
                (__VLS_ctx.text(event.source_url, '-'));
            }
        }
        if (__VLS_ctx.eventWatchtowerTab === 'timeline') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "alert-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.eventWindowTimeline.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "watch-list" },
            });
            for (const [item] of __VLS_getVForSourceType((__VLS_ctx.eventWindowTimeline.slice(0, 24)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (`${__VLS_ctx.text(item.type)}-${__VLS_ctx.text(item.ts)}-${__VLS_ctx.text(item.title)}`),
                    ...{ class: "watch-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(item.type));
                (__VLS_ctx.text(item.title));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(item.level));
                (__VLS_ctx.text(item.ts));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(item.payload?.summary ?? item.payload?.reason_code, '-'));
            }
        }
    }
    else if (__VLS_ctx.activePage === 'alerts') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel alerts-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill mixed" },
        });
        (__VLS_ctx.text(__VLS_ctx.state.alerts?.schema_version, 'p3.alerts.v1'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "alert-hero" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-hero-main" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
            ...{ class: (__VLS_ctx.alertTone(__VLS_ctx.topAlert?.level)) },
        });
        (__VLS_ctx.text(__VLS_ctx.topAlert?.level, 'watch'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        (__VLS_ctx.text(__VLS_ctx.topAlert?.title, 'No high-priority alert in this run'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.alertSummaryText);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.cooldownText(__VLS_ctx.topAlert?.cooldown_until));
        (__VLS_ctx.alertUpdatedText(__VLS_ctx.topAlert?.updated_at));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-stat-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.alertStats.total);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.alertStats.critical);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.alertStats.warning);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.alertStats.cooling);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.alertStats.evidence);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.finalViewText);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "lineage-grid compact" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.alertRunLineage.collect_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.alertRunLineage.p2_radar_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.alertRunLineage.p3_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.alertRunLineage.final_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "alert-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.alerts.length);
        if (!__VLS_ctx.alerts.length) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "empty-note" },
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-list-grid" },
        });
        for (const [alert] of __VLS_getVForSourceType((__VLS_ctx.alerts))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        __VLS_ctx.openAlertEvidence(alert);
                    } },
                key: (__VLS_ctx.text(alert.alert_id)),
                ...{ class: "alert-card" },
                ...{ class: (__VLS_ctx.alertTone(alert.level)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(alert.level));
            (__VLS_ctx.text(alert.state));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(alert.title));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(alert.summary));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (__VLS_ctx.cooldownText(alert.cooldown_until));
            (__VLS_ctx.text(alert.evidence_count, '0'));
            (__VLS_ctx.alertUpdatedText(alert.updated_at));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({});
            (__VLS_ctx.text(alert.alert_id));
            (__VLS_ctx.text(alert.run_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({
                ...{ class: "alert-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        __VLS_ctx.openAlertEvidence(alert);
                    } },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        __VLS_ctx.activePage = 'invalidation';
                    } },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        __VLS_ctx.openAlertRunLogs(alert);
                    } },
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "alert-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.invalidationRules.length);
        (__VLS_ctx.confirmationRules.length);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "watch-list" },
        });
        for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.invalidationRules))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        __VLS_ctx.activePage = 'invalidation';
                    } },
                key: (__VLS_ctx.text(rule.rule_id)),
                ...{ class: "watch-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(rule.title ?? rule.rule_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(rule.horizon));
            (__VLS_ctx.ruleAction(rule));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(rule.reason));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            (__VLS_ctx.ruleConditions(rule));
        }
        for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.confirmationRules))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        __VLS_ctx.activePage = 'invalidation';
                    } },
                key: (__VLS_ctx.text(rule.rule_id)),
                ...{ class: "watch-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(rule.title ?? rule.rule_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(rule.horizon));
            (__VLS_ctx.ruleAction(rule));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(rule.reason));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            (__VLS_ctx.ruleConditions(rule));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "alert-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.eventWindowRows.length);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "event-grid page-grid" },
        });
        for (const [event] of __VLS_getVForSourceType((__VLS_ctx.eventWindowRows))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                key: (__VLS_ctx.text(event.row.feature_id ?? event.payload.event_type)),
                ...{ class: "event-card" },
                ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.eventWindow(event.row))) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.eventType(event.row));
            (__VLS_ctx.daysText(event.daysUntil));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.eventName(event.row));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(event.payload.event_datetime));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.eventWindow(event.row));
            (__VLS_ctx.eventAction(event.row));
            (__VLS_ctx.text(event.payload.event_phase));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (__VLS_ctx.eventDailyWatch(event.row));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({});
            (__VLS_ctx.eventSourceStatus(event.row));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "alert-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-action-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    __VLS_ctx.navigateTo('evidence');
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    __VLS_ctx.activePage = 'invalidation';
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    __VLS_ctx.activePage = 'logs';
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "halving-strip wide" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.daysText(__VLS_ctx.halvingStats.days));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.compactNumber(__VLS_ctx.halvingStats.height));
        (__VLS_ctx.compactNumber(__VLS_ctx.halvingStats.blocks));
    }
    else if (__VLS_ctx.activePage === 'invalidation') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.text(__VLS_ctx.state.invalidation?.schema_version, 'p45.invalidation.v1'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "invalidation-hero" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-hero-main" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
            ...{ class: (__VLS_ctx.statusClass(__VLS_ctx.invalidationWorkbench.validation_state)) },
        });
        (__VLS_ctx.text(__VLS_ctx.invalidationWorkbench.validation_state, 'watching'));
        if (__VLS_ctx.hasInvalidationWorkbench) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            (__VLS_ctx.text(__VLS_ctx.invalidationWorkbench.validation_reason, '等待 BTC response / residual 裁决'));
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            (__VLS_ctx.text(__VLS_ctx.decision.conclusion_sentence, '等待 P4.5 final decision'));
        }
        if (__VLS_ctx.hasInvalidationWorkbench) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.text(__VLS_ctx.workbenchCurrentThesis.headline_state, 'neutral'));
            (__VLS_ctx.text(__VLS_ctx.workbenchCurrentThesis.btc_direction, 'neutral'));
            (__VLS_ctx.text(__VLS_ctx.workbenchCurrentThesis.confidence_score, '0'));
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.text(__VLS_ctx.decision.trade_permission, 'watch_only'));
            (__VLS_ctx.text(__VLS_ctx.decision.confidence ?? __VLS_ctx.aggregation.confidence));
            (__VLS_ctx.text(__VLS_ctx.decision.risk_mode, 'risk mode pending'));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-stat-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.workbenchScores.confirmation_score, String(__VLS_ctx.invalidationStats.confirmation)));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.workbenchScores.invalidation_score, String(__VLS_ctx.invalidationStats.invalidation)));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.workbenchScores.conflict_score, '0'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.workbenchScores.trend_acceptance_score, '0'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.workbenchScores.btc_response_score, '0'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.workbenchCurrentThesis.trade_permission, __VLS_ctx.tradePermissionText));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "lineage-grid compact" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.invalidationRunLineage.collect_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.invalidationRunLineage.p2_radar_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.invalidationRunLineage.p3_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.invalidationRunLineage.final_run_id));
        if (__VLS_ctx.hasInvalidationWorkbench) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "workbench-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "workbench-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.workbenchCurrentThesis.btc_direction)) },
            });
            (__VLS_ctx.text(__VLS_ctx.workbenchCurrentThesis.headline_state, 'neutral'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "detail-kv-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.workbenchCurrentThesis.btc_direction, 'neutral'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.workbenchCurrentThesis.trend_quality, 'mixed'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.workbenchCurrentThesis.trade_permission, 'watch_only'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.workbenchCurrentThesis.confidence_score, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "workbench-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.workbenchPriceAcceptance.direction)) },
            });
            (__VLS_ctx.text(__VLS_ctx.workbenchPriceAcceptance.direction, 'neutral'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "detail-kv-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.workbenchPriceAcceptance.score, 'missing'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.workbenchResidual.direction, 'flat'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.workbenchResidual.zscore, 'missing'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.workbenchMicroResponse.liquidity_survival, 'unknown'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "workbench-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.workbenchTriggeredRules.length);
            (__VLS_ctx.workbenchArmedRules.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "detail-kv-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.workbenchTriggeredRules.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.workbenchArmedRules.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.workbenchBlockedRules.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.workbenchEvidenceMatrix.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "invalidation-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "rule-column" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill bull" },
            });
            (__VLS_ctx.workbenchConfirmationLane.length);
            for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.workbenchConfirmationLane))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    key: (__VLS_ctx.text(rule.rule_id)),
                    ...{ class: "rule-card confirm" },
                    ...{ class: (__VLS_ctx.statusClass(rule.status)) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "rule-card-head" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill" },
                    ...{ class: (__VLS_ctx.statusClass(rule.status)) },
                });
                (__VLS_ctx.text(rule.status, 'arming'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(rule.rule_id, 'confirmation_rule'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(rule.progress, '0'));
                (__VLS_ctx.text(rule.target_view, 'watch'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(rule.reason, '等待确认解释'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
                (__VLS_ctx.asList(rule.current_observations).map((item) => __VLS_ctx.text(item)).join(' · ') || 'waiting observations');
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "metric-chip-grid" },
                });
                for (const [moduleId] of __VLS_getVForSourceType((__VLS_ctx.asList(rule.observed_modules).slice(0, 8)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        key: (__VLS_ctx.text(moduleId)),
                        ...{ class: "metric-chip" },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                    (__VLS_ctx.text(moduleId));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                }
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "rule-column" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill bear" },
            });
            (__VLS_ctx.workbenchInvalidationLane.length);
            for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.workbenchInvalidationLane))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    key: (__VLS_ctx.text(rule.rule_id)),
                    ...{ class: "rule-card" },
                    ...{ class: (__VLS_ctx.statusClass(rule.status)) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "rule-card-head" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill" },
                    ...{ class: (__VLS_ctx.statusClass(rule.status)) },
                });
                (__VLS_ctx.text(rule.status, 'arming'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(rule.rule_id, 'invalidation_rule'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(rule.progress, '0'));
                (__VLS_ctx.text(rule.target_view, 'watch'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(rule.reason, '等待反证解释'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
                (__VLS_ctx.asList(rule.missing_evidence).map((item) => __VLS_ctx.text(item)).join(' · ') || 'gates available');
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "metric-chip-grid" },
                });
                for (const [moduleId] of __VLS_getVForSourceType((__VLS_ctx.asList(rule.observed_modules).slice(0, 8)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        key: (__VLS_ctx.text(moduleId)),
                        ...{ class: "metric-chip" },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                    (__VLS_ctx.text(moduleId));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                }
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "quality-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "quality-card wide" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.workbenchEvidenceMatrix.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "workbench-matrix" },
            });
            for (const [item] of __VLS_getVForSourceType((__VLS_ctx.workbenchEvidenceMatrix))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!(__VLS_ctx.hasInvalidationWorkbench))
                                return;
                            __VLS_ctx.selectedModuleId = __VLS_ctx.text(item.module_id);
                        } },
                    key: (__VLS_ctx.text(item.module_id)),
                    ...{ class: "matrix-row" },
                    ...{ class: (__VLS_ctx.statusClass(item.evidence_state)) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(item.module_id));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(item.layer));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(item.evidence_state));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(item.evidence_weight_status, 'weight pending'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(item.btc_implication, 'no implication'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (item.trigger_eligible ? 'trigger eligible' : 'context / gated');
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "quality-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.workbenchTimeline.length);
            for (const [item] of __VLS_getVForSourceType((__VLS_ctx.workbenchTimeline))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    key: (__VLS_ctx.text(item.rule_id)),
                    ...{ class: "watch-row quality-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(item.rule_id));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(item.status));
                (__VLS_ctx.text(item.rule_type));
                (__VLS_ctx.text(item.progress));
            }
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "invalidation-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "rule-column" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.invalidationRules.length);
            for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.invalidationRules))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    key: (__VLS_ctx.text(rule.rule_id)),
                    ...{ class: "rule-card" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "rule-card-head" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill mixed" },
                });
                (__VLS_ctx.text(rule.horizon, 'horizon'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(rule.title ?? rule.rule_id));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.ruleProgress(rule));
                (__VLS_ctx.ruleAction(rule));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(rule.reason, '等待反证解释'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
                (__VLS_ctx.ruleConditions(rule));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "metric-chip-grid" },
                });
                for (const [metricId] of __VLS_getVForSourceType((__VLS_ctx.ruleMetricIds(rule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                        ...{ onClick: (...[$event]) => {
                                if (!!(__VLS_ctx.activePage === 'topology'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'overview'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'radar'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'evidence'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'article'))
                                    return;
                                if (!!(false && __VLS_ctx.activePage === 'article'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'alerts'))
                                    return;
                                if (!(__VLS_ctx.activePage === 'invalidation'))
                                    return;
                                if (!!(__VLS_ctx.hasInvalidationWorkbench))
                                    return;
                                __VLS_ctx.openMetricEvidence(metricId);
                            } },
                        key: (metricId),
                        ...{ class: "metric-chip" },
                        ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.metricEvidence(metricId)?.direction)) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                    (metricId);
                    if (__VLS_ctx.metricEvidence(metricId)) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                        (__VLS_ctx.text(__VLS_ctx.metricEvidence(metricId)?.value ?? __VLS_ctx.metricEvidence(metricId)?.current_value));
                        (__VLS_ctx.text(__VLS_ctx.metricEvidence(metricId)?.metric_score));
                    }
                    else {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                    }
                }
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "rule-column" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.confirmationRules.length);
            for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.confirmationRules))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    key: (__VLS_ctx.text(rule.rule_id)),
                    ...{ class: "rule-card confirm" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "rule-card-head" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill bear" },
                });
                (__VLS_ctx.text(rule.horizon, 'horizon'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(rule.title ?? rule.rule_id));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.ruleProgress(rule));
                (__VLS_ctx.ruleAction(rule));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.text(rule.reason, '等待确认解释'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
                (__VLS_ctx.ruleConditions(rule));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "metric-chip-grid" },
                });
                for (const [metricId] of __VLS_getVForSourceType((__VLS_ctx.ruleMetricIds(rule)))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                        ...{ onClick: (...[$event]) => {
                                if (!!(__VLS_ctx.activePage === 'topology'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'overview'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'radar'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'evidence'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'article'))
                                    return;
                                if (!!(false && __VLS_ctx.activePage === 'article'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                    return;
                                if (!!(__VLS_ctx.activePage === 'alerts'))
                                    return;
                                if (!(__VLS_ctx.activePage === 'invalidation'))
                                    return;
                                if (!!(__VLS_ctx.hasInvalidationWorkbench))
                                    return;
                                __VLS_ctx.openMetricEvidence(metricId);
                            } },
                        key: (metricId),
                        ...{ class: "metric-chip" },
                        ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.metricEvidence(metricId)?.direction)) },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                    (metricId);
                    if (__VLS_ctx.metricEvidence(metricId)) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                        (__VLS_ctx.text(__VLS_ctx.metricEvidence(metricId)?.value ?? __VLS_ctx.metricEvidence(metricId)?.current_value));
                        (__VLS_ctx.text(__VLS_ctx.metricEvidence(metricId)?.metric_score));
                    }
                    else {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                    }
                }
            }
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "alert-action-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    __VLS_ctx.navigateTo('evidence');
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    __VLS_ctx.activePage = 'alerts';
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    __VLS_ctx.activePage = 'logs';
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    __VLS_ctx.activePage = 'overview';
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    }
    else if (__VLS_ctx.activePage === 'quality') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill quality" },
        });
        (__VLS_ctx.text(__VLS_ctx.state.dataQuality?.schema_version, 'p45.data_quality.v1'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "quality-hero" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-hero-main" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
            ...{ class: (__VLS_ctx.statusClass(__VLS_ctx.qualityContract.status)) },
        });
        (__VLS_ctx.text(__VLS_ctx.qualityContract.status, 'unknown'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        (__VLS_ctx.qualityScoreText);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.qualityBoundaryText);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.text(__VLS_ctx.qualityContract.status));
        (__VLS_ctx.text(__VLS_ctx.qualityFreshnessCheck.status, 'pending'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-stat-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.qualityPayload.metric_count ?? __VLS_ctx.dataQuality.metric_count));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.qualityPayload.module_count ?? __VLS_ctx.dataQuality.module_count ?? __VLS_ctx.state.dashboard?.radar_module_count));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.metricCountAudit.collected_metric_count));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.metricCountAudit.scored_evidence_count));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.qualityPayload.unavailable_metric_count ?? __VLS_ctx.evidenceStats.unavailable));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.qualityPayload.missing_freshness_count));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.evidenceStats.fallback);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.evidenceStats.stale);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "lineage-grid compact" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.state.dataQuality?.run_lineage?.collect_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.state.dataQuality?.run_lineage?.p2_radar_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.state.dataQuality?.run_lineage?.p3_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.state.dataQuality?.run_lineage?.final_run_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "quality-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "quality-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
            ...{ class: (__VLS_ctx.statusClass(__VLS_ctx.qualityContract.status)) },
        });
        (__VLS_ctx.text(__VLS_ctx.qualityContract.status));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.text(__VLS_ctx.qualityContract.view_consistency_check?.status, 'view consistency pending'));
        (__VLS_ctx.text(__VLS_ctx.qualityChecks.duplicate_groups_checked));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "quality-check-grid" },
        });
        for (const [row] of __VLS_getVForSourceType((__VLS_ctx.qualityCheckRows()))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                key: (row.key),
                ...{ class: (__VLS_ctx.statusClass(row.value)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (row.key);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(row.value));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "quality-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill quality" },
        });
        (__VLS_ctx.text(__VLS_ctx.qualityFreshnessCheck.status, 'warning'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.qualityBoundaryText);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "detail-kv-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.qualityFreshnessCheck.available_metric_missing_freshness_count, '0'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.qualityFreshnessCheck.unavailable_metric_missing_freshness_count, '0'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.qualityFreshnessCheck.required_for_available_metrics));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.qualityFreshnessCheck.required_for_unavailable_metrics));
        for (const [warning] of __VLS_getVForSourceType((__VLS_ctx.qualityWarnings))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                key: (__VLS_ctx.text(warning.code)),
                ...{ class: "watch-row quality-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.warningSummary(warning));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "quality-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "quality-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.evidenceStats.total);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.metricCountAuditText);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "detail-kv-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.metricCountAudit.collected_metric_count));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.metricCountAudit.scored_evidence_count));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.metricCountAudit.derived_metric_count));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.metricCountAudit.unavailable_metric_count));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "quality-bars" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "bar bull" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({
            ...{ style: ({ width: `${Math.min(100, __VLS_ctx.evidenceStats.positive)}%` }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.evidenceStats.positive);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "bar bear" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({
            ...{ style: ({ width: `${Math.min(100, __VLS_ctx.evidenceStats.negative)}%` }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.evidenceStats.negative);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "bar mixed" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({
            ...{ style: ({ width: `${Math.min(100, __VLS_ctx.evidenceStats.zero)}%` }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.evidenceStats.zero);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "bar quality" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({
            ...{ style: ({ width: `${Math.min(100, __VLS_ctx.evidenceStats.fallback)}%` }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.evidenceStats.fallback);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "quality-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
            ...{ class: (__VLS_ctx.conflictStats.high ? 'bear' : __VLS_ctx.conflictStats.total ? 'mixed' : 'bull') },
        });
        (__VLS_ctx.conflictStats.total);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "detail-kv-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.conflictStats.definition);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.conflictStats.fallback);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.conflictStats.high);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.duplicateGroups.length);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    if (!(__VLS_ctx.activePage === 'quality'))
                        return;
                    __VLS_ctx.navigateTo('conflict');
                } },
            ...{ class: "watch-row quality-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "quality-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.text(__VLS_ctx.sourceHealth.source_count));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.sourceHealthScopeText);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "detail-kv-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.sourceHealth.current_run_failed_count, '0'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.sourceHealth.current_run_warning_count, '0'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.sourceHealth.history_recent_failed_count, '0'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.sourceHealth.recent_failed_scope, 'split'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "source-status-row" },
        });
        for (const [[status, count]] of __VLS_getVForSourceType((Object.entries(__VLS_ctx.sourceStatusCounts)))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                key: (status),
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.sourceStatusClass(status)) },
            });
            (status);
            (__VLS_ctx.text(count));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "manual-source-list" },
        });
        for (const [row] of __VLS_getVForSourceType((__VLS_ctx.semiAutoSources))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                key: (__VLS_ctx.sourceId(row)),
                ...{ class: "manual-source-card" },
                ...{ class: (__VLS_ctx.sourceStatusClass(__VLS_ctx.sourceAuthState(row))) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.sourceId(row));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.sourceAutomationMode(row));
            (__VLS_ctx.sourceAuthState(row));
            (__VLS_ctx.timestampText(__VLS_ctx.sourceLastVerified(row)));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (__VLS_ctx.sourceManualSummary(row));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!(__VLS_ctx.activePage === 'quality'))
                            return;
                        __VLS_ctx.openSourceDetail(__VLS_ctx.sourceId(row));
                    } },
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "source-run-list" },
        });
        for (const [row] of __VLS_getVForSourceType((__VLS_ctx.currentRunWarningRows))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!(__VLS_ctx.activePage === 'quality'))
                            return;
                        __VLS_ctx.openSourceDetail(String(row.source_id));
                    } },
                key: (`warning-${__VLS_ctx.text(row.source_id)}-${__VLS_ctx.text(row.run_id)}`),
                ...{ class: "source-run-row quality" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(row.source_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(row.status));
            (__VLS_ctx.text(row.mode));
            (__VLS_ctx.text(row.run_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (__VLS_ctx.text(row.error_message, 'warning without blocking failure'));
        }
        for (const [row] of __VLS_getVForSourceType((__VLS_ctx.historyFailedRows))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!(__VLS_ctx.activePage === 'quality'))
                            return;
                        __VLS_ctx.openSourceDetail(String(row.source_id));
                    } },
                key: (`history-${__VLS_ctx.text(row.source_id)}-${__VLS_ctx.text(row.run_id)}`),
                ...{ class: "source-run-row" },
                ...{ class: (__VLS_ctx.sourceStatusClass(row.status)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(row.source_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(row.status));
            (__VLS_ctx.text(row.mode));
            (__VLS_ctx.text(row.run_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (__VLS_ctx.text(row.error_message, 'historical failed run'));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "alert-action-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    if (!(__VLS_ctx.activePage === 'quality'))
                        return;
                    __VLS_ctx.navigateTo('evidence');
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    if (!(__VLS_ctx.activePage === 'quality'))
                        return;
                    __VLS_ctx.activePage = 'source';
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    if (!(__VLS_ctx.activePage === 'quality'))
                        return;
                    __VLS_ctx.activePage = 'logs';
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    if (!(__VLS_ctx.activePage === 'quality'))
                        return;
                    __VLS_ctx.activePage = 'overview';
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    }
    else if (__VLS_ctx.activePage === 'source') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel source-detail-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
            ...{ class: (__VLS_ctx.sourceStatusClass(__VLS_ctx.selectedSourceProfile.status)) },
        });
        (__VLS_ctx.text(__VLS_ctx.selectedSourceProfile.status, 'select source'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "source-picker-grid" },
        });
        for (const [sourceId] of __VLS_getVForSourceType((__VLS_ctx.sourceSummary))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'quality'))
                            return;
                        if (!(__VLS_ctx.activePage === 'source'))
                            return;
                        __VLS_ctx.openSourceDetail(sourceId);
                    } },
                key: (sourceId),
                ...{ class: "source-picker" },
                ...{ class: ({ active: sourceId === __VLS_ctx.selectedSourceId }) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (sourceId);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        }
        if (__VLS_ctx.state.selectedSourceDetail) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "source-hero" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.sourceStatusClass(__VLS_ctx.selectedSourceProfile.status)) },
            });
            (__VLS_ctx.text(__VLS_ctx.selectedSourceProfile.status, 'unknown'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            (__VLS_ctx.text(__VLS_ctx.selectedSourceProfile.source_id ?? __VLS_ctx.selectedSourceId));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.text(__VLS_ctx.selectedSourceProfile.name, 'source profile pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.sourceMeaning(__VLS_ctx.latestSourceRun.error_message ?? __VLS_ctx.selectedSourceProfile.status ?? __VLS_ctx.selectedSourceProfile.source_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "alert-stat-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedSourceProfile.method));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedSourceProfile.priority));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedSourceProfile.group_name));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedSourceProfile.fallback_source_id, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.selectedSourceRuns.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.selectedSourceMetrics.length);
        }
        if (__VLS_ctx.state.selectedSourceDetail) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "source-detail-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "quality-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.sourceStatusClass(__VLS_ctx.latestSourceRun.status)) },
            });
            (__VLS_ctx.text(__VLS_ctx.latestSourceRun.status));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "detail-kv-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.latestSourceRun.run_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.latestSourceRun.mode));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.timestampText(__VLS_ctx.latestSourceRun.started_at));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.timestampText(__VLS_ctx.latestSourceRun.completed_at));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.sourceRunDuration(__VLS_ctx.latestSourceRun));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.sourceMeaning(__VLS_ctx.latestSourceRun.error_message ?? __VLS_ctx.latestSourceRun.status));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "source-error-text" },
            });
            (__VLS_ctx.text(__VLS_ctx.latestSourceRun.error_message, 'no latest error message'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "quality-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill quality" },
            });
            (__VLS_ctx.text(__VLS_ctx.selectedSourceMetadata.quality_score, 'q pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "detail-kv-grid" },
            });
            for (const [row] of __VLS_getVForSourceType((__VLS_ctx.freshnessPolicyRows(__VLS_ctx.selectedSourceFreshnessPolicy)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    key: (row.key),
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (row.key.replace(/_/g, ' '));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(row.value));
            }
        }
        if (__VLS_ctx.state.selectedSourceDetail) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "source-detail-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "quality-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.selectedSourceRawObservations.length);
            for (const [raw] of __VLS_getVForSourceType((__VLS_ctx.selectedSourceRawObservations.slice(0, 6)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    key: (`${__VLS_ctx.text(raw.run_id)}-${__VLS_ctx.text(raw.observed_at)}`),
                    ...{ class: "source-run-row" },
                    ...{ class: (__VLS_ctx.sourceStatusClass(raw.status ?? raw.error_message)) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(raw.run_id));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.timestampText(raw.observed_at));
                (__VLS_ctx.text(raw.mode));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
                (Array.isArray(raw.payload_keys) ? raw.payload_keys.join(', ') : __VLS_ctx.text(raw.payload_keys, 'sanitized preview only'));
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "quality-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.selectedSourceMetrics.length);
            for (const [metric] of __VLS_getVForSourceType((__VLS_ctx.selectedSourceMetrics.slice(0, 10)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    key: (`${__VLS_ctx.text(metric.metric_id)}-${__VLS_ctx.text(metric.run_id)}-${__VLS_ctx.text(metric.ts)}`),
                    ...{ class: "source-run-row" },
                    ...{ class: (metric.is_fallback ? 'quality' : __VLS_ctx.sourceStatusClass(metric.run_mode)) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.metricValueText(metric));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(metric.run_mode));
                (__VLS_ctx.timestampText(metric.ts));
                (__VLS_ctx.text(metric.is_fallback));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
                (__VLS_ctx.text(metric.run_id));
            }
        }
        if (__VLS_ctx.state.selectedSourceDetail) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "source-detail-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "quality-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.selectedSourceEvidence.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "source-status-row" },
            });
            for (const [moduleId] of __VLS_getVForSourceType((__VLS_ctx.selectedSourceModules))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    key: (moduleId),
                    ...{ class: "pill" },
                });
                (moduleId);
            }
            for (const [item] of __VLS_getVForSourceType((__VLS_ctx.selectedSourceEvidence.slice(0, 8)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!(__VLS_ctx.state.selectedSourceDetail))
                                return;
                            __VLS_ctx.openSourceEvidenceItem(item);
                        } },
                    key: (__VLS_ctx.text(item.evidence_id ?? item.metric_id)),
                    ...{ class: "source-run-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(item.metric_id));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(item.radar_module));
                (__VLS_ctx.text(item.direction));
                (__VLS_ctx.text(item.metric_effective_score ?? item.metric_score));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
                (__VLS_ctx.text(item.evidence_id));
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "quality-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.sourceStatusClass(__VLS_ctx.sourceAuthState(__VLS_ctx.selectedManualSource))) },
            });
            (__VLS_ctx.sourceAuthState(__VLS_ctx.selectedManualSource));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.sourceManualSummary(__VLS_ctx.selectedManualSource));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "detail-kv-grid manual-kv-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.sourceAutomationMode(__VLS_ctx.selectedManualSource));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.sourceProfileDir(__VLS_ctx.selectedManualSource));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.timestampText(__VLS_ctx.sourceLastVerified(__VLS_ctx.selectedManualSource)));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedManualSource.requires_human_verified_profile ?? __VLS_ctx.isSemiAutomatedSource(__VLS_ctx.selectedManualSource)));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedManualSource.last_error ?? __VLS_ctx.latestSourceRun.error_message, 'none'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.selectedSourceLastCapture.status ?? __VLS_ctx.selectedSourceLastCapture.capture_path ?? __VLS_ctx.selectedSourceLastCapture.updated_at, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "alert-action-grid source-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'quality'))
                            return;
                        if (!(__VLS_ctx.activePage === 'source'))
                            return;
                        if (!(__VLS_ctx.state.selectedSourceDetail))
                            return;
                        __VLS_ctx.openVerifyWindowForSource(__VLS_ctx.text(__VLS_ctx.selectedManualSource.source_id ?? __VLS_ctx.selectedSourceId));
                    } },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'quality'))
                            return;
                        if (!(__VLS_ctx.activePage === 'source'))
                            return;
                        if (!(__VLS_ctx.state.selectedSourceDetail))
                            return;
                        __VLS_ctx.retryCollectForSource(__VLS_ctx.text(__VLS_ctx.selectedManualSource.source_id ?? __VLS_ctx.selectedSourceId));
                    } },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'quality'))
                            return;
                        if (!(__VLS_ctx.activePage === 'source'))
                            return;
                        if (!(__VLS_ctx.state.selectedSourceDetail))
                            return;
                        __VLS_ctx.viewLastCaptureForSource(__VLS_ctx.text(__VLS_ctx.selectedManualSource.source_id ?? __VLS_ctx.selectedSourceId));
                    } },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'quality'))
                            return;
                        if (!(__VLS_ctx.activePage === 'source'))
                            return;
                        if (!(__VLS_ctx.state.selectedSourceDetail))
                            return;
                        __VLS_ctx.activePage = 'logs';
                    } },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "manual-action-result" },
            });
            (__VLS_ctx.sourceActionStatus(__VLS_ctx.selectedSourceActionResult));
        }
    }
    else if (__VLS_ctx.activePage === 'conflict') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel conflict-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
            ...{ class: (__VLS_ctx.conflictStats.high ? 'bear' : __VLS_ctx.conflictStats.total ? 'mixed' : 'bull') },
        });
        (__VLS_ctx.conflictStats.total);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "quality-hero" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-hero-main" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill quality" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        (__VLS_ctx.conflictStats.total);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-stat-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.conflictStats.high);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.conflictStats.fallback);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.conflictStats.definition);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.duplicateGroups.length);
        if (__VLS_ctx.multiSourceConflictRows.length) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "conflict-grid" },
            });
            for (const [row] of __VLS_getVForSourceType((__VLS_ctx.multiSourceConflictRows))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    key: (`${__VLS_ctx.conflictMetricId(row)}-${__VLS_ctx.text(row.conflict_origin)}-${__VLS_ctx.conflictSelectedSource(row)}`),
                    ...{ class: "conflict-card" },
                    ...{ class: (__VLS_ctx.conflictSeverityClass(row)) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "conflict-card-head" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.metricLabel(__VLS_ctx.conflictMetricId(row)));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(row.radar_module ?? row.module_id, 'module pending'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill" },
                    ...{ class: (__VLS_ctx.conflictSeverityClass(row)) },
                });
                (__VLS_ctx.conflictTypeLabel(row));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "detail-kv-grid" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.conflictSelectedSource(row));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(__VLS_ctx.conflictSourceList(row).join(', '), 'none'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(row.source_resolution ?? row.source_resolution_status ?? row.conflict_origin));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(row.quality_score));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(row.metric_score));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(row.metric_effective_score));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.conflictReason(row));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (__VLS_ctx.conflictImpactText(row));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "article-actions" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!(__VLS_ctx.activePage === 'conflict'))
                                return;
                            if (!(__VLS_ctx.multiSourceConflictRows.length))
                                return;
                            __VLS_ctx.openConflictEvidence(row);
                        } },
                    ...{ class: "small-link" },
                    disabled: (!__VLS_ctx.conflictEvidenceId(row)),
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!(__VLS_ctx.activePage === 'conflict'))
                                return;
                            if (!(__VLS_ctx.multiSourceConflictRows.length))
                                return;
                            __VLS_ctx.openConflictRadar(row);
                        } },
                    ...{ class: "small-link" },
                    disabled: (!row.radar_module && !row.module_id),
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!(__VLS_ctx.activePage === 'conflict'))
                                return;
                            if (!(__VLS_ctx.multiSourceConflictRows.length))
                                return;
                            __VLS_ctx.openSourceDetail(__VLS_ctx.conflictSelectedSource(row));
                        } },
                    ...{ class: "small-link" },
                    disabled: (!__VLS_ctx.conflictSelectedSource(row)),
                });
            }
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "empty-note" },
            });
        }
    }
    else if (__VLS_ctx.activePage === 'logs') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel runlogs-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.runAndOpenLogs) },
            ...{ class: "primary" },
            disabled: (__VLS_ctx.state.running),
        });
        (__VLS_ctx.state.running ? 'Running' : 'Run Full Chain');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "run-pipeline-card" },
            ...{ class: ([__VLS_ctx.runHealthClass, { running: __VLS_ctx.state.running }]) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "run-pipeline-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pipeline-eyebrow" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pipeline-live-dot" },
        });
        (__VLS_ctx.runningStageText);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.store.finalRunId.value, '等待 final_run_id'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "run-status-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pipeline-status-pill" },
            ...{ class: (__VLS_ctx.runHealthClass) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({});
        (__VLS_ctx.state.running ? 'Running' : __VLS_ctx.text(__VLS_ctx.latestRun.status, 'Ready'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.store.refreshLatest) },
            disabled: (__VLS_ctx.state.loading || __VLS_ctx.state.running),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.openAuditReports) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "run-pipeline" },
            ...{ style: (__VLS_ctx.pipelineProgressStyle) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "pipeline-track" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "pipeline-line" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "pipeline-progress" },
        });
        if (__VLS_ctx.pipelineActive) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "pipeline-packet-rail" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pipeline-packet" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pipeline-packet" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pipeline-packet" },
            });
        }
        for (const [node] of __VLS_getVForSourceType((__VLS_ctx.pipelineNodes))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'quality'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'source'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'conflict'))
                            return;
                        if (!(__VLS_ctx.activePage === 'logs'))
                            return;
                        __VLS_ctx.openPipelineStage(node);
                    } },
                key: (node.key),
                ...{ class: "pipeline-node" },
                ...{ class: (node.state) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pipeline-core" },
            });
            if (node.state === 'active') {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pipeline-scan-ring" },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (node.code);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (node.icon);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pipeline-label" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (node.label);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            (__VLS_ctx.shortRunId(node.runId));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (node.state);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "pipeline-footer" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.runLlmEnabled ? 'P1 collect -> P2 radar -> P3 scoring -> P4.5 final -> LLM analyst' : 'P1 collect -> P2 radar -> P3 scoring -> P4.5 final');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.runExecutionProfile);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.state.activeRunJob?.llm_status ?? __VLS_ctx.latestRun.llm_status, __VLS_ctx.runLlmEnabled ? __VLS_ctx.pipelineHeartbeatText : 'skipped'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "run-lineage-board" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill mixed" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "route-context-grid compact" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.frozenFinalLineage.final_run_id, 'pending'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.frozenFinalLineage.pack_id, 'pending'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.frozenFinalCreatedAt, 'pending'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.frozenFinalLineage.runtime_mode ?? __VLS_ctx.latestRun.runtime_mode, 'runtime pending'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "run-lineage-grid" },
        });
        for (const [entry] of __VLS_getVForSourceType((__VLS_ctx.runLineageEntries))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (entry.key),
                ...{ class: "lineage-chip" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (entry.key.replace(/_/g, ' '));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            (__VLS_ctx.text(entry.value));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "run-lineage-board" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill bull" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "route-context-grid compact" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.snapshot_id, 'pending'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.health_state, 'unknown'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.runtime_fresh, 'unknown'));
        (__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.source_fresh, 'unknown'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.last_tick_age_sec, '-'));
        if (__VLS_ctx.runWarnings.length || __VLS_ctx.runErrors.length) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "run-issue-grid" },
            });
            if (__VLS_ctx.runWarnings.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    ...{ class: "run-issue-card quality" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                for (const [warning, index] of __VLS_getVForSourceType((__VLS_ctx.runWarnings))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                        key: (`warning-${index}`),
                    });
                    (__VLS_ctx.issueText(warning));
                }
            }
            if (__VLS_ctx.runErrors.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    ...{ class: "run-issue-card bear" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                for (const [error, index] of __VLS_getVForSourceType((__VLS_ctx.runErrors))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                        key: (`error-${index}`),
                    });
                    (__VLS_ctx.issueText(error));
                }
            }
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "stage-grid" },
        });
        for (const [stage] of __VLS_getVForSourceType((__VLS_ctx.stages))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                key: (__VLS_ctx.stageId(stage)),
                ...{ class: "stage-card" },
                ...{ class: (__VLS_ctx.statusClass(stage.status)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "stage-head" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(stage.label));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(stage.status));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            (__VLS_ctx.text(stage.run_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "stage-meta-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.stageId(stage));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.stageUpdatedText(stage));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.stageScope(stage));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.stageNote(stage));
            if (__VLS_ctx.stageNeedsManualAction(stage)) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "stage-action-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill mixed" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'conflict'))
                                return;
                            if (!(__VLS_ctx.activePage === 'logs'))
                                return;
                            if (!(__VLS_ctx.stageNeedsManualAction(stage)))
                                return;
                            __VLS_ctx.openVerifyWindowForSource(__VLS_ctx.stageManualSourceId(stage));
                        } },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'conflict'))
                                return;
                            if (!(__VLS_ctx.activePage === 'logs'))
                                return;
                            if (!(__VLS_ctx.stageNeedsManualAction(stage)))
                                return;
                            __VLS_ctx.retryCollectForSource(__VLS_ctx.stageManualSourceId(stage));
                        } },
                });
            }
            if (__VLS_ctx.stageReport(stage).file_url) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'conflict'))
                                return;
                            if (!(__VLS_ctx.activePage === 'logs'))
                                return;
                            if (!(__VLS_ctx.stageReport(stage).file_url))
                                return;
                            __VLS_ctx.openReport(__VLS_ctx.stageReport(stage));
                        } },
                    ...{ class: "report-link" },
                });
                (__VLS_ctx.stageArtifactLabel(stage));
                (__VLS_ctx.reportSize(__VLS_ctx.stageReport(stage).size_bytes));
            }
            else {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "artifact-pending" },
                });
                (__VLS_ctx.stageArtifactLabel(stage));
            }
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "audit-report-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.auditReports.length);
        for (const [report] of __VLS_getVForSourceType((__VLS_ctx.auditReports))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'quality'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'source'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'conflict'))
                            return;
                        if (!(__VLS_ctx.activePage === 'logs'))
                            return;
                        __VLS_ctx.openReport(report);
                    } },
                key: (__VLS_ctx.text(report.relative_path ?? report.filename)),
                ...{ class: "audit-report-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.reportTitle(report));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.text(report.phase));
            (__VLS_ctx.reportSize(report.size_bytes));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.reportUpdatedText(report));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.text(report.relative_path ?? report.filename));
        }
        if (__VLS_ctx.state.runResult) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "run-result-box" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({});
            (JSON.stringify(__VLS_ctx.state.runResult, null, 2));
        }
    }
    else if (__VLS_ctx.activePage === 'history') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel history-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
            ...{ class: (__VLS_ctx.state.routeContext.isHistorical ? 'quality' : 'mixed') },
        });
        (__VLS_ctx.state.routeContext.isHistorical ? 'historical mode' : 'latest mode');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "history-hero" },
            ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.historyFinal.final_view ?? __VLS_ctx.historyDecision.direction)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill quality" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        (__VLS_ctx.text(__VLS_ctx.historyFinal.final_view_cn ?? __VLS_ctx.historyDecision.direction_cn ?? __VLS_ctx.historyFinal.final_view, '选择一个历史 run'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.text(__VLS_ctx.historyDecision.conclusion_sentence ?? __VLS_ctx.historyResearch.executive_summary ?? __VLS_ctx.historyPublish.body, '从下方快照选择 final_run_id，回放当时的 P4.5 final payload、文章、证据包和审计报告。'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.historyValidityText());
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-stat-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.historyLineage.final_run_id ?? __VLS_ctx.state.routeContext.final_run_id, 'none'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.historyFinal.runtime_mode ?? __VLS_ctx.historyLineage.runtime_mode));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.historyDecision.confidence ?? __VLS_ctx.historyAggregation.confidence));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.historyDecision.trade_permission));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.historyReports.length);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.historyAnalysts.length);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "history-action-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'quality'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'source'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'conflict'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'logs'))
                        return;
                    if (!(__VLS_ctx.activePage === 'history'))
                        return;
                    __VLS_ctx.store.loadHistory(__VLS_ctx.store.finalRunId.value);
                } },
            disabled: (!__VLS_ctx.store.finalRunId.value),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.text(__VLS_ctx.store.finalRunId.value, 'no latest final_run_id'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.exitHistoryReplay) },
            disabled: (!__VLS_ctx.state.routeContext.isHistorical),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'quality'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'source'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'conflict'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'logs'))
                        return;
                    if (!(__VLS_ctx.activePage === 'history'))
                        return;
                    __VLS_ctx.activePage = 'article';
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.activePage === 'topology'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'overview'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'radar'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'evidence'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(false && __VLS_ctx.activePage === 'article'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'alerts'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'invalidation'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'quality'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'source'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'conflict'))
                        return;
                    if (!!(__VLS_ctx.activePage === 'logs'))
                        return;
                    if (!(__VLS_ctx.activePage === 'history'))
                        return;
                    __VLS_ctx.activePage = 'logs';
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "history-layout" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "history-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.articleHistoryRows.length);
        for (const [row] of __VLS_getVForSourceType((__VLS_ctx.articleHistoryRows))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'quality'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'source'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'conflict'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'logs'))
                            return;
                        if (!(__VLS_ctx.activePage === 'history'))
                            return;
                        __VLS_ctx.openHistorySnapshot(row);
                    } },
                key: (__VLS_ctx.text(row.final_run_id)),
                ...{ class: "snapshot-row" },
                ...{ class: (__VLS_ctx.articleSnapshotClass(row)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(row.title, 'P4.5 Research Article'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.articleSnapshotStatus(row));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            (__VLS_ctx.text(row.final_run_id));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (__VLS_ctx.timestampText(row.created_at));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "history-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill" },
        });
        (__VLS_ctx.text(__VLS_ctx.historyPayload.schema_version, 'p45.history.v1'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "lineage-grid compact" },
        });
        for (const [entry] of __VLS_getVForSourceType((__VLS_ctx.historyLineageEntries))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                key: (entry.key),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (entry.key.replace(/_/g, ' '));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            (__VLS_ctx.text(entry.value));
        }
        if (__VLS_ctx.state.routeContext.isHistorical) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "history-layout" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "history-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.historyPublish.publish_type ?? __VLS_ctx.historyFinal.schema_version));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
            (__VLS_ctx.text(__VLS_ctx.historyPublish.title ?? __VLS_ctx.historyResearch.title, 'historical article'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.text(__VLS_ctx.historyPublish.body ?? __VLS_ctx.historyResearch.executive_summary ?? __VLS_ctx.historyResearch.body, 'article body pending in snapshot'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                ...{ class: "history-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill quality" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "detail-kv-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.historyDecision.confidence_level, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.historyAggregation.data_quality_level, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.historyValidityText());
        }
        if (__VLS_ctx.state.routeContext.isHistorical) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "audit-report-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "panel-head" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.historyReports.length);
            for (const [report] of __VLS_getVForSourceType((__VLS_ctx.historyReports))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'conflict'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'logs'))
                                return;
                            if (!(__VLS_ctx.activePage === 'history'))
                                return;
                            if (!(__VLS_ctx.state.routeContext.isHistorical))
                                return;
                            __VLS_ctx.openReport(report);
                        } },
                    key: (__VLS_ctx.text(report.relative_path ?? report.filename)),
                    ...{ class: "audit-report-card" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.reportTitle(report));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.text(report.phase));
                (__VLS_ctx.reportSize(report.size_bytes));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.reportUpdatedText(report));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(report.relative_path ?? report.filename));
            }
        }
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            ...{ class: "panel settings-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel-head" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "history-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.goDashboard) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.store.refreshLatest) },
            disabled: (__VLS_ctx.state.loading),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "settings-hero" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "pill bull" },
        });
        (__VLS_ctx.text(__VLS_ctx.settingsPayload.status, 'ok'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        (__VLS_ctx.text(__VLS_ctx.settingsApp.app_name, 'onlyBTC'));
        (__VLS_ctx.text(__VLS_ctx.settingsApp.environment, 'development'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "detail-kv-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.settingsPayload.schema_version, 'p45.settings.v1'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.settingsPayload.api_schema_version, 'onlybtc.api.v1'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.settingsApp.api_host));
        (__VLS_ctx.text(__VLS_ctx.settingsApp.api_port));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(__VLS_ctx.settingsApp.default_refresh_seconds));
        if (__VLS_ctx.settingsWarnings.length || __VLS_ctx.settingsErrors.length) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "run-issue-grid" },
            });
            if (__VLS_ctx.settingsWarnings.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    ...{ class: "run-issue-card quality" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                for (const [warning, index] of __VLS_getVForSourceType((__VLS_ctx.settingsWarnings))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                        key: (`settings-warning-${index}`),
                    });
                    (__VLS_ctx.issueText(warning));
                }
            }
            if (__VLS_ctx.settingsErrors.length) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    ...{ class: "run-issue-card bear" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                for (const [error, index] of __VLS_getVForSourceType((__VLS_ctx.settingsErrors))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                        key: (`settings-error-${index}`),
                    });
                    (__VLS_ctx.issueText(error));
                }
            }
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "settings-layout" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.nav, __VLS_intrinsicElements.nav)({
            ...{ class: "settings-tabs" },
            'aria-label': "Settings sections",
        });
        for (const [tab] of __VLS_getVForSourceType((__VLS_ctx.settingsTabs))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'quality'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'source'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'conflict'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'logs'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'history'))
                            return;
                        __VLS_ctx.settingsTab = tab.id;
                    } },
                key: (tab.id),
                ...{ class: ({ active: __VLS_ctx.settingsTab === tab.id }) },
            });
            (tab.label);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "settings-panel" },
        });
        if (__VLS_ctx.settingsTab === 'llm') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "settings-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill quality" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-card-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsLlm.p45_research_provider, 'deepseek'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (__VLS_ctx.settingSourceLabel(__VLS_ctx.settingsLlm.p45_research_provider));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsLlm.deepseek_model, 'deepseek-reasoner'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (__VLS_ctx.settingSourceLabel(__VLS_ctx.settingsLlm.deepseek_model));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.settingsLlmRouting.mock_mode_enabled ? 'enabled' : 'disabled');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsLlmRouting.fallback_policy, 'fallback'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsLlmRuntimeDefaults.timeout_seconds, __VLS_ctx.text(__VLS_ctx.settingsLlm.p45_research_timeout_seconds, '180')));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsLlmRuntimeDefaults.max_tokens_per_call, '4096'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsLlmRuntimeDefaults.temperature, '0.2'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsLlmAvailableCount, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title compact-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill quality" },
            });
            (__VLS_ctx.text(__VLS_ctx.settingsLlmProviders.length));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-key-list" },
            });
            for (const [row] of __VLS_getVForSourceType((__VLS_ctx.settingsLlmProviders))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    key: (__VLS_ctx.text(row.provider)),
                    ...{ class: "settings-key-row llm-route-row" },
                    ...{ class: (row.enabled ? 'bull' : 'neutral') },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(row.provider));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(row.model, 'model missing'));
                (row.enabled ? 'enabled' : __VLS_ctx.text(row.disabled_reason, 'disabled'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
                (__VLS_ctx.text(row.base_url, 'base_url missing'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill" },
                });
                (row.api_key_configured ? 'key configured' : 'no key');
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title compact-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.settingsLlmRoutes.length));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-key-list" },
            });
            for (const [row] of __VLS_getVForSourceType((__VLS_ctx.settingsLlmRoutes))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    key: (__VLS_ctx.text(row.agent_id)),
                    ...{ class: "settings-key-row llm-route-row" },
                    ...{ class: (row.enabled_for_llm ? 'bull' : 'mixed') },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(row.agent_label, __VLS_ctx.text(row.agent_id)));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.text(row.settings_field));
                (row.mock_mode_bypasses_provider ? 'mock bypass' : 'real llm');
                __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
                (__VLS_ctx.text(row.provider));
                (__VLS_ctx.text(row.model, 'model missing'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill" },
                });
                (row.enabled_for_llm ? 'ready' : __VLS_ctx.text(row.disabled_reason, 'disabled'));
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-action-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                disabled: true,
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                disabled: true,
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                disabled: true,
            });
        }
        else if (__VLS_ctx.settingsTab === 'keys') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "settings-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill mixed" },
            });
            (__VLS_ctx.text(__VLS_ctx.settingsKeyRows.length));
            if (__VLS_ctx.settingsKeyMessage || __VLS_ctx.settingsKeyError) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "settings-save-status" },
                    ...{ class: ({ bear: __VLS_ctx.settingsKeyError }) },
                });
                (__VLS_ctx.settingsKeyError || __VLS_ctx.settingsKeyMessage);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-key-list" },
            });
            for (const [row] of __VLS_getVForSourceType((__VLS_ctx.settingsKeyRows))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    key: (row.key),
                    ...{ class: "settings-key-row" },
                    ...{ class: (__VLS_ctx.settingsKeyRowClass(row)) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (row.provider);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (row.key);
                (row.scope);
                (row.status);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({
                    ...{ class: "settings-health-line" },
                });
                (__VLS_ctx.providerHealthStatus(row));
                (__VLS_ctx.providerHealthMeta(row));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
                (__VLS_ctx.text(row.masked, __VLS_ctx.maskedSecret(row.enabled)));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
                    ...{ onKeyup: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'conflict'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'logs'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'history'))
                                return;
                            if (!!(__VLS_ctx.settingsTab === 'llm'))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'keys'))
                                return;
                            __VLS_ctx.saveSettingsKey(row);
                        } },
                    type: "password",
                    autocomplete: "off",
                    spellcheck: "false",
                    placeholder: (row.enabled ? 'new key' : 'api key'),
                });
                (__VLS_ctx.settingsKeyInputs[row.key]);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "settings-key-actions" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'conflict'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'logs'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'history'))
                                return;
                            if (!!(__VLS_ctx.settingsTab === 'llm'))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'keys'))
                                return;
                            __VLS_ctx.saveSettingsKey(row);
                        } },
                    disabled: (__VLS_ctx.settingsKeySaving === row.key || !__VLS_ctx.hasSettingsKeyDraft(row.key)),
                });
                (__VLS_ctx.settingsKeySaving === row.key ? 'Saving' : row.enabled ? 'Rotate' : 'Configure');
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'conflict'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'logs'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'history'))
                                return;
                            if (!!(__VLS_ctx.settingsTab === 'llm'))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'keys'))
                                return;
                            __VLS_ctx.testSettingsProvider(row);
                        } },
                    disabled: (__VLS_ctx.settingsProviderTesting === row.providerId || !row.supportsTest),
                });
                (__VLS_ctx.settingsProviderTesting === row.providerId ? 'Testing' : 'Test');
            }
        }
        else if (__VLS_ctx.settingsTab === 'data') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "settings-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.text(__VLS_ctx.sourceSummary.length));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-card-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.sourceHealth.status ?? __VLS_ctx.sourceHealth.overall_status, 'latest'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.qualityContract.freshness_check ? 'enabled' : 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.qualityChecks.duplicate_groups_checked ? 'checked' : 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.sourceSummary.filter((id) => id.includes('playwright')).length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title compact-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill mixed" },
            });
            (__VLS_ctx.semiAutoSources.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-key-list" },
            });
            for (const [row] of __VLS_getVForSourceType((__VLS_ctx.semiAutoSources))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    key: (__VLS_ctx.sourceId(row)),
                    ...{ class: "settings-key-row manual-settings-row" },
                    ...{ class: (__VLS_ctx.sourceStatusClass(__VLS_ctx.sourceAuthState(row))) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.sourceId(row));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.sourceAutomationMode(row));
                (__VLS_ctx.sourceProfileDir(row));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
                (__VLS_ctx.sourceAuthState(row));
                (__VLS_ctx.timestampText(__VLS_ctx.sourceLastVerified(row)));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.activePage === 'topology'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'overview'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'radar'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'evidence'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(false && __VLS_ctx.activePage === 'article'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'alerts'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'invalidation'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'quality'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'source'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'conflict'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'logs'))
                                return;
                            if (!!(__VLS_ctx.activePage === 'history'))
                                return;
                            if (!!(__VLS_ctx.settingsTab === 'llm'))
                                return;
                            if (!!(__VLS_ctx.settingsTab === 'keys'))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'data'))
                                return;
                            __VLS_ctx.openSourceDetail(__VLS_ctx.sourceId(row));
                        } },
                });
            }
        }
        else if (__VLS_ctx.settingsTab === 'radar') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "settings-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
            });
            (__VLS_ctx.store.radarModules.value.length || 14);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-card-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.contract.status, 'unknown'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.topAlert?.level, 'watch'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.invalidationRules.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.confirmationRules.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
        }
        else if (__VLS_ctx.settingsTab === 'run') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "settings-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill" },
                ...{ class: (__VLS_ctx.runHealthClass) },
            });
            (__VLS_ctx.runningStageText);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-card-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsRunDefaults.run_mode, 'live'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsRunDefaults.runtime_mode, 'deterministic'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsRunDefaults.llm_runtime_mode, 'llm'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.store.finalRunId.value, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-action-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (__VLS_ctx.runAndOpenLogs) },
                ...{ class: "primary" },
                disabled: (__VLS_ctx.state.running),
            });
            (__VLS_ctx.state.running ? 'Running' : 'Run Full Chain');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.activePage === 'topology'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'overview'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'radar'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'evidence'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(false && __VLS_ctx.activePage === 'article'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'eventWatchtower'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'alerts'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'invalidation'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'quality'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'source'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'conflict'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'logs'))
                            return;
                        if (!!(__VLS_ctx.activePage === 'history'))
                            return;
                        if (!!(__VLS_ctx.settingsTab === 'llm'))
                            return;
                        if (!!(__VLS_ctx.settingsTab === 'keys'))
                            return;
                        if (!!(__VLS_ctx.settingsTab === 'data'))
                            return;
                        if (!!(__VLS_ctx.settingsTab === 'radar'))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'run'))
                            return;
                        __VLS_ctx.navigateTo('logs');
                    } },
            });
        }
        else if (__VLS_ctx.settingsTab === 'publish') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "settings-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill mixed" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-card-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.decision.trade_permission, 'watch_only'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.articlePublish.safe_to_publish, 'pending'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
        }
        else if (__VLS_ctx.settingsTab === 'storage') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "settings-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill quality" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-card-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.auditReports.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.articleHistoryRows.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
                ...{ class: "settings-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill bull" },
            });
            (__VLS_ctx.text(__VLS_ctx.settingsPayload.status, 'ok'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-card-grid" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsApp.api_host));
            (__VLS_ctx.text(__VLS_ctx.settingsApp.api_port));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.state.errors.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.timestampText(__VLS_ctx.settingsPayload.created_at));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsAudit.event_count, '0'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            (__VLS_ctx.text(__VLS_ctx.settingsAudit.schema_version, 'p10.c06.settings_key_audit.v1'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.text(__VLS_ctx.settingsAudit.log_path, 'logs/settings-key-audit.jsonl'));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-title compact-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "pill quality" },
            });
            (__VLS_ctx.settingsAuditEvents.length);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "settings-key-list" },
            });
            for (const [event] of __VLS_getVForSourceType((__VLS_ctx.settingsAuditEvents))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
                    key: (__VLS_ctx.text(event.event_id)),
                    ...{ class: "settings-key-row llm-route-row" },
                    ...{ class: (__VLS_ctx.text(event.status) === 'failed' ? 'mixed' : 'bull') },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.text(event.action, 'audit'));
                (__VLS_ctx.text(event.status, 'success'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                (__VLS_ctx.timestampText(event.created_at));
                (__VLS_ctx.text(event.actor, 'local_api'));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
                (__VLS_ctx.compactList(event.env_keys, __VLS_ctx.compactList(event.provider_ids, 'settings')));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "pill" },
                });
                (event.redacted ? 'redacted' : 'check');
            }
        }
    }
}
if (__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.aside, __VLS_intrinsicElements.aside)({
        ...{ class: "summary route-drawer" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ class: "panel route-context-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "panel-head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    (__VLS_ctx.pageTitle);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.routeModeLabel);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.drawerOpen = false;
            } },
        ...{ class: "modal-close" },
        'aria-label': "Close context drawer",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "route-context-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.state.routeContext.final_run_id ?? __VLS_ctx.store.runLineage.value.final_run_id));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.state.routeContext.pack_id ?? __VLS_ctx.store.runLineage.value.pack_id));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.state.routeContext.module_id, 'all'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.state.routeContext.evidence_id, 'none'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.state.routeContext.source_id, 'none'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "route-action-row" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.goDashboard) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.togglePageFullscreen) },
        disabled: (!__VLS_ctx.fullscreenPages.has(__VLS_ctx.activePage)),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ class: "panel decision-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "panel-head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill" },
    });
    (__VLS_ctx.text(__VLS_ctx.state.dashboard?.final_view, 'final_view'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "decision-list" },
    });
    for (const [reason, index] of __VLS_getVForSourceType((__VLS_ctx.decisionReasons))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (`${index}-${__VLS_ctx.text(reason)}`),
            ...{ class: "reason" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "num" },
        });
        (index + 1);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(reason));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "panel-head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill mixed" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "runline" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.frozenFinalLineage.collect_run_id));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.frozenFinalLineage.p2_radar_run_id));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.frozenFinalLineage.p3_run_id));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.frozenFinalLineage.final_run_id));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.llm.provider, 'deepseek'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "panel-head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill bull" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "runline" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.snapshot_id));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.health_state, 'unknown'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.runtime_fresh, 'unknown'));
    (__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.source_fresh, 'unknown'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    (__VLS_ctx.text(__VLS_ctx.liveRuntimeFreshness.last_tick_age_sec, '-'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "panel-head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill quality" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "llm-grid" },
    });
    for (const [item] of __VLS_getVForSourceType((__VLS_ctx.analystCards))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (__VLS_ctx.text(item.analyst_id)),
            ...{ class: "llm-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.text(item.analyst_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.text(item.status));
        (__VLS_ctx.text(item.provider ?? __VLS_ctx.llm.provider, 'DeepSeek'));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        (__VLS_ctx.text(item.title, 'evidence cited'));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "quick-links" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.navigateTo('overview');
            } },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.navigateTo('article');
            } },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.navigateTo('radar');
            } },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.navigateTo('evidence');
            } },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.navigateTo('alerts');
            } },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.navigateTo('invalidation');
            } },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.navigateTo('quality');
            } },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.navigateTo('conflict');
            } },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.navigateTo('logs');
            } },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.navigateTo('history');
            } },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.drawerOpen && !__VLS_ctx.pageFullscreen))
                    return;
                __VLS_ctx.navigateTo('settings');
            } },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.openAuditReports) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
if (__VLS_ctx.activePage === 'evidence' && __VLS_ctx.state.selectedEvidenceDetail) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (__VLS_ctx.closeEvidenceDetail) },
        ...{ class: "modal-backdrop" },
        role: "presentation",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.aside, __VLS_intrinsicElements.aside)({
        ...{ class: "evidence-modal" },
        role: "dialog",
        'aria-modal': "true",
        'aria-label': "Evidence detail",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "detail-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    (__VLS_ctx.evidenceTitle(__VLS_ctx.selectedEvidence));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.closeEvidenceDetail) },
        ...{ class: "modal-close" },
        'aria-label': "Close evidence detail",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-headline" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({
        ...{ class: "evidence-id" },
    });
    (__VLS_ctx.selectedEvidenceId);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "pill" },
        ...{ class: (__VLS_ctx.directionClass(__VLS_ctx.evidenceDisplayDirection(__VLS_ctx.selectedEvidence))) },
    });
    (__VLS_ctx.evidenceDirectionLabel(__VLS_ctx.selectedEvidence));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "detail-brief" },
    });
    (__VLS_ctx.evidenceBrief(__VLS_ctx.selectedEvidence));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "detail-kv-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.value ?? __VLS_ctx.selectedEvidence.current_value));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.metric_self_direction ?? __VLS_ctx.selectedEvidence.direction));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.metric_self_score ?? __VLS_ctx.selectedEvidence.metric_score));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.metric_score));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.metric_effective_score));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.quality_score));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.score_bucket));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.available));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "detail-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.readableMetricText(__VLS_ctx.selectedEvidence.score_reason ?? __VLS_ctx.selectedEvidence.metric_explanation));
    if (__VLS_ctx.evidenceCompositeLine(__VLS_ctx.selectedEvidence)) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.evidenceCompositeLine(__VLS_ctx.selectedEvidence));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.evidenceWeightLine(__VLS_ctx.selectedEvidence));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "detail-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.evidenceSourceLine(__VLS_ctx.selectedEvidence));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.evidenceFreshnessLine(__VLS_ctx.selectedEvidence));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.source_ts));
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.collected_at));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activePage === 'evidence' && __VLS_ctx.state.selectedEvidenceDetail))
                    return;
                __VLS_ctx.openSourceDetail(String(__VLS_ctx.selectedEvidence.source_id));
            } },
        ...{ class: "small-link" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "detail-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.evidenceHorizonLine(__VLS_ctx.selectedEvidence));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.semantic_rule_id));
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.role));
    (__VLS_ctx.text(__VLS_ctx.selectedEvidence.evidence_tier));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "detail-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.text(__VLS_ctx.selectedEvidenceHistory.previous_value));
    (__VLS_ctx.text(__VLS_ctx.selectedEvidenceHistory.change_24h));
    (__VLS_ctx.text(__VLS_ctx.selectedEvidenceHistory.change_7d));
    (__VLS_ctx.text(__VLS_ctx.selectedEvidenceHistory.ma_30d));
    if (__VLS_ctx.selectedEvidence.fallback_used || __VLS_ctx.selectedEvidence.fallback_reason || __VLS_ctx.selectedEvidence.is_stale || __VLS_ctx.selectedEvidence.legacy_future_source_ts) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "detail-section warning" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.text(__VLS_ctx.selectedEvidence.fallback_used));
        (__VLS_ctx.text(__VLS_ctx.selectedEvidence.fallback_reason));
        (__VLS_ctx.text(__VLS_ctx.selectedEvidence.is_stale));
        if (__VLS_ctx.selectedEvidence.freshness_display_note) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.text(__VLS_ctx.selectedEvidence.freshness_display_note));
        }
    }
}
if (__VLS_ctx.state.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "error" },
    });
    (__VLS_ctx.state.error);
}
if (__VLS_ctx.store.hasEndpointErrors.value) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "endpoint-errors" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    for (const [err] of __VLS_getVForSourceType((__VLS_ctx.state.errors))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            key: (`${err.method}-${err.endpoint}-${err.status}`),
        });
        (err.method);
        (err.endpoint);
        (__VLS_ctx.text(err.status));
    }
}
/** @type {__VLS_StyleScopedClasses['shell']} */ ;
/** @type {__VLS_StyleScopedClasses['topbar']} */ ;
/** @type {__VLS_StyleScopedClasses['brand']} */ ;
/** @type {__VLS_StyleScopedClasses['brand-mark']} */ ;
/** @type {__VLS_StyleScopedClasses['ticker']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['run-state-pill']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['run-state-pill']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['updated']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['llm-run-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['linklike']} */ ;
/** @type {__VLS_StyleScopedClasses['event-floating-alert']} */ ;
/** @type {__VLS_StyleScopedClasses['event-floating-icon-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['event-floating-permission']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['event-critical-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['event-critical-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['event-critical-close']} */ ;
/** @type {__VLS_StyleScopedClasses['event-critical-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['event-critical-reasons']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['event-critical-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['event-critical-mock-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['event-critical-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-critical-mock-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['main']} */ ;
/** @type {__VLS_StyleScopedClasses['rail']} */ ;
/** @type {__VLS_StyleScopedClasses['navbtn']} */ ;
/** @type {__VLS_StyleScopedClasses['drawer-reopen']} */ ;
/** @type {__VLS_StyleScopedClasses['fullscreen-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['canvas']} */ ;
/** @type {__VLS_StyleScopedClasses['topology']} */ ;
/** @type {__VLS_StyleScopedClasses['topology-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['layout-reset']} */ ;
/** @type {__VLS_StyleScopedClasses['legend']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['links']} */ ;
/** @type {__VLS_StyleScopedClasses['link']} */ ;
/** @type {__VLS_StyleScopedClasses['node']} */ ;
/** @type {__VLS_StyleScopedClasses['node-tilt']} */ ;
/** @type {__VLS_StyleScopedClasses['node-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['compact-state']} */ ;
/** @type {__VLS_StyleScopedClasses['node-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['node-audit']} */ ;
/** @type {__VLS_StyleScopedClasses['node-score']} */ ;
/** @type {__VLS_StyleScopedClasses['bar']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-node']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-dynamic-shadow']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-head']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-symbol']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-gold-text']} */ ;
/** @type {__VLS_StyleScopedClasses['state']} */ ;
/** @type {__VLS_StyleScopedClasses['score-ring']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-badges']} */ ;
/** @type {__VLS_StyleScopedClasses['status-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['status-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['status-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['status-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['cockpit-readout']} */ ;
/** @type {__VLS_StyleScopedClasses['readout-label']} */ ;
/** @type {__VLS_StyleScopedClasses['readout-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-text']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['mini-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['mini-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['mini-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['mini-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-pair']} */ ;
/** @type {__VLS_StyleScopedClasses['why-strip']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-watch']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bottom-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-row']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-card']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-badges']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-score-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-chain']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-chain']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-chain']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-chain']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-chain']} */ ;
/** @type {__VLS_StyleScopedClasses['driver-line']} */ ;
/** @type {__VLS_StyleScopedClasses['driver-line']} */ ;
/** @type {__VLS_StyleScopedClasses['pressure']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-event-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-widget']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-note']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-kv']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-list']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['halving-strip']} */ ;
/** @type {__VLS_StyleScopedClasses['content-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['event-page-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-hero']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-kvs']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-section']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['driver-column-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['driver-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['driver-row']} */ ;
/** @type {__VLS_StyleScopedClasses['driver-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['pressure']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['driver-row']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-box']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-list']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['data-boundary-strip']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-lineage-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-detail-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-detail-card']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-detail-head']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-badges']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-score-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-chain']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-chain']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-chain']} */ ;
/** @type {__VLS_StyleScopedClasses['horizon-chain']} */ ;
/** @type {__VLS_StyleScopedClasses['driver-block']} */ ;
/** @type {__VLS_StyleScopedClasses['driver-block']} */ ;
/** @type {__VLS_StyleScopedClasses['pressure']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-bullets']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-section']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-detail-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['article-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-module-switch']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-scope-layout']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-scope-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['scope-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['filters']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-scope-svg']} */ ;
/** @type {__VLS_StyleScopedClasses['scope-ring']} */ ;
/** @type {__VLS_StyleScopedClasses['scope-ring']} */ ;
/** @type {__VLS_StyleScopedClasses['scope-ring']} */ ;
/** @type {__VLS_StyleScopedClasses['scope-axis']} */ ;
/** @type {__VLS_StyleScopedClasses['scope-axis']} */ ;
/** @type {__VLS_StyleScopedClasses['scope-scan']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-scope-card-rail']} */ ;
/** @type {__VLS_StyleScopedClasses['left']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-scope-metric-card']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-card-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-score-track']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-center-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['semantic-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-scope-card-rail']} */ ;
/** @type {__VLS_StyleScopedClasses['right']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-scope-metric-card']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-card-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-score-track']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-metric-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['options-volatility-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-policy-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['crypto-breadth-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['macro-radar-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['macro-radar-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['macro-radar-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['macro-radar-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['macro-radar-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['macro-radar-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['macro-radar-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['macro-radar-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['macro-radar-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['macro-radar-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['btc-total-state-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['article-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['small-link']} */ ;
/** @type {__VLS_StyleScopedClasses['small-link']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-note']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-audit-table']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['table-scroll']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['article-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['neutral']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['article-meta-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['conflict-strip']} */ ;
/** @type {__VLS_StyleScopedClasses['conflict-mini-card']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-layout']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-list']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-row']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-row-title']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-row-body']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-row-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['score-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-row-tags']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-source-line']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['article-page']} */ ;
/** @type {__VLS_StyleScopedClasses['article-page-v2']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['article-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['article-meta-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['article-layout']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card']} */ ;
/** @type {__VLS_StyleScopedClasses['publish-card']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['article-flags']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card']} */ ;
/** @type {__VLS_StyleScopedClasses['research-card']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['article-layout']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['module-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['analyst-row']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['citation-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['citation-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card']} */ ;
/** @type {__VLS_StyleScopedClasses['article-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['history-filter-row']} */ ;
/** @type {__VLS_StyleScopedClasses['snapshot-row']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['article-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['event-watchtower-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['event-page-head']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['event-watch-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['event-watch-tab']} */ ;
/** @type {__VLS_StyleScopedClasses['event-status-strip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-visibility-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['event-visibility-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-watchtower-live-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-live-main']} */ ;
/** @type {__VLS_StyleScopedClasses['event-two-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-current-alert']} */ ;
/** @type {__VLS_StyleScopedClasses['event-current-alert-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['event-large-copy']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['blue']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-current-alert']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-large-copy']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['blue']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['blue']} */ ;
/** @type {__VLS_StyleScopedClasses['event-signal-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['event-signal-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-signal-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-signal-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-two-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-live-list']} */ ;
/** @type {__VLS_StyleScopedClasses['event-live-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-llm-read-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-llm-kpi-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-large-copy']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['blue']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-stream-list']} */ ;
/** @type {__VLS_StyleScopedClasses['event-stream-item']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-control-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-daemon-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['source-quality-strip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-note']} */ ;
/** @type {__VLS_StyleScopedClasses['event-live-side']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-large-copy']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-market-window-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-shock-llm-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-reaction-list']} */ ;
/** @type {__VLS_StyleScopedClasses['event-reaction-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-reaction-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-reaction-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-reaction-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-reaction-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-calendar-mini']} */ ;
/** @type {__VLS_StyleScopedClasses['event-calendar-mini-month']} */ ;
/** @type {__VLS_StyleScopedClasses['event-mini-weekday']} */ ;
/** @type {__VLS_StyleScopedClasses['event-mini-day']} */ ;
/** @type {__VLS_StyleScopedClasses['event-empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-summary-widget-large']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-large-copy']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['blue']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-note']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['event-audit-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-audit-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-audit-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['source-quality-strip']} */ ;
/** @type {__VLS_StyleScopedClasses['provider-mesh-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['provider-tier-row']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-list']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-note']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-audit-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-audit-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['provider-mesh-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-llm-detail-head']} */ ;
/** @type {__VLS_StyleScopedClasses['event-large-copy']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-note']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-audit-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-audit-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['event-action-button']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['provider-mesh-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-boundary-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-shock-llm-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-note']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['source-quality-strip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-note']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['provider-mesh-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['provider-tier-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-note']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-item']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-item']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-list']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-watch-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-llm-table-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['event-llm-table']} */ ;
/** @type {__VLS_StyleScopedClasses['event-llm-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['event-panel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-llm-detail-card']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-llm-detail-head']} */ ;
/** @type {__VLS_StyleScopedClasses['event-large-copy']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip-row']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['event-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['event-source-note']} */ ;
/** @type {__VLS_StyleScopedClasses['event-watch-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-watch-card']} */ ;
/** @type {__VLS_StyleScopedClasses['event-watch-card']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['page-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-card']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-list']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['alerts-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-hero']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-hero-main']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-stat-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['lineage-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-note']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-list-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-card']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-list']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['event-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['page-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['event-card']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-action-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['halving-strip']} */ ;
/** @type {__VLS_StyleScopedClasses['wide']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['invalidation-hero']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-hero-main']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-stat-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['lineage-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['workbench-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['workbench-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['workbench-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['workbench-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['invalidation-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-column']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-card']} */ ;
/** @type {__VLS_StyleScopedClasses['confirm']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-chip-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-column']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-card']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-chip-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['wide']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['workbench-matrix']} */ ;
/** @type {__VLS_StyleScopedClasses['matrix-row']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-row']} */ ;
/** @type {__VLS_StyleScopedClasses['invalidation-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-column']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-card']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-chip-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-column']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-card']} */ ;
/** @type {__VLS_StyleScopedClasses['confirm']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-chip-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-action-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-hero']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-hero-main']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-stat-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['lineage-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-check-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-row']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-bars']} */ ;
/** @type {__VLS_StyleScopedClasses['bar']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['bar']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['bar']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['bar']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['watch-row']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-row']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['source-status-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['manual-source-list']} */ ;
/** @type {__VLS_StyleScopedClasses['manual-source-card']} */ ;
/** @type {__VLS_StyleScopedClasses['source-run-list']} */ ;
/** @type {__VLS_StyleScopedClasses['source-run-row']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['source-run-row']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-action-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['source-detail-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['source-picker-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['source-picker']} */ ;
/** @type {__VLS_StyleScopedClasses['source-hero']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-stat-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['source-detail-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['source-error-text']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['source-detail-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['source-run-row']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['source-run-row']} */ ;
/** @type {__VLS_StyleScopedClasses['source-detail-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['source-status-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['source-run-row']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['manual-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-action-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['source-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['manual-action-result']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['conflict-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-hero']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-hero-main']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-stat-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['conflict-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['conflict-card']} */ ;
/** @type {__VLS_StyleScopedClasses['conflict-card-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['article-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['small-link']} */ ;
/** @type {__VLS_StyleScopedClasses['small-link']} */ ;
/** @type {__VLS_StyleScopedClasses['small-link']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-note']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['runlogs-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['run-pipeline-card']} */ ;
/** @type {__VLS_StyleScopedClasses['run-pipeline-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-eyebrow']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-live-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['run-status-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-status-pill']} */ ;
/** @type {__VLS_StyleScopedClasses['run-pipeline']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-track']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-line']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-packet-rail']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-packet']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-packet']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-packet']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-node']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-core']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-scan-ring']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-label']} */ ;
/** @type {__VLS_StyleScopedClasses['pipeline-footer']} */ ;
/** @type {__VLS_StyleScopedClasses['run-lineage-board']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['route-context-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['run-lineage-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['lineage-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['run-lineage-board']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['route-context-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['run-issue-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['run-issue-card']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['run-issue-card']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['stage-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['stage-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stage-head']} */ ;
/** @type {__VLS_StyleScopedClasses['stage-meta-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['stage-action-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['report-link']} */ ;
/** @type {__VLS_StyleScopedClasses['artifact-pending']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-report-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-report-card']} */ ;
/** @type {__VLS_StyleScopedClasses['run-result-box']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['history-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['history-hero']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-stat-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['history-action-row']} */ ;
/** @type {__VLS_StyleScopedClasses['history-layout']} */ ;
/** @type {__VLS_StyleScopedClasses['history-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['snapshot-row']} */ ;
/** @type {__VLS_StyleScopedClasses['history-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['lineage-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['history-layout']} */ ;
/** @type {__VLS_StyleScopedClasses['history-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['history-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-report-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-report-card']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-page']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['history-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-hero']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['run-issue-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['run-issue-card']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['run-issue-card']} */ ;
/** @type {__VLS_StyleScopedClasses['bear']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-layout']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-card-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['compact-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-key-list']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-key-row']} */ ;
/** @type {__VLS_StyleScopedClasses['llm-route-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['compact-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-key-list']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-key-row']} */ ;
/** @type {__VLS_StyleScopedClasses['llm-route-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-action-row']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-save-status']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-key-list']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-key-row']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-health-line']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-key-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-card-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['compact-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-key-list']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-key-row']} */ ;
/** @type {__VLS_StyleScopedClasses['manual-settings-row']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-card-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-card-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-action-row']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-card-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-card-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-card-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['compact-title']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-key-list']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-key-row']} */ ;
/** @type {__VLS_StyleScopedClasses['llm-route-row']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['summary']} */ ;
/** @type {__VLS_StyleScopedClasses['route-drawer']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['route-context-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-close']} */ ;
/** @type {__VLS_StyleScopedClasses['route-context-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['route-action-row']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['decision-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['decision-list']} */ ;
/** @type {__VLS_StyleScopedClasses['reason']} */ ;
/** @type {__VLS_StyleScopedClasses['num']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['mixed']} */ ;
/** @type {__VLS_StyleScopedClasses['runline']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['bull']} */ ;
/** @type {__VLS_StyleScopedClasses['runline']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-head']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['quality']} */ ;
/** @type {__VLS_StyleScopedClasses['llm-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['llm-card']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-links']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-backdrop']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-title']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-close']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-headline']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-id']} */ ;
/** @type {__VLS_StyleScopedClasses['pill']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-brief']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-kv-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['small-link']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-section']} */ ;
/** @type {__VLS_StyleScopedClasses['warning']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['endpoint-errors']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            pages: pages,
            store: store,
            state: state,
            activePage: activePage,
            drawerOpen: drawerOpen,
            pageFullscreen: pageFullscreen,
            selectedModuleId: selectedModuleId,
            selectedEvidenceId: selectedEvidenceId,
            selectedSourceId: selectedSourceId,
            selectedRadarMetricId: selectedRadarMetricId,
            evidenceModuleFilter: evidenceModuleFilter,
            evidenceBucketFilter: evidenceBucketFilter,
            settingsTab: settingsTab,
            settingsKeyInputs: settingsKeyInputs,
            settingsKeySaving: settingsKeySaving,
            settingsProviderTesting: settingsProviderTesting,
            settingsKeyMessage: settingsKeyMessage,
            settingsKeyError: settingsKeyError,
            selectedEventLlmAnalysisId: selectedEventLlmAnalysisId,
            topologyRef: topologyRef,
            btcRef: btcRef,
            eventAlertPosition: eventAlertPosition,
            eventWatchtowerTab: eventWatchtowerTab,
            dismissedCriticalAlertKey: dismissedCriticalAlertKey,
            eventWindowHiddenKeys: eventWindowHiddenKeys,
            decision: decision,
            btcCockpit: btcCockpit,
            radarRuntimeDaemon: radarRuntimeDaemon,
            radarRuntimeHealth: radarRuntimeHealth,
            radarRuntimeCockpit: radarRuntimeCockpit,
            btcTimescaleJudge: btcTimescaleJudge,
            hasCockpit: hasCockpit,
            aggregation: aggregation,
            contract: contract,
            dataQuality: dataQuality,
            llm: llm,
            horizons: horizons,
            invalidationRules: invalidationRules,
            confirmationRules: confirmationRules,
            alerts: alerts,
            eventWatchtowerPayload: eventWatchtowerPayload,
            eventWindowState: eventWindowState,
            eventWindowOverlay: eventWindowOverlay,
            eventWindowActive: eventWindowActive,
            eventWindowDaemon: eventWindowDaemon,
            eventWindowTimeline: eventWindowTimeline,
            eventWindowCalendar: eventWindowCalendar,
            eventCalendarMiniWeekdays: eventCalendarMiniWeekdays,
            eventCalendarMiniMonthLabel: eventCalendarMiniMonthLabel,
            eventCalendarMiniDays: eventCalendarMiniDays,
            eventWindowSources: eventWindowSources,
            eventWindowSourceFetches: eventWindowSourceFetches,
            eventWindowSourceQuality: eventWindowSourceQuality,
            eventWindowProviderConfidence: eventWindowProviderConfidence,
            eventWindowProviderTierCounts: eventWindowProviderTierCounts,
            eventWindowExpectation: eventWindowExpectation,
            eventWindowPredictionOdds: eventWindowPredictionOdds,
            eventWindowSecondaryMesh: eventWindowSecondaryMesh,
            eventWindowDisabledCapabilities: eventWindowDisabledCapabilities,
            eventWindowSourceMode: eventWindowSourceMode,
            eventWindowCalendarFallbackNotice: eventWindowCalendarFallbackNotice,
            eventWindowSourceCounts: eventWindowSourceCounts,
            eventWindowShockLane: eventWindowShockLane,
            eventWindowShockLlmAnalysis: eventWindowShockLlmAnalysis,
            eventWindowMarketProbe: eventWindowMarketProbe,
            eventWindowMarketReturns: eventWindowMarketReturns,
            eventWindowMarketReturnRows: eventWindowMarketReturnRows,
            eventWindowShockEvidence: eventWindowShockEvidence,
            eventWindowDaemonStaleReasons: eventWindowDaemonStaleReasons,
            eventWindowDaemonHealthState: eventWindowDaemonHealthState,
            eventWindowSummaryAlert: eventWindowSummaryAlert,
            eventWindowSummaryTitle: eventWindowSummaryTitle,
            eventWindowSummarySubtitle: eventWindowSummarySubtitle,
            eventWindowSummaryDetail: eventWindowSummaryDetail,
            eventWindowSummaryAction: eventWindowSummaryAction,
            eventWindowReasonCodes: eventWindowReasonCodes,
            eventWindowPostReaction: eventWindowPostReaction,
            eventWindowSpeechMonitor: eventWindowSpeechMonitor,
            eventWindowLlmAnalyses: eventWindowLlmAnalyses,
            selectedEventLlmAnalysis: selectedEventLlmAnalysis,
            eventWindowDirectScoreImpact: eventWindowDirectScoreImpact,
            eventWindowNextDueSources: eventWindowNextDueSources,
            eventWindowPersistedScheduler: eventWindowPersistedScheduler,
            eventWindowLastRunOnce: eventWindowLastRunOnce,
            eventWindowAuditBundle: eventWindowAuditBundle,
            eventWindowAuditRegression: eventWindowAuditRegression,
            eventWindowOverlayForbiddenKeys: eventWindowOverlayForbiddenKeys,
            eventWindowLlmViolations: eventWindowLlmViolations,
            eventWindowAuditReportLinks: eventWindowAuditReportLinks,
            eventWatchtowerTabs: eventWatchtowerTabs,
            eventCurrentAlertAcked: eventCurrentAlertAcked,
            eventCurrentAlertHidden: eventCurrentAlertHidden,
            eventCriticalLikeActive: eventCriticalLikeActive,
            showEventCriticalOverlay: showEventCriticalOverlay,
            showEventCriticalMockOverlay: showEventCriticalMockOverlay,
            eventFloatingAlertMuted: eventFloatingAlertMuted,
            showEventFloatingAlert: showEventFloatingAlert,
            eventFloatingTitle: eventFloatingTitle,
            eventFloatingSubtitle: eventFloatingSubtitle,
            eventFloatingMessage: eventFloatingMessage,
            eventFloatingAlertStyle: eventFloatingAlertStyle,
            stages: stages,
            auditReports: auditReports,
            latestRun: latestRun,
            frozenFinalLineage: frozenFinalLineage,
            frozenFinalCreatedAt: frozenFinalCreatedAt,
            liveRuntimeFreshness: liveRuntimeFreshness,
            runExecutionProfile: runExecutionProfile,
            runLlmEnabled: runLlmEnabled,
            runWarnings: runWarnings,
            runErrors: runErrors,
            runLineageEntries: runLineageEntries,
            settingsLlm: settingsLlm,
            settingsPayload: settingsPayload,
            settingsApp: settingsApp,
            settingsRunDefaults: settingsRunDefaults,
            settingsLlmRouting: settingsLlmRouting,
            settingsLlmRuntimeDefaults: settingsLlmRuntimeDefaults,
            settingsLlmProviders: settingsLlmProviders,
            settingsLlmRoutes: settingsLlmRoutes,
            settingsLlmAvailableCount: settingsLlmAvailableCount,
            settingsAudit: settingsAudit,
            settingsAuditEvents: settingsAuditEvents,
            settingsWarnings: settingsWarnings,
            settingsErrors: settingsErrors,
            settingsTabs: settingsTabs,
            settingsKeyRows: settingsKeyRows,
            sourceHealth: sourceHealth,
            qualityPayload: qualityPayload,
            metricCountAudit: metricCountAudit,
            qualityContract: qualityContract,
            qualityFreshnessCheck: qualityFreshnessCheck,
            qualityWarnings: qualityWarnings,
            qualityChecks: qualityChecks,
            sourceStatusCounts: sourceStatusCounts,
            currentRunWarningRows: currentRunWarningRows,
            historyFailedRows: historyFailedRows,
            selectedSourceLastCapture: selectedSourceLastCapture,
            selectedSourceActionResult: selectedSourceActionResult,
            selectedSourceProfile: selectedSourceProfile,
            selectedSourceMetadata: selectedSourceMetadata,
            selectedSourceFreshnessPolicy: selectedSourceFreshnessPolicy,
            selectedSourceRuns: selectedSourceRuns,
            selectedSourceRawObservations: selectedSourceRawObservations,
            selectedSourceMetrics: selectedSourceMetrics,
            latestSourceRun: latestSourceRun,
            selectedSourceEvidence: selectedSourceEvidence,
            semiAutoSources: semiAutoSources,
            selectedSourceModules: selectedSourceModules,
            selectedManualSource: selectedManualSource,
            analystArticles: analystArticles,
            selectedRadarModule: selectedRadarModule,
            selectedRadarMetrics: selectedRadarMetrics,
            selectedRadarMetric: selectedRadarMetric,
            selectedRadarMetricStats: selectedRadarMetricStats,
            sourceSummary: sourceSummary,
            duplicateGroups: duplicateGroups,
            multiSourceConflictRows: multiSourceConflictRows,
            conflictStats: conflictStats,
            evidenceRunLineage: evidenceRunLineage,
            selectedEvidence: selectedEvidence,
            selectedEvidenceHistory: selectedEvidenceHistory,
            evidenceModules: evidenceModules,
            evidenceBuckets: evidenceBuckets,
            filteredEvidenceItems: filteredEvidenceItems,
            evidenceStats: evidenceStats,
            topologyModules: topologyModules,
            dynamicLinks: dynamicLinks,
            decisionReasons: decisionReasons,
            finalViewText: finalViewText,
            tradePermissionText: tradePermissionText,
            cockpitHorizon: cockpitHorizon,
            hasRuntimeCockpit: hasRuntimeCockpit,
            cockpitSummaryText: cockpitSummaryText,
            cockpitFastScore: cockpitFastScore,
            cockpitReadoutLabel: cockpitReadoutLabel,
            cockpitFastDirection: cockpitFastDirection,
            cockpitFastStage: cockpitFastStage,
            cockpitPressureText: cockpitPressureText,
            cockpitSupportText: cockpitSupportText,
            cockpitConflictText: cockpitConflictText,
            primaryCockpitTrigger: primaryCockpitTrigger,
            primaryCockpitInvalidation: primaryCockpitInvalidation,
            dataQualityLabel: dataQualityLabel,
            contractStatus: contractStatus,
            alertRunLineage: alertRunLineage,
            alertStats: alertStats,
            qualityScoreText: qualityScoreText,
            qualityBoundaryText: qualityBoundaryText,
            sourceHealthScopeText: sourceHealthScopeText,
            metricCountAuditText: metricCountAuditText,
            alertSummaryText: alertSummaryText,
            scorePercent: scorePercent,
            scoreRingStyle: scoreRingStyle,
            btcNodeClass: btcNodeClass,
            topAlert: topAlert,
            eventWindowRows: eventWindowRows,
            halvingStats: halvingStats,
            runningStageText: runningStageText,
            runHealthClass: runHealthClass,
            pipelineNodes: pipelineNodes,
            pipelineActive: pipelineActive,
            pipelineProgressStyle: pipelineProgressStyle,
            pipelineHeartbeatText: pipelineHeartbeatText,
            analystCards: analystCards,
            articleRunLineage: articleRunLineage,
            articleFinalPayload: articleFinalPayload,
            articleResearch: articleResearch,
            articlePublish: articlePublish,
            articleLlmResearch: articleLlmResearch,
            articleAnalystRows: articleAnalystRows,
            articleHistoryRows: articleHistoryRows,
            historyPayload: historyPayload,
            historyFinal: historyFinal,
            historyDecision: historyDecision,
            historyAggregation: historyAggregation,
            historyLineage: historyLineage,
            historyReports: historyReports,
            historyResearch: historyResearch,
            historyPublish: historyPublish,
            historyAnalysts: historyAnalysts,
            historyLineageEntries: historyLineageEntries,
            articleStatusText: articleStatusText,
            articleRuntimeMode: articleRuntimeMode,
            articleEvidenceCitations: articleEvidenceCitations,
            overviewSupportDrivers: overviewSupportDrivers,
            overviewPressureDrivers: overviewPressureDrivers,
            overviewScoreComponents: overviewScoreComponents,
            overviewScoreNormalization: overviewScoreNormalization,
            overviewRunLineage: overviewRunLineage,
            overviewDataBoundary: overviewDataBoundary,
            overviewWatchRows: overviewWatchRows,
            invalidationRunLineage: invalidationRunLineage,
            invalidationWorkbench: invalidationWorkbench,
            hasInvalidationWorkbench: hasInvalidationWorkbench,
            workbenchCurrentThesis: workbenchCurrentThesis,
            workbenchScores: workbenchScores,
            workbenchPriceAcceptance: workbenchPriceAcceptance,
            workbenchResidual: workbenchResidual,
            workbenchMicroResponse: workbenchMicroResponse,
            workbenchEvidenceMatrix: workbenchEvidenceMatrix,
            workbenchTimeline: workbenchTimeline,
            workbenchTriggeredRules: workbenchTriggeredRules,
            workbenchArmedRules: workbenchArmedRules,
            workbenchBlockedRules: workbenchBlockedRules,
            workbenchConfirmationLane: workbenchConfirmationLane,
            workbenchInvalidationLane: workbenchInvalidationLane,
            invalidationStats: invalidationStats,
            fullscreenPages: fullscreenPages,
            pageTitle: pageTitle,
            routeModeLabel: routeModeLabel,
            pageShellClass: pageShellClass,
            text: text,
            maskedSecret: maskedSecret,
            hasSettingsKeyDraft: hasSettingsKeyDraft,
            settingsKeyRowClass: settingsKeyRowClass,
            saveSettingsKey: saveSettingsKey,
            providerHealthStatus: providerHealthStatus,
            providerHealthMeta: providerHealthMeta,
            testSettingsProvider: testSettingsProvider,
            settingSourceLabel: settingSourceLabel,
            navigateTo: navigateTo,
            goDashboard: goDashboard,
            togglePageFullscreen: togglePageFullscreen,
            articleText: articleText,
            articleParagraphs: articleParagraphs,
            articleTitle: articleTitle,
            citationLabel: citationLabel,
            citationMeta: citationMeta,
            evidenceTitle: evidenceTitle,
            evidenceBrief: evidenceBrief,
            evidenceDisplayDirection: evidenceDisplayDirection,
            evidenceDirectionLabel: evidenceDirectionLabel,
            evidenceCompositeLine: evidenceCompositeLine,
            evidenceOneLine: evidenceOneLine,
            evidenceScoreLine: evidenceScoreLine,
            evidenceFreshnessLine: evidenceFreshnessLine,
            evidenceSourceLine: evidenceSourceLine,
            evidenceHorizonLine: evidenceHorizonLine,
            evidenceBadges: evidenceBadges,
            evidenceBadgeClass: evidenceBadgeClass,
            evidenceWeightLine: evidenceWeightLine,
            openArticleCitation: openArticleCitation,
            openArticleSnapshot: openArticleSnapshot,
            openHistorySnapshot: openHistorySnapshot,
            exitArticleHistory: exitArticleHistory,
            exitHistoryReplay: exitHistoryReplay,
            historyValidityText: historyValidityText,
            articleSnapshotClass: articleSnapshotClass,
            articleSnapshotStatus: articleSnapshotStatus,
            driverReason: driverReason,
            driverContribution: driverContribution,
            openMetricEvidence: openMetricEvidence,
            normalizationText: normalizationText,
            componentPercent: componentPercent,
            ruleSummary: ruleSummary,
            daysText: daysText,
            compactNumber: compactNumber,
            eventType: eventType,
            eventName: eventName,
            eventWindow: eventWindow,
            eventLlmToneClass: eventLlmToneClass,
            sourceModeTone: sourceModeTone,
            daemonHealthTone: daemonHealthTone,
            eventAuditStatusTone: eventAuditStatusTone,
            eventLlmConfidence: eventLlmConfidence,
            eventLlmSummary: eventLlmSummary,
            eventLlmBoundaryPass: eventLlmBoundaryPass,
            eventAction: eventAction,
            eventSourceStatus: eventSourceStatus,
            eventDailyWatch: eventDailyWatch,
            alertTone: alertTone,
            cooldownText: cooldownText,
            ruleAction: ruleAction,
            ruleConditions: ruleConditions,
            ruleMetricIds: ruleMetricIds,
            metricEvidence: metricEvidence,
            ruleProgress: ruleProgress,
            sourceStatusClass: sourceStatusClass,
            sourceMeaning: sourceMeaning,
            freshnessPolicyRows: freshnessPolicyRows,
            sourceId: sourceId,
            sourceAuthState: sourceAuthState,
            sourceAutomationMode: sourceAutomationMode,
            sourceProfileDir: sourceProfileDir,
            sourceLastVerified: sourceLastVerified,
            isSemiAutomatedSource: isSemiAutomatedSource,
            sourceManualSummary: sourceManualSummary,
            sourceActionStatus: sourceActionStatus,
            sourceRunDuration: sourceRunDuration,
            metricValueText: metricValueText,
            qualityCheckRows: qualityCheckRows,
            warningSummary: warningSummary,
            alertUpdatedText: alertUpdatedText,
            openAlertEvidence: openAlertEvidence,
            openAlertRunLogs: openAlertRunLogs,
            statusClass: statusClass,
            shortRunId: shortRunId,
            openPipelineStage: openPipelineStage,
            stageNote: stageNote,
            stageId: stageId,
            stageScope: stageScope,
            stageArtifactLabel: stageArtifactLabel,
            stageNeedsManualAction: stageNeedsManualAction,
            stageManualSourceId: stageManualSourceId,
            stageUpdatedText: stageUpdatedText,
            reportTitle: reportTitle,
            reportSize: reportSize,
            openReport: openReport,
            stageReport: stageReport,
            reportUpdatedText: reportUpdatedText,
            timestampText: timestampText,
            issueText: issueText,
            conflictSeverityClass: conflictSeverityClass,
            conflictTypeLabel: conflictTypeLabel,
            conflictSourceList: conflictSourceList,
            conflictSelectedSource: conflictSelectedSource,
            conflictReason: conflictReason,
            conflictImpactText: conflictImpactText,
            conflictMetricId: conflictMetricId,
            conflictEvidenceId: conflictEvidenceId,
            openConflictEvidence: openConflictEvidence,
            openConflictRadar: openConflictRadar,
            directionClass: directionClass,
            nodeStyle: nodeStyle,
            nodeClass: nodeClass,
            moduleDisplayLabel: moduleDisplayLabel,
            moduleDisplayShortLabel: moduleDisplayShortLabel,
            moduleDisplayClass: moduleDisplayClass,
            moduleName: moduleName,
            shortModuleName: shortModuleName,
            moduleMeta: moduleMeta,
            radarMetricRail: radarMetricRail,
            radarMetricBarWidth: radarMetricBarWidth,
            radarMetricCompactMeta: radarMetricCompactMeta,
            radarMetricClass: radarMetricClass,
            radarMetricSummary: radarMetricSummary,
            hasTradeStructureStates: hasTradeStructureStates,
            tradeStructureStateRows: tradeStructureStateRows,
            isBtcTotalStateModule: isBtcTotalStateModule,
            isDerivativesCrowdingModule: isDerivativesCrowdingModule,
            isTradeStructureFlowModule: isTradeStructureFlowModule,
            derivativesCrowdingLayerCards: derivativesCrowdingLayerCards,
            isOptionsVolatilityModule: isOptionsVolatilityModule,
            isEventPolicyModule: isEventPolicyModule,
            isCryptoBreadthModule: isCryptoBreadthModule,
            isMacroRadarModule: isMacroRadarModule,
            isDollarLiquidityModule: isDollarLiquidityModule,
            isTreasuryCreditModule: isTreasuryCreditModule,
            isFundFlowModule: isFundFlowModule,
            isBtcAdoptionModule: isBtcAdoptionModule,
            isAsiaRiskModule: isAsiaRiskModule,
            isKlineOrderflowModule: isKlineOrderflowModule,
            isOnchainValuationModule: isOnchainValuationModule,
            derivativesCrowdingScopeText: derivativesCrowdingScopeText,
            btcTotalLayerCards: btcTotalLayerCards,
            optionsVolatilityContract: optionsVolatilityContract,
            optionsVolatilityLayerCards: optionsVolatilityLayerCards,
            eventPolicyContract: eventPolicyContract,
            eventPolicyLayerCards: eventPolicyLayerCards,
            cryptoBreadthContract: cryptoBreadthContract,
            cryptoBreadthLayerCards: cryptoBreadthLayerCards,
            macroRadarContract: macroRadarContract,
            macroRadarLayerCards: macroRadarLayerCards,
            dollarLiquidityContract: dollarLiquidityContract,
            dollarLiquidityLayerCards: dollarLiquidityLayerCards,
            treasuryCreditContract: treasuryCreditContract,
            treasuryCreditLayerCards: treasuryCreditLayerCards,
            fundFlowContract: fundFlowContract,
            fundFlowLayerCards: fundFlowLayerCards,
            onchainValuationContract: onchainValuationContract,
            onchainValuationLayerCards: onchainValuationLayerCards,
            btcAdoptionContract: btcAdoptionContract,
            btcAdoptionLayerCards: btcAdoptionLayerCards,
            asiaRiskContract: asiaRiskContract,
            asiaRiskLayerCards: asiaRiskLayerCards,
            klineOrderflowContract: klineOrderflowContract,
            klineOrderflowLayerCards: klineOrderflowLayerCards,
            tradeStructureFlowLayerCards: tradeStructureFlowLayerCards,
            selectRadarMetric: selectRadarMetric,
            openSelectedRadarEvidence: openSelectedRadarEvidence,
            directionText: directionText,
            moduleAuditMeta: moduleAuditMeta,
            resetRadarLayout: resetRadarLayout,
            handleBtcMove: handleBtcMove,
            resetBtcTilt: resetBtcTilt,
            handleRadarNodeMove: handleRadarNodeMove,
            resetRadarNodeTilt: resetRadarNodeTilt,
            startDrag: startDrag,
            dragNode: dragNode,
            stopDrag: stopDrag,
            ackCurrentEventAlert: ackCurrentEventAlert,
            dismissEventFloatingAlertSession: dismissEventFloatingAlertSession,
            clearVisibleNonCriticalEventAlerts: clearVisibleNonCriticalEventAlerts,
            restoreEventWindowHiddenAlerts: restoreEventWindowHiddenAlerts,
            muteEventFloatingAlert: muteEventFloatingAlert,
            expandEventFloatingAlert: expandEventFloatingAlert,
            setEventFloatingAlertHover: setEventFloatingAlertHover,
            resetEventAlertPosition: resetEventAlertPosition,
            startEventAlertDrag: startEventAlertDrag,
            dragEventAlert: dragEventAlert,
            stopEventAlertDrag: stopEventAlertDrag,
            dismissEventCriticalOverlay: dismissEventCriticalOverlay,
            openRadarNode: openRadarNode,
            horizonFullLabel: horizonFullLabel,
            horizonDirection: horizonDirection,
            metricLabel: metricLabel,
            driverMetricId: driverMetricId,
            readableMetricText: readableMetricText,
            asList: asList,
            compactList: compactList,
            marketReturnPct: marketReturnPct,
            marketReturnTone: marketReturnTone,
            horizonConfidence: horizonConfidence,
            horizonScore: horizonScore,
            horizonDisplayScore: horizonDisplayScore,
            horizonSummary: horizonSummary,
            horizonCardClasses: horizonCardClasses,
            horizonFreshnessBadges: horizonFreshnessBadges,
            horizonRadarContext: horizonRadarContext,
            horizonEventTrustCap: horizonEventTrustCap,
            horizonEventPhase: horizonEventPhase,
            horizonBtcAcceptance: horizonBtcAcceptance,
            horizonDirectEvidenceText: horizonDirectEvidenceText,
            horizonConfirmationRules: horizonConfirmationRules,
            horizonInvalidationRules: horizonInvalidationRules,
            horizonWatchRules: horizonWatchRules,
            runAndOpenLogs: runAndOpenLogs,
            openRadarDetail: openRadarDetail,
            openEvidenceDetail: openEvidenceDetail,
            closeEvidenceDetail: closeEvidenceDetail,
            openSourceDetail: openSourceDetail,
            openVerifyWindowForSource: openVerifyWindowForSource,
            retryCollectForSource: retryCollectForSource,
            viewLastCaptureForSource: viewLastCaptureForSource,
            openSourceEvidenceItem: openSourceEvidenceItem,
            openAuditReports: openAuditReports,
            openLlmAppendix: openLlmAppendix,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
