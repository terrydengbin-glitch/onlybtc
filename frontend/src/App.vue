<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from './api'
import { useOnlybtcStore } from './store'

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
] as const
const validPageIds = new Set<string>([
  ...pages.map((page) => page.id),
  'overview',
  'article',
  'invalidation',
  'source',
  'conflict',
])

type PageId =
  | 'topology'
  | 'eventWatchtower'
  | 'overview'
  | 'radar'
  | 'evidence'
  | 'article'
  | 'alerts'
  | 'invalidation'
  | 'quality'
  | 'source'
  | 'conflict'
  | 'logs'
  | 'history'
  | 'settings'
type Row = Record<string, unknown>
type EventCalendarMiniDay = {
  key: string
  day: number | null
  events: Row[]
  primary: Row
  labels: string[]
  tone: string
  isBlank: boolean
  isActive: boolean
}
type LayoutPoint = { x: number; y: number }
type DragState = {
  moduleId: string
  pointerId: number
  target: HTMLElement
  startClientX: number
  startClientY: number
  moved: boolean
}
type FloatingAlertDragState = {
  pointerId: number
  target: HTMLElement
  offsetX: number
  offsetY: number
  startClientX: number
  startClientY: number
  moved: boolean
}

const store = useOnlybtcStore()
const state = store.state
const activePage = ref<PageId>('topology')
const drawerOpen = ref(true)
const pageFullscreen = ref(false)
const selectedModuleId = ref('')
const selectedEvidenceId = ref('')
const selectedSourceId = ref('')
const selectedRadarMetricId = ref('')
const evidenceModuleFilter = ref('all')
const evidenceBucketFilter = ref('all')
const settingsTab = ref('llm')
const settingsKeyInputs = reactive<Record<string, string>>({})
const settingsKeySaving = ref('')
const settingsProviderTesting = ref('')
const settingsKeyMessage = ref('')
const settingsKeyError = ref('')
const selectedEventLlmAnalysisId = ref('')
const topologyRef = ref<HTMLElement | null>(null)
const btcRef = ref<HTMLElement | null>(null)
const radarLayout = reactive<Record<string, LayoutPoint>>({})
const dragging = ref<DragState | null>(null)
const eventAlertDragging = ref<FloatingAlertDragState | null>(null)
const eventAlertPosition = ref<LayoutPoint | null>(null)
const eventAlertMutedUntil = ref(0)
const eventAlertNowMs = ref(Date.now())
const eventFloatingAlertHovered = ref(false)
const eventWatchtowerTab = ref<'live' | 'calendar' | 'timeline' | 'speeches' | 'shock' | 'audit' | 'history'>('live')
const dismissedCriticalAlertKey = ref('')
const eventWindowAckKeys = ref<string[]>([])
const eventWindowHiddenKeys = ref<string[]>([])
const suppressNextEventAlertClick = ref(false)
const suppressNextNodeClick = ref(false)
const radarDefaultLoading = ref(false)
let syncingRoute = false
let eventAlertClockTimer: number | undefined
let eventWindowLiveTimer: number | undefined
let eventWindowLiveRefreshInFlight = false

const RADAR_LAYOUT_KEY = 'onlybtc:p5:radar-layout:v1'
const EVENT_ALERT_POSITION_KEY = 'onlybtc:p5:event-alert-position:v1'
const EVENT_ALERT_MUTE_KEY = 'onlybtc:p5:event-alert-muted-until:v1'
const EVENT_WINDOW_ACK_KEY = 'onlybtc:event-window:ack:v1'
const EVENT_WINDOW_HIDDEN_KEY = 'onlybtc:event-window:hidden:v1'
const EVENT_WINDOW_CRITICAL_DISMISS_KEY = 'onlybtc:event-window:critical-dismiss:v1'
const defaultLayoutPoints: LayoutPoint[] = [
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
]

const decision = computed(() => state.dashboard?.decision_card ?? {})
const btcCockpit = computed(() => ((state.dashboard?.btc_trend_cockpit ?? state.overview?.btc_trend_cockpit ?? {}) as Row))
const radarRuntimePayload = computed(() => ((state.radarRuntimeCockpit?.runtime as Row | undefined) ?? (state.dashboard?.radar_runtime as Row | undefined) ?? {}) as Row)
const radarRuntimeDaemon = computed(() => ((state.radarRuntimeDaemon?.daemon as Row | undefined) ?? {}) as Row)
const radarRuntimeHealth = computed(() => ((radarRuntimePayload.value.health as Row | undefined) ?? (state.dashboard?.radar_runtime_health as Row | undefined) ?? {}) as Row)
const radarRuntimeCockpit = computed(() => ((radarRuntimePayload.value.btc_runtime_cockpit as Row | undefined) ?? (state.dashboard?.btc_runtime_cockpit as Row | undefined) ?? {}) as Row)
const btcTimescaleJudge = computed(() => ((state.dashboard?.btc_timescale_judge ?? state.overview?.btc_timescale_judge ?? {}) as Row))
const directTrendApi = computed(() => ((state.dashboard?.direct_trend_api ?? state.overview?.direct_trend_api ?? {}) as Row))
const hasCockpit = computed(() => text(btcCockpit.value.schema_version, '') === 'p45.btc_trend_cockpit.v2')
const aggregation = computed(() => state.dashboard?.aggregation_audit ?? {})
const contract = computed(() => state.dashboard?.contract_validation ?? {})
const dataQuality = computed(() => state.dashboard?.data_quality ?? {})
const llm = computed(() => state.dashboard?.llm ?? {})
const horizons = computed(() => {
  return ['4h', '1d', '3d', '7d'].map((key) => [key, normalizeTimescaleHorizon(key)] as [string, Row])
})
const invalidationRules = computed(() => state.invalidation?.invalidation_rules ?? [])
const confirmationRules = computed(() => state.invalidation?.confirmation_rules ?? [])
const alerts = computed(() => (state.alerts?.alerts as Row[] | undefined) ?? [])
const events = computed(() => (state.events?.events as Row[] | undefined) ?? [])
const eventWatchtowerPayload = computed(() => ((state.eventWindow?.event_window as Row | undefined) ?? (state.dashboard?.event_window_v3 as Row | undefined) ?? {}) as Row)
const eventWindowState = computed(() => ((eventWatchtowerPayload.value.state as Row | undefined) ?? {}) as Row)
const eventWindowOverlay = computed(() => ((eventWatchtowerPayload.value.overlay as Row | undefined) ?? {}) as Row)
const eventWindowActive = computed(() => ((eventWatchtowerPayload.value.active_event as Row | undefined) ?? {}) as Row)
const eventWindowDaemon = computed(() => ((state.eventWindowDaemon?.daemon as Row | undefined) ?? (eventWatchtowerPayload.value.daemon as Row | undefined) ?? {}) as Row)
const eventWindowTimeline = computed(() => ((state.eventWindowTimeline?.items as Row[] | undefined) ?? []) as Row[])
const eventWindowCalendar = computed(() => ((state.eventWindowCalendar?.items as Row[] | undefined) ?? (eventWatchtowerPayload.value.calendar_items as Row[] | undefined) ?? []) as Row[])
const eventCalendarMiniWeekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const
const eventCalendarMiniAnchor = computed(() => {
  const candidates = [
    eventWindowActive.value.release_time_utc,
    eventWindowActive.value.release_time,
    eventWindowActive.value.event_time,
    ...eventWindowCalendar.value.flatMap((event) => [event.release_time_utc, event.release_time, event.event_time, event.date]),
  ]
  for (const candidate of candidates) {
    const parsed = parseEventDate(candidate)
    if (parsed) return parsed
  }
  return new Date()
})
const eventCalendarMiniMonthLabel = computed(() =>
  eventCalendarMiniAnchor.value.toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' }),
)
const eventCalendarMiniDays = computed<EventCalendarMiniDay[]>(() => {
  const anchor = eventCalendarMiniAnchor.value
  const year = anchor.getUTCFullYear()
  const month = anchor.getUTCMonth()
  const firstDay = new Date(Date.UTC(year, month, 1))
  const dayCount = new Date(Date.UTC(year, month + 1, 0)).getUTCDate()
  const byDay = new Map<number, Row[]>()
  for (const event of eventWindowCalendar.value) {
    const parsed = parseEventDate(event.release_time_utc ?? event.release_time ?? event.event_time ?? event.date)
    if (!parsed || parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month) continue
    const day = parsed.getUTCDate()
    byDay.set(day, [...(byDay.get(day) ?? []), event])
  }

  const activeId = text(eventWindowActive.value.event_id, '')
  const cells: EventCalendarMiniDay[] = []
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
    })
  }
  for (let day = 1; day <= dayCount; day += 1) {
    const events = [...(byDay.get(day) ?? [])].sort((a, b) => eventImportanceRank(b) - eventImportanceRank(a))
    const primary = events[0] ?? {}
    cells.push({
      key: `${year}-${month + 1}-${day}`,
      day,
      events,
      primary,
      labels: events.map((event) => eventShortLabel(event)).filter(Boolean).slice(0, 2),
      tone: eventCalendarTone(primary),
      isBlank: false,
      isActive: Boolean(activeId && events.some((event) => text(event.event_id, '') === activeId)),
    })
  }
  return cells
})
const eventWindowAlerts = computed(() => ((state.eventWindowAlerts?.items as Row[] | undefined) ?? (eventWatchtowerPayload.value.alerts as Row[] | undefined) ?? []) as Row[])
const eventWindowSourceStatus = computed(() => ((state.eventWindowSources as Row | undefined) ?? {}) as Row)
const eventWindowSourceSummary = computed(() => ((eventWindowSourceStatus.value.summary as Row | undefined) ?? {}) as Row)
const eventWindowSources = computed(() => ((eventWindowSourceStatus.value.sources as Row[] | undefined) ?? []) as Row[])
const eventWindowSourceFetches = computed(() => ((state.eventWindowSourceFetches?.items as Row[] | undefined) ?? []) as Row[])
const eventWindowSourceQuality = computed(() => (((eventWatchtowerPayload.value.data_quality as Row | undefined)?.source_quality as Row | undefined) ?? {}) as Row)
const eventWindowProviderConfidence = computed(() => (((eventWatchtowerPayload.value.data_quality as Row | undefined)?.provider_confidence as Row | undefined) ?? {}) as Row)
const eventWindowProviderTierCounts = computed(() => ((eventWindowProviderConfidence.value.provider_tier_counts as Row | undefined) ?? {}) as Row)
const eventWindowExpectation = computed(() => ((eventWatchtowerPayload.value.expectation_monitor as Row | undefined) ?? {}) as Row)
const eventWindowPredictionOdds = computed(() => ((eventWindowExpectation.value.prediction_market_odds as Row | undefined) ?? {}) as Row)
const eventWindowSecondaryMesh = computed(() => ((eventWindowExpectation.value.secondary_calendar_mesh as Row | undefined) ?? {}) as Row)
const eventWindowDisabledCapabilities = computed(() => [
  ...(((eventWindowSourceQuality.value.disabled_capabilities as string[] | undefined) ?? []) as string[]),
  ...(((eventWindowProviderConfidence.value.disabled_capabilities as string[] | undefined) ?? []) as string[]),
].filter((value, index, arr) => arr.indexOf(value) === index))
const eventWindowSourceMode = computed(() =>
  text(
    eventWindowSourceQuality.value.overall_source_mode
      ?? eventWindowProviderConfidence.value.lineage_mode
      ?? eventWindowSourceSummary.value.overall_source_mode
      ?? (eventWatchtowerPayload.value.data_quality as Row | undefined)?.overall_source_mode,
    'unknown',
  ),
)
const eventWindowCalendarFallbackNotice = computed(() => {
  const blockedProvider = text(eventWindowActive.value.blocked_provider, '')
  const provider = text(eventWindowActive.value.provider, '')
  const tier = text(eventWindowActive.value.source_tier, '')
  if (!blockedProvider && eventWindowActive.value.fallback_used !== true) return ''
  if (tier === 'official_mirror') return `BLS official blocked, using mirror source ${provider || 'official_mirror'}`
  if (tier === 'secondary_calendar') return `BLS official blocked, using secondary source ${provider || 'secondary_calendar'}`
  if (tier === 'manual_override') return `BLS official blocked, using manual override ${provider || 'manual_override'}`
  return `BLS official blocked, using fallback source ${provider || tier || 'unknown'}`
})
const eventWindowSourceCounts = computed(() => ({
  live: Number(eventWindowSourceSummary.value.live_source_count ?? eventWindowSourceQuality.value.live_source_count ?? 0),
  partial: Number(eventWindowSourceSummary.value.partial_source_count ?? eventWindowSourceQuality.value.partial_source_count ?? 0),
  fallback: Number(eventWindowSourceSummary.value.fallback_source_count ?? eventWindowSourceQuality.value.fallback_source_count ?? 0),
  failed: Number(eventWindowSourceSummary.value.failed_source_count ?? eventWindowSourceQuality.value.failed_source_count ?? 0),
}))
const eventWindowShockLane = computed(() => ((eventWatchtowerPayload.value.shock_fast_lane as Row | undefined) ?? {}) as Row)
const eventWindowShockLlmAnalysis = computed(() => ((eventWindowShockLane.value.llm_analysis as Row | undefined) ?? {}) as Row)
const eventWindowMarketProbe = computed(() => {
  const direct = (eventWatchtowerPayload.value.market_probe as Row | undefined) ?? null
  if (direct && Object.keys(direct).length) return direct
  const probes = (eventWatchtowerPayload.value.market_probes as Row[] | undefined) ?? []
  return (probes[0] ?? {}) as Row
})
const eventWindowMarketReturns = computed(() => ((eventWindowMarketProbe.value.returns as Row | undefined) ?? {}) as Row)
const eventWindowMarketReturnZ = computed(() => ((eventWindowMarketProbe.value.return_zscores as Row | undefined) ?? {}) as Row)
const eventWindowMarketReturnRows = computed(() =>
  ['5m', '15m', '1h', '4h', '24h'].map((window) => ({
    window,
    value: eventWindowMarketReturns.value[window],
    z: eventWindowMarketReturnZ.value[window],
  })),
)
const eventWindowShockEvidence = computed(() => ((eventWindowShockLane.value.evidence as Row | undefined) ?? {}) as Row)
const eventWindowDaemonStaleReasons = computed(() => asList(eventWindowDaemon.value.stale_reasons).map((item) => text(item)))
const eventWindowDaemonHealthState = computed(() => text(eventWindowDaemon.value.health_state ?? eventWindowDaemon.value.status, 'unknown'))
const eventWindowSummaryAlert = computed(() => (eventWindowAlerts.value[0] as Row | undefined) ?? {})
const eventWindowSummaryTitle = computed(() => {
  const shockDetected = Boolean(eventWindowShockLane.value.shock_detected)
  if (shockDetected) return `Shock lane · ${text(eventWindowShockLane.value.shock_type, 'unknown')}`
  return text(eventWindowActive.value.title, 'Event Watchtower active')
})
const eventWindowSummarySubtitle = computed(() => {
  const stateName = text(eventWindowState.value.event_window_state, 'calendar_monitor')
  const phase = text(eventWindowActive.value.phase, 'calendar_awareness')
  const modifier = text(eventWindowOverlay.value.trade_permission_modifier, 'none')
  return `${stateName} · ${phase} · overlay ${modifier}`
})
const eventWindowSummaryDetail = computed(() => {
  const level = text(eventWindowState.value.emergency_level, 'none')
  const trust = text(eventWindowOverlay.value.ordinary_radar_trust, 'normal')
  const daemon = text(eventWindowDaemon.value.status, 'running')
  return `Emergency ${level}; radar trust ${trust}; daemon ${daemon}.`
})
const eventWindowSummaryAction = computed(() => {
  const modifier = text(eventWindowOverlay.value.trade_permission_modifier, 'none')
  if (modifier === 'event_lock') return 'event lock · avoid new position'
  if (modifier === 'watch_only') return 'watch only · wait for validation'
  if (modifier === 'reduce_size') return 'reduce size · monitor source drift'
  return 'normal monitoring'
})
const eventWindowReasonCodes = computed(() => asList(eventWindowState.value.reason_codes).map((item) => text(item)).slice(0, 5))
const eventWindowPostReaction = computed(() => ((eventWatchtowerPayload.value.post_event_reaction as Row | undefined) ?? {}) as Row)
const eventWindowSpeechMonitor = computed(() => ((eventWatchtowerPayload.value.fed_speech_monitor as Row | undefined) ?? {}) as Row)
const eventWindowLlmAnalyses = computed(() => ((eventWatchtowerPayload.value.llm_analyses as Row[] | undefined) ?? []) as Row[])
const eventWindowPrimaryLlmAnalysis = computed(() => {
  const analyses = [...eventWindowLlmAnalyses.value]
  if (!analyses.length) return {} as Row
  const relevanceRank: Record<string, number> = { high: 3, medium: 2, low: 1 }
  return analyses.sort((a, b) => {
    const relA = relevanceRank[text(a.policy_relevance, 'low').toLowerCase()] ?? 0
    const relB = relevanceRank[text(b.policy_relevance, 'low').toLowerCase()] ?? 0
    if (relA !== relB) return relB - relA
    return Number(b.tone_confidence ?? b.confidence ?? 0) - Number(a.tone_confidence ?? a.confidence ?? 0)
  })[0] as Row
})
const selectedEventLlmAnalysis = computed(() => {
  const id = text(selectedEventLlmAnalysisId.value, '')
  if (id) {
    const match = eventWindowLlmAnalyses.value.find((item) => text(item.analysis_id, '') === id)
    if (match) return match
  }
  return eventWindowPrimaryLlmAnalysis.value
})
const eventWindowDirectScoreImpact = computed(() => text(eventWatchtowerPayload.value.direct_score_impact, 'false'))
const eventWindowScheduler = computed(() => ((eventWindowDaemon.value.source_cadence as Row | undefined) ?? {}) as Row)
const eventWindowNextDueSources = computed(() => asList(eventWindowDaemon.value.next_due_sources).map((item) => text(item)).slice(0, 6))
const eventWindowPersistedScheduler = computed(() => ((eventWindowDaemon.value.persisted_scheduler_state as Row[] | undefined) ?? []) as Row[])
const eventWindowLastRunOnce = computed(() => ((state.eventWindowRunOnceResult as Row | undefined) ?? {}) as Row)
const eventWindowAuditBundle = computed(() => ((state.eventWindowAuditBundle?.audit_bundle as Row | undefined) ?? {}) as Row)
const eventWindowAuditBundleReports = computed(() => ((eventWindowAuditBundle.value.reports as Row[] | undefined) ?? []) as Row[])
const eventWindowAuditFileMeta = computed(() => ((eventWindowAuditBundle.value.report_file_meta as Row[] | undefined) ?? []) as Row[])
const eventWindowAuditRegression = computed(() => ((eventWindowAuditBundle.value.regression_report as Row | undefined) ?? {}) as Row)
const eventWindowOverlayForbiddenKeys = computed(() =>
  asList(
    eventWindowOverlay.value.forbidden_keys
      ?? eventWindowOverlay.value.forbidden_content_keys
      ?? eventWatchtowerPayload.value.forbidden_keys
      ?? eventWatchtowerPayload.value.forbidden_content_keys,
  ).map((item) => text(item)),
)
const eventWindowLlmViolations = computed(() =>
  asList(selectedEventLlmAnalysis.value.violations ?? selectedEventLlmAnalysis.value.boundary_violations).map((item) => text(item)),
)
const eventWindowAuditReportLinks = computed<Row[]>(() => {
  const defaults: Row[] = [
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
  ]
  return defaults.map((report) => {
    const filename = text(report.filename, '')
    const meta =
      eventWindowAuditFileMeta.value.find((item) => text(item.path, '').includes(filename)) ??
      eventWindowAuditBundleReports.value.find((item) => text(item.html_path ?? item.path, '').includes(filename)) ??
      {}
    return { ...report, ...meta, filename, relative_path: text(meta.path ?? meta.html_path ?? report.relative_path, text(report.relative_path, '')) }
  })
})
const eventWatchtowerTabs = [
  { id: 'live', label: 'Live' },
  { id: 'calendar', label: 'Calendar' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'speeches', label: 'Speeches' },
  { id: 'shock', label: 'Shock Lane' },
  { id: 'audit', label: 'Audit' },
  { id: 'history', label: 'History' },
] as const
const eventWindowVisibilityKey = computed(() =>
  [
    text(eventWatchtowerPayload.value.snapshot_id, ''),
    text(eventWindowState.value.valid_until, ''),
    text(eventWindowState.value.event_window_state, ''),
    text(eventWindowState.value.emergency_level, ''),
  ].join('|'),
)
const eventCriticalAlertKey = computed(() =>
  [
    text(eventWatchtowerPayload.value.snapshot_id, ''),
    text(eventWindowState.value.valid_until, ''),
    text(eventWindowState.value.event_window_state, ''),
    text(eventWindowState.value.emergency_level, ''),
    text(eventWindowOverlay.value.trade_permission_modifier, ''),
  ].join('|'),
)
const eventCurrentAlertAcked = computed(() => eventWindowAckKeys.value.includes(eventWindowVisibilityKey.value))
const eventCurrentAlertHidden = computed(() => eventWindowHiddenKeys.value.includes(eventWindowVisibilityKey.value))
const eventCriticalLikeActive = computed(() => {
  const level = text(eventWindowState.value.emergency_level, 'none').toLowerCase()
  const modifier = text(eventWindowOverlay.value.trade_permission_modifier, 'none').toLowerCase()
  return level === 'critical' || ['event_lock', 'avoid_new_position'].includes(modifier)
})
const eventCriticalOverlayActive = computed(() => {
  return eventCriticalLikeActive.value
})
const showEventCriticalOverlay = computed(
  () => eventCriticalOverlayActive.value && dismissedCriticalAlertKey.value !== eventCriticalAlertKey.value,
)
const eventCriticalMockOverlayEnabled = computed(() => {
  if (!import.meta.env.DEV || typeof window === 'undefined') return false
  return new URLSearchParams(window.location.search).get('event_mock') === 'critical'
})
const showEventCriticalMockOverlay = computed(() => eventCriticalMockOverlayEnabled.value && !showEventCriticalOverlay.value)
const eventFloatingAlertMuted = computed(() => eventAlertNowMs.value < eventAlertMutedUntil.value)
const eventFloatingAlertEligible = computed(() => {
  const level = text(eventWindowState.value.emergency_level, 'none').toLowerCase()
  return level === 'high' && !eventCriticalOverlayActive.value && !eventCurrentAlertHidden.value
})
const showEventFloatingAlert = computed(() =>
  !eventCurrentAlertHidden.value &&
  (eventFloatingAlertEligible.value || eventFloatingAlertHovered.value || Boolean(eventAlertDragging.value)),
)
const eventFloatingTitle = computed(() => `EVENT WATCH · ${text(eventWindowState.value.emergency_level, 'high').toUpperCase()}`)
const eventFloatingSubtitle = computed(() => {
  const eventType = text(eventWindowActive.value.event_type, 'event')
  const timeToEvent = daysText(Number(eventWindowActive.value.time_to_event_sec ?? 0) / 86400)
  const trust = text(eventWindowOverlay.value.ordinary_radar_trust, 'reduced')
  return `${eventType} in T-${timeToEvent} · radar trust ${trust}`
})
const eventFloatingMessage = computed(() => {
  const codes = eventWindowReasonCodes.value
  if (codes.some((code) => code.includes('inflation') || code.includes('nowcast'))) {
    return 'Inflation upside risk is building before release. Ordinary radar trend continuation is downgraded until release + 30m.'
  }
  if (codes.some((code) => code.includes('drawdown') || code.includes('market_dislocation'))) {
    return 'BTC market shock is being monitored. Ordinary radar trend continuation is downgraded until the shock is absorbed or confirmed.'
  }
  return `${text(eventWindowActive.value.title, 'Event risk')} is active. Ordinary radar trend continuation is downgraded until Event Watch validates the risk window.`
})
const eventFloatingAlertStyle = computed(() => {
  const pos = eventAlertPosition.value
  if (!pos) return {}
  return {
    left: `${pos.x}px`,
    top: `${pos.y}px`,
  }
})
const stages = computed(() => state.runs?.stages ?? [])
const auditReports = computed(() => store.reports.value)
const latestRun = computed(() => ((state.runs?.latest as Row | undefined) ?? store.runLineage.value ?? {}) as Row)
const frozenFinalLineage = computed(() => {
  if (state.routeContext.isHistorical && state.selectedHistory?.run_lineage) {
    return state.selectedHistory.run_lineage as Row
  }
  return ((state.dashboard?.run_lineage as Row | undefined) ?? store.runLineage.value ?? latestRun.value ?? {}) as Row
})
const frozenFinalCreatedAt = computed(() =>
  firstPresent(frozenFinalLineage.value.created_at, state.dashboard?.created_at, state.dashboard?.updated_at),
)
const liveRuntimeFreshness = computed(() => ({
  snapshot_id: firstPresent(
    radarRuntimeHealth.value.snapshot_id,
    radarRuntimeDaemon.value.last_snapshot_id,
    radarRuntimePayload.value.snapshot_id,
  ),
  health_state: firstPresent(radarRuntimeHealth.value.health_state, radarRuntimeDaemon.value.health_state, radarRuntimeDaemon.value.status),
  runtime_fresh: firstPresent(radarRuntimeHealth.value.runtime_fresh, radarRuntimeDaemon.value.runtime_fresh),
  source_fresh: firstPresent(radarRuntimeHealth.value.source_fresh, radarRuntimeDaemon.value.source_fresh),
  source_freshness_state: firstPresent(radarRuntimeHealth.value.source_freshness_state, radarRuntimeDaemon.value.source_freshness_state),
  fresh_module_count: radarRuntimeHealth.value.fresh_module_count,
  expected_module_count: radarRuntimeHealth.value.expected_module_count,
  last_tick_age_sec: radarRuntimeDaemon.value.last_tick_age_sec,
}))
const runExecutionProfile = computed(() =>
  text(
    state.activeRunJob?.execution_profile ??
      state.runResult?.execution_profile ??
      latestRun.value.execution_profile,
    state.llmRunEnabled ? 'full_with_llm' : 'fast_deterministic',
  ),
)
const runLlmEnabled = computed(() => {
  const job = ((state.activeRunJob ?? state.runResult ?? {}) as Row)
  if (typeof job.llm_enabled === 'boolean') return job.llm_enabled
  return runExecutionProfile.value !== 'fast_deterministic' && state.llmRunEnabled
})
const runChainLabel = computed(() =>
  runLlmEnabled.value ? 'P1 -> P2 -> P3 -> P4.5 -> LLM' : 'P1 -> P2 -> P3 -> P4.5',
)
const runWarnings = computed(() => ((state.runs?.warnings as Row[] | string[] | undefined) ?? []) as Array<Row | string>)
const runErrors = computed(() => ((state.runs?.errors as Row[] | string[] | undefined) ?? []) as Array<Row | string>)
const pipelineDefs = [
  { key: 'p1', code: 'P1', label: 'Collect', match: ['p1', 'collect'], runKey: 'collect_run_id' },
  { key: 'p2', code: 'P2', label: 'Radar', match: ['p2', 'radar'], runKey: 'p2_radar_run_id' },
  { key: 'p3', code: 'P3', label: 'Scoring', match: ['p3', 'scoring'], runKey: 'p3_run_id' },
  { key: 'p45', code: 'P4.5', label: 'Final Pack', match: ['p45', 'p4.5', 'final'], runKey: 'final_run_id' },
  { key: 'llm', code: 'LLM', label: 'Analyst', match: ['llm_analyst', 'llm analyst', 'analyst', 'llm'], runKey: 'llm_analyst_run_id' },
]
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
  ]
  const entries = preferredOrder
    .filter((key) => latestRun.value[key])
    .map((key) => ({ key, value: latestRun.value[key] }))
  for (const [key, value] of Object.entries(latestRun.value)) {
    if (preferredOrder.includes(key) || value === undefined || value === null || typeof value === 'object') continue
    if (String(key).endsWith('_run_id') || key === 'runtime_mode' || key === 'created_at') entries.push({ key, value })
  }
  return entries
})
const settingsLlm = computed(() => (state.settings?.llm as Row | undefined) ?? {})
const settingsPayload = computed(() => ((state.settings as Row | null) ?? {}) as Row)
const settingsApp = computed(() => ((settingsPayload.value.app as Row | undefined) ?? {}) as Row)
const settingsRunDefaults = computed(() => ((settingsPayload.value.run_defaults as Row | undefined) ?? {}) as Row)
const settingsLlmRouting = computed(() => ((settingsPayload.value.llm_routing as Row | undefined) ?? {}) as Row)
const settingsLlmRuntimeDefaults = computed(() => ((settingsLlmRouting.value.runtime_defaults as Row | undefined) ?? {}) as Row)
const settingsLlmProviders = computed(() => ((settingsLlmRouting.value.providers as Row[] | undefined) ?? []) as Row[])
const settingsLlmRoutes = computed(() => ((settingsLlmRouting.value.p4_agent_routes as Row[] | undefined) ?? []) as Row[])
const settingsLlmAvailableCount = computed(() => ((settingsLlmRouting.value.available_providers as unknown[] | undefined) ?? []).length)
const settingsAudit = computed(() => ((settingsPayload.value.settings_audit as Row | undefined) ?? {}) as Row)
const settingsAuditEvents = computed(() => ((settingsAudit.value.events as Row[] | undefined) ?? []) as Row[])
const settingsWarnings = computed(() => ((settingsPayload.value.warnings as Row[] | string[] | undefined) ?? []) as Array<Row | string>)
const settingsErrors = computed(() => ((settingsPayload.value.errors as Row[] | string[] | undefined) ?? []) as Array<Row | string>)
const settingsProviderRows = computed(() =>
  (((settingsPayload.value.providers as Row | undefined)?.providers as Row[] | undefined) ?? []) as Row[],
)
const settingsProviderHealthRows = computed(() =>
  (((settingsPayload.value.provider_health as Row | undefined)?.items as Row[] | undefined) ?? []) as Row[],
)
const settingsProviderHealthById = computed(() => {
  const byId: Record<string, Row> = {}
  for (const row of settingsProviderHealthRows.value) byId[text(row.provider_id)] = row
  return byId
})
const settingsTabs = [
  { id: 'llm', label: 'LLM Providers' },
  { id: 'keys', label: 'API Keys' },
  { id: 'data', label: 'Data Sources' },
  { id: 'radar', label: 'Radar & Alerts' },
  { id: 'run', label: 'Run Once' },
  { id: 'publish', label: 'Publish' },
  { id: 'storage', label: 'Storage' },
  { id: 'system', label: 'System' },
]
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
      }))
  }
  return [
    { providerId: 'deepseek', key: 'ONLYBTC_DEEPSEEK_API_KEY', enabled: settingsLlm.value.has_deepseek_key === true, provider: 'DeepSeek', scope: 'P4.5 research / analyst', masked: '', status: 'legacy', supportsTest: true, health: {} as Row },
    { providerId: 'openai', key: 'ONLYBTC_OPENAI_API_KEY', enabled: settingsLlm.value.has_openai_key === true, provider: 'OpenAI', scope: 'fallback / validation', masked: '', status: 'legacy', supportsTest: true, health: {} as Row },
    { providerId: 'qwen', key: 'ONLYBTC_QWEN_API_KEY', enabled: settingsLlm.value.has_qwen_key === true, provider: 'Qwen', scope: 'legacy optional', masked: '', status: 'legacy', supportsTest: true, health: {} as Row },
    { providerId: 'volcano', key: 'ONLYBTC_VOLCANO_API_KEY', enabled: settingsLlm.value.has_volcano_key === true, provider: 'Volcano', scope: 'legacy optional', masked: '', status: 'legacy', supportsTest: true, health: {} as Row },
    { providerId: 'kimi', key: 'ONLYBTC_KIMI_API_KEY', enabled: settingsLlm.value.has_kimi_key === true, provider: 'Kimi', scope: 'legacy optional', masked: '', status: 'legacy', supportsTest: true, health: {} as Row },
  ]
})
const sourceHealth = computed(() => (state.dataQuality?.source_health as Row | undefined) ?? {})
const qualityPayload = computed(() => ((state.dataQuality?.data_quality as Row | undefined) ?? dataQuality.value ?? {}) as Row)
const metricCountAudit = computed(() =>
  ((state.dataQuality?.metric_count_audit as Row | undefined) ??
    (qualityPayload.value.metric_count_audit as Row | undefined) ??
    {}) as Row,
)
const qualityContract = computed(() => ((state.dataQuality?.contract_validation as Row | undefined) ?? contract.value ?? {}) as Row)
const qualityFreshnessCheck = computed(() => ((qualityContract.value.freshness_check as Row | undefined) ?? {}) as Row)
const qualityWarnings = computed(() => ((qualityContract.value.warnings as Row[] | undefined) ?? []) as Row[])
const qualityChecks = computed(() => ((qualityContract.value.checks as Row | undefined) ?? {}) as Row)
const sourceStatusCounts = computed(() => ((sourceHealth.value.status_counts as Row | undefined) ?? {}) as Row)
const recentSourceRows = computed(() => ((sourceHealth.value.recent_failed_sources as Row[] | undefined) ?? []).slice(0, 18))
const currentRunWarningRows = computed(() => ((sourceHealth.value.current_run_warning_sources as Row[] | undefined) ?? []).slice(0, 8))
const historyFailedRows = computed(() => ((sourceHealth.value.history_recent_failed_sources as Row[] | undefined) ?? []).slice(0, 12))
const evidenceItems = computed(() => (state.evidence?.items as Row[] | undefined) ?? [])
const selectedSourceDetail = computed(() => ((state.selectedSourceDetail as Row | null) ?? {}) as Row)
const selectedSourceAuthState = computed(() => ((state.selectedSourceAuthState as Row | null) ?? {}) as Row)
const selectedSourceLastCapture = computed(() => ((state.selectedSourceLastCapture as Row | null) ?? {}) as Row)
const selectedSourceActionResult = computed(() => ((state.selectedSourceActionResult as Row | null) ?? {}) as Row)
const selectedSourceProfile = computed(() => ((selectedSourceDetail.value.source as Row | undefined) ?? {}) as Row)
const selectedSourceMetadata = computed(() => ((selectedSourceProfile.value.metadata as Row | undefined) ?? {}) as Row)
const selectedSourceFreshnessPolicy = computed(() => ((selectedSourceMetadata.value.freshness_policy as Row | undefined) ?? {}) as Row)
const selectedSourceRuns = computed(() => ((selectedSourceDetail.value.runs as Row[] | undefined) ?? []) as Row[])
const selectedSourceRawObservations = computed(() => ((selectedSourceDetail.value.raw_observations as Row[] | undefined) ?? []) as Row[])
const selectedSourceMetrics = computed(() => ((selectedSourceDetail.value.metrics as Row[] | undefined) ?? []) as Row[])
const latestSourceRun = computed(() => selectedSourceRuns.value[0] ?? {})
const selectedSourceEvidence = computed(() => evidenceItems.value.filter((item) => String(item.source_id ?? '') === selectedSourceId.value))
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
  ] as Row[]
  const fromSourceRows = recentSourceRows.value
    .filter((row) => isSemiAutomatedSource(row))
    .map((row) => ({ ...row, automation_mode: row.automation_mode ?? 'semi_automated', auth_state: sourceAuthState(row) }))
  const byId = new Map<string, Row>()
  for (const row of [...known, ...fromSourceRows] as Row[]) byId.set(sourceId(row), row)
  return [...byId.values()]
})
const selectedSourceModules = computed(() => {
  const modules = new Set(selectedSourceEvidence.value.map((item) => text(item.radar_module, 'module')))
  return [...modules]
})
const selectedManualSource = computed(() => {
  const existing = semiAutoSources.value.find((row) => text(row.source_id) === selectedSourceId.value)
  return {
    ...(existing ?? {}),
    ...selectedSourceProfile.value,
    ...selectedSourceAuthState.value,
    source_id: selectedSourceId.value || text((existing as Row | undefined)?.source_id ?? selectedSourceProfile.value.source_id),
  } as Row
})
const analystArticles = computed(() => (state.articles?.llm_analyst_articles as Row[] | undefined) ?? [])
const selectedRadarModule = computed(() => (state.selectedRadarDetail?.module as Row | undefined) ?? {})
const selectedRadarMetrics = computed(() => (state.selectedRadarDetail?.metrics as Row[] | undefined) ?? [])
const selectedRadarMetric = computed(() => {
  const preferred = selectedRadarMetrics.value.find((metric) => text(metric.metric_id) === selectedRadarMetricId.value)
  return (preferred ?? selectedRadarMetrics.value[0] ?? {}) as Row
})
const selectedRadarTopMetrics = computed(() => selectedRadarMetrics.value
  .filter((metric) => metric.available !== false)
  .map((metric, index) => ({ metric, index }))
  .sort((left, right) => {
    const scoreDelta = radarMetricStrength(right.metric) - radarMetricStrength(left.metric)
    if (Math.abs(scoreDelta) > 0.000001) return scoreDelta
    return Number(right.metric.quality_score ?? 0) - Number(left.metric.quality_score ?? 0)
  })
  .slice(0, 10)
  .map(({ metric }) => metric))
const selectedRadarMetricStats = computed(() => {
  let support = 0
  let pressure = 0
  let mixed = 0
  let quality = 0
  for (const metric of selectedRadarMetrics.value) {
    const klass = radarMetricClass(metric)
    if (metric.fallback_used || metric.is_stale || metric.available === false) quality += 1
    else if (['bull', 'bullish', 'positive'].includes(klass)) support += 1
    else if (['bear', 'bearish', 'negative'].includes(klass)) pressure += 1
    else mixed += 1
  }
  return { support, pressure, mixed, quality }
})
const analystFallback = [
  { analyst_id: 'Macro Analyst', status: 'waiting', title: 'evidence pending' },
  { analyst_id: 'Liquidity Analyst', status: 'waiting', title: 'evidence pending' },
  { analyst_id: 'Microstructure Analyst', status: 'waiting', title: 'evidence pending' },
  { analyst_id: 'On-chain Analyst', status: 'waiting', title: 'evidence pending' },
] as Row[]

const sourceSummary = computed(() => {
  const sourceIds = new Set(evidenceItems.value.map((item) => String(item.source_id ?? 'unknown')))
  return [...sourceIds].slice(0, 12)
})

const duplicateGroups = computed(() => {
  const groups = new Map<string, Row[]>()
  for (const item of evidenceItems.value) {
    const group = String(item.duplicate_group_id ?? item.metric_id ?? 'unknown')
    groups.set(group, [...(groups.get(group) ?? []), item])
  }
  return [...groups.entries()]
    .filter(([, items]) => items.length > 1)
    .slice(0, 20)
    .map(([group, items]) => ({ group, items }))
})
const rawSourceConflicts = computed(() => {
  const dashboardConflicts = ((state.dashboard?.conflicting_evidence as Row | undefined)?.source_conflicts as unknown) ?? []
  const evidenceConflicts = ((state.evidence?.conflicting_evidence as Row | undefined)?.source_conflicts as unknown) ?? []
  const qualityConflicts = ((state.dataQuality?.conflicting_evidence as Row | undefined)?.source_conflicts as unknown) ?? []
  return [...asList(dashboardConflicts), ...asList(evidenceConflicts), ...asList(qualityConflicts)] as Row[]
})
const multiSourceConflictRows = computed(() => {
  const rows: Row[] = []
  for (const item of rawSourceConflicts.value) {
    rows.push({ ...item, conflict_origin: 'source_conflict' })
  }
  for (const group of duplicateGroups.value) {
    const sources = [...new Set(group.items.map((item) => text(item.source_id)).filter((item) => item !== '-'))]
    if (sources.length <= 1 && group.items.length <= 1) continue
    const selected = group.items.find((item) => item.role === 'primary_signal' || item.evidence_tier === 'primary') ?? group.items[0]
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
    })
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
    })
  }
  const seen = new Set<string>()
  return rows.filter((row) => {
    const key = `${text(row.metric_id)}|${text(row.selected_source ?? row.source_id)}|${text(row.conflict_origin)}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
})
const conflictStats = computed(() => ({
  total: multiSourceConflictRows.value.length,
  high: multiSourceConflictRows.value.filter((row) => conflictSeverityClass(row) === 'bear').length,
  fallback: multiSourceConflictRows.value.filter((row) => row.fallback_used === true || row.fallback_reason).length,
  definition: multiSourceConflictRows.value.filter((row) => text(row.conflict_type).includes('definition')).length,
}))

const evidenceRunLineage = computed(() => ((state.evidence?.run_lineage as Row | undefined) ?? store.runLineage.value ?? {}) as Row)
const selectedEvidence = computed(() => ((state.selectedEvidenceDetail?.evidence as Row | undefined) ?? {}) as Row)
const selectedEvidenceHistory = computed(() => ((selectedEvidence.value.history_context as Row | undefined) ?? {}) as Row)
const evidenceModules = computed(() => {
  const modules = new Set<string>()
  for (const item of evidenceItems.value) {
    const moduleId = String(item.radar_module ?? item.module_id ?? '')
    if (moduleId) modules.add(moduleId)
  }
  return [...modules].sort()
})
const evidenceBuckets = computed(() => {
  const buckets = new Set<string>()
  for (const item of evidenceItems.value) {
    const bucket = String(item.score_bucket ?? item.direction ?? '')
    if (bucket) buckets.add(bucket)
  }
  return [...buckets].sort()
})
const filteredEvidenceItems = computed(() =>
  evidenceItems.value.filter((item) => {
    const moduleId = String(item.radar_module ?? item.module_id ?? '')
    const bucket = String(item.score_bucket ?? item.direction ?? '')
    return (
      (evidenceModuleFilter.value === 'all' || moduleId === evidenceModuleFilter.value) &&
      (evidenceBucketFilter.value === 'all' || bucket === evidenceBucketFilter.value)
    )
  }),
)
const evidenceStats = computed(() => {
  const stats = {
    total: evidenceItems.value.length,
    positive: 0,
    negative: 0,
    zero: 0,
    stale: 0,
    fallback: 0,
    unavailable: 0,
  }
  for (const item of evidenceItems.value) {
    const bucket = String(item.score_bucket ?? '').toLowerCase()
    const direction = String(item.direction ?? '').toLowerCase()
    if (bucket.includes('positive') || direction.includes('bull')) stats.positive += 1
    else if (bucket.includes('negative') || direction.includes('bear')) stats.negative += 1
    else stats.zero += 1
    if (item.is_stale === true || String(item.freshness_status ?? '').includes('stale')) stats.stale += 1
    if (item.fallback_used === true || item.fallback_reason) stats.fallback += 1
    if (item.available === false) stats.unavailable += 1
  }
  return stats
})

const topologyModules = computed(() =>
  store.radarModules.value.slice(0, 14).map((module, index) => ({
    module,
    index,
    direction: moduleDisplayState(module),
  })),
)

const dynamicLinks = computed(() =>
  topologyModules.value.map((node) => {
    const moduleId = moduleName(node.module)
    const point = displayNodePoint(moduleId, node.index)
    const kind = directionClass(node.direction)
    const depth = nodeDepth(point)
    return {
      moduleId,
      kind,
      path: linkPath(point),
      opacity: depth.opacity,
      strokeWidth: depth.strokeWidth,
    }
  }),
)

const decisionReasons = computed(() => {
  if (hasCockpit.value) {
    const summary = ((btcCockpit.value.ui_summary as Row | undefined) ?? {}) as Row
    return [
      summary.fast_read,
      summary.confirmation_read,
      summary.why_not_strong,
      summary.next_trigger,
    ].filter(Boolean).slice(0, 4)
  }
  const reasons = decision.value.why_not_strong
  const list = Array.isArray(reasons) ? reasons : []
  const fallback = [
    decision.value.conclusion_sentence,
    'Short-term support and medium-term pressure coexist; direction consensus is not strong enough.',
    'Zero-score metrics are high, so strength cannot be upgraded to a strong one-sided view.',
    invalidationRules.value[0]?.title ?? confirmationRules.value[0]?.title,
  ]
  return [...list, ...fallback].filter(Boolean).slice(0, 4)
})

const finalViewText = computed(() =>
  hasCockpit.value
    ? text(btcCockpit.value.headline_state, 'neutral')
    : state.dashboard?.final_view_cn ?? state.dashboard?.final_view ?? '-',
)

const tradePermissionText = computed(() => text(btcCockpit.value.trade_permission ?? decision.value.trade_permission, 'watch_only'))

const cockpitUiSummary = computed(() => ((btcCockpit.value.ui_summary as Row | undefined) ?? {}) as Row)
const cockpitHorizon = computed(() => ((btcCockpit.value.horizon as Record<string, Row> | undefined) ?? {}) as Record<string, Row>)
const hasRuntimeCockpit = computed(() => text(radarRuntimeCockpit.value.schema_version, '') === 'p45.radar_runtime_cockpit.v2')
const runtimeCockpitScores = computed(() => ((radarRuntimeCockpit.value.scores as Row | undefined) ?? {}) as Row)
const cockpitSummaryText = computed(() => {
  if (!hasCockpit.value) return text(decision.value.conclusion_sentence, 'Waiting for P4.5 decision card')
  return text(
    cockpitUiSummary.value.fast_read,
    `${text(btcCockpit.value.headline_state, 'neutral')} · ${text(btcCockpit.value.trend_quality, 'unconfirmed')}`,
  )
})
const cockpitScores = computed(() => ((btcCockpit.value.scores as Row | undefined) ?? {}) as Row)
const cockpitFastScore = computed(() => {
  const raw = Number(
    hasRuntimeCockpit.value
      ? runtimeCockpitScores.value.fast_net_score ?? radarRuntimeCockpit.value.fast_net_score ?? 0
      : cockpitScores.value.fast_net_score ?? 0,
  )
  if (!Number.isFinite(raw)) return '0.00'
  return `${raw >= 0 ? '+' : ''}${raw.toFixed(2)}`
})
const cockpitReadoutLabel = computed(() => (hasRuntimeCockpit.value ? 'Runtime fast' : 'Fast layer'))
const cockpitFastDirection = computed(() =>
  hasRuntimeCockpit.value
    ? signedDirection(Number(runtimeCockpitScores.value.fast_net_score ?? radarRuntimeCockpit.value.fast_net_score ?? 0))
    : text(cockpitHorizon.value['4h']?.direction ?? btcCockpit.value.btc_direction, 'neutral'),
)
const cockpitFastStage = computed(() =>
  hasRuntimeCockpit.value
    ? text(radarRuntimeCockpit.value.headline_stage, 'nowcast')
    : text(cockpitHorizon.value['4h']?.stage ?? btcCockpit.value.trend_phase, 'none'),
)
const cockpitPressureText = computed(() =>
  text(cockpitUiSummary.value.main_pressure, 'No dominant pressure module.'),
)
const cockpitSupportText = computed(() =>
  text(cockpitUiSummary.value.main_support, 'No dominant support module.'),
)
const cockpitConflictText = computed(() =>
  text(cockpitUiSummary.value.why_not_strong, 'Waiting for acceptance or conflict resolution.'),
)
const primaryCockpitTrigger = computed(() => {
  const triggers = btcCockpit.value.next_confirmation_triggers
  return Array.isArray(triggers) ? text(triggers[0], '等待确认条件') : primaryConfirmationTitle.value
})
const primaryCockpitInvalidation = computed(() => {
  const triggers = btcCockpit.value.next_invalidation_triggers
  return Array.isArray(triggers) ? text(triggers[0], '等待反证条件') : primaryInvalidationTitle.value
})

const dataQualityLabel = computed(() =>
  text(
    dataQuality.value.data_quality_level ??
      dataQuality.value.quality_level ??
      dataQuality.value.status ??
      contract.value.status,
    'quality',
  ),
)

const contractStatus = computed(() => text(contract.value.status, 'unknown'))

const alertLevel = computed(() => String((alerts.value[0] as Row | undefined)?.level ?? 'watch').toLowerCase())
const alertRunLineage = computed(() => ((state.alerts?.run_lineage as Row | undefined) ?? store.runLineage.value ?? {}) as Row)
const alertStats = computed(() => {
  const stats = {
    total: alerts.value.length,
    critical: 0,
    warning: 0,
    info: 0,
    cooling: 0,
    active: 0,
    evidence: 0,
  }
  for (const alert of alerts.value) {
    const level = String(alert.level ?? '').toLowerCase()
    const status = String(alert.state ?? '').toLowerCase()
    if (level.includes('critical') || level.includes('high')) stats.critical += 1
    else if (level.includes('warning') || level.includes('watch')) stats.warning += 1
    else stats.info += 1
    if (status.includes('cool')) stats.cooling += 1
    else stats.active += 1
    const evidenceCount = Number(alert.evidence_count ?? 0)
    if (Number.isFinite(evidenceCount)) stats.evidence += evidenceCount
  }
  return stats
})
const qualityScoreText = computed(() => {
  const score = Number(qualityPayload.value.avg_metric_quality ?? dataQuality.value.avg_metric_quality ?? dataQuality.value.quality_score)
  if (!Number.isFinite(score)) return '-'
  return score.toFixed(4)
})
const qualityBoundaryText = computed(() => {
  const availableMissing = Number(qualityFreshnessCheck.value.available_metric_missing_freshness_count ?? 0)
  const unavailableMissing = Number(qualityFreshnessCheck.value.unavailable_metric_missing_freshness_count ?? qualityPayload.value.missing_freshness_count ?? 0)
  if (availableMissing > 0) return `${availableMissing} available metrics missing freshness; review before publishing.`
  if (unavailableMissing > 0) return `${unavailableMissing} unavailable metrics missing freshness; treated as warning, not a blocking failure.`
  return 'Available metrics have required freshness fields.'
})
const sourceHealthScopeText = computed(() => {
  const currentFailed = Number(sourceHealth.value.current_run_failed_count ?? 0)
  const currentWarning = Number(sourceHealth.value.current_run_warning_count ?? 0)
  const historyFailed = Number(sourceHealth.value.history_recent_failed_count ?? 0)
  return `current run failures ${currentFailed} · current warnings ${currentWarning} · history failures ${historyFailed}`
})
const metricCountAuditText = computed(() =>
  text(
    metricCountAudit.value.count_explanation,
    'P1 counts collected metrics; P4.5 counts scored evidence records used by the report contract.',
  ),
)
const alertSummaryText = computed(() => {
  if (!alerts.value.length) return 'No active alerts in this run; continue monitoring invalidation and confirmation rules.'
  const top = alerts.value[0]
  return `${text(top.level, 'watch')} · ${text(top.state, 'active')} · ${text(top.summary, 'Waiting for alert summary')}`
})

const scorePercent = computed(() => {
  const raw = hasCockpit.value ? btcCockpit.value.confidence_score : decision.value.confidence ?? aggregation.value.confidence ?? 0
  const confidence = Number(raw)
  if (!Number.isFinite(confidence)) return '0%'
  const percent = confidence > 1 ? confidence : confidence * 100
  return `${Math.max(0, Math.min(100, Math.round(percent)))}%`
})

const scoreRingStyle = computed(() => {
  const raw = hasCockpit.value ? btcCockpit.value.confidence_score : decision.value.confidence ?? aggregation.value.confidence ?? 0
  const confidence = Number(raw)
  const value = confidence > 1 ? confidence : confidence * 100
  const percent = Math.max(0, Math.min(100, Number.isFinite(value) ? Math.round(value) : 0))
  return { '--score-percent': `${percent}%` }
})

const btcNodeClass = computed(() => {
  const classes = [directionClass(hasCockpit.value ? btcCockpit.value.headline_state : state.dashboard?.final_view)]
  const contractBad = !['passed', 'ok', 'pass'].includes(contractStatus.value.toLowerCase())
  const qualityBad = ['bad', 'failed', 'critical'].some((item) => dataQualityLabel.value.toLowerCase().includes(item))
  if (alertLevel.value.includes('critical')) classes.push('pulse-critical')
  else if (alertLevel.value.includes('high') || alertLevel.value.includes('warning')) classes.push('pulse-warning')
  if (contractBad || qualityBad) classes.push('pulse-quality')
  return classes
})

const primaryInvalidationTitle = computed(() => text(invalidationRules.value[0]?.title, '等待反证条件'))
const primaryConfirmationTitle = computed(() => text(confirmationRules.value[0]?.title, '等待确认条件'))
const topAlert = computed(() => alerts.value[0] as Row | undefined)
const eventWindowRows = computed(() =>
  events.value
    .map((row) => ({
      row,
      payload: ((row.payload as Row | undefined) ?? {}) as Row,
      daysUntil: Number(((row.payload as Row | undefined) ?? {}).days_until ?? row.value ?? Number.POSITIVE_INFINITY),
    }))
    .sort((left, right) => left.daysUntil - right.daysUntil),
)
const halvingStats = computed(() => ({
  days: metricValue('btc_halving_estimated_days'),
  height: metricValue('btc_block_height'),
  blocks: metricValue('btc_halving_blocks_remaining'),
}))
const runningStageText = computed(() => {
  if (state.running) return `running · ${runChainLabel.value}`
  const failed = stages.value.find((stage) => String(stage.status ?? '').toLowerCase().includes('fail'))
  if (failed) return `failed · ${text(failed.label ?? failed.stage_id)}`
  const degraded = stages.value.find((stage) => String(stage.status ?? '').toLowerCase().includes('error'))
  if (degraded) return `degraded · ${text(degraded.label ?? degraded.stage_id)}`
  return `ready · ${stages.value.length || 0} stages`
})
const runHealthClass = computed(() => {
  if (state.running) return 'mixed'
  if (stages.value.some((stage) => String(stage.status ?? '').toLowerCase().includes('fail'))) return 'bear'
  if (stages.value.some((stage) => String(stage.status ?? '').toLowerCase().includes('error'))) return 'quality'
  return 'bull'
})
const pipelineNodes = computed(() => {
  const nodes = pipelineDefs.map((definition, index) => {
    const stage = findPipelineStage(definition.match)
    const stateName = pipelineStageState(stage, index)
    return {
      ...definition,
      index,
      stage,
      state: stateName,
      icon: pipelineStateIcon(stateName),
      runId: pipelineRunId(definition.runKey, stage),
      report: stage ? stageReport(stage) : ({} as Row),
    }
  })
  return nodes
})
const pipelineActive = computed(() => state.running || pipelineNodes.value.some((node) => node.state === 'active'))
const pipelineProgressPercent = computed(() => {
  if (!pipelineNodes.value.length) return 0
  if (!stages.value.length && !pipelineActive.value) return 0
  const progressStates = new Set(['done', 'degraded', 'failed', 'active'])
  const furthestIndex = pipelineNodes.value.reduce((maxIndex, node) => {
    return progressStates.has(node.state) ? Math.max(maxIndex, node.index) : maxIndex
  }, -1)
  if (furthestIndex < 0) return 0
  const maxUnits = Math.max(1, pipelineNodes.value.length - 1)
  const maxLineWidth = 80
  return clamp((furthestIndex / maxUnits) * maxLineWidth, 0, maxLineWidth)
})
const pipelineProgressStyle = computed(() => ({ '--pipeline-progress': `${pipelineProgressPercent.value}%` }))
const pipelineHeartbeatText = computed(() => (pipelineActive.value ? 'audit stream active' : 'audit stream idle'))

const analystCards = computed(() => {
  const cards = analystArticles.value.length ? analystArticles.value : analystFallback
  return cards.slice(0, 4)
})

const articleRunLineage = computed(() => {
  if (state.routeContext.isHistorical && state.selectedHistory?.run_lineage) {
    return state.selectedHistory.run_lineage as Row
  }
  return ((state.articles?.run_lineage as Row | undefined) ?? store.runLineage.value ?? {}) as Row
})

const articleFinalPayload = computed(() => {
  if (state.routeContext.isHistorical && state.selectedHistory?.final) {
    return state.selectedHistory.final as Row
  }
  return {} as Row
})

const articleResearch = computed(() =>
  ((articleFinalPayload.value.research_article as Row | undefined) ??
    (state.articles?.research_article as Row | undefined) ??
    {}) as Row,
)

const articlePublish = computed(() =>
  ((articleFinalPayload.value.publish_article as Row | undefined) ??
    (state.articles?.publish_article as Row | undefined) ??
    {}) as Row,
)

const articleLlmResearch = computed(() => ((state.articles?.llm_research as Row | undefined) ?? {}) as Row)

const articleAnalystRows = computed(() => {
  const llmRows = (state.articles?.llm_analyst_articles as Row[] | undefined) ?? []
  const deterministicRows = (state.articles?.analyst_articles as Row[] | undefined) ?? []
  return (llmRows.length ? llmRows : deterministicRows).slice(0, 4)
})

const articleHistoryRows = computed(() => {
  const rows = ((state.articleHistory?.items as Row[] | undefined) ?? []).slice(0, 20)
  if (rows.length) return rows
  const latest = ((state.runs?.latest as Row | undefined) ?? {}) as Row
  return latest.final_run_id ? [latest] : []
})

const historyPayload = computed(() => ((state.selectedHistory as Row | null) ?? {}) as Row)
const historyFinal = computed(() => ((historyPayload.value.final as Row | undefined) ?? {}) as Row)
const historyDecision = computed(() => ((historyFinal.value.decision_card as Row | undefined) ?? {}) as Row)
const historyAggregation = computed(() => ((historyFinal.value.aggregation_audit as Row | undefined) ?? {}) as Row)
const historyLineage = computed(() => ((historyPayload.value.run_lineage as Row | undefined) ?? {}) as Row)
const historyReports = computed(() => (((historyPayload.value.audit_reports as Row | undefined)?.reports as Row[] | undefined) ?? []))
const historyResearch = computed(() => ((historyFinal.value.research_article as Row | undefined) ?? {}) as Row)
const historyPublish = computed(() => ((historyFinal.value.publish_article as Row | undefined) ?? {}) as Row)
const historyLlm = computed(() => ((historyPayload.value.llm_research as Row | undefined) ?? {}) as Row)
const historyAnalysts = computed(() => ((historyPayload.value.analyst_articles as Row[] | undefined) ?? (historyFinal.value.analyst_articles as Row[] | undefined) ?? []).slice(0, 4))
const historyLineageEntries = computed(() =>
  Object.entries(historyLineage.value)
    .filter(([, value]) => value !== undefined && value !== null && typeof value !== 'object')
    .map(([key, value]) => ({ key, value })),
)

const articleStatusText = computed(() => {
  const publishStatus = articlePublish.value.safe_to_publish === true ? 'published' : 'draft'
  const fallback = articleFinalPayload.value.fallback_used === true ? 'fallback generated' : publishStatus
  return text(articleFinalPayload.value.article_status ?? articlePublish.value.status ?? fallback, publishStatus)
})

const articleRuntimeMode = computed(() =>
  text(
    articleFinalPayload.value.runtime_mode ??
      articleLlmResearch.value.runtime_mode ??
      articleRunLineage.value.runtime_mode,
    'deterministic',
  ),
)

const articleEvidenceCitations = computed(() => {
  const ids = new Set<string>()
  collectEvidenceIds(articleResearch.value, ids)
  collectEvidenceIds(articlePublish.value, ids)
  collectEvidenceIds(articleLlmResearch.value, ids)
  for (const item of articleAnalystRows.value) collectEvidenceIds(item, ids)
  return [...ids].slice(0, 36).map((id) => {
    const evidence = evidenceItems.value.find((item) => String(item.evidence_id ?? '') === id)
    return { id, evidence }
  })
})

const overviewSupportDrivers = computed(() => asList(aggregation.value.support_drivers).slice(0, 8) as Row[])
const overviewPressureDrivers = computed(() => asList(aggregation.value.pressure_drivers).slice(0, 8) as Row[])
const overviewScoreComponents = computed(() => ((aggregation.value.score_components as Row | undefined) ?? {}) as Row)
const overviewScoreNormalization = computed(() => ((aggregation.value.score_normalization as Row | undefined) ?? {}) as Row)
const overviewRunLineage = computed(() => ((state.overview?.run_lineage as Row | undefined) ?? store.runLineage.value ?? {}) as Row)
const overviewDataBoundary = computed(() => {
  const article = (state.overview?.research_article as Row | undefined) ?? {}
  return asList(article.data_boundary).map((item) => text(item)).slice(0, 6)
})
const overviewWatchRows = computed(() => [
  ...invalidationRules.value.slice(0, 3).map((rule) => ({ kind: 'invalidation', rule })),
  ...confirmationRules.value.slice(0, 2).map((rule) => ({ kind: 'confirmation', rule })),
])
const invalidationRunLineage = computed(() => ((state.invalidation?.run_lineage as Row | undefined) ?? store.runLineage.value ?? {}) as Row)
const invalidationWorkbench = computed(() => ((state.invalidation ?? {}) as Row))
const hasInvalidationWorkbench = computed(() => text(invalidationWorkbench.value.schema_version, '') === 'p45.invalidation_workbench.v2')
const workbenchCurrentThesis = computed(() => ((invalidationWorkbench.value.current_thesis as Row | undefined) ?? {}) as Row)
const workbenchScores = computed(() => ((invalidationWorkbench.value.scores as Row | undefined) ?? {}) as Row)
const workbenchBtcResponse = computed(() => ((invalidationWorkbench.value.btc_response as Row | undefined) ?? {}) as Row)
const workbenchPriceAcceptance = computed(() => ((workbenchBtcResponse.value.price_acceptance as Row | undefined) ?? {}) as Row)
const workbenchResidual = computed(() => ((workbenchBtcResponse.value.residual as Row | undefined) ?? {}) as Row)
const workbenchMicroResponse = computed(() => ((workbenchBtcResponse.value.micro_response as Row | undefined) ?? {}) as Row)
const workbenchRuleGroups = computed(() => ((invalidationWorkbench.value.rule_groups as Row | undefined) ?? {}) as Row)
const workbenchEvidenceMatrix = computed(() => asList(invalidationWorkbench.value.module_evidence_matrix).slice(0, 30) as Row[])
const workbenchTimeline = computed(() => asList(invalidationWorkbench.value.timeline).slice(0, 20) as Row[])
const workbenchTriggeredRules = computed(() => asList(invalidationWorkbench.value.triggered_rules).slice(0, 8) as Row[])
const workbenchArmedRules = computed(() => asList(invalidationWorkbench.value.armed_rules).slice(0, 8) as Row[])
const workbenchBlockedRules = computed(() => asList(invalidationWorkbench.value.blocked_rules).slice(0, 8) as Row[])
const workbenchConfirmationLane = computed(() => [
  ...asList(workbenchRuleGroups.value.confirm_current_view),
  ...asList(workbenchRuleGroups.value.upgrade_scenarios),
] as Row[])
const workbenchInvalidationLane = computed(() => [
  ...asList(workbenchRuleGroups.value.refute_current_view),
  ...asList(workbenchRuleGroups.value.break_neutral_scenarios),
  ...asList(workbenchRuleGroups.value.downgrade_scenarios),
] as Row[])
const invalidationStats = computed(() => ({
  invalidation: invalidationRules.value.length,
  confirmation: confirmationRules.value.length,
  finalView: text(workbenchCurrentThesis.value.btc_direction ?? state.invalidation?.final_view ?? state.dashboard?.final_view, 'watch'),
  horizonCount: horizons.value.length,
}))
const fullscreenPages = new Set<PageId>(['evidence', 'article', 'quality', 'logs', 'history', 'source', 'radar'])
const pageTitle = computed(() => {
  const labels: Record<PageId, string> = {
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
  }
  return labels[activePage.value] ?? 'Dashboard'
})
const routeModeLabel = computed(() => (state.routeContext.isHistorical ? 'history replay' : 'latest run'))
const pageShellClass = computed(() => ({
  'drawer-closed': !drawerOpen.value,
  'page-fullscreen': pageFullscreen.value,
}))

onMounted(async () => {
  applyRouteFromUrl()
  loadRadarLayout()
  loadEventAlertPosition()
  loadEventAlertMute()
  loadEventWindowVisibilityState()
  eventAlertClockTimer = window.setInterval(() => {
    eventAlertNowMs.value = Date.now()
  }, 1000)
  eventWindowLiveTimer = window.setInterval(() => {
    void refreshEventWindowLive()
  }, 15000)
  window.addEventListener('keydown', handleGlobalKeydown)
  window.addEventListener('popstate', applyRouteFromUrl)
  await store.refreshLatest()
  const restoredJob = await store.resumeActiveRunJob()
  if (restoredJob && state.running) activePage.value = 'logs'
  await hydrateRouteSelection()
  await ensureDefaultRadarDetail()
  await nextTick()
})

watch(activePage, async (page) => {
  if (!syncingRoute) syncRouteToUrl()
  if (page === 'radar') await ensureDefaultRadarDetail()
  if (page === 'eventWatchtower') await refreshEventWindowLive()
})

function signedDirection(score: number) {
  if (!Number.isFinite(score) || Math.abs(score) < 0.1) return 'neutral'
  return score > 0 ? 'bullish' : 'bearish'
}

watch(
  () => ({
    final: state.routeContext.final_run_id,
    pack: state.routeContext.pack_id,
    module: state.routeContext.module_id,
    evidence: state.routeContext.evidence_id,
    source: state.routeContext.source_id,
    analyst: state.routeContext.analyst_id,
    historical: state.routeContext.isHistorical,
    fullscreen: pageFullscreen.value,
  }),
  () => {
    if (!syncingRoute) syncRouteToUrl()
  },
)

onBeforeUnmount(() => {
  stopDrag()
  if (eventAlertClockTimer) window.clearInterval(eventAlertClockTimer)
  if (eventWindowLiveTimer) window.clearInterval(eventWindowLiveTimer)
  window.removeEventListener('keydown', handleGlobalKeydown)
  window.removeEventListener('popstate', applyRouteFromUrl)
})

async function refreshEventWindowLive() {
  if (eventWindowLiveRefreshInFlight || state.routeContext.isHistorical) return
  eventWindowLiveRefreshInFlight = true
  try {
    await store.refreshEventWindowLatest()
  } finally {
    eventWindowLiveRefreshInFlight = false
  }
}

function text(value: unknown, fallback = '-') {
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value === 'number') return Number.isInteger(value) ? `${value}` : value.toFixed(4)
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return repairMojibake(String(value))
}

function parseEventDate(value: unknown) {
  const raw = text(value, '').trim()
  if (!raw) return null
  const dateOnly = raw.match(/^\d{4}-\d{2}-\d{2}/)?.[0]
  const parsed = new Date(raw)
  if (Number.isFinite(parsed.getTime())) return parsed
  if (dateOnly) {
    const normalized = new Date(`${dateOnly}T00:00:00Z`)
    if (Number.isFinite(normalized.getTime())) return normalized
  }
  return null
}

function eventShortLabel(event: Row) {
  const eventType = text(event.event_type ?? event.type ?? event.category, 'event').toUpperCase()
  if (eventType.includes('FOMC')) return 'FOMC'
  if (eventType.includes('NFP') || eventType.includes('PAYROLL')) return 'NFP'
  if (eventType.includes('PCE')) return 'PCE'
  if (eventType.includes('CPI')) return 'CPI'
  if (eventType.includes('SPEECH')) return 'FED'
  return eventType.replace(/[^A-Z0-9]/g, '').slice(0, 4) || 'EVT'
}

function eventImportanceRank(event: Row) {
  const value = text(event.importance ?? event.impact ?? event.level, '').toLowerCase()
  if (['critical', 'red', 'high'].some((key) => value.includes(key))) return 3
  if (['medium', 'yellow', 'watch', 'mixed'].some((key) => value.includes(key))) return 2
  if (['low', 'normal'].some((key) => value.includes(key))) return 1
  return 0
}

function eventCalendarTone(event: Row) {
  const rank = eventImportanceRank(event)
  if (rank >= 3) return 'bear'
  if (rank === 2) return 'mixed'
  if (rank === 1) return 'bull'
  return 'quality'
}

function maskedSecret(enabled: unknown) {
  return enabled ? 'configured · ********' : 'not configured'
}

function hasSettingsKeyDraft(key: unknown) {
  return Boolean(String(settingsKeyInputs[String(key ?? '')] ?? '').trim())
}

function settingsKeyRowClass(row: { enabled: boolean; status: string }) {
  if (row.enabled) return 'bull'
  if (row.status === 'missing_required' || row.status === 'provider_locked') return 'mixed'
  return 'neutral'
}

async function saveSettingsKey(row: { key: string; provider: string }) {
  const key = String(row.key ?? '')
  const value = String(settingsKeyInputs[key] ?? '').trim()
  if (!key || !value) {
    settingsKeyError.value = 'Enter a key before saving.'
    settingsKeyMessage.value = ''
    return
  }
  settingsKeySaving.value = key
  settingsKeyError.value = ''
  settingsKeyMessage.value = ''
  try {
    await api.updateSettingsEnv({ [key]: value })
    settingsKeyInputs[key] = ''
    settingsKeyMessage.value = `${row.provider} saved · settings reloaded`
    await store.refreshLatest()
  } catch (err) {
    settingsKeyError.value = err instanceof Error ? err.message : 'Failed to save settings.'
  } finally {
    settingsKeySaving.value = ''
  }
}

function providerHealthStatus(row: { health: Row }) {
  return text(row.health.status, 'untested')
}

function providerHealthMeta(row: { health: Row }) {
  const testedAt = text(row.health.last_tested_at, '')
  const latency = row.health.latency_ms === null || row.health.latency_ms === undefined ? '' : `${row.health.latency_ms}ms`
  const error = text(row.health.error_message, '')
  return [latency, testedAt ? timestampText(testedAt) : '', error].filter(Boolean).join(' · ') || 'not tested'
}

async function testSettingsProvider(row: { providerId: string; provider: string; supportsTest: boolean }) {
  if (!row.supportsTest) {
    settingsKeyError.value = `${row.provider} health test is not integrated yet.`
    settingsKeyMessage.value = ''
    return
  }
  settingsProviderTesting.value = row.providerId
  settingsKeyError.value = ''
  settingsKeyMessage.value = ''
  try {
    const result = await api.testProviderHealth(row.providerId)
    settingsKeyMessage.value = `${row.provider} test ${text(result.status, 'completed')}`
    await store.refreshLatest()
  } catch (err) {
    settingsKeyError.value = err instanceof Error ? err.message : 'Provider test failed.'
  } finally {
    settingsProviderTesting.value = ''
  }
}

function settingSourceLabel(value: unknown, fallback = '.env / default') {
  return value === null || value === undefined || value === '' ? 'default' : fallback
}

function repairMojibake(value: string) {
  if (!/[ÃÂâåçèéïã¼½¿]/.test(value)) return value
  if ([...value].some((char) => char.charCodeAt(0) > 255)) return value
  try {
    const bytes = Uint8Array.from([...value].map((char) => char.charCodeAt(0)))
    const decoded = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
    return decoded.includes('\uFFFD') ? value : decoded
  } catch {
    return value
  }
}

function navigateTo(page: PageId, options: { keepEvidenceDetail?: boolean } = {}) {
  if (page === 'evidence' && !options.keepEvidenceDetail) {
    closeEvidenceDetail()
  }
  activePage.value = page
}

async function goDashboard() {
  pageFullscreen.value = false
  drawerOpen.value = true
  if (state.routeContext.isHistorical) {
    store.exitHistoryMode()
    state.routeContext.module_id = ''
    state.routeContext.evidence_id = ''
    state.routeContext.source_id = ''
    state.routeContext.analyst_id = ''
    await store.refreshLatest()
  }
  activePage.value = 'topology'
}

function closeDetailPage() {
  if (activePage.value === 'evidence' && state.selectedEvidenceDetail) {
    closeEvidenceDetail()
    return
  }
  goDashboard()
}

function togglePageFullscreen() {
  if (!fullscreenPages.has(activePage.value)) return
  pageFullscreen.value = !pageFullscreen.value
  if (pageFullscreen.value) drawerOpen.value = false
}

function syncRouteToUrl() {
  const params = new URLSearchParams()
  if (activePage.value !== 'topology') params.set('page', activePage.value)
  if (state.routeContext.final_run_id) params.set('final_run_id', state.routeContext.final_run_id)
  if (state.routeContext.pack_id) params.set('pack_id', state.routeContext.pack_id)
  if (state.routeContext.module_id) params.set('module_id', state.routeContext.module_id)
  if (state.routeContext.evidence_id) params.set('evidence_id', state.routeContext.evidence_id)
  if (state.routeContext.source_id) params.set('source_id', state.routeContext.source_id)
  if (state.routeContext.analyst_id) params.set('analyst_id', state.routeContext.analyst_id)
  if (state.routeContext.isHistorical) params.set('mode', 'history')
  if (pageFullscreen.value) params.set('fullscreen', '1')
  const query = params.toString()
  const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`
  if (nextUrl !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
    window.history.replaceState({}, '', nextUrl)
  }
}

function applyRouteFromUrl() {
  syncingRoute = true
  try {
    const params = new URLSearchParams(window.location.search)
    const requestedPage = params.get('page')
    if (requestedPage && validPageIds.has(requestedPage)) activePage.value = requestedPage as PageId
    state.routeContext.final_run_id = params.get('final_run_id') ?? state.routeContext.final_run_id
    state.routeContext.pack_id = params.get('pack_id') ?? state.routeContext.pack_id
    state.routeContext.module_id = params.get('module_id') ?? state.routeContext.module_id
    state.routeContext.evidence_id = params.get('evidence_id') ?? state.routeContext.evidence_id
    state.routeContext.source_id = params.get('source_id') ?? state.routeContext.source_id
    state.routeContext.analyst_id = params.get('analyst_id') ?? state.routeContext.analyst_id
    const historyCapablePage = ['history', 'article'].includes(String(requestedPage ?? activePage.value))
    state.routeContext.isHistorical = params.get('mode') === 'history' && historyCapablePage
    pageFullscreen.value = params.get('fullscreen') === '1'
    drawerOpen.value = !pageFullscreen.value
  } finally {
    syncingRoute = false
  }
}

async function hydrateRouteSelection() {
  const context = state.routeContext
  if (context.isHistorical && context.final_run_id) await store.loadHistory(context.final_run_id)
  if (context.module_id) {
    selectedModuleId.value = context.module_id
    await store.loadRadarDetail(context.module_id)
  }
  if (context.evidence_id) {
    selectedEvidenceId.value = context.evidence_id
    await store.loadEvidenceDetail(context.evidence_id)
  } else if (activePage.value === 'evidence') {
    closeEvidenceDetail()
  }
  if (context.source_id) {
    selectedSourceId.value = context.source_id
    await store.loadSourceDetail(context.source_id)
  }
}

function articleText(value: unknown, fallback = '-') {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const row = value as Row
    return text(row.body ?? row.article ?? row.executive_summary ?? row.summary ?? row.title, fallback)
  }
  return text(value, fallback)
}

function articleParagraphs(value: unknown, fallback = '-') {
  return articleText(value, fallback)
    .split(/\n+/)
    .map((line) => line.replace(/^#{1,4}\s*/, '').trim())
    .filter(Boolean)
    .slice(0, 18)
}

function collectEvidenceIds(value: unknown, ids: Set<string>) {
  if (!value) return
  if (typeof value === 'string') {
    for (const match of value.matchAll(/p3-score-[A-Za-z0-9_-]+(?:-[A-Za-z0-9_]+)*/g)) {
      ids.add(match[0])
    }
    return
  }
  if (Array.isArray(value)) {
    for (const item of value) collectEvidenceIds(item, ids)
    return
  }
  if (typeof value === 'object') {
    for (const item of Object.values(value as Row)) collectEvidenceIds(item, ids)
  }
}

function articleTitle(article: Row, fallback = 'P4.5 Research Article') {
  return text(article.title ?? article.headline, fallback)
}

function citationLabel(id: string, evidence?: Row) {
  return text(evidence?.metric_id ?? id.split('-').slice(-1)[0], id)
}

function citationMeta(evidence?: Row) {
  if (!evidence) return 'pending detail'
  return `${text(evidence.radar_module)} · score ${text(evidence.metric_effective_score ?? evidence.metric_score)} · ${text(evidence.source_id)}`
}

function evidenceTitle(item: Row) {
  return text(item.metric_name ?? metricLabel(item.metric_id), text(item.metric_id, 'metric'))
}

function evidenceBrief(item: Row) {
  return readableMetricText(item.p45_metric_brief ?? item.metric_explanation ?? item.score_reason ?? item.metric_id)
}

function evidenceDisplayDirection(item: Row) {
  return item.metric_self_direction ?? item.direction
}

function evidenceDirectionLabel(item: Row) {
  const selfDirection = item.metric_self_direction
  const compositeState = item.module_composite_state
  if (selfDirection && compositeState) {
    return `self ${text(selfDirection)}`
  }
  return text(evidenceDisplayDirection(item))
}

function evidenceCompositeLine(item: Row) {
  if (!item.module_composite_state && item.module_composite_score == null) return ''
  return `composite ${text(item.module_composite_state)} · ${text(item.module_composite_direction)} · contribution ${text(item.kline_composite_contribution)}`
}

function evidenceOneLine(item: Row) {
  const summary = evidenceBrief(item)
  if (!summary || summary === '-') return '等待指标说明'
  return summary
    .replace(/\s+/g, ' ')
    .replace(/语义规则=.*$/u, '')
    .trim()
}

function evidenceScoreLine(item: Row) {
  return `score ${text(item.metric_score)} · effective ${text(item.metric_effective_score)} · q ${text(item.quality_score)}`
}

function evidenceFreshnessLine(item: Row) {
  const status = item.freshness_display_status ?? item.freshness_status ?? item.business_recency_status
  const note = item.freshness_display_note ? ` | ${text(item.freshness_display_note)}` : ''
  return `${text(status)} | fresh ${text(item.freshness_minutes)}m | stale after ${text(item.stale_after_minutes)}m${note}`
}

function evidenceSourceLine(item: Row) {
  return `${text(item.source_id)} | ${text(item.source_run_id ?? item.collect_run_id)}`
}

function evidenceHorizonLine(item: Row) {
  return `${text(item.horizon_tags)} | duplicate ${text(item.duplicate_group_id)} | module weight ${text(item.module_weight)}`
}

function evidenceBadges(item: Row) {
  const badges = [text(item.run_mode, 'live'), text(item.role, 'signal')]
  if (item.fallback_used === true || item.fallback_reason) badges.push('fallback')
  if (item.is_stale === true || String(item.freshness_status ?? '').includes('stale')) badges.push('stale')
  if (item.available === false) badges.push('unavailable')
  if (item.evidence_tier) badges.push(text(item.evidence_tier))
  return badges.filter(Boolean).slice(0, 5)
}

function evidenceBadgeClass(value: unknown) {
  const badge = String(value ?? '').toLowerCase()
  if (badge.includes('fallback') || badge.includes('stale') || badge.includes('quality')) return 'quality'
  if (badge.includes('unavailable') || badge.includes('negative')) return 'bear'
  if (badge.includes('live') || badge.includes('exact')) return 'bull'
  return 'neutral'
}

function evidenceWeightLine(item: Row) {
  return `freshness ${text(item.freshness_weight)} | horizon ${text(item.horizon_weight)} | duplicate ${text(item.duplicate_adjustment)} | weight ${text(item.weight)}`
}

function openArticleCitation(id: string) {
  activePage.value = 'evidence'
  void openEvidenceDetail(id)
}

async function openArticleSnapshot(row: Row) {
  const finalRunId = String(row.final_run_id ?? '')
  if (!finalRunId) return
  await store.loadHistory(finalRunId)
  activePage.value = 'article'
}

async function openHistorySnapshot(row: Row) {
  const finalRunId = String(row.final_run_id ?? row.run_id ?? '')
  if (!finalRunId) return
  await store.loadHistory(finalRunId)
  activePage.value = 'history'
}

function exitArticleHistory() {
  store.exitHistoryMode()
  void store.refreshLatest()
}

function exitHistoryReplay() {
  store.exitHistoryMode()
  void store.refreshLatest()
}

function historyValidityText() {
  return 'Replay uses Signal Validity / Alert Validity / Confidence Calibration. It does not score call accuracy.'
}

function articleSnapshotClass(row: Row) {
  return directionClass(row.final_view ?? row.article_status ?? row.contract_status)
}

function articleSnapshotStatus(row: Row) {
  return `${text(row.article_status, 'snapshot')} · ${text(row.final_view_cn ?? row.final_view, 'final_view')}`
}

function driverReason(driver: Row) {
  return readableMetricText(driver.reason ?? driver.summary ?? driver.metric_id)
}

function driverContribution(driver: Row) {
  return text(driver.weighted_contribution ?? driver.contribution ?? driver.metric_effective_score)
}

async function openMetricEvidence(metricId: unknown) {
  const id = driverMetricId(metricId)
  const evidence = evidenceItems.value.find((item) => String(item.metric_id ?? '') === id)
  if (evidence?.evidence_id) {
    await openEvidenceDetail(String(evidence.evidence_id))
    return
  }
  activePage.value = 'evidence'
}

function normalizationText() {
  const normalization = overviewScoreNormalization.value
  const explanation = readableMetricText(normalization.explanation)
  if (explanation) return explanation
  return 'Directional score is normalized by module weight, data quality, freshness, horizon and duplicate adjustment.'
}

function componentPercent(value: unknown) {
  const num = Number(value)
  if (!Number.isFinite(num)) return text(value)
  return `${Math.round(num * 100)}%`
}

function ruleSummary(rule: Row) {
  return `${text(rule.horizon)} · ${text(ruleAction(rule))} · ${readableMetricText(rule.reason)}`
}

function metricValue(metricId: string) {
  const item = evidenceItems.value.find((entry) => String(entry.metric_id ?? '') === metricId)
  return item?.value ?? item?.current_value
}

function firstText(value: unknown, fallback = '-') {
  if (Array.isArray(value)) return text(value[0], fallback)
  return text(value, fallback)
}

function daysText(value: unknown) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  if (Math.abs(num) < 1) return `${(num * 24).toFixed(1)}h`
  return `${num.toFixed(1)}d`
}

function compactNumber(value: unknown) {
  const num = Number(value)
  if (!Number.isFinite(num)) return text(value)
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(num)
}

function eventPayload(row: Row) {
  return ((row.payload as Row | undefined) ?? {}) as Row
}

function eventType(row: Row) {
  const payload = eventPayload(row)
  return text(payload.event_type ?? payload.type ?? row.feature_id, 'event')
}

function eventName(row: Row) {
  const payload = eventPayload(row)
  return text(payload.event_name ?? payload.name ?? payload.event_type, eventType(row))
}

function eventWindow(row: Row) {
  const payload = eventPayload(row)
  return text(payload.window ?? payload.event_phase, 'watch')
}

function eventLlmToneClass(value: unknown) {
  const tone = text(value, '').toLowerCase()
  if (tone.includes('hawk')) return 'mixed'
  if (tone.includes('dov')) return 'bull'
  if (tone.includes('not_policy')) return 'quality'
  if (tone.includes('ambiguous') || tone.includes('data') || tone.includes('balanced')) return 'blue'
  return ''
}

function sourceModeTone(value: unknown) {
  const mode = text(value, '').toLowerCase()
  if (mode.includes('blocked') || mode.includes('failed') || mode.includes('degraded')) return 'bear'
  if (mode.includes('partial_live') || mode.includes('functional')) return 'bull'
  if (mode.includes('partial') || mode.includes('fallback') || mode.includes('proxy')) return 'mixed'
  if (mode.includes('live')) return 'bull'
  return 'quality'
}

function daemonHealthTone(value: unknown) {
  const mode = text(value, '').toLowerCase()
  if (mode.includes('failed')) return 'bear'
  if (mode.includes('stale')) return 'mixed'
  if (mode.includes('degraded')) return 'warning'
  if (mode.includes('paused')) return 'quality'
  if (mode.includes('healthy') || mode.includes('running')) return 'bull'
  return 'quality'
}

function eventAuditStatusTone(value: unknown) {
  const status = text(value, '').toLowerCase()
  if (status.includes('pass') || status.includes('true') || status.includes('ok')) return 'bull'
  if (status.includes('stale') || status.includes('partial') || status.includes('pending')) return 'mixed'
  if (status.includes('fail') || status.includes('false') || status.includes('missing')) return 'bear'
  return 'quality'
}

function eventLlmConfidence(item: Row) {
  return text(item.tone_confidence ?? item.confidence ?? item.confidence_score, '-')
}

function eventLlmSummary(item: Row) {
  return text(item.summary_cn ?? item.summary_zh ?? item.summary ?? item.reason_cn ?? item.reason, '暂无 LLM 中文摘要。')
}

function eventLlmBoundaryPass(item: Row) {
  if (typeof item.boundary_pass === 'boolean') return item.boundary_pass
  if (typeof item.boundary === 'boolean') return item.boundary
  return text(eventWindowDirectScoreImpact.value, 'false') === 'false'
}

function eventAction(row: Row) {
  const payload = eventPayload(row)
  return firstText(payload.window_action ?? payload.action ?? payload.publish_impact, 'monitor')
}

function eventSourceStatus(row: Row) {
  const payload = eventPayload(row)
  const trace = ((payload.source_trace as Row | undefined) ?? {}) as Row
  return text(payload.source_resolution_status ?? trace.source_resolution_status ?? trace.event_source, 'source')
}

function eventDailyWatch(row: Row) {
  const payload = eventPayload(row)
  const daily = ((payload.daily_watch as Row | undefined) ?? {}) as Row
  const active = daily.active === true ? 'daily watch' : 'monitor'
  return `${active} · ${text(daily.change_summary, 'no new change')}`
}

function eventQuality(row: Row) {
  const payload = eventPayload(row)
  return text(payload.quality_score ?? payload.quality)
}

function alertTone(value: unknown) {
  const level = String(value ?? '').toLowerCase()
  if (level.includes('critical')) return 'bear'
  if (level.includes('high')) return 'mixed'
  if (level.includes('warning') || level.includes('watch')) return 'mixed'
  if (level.includes('info')) return 'neutral'
  return 'quality'
}

function cooldownText(value: unknown) {
  if (!value) return 'no cooldown'
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return text(value)
  return `cooldown until ${date.toLocaleString()}`
}

function ruleAction(rule: Row) {
  const action = rule.action_if_triggered
  if (action && typeof action === 'object' && !Array.isArray(action)) {
    const row = action as Row
    return `${text(row.from, 'current')} -> ${text(row.to, 'watch')}`
  }
  return text(action, 'watch')
}

function ruleConditions(rule: Row) {
  const conditions = Array.isArray(rule.conditions) ? (rule.conditions as Row[]) : []
  const expression = conditions
    .map((condition) =>
      `${text(condition.metric_id)}.${text(condition.field, 'value')} ${text(condition.op, '=')} ${text(condition.value)}`,
    )
    .join(` ${text(rule.operator, 'AND')} `)
  return expression || 'waiting for structured conditions'
}

function ruleMetricIds(rule: Row) {
  const ids = Array.isArray(rule.metric_ids) ? rule.metric_ids : []
  if (ids.length) return ids.map((id) => String(id)).filter(Boolean)
  const conditions = Array.isArray(rule.conditions) ? (rule.conditions as Row[]) : []
  return [...new Set(conditions.map((condition) => String(condition.metric_id ?? '')).filter(Boolean))]
}

function metricEvidence(metricId: unknown) {
  const id = String(metricId ?? '')
  return evidenceItems.value.find((item) => String(item.metric_id ?? '') === id)
}

function ruleConditionStatus(condition: Row) {
  const evidence = metricEvidence(condition.metric_id)
  const field = String(condition.field ?? 'value')
  const current = Number((evidence as Row | undefined)?.[field] ?? evidence?.metric_score ?? evidence?.value)
  const threshold = Number(condition.value)
  const op = String(condition.op ?? '')
  if (!Number.isFinite(current) || !Number.isFinite(threshold)) return 'waiting'
  if (op === '>') return current > threshold ? 'met' : 'not met'
  if (op === '>=') return current >= threshold ? 'met' : 'not met'
  if (op === '<') return current < threshold ? 'met' : 'not met'
  if (op === '<=') return current <= threshold ? 'met' : 'not met'
  if (op === '==') return current === threshold ? 'met' : 'not met'
  return 'watch'
}

function ruleProgress(rule: Row) {
  const conditions = Array.isArray(rule.conditions) ? (rule.conditions as Row[]) : []
  if (!conditions.length) return 'waiting conditions'
  const met = conditions.filter((condition) => ruleConditionStatus(condition) === 'met').length
  return `${met}/${conditions.length} conditions met`
}

function sourceStatusClass(value: unknown) {
  const status = String(value ?? '').toLowerCase()
  if (status.includes('challenge') || status.includes('captcha') || status.includes('reauth') || status.includes('manual')) return 'mixed'
  if (status.includes('healthy') || status.includes('ok')) return 'bull'
  if (status.includes('archived') || status.includes('fallback')) return 'quality'
  if (status.includes('fail') || status.includes('error')) return 'bear'
  return 'neutral'
}

function sourceMeaning(value: unknown) {
  const status = String(value ?? '').toLowerCase()
  if (status.includes('403') || status.includes('forbidden')) return '可能被官方站点或页面防护拦截，需要 fallback 或人工验证。'
  if (status.includes('actual')) return '业务数据可能尚未发布，不能简单视为采集失败。'
  if (status.includes('challenge') || status.includes('captcha') || status.includes('human')) return '需要人工验证或半自动重新授权。'
  if (status.includes('timeout')) return '页面加载超时，优先检查网络、页面结构或 Playwright 等待策略。'
  if (status.includes('fallback')) return '当前链路存在 fallback，可审计但需要区分主源与替代源。'
  if (status.includes('healthy') || status.includes('fresh')) return '主源当前可用，freshness 与业务时效仍需结合判断。'
  return '按 source status、freshness policy 和 downstream evidence 共同判断。'
}

function freshnessPolicyRows(policy: Row) {
  return Object.entries(policy).map(([key, value]) => ({ key, value }))
}

function sourceId(row: Row) {
  return text(row.source_id ?? row.id ?? row.source, 'unknown-source')
}

function sourceAuthState(row: Row) {
  const content = JSON.stringify(row).toLowerCase()
  if (row.auth_state) return text(row.auth_state)
  if (row.manual_reauth_required || content.includes('manual_reauth_required')) return 'required'
  if (row.requires_human_verified_profile || content.includes('human challenge') || content.includes('captcha')) return 'required'
  if (content.includes('valid') || content.includes('verified')) return 'valid'
  return 'unknown'
}

function sourceAutomationMode(row: Row) {
  if (row.automation_mode) return text(row.automation_mode)
  if (isSemiAutomatedSource(row)) return 'semi_automated'
  return 'auto'
}

function sourceProfileDir(row: Row) {
  const metadata = (row.metadata as Row | undefined) ?? {}
  return text(row.profile_dir ?? metadata.profile_dir, sourceId(row).includes('bitbo') ? 'cache/playwright-bitbo-profile' : '-')
}

function sourceLastVerified(row: Row) {
  const metadata = (row.metadata as Row | undefined) ?? {}
  return row.last_verified_at ?? metadata.last_verified_at ?? row.verified_at ?? '-'
}

function isSemiAutomatedSource(row: Row) {
  const content = JSON.stringify(row).toLowerCase()
  const id = sourceId(row).toLowerCase()
  return (
    id.includes('bitbo') ||
    id.includes('sth-lth') ||
    Boolean(row.requires_human_verified_profile) ||
    Boolean(row.manual_reauth_required) ||
    content.includes('human challenge') ||
    content.includes('captcha') ||
    content.includes('precondition required') ||
    content.includes('reauth')
  )
}

function sourceManualSummary(row: Row) {
  const auth = sourceAuthState(row)
  if (auth === 'required') return '需要人工验证一次，验证后的浏览器 profile 会继续服务自动采集。'
  if (auth === 'valid') return '人工验证 profile 当前可用，后续可自动重试采集。'
  return '等待后端 auth-state，若遇到 Human Challenge 可从这里打开验证窗口。'
}

function sourceActionStatus(result: Row) {
  if (!Object.keys(result).length) return 'No manual action has been triggered in this view.'
  return text(result.status ?? result.auth_state ?? result.message ?? result.error, 'action result received')
}

function sourceRunDuration(run: Row) {
  const started = new Date(String(run.started_at ?? ''))
  const completed = new Date(String(run.completed_at ?? ''))
  if (!Number.isNaN(started.getTime()) && !Number.isNaN(completed.getTime())) {
    return `${Math.max(0, completed.getTime() - started.getTime())} ms`
  }
  return text(run.latency_ms, 'latency pending')
}

function metricValueText(metric: Row) {
  return `${text(metric.metric_id)} = ${text(metric.value)} · q ${text(metric.quality_score)}`
}

function qualityCheckRows(limit = 18) {
  return Object.entries(qualityChecks.value)
    .map(([key, value]) => ({ key, value }))
    .slice(0, limit)
}

function warningSummary(warning: Row) {
  return `${text(warning.code, 'warning')} · count ${text(warning.count, '-')}`
}

function alertUpdatedText(value: unknown) {
  if (!value) return 'updated time pending'
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return text(value)
  return `updated ${date.toLocaleString()}`
}

function openAlertEvidence(alert: Row) {
  const level = String(alert.level ?? '').toLowerCase()
  evidenceModuleFilter.value = 'all'
  if (level.includes('critical') || level.includes('high') || level.includes('warning')) {
    evidenceBucketFilter.value = 'negative'
  } else {
    evidenceBucketFilter.value = 'all'
  }
  activePage.value = 'evidence'
}

function openAlertRunLogs(alert: Row) {
  const runId = String(alert.run_id ?? '')
  if (runId) state.routeContext.final_run_id = String(alertRunLineage.value.final_run_id ?? state.routeContext.final_run_id)
  activePage.value = 'logs'
}

function statusClass(value: unknown) {
  const status = String(value ?? '').toLowerCase()
  if (status.includes('context') || status.includes('discounted')) return 'quality'
  if (status.includes('confirmed') || status.includes('triggered') || status.includes('accepted')) return 'bull'
  if (status.includes('refuted') || status.includes('rejected') || status.includes('blocked')) return 'bear'
  if (status.includes('conflict') || status.includes('armed') || status.includes('arming') || status.includes('watch')) return 'mixed'
  if (status.includes('stale') || status.includes('missing') || status.includes('expired')) return 'quality'
  if (status.includes('completed') && status.includes('error')) return 'quality'
  if (status.includes('complete') || status.includes('ok') || status.includes('pass')) return 'bull'
  if (status.includes('running') || status.includes('pending')) return 'mixed'
  if (status.includes('fail') || status.includes('error')) return 'bear'
  return 'neutral'
}

function normalizedStageText(stage: Row) {
  return `${stage.stage_id ?? ''} ${stage.phase ?? ''} ${stage.label ?? ''}`.toLowerCase()
}

function findPipelineStage(matchers: string[]) {
  const normalizedMatchers = matchers.map((item) => item.toLowerCase())
  return stages.value.find((stage) => {
    const content = normalizedStageText(stage)
    return normalizedMatchers.some((matcher) => content.includes(matcher))
  }) as Row | undefined
}

function completedLike(stage: Row | undefined) {
  const status = String(stage?.status ?? '').toLowerCase()
  return status.includes('complete') || status.includes('ok') || status.includes('pass') || status.includes('skipped')
}

function pipelineActiveIndex() {
  if (!state.running) return -1
  const firstOpen = pipelineDefs.findIndex((definition) => !completedLike(findPipelineStage(definition.match)))
  return firstOpen >= 0 ? firstOpen : pipelineDefs.length - 1
}

function pipelineStageState(stage: Row | undefined, index: number) {
  const status = String(stage?.status ?? '').toLowerCase()
  if (status.includes('fail')) return 'failed'
  if (status.includes('completed_with_llm_errors') || (status.includes('completed') && status.includes('error'))) return 'degraded'
  if (state.running && index === pipelineActiveIndex()) return 'active'
  if (status.includes('running') || status.includes('pending')) return 'active'
  if (completedLike(stage)) return 'done'
  if (status.includes('error')) return 'degraded'
  return 'waiting'
}

function pipelineStateIcon(stateName: string) {
  if (stateName === 'done') return '✓'
  if (stateName === 'active') return '◌'
  if (stateName === 'degraded') return '!'
  if (stateName === 'failed') return '×'
  return '·'
}

function pipelineRunId(runKey: string, stage: Row | undefined) {
  return text(stage?.run_id ?? latestRun.value[runKey] ?? store.runLineage.value?.[runKey], 'pending')
}

function shortRunId(value: unknown) {
  const id = text(value, 'pending')
  return id.length > 22 ? `${id.slice(0, 20)}...` : id
}

function openPipelineStage(node: Row) {
  const report = ((node.report as Row | undefined) ?? {}) as Row
  if (report.file_url || report.relative_path || report.filename) openReport(report)
}

function stageNote(stage: Row) {
  const status = String(stage.status ?? '').toLowerCase()
  if (status.includes('skipped')) return 'Stage skipped by run execution profile; deterministic decision remains available.'
  if (status.includes('completed') && status.includes('error')) return '非阻塞降级: LLM appendix has degradation; main artifacts remain auditable.'
  if (status.includes('complete')) return 'Stage completed and artifacts are included in this run lineage.'
  if (status.includes('running')) return 'Stage is running; waiting for backend status refresh.'
  if (status.includes('fail')) return text(stage.error ?? stage.message, 'Stage failed; check backend logs.')
  return text(stage.message ?? stage.note, 'Waiting for stage status.')
}

function stageId(stage: Row) {
  return text(stage.stage_id ?? stage.phase ?? stage.label, 'stage')
}

function stageScope(stage: Row) {
  const parts = [
    stage.source_id ? `source ${text(stage.source_id)}` : '',
    stage.module_id ? `module ${text(stage.module_id)}` : '',
    stage.metric_id ? `metric ${text(stage.metric_id)}` : '',
    stage.error_code ? `error ${text(stage.error_code)}` : '',
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : 'scope included when backend reports source/module/metric'
}

function stageArtifactLabel(stage: Row) {
  const report = stageReport(stage)
  if (report.relative_path || report.filename || report.file_url) return reportTitle(report)
  const id = stageId(stage)
  if (id.includes('p1')) return 'P1 数据采集审计'
  if (id.includes('p2')) return 'P2 Radar 质检报告'
  if (id.includes('p3')) return 'P3 算法审计报告'
  if (id.includes('llm')) return 'P4.5 研究报告 · LLM appendix'
  if (id.includes('p45')) return 'P4.5 研究报告'
  return 'artifact pending'
}

function stageNeedsManualAction(stage: Row) {
  const content = JSON.stringify(stage).toLowerCase()
  return (
    content.includes('human challenge') ||
    content.includes('captcha') ||
    content.includes('manual_reauth_required') ||
    content.includes('precondition required') ||
    content.includes('reauth')
  )
}

function stageManualSourceId(stage: Row) {
  return text(stage.source_id ?? stage.blocked_source_id ?? stage.manual_source_id, 'bitbo-sth-lth-realized-price')
}

function stageUpdatedText(stage: Row) {
  return timestampText(stage.updated_at ?? stage.completed_at ?? stage.created_at)
}

function reportTitle(report: Row) {
  const phase = String(report.phase ?? '').toLowerCase()
  const filename = String(report.filename ?? report.relative_path ?? '')
  if (phase === 'p1' || filename.includes('p1-')) return 'P1 数据采集审计'
  if (phase === 'p2' || filename.includes('p2-')) return 'P2 Radar 质检报告'
  if (phase === 'p3' || filename.includes('p3-')) return 'P3 算法审计报告'
  if (phase === 'p45' || filename.includes('p45-')) return 'P4.5 研究报告'
  return text(report.title ?? report.phase ?? report.filename, 'Audit Report')
}

function reportSize(value: unknown) {
  const size = Number(value)
  if (!Number.isFinite(size)) return '-'
  if (size > 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  if (size > 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${size} B`
}

function reportHref(report: Row) {
  const relativePath = String(report.relative_path ?? report.filename ?? '')
  if (relativePath) {
    const parts = relativePath.replace(/\\/g, '/').split('/').filter(Boolean)
    const reportsIndex = parts.findIndex((part) => part === 'reports')
    const reportParts = reportsIndex >= 0 ? parts.slice(reportsIndex + 1) : parts
    if (reportParts.length) {
      const backendOrigin =
        window.location.port === '8118' ? window.location.origin : `${window.location.protocol}//${window.location.hostname}:8118`
      return `${backendOrigin}/reports/${reportParts.map((part) => encodeURIComponent(part)).join('/')}`
    }
  }
  return String(report.file_url ?? '')
}

function openReport(report: Row) {
  const url = reportHref(report)
  if (url) window.open(url, '_blank', 'noopener,noreferrer')
}

function stageReport(stage: Row) {
  return ((stage.audit_report as Row | undefined) ?? {}) as Row
}

function reportUpdatedText(report: Row) {
  return timestampText(report.updated_at ?? report.created_at)
}

function timestampText(value: unknown) {
  if (!value) return 'time pending'
  if (typeof value === 'number') return new Date(value * 1000).toLocaleString()
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return text(value)
  return date.toLocaleString()
}

function issueText(issue: Row | string) {
  if (typeof issue === 'string') return issue
  return text(issue.message ?? issue.detail ?? issue.code ?? issue.error ?? issue)
}

function conflictSeverityClass(row: Row) {
  const severity = String(row.severity ?? row.conflict_severity ?? row.level ?? '').toLowerCase()
  const type = String(row.conflict_type ?? row.source_resolution ?? '').toLowerCase()
  if (severity.includes('high') || severity.includes('critical') || type.includes('value_conflict')) return 'bear'
  if (severity.includes('medium') || type.includes('update_lag') || row.fallback_used === true) return 'mixed'
  if (type.includes('definition') || type.includes('duplicate')) return 'quality'
  return 'neutral'
}

function conflictTypeLabel(row: Row) {
  const type = text(row.conflict_type ?? row.conflict_origin ?? row.source_resolution, 'source_conflict')
  if (type.includes('definition')) return '口径差异'
  if (type.includes('update')) return '更新时间差异'
  if (type.includes('value')) return '数值冲突'
  if (type.includes('fallback')) return 'Fallback 仲裁'
  if (type.includes('duplicate')) return '重复影响降权'
  return type
}

function conflictSourceList(row: Row) {
  const candidates = [
    ...asList(row.candidate_sources),
    ...asList(row.candidates).map((item) => (typeof item === 'object' ? (item as Row).source_id : item)),
    row.conflicting_source,
    row.fallback_source,
    row.cross_check_source,
  ]
  return [...new Set(candidates.map((item) => text(item)).filter((item) => item !== '-'))]
}

function conflictSelectedSource(row: Row) {
  return text(row.selected_source ?? row.primary_source ?? row.source_id, 'selected source pending')
}

function conflictReason(row: Row) {
  return text(
    row.selected_reason ??
      row.resolution_reason ??
      row.fallback_reason ??
      row.source_resolution ??
      'Selected by priority, freshness, quality and downstream scoring policy.',
  )
}

function conflictImpactText(row: Row) {
  const score = text(row.metric_effective_score ?? row.downstream_metric_effective_score ?? row.metric_score)
  const evidenceId = text(row.evidence_id ?? row.downstream_evidence_id, 'pending evidence')
  const boundary = conflictSeverityClass(row) === 'bear' ? '可能影响方向，需要校准源优先级。' : '作为 data boundary 展示，不直接视为采集失败。'
  return `${boundary} downstream score=${score}; evidence=${evidenceId}.`
}

function conflictMetricId(row: Row) {
  return text(row.metric_id ?? row.feature_id ?? row.group, 'metric')
}

function conflictEvidenceId(row: Row) {
  return text(row.evidence_id ?? row.downstream_evidence_id, '')
}

async function openConflictEvidence(row: Row) {
  const evidenceId = conflictEvidenceId(row)
  if (evidenceId) await openEvidenceDetail(evidenceId)
}

async function openConflictRadar(row: Row) {
  const moduleId = text(row.radar_module ?? row.module_id, '')
  if (moduleId) await openRadarDetail(moduleId)
}

function directionClass(value: unknown) {
  const direction = String(value ?? '').toLowerCase()
  if (
    direction.includes('bearish_but_improving') ||
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
    direction.includes('event_risk_locked')
  ) {
    return 'mixed'
  }
  if (direction.includes('event_neutral')) return 'neutral'
  if (direction.includes('bull')) return 'bull'
  if (direction.includes('bear')) return 'bear'
  if (direction.includes('quality') || direction.includes('fallback')) return 'quality'
  if (direction.includes('mixed') || direction.includes('watch')) return 'mixed'
  return 'neutral'
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function moduleLayoutKey(moduleId: string) {
  return moduleId || 'module'
}

function defaultPoint(index: number): LayoutPoint {
  return defaultLayoutPoints[index] ?? { x: 50, y: 50 }
}

function nodePoint(moduleId: string, index: number): LayoutPoint {
  return radarLayout[moduleLayoutKey(moduleId)] ?? defaultPoint(index)
}

function repelByActiveNode(moduleId: string, index: number, basePoint: LayoutPoint): LayoutPoint {
  const drag = dragging.value
  if (!drag || drag.moduleId === moduleLayoutKey(moduleId) || !drag.moved) return basePoint

  const activePoint = radarLayout[drag.moduleId]
  if (!activePoint) return basePoint

  const dx = basePoint.x - activePoint.x
  const dy = basePoint.y - activePoint.y
  const distance = Math.hypot(dx, dy)
  const influenceRadius = 28
  if (distance >= influenceRadius) return basePoint

  const unitX = distance > 0.1 ? dx / distance : basePoint.x >= 50 ? 1 : -1
  const unitY = distance > 0.1 ? dy / distance : basePoint.y >= 50 ? 1 : -1
  const btcDx = basePoint.x - 50
  const btcDy = basePoint.y - 50
  const btcDistance = Math.max(1, Math.hypot(btcDx, btcDy))
  const awayFromBtcX = btcDx / btcDistance
  const awayFromBtcY = btcDy / btcDistance
  const strength = ((influenceRadius - distance) / influenceRadius) * 9
  const defaultBase = defaultPoint(index)

  return {
    x: clamp(basePoint.x + (unitX * 0.72 + awayFromBtcX * 0.28) * strength, defaultBase.x - 10, defaultBase.x + 10),
    y: clamp(basePoint.y + (unitY * 0.72 + awayFromBtcY * 0.28) * strength, defaultBase.y - 10, defaultBase.y + 10),
  }
}

function displayNodePoint(moduleId: string, index: number): LayoutPoint {
  const point = nodePoint(moduleId, index)
  return repelByActiveNode(moduleId, index, point)
}

function nodeDistanceRatio(point: LayoutPoint) {
  const dx = point.x - 50
  const dy = point.y - 50
  return clamp(Math.hypot(dx, dy) / 58, 0, 1)
}

function nodeDepth(point: LayoutPoint) {
  const ratio = nodeDistanceRatio(point)
  return {
    scale: clamp(1.1 - ratio * 0.3, 0.78, 1.08),
    opacity: clamp(1 - ratio * 0.28, 0.62, 0.98),
    strokeWidth: clamp(4.2 - ratio * 2, 1.8, 3.6),
  }
}

function linkPath(point: LayoutPoint) {
  const startX = point.x * 10
  const startY = point.y * 6.2
  const endX = 500
  const endY = 310
  const bend = 0.42
  const controlX = startX + (endX - startX) * bend
  const controlY = startY + (endY - startY) * bend
  return `M${startX.toFixed(1)} ${startY.toFixed(1)} Q${controlX.toFixed(1)} ${controlY.toFixed(1)} ${endX} ${endY}`
}

function nodeStyle(moduleId: string, index: number) {
  const point = displayNodePoint(moduleId, index)
  const depth = nodeDepth(point)
  return {
    left: `${point.x}%`,
    top: `${point.y}%`,
    '--node-scale': depth.scale.toFixed(3),
    '--node-opacity': depth.opacity.toFixed(3),
  }
}

function nodeClass(node: { direction: string; index: number; module: Row }) {
  return [directionClass(node.direction), dragging.value?.moduleId === moduleLayoutKey(moduleName(node.module)) ? 'dragging' : '']
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
] as const

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
])

function isMeaningfulCompositeState(value: unknown) {
  const state = String(value ?? '').toLowerCase()
  if (!state || state === 'null' || state === 'undefined') return false
  return (
    MEANINGFUL_MODULE_STATES.has(state) ||
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
    state.includes('_untrusted')
  )
}

function moduleDisplayState(module: Row) {
  for (const key of DISPLAY_STATE_PRIORITY) {
    const value = module[key]
    if (
      (
        key === 'fund_flow_state' ||
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
        key === 'positioning_state'
      ) &&
      isMeaningfulCompositeState(value)
    ) {
      return String(value)
    }
    if (key === 'module_effective_direction' || key === 'module_direction') {
      return String(value ?? 'neutral')
    }
  }
  return 'neutral'
}

function moduleDisplayLabel(module: Row) {
  const state = moduleDisplayState(module).toLowerCase()
  const labels: Record<string, string> = {
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
  }
  return labels[state] ?? text(state || (module.module_effective_direction ?? module.module_direction), 'watch')
}

function moduleDisplayShortLabel(module: Row) {
  const state = moduleDisplayState(module).toLowerCase()
  const labels: Record<string, string> = {
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
  }
  return labels[state] ?? text(state || (module.module_effective_direction ?? module.module_direction), 'watch')
}

function moduleDisplayClass(module: Row) {
  const composite = moduleCompositeTone(module)
  if (composite !== 'legacy') return composite

  const state = moduleDisplayState(module).toLowerCase()
  if (
    [
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
    ].includes(state)
  ) {
    return 'mixed'
  }
  if (state === 'event_neutral') {
    return 'neutral'
  }
  if (['absorption_or_trapped_long', 'buy_pressure_rejected', 'long_flush_panic_risk'].includes(state)) {
    return 'bear'
  }
  if (['sell_absorption_or_trapped_short', 'sell_pressure_rejected'].includes(state)) {
    return 'bull'
  }
  if (['price_up_confirmed', 'short_covering_bounce', 'overheated_upside', 'short_squeeze_potential'].includes(state)) {
    return 'bull'
  }
  if (['price_down_confirmed', 'long_crowding_downside', 'deleveraging_downside'].includes(state)) {
    return 'bear'
  }
  if (['btc_broad_confirmed_uptrend', 'alt_beta_rotation'].includes(state)) {
    return 'bull'
  }
  if (state === 'macro_trend_confirmed_bullish') {
    return 'bull'
  }
  if (state === 'liquidity_tailwind_confirmed') {
    return 'bull'
  }
  if (['etf_demand_accelerating', 'etf_demand_confirmed', 'stablecoin_liquidity_tailwind', 'supply_squeeze_support', 'btc_accepting_flow_tailwind', 'btc_resisting_flow_headwind'].includes(state)) {
    return 'bull'
  }
  if (['broad_risk_off', 'macro_headwind_confirmed_bearish', 'liquidity_headwind_confirmed', 'etf_outflow_confirmed', 'stablecoin_liquidity_drain', 'exchange_supply_pressure', 'btc_rejecting_flow_tailwind'].includes(state)) {
    return 'bear'
  }
  if (['macro_neutral', 'liquidity_neutral', 'fund_flow_neutral'].includes(state)) {
    return 'neutral'
  }
  if (state === 'bearish_confirmation') {
    return 'bear'
  }
  return directionClass(state)
}

function moduleCompositeTone(module: Row) {
  const score = Number(module.module_effective_score ?? module.module_score ?? 0)
  const stage = text(module.signal_stage ?? module.stage, '').toLowerCase()
  const effectiveDirection = text(module.module_effective_direction ?? module.effective_direction, '').toLowerCase()
  const rawDirection = text(module.module_direction ?? module.direction, '').toLowerCase()
  const implication = text(module.btc_implication, '').toLowerCase()
  const state = moduleDisplayState(module).toLowerCase()
  const supportCount = asList(module.support_drivers).length
  const pressureCount = asList(module.pressure_drivers).length
  const conflictCount = asList(module.conflict_drivers).length
  const qualityCount = asList(module.data_quality_flags).length
  const freshness = text(module.freshness_state ?? module.participation_policy, '').toLowerCase()
  const hasQualityIssue =
    qualityCount > 0 ||
    freshness.includes('stale') ||
    freshness.includes('blocked') ||
    freshness.includes('fallback') ||
    state.includes('data_quality')

  if (hasQualityIssue) return 'quality'
  if (conflictCount > 0 || effectiveDirection.includes('conflict') || rawDirection.includes('conflict')) return 'mixed'

  const isWarningStage = stage.includes('early_warning') || stage.includes('fast_signal') || stage.includes('watch')
  const isConfirmedStage = stage.includes('confirmed')
  const pressureLeads = pressureCount > supportCount
  const supportLeads = supportCount > pressureCount
  const bearishAccepted = effectiveDirection.includes('bearish') || rawDirection.includes('bearish')
  const bullishAccepted = effectiveDirection.includes('bullish') || rawDirection.includes('bullish')
  const fragilePressure =
    implication.includes('fragile') ||
    implication.includes('rejected') ||
    implication.includes('weak') ||
    state.includes('fragility') ||
    state.includes('warning') ||
    state.includes('pressure')

  if (isConfirmedStage && bearishAccepted && score <= -0.08) return 'bear'
  if (isConfirmedStage && bullishAccepted && score >= 0.08) return 'bull'

  if (isWarningStage && pressureLeads) return 'mixed'
  if (isWarningStage && supportLeads && score >= 0.08) return 'bull'
  if (isWarningStage && supportLeads) return 'mixed'

  if (pressureLeads && (score <= -0.08 || fragilePressure)) return 'mixed'
  if (supportLeads && score >= 0.10) return 'bull'
  if (score <= -0.18 && pressureCount > 0) return 'bear'
  if (score >= 0.18 && supportCount > 0) return 'bull'
  if (Math.abs(score) < 0.08 && !pressureLeads && !supportLeads) return 'neutral'

  return 'legacy'
}

function moduleName(module: Row) {
  return String(module.radar_module ?? module.module_id ?? 'module')
}

function shortModuleName(module: Row) {
  return moduleName(module)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .slice(0, 28)
}

function moduleMeta(module: Row) {
  return moduleReadableSummary(module)
}

function moduleById(moduleId: string) {
  return store.radarModules.value.find((module) => moduleName(module) === moduleId) ?? {}
}

function defaultRadarModuleId() {
  const modules = store.radarModules.value
  return moduleName(modules.find((module) => moduleName(module) === 'macro_radar') ?? modules[0] ?? {})
}

async function ensureDefaultRadarDetail() {
  if (activePage.value !== 'radar' || radarDefaultLoading.value || state.selectedRadarDetail) return
  const moduleId = defaultRadarModuleId()
  if (!moduleId || moduleId === 'module') return
  radarDefaultLoading.value = true
  try {
    await openRadarDetail(moduleId)
  } finally {
    radarDefaultLoading.value = false
  }
}

function radarScopeMetrics() {
  return selectedRadarMetrics.value.slice(0, 18)
}

function radarMetricStrength(metric: Row) {
  return Math.abs(Number(metric.metric_effective_score ?? metric.metric_score ?? 0))
}

function radarMetricRail(side: 'left' | 'right') {
  return selectedRadarTopMetrics.value.filter((_, index) => (side === 'left' ? index % 2 === 0 : index % 2 === 1))
}

function radarMetricBarWidth(metric: Row) {
  const score = radarMetricStrength(metric)
  const width = Math.max(8, Math.min(100, (score / 0.1) * 100))
  return `${width}%`
}

function radarMetricCompactMeta(metric: Row) {
  const direction = text(metric.direction ?? metric.semantic_direction ?? metric.metric_direction, 'context')
  const score = text(metric.metric_effective_score ?? metric.metric_score)
  return `${direction} · score ${score}`
}

function radarMetricAngle(index: number, total: number) {
  const count = Math.max(total, 1)
  return -90 + (360 / count) * index
}

function radarMetricRadius(metric: Row) {
  const score = Math.abs(Number(metric.metric_effective_score ?? metric.metric_score ?? 0))
  const normalized = Math.min(1, score / 0.1)
  return 34 + (1 - normalized) * 22
}

function radarMetricPoint(metric: Row, index: number, total: number) {
  const angle = (radarMetricAngle(index, total) * Math.PI) / 180
  const radius = radarMetricRadius(metric)
  return {
    x: 50 + Math.cos(angle) * radius,
    y: 50 + Math.sin(angle) * radius,
  }
}

function radarSafePoint(metric: Row, index: number, total: number) {
  const point = radarMetricPoint(metric, index, total)
  return {
    x: Math.max(8, Math.min(92, point.x)),
    y: Math.max(12, Math.min(88, point.y)),
  }
}

function radarNodeStyle(metric: Row, index: number, total: number) {
  const point = radarSafePoint(metric, index, total)
  const quality = Number(metric.quality_score ?? 0.78)
  const scale = Math.max(0.78, Math.min(0.98, 0.7 + quality * 0.22))
  return {
    left: `${point.x}%`,
    top: `${point.y}%`,
    '--metric-scale': scale.toFixed(3),
  }
}

function radarLinkPath(metric: Row, index: number, total: number) {
  const safePoint = radarSafePoint(metric, index, total)
  const dx = safePoint.x - 50
  const dy = safePoint.y - 50
  const distance = Math.max(1, Math.sqrt(dx * dx + dy * dy))
  const ux = dx / distance
  const uy = dy / distance
  const startOffset = 13
  const endOffset = 3.6
  const startX = 50 + ux * startOffset
  const startY = 50 + uy * startOffset
  const endX = safePoint.x - ux * endOffset
  const endY = safePoint.y - uy * endOffset
  return `M${(startX * 10).toFixed(1)} ${(startY * 6.4).toFixed(1)} L${(endX * 10).toFixed(1)} ${(endY * 6.4).toFixed(1)}`
}

function radarMetricClass(metric: Row) {
  if (metric.fallback_used || metric.is_stale || metric.available === false) return 'quality'
  return directionClass(metric.direction ?? metric.score_bucket)
}

function radarMetricWidth(metric: Row) {
  const score = Math.abs(Number(metric.metric_effective_score ?? metric.metric_score ?? 0))
  return Math.max(1.4, Math.min(5.5, 1.8 + score * 42))
}

function radarMetricSummary(metric: Row) {
  if (metric.price_response_state || metric.flow_price_efficiency_state || metric.price_response_source) {
    return `Price response ${text(metric.price_response_state, 'unknown')} · efficiency ${text(metric.flow_price_efficiency_state, 'unknown')} · source ${text(metric.price_response_source, 'unknown')}. This is a confirmation layer, not a standalone bullish/bearish trigger.`
  }
  return readableMetricText(metric.p45_metric_brief ?? metric.metric_explanation ?? metric.score_reason ?? metric.metric_id)
}

function radarMetricValueScoreLine(metric: Row) {
  const value = metric.value ?? metric.current_value
  const score = metric.metric_effective_score ?? metric.metric_score
  return `value ${text(value)} · score ${text(score)}`
}

function hasTradeStructureStates(module: Row) {
  return moduleName(module) === 'trade_structure_flow' && Boolean(
    module.trade_structure_flow_v23 ||
    module.signal_stage ||
    module.multi_horizon ||
    module.scores ||
    module.trade_structure_state ||
    module.aggressive_flow_state ||
    module.price_response_state ||
    module.liquidation_state ||
    module.mempool_pressure_state ||
    module.stablecoin_liquidity_state
  )
}

function tradeStructureStateRows(module: Row) {
  const contract = tradeStructureFlowContract(module)
  return [
    ['stage', contract.signal_stage],
    ['state', contract.trade_structure_state],
    ['BTC', contract.btc_implication],
    ['aggressive', module.aggressive_flow_state],
    ['price', module.price_response_state],
    ['liquidation', module.liquidation_state],
    ['mempool', module.mempool_pressure_state],
    ['stablecoin', module.stablecoin_liquidity_state],
  ].filter((item) => item[1] != null && item[1] !== '')
}

function asRow(value: unknown): Row {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Row) : {}
}

function isBtcTotalStateModule(module: Row) {
  return moduleName(module) === 'btc_total_state'
}

function isDerivativesCrowdingModule(module: Row) {
  return moduleName(module) === 'derivatives_crowding'
}

function isTradeStructureFlowModule(module: Row) {
  return moduleName(module) === 'trade_structure_flow'
}

function derivativesCrowdingContract(module: Row) {
  const contract = asRow(module.derivatives_crowding_v25)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
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
  }
}

function derivativesCrowdingLayerCards(module: Row) {
  const contract = derivativesCrowdingContract(module)
  const funding = asRow(contract.states.funding)
  const oi = asRow(contract.states.open_interest)
  const positioning = asRow(contract.states.positioning)
  const liquidation = asRow(contract.states.liquidation)
  const response = asRow(contract.states.btc_response)
  const residual = asRow(contract.states.trend_acceptance)
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
  ]
}

function isOptionsVolatilityModule(module: Row) {
  return moduleName(module) === 'options_volatility'
}

function isEventPolicyModule(module: Row) {
  return moduleName(module) === 'event_policy'
}

function isCryptoBreadthModule(module: Row) {
  return moduleName(module) === 'crypto_breadth'
}

function isMacroRadarModule(module: Row) {
  return moduleName(module) === 'macro_radar'
}

function isDollarLiquidityModule(module: Row) {
  return moduleName(module) === 'dollar_liquidity'
}

function isTreasuryCreditModule(module: Row) {
  return moduleName(module) === 'treasury_credit'
}

function isFundFlowModule(module: Row) {
  return moduleName(module) === 'fund_flow'
}

function isBtcAdoptionModule(module: Row) {
  return moduleName(module) === 'btc_adoption'
}

function isAsiaRiskModule(module: Row) {
  return moduleName(module) === 'asia_risk'
}

function isKlineOrderflowModule(module: Row) {
  return moduleName(module) === 'kline_orderflow'
}

function isOnchainValuationModule(module: Row) {
  return moduleName(module) === 'onchain_valuation'
}

function derivativesCrowdingScopeText() {
  return 'Funding / OI here describe derivatives crowding, leverage heat and squeeze risk. BTC Total State reads them only with price_state as a composite short-term input.'
}

function btcTotalContract(module: Row) {
  const contract = asRow(module.btc_total_state_v2)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
  return {
    btc_short_term_state: pick('btc_short_term_state'),
    price_state: asRow(pick('price_state')),
    perp_state: asRow(pick('perp_state')),
    cycle_context: asRow(pick('cycle_context')),
    audit_context: asRow(pick('audit_context')),
    context_notes: asList(pick('context_notes')),
    audit_notes: asList(pick('audit_notes')),
  }
}

function btcTotalLayerCards(module: Row) {
  const contract = btcTotalContract(module)
  const price = contract.price_state
  const perp = contract.perp_state
  const cycle = contract.cycle_context
  const audit = contract.audit_context
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
  ]
}

function btcTotalBasisRows(value: unknown) {
  const basis = asRow(value)
  return Object.entries(basis)
    .filter(([, entry]) => entry !== null && entry !== undefined && entry !== '')
    .slice(0, 4)
}

function optionsVolatilityContract(module: Row) {
  const contract = asRow(module.options_volatility_v21)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
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
  }
}

function optionsVolatilityLayerCards(module: Row) {
  const contract = optionsVolatilityContract(module)
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
  ]
}

function eventPolicyDefaultTradeGate(): Row {
  return {
    allow_new_position: true,
    allow_add_position: true,
    allow_breakout_entry: true,
    allow_market_entry: true,
    position_size_multiplier: 1,
    require_wait_until_ts: null,
    reason_code: 'EVENT_NEUTRAL',
  }
}

function eventPolicyContract(module: Row) {
  const contract = asRow(module.event_policy_v21)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
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
  }
}

function boolGateText(value: unknown) {
  return value === false ? 'blocked' : 'allowed'
}

function eventPolicyGateRows(gate: Row) {
  return [
    ['new position', boolGateText(gate.allow_new_position)],
    ['add position', boolGateText(gate.allow_add_position)],
    ['breakout entry', boolGateText(gate.allow_breakout_entry)],
    ['market entry', boolGateText(gate.allow_market_entry)],
    ['size multiplier', gate.position_size_multiplier],
    ['reason', gate.reason_code],
  ].filter(([, value]) => value !== null && value !== undefined && value !== '')
}

function eventPolicyLayerCards(module: Row) {
  const contract = eventPolicyContract(module)
  const gate = contract.trade_gate
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
  ]
}

function cryptoBreadthContract(module: Row) {
  const contract = asRow(module.crypto_breadth_v3)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
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
  }
}

function cryptoBreadthLayerCards(module: Row) {
  const contract = cryptoBreadthContract(module)
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
  ]
}

function macroRadarContract(module: Row) {
  const contract = asRow(module.macro_radar_v3)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
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
  }
}

function macroRadarLayerCards(module: Row) {
  const contract = macroRadarContract(module)
  const btcRelativeMissingReason = contract.btc_relative_confirmation.missing_reason
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
  ]
}

function dollarLiquidityContract(module: Row) {
  const contract = asRow(module.dollar_liquidity_v21)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
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
  }
}

function dollarLiquidityLayerCards(module: Row) {
  const contract = dollarLiquidityContract(module)
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
  ]
}

function treasuryCreditContract(module: Row) {
  const contract = asRow(module.treasury_credit_v21)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
  const states = asRow(pick('states'))
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
  }
}

function treasuryCreditLayerCards(module: Row) {
  const contract = treasuryCreditContract(module)
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
  ]
}

function fundFlowContract(module: Row) {
  const contract = asRow(module.fund_flow_v22)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
  const states = asRow(pick('states'))
  const scores = asRow(pick('scores'))
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
  }
}

function fundFlowLayerCards(module: Row) {
  const contract = fundFlowContract(module)
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
  ]
}

function onchainValuationContract(module: Row) {
  const contract = asRow(module.onchain_valuation_v22)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
  const states = asRow(pick('states'))
  const scores = asRow(pick('scores'))
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
  }
}

function onchainValuationLayerCards(module: Row) {
  const contract = onchainValuationContract(module)
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
  ]
}

function btcAdoptionContract(module: Row) {
  const contract = asRow(module.btc_adoption_v23)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
  const states = asRow(pick('states'))
  const scores = asRow(pick('scores'))
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
  }
}

function btcAdoptionLayerCards(module: Row) {
  const contract = btcAdoptionContract(module)
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
  ]
}

function asiaRiskContract(module: Row) {
  const contract = asRow(module.asia_risk_v23)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
  const states = asRow(pick('states'))
  const scores = asRow(pick('scores'))
  const btcResponse = asRow(pick('btc_response'))
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
  }
}

function asiaRiskLayerCards(module: Row) {
  const contract = asiaRiskContract(module)
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
  ]
}

function klineOrderflowContract(module: Row) {
  const contract = asRow(module.kline_orderflow_v22)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
  const scores = asRow(pick('scores'))
  const keyLevels = asRow(pick('key_levels'))
  const drivers = asRow(pick('drivers'))
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
  }
}

function klineOrderflowLayerCards(module: Row) {
  const contract = klineOrderflowContract(module)
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
  ]
}

function tradeStructureFlowContract(module: Row) {
  const contract = asRow(module.trade_structure_flow_v23)
  const profile = asRow(module.module_semantic_profile)
  const pick = (key: string) => module[key] ?? contract[key] ?? profile[key]
  const scores = asRow(pick('scores'))
  const states = asRow(pick('states'))
  const multiHorizon = asRow(pick('multi_horizon'))
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
  }
}

function tradeStructureFlowLayerCards(module: Row) {
  const contract = tradeStructureFlowContract(module)
  const horizon5m = asRow(contract.multi_horizon['5m'])
  const horizon15m = asRow(contract.multi_horizon['15m'])
  const horizon1h = asRow(contract.multi_horizon['1h'])
  const liquidity = asRow(contract.states.liquidity)
  const aggressive = asRow(contract.states.aggressive_flow)
  const leverage = asRow(contract.states.leverage)
  const liquidation = asRow(contract.states.liquidation)
  const residual = asRow(contract.states.residual)
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
  ]
}

function radarMetricQualityLine(metric: Row) {
  const freshness = metric.is_stale ? 'stale' : text(metric.freshness_status ?? metric.business_recency_status, 'fresh')
  const fallback = metric.fallback_used ? 'fallback' : 'primary'
  return `${freshness} · ${fallback} · q ${text(metric.quality_score)}`
}

function selectRadarMetric(metric: Row) {
  selectedRadarMetricId.value = text(metric.metric_id)
}

async function openSelectedRadarEvidence(metric: Row) {
  const evidenceId = String(metric.evidence_id ?? '')
  if (evidenceId) {
    await openEvidenceDetail(evidenceId)
    return
  }
  await openMetricEvidence(metric.metric_id)
}

function directionText(value: unknown) {
  const direction = String(value ?? '').toLowerCase()
  if (direction.includes('bull')) return 'bullish'
  if (direction.includes('bear')) return 'bearish'
  if (direction.includes('mixed')) return 'mixed'
  if (direction.includes('neutral')) return 'neutral'
  return 'watch'
}

function moduleReadableSummary(module: Row) {
  const explanation = module.module_explanation ?? module.module_summary
  if (explanation) return text(explanation)
  const id = moduleName(module)
  const state = moduleDisplayState(module)
  const direction = directionText(state)
  const positive = Number(module.positive_metric_count ?? 0)
  const negative = Number(module.negative_metric_count ?? 0)
  const unavailable = Number(module.unavailable_metric_count ?? 0)
  const split = positive > 0 && negative > 0 ? ', with internal signal disagreement' : ''
  const boundary = unavailable > 0 ? ', with unavailable metrics as data boundary' : ''
  if (id === 'fund_flow' && String(module.fund_flow_state ?? '').toLowerCase() === 'bearish_but_improving') {
    return 'Fund flow is bearish but improving: ETF/stablecoin pressure remains, while exchange balance contraction provides marginal support.'
  }
  if (id === 'fund_flow') {
    const contract = fundFlowContract(module)
    return `Fund flow: ${text(contract.fund_flow_state, 'fund_flow_neutral')}; BTC implication ${text(contract.btc_implication, 'neutral')}; ETF ${text(contract.etf_demand.state, 'missing')}; exchange ${text(contract.exchange_supply.state, 'missing')}; BTC response ${text(contract.btc_response_confirmation.state, 'missing')}. This module confirms or refutes whether BTC accepts fund-flow tailwinds or headwinds.`
  }
  if (id === 'onchain_valuation') {
    const contract = onchainValuationContract(module)
    return `On-chain valuation: ${text(contract.onchain_valuation_state, 'onchain_neutral')}; stage ${text(contract.signal_stage, 'none')}; bias ${text(contract.module_bias, 'neutral')}; BTC ${text(contract.btc_implication, 'neutral')}. Slow regime and fast trend-delta are separated, with STH cost basis, SOPR and residual used for confirmation.`
  }
  if (id === 'btc_adoption') {
    const contract = btcAdoptionContract(module)
    return `BTC adoption: ${text(contract.btc_adoption_state, 'btc_adoption_neutral')}; stage ${text(contract.signal_stage, 'none')}; BTC ${text(contract.btc_implication, 'neutral')}. Fast, core and regime layers separate real settlement confirmation from raw activity, fee noise, hashrate and Lightning context.`
  }
  if (id === 'asia_risk') {
    const contract = asiaRiskContract(module)
    return `Asia risk: ${text(contract.asia_risk_state, 'asia_risk_neutral')}; stage ${text(contract.signal_stage, 'none')}; BTC ${text(contract.btc_implication, 'neutral')}. Risk pressure is context until Asia-session BTC response, VWAP/range and residual confirm or reject it.`
  }
  if (id === 'kline_orderflow') {
    const contract = klineOrderflowContract(module)
    return `Kline orderflow: ${text(contract.kline_orderflow_state, 'neutral')}; stage ${text(contract.signal_stage, 'none')}; BTC ${text(contract.btc_implication, 'neutral')}. Active taker flow is directional only when price structure, VWAP acceptance and residual confirm it.`
  }
  if (id === 'kline_orderflow' && String(module.trend_state ?? '').toLowerCase() === 'neutral_wait_confirm') {
    return 'Kline orderflow is waiting for confirmation: short-term scores lean positive, but the composite structure is not confirmed yet.'
  }
  if (id === 'derivatives_crowding') {
    const contract = derivativesCrowdingContract(module)
    if (contract.semantic_profile_version === 'p3.c60.derivatives_crowding.v2.5' || module.derivatives_crowding_v25) {
      return `Derivatives crowding: ${text(contract.derivatives_state, 'derivatives_neutral')}; stage ${text(contract.signal_stage, 'none')}; BTC ${text(contract.btc_implication, 'neutral')}. Direction is confirmed only when BTC response, trend prior and standardized residual accept the leveraged structure.`
    }
    const crowding = text(module.crowding_state, 'unknown')
    const heat = text(module.leverage_heat_state, 'unknown')
    const positioning = text(module.top_positioning_state ?? module.positioning_state, 'balanced')
    const squeeze = text(module.long_short_squeeze_risk, 'none')
    return `Derivatives crowding: ${crowding}; leverage heat ${heat}; positioning ${positioning}; squeeze risk ${squeeze}. Funding/OI are derivatives risk inputs here, not BTC Total State direction drivers.`
  }
  if (id === 'trade_structure_flow') {
    const contract = tradeStructureFlowContract(module)
    if (contract.semantic_profile_version === 'p3.c58.trade_structure_flow.v2.3' || module.trade_structure_flow_v23) {
      return `Trade structure flow: ${text(contract.trade_structure_state, 'trade_structure_neutral')}; stage ${text(contract.signal_stage, 'none')}; BTC ${text(contract.btc_implication, 'neutral')}. Direction is confirmed only when microstructure pressure, multi-horizon price acceptance and standardized residual align.`
    }
    if (module.trade_structure_summary) return text(module.trade_structure_summary)
    const state = text(module.trade_structure_state, 'mixed_structure')
    const aggressive = text(module.aggressive_flow_state, 'unknown')
    const price = text(module.price_response_state, 'unknown')
    const risk = text(module.risk_state, 'normal_context')
    return `Trade structure: ${state}; aggressive flow ${aggressive}; price response ${price}; risk ${risk}. Taker pressure is not a trend confirmation by itself.`
  }
  if (id === 'btc_total_state') {
    const contract = btcTotalContract(module)
    const price = asRow(contract.price_state)
    const perp = asRow(contract.perp_state)
    return `BTC total state: ${text(contract.btc_short_term_state, direction)}; price ${text(price.state, 'missing')}; perp ${text(perp.state, 'missing')}. Halving and block height are context/audit only.`
  }
  if (id === 'options_volatility') {
    const contract = optionsVolatilityContract(module)
    return `Options structure: ${text(contract.options_short_term_state, 'vol_neutral')}; risk ${text(contract.risk_score)}; trade hint ${text(contract.trade_permission_hint, 'normal')}. This module adjusts risk and confidence, not final direction.`
  }
  if (id === 'event_policy') {
    const contract = eventPolicyContract(module)
    const gate = contract.trade_gate
    return `Event gate: ${text(contract.event_short_term_state, 'event_neutral')}; phase ${text(contract.event_window_phase, 'neutral')}; lock ${text(contract.event_risk_lock_level, 'none')}; reason ${text(gate.reason_code, 'EVENT_NEUTRAL')}. This module controls trade permission, not final direction.`
  }
  if (id === 'crypto_breadth') {
    const contract = cryptoBreadthContract(module)
    return `Crypto breadth: ${text(contract.crypto_breadth_state, 'neutral_wait_confirm')}; BTC implication ${text(contract.btc_implication, 'neutral')}; breadth ${text(contract.breadth_participation.state, 'missing')}; diffusion ${text(contract.market_cap_diffusion.state, 'missing')}. This module confirms or refutes BTC trend quality.`
  }
  if (id === 'macro_radar') {
    const contract = macroRadarContract(module)
    return `Macro radar: ${text(contract.macro_trend_state, 'macro_neutral')}; BTC implication ${text(contract.btc_implication, 'neutral')}; rates ${text(contract.rates_pressure.state, 'missing')}; impulse ${text(contract.macro_impulse.state, 'missing')}; BTC relative ${text(contract.btc_relative_confirmation.state, 'missing')}. This module confirms or refutes BTC trend quality through macro context.`
  }
  if (id === 'dollar_liquidity') {
    const contract = dollarLiquidityContract(module)
    return `Dollar liquidity: ${text(contract.dollar_liquidity_state, 'liquidity_neutral')}; impulse ${text(contract.liquidity_impulse.state, 'missing')}; repo funding ${text(contract.repo_funding_pressure.state, 'missing')}; BTC response ${text(contract.btc_response_confirmation.state, 'missing')}. This module confirms or refutes BTC trend through USD liquidity and funding conditions.`
  }
  if (id === 'treasury_credit') {
    const contract = treasuryCreditContract(module)
    return `Treasury credit: ${text(contract.treasury_credit_state, 'treasury_credit_neutral')}; BTC implication ${text(contract.btc_implication, 'neutral')}; real yield ${text(contract.real_yield_pressure.state, 'missing')}; credit ${text(contract.credit_stress.state, 'missing')}; BTC response ${text(contract.btc_response_confirmation.state, 'missing')}. This module confirms or refutes BTC trend through rates, curve and credit stress.`
  }
  const templates: Record<string, string> = {
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
  }
  return templates[id] ?? `${shortModuleName(module)} is ${direction}${split}${boundary}.`
}

function moduleAuditMeta(module: Row) {
  const positive = text(module.positive_metric_count, '0')
  const negative = text(module.negative_metric_count, '0')
  const zero = text(module.zero_metric_count, '0')
  const unavailable = text(module.unavailable_metric_count, '0')
  const quality = text(module.module_quality_score ?? module.quality_score)
  return `q=${quality} · +${positive}/-${negative} · 0=${zero} · NA=${unavailable}`
}

function loadRadarLayout() {
  const raw = window.localStorage.getItem(RADAR_LAYOUT_KEY)
  if (!raw) return
  try {
    const parsed = JSON.parse(raw) as Record<string, LayoutPoint>
    for (const [moduleId, point] of Object.entries(parsed)) {
      if (Number.isFinite(point?.x) && Number.isFinite(point?.y)) {
        radarLayout[moduleId] = { x: clamp(point.x, 4, 96), y: clamp(point.y, 8, 92) }
      }
    }
  } catch {
    window.localStorage.removeItem(RADAR_LAYOUT_KEY)
  }
}

function saveRadarLayout() {
  window.localStorage.setItem(RADAR_LAYOUT_KEY, JSON.stringify(radarLayout))
}

function resetRadarLayout() {
  for (const key of Object.keys(radarLayout)) delete radarLayout[key]
  window.localStorage.removeItem(RADAR_LAYOUT_KEY)
}

function handleBtcMove(event: MouseEvent) {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const px = x / rect.width - 0.5
  const py = y / rect.height - 0.5
  const rotateY = px * 10
  const rotateX = -py * 8
  const shadowX = -px * 28
  const shadowY = 22 + Math.abs(py) * 10 - py * 10
  const shadowScaleX = 1.05 + Math.abs(px) * 0.24
  const shadowScaleY = 0.78 - Math.abs(py) * 0.16
  const shadowBlur = 22 + (0.5 - Math.min(0.5, Math.hypot(px, py))) * 20
  const shadowOpacity = 0.22 + Math.min(0.18, Math.hypot(px, py) * 0.24)
  target.style.setProperty('--btc-rx', `${rotateX.toFixed(2)}deg`)
  target.style.setProperty('--btc-ry', `${rotateY.toFixed(2)}deg`)
  target.style.setProperty('--btc-shadow-x', `${shadowX.toFixed(1)}px`)
  target.style.setProperty('--btc-shadow-y', `${shadowY.toFixed(1)}px`)
  target.style.setProperty('--btc-shadow-scale-x', shadowScaleX.toFixed(3))
  target.style.setProperty('--btc-shadow-scale-y', shadowScaleY.toFixed(3))
  target.style.setProperty('--btc-shadow-blur', `${shadowBlur.toFixed(1)}px`)
  target.style.setProperty('--btc-shadow-opacity', shadowOpacity.toFixed(3))
}

function resetBtcTilt(event: MouseEvent) {
  const target = event.currentTarget as HTMLElement
  target.style.setProperty('--btc-rx', '0deg')
  target.style.setProperty('--btc-ry', '0deg')
  target.style.setProperty('--btc-shadow-x', '0px')
  target.style.setProperty('--btc-shadow-y', '26px')
  target.style.setProperty('--btc-shadow-scale-x', '1')
  target.style.setProperty('--btc-shadow-scale-y', '0.82')
  target.style.setProperty('--btc-shadow-blur', '34px')
  target.style.setProperty('--btc-shadow-opacity', '0.18')
}

function handleRadarNodeMove(event: MouseEvent) {
  if (dragging.value || window.matchMedia('(max-width: 1100px)').matches) return
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const rotateY = (x / rect.width - 0.5) * 8
  const rotateX = (0.5 - y / rect.height) * 6
  target.style.setProperty('--node-rx', `${rotateX.toFixed(2)}deg`)
  target.style.setProperty('--node-ry', `${rotateY.toFixed(2)}deg`)
}

function resetRadarNodeTilt(event: MouseEvent | PointerEvent) {
  const target = event.currentTarget as HTMLElement
  target.style.setProperty('--node-rx', '0deg')
  target.style.setProperty('--node-ry', '0deg')
}

function clampAwayFromBtc(x: number, y: number, target: HTMLElement): LayoutPoint {
  const topology = topologyRef.value
  const btc = btcRef.value
  if (!topology || !btc) return { x, y }

  const topologyRect = topology.getBoundingClientRect()
  const btcRect = btc.getBoundingClientRect()
  const nodeRect = target.getBoundingClientRect()
  const padding = 12
  const nodeHalfW = nodeRect.width / 2
  const nodeHalfH = nodeRect.height / 2
  const minX = nodeHalfW
  const maxX = topologyRect.width - nodeHalfW
  const minY = 96 + nodeHalfH
  const maxY = topologyRect.height - nodeHalfH

  let px = clamp((x / 100) * topologyRect.width, minX, maxX)
  let py = clamp((y / 100) * topologyRect.height, minY, maxY)

  const btcCenterX = btcRect.left - topologyRect.left + btcRect.width / 2
  const btcCenterY = btcRect.top - topologyRect.top + btcRect.height / 2
  const halfW = btcRect.width / 2 + nodeHalfW + padding
  const halfH = btcRect.height / 2 + nodeHalfH + padding
  const dx = px - btcCenterX
  const dy = py - btcCenterY

  if (Math.abs(dx) < halfW && Math.abs(dy) < halfH) {
    if (Math.abs(dx) < 0.1 && Math.abs(dy) < 0.1) {
      py = btcCenterY - halfH
    } else {
      const tx = Math.abs(dx) > 0.1 ? halfW / Math.abs(dx) : Number.POSITIVE_INFINITY
      const ty = Math.abs(dy) > 0.1 ? halfH / Math.abs(dy) : Number.POSITIVE_INFINITY
      const t = Math.min(tx, ty)
      px = btcCenterX + dx * t
      py = btcCenterY + dy * t
    }
  }

  px = clamp(px, minX, maxX)
  py = clamp(py, minY, maxY)
  return {
    x: (px / topologyRect.width) * 100,
    y: (py / topologyRect.height) * 100,
  }
}

function updateDraggedPoint(event: PointerEvent) {
  const drag = dragging.value
  const topology = topologyRef.value
  if (!drag || !topology) return
  const rect = topology.getBoundingClientRect()
  const rawX = ((event.clientX - rect.left) / rect.width) * 100
  const rawY = ((event.clientY - rect.top) / rect.height) * 100
  radarLayout[drag.moduleId] = clampAwayFromBtc(rawX, rawY, drag.target)
}

function startDrag(event: PointerEvent, moduleId: string) {
  if (window.matchMedia('(max-width: 1100px)').matches) return
  const target = event.currentTarget as HTMLElement
  target.style.setProperty('--node-rx', '0deg')
  target.style.setProperty('--node-ry', '0deg')
  dragging.value = {
    moduleId: moduleLayoutKey(moduleId),
    pointerId: event.pointerId,
    target,
    startClientX: event.clientX,
    startClientY: event.clientY,
    moved: false,
  }
  target.setPointerCapture(event.pointerId)
  document.body.classList.add('dragging-radar-node')
}

function dragNode(event: PointerEvent) {
  const drag = dragging.value
  if (!drag || drag.pointerId !== event.pointerId) return
  const distance = Math.hypot(event.clientX - drag.startClientX, event.clientY - drag.startClientY)
  if (!drag.moved && distance < 4) return
  drag.moved = true
  updateDraggedPoint(event)
}

function stopDrag(event?: PointerEvent) {
  const drag = dragging.value
  if (!drag) return
  if (event && drag.pointerId !== event.pointerId) return
  try {
    if (event) drag.target.releasePointerCapture(event.pointerId)
  } catch {
    // Pointer capture can be released by the browser if the pointer leaves the window.
  }
  if (drag.moved) {
    for (const node of topologyModules.value) {
      const moduleId = moduleLayoutKey(moduleName(node.module))
      const point = displayNodePoint(moduleId, node.index)
      radarLayout[moduleId] = { x: clamp(point.x, 4, 96), y: clamp(point.y, 8, 92) }
    }
    saveRadarLayout()
    suppressNextNodeClick.value = true
    window.setTimeout(() => {
      suppressNextNodeClick.value = false
    }, 0)
  }
  dragging.value = null
  document.body.classList.remove('dragging-radar-node')
}

function loadEventAlertPosition() {
  try {
    const raw = window.localStorage.getItem(EVENT_ALERT_POSITION_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as Partial<LayoutPoint>
    if (Number.isFinite(parsed.x) && Number.isFinite(parsed.y)) {
      eventAlertPosition.value = {
        x: clamp(Number(parsed.x), 8, Math.max(window.innerWidth - 220, 8)),
        y: clamp(Number(parsed.y), 58, Math.max(window.innerHeight - 120, 58)),
      }
    }
  } catch {
    eventAlertPosition.value = null
  }
}

function saveEventAlertPosition() {
  if (!eventAlertPosition.value) {
    window.localStorage.removeItem(EVENT_ALERT_POSITION_KEY)
    return
  }
  window.localStorage.setItem(EVENT_ALERT_POSITION_KEY, JSON.stringify(eventAlertPosition.value))
}

function loadEventAlertMute() {
  try {
    const raw = window.localStorage.getItem(EVENT_ALERT_MUTE_KEY)
    const until = raw ? Number(raw) : 0
    eventAlertMutedUntil.value = Number.isFinite(until) ? until : 0
  } catch {
    eventAlertMutedUntil.value = 0
  }
}

function readStorageList(storage: Storage, key: string) {
  try {
    const parsed = JSON.parse(storage.getItem(key) || '[]') as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.map((item) => text(item, '')).filter(Boolean)
  } catch {
    return []
  }
}

function writeStorageList(storage: Storage, key: string, values: string[]) {
  storage.setItem(key, JSON.stringify([...new Set(values.filter(Boolean))]))
}

function loadEventWindowVisibilityState() {
  eventWindowAckKeys.value = readStorageList(window.localStorage, EVENT_WINDOW_ACK_KEY)
  eventWindowHiddenKeys.value = readStorageList(window.sessionStorage, EVENT_WINDOW_HIDDEN_KEY)
  dismissedCriticalAlertKey.value = text(window.sessionStorage.getItem(EVENT_WINDOW_CRITICAL_DISMISS_KEY), '')
}

function saveEventWindowAckKeys() {
  try {
    writeStorageList(window.localStorage, EVENT_WINDOW_ACK_KEY, eventWindowAckKeys.value)
  } catch {
    // Ack is local UI state only; Event Window payload remains authoritative.
  }
}

function saveEventWindowHiddenKeys() {
  try {
    writeStorageList(window.sessionStorage, EVENT_WINDOW_HIDDEN_KEY, eventWindowHiddenKeys.value)
  } catch {
    // Hidden alerts are optional frontend visibility state.
  }
}

function ackCurrentEventAlert() {
  const key = eventWindowVisibilityKey.value
  if (!key || key === '|||') return
  eventWindowAckKeys.value = [...new Set([...eventWindowAckKeys.value, key])]
  saveEventWindowAckKeys()
}

function hideCurrentEventAlertForSession() {
  const key = eventWindowVisibilityKey.value
  if (!key || key === '|||') return
  eventWindowHiddenKeys.value = [...new Set([...eventWindowHiddenKeys.value, key])]
  eventFloatingAlertHovered.value = false
  saveEventWindowHiddenKeys()
}

function dismissEventFloatingAlertSession(event?: MouseEvent) {
  event?.stopPropagation()
  hideCurrentEventAlertForSession()
}

function clearVisibleNonCriticalEventAlerts() {
  if (eventCriticalLikeActive.value) return
  hideCurrentEventAlertForSession()
}

function restoreEventWindowHiddenAlerts() {
  eventWindowHiddenKeys.value = []
  dismissedCriticalAlertKey.value = ''
  eventAlertMutedUntil.value = 0
  eventAlertNowMs.value = Date.now()
  saveEventWindowHiddenKeys()
  try {
    window.localStorage.removeItem(EVENT_ALERT_MUTE_KEY)
    window.sessionStorage.removeItem(EVENT_WINDOW_CRITICAL_DISMISS_KEY)
  } catch {
    // Optional local mute cleanup.
  }
}

function muteEventFloatingAlert(minutes = 15) {
  const until = Date.now() + minutes * 60 * 1000
  eventAlertMutedUntil.value = until
  eventAlertNowMs.value = Date.now()
  try {
    window.localStorage.setItem(EVENT_ALERT_MUTE_KEY, String(until))
  } catch {
    // Local mute is optional; live Event Watchtower state remains visible on the page.
  }
}

function expandEventFloatingAlert(event: MouseEvent) {
  if (suppressNextEventAlertClick.value) {
    event.preventDefault()
    return
  }
  if (!eventFloatingAlertMuted.value) return
  eventAlertMutedUntil.value = 0
  eventAlertNowMs.value = Date.now()
  try {
    window.localStorage.removeItem(EVENT_ALERT_MUTE_KEY)
  } catch {
    // Optional local state cleanup.
  }
}

function setEventFloatingAlertHover(value: boolean) {
  eventFloatingAlertHovered.value = value
}

function resetEventAlertPosition() {
  eventAlertPosition.value = null
  saveEventAlertPosition()
}

function startEventAlertDrag(event: PointerEvent) {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  eventAlertPosition.value = {
    x: rect.left,
    y: rect.top,
  }
  eventAlertDragging.value = {
    pointerId: event.pointerId,
    target,
    offsetX: event.clientX - rect.left,
    offsetY: event.clientY - rect.top,
    startClientX: event.clientX,
    startClientY: event.clientY,
    moved: false,
  }
  target.setPointerCapture(event.pointerId)
  document.body.classList.add('dragging-event-alert')
}

function dragEventAlert(event: PointerEvent) {
  const drag = eventAlertDragging.value
  if (!drag || drag.pointerId !== event.pointerId) return
  const distance = Math.hypot(event.clientX - drag.startClientX, event.clientY - drag.startClientY)
  if (!drag.moved && distance < 4) return
  drag.moved = true
  const width = drag.target.offsetWidth || 460
  const height = drag.target.offsetHeight || 92
  eventAlertPosition.value = {
    x: clamp(event.clientX - drag.offsetX, 8, Math.max(window.innerWidth - width - 8, 8)),
    y: clamp(event.clientY - drag.offsetY, 58, Math.max(window.innerHeight - height - 8, 58)),
  }
}

function stopEventAlertDrag(event?: PointerEvent) {
  const drag = eventAlertDragging.value
  if (!drag) return
  if (event && drag.pointerId !== event.pointerId) return
  try {
    if (event) drag.target.releasePointerCapture(event.pointerId)
  } catch {
    // Pointer capture may already be released.
  }
  if (drag.moved) {
    saveEventAlertPosition()
    suppressNextEventAlertClick.value = true
    window.setTimeout(() => {
      suppressNextEventAlertClick.value = false
    }, 0)
  }
  eventAlertDragging.value = null
  document.body.classList.remove('dragging-event-alert')
}

function openEventWatchtowerFromAlert(event: MouseEvent) {
  if (suppressNextEventAlertClick.value) {
    event.preventDefault()
    return
  }
  activePage.value = 'eventWatchtower'
}

function dismissEventCriticalOverlay() {
  dismissedCriticalAlertKey.value = eventCriticalAlertKey.value
  try {
    window.sessionStorage.setItem(EVENT_WINDOW_CRITICAL_DISMISS_KEY, dismissedCriticalAlertKey.value)
  } catch {
    // Critical dismiss is session-only visibility; live Event Window state remains visible.
  }
}

async function openRadarNode(event: MouseEvent, moduleId: string) {
  if (suppressNextNodeClick.value) {
    event.preventDefault()
    return
  }
  await openRadarDetail(moduleId)
}

function horizonLabel(key: string) {
  if (key === 'h24' || key === '24h' || key === '1d') return '24h'
  if (key === 'd3' || key === '3d') return '3d'
  if (key === 'd7' || key === '7d') return '7d'
  return key
}

function horizonFullLabel(key: string) {
  if (key === '4h') return '4h 变盘侦测'
  if (key === '1d' || key === 'h24' || key === '24h') return '1d / 24h 短线趋势'
  if (key === '3d' || key === 'd3') return '3d 资金 / 宏观确认'
  if (key === '7d' || key === 'd7') return '7d Regime 背景'
  return key
}

function horizonDirection(key: string) {
  return normalizeTimescaleHorizon(key).direction
}

function horizonPairDirection(left: 'd3' | 'd7', right: 'd3' | 'd7') {
  const leftDirection = text(horizonDirection(left), '-')
  const rightDirection = text(horizonDirection(right), '-')
  return `${horizonLabel(left)} ${leftDirection} · ${horizonLabel(right)} ${rightDirection}`
}

function normalizeTimescaleHorizon(key: string): Row {
  const source = timescaleHorizonSource(key)
  const score = firstPresent(
    source.direct_trend_direction_score,
    source.direction_score,
    source.effective_score,
    source.score,
  )
  const trust = firstPresent(source.direct_trend_trust_score, source.trust_score, source.confidence_score, source.confidence)
  const acceptance = firstPresent(source.direct_trend_acceptance_score, source.acceptance_score)
  const display = firstPresent(source.direct_trend_display_score, source.display_score)
  const radarContext = asRow(source.radar_context)
  const eventTrust = asRow(source.event_trust)
  const eventCap = firstPresent(source.event_trust_cap, eventTrust.event_trust_cap)
  const direction = firstPresent(source.direction, Number.isFinite(Number(score)) ? signedDirection(Number(score)) : undefined)
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
  }
}

function timescaleHorizonSource(key: string): Row {
  const judgeHorizons = asRow(btcTimescaleJudge.value.horizons) as Record<string, unknown>
  const apiHorizons = asRow(directTrendApi.value.horizons) as Record<string, unknown>
  const views = ((state.dashboard?.horizon_views ?? state.overview?.horizon_views ?? {}) as Record<string, Row>)
  const legacyKeys = key === '1d'
    ? ['1d', '24h', 'h24']
    : key === '3d'
      ? ['3d', 'd3']
      : key === '7d'
        ? ['7d', 'd7']
        : [key]
  for (const candidate of [key, ...legacyKeys]) {
    const value = judgeHorizons[candidate] ?? apiHorizons[candidate] ?? views[candidate]
    if (value && typeof value === 'object' && !Array.isArray(value)) return value as Row
  }
  return { fallback_used: true, fallback_reason: 'waiting_for_timescale_payload' }
}

function firstPresent(...values: unknown[]) {
  return values.find((value) => value !== undefined && value !== null && value !== '')
}

const metricLabelMap: Record<string, string> = {
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
}

function metricLabel(metricId: unknown) {
  const id = driverMetricId(metricId)
  if (!id) return '-'
  return metricLabelMap[id] ?? id.replace(/_/g, ' ')
}

function driverMetricId(value: unknown) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const row = value as Row
    return String(row.metric_id ?? row.id ?? row.name ?? '')
  }
  return String(value ?? '')
}

function readableMetricText(value: unknown) {
  let output = text(value, '')
  const ids = Object.keys(metricLabelMap).sort((left, right) => right.length - left.length)
  for (const id of ids) {
    output = output.split(id).join(metricLabelMap[id])
  }
  return output
}

function asList(value: unknown) {
  if (Array.isArray(value)) return value.filter((item) => item !== null && item !== undefined && item !== '')
  if (value === null || value === undefined || value === '') return []
  return [value]
}

function compactList(value: unknown, fallback = '-') {
  const items = asList(value).map((item) => text(item)).filter(Boolean)
  return items.length ? items.slice(0, 4).join(', ') : fallback
}

function marketReturnPct(value: unknown) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '-'
  const sign = numeric > 0 ? '+' : ''
  return `${sign}${(numeric * 100).toFixed(2)}%`
}

function marketReturnTone(value: unknown) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 'quality'
  if (numeric <= -0.01) return 'bear'
  if (numeric < -0.003) return 'mixed'
  if (numeric >= 0.01) return 'bull'
  return 'quality'
}

function metricChips(value: unknown, limit = 5) {
  return asList(value)
    .map((item) => driverMetricId(item))
    .filter((item, index, array) => array.indexOf(item) === index)
    .slice(0, limit)
}

function horizonConfidence(item: Row) {
  const value = item.direct_trend_trust_score ?? item.trust_score ?? item.confidence_score ?? item.confidence
  if (typeof value === 'number') return value.toFixed(2)
  return text(value)
}

function horizonAcceptance(item: Row) {
  const acceptance = ((item.acceptance as Row | undefined) ?? {}) as Row
  const value = item.direct_trend_acceptance_score ?? item.acceptance_score
  if (typeof value === 'number') return value.toFixed(2)
  return text(acceptance.state, '')
}

function horizonScore(item: Row) {
  const value = item.direct_trend_direction_score ?? item.direction_score ?? item.effective_score ?? item.score
  if (typeof value === 'number') return value.toFixed(2)
  return text(value)
}

function horizonDisplayScore(item: Row) {
  const value = item.direct_trend_display_score ?? item.display_score
  if (typeof value === 'number') return value.toFixed(2)
  return text(value)
}

function horizonSummary(key: string, item: Row) {
  const reason = readableMetricText(item.reason)
  if (reason) return reason
  const summary = readableMetricText(item.summary)
  if (summary) return summary
  const interpretation = readableMetricText(item.interpretation)
  if (interpretation) return interpretation
  const direction = directionText(item.direction)
  const support = metricChips(item.support_drivers, 3).map(metricLabel).join(', ')
  const pressure = metricChips(item.pressure_drivers, 3).map(metricLabel).join(', ')
  const supportText = support ? `support from ${support}` : 'support drivers need confirmation'
  const pressureText = pressure ? `pressure from ${pressure}` : 'pressure drivers are not dominant'
  return `${horizonFullLabel(key)} is ${direction}; ${supportText}; ${pressureText}.`
}

function horizonTone(item: Row) {
  if (item.source_fresh === false || item.source_fresh === 'stale') return 'quality'
  const score = Number(item.direct_trend_direction_score ?? item.direction_score ?? item.effective_score ?? item.score)
  if (Number.isFinite(score)) {
    if (score >= 15) return 'bull'
    if (score <= -15) return 'bear'
    if (Math.abs(score) >= 5) return 'mixed'
    return 'neutral'
  }
  return directionClass(item.direction)
}

function horizonCardClasses(item: Row) {
  const classes = [horizonTone(item)]
  const trust = Number(item.direct_trend_trust_score ?? item.trust_score ?? item.confidence_score ?? item.confidence)
  if (Number.isFinite(trust) && trust < 55) classes.push('low-trust')
  if (item.fallback_used === true || item.fallback_reason) classes.push('fallback')
  if (horizonWarning(item)) classes.push('warning')
  return classes
}

function horizonFreshnessBadges(item: Row) {
  const badges = [
    `runtime ${text(item.runtime_fresh, 'unknown')}`,
    `source ${text(item.source_fresh, 'unknown')}`,
  ]
  if (item.fallback_used === true || item.fallback_reason) badges.push('fallback')
  if (horizonWarning(item)) badges.push('event warning')
  return badges
}

function horizonWarning(item: Row) {
  const flags = asList(item.semantic_flags).map((flag) => String(flag).toLowerCase())
  const state = String(item.state ?? '').toLowerCase()
  const reason = String(item.reason ?? '').toLowerCase()
  return [...flags, state, reason].some((value) => value.includes('volatility_shock') || value.includes('event_distorted'))
}

function horizonRadarContext(item: Row) {
  const context = asRow(item.radar_context)
  const status = text(context.status, 'waiting')
  const bias = text(context.bias, '0')
  return `${status} · bias ${bias}`
}

function horizonEventTrustCap(item: Row) {
  const eventTrust = asRow(item.event_trust)
  return text(eventTrust.event_trust_cap ?? item.event_trust_cap, 'not capped')
}

function horizonEventPhase(item: Row) {
  const flags = asList(item.semantic_flags).map((flag) => String(flag).toLowerCase())
  const known = ['pre_event', 'post_event_unconfirmed', 'post_event_accepted', 'shock_absorbed', 'event_distorted', 'volatility_shock']
  const matched = known.find((phase) => flags.some((flag) => flag.includes(phase)))
  if (matched) return matched
  const eventTrust = asRow(item.event_trust)
  return text(
    eventTrust.phase ??
      eventTrust.event_phase ??
      eventWindowState.value.event_phase ??
      eventWindowState.value.event_window_state,
    'calendar_monitor',
  )
}

function horizonBtcAcceptance(item: Row) {
  const state = asRow(item.acceptance).state
  const score = item.direct_trend_acceptance_score ?? item.acceptance_score
  if (state) return `${text(state)} · ${text(score)}`
  return text(score, 'waiting')
}

function horizonDirectEvidenceText(item: Row, limit = 3) {
  const evidence = asRow(item.direct_evidence) as Record<string, unknown>
  const rows: string[] = []
  for (const [group, metrics] of Object.entries(evidence)) {
    const groupRows = asRow(metrics) as Record<string, unknown>
    const topMetric = Object.entries(groupRows)
      .map(([metricId, payload]) => ({ metricId, payload: asRow(payload) }))
      .sort((left, right) => Math.abs(Number(right.payload.score ?? 0)) - Math.abs(Number(left.payload.score ?? 0)))[0]
    if (topMetric) {
      const semantic = topMetric.payload.semantic_state ? ` · ${text(topMetric.payload.semantic_state)}` : ''
      rows.push(`${metricLabel(topMetric.metricId)} ${text(topMetric.payload.score)}${semantic}`)
    } else if (Object.keys(groupRows).length === 0 && ['price_structure', 'orderflow_acceptance', 'btc_residual_cross_asset'].includes(group)) {
      rows.push(`${group.replace(/_/g, ' ')} pending`)
    }
    if (rows.length >= limit) break
  }
  return rows.length ? rows.join(' · ') : 'direct evidence pending'
}

function horizonConfirmationRules(item: Row, limit = 2) {
  const rules = asList(item.next_confirmation).map((rule) => readableMetricText(rule))
  if (rules.length) return rules.slice(0, limit)
  return horizonWatchRules(item, limit)
}

function horizonInvalidationRules(item: Row, limit = 2) {
  const rules = asList(item.invalidation).map((rule) => readableMetricText(rule))
  if (rules.length) return rules.slice(0, limit)
  return asList(item.next_invalidation_triggers).map((rule) => readableMetricText(rule)).slice(0, limit)
}

function horizonEvidenceChips(item: Row, bucket: string, limit = 3) {
  const evidence = ((item.evidence as Row | undefined) ?? {}) as Record<string, unknown>
  return asList(evidence[bucket])
    .map((entry) => {
      if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
        const row = entry as Row
        return String(row.module_id ?? row.metric_id ?? row.name ?? '')
      }
      return String(entry ?? '')
    })
    .filter((entry, index, array) => entry && array.indexOf(entry) === index)
    .slice(0, limit)
}

function horizonWatchRules(item: Row, limit = 4) {
  const confirmations = asList(item.next_confirmation_triggers).map((rule) => readableMetricText(rule))
  const invalidations = asList(item.next_invalidation_triggers).map((rule) => readableMetricText(rule))
  const v2Rules = [...confirmations, ...invalidations]
  if (v2Rules.length) return v2Rules.slice(0, limit)
  const rules = asList(item.watch_rules).map((rule) => readableMetricText(rule))
  if (rules.length) return rules.slice(0, limit)
  const drivers = [...metricChips(item.support_drivers, 2), ...metricChips(item.pressure_drivers, 2)]
  return drivers.slice(0, limit).map((driver) => `Watch whether ${metricLabel(driver)} continues the current direction`)
}

async function runAndOpenLogs() {
  if (state.routeContext.isHistorical) {
    store.exitHistoryMode()
    await store.refreshLatest()
  }
  navigateTo('logs')
  await store.runFullChain({ llmEnabled: state.llmRunEnabled })
}

async function toggleFullscreen() {
  if (document.fullscreenElement) {
    await document.exitFullscreen()
  } else {
    await document.documentElement.requestFullscreen()
  }
}

async function openRadarDetail(moduleId: string) {
  navigateTo('radar')
  selectedModuleId.value = moduleId
  await store.loadRadarDetail(moduleId)
  selectedRadarMetricId.value = text(selectedRadarMetrics.value[0]?.metric_id, '')
}

async function openEvidenceDetail(evidenceId: string) {
  navigateTo('evidence', { keepEvidenceDetail: true })
  selectedEvidenceId.value = evidenceId
  await store.loadEvidenceDetail(evidenceId)
  selectedEvidenceId.value = state.routeContext.evidence_id || evidenceId
}

function closeEvidenceDetail() {
  selectedEvidenceId.value = ''
  state.selectedEvidenceDetail = null
  state.routeContext.evidence_id = ''
}

function handleGlobalKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && activePage.value === 'evidence' && state.selectedEvidenceDetail) {
    closeEvidenceDetail()
  }
}

async function openSourceDetail(sourceId: string) {
  navigateTo('source')
  selectedSourceId.value = sourceId
  await store.loadSourceDetail(sourceId)
}

async function openVerifyWindowForSource(sourceIdValue: string) {
  const result = await store.openSourceVerifyWindow(sourceIdValue)
  const url = String((result as Row | null)?.url ?? (result as Row | null)?.verify_url ?? '')
  if (url) window.open(url, '_blank', 'noopener,noreferrer')
}

async function retryCollectForSource(sourceIdValue: string) {
  await store.retrySourceCollect(sourceIdValue)
  await store.refreshLatest()
}

async function viewLastCaptureForSource(sourceIdValue: string) {
  await store.loadSourceLastCapture(sourceIdValue)
  selectedSourceId.value = sourceIdValue
  navigateTo('source')
}

async function openSourceEvidenceItem(item: Row) {
  const evidenceId = String(item.evidence_id ?? '')
  if (evidenceId) {
    await openEvidenceDetail(evidenceId)
    return
  }
  await openMetricEvidence(item.metric_id)
}

function openAuditReports() {
  navigateTo('logs')
}

function openLlmAppendix() {
  navigateTo('article')
}
</script>

<template>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">B</span>
        <strong>onlyBTC</strong>
      </div>
      <div class="ticker">
        <strong>BTC {{ text(state.dashboard?.btc_price, '') }}</strong>
        <span class="pill" :class="directionClass(state.dashboard?.final_view)">
          <span class="dot"></span> final view: {{ state.dashboard?.final_view_cn ?? state.dashboard?.final_view ?? '-' }}
        </span>
        <span class="pill mixed"><span class="dot mixed"></span> alert: {{ text((alerts[0] as Row | undefined)?.level, 'watch') }}</span>
        <span class="pill bull"><span class="dot bull"></span> contract {{ text(contract.status, '-') }}</span>
        <span class="pill mixed" title="Frozen P4.5 final lineage; not the live radar heartbeat">
          frozen final {{ shortRunId(frozenFinalLineage.final_run_id) }}
        </span>
        <button class="pill run-state-pill" :class="runHealthClass" @click="navigateTo('logs')">
          <span class="dot"></span> {{ runningStageText }}
        </button>
        <button class="pill run-state-pill" :class="statusClass(liveRuntimeFreshness.health_state)" @click="store.runRadarRuntimeOnce()">
          <span class="dot"></span>
          live runtime {{ text(liveRuntimeFreshness.health_state, 'runtime') }}
          · fresh {{ text(liveRuntimeFreshness.fresh_module_count, '0') }}/{{ text(liveRuntimeFreshness.expected_module_count, '14') }}
          · source {{ text(liveRuntimeFreshness.source_freshness_state, 'unknown') }}
        </button>
        <span class="updated">Frozen final updated {{ text(frozenFinalCreatedAt, '-') }}</span>
      </div>
      <div class="actions">
        <span class="pill quality"><span class="dot quality"></span> data quality {{ text(dataQuality.avg_metric_quality ?? dataQuality.quality_score) }}</span>
        <button
          class="llm-run-toggle"
          :class="{ active: state.llmRunEnabled }"
          :title="state.llmRunEnabled ? 'LLM on: P4.5 结论先出，LLM 文章后台补全' : 'Fast only: 本轮只跑到 P4.5 deterministic final'"
          @click="store.setLlmRunEnabled(!state.llmRunEnabled)"
        >
          {{ state.llmRunEnabled ? 'LLM on' : 'Fast only' }}
        </button>
        <button class="primary" @click="runAndOpenLogs" :disabled="state.running">
          {{ state.running ? 'Running' : 'Run Full Chain' }}
        </button>
        <button class="linklike" @click="openAuditReports">Audit Reports</button>
        <button @click="navigateTo('settings')">Settings</button>
      </div>
    </header>

    <article
      v-if="showEventFloatingAlert"
      class="event-floating-alert"
      :class="[alertTone(eventWindowState.emergency_level), { 'is-positioned': eventAlertPosition, 'is-muted': eventFloatingAlertMuted }]"
      :style="eventFloatingAlertStyle"
      :title="eventFloatingAlertMuted ? '点击展开，拖动调整位置，双击归位' : '拖动调整位置，双击归位'"
      role="status"
      aria-live="polite"
      @mouseenter="setEventFloatingAlertHover(true)"
      @mouseleave="setEventFloatingAlertHover(false)"
      @focusin="setEventFloatingAlertHover(true)"
      @focusout="setEventFloatingAlertHover(false)"
      @click="expandEventFloatingAlert"
      @dblclick.stop="resetEventAlertPosition"
      @pointerdown="startEventAlertDrag"
      @pointermove="dragEventAlert"
      @pointerup="stopEventAlertDrag"
      @pointercancel="stopEventAlertDrag"
    >
      <template v-if="eventFloatingAlertMuted">
        <span class="event-floating-icon-dot"></span>
        <div>
          <strong>EVENT WATCH</strong>
          <small>{{ text(eventWindowActive.event_type, 'event') }} · {{ text(eventWindowState.emergency_level, 'high') }}</small>
        </div>
      </template>
      <template v-else>
      <header>
        <div>
          <strong>{{ eventFloatingTitle }}</strong>
          <small>{{ eventFloatingSubtitle }}</small>
        </div>
        <span class="event-floating-permission">{{ text(eventWindowOverlay.trade_permission_modifier, 'watch_only') }}</span>
      </header>
      <p>{{ eventFloatingMessage }}</p>
      <footer>
        <button type="button" @pointerdown.stop @click.stop="muteEventFloatingAlert(15)">Mute 15m</button>
        <button type="button" @pointerdown.stop @click.stop="dismissEventFloatingAlertSession">Dismiss session</button>
        <button type="button" class="primary" @pointerdown.stop @click.stop="activePage = 'eventWatchtower'">Open</button>
      </footer>
      </template>
    </article>

    <section v-if="showEventCriticalOverlay" class="event-critical-overlay" role="dialog" aria-modal="true" aria-label="Critical event window alert">
      <article class="event-critical-card" :class="alertTone(eventWindowState.emergency_level)">
        <header>
          <span class="pill bear"><span class="dot bear"></span> {{ text(eventWindowState.emergency_level, 'critical') }}</span>
          <button class="event-critical-close" @click="dismissEventCriticalOverlay">Dismiss session</button>
        </header>
        <h2>{{ text(eventWindowActive.title, 'Policy shock watch') }}</h2>
        <p>
          {{ text(eventWindowState.event_window_state, 'unscheduled_shock_confirmed') }} ·
          overlay {{ text(eventWindowOverlay.trade_permission_modifier, 'event_lock') }} ·
          radar trust {{ text(eventWindowOverlay.ordinary_radar_trust, 'blocked') }}.
        </p>
        <div class="event-critical-meta">
          <span><small>event window state</small><strong>{{ text(eventWindowState.event_window_state, 'critical') }}</strong></span>
          <span><small>trade permission</small><strong>{{ text(eventWindowOverlay.trade_permission_modifier, 'event_lock') }}</strong></span>
          <span><small>ordinary radar trust</small><strong>{{ text(eventWindowOverlay.ordinary_radar_trust, 'blocked') }}</strong></span>
          <span><small>valid until</small><strong>{{ text(eventWindowState.valid_until, '-') }}</strong></span>
          <span><small>direct score impact</small><strong>{{ eventWindowDirectScoreImpact }}</strong></span>
          <span><small>snapshot</small><strong>{{ text(eventWatchtowerPayload.snapshot_id, '-') }}</strong></span>
        </div>
        <div class="event-critical-reasons">
          <span v-for="code in eventWindowReasonCodes" :key="code" class="event-chip mixed">{{ code }}</span>
          <span v-if="!eventWindowReasonCodes.length" class="event-chip">reason_codes none</span>
        </div>
        <footer>
          <button class="primary" @click="activePage = 'eventWatchtower'">Open Watchtower</button>
          <small>Event Window changes emergency overlay and radar trust; it does not directly modify BTC score.</small>
        </footer>
      </article>
    </section>

    <section
      v-if="showEventCriticalMockOverlay"
      class="event-critical-overlay event-critical-mock-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Mock critical event window alert"
    >
      <article class="event-critical-card event-critical-mock-card">
        <header>
          <span class="pill mixed"><span class="dot mixed"></span> MOCK / audit only</span>
          <span class="event-chip">dev query flag</span>
        </header>
        <h2>CRITICAL MOCK STATE</h2>
        <p>
          This audit-only overlay is enabled only by local dev flag <code>?event_mock=critical</code>.
          It does not read Event Window payload, write store state, or change BTC/radar scores.
        </p>
        <footer>
          <button class="primary" @click="activePage = 'eventWatchtower'">Open Watchtower</button>
          <small>Mock / audit only. Not part of the default live production path.</small>
        </footer>
      </article>
    </section>

    <section class="main" :class="pageShellClass">
      <aside class="rail">
        <button
          v-for="page in pages"
          :key="page.id"
          class="navbtn"
          :class="{ active: activePage === page.id }"
          @click="navigateTo(page.id)"
        >
          {{ page.label }}
        </button>
      </aside>

      <button v-if="!drawerOpen && !pageFullscreen" class="drawer-reopen" @click="drawerOpen = true">Open Context</button>
      <div v-if="pageFullscreen" class="fullscreen-toolbar">
        <div>
          <span>{{ pageTitle }}</span>
          <code>{{ text(state.routeContext.final_run_id ?? store.runLineage.value.final_run_id, 'latest') }}</code>
        </div>
        <div>
          <button @click="togglePageFullscreen">Exit Fullscreen</button>
          <button @click="goDashboard">Back Dashboard</button>
        </div>
      </div>

      <section v-if="activePage === 'topology'" class="canvas">
        <article ref="topologyRef" class="topology">
          <div class="topology-title">
            <span class="pill">P4.5 Report v2</span>
            <span>{{ store.radarModules.value.length || 14 }} Radar modules · {{ state.dashboard?.metric_evidence_count ?? 0 }} scored evidence · DeepSeek appendix</span>
            <button class="layout-reset" @click="resetRadarLayout">Reset Layout</button>
          </div>

          <div class="legend">
            <span class="pill"><span class="dot bull"></span> support</span>
            <span class="pill"><span class="dot bear"></span> pressure</span>
            <span class="pill"><span class="dot mixed"></span> mixed</span>
            <span class="pill"><span class="dot quality"></span> data quality</span>
          </div>

          <svg class="links" viewBox="0 0 1000 620" preserveAspectRatio="none" aria-hidden="true">
            <path
              v-for="link in dynamicLinks"
              :key="`link-${link.moduleId}`"
              :d="link.path"
              class="link"
              :class="link.kind"
              :style="{ opacity: link.opacity, strokeWidth: link.strokeWidth }"
            />
          </svg>

          <button
            v-for="node in topologyModules"
            :key="moduleName(node.module)"
            class="node"
            :class="nodeClass(node)"
            :style="nodeStyle(moduleName(node.module), node.index)"
            @pointerdown="startDrag($event, moduleName(node.module))"
            @pointermove="dragNode"
            @pointerup="stopDrag"
            @pointercancel="stopDrag"
            @mousemove="handleRadarNodeMove"
            @mouseleave="resetRadarNodeTilt"
            @click="openRadarNode($event, moduleName(node.module))"
          >
            <div class="node-tilt">
              <div class="node-title">
                {{ shortModuleName(node.module) }}
                <span class="pill compact-state" :title="moduleDisplayLabel(node.module)">
                  {{ moduleDisplayShortLabel(node.module) }}
                </span>
              </div>
              <div class="node-meta">{{ moduleMeta(node.module) }}</div>
              <div class="node-audit">{{ moduleAuditMeta(node.module) }}</div>
              <div class="node-score">
                <div class="bar" :class="directionClass(node.direction)"><i :style="{ width: `${Math.min(92, Math.max(18, Math.abs(Number(node.module.module_effective_score ?? node.module.module_score ?? 0)) * 240))}%` }"></i></div>
                <span>{{ text(node.module.module_effective_score ?? node.module.module_score) }}</span>
              </div>
            </div>
          </button>

          <article
            ref="btcRef"
            class="btc-node"
            :class="btcNodeClass"
            @mousemove="handleBtcMove"
            @mouseleave="resetBtcTilt"
          >
            <span class="btc-dynamic-shadow" aria-hidden="true"></span>
            <div class="btc-head">
              <div>
                <div class="btc-symbol btc-gold-text" data-text="BTC">BTC</div>
                <div class="state">{{ finalViewText }} · {{ tradePermissionText }}</div>
              </div>
              <div class="score-ring" :style="scoreRingStyle">{{ scorePercent }}</div>
            </div>
            <div class="btc-badges">
              <button class="status-chip" @click="activePage = 'quality'">quality {{ dataQualityLabel }}</button>
              <button class="status-chip" @click="activePage = 'logs'">contract {{ contractStatus }}</button>
              <button v-if="hasCockpit" class="status-chip" @click="activePage = 'overview'">cockpit v2</button>
              <button v-if="hasRuntimeCockpit" class="status-chip" @click="activePage = 'radar'">runtime {{ text(radarRuntimeHealth.health_state, 'fresh') }}</button>
            </div>
            <div v-if="hasCockpit" class="cockpit-readout" :class="directionClass(cockpitFastDirection)">
              <span class="readout-label">{{ cockpitReadoutLabel }}</span>
              <strong>{{ cockpitFastScore }}</strong>
              <span class="readout-chip">{{ cockpitFastDirection }}</span>
              <small>{{ cockpitFastStage }}</small>
            </div>
            <p v-else class="summary-text">{{ cockpitSummaryText }}</p>
            <div class="btc-grid">
              <div class="mini-kv"><span>strength</span><strong>{{ text(btcCockpit.btc_strength ?? decision.strength_cn ?? decision.strength) }}</strong></div>
              <div class="mini-kv"><span>quality</span><strong>{{ text(btcCockpit.trend_quality ?? decision.risk_mode) }}</strong></div>
              <div class="mini-kv"><span>4h</span><strong>{{ text(cockpitHorizon['4h']?.direction ?? horizonDirection('4h')) }}</strong></div>
              <div class="mini-kv horizon-pair"><span>24h / 3d</span><strong>{{ text(cockpitHorizon['24h']?.direction ?? horizonDirection('1d')) }} · {{ text(cockpitHorizon['3d']?.direction ?? horizonDirection('3d')) }}</strong></div>
            </div>
            <div class="why-strip">
              <button @click="activePage = 'overview'">Pressure: {{ cockpitPressureText }}</button>
              <button @click="activePage = 'overview'">Support: {{ cockpitSupportText }}</button>
              <button @click="activePage = 'overview'">Conflict: {{ cockpitConflictText }}</button>
            </div>
            <div class="btc-watch">
              <button @click="activePage = 'invalidation'">反证条件：{{ primaryCockpitInvalidation }}</button>
              <button @click="activePage = 'invalidation'">确认条件：{{ primaryCockpitTrigger }}</button>
            </div>
            <div class="btc-actions">
              <button class="pill" @click="activePage = 'overview'">View Overview</button>
              <button class="pill" @click="activePage = 'article'">Read Article</button>
              <button class="pill" @click="navigateTo('evidence')">Evidence</button>
              <button class="pill" @click="openLlmAppendix">LLM</button>
            </div>
          </article>
        </article>

        <div class="bottom-grid">
          <article class="panel">
            <div class="panel-head"><h2>时间尺度视图</h2><span class="pill">{{ text(btcTimescaleJudge.schema_version, 'horizon_views') }}</span></div>
            <div class="horizon-row">
              <button
                v-for="[key, item] in horizons"
                :key="key"
                class="horizon-card"
                :class="horizonCardClasses(item)"
                @click="activePage = 'overview'"
              >
                <div class="horizon-card-head">
                  <strong>{{ horizonFullLabel(key) }}</strong>
                  <span>{{ directionText(item.direction) }}</span>
                </div>
                <div class="horizon-badges">
                  <i v-for="badge in horizonFreshnessBadges(item)" :key="`${key}-${badge}`">{{ badge }}</i>
                </div>
                <span class="horizon-meta">State {{ text(item.state, 'waiting') }}</span>
                <div class="horizon-score-grid">
                  <span><small>Direction</small><b>{{ horizonScore(item) }}</b></span>
                  <span><small>Trust</small><b>{{ horizonConfidence(item) }}</b></span>
                  <span><small>Display</small><b>{{ horizonDisplayScore(item) }}</b></span>
                </div>
                <small>{{ horizonSummary(key, item) }}</small>
                <div class="horizon-chain">
                  <span>Direct Evidence</span>
                  <p>{{ horizonDirectEvidenceText(item) }}</p>
                </div>
                <div class="horizon-chain">
                  <span>Radar Context</span>
                  <p>{{ horizonRadarContext(item) }}</p>
                </div>
                <div class="horizon-chain">
                  <span>BTC Acceptance</span>
                  <p>{{ horizonBtcAcceptance(item) }}</p>
                </div>
                <div class="horizon-chain">
                  <span>Event Trust Cap</span>
                  <p>{{ horizonEventTrustCap(item) }}</p>
                </div>
                <div v-if="key === '4h' || key === '1d'" class="horizon-chain">
                  <span>Event Phase</span>
                  <p>{{ horizonEventPhase(item) }}</p>
                </div>
                <div class="driver-line">
                  <span>Next Confirmation</span>
                  <i
                    v-for="rule in horizonConfirmationRules(item, 2)"
                    :key="`confirm-${key}-${rule}`"
                    :title="rule"
                  >
                    {{ rule }}
                  </i>
                </div>
                <div class="driver-line pressure">
                  <span>Invalidation</span>
                  <i
                    v-for="rule in horizonInvalidationRules(item, 2)"
                    :key="`invalidate-${key}-${rule}`"
                    :title="rule"
                  >
                    {{ rule }}
                  </i>
                </div>
                <em>{{ text(item.fallback_reason, 'v2.2 direct trend payload') }}</em>
              </button>
            </div>
          </article>
          <article class="panel alert-event-panel">
            <div class="panel-head">
              <h2>预警 / 事件窗口</h2>
              <button class="pill mixed" @click="activePage = 'eventWatchtower'">Open Watchtower</button>
            </div>
            <button class="alert-card event-summary-widget" :class="alertTone(eventWindowState.emergency_level)" @click="activePage = 'eventWatchtower'">
              <span>
                {{ text(eventWindowState.emergency_level, 'none') }} ·
                {{ text(eventWindowState.event_window_state, 'calendar_monitor') }}
              </span>
              <strong>{{ eventWindowSummaryTitle }}</strong>
              <small>{{ eventWindowSummarySubtitle }}</small>
              <em>{{ eventWindowSummaryDetail }}</em>
            </button>
            <div class="event-summary-grid">
              <button class="event-summary-kv" @click="activePage = 'eventWatchtower'">
                <span>Overlay</span>
                <strong>{{ text(eventWindowOverlay.trade_permission_modifier, 'none') }}</strong>
                <small>{{ eventWindowSummaryAction }}</small>
              </button>
              <button class="event-summary-kv" @click="activePage = 'eventWatchtower'">
                <span>Radar trust</span>
                <strong>{{ text(eventWindowOverlay.ordinary_radar_trust, 'normal') }}</strong>
                <small>does not modify BTC score</small>
              </button>
              <button class="event-summary-kv" @click="activePage = 'eventWatchtower'">
                <span>Daemon</span>
                <strong>{{ text(eventWindowDaemon.status, 'running') }}</strong>
                <small>{{ text(eventWindowDaemon.collection_mode, 'standalone daemon') }}</small>
              </button>
              <button class="event-summary-kv" :class="marketReturnTone(eventWindowMarketReturns['4h'])" @click="activePage = 'eventWatchtower'">
                <span>Market probe</span>
                <strong>4h {{ marketReturnPct(eventWindowMarketReturns['4h']) }}</strong>
                <small>{{ text(eventWindowDaemon.runtime_code_version, 'watchtower runtime') }}</small>
              </button>
              <button class="event-summary-kv" @click="activePage = 'eventWatchtower'">
                <span>Source mode</span>
                <strong>{{ eventWindowSourceMode }}</strong>
                <small>
                  live {{ eventWindowSourceCounts.live }} · partial {{ eventWindowSourceCounts.partial }} ·
                  fallback {{ eventWindowSourceCounts.fallback }} · failed {{ eventWindowSourceCounts.failed }}
                </small>
              </button>
            </div>
            <p v-if="eventWindowDisabledCapabilities.length || eventWindowSourceCounts.failed > 0" class="event-source-note">
              Source capabilities:
              <template v-if="eventWindowDisabledCapabilities.length">
                {{ eventWindowDisabledCapabilities.slice(0, 5).join(', ') }}
              </template>
              <template v-else>no disabled capability</template>
              · failed sources {{ eventWindowSourceCounts.failed }}
            </p>
            <div class="event-summary-grid">
              <button class="event-summary-kv" :class="statusClass(radarRuntimeDaemon.health_state ?? radarRuntimeDaemon.status)" @click="store.runRadarRuntimeOnce()">
                <span>Radar runtime</span>
                <strong>{{ text(radarRuntimeDaemon.health_state ?? radarRuntimeDaemon.status, 'unknown') }}</strong>
                <small>independent run once · heartbeat {{ text(radarRuntimeDaemon.last_tick_age_sec, '-') }}s</small>
              </button>
              <button class="event-summary-kv" :class="statusClass(radarRuntimeHealth.health_state)" @click="activePage = 'radar'">
                <span>Module freshness</span>
                <strong>{{ text(radarRuntimeHealth.fresh_module_count, '0') }}/{{ text(radarRuntimeHealth.expected_module_count, '14') }}</strong>
                <small>runtime stale {{ text(radarRuntimeHealth.stale_module_count, '0') }} · source {{ text(radarRuntimeHealth.source_freshness_state, 'unknown') }}</small>
              </button>
              <button class="event-summary-kv" @click="activePage = 'overview'">
                <span>Runtime cockpit</span>
                <strong>{{ text(radarRuntimeCockpit.headline_stage, 'pending') }}</strong>
                <small>{{ text(radarRuntimeCockpit.why_not_confirmed, 'waiting for runtime snapshot') }}</small>
              </button>
            </div>
            <div class="watch-list compact">
              <button class="watch-row" @click="activePage = 'eventWatchtower'">
                <strong>Active event · {{ text(eventWindowActive.title, 'calendar monitor') }}</strong>
                <small>{{ text(eventWindowActive.event_type, 'event') }} · {{ daysText(Number(eventWindowActive.time_to_event_sec ?? 0) / 86400) }}</small>
                <span>{{ text(eventWindowActive.phase, 'calendar_awareness') }} · valid until {{ text(eventWindowState.valid_until, '-') }}</span>
              </button>
              <button class="watch-row" @click="activePage = 'eventWatchtower'">
                <strong>Shock lane · {{ text(eventWindowShockLane.shock_type, 'none') }}</strong>
                <small>{{ text(eventWindowShockLane.confirmation_level, 'none') }} · sources {{ text(eventWindowShockLane.source_count, '0') }}</small>
                <span>
                  market {{ text(eventWindowShockLane.market_dislocation, 'false') }} ·
                  micro {{ text(eventWindowShockLane.btc_microstructure_confirmation, 'false') }} ·
                  {{ text(eventWindowShockEvidence.primary_window, '-') }} {{ marketReturnPct(eventWindowShockEvidence.primary_return) }}
                </span>
              </button>
              <button class="watch-row" @click="activePage = 'eventWatchtower'">
                <strong>Latest alert · {{ text(eventWindowSummaryAlert.title, 'no active event-window alert') }}</strong>
                <small>{{ text(eventWindowSummaryAlert.emergency_level, 'none') }} · {{ text(eventWindowSummaryAlert.status, 'open') }}</small>
                <span>{{ text(eventWindowSummaryAlert.summary, 'Event Window is monitoring scheduled and unscheduled risk.') }}</span>
              </button>
            </div>
            <div class="halving-strip">
              <span>Event Window boundary</span>
              <strong>direct score impact: false</strong>
              <small>ordinary radar trust is capped by overlay, BTC score is not overwritten.</small>
            </div>
          </article>
        </div>
      </section>

      <section v-else class="content-page">
        <article v-if="activePage === 'overview'" class="panel overview-page">
          <div class="panel-head event-page-head">
            <h2>BTC Overview</h2>
            <span class="pill" :class="directionClass(state.dashboard?.final_view)">final {{ finalViewText }}</span>
          </div>
          <section class="overview-hero">
            <p>{{ text(decision.conclusion_sentence, 'Waiting for P4.5 decision card') }}</p>
            <div class="overview-kvs">
              <span>strength <strong>{{ text(decision.strength_cn ?? decision.strength) }}</strong></span>
              <span>confidence <strong>{{ text(decision.confidence_level ?? decision.confidence) }}</strong></span>
              <span>permission <strong>{{ tradePermissionText }}</strong></span>
            </div>
          </section>
          <section class="overview-section">
            <h3>时间尺度细节</h3>
            <h3>Current State</h3>
            <div class="overview-state-grid">
              <article>
                <span>directional score</span>
                <strong>{{ text(aggregation.directional_score ?? aggregation.final_score_adjusted) }}</strong>
                <small>raw net {{ text(aggregation.raw_net_score ?? overviewScoreComponents.net_score) }}</small>
              </article>
              <article>
                <span>support pressure</span>
                <strong>{{ text(overviewScoreComponents.support_score_abs) }} / {{ text(overviewScoreComponents.pressure_score_abs) }}</strong>
                <small>disagreement {{ text(aggregation.disagreement_level) }}</small>
              </article>
              <article>
                <span>zero metric ratio</span>
                <strong>{{ componentPercent(overviewScoreComponents.zero_metric_ratio) }}</strong>
                <small>unavailable {{ componentPercent(overviewScoreComponents.unavailable_metric_ratio) }}</small>
              </article>
              <article>
                <span>risk mode</span>
                <strong>{{ text(decision.risk_mode, 'balanced') }}</strong>
                <small>{{ text(decision.valid_horizon, '24h_to_3d') }}</small>
              </article>
            </div>
            <h3>Key Drivers / Conflicting Evidence</h3>
            <div class="driver-column-grid">
              <article class="driver-panel">
                <div class="article-card-head">
                  <h4>Support drivers</h4>
                  <span class="pill bull">{{ overviewSupportDrivers.length }}</span>
                </div>
                <button
                  v-for="driver in overviewSupportDrivers"
                  :key="`support-driver-${driverMetricId(driver)}`"
                  class="driver-row"
                  :class="directionClass(driver.direction)"
                  @click="openMetricEvidence(driver.metric_id)"
                >
                  <strong>{{ metricLabel(driver.metric_id) }}</strong>
                  <span>{{ text(driver.module) }} · {{ driverContribution(driver) }}</span>
                  <small>{{ driverReason(driver) }}</small>
                </button>
              </article>
              <article class="driver-panel pressure">
                <div class="article-card-head">
                  <h4>Pressure drivers</h4>
                  <span class="pill bear">{{ overviewPressureDrivers.length }}</span>
                </div>
                <button
                  v-for="driver in overviewPressureDrivers"
                  :key="`pressure-driver-${driverMetricId(driver)}`"
                  class="driver-row"
                  :class="directionClass(driver.direction)"
                  @click="openMetricEvidence(driver.metric_id)"
                >
                  <strong>{{ metricLabel(driver.metric_id) }}</strong>
                  <span>{{ text(driver.module) }} · {{ driverContribution(driver) }}</span>
                  <small>{{ driverReason(driver) }}</small>
                </button>
              </article>
            </div>
            <h3>Confidence Explanation</h3>
            <div class="confidence-box">
              <p>{{ normalizationText() }}</p>
              <div class="module-stats">
                <span>normalization {{ text(overviewScoreNormalization.normalization_base) }}</span>
                <span>threshold {{ text((overviewScoreNormalization.direction_threshold as Row | undefined)?.neutral_low) }} / {{ text((overviewScoreNormalization.direction_threshold as Row | undefined)?.neutral_high) }}</span>
                <span>confidence penalty {{ text(overviewScoreComponents.confidence_penalty) }}</span>
                <span>data quality {{ text(aggregation.data_quality_level) }}</span>
              </div>
            </div>
            <h3>What Would Change The View</h3>
            <div class="watch-list compact">
              <button
                v-for="item in overviewWatchRows"
                :key="`${item.kind}-${text(item.rule.rule_id)}`"
                class="watch-row"
                @click="activePage = 'invalidation'"
              >
                <strong>{{ item.kind }} · {{ text(item.rule.title ?? item.rule.rule_id) }}</strong>
                <small>{{ ruleSummary(item.rule) }}</small>
              </button>
            </div>
            <div v-if="overviewDataBoundary.length" class="data-boundary-strip">
              <span v-for="item in overviewDataBoundary" :key="item">{{ item }}</span>
            </div>
            <h3>Run Lineage</h3>
            <div class="overview-lineage-grid">
              <span><small>collect</small><code>{{ text(overviewRunLineage.collect_run_id) }}</code></span>
              <span><small>p2 radar</small><code>{{ text(overviewRunLineage.p2_radar_run_id) }}</code></span>
              <span><small>p3</small><code>{{ text(overviewRunLineage.p3_run_id) }}</code></span>
              <span><small>p45 final</small><code>{{ text(overviewRunLineage.final_run_id) }}</code></span>
            </div>
            <div class="horizon-detail-grid">
              <article
                v-for="[key, item] in horizons"
                :key="`detail-${key}`"
                class="horizon-detail-card"
                :class="horizonCardClasses(item)"
              >
                <div class="horizon-detail-head">
                  <strong>{{ horizonFullLabel(key) }}</strong>
                  <span>{{ directionText(item.direction) }}</span>
                </div>
                <div class="horizon-badges">
                  <i v-for="badge in horizonFreshnessBadges(item)" :key="`detail-${key}-${badge}`">{{ badge }}</i>
                </div>
                <div class="horizon-score-grid">
                  <span><small>Direction Score</small><b>{{ horizonScore(item) }}</b></span>
                  <span><small>Trust</small><b>{{ horizonConfidence(item) }}</b></span>
                  <span><small>Display Score</small><b>{{ horizonDisplayScore(item) }}</b></span>
                </div>
                <p>State {{ text(item.state, 'waiting') }} · Event Phase {{ key === '4h' || key === '1d' ? horizonEventPhase(item) : 'context' }}</p>
                <p>{{ horizonSummary(key, item) }}</p>
                <div class="horizon-chain">
                  <span>Direct Evidence</span>
                  <p>{{ horizonDirectEvidenceText(item, 5) }}</p>
                </div>
                <div class="horizon-chain">
                  <span>Radar Context</span>
                  <p>{{ horizonRadarContext(item) }}</p>
                </div>
                <div class="horizon-chain">
                  <span>BTC Acceptance</span>
                  <p>{{ horizonBtcAcceptance(item) }}</p>
                </div>
                <div class="horizon-chain">
                  <span>Event Trust Cap</span>
                  <p>{{ horizonEventTrustCap(item) }}</p>
                </div>
                <div class="driver-block">
                  <h4>Next Confirmation</h4>
                  <span v-for="rule in horizonConfirmationRules(item, 5)" :key="`detail-confirm-${key}-${rule}`" :title="rule">
                    {{ rule }}
                  </span>
                </div>
                <div class="driver-block pressure">
                  <h4>Invalidation</h4>
                  <span v-for="rule in horizonInvalidationRules(item, 5)" :key="`detail-invalidate-${key}-${rule}`" :title="rule">
                    {{ rule }}
                  </span>
                </div>
                <ul class="watch-bullets">
                  <li v-for="rule in horizonWatchRules(item, 5)" :key="`${key}-${rule}`">{{ rule }}</li>
                </ul>
              </article>
            </div>
          </section>
          <section class="overview-section">
            <h3>为什么不是强单边</h3>
            <p v-for="reason in decisionReasons" :key="text(reason)">{{ text(reason) }}</p>
          </section>
        </article>

        <article v-else-if="activePage === 'radar'" class="panel radar-detail-page">
          <div class="panel-head">
            <div>
              <h2>Radar Detail Scope</h2>
              <p>Module scope · metric nodes · evidence drilldown</p>
            </div>
            <div class="article-actions">
              <button class="pill" @click="activePage = 'topology'">Back Dashboard</button>
              <button class="pill" @click="navigateTo('evidence')">Evidence</button>
              <button class="pill quality" @click="activePage = 'quality'">Data Quality</button>
            </div>
          </div>

          <section class="radar-module-switch">
            <button
              v-for="module in store.radarModules.value"
              :key="moduleName(module)"
              :class="[moduleDisplayClass(module), selectedModuleId === moduleName(module) ? 'active' : '']"
              @click="openRadarDetail(moduleName(module))"
            >
              <strong>{{ shortModuleName(module) }}</strong>
              <small>{{ moduleDisplayLabel(module) }} · {{ text(module.module_effective_score ?? module.module_score) }}</small>
            </button>
          </section>

          <section v-if="state.selectedRadarDetail" class="radar-scope-layout">
            <section class="radar-scope-panel">
              <div class="scope-toolbar">
                <div class="filters">
                  <span class="pill bull"><span class="dot bull"></span> support {{ selectedRadarMetricStats.support }}</span>
                  <span class="pill bear"><span class="dot bear"></span> pressure {{ selectedRadarMetricStats.pressure }}</span>
                  <span class="pill mixed"><span class="dot mixed"></span> mixed {{ selectedRadarMetricStats.mixed }}</span>
                  <span class="pill quality"><span class="dot quality"></span> fallback / stale {{ selectedRadarMetricStats.quality }}</span>
                </div>
                <span class="pill">top metrics only · full audit table below</span>
              </div>

              <svg class="radar-scope-svg" viewBox="0 0 640 640" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
                <circle class="scope-ring" cx="320" cy="320" r="96" />
                <circle class="scope-ring" cx="320" cy="320" r="176" />
                <circle class="scope-ring" cx="320" cy="320" r="256" />
                <line class="scope-axis" x1="320" y1="58" x2="320" y2="582" />
                <line class="scope-axis" x1="58" y1="320" x2="582" y2="320" />
                <path class="scope-scan" d="M320 320 L320 58 A262 262 0 0 1 495 126 Z" />
              </svg>

              <section class="radar-scope-card-rail left" aria-label="Top radar metrics left">
                <button
                  v-for="(metric, index) in radarMetricRail('left')"
                  :key="`rail-left-${text(metric.evidence_id ?? metric.metric_id)}`"
                  class="radar-scope-metric-card"
                  :class="[radarMetricClass(metric), selectedRadarMetricId === text(metric.metric_id) ? 'selected' : '']"
                  @click="selectRadarMetric(metric)"
                >
                  <div class="metric-card-head">
                    <strong>{{ metricLabel(metric.metric_id) }}</strong>
                    <span class="pill">top {{ index * 2 + 1 }}</span>
                  </div>
                  <p>{{ radarMetricSummary(metric) }}</p>
                  <div class="metric-card-meta">
                    <span>{{ radarMetricCompactMeta(metric) }}</span>
                    <span>q {{ text(metric.quality_score) }}</span>
                  </div>
                  <div class="metric-score-track"><span :style="{ width: radarMetricBarWidth(metric) }"></span></div>
                </button>
              </section>

              <article class="radar-center-card" :class="moduleDisplayClass(selectedRadarModule)">
                <span class="pill" :class="moduleDisplayClass(selectedRadarModule)">
                  {{ moduleDisplayLabel(selectedRadarModule) }}
                </span>
                <h3>{{ text(selectedRadarModule.radar_module ?? selectedModuleId, 'Select Radar Module') }}</h3>
                <p>{{ moduleMeta(selectedRadarModule) }}</p>
                <div class="module-stats">
                  <span>score {{ text(selectedRadarModule.module_effective_score ?? selectedRadarModule.module_score) }}</span>
                  <span>quality {{ text(selectedRadarModule.module_quality_score) }}</span>
                  <span>metrics {{ text(selectedRadarMetrics.length) }}</span>
                  <span>weight {{ text(selectedRadarModule.module_weight) }}</span>
                </div>
                <div class="module-stats semantic-stats">
                  <span>stage {{ text(selectedRadarModule.signal_stage ?? selectedRadarModule.stage, 'none') }}</span>
                  <span>support {{ asList(selectedRadarModule.support_drivers).length }}</span>
                  <span>pressure {{ asList(selectedRadarModule.pressure_drivers).length }}</span>
                  <span>tone {{ moduleDisplayClass(selectedRadarModule) }}</span>
                </div>
                <div
                  v-if="selectedRadarModule.crowding_state || selectedRadarModule.positioning_state || selectedRadarModule.top_positioning_state || selectedRadarModule.long_short_squeeze_risk"
                  class="module-stats semantic-stats"
                >
                  <span>crowding {{ text(selectedRadarModule.crowding_state) }}</span>
                  <span>positioning {{ text(selectedRadarModule.top_positioning_state ?? selectedRadarModule.positioning_state) }}</span>
                  <span>squeeze {{ text(selectedRadarModule.long_short_squeeze_risk) }}</span>
                </div>
                <div
                  v-if="hasTradeStructureStates(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span v-for="row in tradeStructureStateRows(selectedRadarModule)" :key="`trade-${row[0]}`">
                    {{ row[0] }} {{ text(row[1]) }}
                  </span>
                </div>
                <div
                  v-if="isOptionsVolatilityModule(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span>structure {{ text(optionsVolatilityContract(selectedRadarModule).options_short_term_state, 'vol_neutral') }}</span>
                  <span>risk {{ text(optionsVolatilityContract(selectedRadarModule).risk_score) }}</span>
                  <span>hint {{ text(optionsVolatilityContract(selectedRadarModule).trade_permission_hint, 'normal') }}</span>
                </div>
                <div
                  v-if="isEventPolicyModule(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span>gate {{ text(eventPolicyContract(selectedRadarModule).event_short_term_state, 'event_neutral') }}</span>
                  <span>phase {{ text(eventPolicyContract(selectedRadarModule).event_window_phase, 'neutral') }}</span>
                  <span>reason {{ text(eventPolicyContract(selectedRadarModule).trade_gate.reason_code, 'EVENT_NEUTRAL') }}</span>
                </div>
                <div
                  v-if="isCryptoBreadthModule(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span>state {{ text(cryptoBreadthContract(selectedRadarModule).crypto_breadth_state, 'neutral_wait_confirm') }}</span>
                  <span>BTC {{ text(cryptoBreadthContract(selectedRadarModule).btc_implication, 'neutral') }}</span>
                  <span>risk {{ text(cryptoBreadthContract(selectedRadarModule).risk_score) }}</span>
                </div>
                <div
                  v-if="isMacroRadarModule(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span>state {{ text(macroRadarContract(selectedRadarModule).macro_trend_state, 'macro_neutral') }}</span>
                  <span>BTC {{ text(macroRadarContract(selectedRadarModule).btc_implication, 'neutral') }}</span>
                  <span>risk {{ text(macroRadarContract(selectedRadarModule).risk_score) }}</span>
                </div>
                <div
                  v-if="isDollarLiquidityModule(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span>state {{ text(dollarLiquidityContract(selectedRadarModule).dollar_liquidity_state, 'liquidity_neutral') }}</span>
                  <span>funding {{ text(dollarLiquidityContract(selectedRadarModule).repo_funding_pressure.state, 'missing') }}</span>
                  <span>BTC {{ text(dollarLiquidityContract(selectedRadarModule).btc_response_confirmation.state, 'missing') }}</span>
                </div>
                <div
                  v-if="isTreasuryCreditModule(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span>state {{ text(treasuryCreditContract(selectedRadarModule).treasury_credit_state, 'treasury_credit_neutral') }}</span>
                  <span>credit {{ text(treasuryCreditContract(selectedRadarModule).credit_stress.state, 'missing') }}</span>
                  <span>BTC {{ text(treasuryCreditContract(selectedRadarModule).btc_response_confirmation.state, 'missing') }}</span>
                </div>
                <div
                  v-if="isFundFlowModule(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span>state {{ text(fundFlowContract(selectedRadarModule).fund_flow_state, 'fund_flow_neutral') }}</span>
                  <span>ETF {{ text(fundFlowContract(selectedRadarModule).etf_demand.state, 'missing') }}</span>
                  <span>BTC {{ text(fundFlowContract(selectedRadarModule).btc_response_confirmation.state, 'missing') }}</span>
                </div>
                <div
                  v-if="isOnchainValuationModule(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span>stage {{ text(onchainValuationContract(selectedRadarModule).signal_stage, 'none') }}</span>
                  <span>bias {{ text(onchainValuationContract(selectedRadarModule).module_bias, 'neutral') }}</span>
                  <span>STH {{ text(onchainValuationContract(selectedRadarModule).cost_basis.state, 'missing') }}</span>
                </div>
                <div
                  v-if="isAsiaRiskModule(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span>stage {{ text(asiaRiskContract(selectedRadarModule).signal_stage, 'none') }}</span>
                  <span>state {{ text(asiaRiskContract(selectedRadarModule).asia_risk_state, 'asia_risk_neutral') }}</span>
                  <span>BTC {{ text(asiaRiskContract(selectedRadarModule).btc_response_confirmation.state, 'missing') }}</span>
                </div>
                <div
                  v-if="isKlineOrderflowModule(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span>stage {{ text(klineOrderflowContract(selectedRadarModule).signal_stage, 'none') }}</span>
                  <span>state {{ text(klineOrderflowContract(selectedRadarModule).kline_orderflow_state, 'neutral') }}</span>
                  <span>vol {{ text(klineOrderflowContract(selectedRadarModule).volatility_regime, 'normal_vol') }}</span>
                </div>
                <div
                  v-if="isBtcAdoptionModule(selectedRadarModule)"
                  class="module-stats semantic-stats"
                >
                  <span>stage {{ text(btcAdoptionContract(selectedRadarModule).signal_stage, 'none') }}</span>
                  <span>state {{ text(btcAdoptionContract(selectedRadarModule).btc_adoption_state, 'btc_adoption_neutral') }}</span>
                  <span>BTC {{ text(btcAdoptionContract(selectedRadarModule).btc_response_confirmation.state, 'missing') }}</span>
                </div>
              </article>

              <section class="radar-scope-card-rail right" aria-label="Top radar metrics right">
                <button
                  v-for="(metric, index) in radarMetricRail('right')"
                  :key="`rail-right-${text(metric.evidence_id ?? metric.metric_id)}`"
                  class="radar-scope-metric-card"
                  :class="[radarMetricClass(metric), selectedRadarMetricId === text(metric.metric_id) ? 'selected' : '']"
                  @click="selectRadarMetric(metric)"
                >
                  <div class="metric-card-head">
                    <strong>{{ metricLabel(metric.metric_id) }}</strong>
                    <span class="pill">top {{ index * 2 + 2 }}</span>
                  </div>
                  <p>{{ radarMetricSummary(metric) }}</p>
                  <div class="metric-card-meta">
                    <span>{{ radarMetricCompactMeta(metric) }}</span>
                    <span>q {{ text(metric.quality_score) }}</span>
                  </div>
                  <div class="metric-score-track"><span :style="{ width: radarMetricBarWidth(metric) }"></span></div>
                </button>
              </section>
            </section>

            <aside class="radar-metric-panel">
              <section v-if="isBtcTotalStateModule(selectedRadarModule)" class="btc-total-state-grid">
                <article
                  v-for="card in btcTotalLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isBtcTotalStateModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>Funding / OI are read with price_state. Halving and block height stay out of direction drivers.</p>
              </section>
              <section v-if="isOptionsVolatilityModule(selectedRadarModule)" class="btc-total-state-grid options-volatility-grid">
                <article
                  v-for="card in optionsVolatilityLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isOptionsVolatilityModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>Options Volatility adjusts risk, confidence and trade permission. It does not turn put-call, skew, max pain or gamma wall into bullish/bearish drivers.</p>
              </section>
              <section v-if="isEventPolicyModule(selectedRadarModule)" class="btc-total-state-grid event-policy-grid">
                <article
                  v-for="card in eventPolicyLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isEventPolicyModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>Event Policy adjusts risk locks, trade permission and size multiplier. CPI, FOMC, Fed speech and blackout windows do not become bullish/bearish drivers.</p>
              </section>
              <section v-if="isCryptoBreadthModule(selectedRadarModule)" class="btc-total-state-grid crypto-breadth-grid">
                <article
                  v-for="card in cryptoBreadthLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isCryptoBreadthModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>Crypto Breadth confirms or refutes BTC trend quality. BTC dominance, ETHBTC, TOTAL2 and sector heat are not standalone bullish/bearish drivers.</p>
              </section>
              <section v-if="isMacroRadarModule(selectedRadarModule)" class="btc-total-state-grid macro-radar-grid">
                <article
                  v-for="card in macroRadarLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isMacroRadarModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>Macro Radar confirms or refutes BTC trend through cross-asset context. DXY, VIX, Nasdaq, rates, gold and oil are not standalone BTC direction drivers.</p>
              </section>
              <section v-if="isDollarLiquidityModule(selectedRadarModule)" class="btc-total-state-grid macro-radar-grid">
                <article
                  v-for="card in dollarLiquidityLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isDollarLiquidityModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>Dollar Liquidity confirms or refutes BTC trend through net liquidity impulse, reserve buffer, repo funding pressure and BTC response. Fed balance sheet, TGA, RRP and SOFR are not standalone bullish/bearish drivers.</p>
              </section>
              <section v-if="isTreasuryCreditModule(selectedRadarModule)" class="btc-total-state-grid macro-radar-grid">
                <article
                  v-for="card in treasuryCreditLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isTreasuryCreditModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>Treasury Credit separates rates warning, real-yield pressure, curve regime, credit widening and BTC residual. 2Y, 10Y, HY OAS or falling yields alone do not become BTC direction calls.</p>
              </section>
              <section v-if="isFundFlowModule(selectedRadarModule)" class="btc-total-state-grid macro-radar-grid">
                <article
                  v-for="card in fundFlowLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isFundFlowModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>Fund Flow confirms or refutes BTC trend through ETF demand, stablecoin liquidity, exchange supply and BTC response. ETF inflow, stablecoin growth, balance decline or outflow easing are not standalone BTC direction calls.</p>
              </section>
              <section v-if="isOnchainValuationModule(selectedRadarModule)" class="btc-total-state-grid macro-radar-grid">
                <article
                  v-for="card in onchainValuationLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isOnchainValuationModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>On-chain Valuation separates slow regime from fast trend-delta. MVRV/NUPL, SOPR, realized cap, STH cost basis and miner/whale proxies cannot become confirmed direction without BTC response and residual confirmation.</p>
              </section>
              <section v-if="isBtcAdoptionModule(selectedRadarModule)" class="btc-total-state-grid macro-radar-grid">
                <article
                  v-for="card in btcAdoptionLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isBtcAdoptionModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>BTC Adoption confirms or refutes trend through real settlement demand and BTC response. Active addresses, transaction count, hashrate, Lightning capacity and fees are not standalone BTC direction calls.</p>
              </section>
              <section v-if="isAsiaRiskModule(selectedRadarModule)" class="btc-total-state-grid macro-radar-grid">
                <article
                  v-for="card in asiaRiskLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isAsiaRiskModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>Asia Risk treats USDJPY, USDCNH, Nikkei, HSTECH and Korea premium as pressure or demand context. Confirmed direction requires BTC Asia-session response, residual and VWAP/range structure.</p>
              </section>
              <section v-if="isTradeStructureFlowModule(selectedRadarModule)" class="btc-total-state-grid macro-radar-grid">
                <article
                  v-for="card in tradeStructureFlowLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isTradeStructureFlowModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>Trade Structure Flow separates structure pressure from BTC direction. Volume, taker ratio, funding, OI, liquidity thinning and liquidation spikes do not become confirmed signals without price acceptance and standardized residual confirmation.</p>
              </section>
              <section v-if="isKlineOrderflowModule(selectedRadarModule)" class="btc-total-state-grid macro-radar-grid">
                <article
                  v-for="card in klineOrderflowLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isKlineOrderflowModule(selectedRadarModule)" class="detail-section warning">
                <h4>Direction Boundary</h4>
                <p>Kline Orderflow separates fast warning from confirmed trend. Taker buy/sell ratio, volume spikes, VWAP crosses and one 5m candle do not become direction calls without price acceptance, VWAP duration and residual confirmation.</p>
              </section>
              <section v-if="isDerivativesCrowdingModule(selectedRadarModule)" class="btc-total-state-grid macro-radar-grid">
                <article
                  v-for="card in derivativesCrowdingLayerCards(selectedRadarModule)"
                  :key="card.key"
                  class="btc-total-state-card"
                  :class="card.key"
                >
                  <div>
                    <span class="pill">{{ card.title }}</span>
                    <h4>{{ text(card.state, 'missing') }}</h4>
                    <p>{{ card.meta }}</p>
                  </div>
                  <p>{{ card.note }}</p>
                  <dl v-if="card.rows.length">
                    <template v-for="[key, value] in card.rows" :key="`${card.key}-${key}`">
                      <dt>{{ key }}</dt>
                      <dd>{{ text(value) }}</dd>
                    </template>
                  </dl>
                </article>
              </section>
              <section v-if="isDerivativesCrowdingModule(selectedRadarModule)" class="detail-section warning">
                <h4>Derivatives Scope</h4>
                <p>{{ derivativesCrowdingScopeText() }} Funding, OI, long/short ratios and liquidation spikes are never standalone BTC direction calls; v2.5 needs BTC response, trend prior and standardized residual alignment.</p>
              </section>
              <section class="detail-section">
                <span class="pill" :class="radarMetricClass(selectedRadarMetric)">selected metric</span>
                <h3>{{ evidenceTitle(selectedRadarMetric) }}</h3>
                <p>{{ radarMetricSummary(selectedRadarMetric) }}</p>
                <div class="detail-kv-grid">
                  <span><small>value</small><strong>{{ text(selectedRadarMetric.value ?? selectedRadarMetric.current_value) }}</strong></span>
                  <span><small>metric score</small><strong>{{ text(selectedRadarMetric.metric_score) }}</strong></span>
                  <span><small>effective</small><strong>{{ text(selectedRadarMetric.metric_effective_score) }}</strong></span>
                  <span><small>quality</small><strong>{{ text(selectedRadarMetric.quality_score) }}</strong></span>
                </div>
              </section>
              <section class="detail-section">
                <h4>Source & Freshness</h4>
                <p>{{ evidenceSourceLine(selectedRadarMetric) }}</p>
                <p>{{ evidenceFreshnessLine(selectedRadarMetric) }}</p>
                <p>horizon {{ text(selectedRadarMetric.horizon_tags) }} · duplicate {{ text(selectedRadarMetric.duplicate_group_id) }}</p>
              </section>
              <section
                v-if="selectedRadarMetric.positioning_signal || selectedRadarMetric.crowding_contribution || selectedRadarMetric.positioning_scope"
                class="detail-section"
              >
                <h4>Positioning Semantics</h4>
                <p>
                  signal {{ text(selectedRadarMetric.positioning_signal) }} · contribution
                  {{ text(selectedRadarMetric.crowding_contribution) }} · scope
                  {{ text(selectedRadarMetric.positioning_scope) }}
                </p>
                <p>Long/short ratio is a positioning skew signal, not long OI / short OI.</p>
              </section>
              <section
                v-if="isDerivativesCrowdingModule(selectedRadarModule) && ['btc_funding_rate', 'btc_open_interest'].includes(text(selectedRadarMetric.metric_id))"
                class="detail-section"
              >
                <h4>Funding / OI Scope</h4>
                <p>In derivatives_crowding this metric describes crowding, leverage heat or squeeze risk. It is not the BTC Total State short-term direction driver.</p>
              </section>
              <section
                v-if="selectedRadarMetric.price_response_state || selectedRadarMetric.flow_price_efficiency_state || selectedRadarMetric.price_response_source"
                class="detail-section"
              >
                <h4>Price Response Confirmation</h4>
                <p>
                  state {{ text(selectedRadarMetric.price_response_state) }} · confidence
                  {{ text(selectedRadarMetric.price_response_confidence) }} · efficiency
                  {{ text(selectedRadarMetric.flow_price_efficiency_state) }}
                </p>
                <p>source {{ text(selectedRadarMetric.price_response_source) }} · confirmation layer only, not a standalone trend trigger.</p>
              </section>
              <section
                v-if="multiSourceConflictRows.some((row) => conflictMetricId(row) === text(selectedRadarMetric.metric_id))"
                class="detail-section warning"
              >
                <h4>Source Arbitration</h4>
                <p
                  v-for="row in multiSourceConflictRows.filter((item) => conflictMetricId(item) === text(selectedRadarMetric.metric_id)).slice(0, 2)"
                  :key="`${conflictMetricId(row)}-${text(row.conflict_origin)}`"
                >
                  {{ conflictTypeLabel(row) }} · selected {{ conflictSelectedSource(row) }} · {{ conflictImpactText(row) }}
                </p>
              </section>
              <section class="detail-section">
                <h4>Actions</h4>
                <div class="article-actions">
                  <button class="small-link" @click="openSelectedRadarEvidence(selectedRadarMetric)">Open Evidence</button>
                  <button class="small-link" @click="openSourceDetail(String(selectedRadarMetric.source_id))">Open Source</button>
                </div>
              </section>
              <section v-if="selectedRadarMetric.fallback_used || selectedRadarMetric.is_stale || selectedRadarMetric.available === false" class="detail-section warning">
                <h4>Quality Boundary</h4>
                <p>fallback {{ text(selectedRadarMetric.fallback_used) }} · stale {{ text(selectedRadarMetric.is_stale) }} · available {{ text(selectedRadarMetric.available) }}</p>
                <p>{{ text(selectedRadarMetric.fallback_reason, 'No fallback reason') }}</p>
              </section>
            </aside>
          </section>

          <section v-else class="empty-note">
            请选择一个 Radar module。Dashboard 拓扑节点点击后也会进入这里。
          </section>

          <section v-if="selectedRadarMetrics.length" class="radar-audit-table">
            <div class="section-title-row">
              <h3>Metric Audit Table</h3>
              <span class="pill">{{ selectedRadarMetrics.length }} metrics</span>
            </div>
            <div class="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>metric</th>
                    <th>direction</th>
                    <th>value</th>
                    <th>score</th>
                    <th>quality</th>
                    <th>source</th>
                    <th>summary</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="metric in selectedRadarMetrics" :key="text(metric.evidence_id ?? metric.metric_id)" @click="selectRadarMetric(metric)">
                    <td>{{ metricLabel(metric.metric_id) }}</td>
                    <td>{{ text(metric.direction) }}</td>
                    <td>{{ text(metric.value ?? metric.current_value) }}</td>
                    <td>{{ text(metric.metric_effective_score ?? metric.metric_score) }}</td>
                    <td>{{ text(metric.quality_score) }}</td>
                    <td>{{ text(metric.source_id) }}</td>
                    <td>{{ radarMetricSummary(metric) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </article>

        <article v-else-if="activePage === 'evidence'" class="panel evidence-page">
          <div class="panel-head">
            <div>
              <h2>Evidence Workbench</h2>
              <p>P4.5 scored evidence | data + interpretation + run context</p>
            </div>
            <div class="article-actions">
              <span class="pill">{{ filteredEvidenceItems.length }} / {{ evidenceStats.total }} items</span>
              <span class="pill bull">+{{ evidenceStats.positive }}</span>
              <span class="pill bear">-{{ evidenceStats.negative }}</span>
              <span class="pill neutral">0 {{ evidenceStats.zero }}</span>
              <span v-if="evidenceStats.fallback" class="pill quality">fallback {{ evidenceStats.fallback }}</span>
              <span v-if="evidenceStats.stale" class="pill quality">stale {{ evidenceStats.stale }}</span>
            </div>
          </div>

          <section class="article-meta-grid">
            <span><small>collect</small><code>{{ text(evidenceRunLineage.collect_run_id) }}</code></span>
            <span><small>p2 radar</small><code>{{ text(evidenceRunLineage.p2_radar_run_id) }}</code></span>
            <span><small>p3</small><code>{{ text(evidenceRunLineage.p3_run_id) }}</code></span>
            <span><small>pack</small><code>{{ text(evidenceRunLineage.pack_id) }}</code></span>
            <span><small>final</small><code>{{ text(evidenceRunLineage.final_run_id) }}</code></span>
            <span><small>runtime</small><strong>{{ text(evidenceRunLineage.runtime_mode) }}</strong></span>
          </section>

          <section class="evidence-toolbar">
            <label>
              <small>Radar module</small>
              <select v-model="evidenceModuleFilter">
                <option value="all">All modules</option>
                <option v-for="moduleId in evidenceModules" :key="moduleId" :value="moduleId">{{ moduleId }}</option>
              </select>
            </label>
            <label>
              <small>Score bucket</small>
              <select v-model="evidenceBucketFilter">
                <option value="all">All buckets</option>
                <option v-for="bucket in evidenceBuckets" :key="bucket" :value="bucket">{{ bucket }}</option>
              </select>
            </label>
            <button @click="evidenceModuleFilter = 'all'; evidenceBucketFilter = 'all'">Reset filters</button>
            <button @click="navigateTo('conflict')">Source conflicts {{ conflictStats.total }}</button>
          </section>

          <section v-if="multiSourceConflictRows.length" class="conflict-strip">
            <article
              v-for="row in multiSourceConflictRows.slice(0, 3)"
              :key="`evidence-conflict-${conflictMetricId(row)}-${text(row.conflict_origin)}`"
              class="conflict-mini-card"
              :class="conflictSeverityClass(row)"
              @click="openConflictEvidence(row)"
            >
              <strong>{{ metricLabel(conflictMetricId(row)) }}</strong>
              <span>{{ conflictTypeLabel(row) }} · selected {{ conflictSelectedSource(row) }}</span>
              <small>{{ conflictImpactText(row) }}</small>
            </article>
          </section>

          <section class="evidence-layout">
            <div class="evidence-list">
          <button
            v-for="item in filteredEvidenceItems.slice(0, 120)"
            :key="text(item.evidence_id)"
            class="evidence-row"
            :class="[directionClass(evidenceDisplayDirection(item)), selectedEvidenceId === text(item.evidence_id) ? 'selected' : '']"
            @click="openEvidenceDetail(String(item.evidence_id))"
          >
            <span class="evidence-row-title">
              <strong>{{ evidenceTitle(item) }}</strong>
              <em>{{ text(item.radar_module) }}</em>
            </span>
                <span class="evidence-row-body">{{ evidenceOneLine(item) }}</span>
                <span class="evidence-row-meta">
                  <strong class="score-chip" :class="directionClass(evidenceDisplayDirection(item))">{{ evidenceDirectionLabel(item) }}</strong>
                  <small>{{ evidenceScoreLine(item) }}</small>
                  <small v-if="evidenceCompositeLine(item)">{{ evidenceCompositeLine(item) }}</small>
                  <small>{{ evidenceFreshnessLine(item) }}</small>
                </span>
            <span class="evidence-row-tags">
              <i v-for="badge in evidenceBadges(item)" :key="`${text(item.evidence_id)}-${badge}`" :class="evidenceBadgeClass(badge)">{{ badge }}</i>
            </span>
            <small class="evidence-source-line">{{ text(item.radar_module) }} · {{ text(item.source_id) }}</small>
          </button>
            </div>
          </section>
        </article>

        <article v-else-if="activePage === 'article'" class="panel article-page article-page-v2">
          <div class="panel-head">
            <div>
              <h2>Article Center</h2>
              <p>P4.5 Report v2 · latest and replay snapshots</p>
            </div>
            <div class="article-actions">
              <span class="pill" :class="directionClass(articleFinalPayload.final_view ?? state.articles?.final_view)">
                {{ finalViewText }}
              </span>
              <button v-if="state.routeContext.isHistorical" @click="exitArticleHistory">Exit Replay</button>
              <button @click="openAuditReports">Audit HTML</button>
            </div>
          </div>

          <section class="article-meta-grid">
            <span><small>final_run_id</small><code>{{ text(articleRunLineage.final_run_id) }}</code></span>
            <span><small>pack_id</small><code>{{ text(articleRunLineage.pack_id) }}</code></span>
            <span><small>article_run_id</small><code>{{ text(articleRunLineage.article_run_id) }}</code></span>
            <span><small>llm_research_run_id</small><code>{{ text(articleRunLineage.llm_research_run_id) }}</code></span>
            <span><small>runtime</small><strong>{{ articleRuntimeMode }}</strong></span>
            <span><small>status</small><strong>{{ articleStatusText }}</strong></span>
          </section>

          <section class="article-layout">
            <article class="article-card publish-card">
              <div class="article-card-head">
                <h3>{{ articleTitle(articlePublish, 'Publish Article') }}</h3>
                <span class="pill bull">{{ text(articlePublish.publish_type, 'market_view') }}</span>
              </div>
              <p v-for="line in articleParagraphs(articlePublish, '暂无发文正文')" :key="`pub-${line}`">{{ line }}</p>
              <div class="article-flags">
                <span>safe {{ text(articlePublish.safe_to_publish) }}</span>
                <span>score {{ text(articlePublish.publish_score) }}</span>
                <span>{{ text(articlePublish.reject_reason, 'no reject') }}</span>
              </div>
            </article>

            <article class="article-card research-card">
              <div class="article-card-head">
                <h3>{{ articleTitle(articleResearch, 'Research Article') }}</h3>
                <span class="pill mixed">research</span>
              </div>
              <p v-for="line in articleParagraphs(articleResearch, articleText(state.articles?.deterministic_article))" :key="`research-${line}`">{{ line }}</p>
            </article>
          </section>

          <section class="article-layout secondary">
            <article class="article-card">
              <div class="article-card-head">
                <h3>LLM Research Appendix</h3>
                <span class="pill quality">internal_reference</span>
              </div>
              <div class="module-stats">
                <span>{{ text(articleLlmResearch.provider, 'deepseek') }}</span>
                <span>{{ text(articleLlmResearch.model, 'model') }}</span>
                <span>{{ text(articleLlmResearch.status, 'pending') }}</span>
                <span>{{ text(articleLlmResearch.runtime_mode, 'llm') }}</span>
              </div>
              <p>{{ articleTitle(articleLlmResearch, 'LLM appendix') }}</p>
              <details>
                <summary>Open internal reference text</summary>
                <p v-for="line in articleParagraphs(articleLlmResearch.article, '暂无 LLM 附录正文')" :key="`llm-${line}`">{{ line }}</p>
              </details>
            </article>

            <article class="article-card">
              <div class="article-card-head">
                <h3>Analyst Articles</h3>
                <span class="pill">{{ articleAnalystRows.length }} analysts</span>
              </div>
              <button v-for="item in articleAnalystRows" :key="text(item.analyst_id)" class="analyst-row" :class="directionClass(item.direction_view ?? item.status)">
                <strong>{{ text(item.analyst_id) }}</strong>
                <span>{{ text(item.status) }} · {{ text(item.provider, 'deterministic') }}</span>
                <small>{{ text(item.title) }}</small>
              </button>
            </article>
          </section>

          <section class="article-card">
            <div class="article-card-head">
              <h3>Evidence Citations</h3>
              <span class="pill">{{ articleEvidenceCitations.length }} refs</span>
            </div>
            <div class="citation-grid">
              <button v-for="item in articleEvidenceCitations" :key="item.id" class="citation-chip" :class="directionClass(item.evidence?.direction)" @click="openArticleCitation(item.id)">
                <strong>{{ citationLabel(item.id, item.evidence) }}</strong>
                <small>{{ citationMeta(item.evidence) }}</small>
              </button>
            </div>
          </section>

          <section class="article-card">
            <div class="article-card-head">
              <h3>History Snapshots</h3>
              <span class="pill">{{ articleHistoryRows.length }} runs</span>
            </div>
            <div class="history-filter-row">
              <span>filter: latest / replay / status-aware snapshots</span>
              <span>current mode: {{ text(state.routeContext.isHistorical ? 'replay' : 'latest') }}</span>
            </div>
            <button v-for="row in articleHistoryRows" :key="text(row.final_run_id)" class="snapshot-row" :class="articleSnapshotClass(row)" @click="openArticleSnapshot(row)">
              <span>
                <strong>{{ text(row.title, 'P4.5 Research Article') }}</strong>
                <small>{{ articleSnapshotStatus(row) }}</small>
              </span>
              <code>{{ text(row.final_run_id) }}</code>
              <em>{{ text(row.created_at) }}</em>
            </button>
          </section>
        </article>

        <article v-else-if="false && activePage === 'article'" class="panel article-page">
          <h2>Research / Publish Article</h2>
          <h3>发文版本</h3>
          <p>{{ text(state.articles?.publish_article?.body, '暂无发文正文') }}</p>
          <h3>研究正文</h3>
          <p>{{ text(state.articles?.research_article?.executive_summary ?? state.articles?.deterministic_article) }}</p>
          <h3>LLM Research Appendix</h3>
          <p>internal_reference · {{ text(state.articles?.llm_research?.status) }}</p>
          <p>{{ text(state.articles?.llm_research?.title) }}</p>
          <h3>四位分析师 LLM</h3>
          <p v-for="item in analystArticles" :key="text(item.analyst_id)">
            {{ text(item.analyst_id) }} · {{ text(item.status) }} · {{ text(item.title) }}
          </p>
        </article>

        <article v-else-if="activePage === 'eventWatchtower'" class="panel event-watchtower-page">
          <div class="panel-head event-page-head">
            <div>
              <h2>Event Window / Policy Shock Watchtower</h2>
              <p>独立常驻 daemon · 官方事件、预期漂移、Fed 文本、突发冲击和 BTC 事件后反应。</p>
            </div>
            <div class="panel-actions">
              <span class="pill" :class="alertTone(eventWindowState.emergency_level)">{{ text(eventWindowState.emergency_level, 'none') }}</span>
              <button class="pill bull" @click="store.runEventWindowOnce()">Run Event Once</button>
              <button class="pill" @click="store.runEventWindowAuditBundle()">Audit Bundle</button>
              <button v-if="text(eventWindowDaemon.status) === 'paused_by_user'" class="pill bull" @click="store.resumeEventWindowDaemon()">resume daemon</button>
              <button v-else class="pill mixed" @click="store.pauseEventWindowDaemon()">pause daemon</button>
            </div>
          </div>

          <nav class="event-watch-tabs" aria-label="Event Watchtower sections">
            <button
              v-for="tab in eventWatchtowerTabs"
              :key="tab.id"
              class="event-watch-tab"
              :class="{ active: eventWatchtowerTab === tab.id }"
              @click="eventWatchtowerTab = tab.id"
            >
              {{ tab.label }}
            </button>
          </nav>

          <section class="event-status-strip">
            <article class="event-stat-card" :class="alertTone(eventWindowState.emergency_level)">
              <small>Emergency Level</small>
              <strong>{{ text(eventWindowState.emergency_level, 'none') }}</strong>
              <span>{{ text(eventWindowState.event_window_state, 'calendar_monitor') }}</span>
            </article>
            <article class="event-stat-card">
              <small>Radar Trust</small>
              <strong>{{ text(eventWindowOverlay.ordinary_radar_trust, 'normal') }}</strong>
              <span>confidence cap {{ text(eventWindowOverlay.confidence_cap, 'none') }}</span>
            </article>
            <article class="event-stat-card">
              <small>Overlay</small>
              <strong>{{ text(eventWindowOverlay.trade_permission_modifier, 'none') }}</strong>
              <span>direct score impact {{ eventWindowDirectScoreImpact }}</span>
            </article>
            <article class="event-stat-card">
              <small>Active Event</small>
              <strong>{{ text(eventWindowActive.event_type, 'event') }} · {{ daysText(Number(eventWindowActive.time_to_event_sec ?? 0) / 86400) }}</strong>
              <span>{{ text(eventWindowActive.title, 'Calendar monitor') }}</span>
            </article>
            <article class="event-stat-card" :class="daemonHealthTone(eventWindowDaemonHealthState)">
              <small>Daemon Runtime</small>
              <strong>{{ eventWindowDaemonHealthState }}</strong>
              <span>
                heartbeat {{ text(eventWindowDaemon.last_tick_age_sec ?? eventWindowDaemon.last_snapshot_age_sec, '-') }}s ·
                {{ text(eventWindowDaemon.runtime_code_version, 'event_watchtower.v3') }}
              </span>
            </article>
            <article class="event-stat-card" :class="marketReturnTone(eventWindowMarketReturns['1h'])">
              <small>Market Probe</small>
              <strong>1h {{ marketReturnPct(eventWindowMarketReturns['1h']) }}</strong>
              <span>probe age {{ text(eventWindowDaemon.market_probe_age_sec ?? eventWindowMarketProbe.freshness_sec, '-') }}s</span>
            </article>
            <article class="event-stat-card" :class="sourceModeTone(eventWindowSourceMode)">
              <small>Source Quality</small>
              <strong>{{ eventWindowSourceMode }}</strong>
              <span>
                {{ eventWindowSourceQuality.functional_live ? 'functional live' : 'capability limited' }} ·
                live {{ eventWindowSourceCounts.live }} · partial {{ eventWindowSourceCounts.partial }} ·
                fallback {{ eventWindowSourceCounts.fallback }} · failed {{ eventWindowSourceCounts.failed }}
              </span>
            </article>
          </section>

          <section class="event-visibility-controls">
            <div>
              <strong>Visibility Controls</strong>
              <span>
                snapshot {{ text(eventWatchtowerPayload.snapshot_id, '-') }} ·
                valid {{ text(eventWindowState.valid_until, '-') }}
              </span>
            </div>
            <div class="event-visibility-actions">
              <button class="event-action-button bull" :disabled="eventCurrentAlertAcked" @click="ackCurrentEventAlert">
                {{ eventCurrentAlertAcked ? 'Acked' : 'Ack current alert' }}
              </button>
              <button class="event-action-button mixed" :disabled="eventCurrentAlertHidden" @click="dismissEventFloatingAlertSession">
                Dismiss session
              </button>
              <button class="event-action-button" :disabled="!eventWindowHiddenKeys.length && !dismissedCriticalAlertKey && !eventFloatingAlertMuted" @click="restoreEventWindowHiddenAlerts">
                Show hidden / restore
              </button>
              <button class="event-action-button" :disabled="eventCriticalLikeActive || eventCurrentAlertHidden" @click="clearVisibleNonCriticalEventAlerts">
                Clear visible
              </button>
              <span class="event-chip" :class="eventCurrentAlertAcked ? 'bull' : 'quality'">ack {{ eventCurrentAlertAcked ? 'yes' : 'no' }}</span>
              <span class="event-chip" :class="eventCurrentAlertHidden ? 'mixed' : 'quality'">hidden {{ eventCurrentAlertHidden ? 'session' : 'none' }}</span>
            </div>
            <p>
              Visibility controls do not modify Event Window state, SQLite history, BTC score, or radar score.
              Critical state remains visible in status, rail, dashboard summary, and audit views.
            </p>
          </section>

          <section v-if="eventWatchtowerTab === 'live'" class="event-watchtower-live-grid">
            <div class="event-live-main">
              <section class="event-two-panel">
                <article v-if="eventCurrentAlertHidden" class="event-panel-card event-current-alert event-current-alert-hidden">
                  <header>
                    <h3>Current Alert</h3>
                    <span class="pill mixed">hidden for session</span>
                  </header>
                  <p class="event-large-copy">
                    This alert is hidden only in the current browser session. Backend state, SQLite history, BTC score,
                    and radar score are unchanged.
                  </p>
                  <div class="event-chip-row">
                    <span class="event-chip blue">state {{ text(eventWindowState.event_window_state, 'calendar_monitor') }}</span>
                    <span class="event-chip" :class="alertTone(eventWindowState.emergency_level)">emergency {{ text(eventWindowState.emergency_level, 'none') }}</span>
                    <span class="event-chip">direct_score_impact={{ eventWindowDirectScoreImpact }}</span>
                  </div>
                </article>
                <article v-else class="event-panel-card event-current-alert" :class="[alertTone(eventWindowState.emergency_level), { acknowledged: eventCurrentAlertAcked }]">
                  <header>
                    <h3>Current Alert</h3>
                    <span class="pill" :class="alertTone(eventWindowState.emergency_level)">
                      {{ eventCurrentAlertAcked ? 'acked · ' : '' }}{{ text(eventWindowState.emergency_level, 'none') }}
                    </span>
                  </header>
                  <p class="event-large-copy">
                    <strong>{{ text(eventWindowActive.title, 'Calendar monitor') }}</strong><br />
                    {{ text(eventWindowSummaryAlert.summary ?? eventWindowSummaryDetail, 'No active high-priority event alert. Ordinary radar trust remains normal.') }}
                  </p>
                  <div class="event-chip-row">
                    <span class="event-chip blue">state {{ text(eventWindowState.event_window_state, 'calendar_monitor') }}</span>
                    <span v-for="code in eventWindowReasonCodes.slice(0, 4)" :key="code" class="event-chip mixed">{{ code }}</span>
                    <span v-if="!eventWindowReasonCodes.length" class="event-chip">reason_codes none</span>
                    <span class="event-chip bull">{{ text(eventWindowOverlay.trade_permission_modifier, 'none') }}</span>
                    <span class="event-chip">valid {{ text(eventWindowState.valid_until, '-') }}</span>
                    <span class="event-chip">direct_score_impact={{ eventWindowDirectScoreImpact }}</span>
                  </div>
                </article>

                <article class="event-panel-card">
                  <header>
                    <h3>Expectation Drift</h3>
                    <span class="pill blue">live snapshots</span>
                  </header>
                  <div class="event-signal-row">
                    <strong>{{ text(eventWindowExpectation.expectation_gap, '-') }}</strong>
                    <span>
                      <b>Nowcast gap</b>
                      <small>{{ text(eventWindowExpectation.risk_direction, 'unknown') }} · Cleveland / consensus proxy</small>
                    </span>
                    <em class="pill mixed">{{ text(eventWindowExpectation.risk_direction, 'neutral') }}</em>
                  </div>
                  <div class="event-signal-row">
                    <strong>{{ text(eventWindowExpectation.rate_cut_prob_drift_1d, '-') }}</strong>
                    <span>
                      <b>Rate odds drift 24h</b>
                      <small>{{ text(eventWindowPredictionOdds.status, 'prediction market / proxy') }}</small>
                    </span>
                    <em class="pill">{{ text(eventWindowProviderConfidence.rate_probability_confidence, '-') }}</em>
                  </div>
                  <div class="event-signal-row">
                    <strong>{{ text(eventWindowExpectation.expectation_drift_1d, '-') }}</strong>
                    <span>
                      <b>Expectation drift 1d</b>
                      <small>calendar consensus / nowcast delta</small>
                    </span>
                    <em class="pill">{{ text(eventWindowSecondaryMesh.status, 'mesh') }}</em>
                  </div>
                  <div class="event-signal-row">
                    <strong>{{ text(eventWindowExpectation.expectation_drift_3d, '-') }}</strong>
                    <span>
                      <b>Expectation drift 3d</b>
                      <small>prediction odds {{ text(eventWindowPredictionOdds.current_odds ?? eventWindowPredictionOdds.odds ?? eventWindowPredictionOdds.rate_cut_probability, '-') }}</small>
                    </span>
                    <em class="pill">{{ text(eventWindowExpectation.prediction_market_status ?? eventWindowPredictionOdds.status, 'pending') }}</em>
                  </div>
                </article>
              </section>

              <section class="event-two-panel">
                <article class="event-panel-card">
                  <header>
                    <h3>Active Event Timeline</h3>
                    <span class="pill">Calendar View</span>
                  </header>
                  <div class="event-live-list">
                    <div
                      v-for="event in eventWindowCalendar.slice(0, 3)"
                      :key="text(event.event_id)"
                      class="event-live-row"
                    >
                      <strong>{{ daysText(Number(event.time_to_event_sec ?? eventWindowActive.time_to_event_sec ?? 0) / 86400) }}</strong>
                      <span>
                        <b>{{ text(event.title, 'Calendar event') }}</b>
                        <small>{{ text(event.source_tier, 'source') }} · {{ text(event.event_type, '-') }} · phase {{ text(event.phase, 'scheduled') }}</small>
                      </span>
                      <em class="pill" :class="alertTone(event.importance)">{{ text(event.importance, 'monitor') }}</em>
                    </div>
                    <div v-if="!eventWindowCalendar.length" class="event-empty-state">No calendar rows in current snapshot.</div>
                  </div>
                </article>

                <article class="event-panel-card event-llm-read-card">
                  <header>
                    <h3>Fed Speech / Policy Text</h3>
                    <span class="pill" :class="eventLlmToneClass(selectedEventLlmAnalysis.tone ?? eventWindowSpeechMonitor.tone)">
                      {{ text(selectedEventLlmAnalysis.provider, 'deepseek') }} · {{ text(selectedEventLlmAnalysis.status, 'success') }}
                    </span>
                  </header>
                  <div class="event-llm-kpi-grid">
                    <span>
                      <small>tone</small>
                      <strong>{{ text(selectedEventLlmAnalysis.tone ?? eventWindowSpeechMonitor.tone, 'pending') }}</strong>
                    </span>
                    <span>
                      <small>confidence</small>
                      <strong>{{ eventLlmConfidence(selectedEventLlmAnalysis) }}</strong>
                    </span>
                    <span>
                      <small>relevance</small>
                      <strong>{{ text(selectedEventLlmAnalysis.policy_relevance ?? eventWindowSpeechMonitor.policy_relevance, 'unknown') }}</strong>
                    </span>
                    <span :class="eventLlmBoundaryPass(selectedEventLlmAnalysis) ? 'bull' : 'bear'">
                      <small>boundary</small>
                      <strong>{{ eventLlmBoundaryPass(selectedEventLlmAnalysis) ? 'pass' : 'guard' }}</strong>
                    </span>
                  </div>
                  <p class="event-large-copy">{{ eventLlmSummary(selectedEventLlmAnalysis) }}</p>
                  <div class="event-chip-row">
                    <span class="event-chip blue">speaker {{ text(selectedEventLlmAnalysis.speaker ?? eventWindowSpeechMonitor.speaker, '-') }}</span>
                    <span class="event-chip">policy_relevance {{ text(selectedEventLlmAnalysis.policy_relevance ?? eventWindowSpeechMonitor.policy_relevance, 'unknown') }}</span>
                    <span class="event-chip">tone_confidence {{ eventLlmConfidence(selectedEventLlmAnalysis) }}</span>
                    <span class="event-chip" :class="eventLlmToneClass(selectedEventLlmAnalysis.tone ?? eventWindowSpeechMonitor.tone)">
                      {{ text(selectedEventLlmAnalysis.tone ?? eventWindowSpeechMonitor.tone, 'pending') }}
                    </span>
                    <span class="event-chip">no BTC direction · direct_score_impact={{ eventWindowDirectScoreImpact }}</span>
                    <span class="event-chip">analyses {{ eventWindowLlmAnalyses.length }}</span>
                  </div>
                </article>
              </section>

              <article class="event-panel-card">
                <header>
                  <h3>Timeline · {{ text(eventWatchtowerPayload.asof_ts, '-') }}</h3>
                  <span class="pill">hh:mm evidence stream</span>
                </header>
                <div class="event-stream-list">
                  <div
                    v-for="item in eventWindowTimeline.slice(0, 5)"
                    :key="`${text(item.type)}-${text(item.ts)}-${text(item.title)}`"
                    class="event-stream-item"
                    :class="alertTone(item.level)"
                  >
                    <strong>{{ text(item.ts, '-') }} · {{ text(item.title, 'event update') }}</strong>
                    <p>{{ text((item.payload as Row | undefined)?.summary ?? (item.payload as Row | undefined)?.reason_code ?? item.type, '-') }}</p>
                    <span class="event-chip">{{ text(item.level, 'info') }}</span>
                  </div>
                  <div v-if="!eventWindowTimeline.length" class="event-empty-state">No timeline rows in current snapshot.</div>
                </div>
              </article>

              <article class="event-panel-card event-control-panel">
                <header>
                  <h3>Daemon Scheduler / Manual Full Sweep</h3>
                  <span class="pill">{{ text(eventWindowDaemon.collection_mode, 'standalone_daemon') }}</span>
                </header>
                <div class="event-daemon-toolbar">
                  <button class="event-action-button bull" @click="store.runEventWindowOnce()">Run Event Once</button>
                  <button class="event-action-button" @click="store.runEventWindowAuditBundle()">Audit Bundle</button>
                  <button
                    v-if="text(eventWindowDaemon.status) === 'paused_by_user'"
                    class="event-action-button bull"
                    @click="store.resumeEventWindowDaemon()"
                  >
                    Resume Daemon
                  </button>
                  <button v-else class="event-action-button mixed" @click="store.pauseEventWindowDaemon()">Pause Daemon</button>
                </div>
                <div class="source-quality-strip">
                  <span><small>health</small><strong>{{ eventWindowDaemonHealthState }}</strong></span>
                  <span><small>watchdog</small><strong>{{ text((eventWindowDaemon.watchdog as Row | undefined)?.enabled, 'false') }}</strong></span>
                  <span><small>heartbeat</small><strong>{{ text(eventWindowDaemon.last_tick_age_sec, '-') }}s</strong></span>
                  <span><small>market probe</small><strong>{{ text(eventWindowDaemon.market_probe_age_sec, '-') }}s</strong></span>
                  <span><small>scheduler</small><strong>{{ text(eventWindowDaemon.scheduler_enabled, 'false') }}</strong></span>
                  <span><small>profile</small><strong>{{ text(eventWindowDaemon.cadence_profile, 'balanced') }}</strong></span>
                  <span><small>next due</small><strong>{{ eventWindowNextDueSources.length ? eventWindowNextDueSources.join(', ') : 'none' }}</strong></span>
                  <span><small>run once snapshot</small><strong>{{ text(eventWindowLastRunOnce.snapshot_id, '-') }}</strong></span>
                  <span><small>bundle</small><strong>{{ text(eventWindowAuditBundle.overall_status, '-') }}</strong></span>
                  <span><small>status schema</small><strong>{{ text(eventWindowDaemon.status_schema_version, '-') }}</strong></span>
                  <span><small>snapshot age</small><strong>{{ text(eventWindowDaemon.last_snapshot_age_sec, '-') }}s</strong></span>
                </div>
                <p v-if="eventWindowDaemonStaleReasons.length" class="event-source-note">
                  Daemon stale guard:
                  {{ eventWindowDaemonStaleReasons.join(', ') }}
                </p>
              </article>
            </div>

            <aside class="event-live-side">
              <article class="event-panel-card">
                <header>
                  <h3>Shock Fast Lane</h3>
                  <span class="pill" :class="eventWindowShockLane.shock_detected ? alertTone(eventWindowState.emergency_level) : 'quality'">
                    {{ eventWindowShockLane.shock_detected ? text(eventWindowShockLane.shock_type, 'shock') : 'none' }}
                  </span>
                </header>
                <p class="event-large-copy">
                  {{ text(eventWindowShockLane.summary, 'No official unscheduled policy shock. source_count below threshold; market stable; BTC move remains within normal event-window volatility.') }}
                </p>
                <div class="event-chip-row">
                  <span class="event-chip">confirmation {{ text(eventWindowShockLane.confirmation_level, 'none') }}</span>
                  <span class="event-chip">source_count {{ text(eventWindowShockLane.source_count, '0') }}</span>
                  <span class="event-chip bull">market {{ text(eventWindowShockLane.market_dislocation, 'stable') }}</span>
                  <span class="event-chip">micro {{ text(eventWindowShockLane.btc_microstructure_confirmation, 'none') }}</span>
                  <span class="event-chip">rumor {{ text(eventWindowShockLane.rumor_risk, 'none') }}</span>
                  <span class="event-chip mixed">window {{ text(eventWindowShockEvidence.primary_window, '-') }}</span>
                  <span class="event-chip">z {{ text(eventWindowShockEvidence.primary_return_z, '-') }}</span>
                </div>
                <div class="event-market-window-grid">
                  <span
                    v-for="row in eventWindowMarketReturnRows"
                    :key="row.window"
                    :class="marketReturnTone(row.value)"
                  >
                    <small>{{ row.window }}</small>
                    <strong>{{ marketReturnPct(row.value) }}</strong>
                    <em>z {{ text(row.z, '-') }}</em>
                  </span>
                </div>
                <div class="event-shock-llm-card">
                  <header>
                    <h4>LLM 中文观察</h4>
                    <span class="pill">{{ text(eventWindowShockLlmAnalysis.provider, 'pending') }}</span>
                    <span class="pill" :class="text(eventWindowShockLlmAnalysis.status) === 'success' ? 'quality' : 'mixed'">
                      {{ text(eventWindowShockLlmAnalysis.status, 'pending') }}
                    </span>
                  </header>
                  <p><strong>摘要：</strong>{{ text(eventWindowShockLlmAnalysis.summary_zh, '等待 Shock Fast Lane 生成中文观察。') }}</p>
                  <p><strong>原因：</strong>{{ text(eventWindowShockLlmAnalysis.risk_reason_zh, '暂无结构化冲击原因。') }}</p>
                  <p><strong>边界：</strong>{{ text(eventWindowShockLlmAnalysis.action_boundary_zh, '只解释事件窗口覆盖层，不改变 BTC 或 radar 分数。') }}</p>
                  <small>
                    Boundary pass: {{ text(eventWindowShockLlmAnalysis.boundary_pass, 'pending') }}
                    · source {{ text(eventWindowShockLlmAnalysis.analysis_source, 'live_api') }}
                    · snapshot {{ text(eventWindowShockLlmAnalysis.snapshot_id ?? eventWindowShockLlmAnalysis.source_snapshot_id, '-') }}
                  </small>
                </div>
              </article>

              <article class="event-panel-card">
                <header>
                  <h3>BTC Reaction Check</h3>
                  <span class="pill">{{ text(eventWindowPostReaction.reaction_state ?? eventWindowPostReaction.followthrough, 'pending') }}</span>
                  <span class="pill" :class="eventWindowPostReaction.event_lock_release_allowed ? 'bull' : 'mixed'">
                    unlock {{ text(eventWindowPostReaction.event_lock_release_allowed, 'false') }}
                  </span>
                </header>
                <div class="event-reaction-list">
                  <div class="event-reaction-row">
                    <strong>5m</strong>
                    <span><b>{{ marketReturnPct(eventWindowPostReaction.btc_return_5m) }}</b><small>post-event first impulse</small></span>
                    <em class="pill" :class="marketReturnTone(eventWindowPostReaction.btc_return_5m)">{{ text(eventWindowPostReaction.actual_status, 'pending') }}</em>
                  </div>
                  <div class="event-reaction-row">
                    <strong>30m</strong>
                    <span><b>{{ marketReturnPct(eventWindowPostReaction.btc_return_30m) }}</b><small>absorption / follow-through window</small></span>
                    <em class="pill" :class="eventWindowPostReaction.btc_absorbed_shock ? 'bull' : 'mixed'">absorbed {{ text(eventWindowPostReaction.btc_absorbed_shock, '-') }}</em>
                  </div>
                  <div class="event-reaction-row">
                    <strong>2h</strong>
                    <span><b>{{ marketReturnPct(eventWindowPostReaction.btc_return_2h) }}</b><small>event lock release guard</small></span>
                    <em class="pill" :class="marketReturnTone(eventWindowPostReaction.btc_return_2h)">{{ text(eventWindowPostReaction.followthrough, 'pending') }}</em>
                  </div>
                  <div class="event-reaction-row">
                    <strong>flow</strong>
                    <span><b>OI {{ text(eventWindowPostReaction.oi_change, '-') }}</b><small>funding {{ text(eventWindowPostReaction.funding_rate, '-') }} · vol {{ text(eventWindowPostReaction.realized_volatility, '-') }}</small></span>
                    <em class="pill">cvd {{ text(eventWindowPostReaction.cvd_proxy, '-') }}</em>
                  </div>
                  <div class="event-reaction-row">
                    <strong>ofi</strong>
                    <span><b>{{ text(eventWindowPostReaction.ofi_proxy, '-') }}</b><small>{{ text(eventWindowPostReaction.event_lock_release_reason, 'post_event_reaction_pending') }}</small></span>
                    <em class="pill">basis {{ text(eventWindowPostReaction.basis, '-') }}</em>
                  </div>
                </div>
              </article>

              <article class="event-panel-card">
                <header>
                  <h3>Calendar Mini</h3>
                  <span class="pill">{{ eventCalendarMiniMonthLabel }}</span>
                </header>
                <div class="event-calendar-mini event-calendar-mini-month">
                  <span
                    v-for="weekday in eventCalendarMiniWeekdays"
                    :key="weekday"
                    class="event-mini-weekday"
                  >
                    {{ weekday }}
                  </span>
                  <span
                    v-for="day in eventCalendarMiniDays"
                    :key="day.key"
                    class="event-mini-day"
                    :class="[day.tone, { blank: day.isBlank, active: day.isActive, empty: !day.events.length }]"
                  >
                    <b>{{ day.day ?? '' }}</b>
                    <small>{{ day.labels.length ? day.labels.join('/') : '-' }}</small>
                  </span>
                  <span v-if="!eventWindowCalendar.length" class="event-empty-state">No events</span>
                </div>
              </article>

              <article class="event-panel-card event-summary-widget-large" :class="alertTone(eventWindowState.emergency_level)">
                <header>
                  <h3>Dashboard Summary Widget</h3>
                  <span class="pill" :class="alertTone(eventWindowState.emergency_level)">{{ text(eventWindowState.emergency_level, 'none') }}</span>
                </header>
                <p class="event-large-copy">{{ text(eventWindowSummarySubtitle, 'Compact summary for existing 预警 / 事件窗口 area.') }}</p>
                <div class="event-chip-row">
                  <span class="event-chip mixed">{{ text(eventWindowActive.event_type, 'event') }} {{ daysText(Number(eventWindowActive.time_to_event_sec ?? 0) / 86400) }}</span>
                  <span class="event-chip blue">{{ text(eventWindowOverlay.trade_permission_modifier, 'none') }}</span>
                  <span class="event-chip">{{ text(eventWindowOverlay.ordinary_radar_trust, 'normal') }}</span>
                  <span class="event-chip" :class="sourceModeTone(eventWindowSourceMode)">{{ eventWindowSourceMode }}</span>
                </div>
                <p class="event-source-note">
                  Sources live {{ eventWindowSourceCounts.live }} · partial {{ eventWindowSourceCounts.partial }} ·
                  fallback {{ eventWindowSourceCounts.fallback }} · failed {{ eventWindowSourceCounts.failed }}
                  <template v-if="eventWindowDisabledCapabilities.length">
                    · disabled {{ eventWindowDisabledCapabilities.slice(0, 3).join(', ') }}
                  </template>
                  <template v-if="eventWindowCalendarFallbackNotice">
                    · {{ eventWindowCalendarFallbackNotice }}
                  </template>
                </p>
                <button class="event-action-button bull" disabled>Open Watchtower</button>
              </article>
            </aside>
          </section>

          <section v-if="eventWatchtowerTab === 'audit'" class="event-audit-grid">
            <article class="event-panel-card event-audit-card">
              <header>
                <h3>Source Chain Audit</h3>
                <span class="pill" :class="sourceModeTone(eventWindowSourceMode)">{{ eventWindowSourceMode }}</span>
              </header>
              <div class="event-audit-actions">
                <button class="event-action-button" @click="openReport(eventWindowAuditReportLinks[0])">Open HTML 1</button>
                <span class="event-chip" :class="eventAuditStatusTone(eventWindowAuditBundle.overall_status)">
                  bundle {{ text(eventWindowAuditBundle.overall_status, 'pending') }}
                </span>
                <span class="event-chip">snapshot {{ text(eventWindowAuditBundle.snapshot_id ?? eventWatchtowerPayload.snapshot_id, '-') }}</span>
              </div>
              <div class="source-quality-strip">
                <span><small>overall mode</small><strong>{{ eventWindowSourceMode }}</strong></span>
                <span><small>live</small><strong>{{ eventWindowSourceCounts.live }}</strong></span>
                <span><small>partial</small><strong>{{ eventWindowSourceCounts.partial }}</strong></span>
                <span><small>fallback</small><strong>{{ eventWindowSourceCounts.fallback }}</strong></span>
                <span><small>failed</small><strong>{{ eventWindowSourceCounts.failed }}</strong></span>
                <span><small>disabled</small><strong>{{ eventWindowDisabledCapabilities.length }}</strong></span>
              </div>
              <div class="provider-mesh-grid">
                <span><small>calendar quality</small><strong>{{ text(eventWindowSourceQuality.calendar_quality, '-') }}</strong></span>
                <span><small>actual quality</small><strong>{{ text(eventWindowSourceQuality.actual_quality, '-') }}</strong></span>
                <span><small>nowcast quality</small><strong>{{ text(eventWindowSourceQuality.nowcast_quality, '-') }}</strong></span>
                <span><small>consensus quality</small><strong>{{ text(eventWindowSourceQuality.consensus_quality, '-') }}</strong></span>
                <span><small>fedwatch quality</small><strong>{{ text(eventWindowSourceQuality.fedwatch_quality, '-') }}</strong></span>
                <span><small>speech quality</small><strong>{{ text(eventWindowSourceQuality.speech_quality, '-') }}</strong></span>
                <span><small>calendar confidence</small><strong>{{ text(eventWindowProviderConfidence.calendar_confidence, '-') }}</strong></span>
                <span><small>consensus confidence</small><strong>{{ text(eventWindowProviderConfidence.consensus_confidence, '-') }}</strong></span>
                <span><small>nowcast confidence</small><strong>{{ text(eventWindowProviderConfidence.nowcast_confidence, '-') }}</strong></span>
                <span><small>actual confidence</small><strong>{{ text(eventWindowProviderConfidence.actual_confidence, '-') }}</strong></span>
                <span><small>rate odds confidence</small><strong>{{ text(eventWindowProviderConfidence.rate_probability_confidence, '-') }}</strong></span>
                <span><small>prediction confidence</small><strong>{{ text(eventWindowProviderConfidence.prediction_market_confidence, '-') }}</strong></span>
              </div>
              <div class="provider-tier-row">
                <span>official {{ text(eventWindowProviderTierCounts.official, '0') }}</span>
                <span>official_mirror {{ text(eventWindowProviderTierCounts.official_mirror, '0') }}</span>
                <span>secondary_consensus {{ text(eventWindowProviderTierCounts.secondary_consensus, '0') }}</span>
                <span>secondary_calendar {{ text(eventWindowProviderTierCounts.secondary_calendar, '0') }}</span>
                <span>prediction_market {{ text(eventWindowProviderTierCounts.prediction_market, '0') }}</span>
                <span>market_proxy {{ text(eventWindowProviderTierCounts.market_implied_proxy, '0') }}</span>
                <span>manual_override {{ text(eventWindowProviderTierCounts.manual_override, '0') }}</span>
                <span>failed {{ text(eventWindowProviderTierCounts.failed ?? eventWindowProviderTierCounts.missing, '0') }}</span>
              </div>
              <div class="watch-list compact">
                <div
                  v-for="fetch in eventWindowSourceFetches.slice(0, 6)"
                  :key="`audit-${text(fetch.fetch_id)}`"
                  class="watch-row"
                >
                  <strong>{{ text(fetch.source_id) }} · {{ text(fetch.status) }}</strong>
                  <small>{{ text(fetch.started_at ?? fetch.last_attempt_at) }} · {{ text(fetch.endpoint_url, '-') }}</small>
                  <span>{{ text(fetch.error_message || `${text(fetch.parsed_item_count, '0')} parsed`) }}</span>
                </div>
                <div v-if="!eventWindowSourceFetches.length" class="event-empty-state">No fetch lineage rows in current source diagnostics.</div>
              </div>
              <p class="event-source-note">
                Non-official sources are labelled by tier. Consensus missing disables surprise math; nowcast risk remains visible.
                FedWatch proxy is shown as proxy/prediction-market confidence, not CME FedWatch.
              </p>
            </article>

            <article class="event-panel-card event-audit-card">
              <header>
                <h3>State / Overlay / LLM Audit</h3>
                <span class="pill" :class="alertTone(eventWindowState.emergency_level)">{{ text(eventWindowState.emergency_level, 'none') }}</span>
              </header>
              <div class="event-audit-actions">
                <button class="event-action-button" @click="openReport(eventWindowAuditReportLinks[1])">Open HTML 2</button>
                <span class="event-chip">direct_score_impact={{ eventWindowDirectScoreImpact }}</span>
                <span class="event-chip" :class="eventWindowOverlayForbiddenKeys.length ? 'bear' : 'bull'">
                  forbidden_keys {{ eventWindowOverlayForbiddenKeys.length ? eventWindowOverlayForbiddenKeys.join(', ') : 'empty / pass' }}
                </span>
              </div>
              <div class="provider-mesh-grid">
                <span><small>event_window_state</small><strong>{{ text(eventWindowState.event_window_state, 'calendar_monitor') }}</strong></span>
                <span><small>state_priority</small><strong>{{ text(eventWindowState.state_priority, '-') }}</strong></span>
                <span><small>emergency_level</small><strong>{{ text(eventWindowState.emergency_level, 'none') }}</strong></span>
                <span><small>valid_until</small><strong>{{ text(eventWindowState.valid_until, '-') }}</strong></span>
                <span><small>trade permission</small><strong>{{ text(eventWindowOverlay.trade_permission_modifier, 'none') }}</strong></span>
                <span><small>confidence cap</small><strong>{{ text(eventWindowOverlay.confidence_cap, 'none') }}</strong></span>
                <span><small>volatility warning</small><strong>{{ text(eventWindowOverlay.volatility_warning, 'none') }}</strong></span>
                <span><small>ordinary radar trust</small><strong>{{ text(eventWindowOverlay.ordinary_radar_trust, 'normal') }}</strong></span>
              </div>
              <div class="event-chip-row">
                <span v-for="code in eventWindowReasonCodes" :key="`audit-${code}`" class="event-chip mixed">{{ code }}</span>
                <span v-if="!eventWindowReasonCodes.length" class="event-chip">reason_codes none</span>
              </div>
              <div class="event-llm-detail-head">
                <span><small>provider</small><strong>{{ text(selectedEventLlmAnalysis.provider, 'deepseek') }}</strong></span>
                <span><small>status</small><strong>{{ text(selectedEventLlmAnalysis.status, 'pending') }}</strong></span>
                <span><small>tone</small><strong>{{ text(selectedEventLlmAnalysis.tone, 'pending') }}</strong></span>
                <span><small>tone confidence</small><strong>{{ eventLlmConfidence(selectedEventLlmAnalysis) }}</strong></span>
                <span><small>policy relevance</small><strong>{{ text(selectedEventLlmAnalysis.policy_relevance, 'unknown') }}</strong></span>
                <span><small>speaker</small><strong>{{ text(selectedEventLlmAnalysis.speaker ?? eventWindowSpeechMonitor.speaker, '-') }}</strong></span>
                <span><small>speaker weight</small><strong>{{ text(selectedEventLlmAnalysis.speaker_weight, '-') }}</strong></span>
                <span :class="eventLlmBoundaryPass(selectedEventLlmAnalysis) ? 'bull' : 'bear'">
                  <small>boundary passed</small><strong>{{ eventLlmBoundaryPass(selectedEventLlmAnalysis) }}</strong>
                </span>
              </div>
              <p class="event-large-copy">{{ eventLlmSummary(selectedEventLlmAnalysis) }}</p>
              <p class="event-source-note">
                LLM only classifies tone, relevance, and confidence. It does not output BTC bullish/bearish, modify emergency_level,
                or modify trade permission. Violations: {{ eventWindowLlmViolations.length ? eventWindowLlmViolations.join(', ') : 'none' }}.
              </p>
            </article>

            <article class="event-panel-card event-audit-card">
              <header>
                <h3>Shock Fast Lane Audit</h3>
                <span class="pill" :class="eventWindowShockLane.shock_detected ? alertTone(eventWindowState.emergency_level) : 'quality'">
                  {{ text(eventWindowShockLane.shock_detected, 'false') }}
                </span>
              </header>
              <div class="event-audit-actions">
                <button class="event-action-button" @click="openReport(eventWindowAuditReportLinks[2])">Open HTML 3</button>
                <span class="event-chip" :class="eventAuditStatusTone(eventWindowAuditRegression.overall_status)">
                  regression {{ text(eventWindowAuditRegression.overall_status, 'pending') }}
                </span>
                <span class="event-chip">direct_score_impact={{ eventWindowDirectScoreImpact }}</span>
              </div>
              <div class="provider-mesh-grid">
                <span><small>shock_detected</small><strong>{{ text(eventWindowShockLane.shock_detected, 'false') }}</strong></span>
                <span><small>shock_type</small><strong>{{ text(eventWindowShockLane.shock_type, 'none') }}</strong></span>
                <span><small>confirmation</small><strong>{{ text(eventWindowShockLane.confirmation_level, 'none') }}</strong></span>
                <span><small>source_count</small><strong>{{ text(eventWindowShockLane.source_count, '0') }}</strong></span>
                <span><small>market dislocation</small><strong>{{ text(eventWindowShockLane.market_dislocation, 'false') }}</strong></span>
                <span><small>microstructure</small><strong>{{ text(eventWindowShockLane.btc_microstructure_confirmation, 'false') }}</strong></span>
                <span><small>rumor risk</small><strong>{{ text(eventWindowShockLane.rumor_risk, 'false') }}</strong></span>
                <span><small>overlay</small><strong>{{ text(eventWindowOverlay.trade_permission_modifier, 'none') }}</strong></span>
              </div>
              <div class="event-boundary-grid">
                <span :class="eventWindowDirectScoreImpact === 'false' ? 'bull' : 'bear'">direct_score_impact_false</span>
                <span :class="eventWindowShockLane.rumor_risk && text(eventWindowState.emergency_level) === 'critical' ? 'bear' : 'bull'">rumor_not_critical</span>
                <span :class="text(eventWindowShockLane.confirmation_level, '').includes('official') ? 'bull' : 'mixed'">official_has_url_hash</span>
                <span :class="eventWindowShockEvidence.primary_window ? 'bull' : 'mixed'">market_has_evidence</span>
                <span :class="text(eventWindowAuditRegression.overall_status, 'pending') === 'PASS' ? 'bull' : 'mixed'">synthetic_regression</span>
              </div>
              <div class="event-shock-llm-card">
                <header>
                  <h4>LLM 中文冲击解释</h4>
                  <span class="pill" :class="eventAuditStatusTone(eventWindowShockLlmAnalysis.boundary_pass)">
                    boundary {{ text(eventWindowShockLlmAnalysis.boundary_pass, 'pending') }}
                  </span>
                </header>
                <p><strong>摘要：</strong>{{ text(eventWindowShockLlmAnalysis.summary_zh, '等待 Shock Fast Lane 生成中文观察。') }}</p>
                <p><strong>原因：</strong>{{ text(eventWindowShockLlmAnalysis.risk_reason_zh, '暂无结构化冲击原因。') }}</p>
                <p><strong>边界：</strong>{{ text(eventWindowShockLlmAnalysis.action_boundary_zh, '只解释事件窗口覆盖层，不改变 BTC score、radar score 或趋势方向。') }}</p>
              </div>
            </article>
          </section>

          <section v-if="eventWatchtowerTab === 'history'" class="alert-section">
            <div class="section-title-row">
              <h3>Source Quality Mesh</h3>
              <span class="pill" :class="sourceModeTone(eventWindowSourceQuality.overall_source_mode)">
                {{ text(eventWindowSourceQuality.overall_source_mode, 'partial_live') }}
              </span>
            </div>
            <p class="event-source-note">
              {{ text(eventWindowSourceQuality.confidence_note, 'partial_live is functional for monitoring; missing fields only disable their own calculations.') }}
            </p>
            <div class="event-chip-row">
              <span class="event-chip" :class="eventWindowSourceQuality.functional_live ? 'bull' : 'mixed'">
                functional_live {{ eventWindowSourceQuality.functional_live === false ? 'false' : 'true' }}
              </span>
              <span class="event-chip" :class="eventWindowSourceQuality.blocked ? 'bear' : 'bull'">
                blocked {{ eventWindowSourceQuality.blocked ? 'true' : 'false' }}
              </span>
            </div>
            <div class="source-quality-strip">
              <span><small>calendar</small><strong>{{ text(eventWindowSourceQuality.calendar_quality, '-') }}</strong></span>
              <span><small>actual</small><strong>{{ text(eventWindowSourceQuality.actual_quality, '-') }}</strong></span>
              <span><small>nowcast</small><strong>{{ text(eventWindowSourceQuality.nowcast_quality, '-') }}</strong></span>
              <span><small>consensus</small><strong>{{ text(eventWindowSourceQuality.consensus_quality, '-') }}</strong></span>
              <span><small>fedwatch</small><strong>{{ text(eventWindowSourceQuality.fedwatch_quality, '-') }}</strong></span>
              <span><small>speech</small><strong>{{ text(eventWindowSourceQuality.speech_quality, '-') }}</strong></span>
            </div>
            <p class="event-source-note">
              Disabled:
              <template v-if="eventWindowDisabledCapabilities.length">
                {{ eventWindowDisabledCapabilities.join(', ') }}
              </template>
              <template v-else>none</template>
            </p>
          </section>

          <section v-if="eventWatchtowerTab === 'history'" class="alert-section">
            <div class="section-title-row">
              <h3>Provider Mesh v3.2</h3>
              <span class="pill">{{ text(eventWindowProviderConfidence.lineage_mode, 'partial_live') }}</span>
            </div>
            <div class="provider-mesh-grid">
              <span><small>calendar</small><strong>{{ text(eventWindowProviderConfidence.calendar_confidence, '-') }}</strong></span>
              <span><small>consensus</small><strong>{{ text(eventWindowProviderConfidence.consensus_confidence, '-') }}</strong></span>
              <span><small>nowcast</small><strong>{{ text(eventWindowProviderConfidence.nowcast_confidence, '-') }}</strong></span>
              <span><small>actual</small><strong>{{ text(eventWindowProviderConfidence.actual_confidence, '-') }}</strong></span>
              <span><small>rate odds</small><strong>{{ text(eventWindowProviderConfidence.rate_probability_confidence, '-') }}</strong></span>
              <span><small>prediction</small><strong>{{ text(eventWindowProviderConfidence.prediction_market_confidence, '-') }}</strong></span>
            </div>
            <div class="provider-tier-row">
              <span>official {{ text(eventWindowProviderTierCounts.official, '0') }}</span>
              <span>mirror {{ text(eventWindowProviderTierCounts.official_mirror, '0') }}</span>
              <span>secondary {{ Number(eventWindowProviderTierCounts.secondary_consensus ?? 0) + Number(eventWindowProviderTierCounts.secondary_calendar ?? 0) }}</span>
              <span>prediction {{ text(eventWindowProviderTierCounts.prediction_market, '0') }}</span>
              <span>proxy {{ text(eventWindowProviderTierCounts.market_implied_proxy, '0') }}</span>
            </div>
            <p class="event-source-note">
              Secondary calendar {{ text(eventWindowSecondaryMesh.secondary_calendar_status, 'missing') }}
              · consensus {{ text(eventWindowSecondaryMesh.consensus_status, 'missing') }}
              · prediction {{ text(eventWindowPredictionOdds.status, 'missing') }}
              · markets {{ text(eventWindowPredictionOdds.market_count, '0') }}
            </p>
          </section>

          <section v-if="eventWatchtowerTab === 'history'" class="alert-section">
            <div class="section-title-row">
              <h3>Live Source Status</h3>
              <span class="pill">{{ eventWindowSources.length }} sources</span>
            </div>
            <div class="event-source-grid">
              <div
                v-for="source in eventWindowSources"
                :key="text(source.source_id)"
                class="event-source-item"
                :class="`source-mode-${text(source.source_mode, 'unknown')}`"
              >
                <div>
                  <strong>{{ text(source.source_id) }}</strong>
                  <small>{{ text(source.source_tier, 'tier') }} · {{ text(source.source_mode, 'unknown') }}</small>
                </div>
                <span>{{ text(source.parsed_item_count, '0') }} items</span>
                <p>{{ text(source.last_error || source.last_success_at || source.last_attempt_at, '-') }}</p>
              </div>
            </div>
          </section>

          <section v-if="eventWatchtowerTab === 'history'" class="alert-section">
            <div class="section-title-row">
              <h3>Scheduler State</h3>
              <span class="pill">{{ eventWindowPersistedScheduler.length }} groups</span>
            </div>
            <div class="event-source-grid">
              <div
                v-for="item in eventWindowPersistedScheduler"
                :key="text(item.source_group)"
                class="event-source-item"
              >
                <div>
                  <strong>{{ text(item.source_group) }}</strong>
                  <small>{{ text(item.phase, 'normal') }} · {{ text(item.interval_sec, '-') }}s</small>
                </div>
                <span>{{ text(item.last_status, 'pending') }}</span>
                <p>next {{ text(item.next_due_at, '-') }} · last {{ text(item.last_success_at, '-') }}</p>
              </div>
            </div>
          </section>

          <section v-if="eventWatchtowerTab === 'history'" class="alert-section">
            <div class="section-title-row">
              <h3>Fetch Lineage</h3>
              <span class="pill">{{ eventWindowSourceFetches.length }} attempts</span>
            </div>
            <div class="watch-list compact">
              <div
                v-for="fetch in eventWindowSourceFetches.slice(0, 16)"
                :key="text(fetch.fetch_id)"
                class="watch-row"
              >
                <strong>{{ text(fetch.source_id) }} · {{ text(fetch.status) }}</strong>
                <small>{{ text(fetch.started_at) }} · {{ text(fetch.endpoint_url) }}</small>
                <span>{{ text(fetch.error_message || `${text(fetch.parsed_item_count, '0')} parsed`) }}</span>
              </div>
            </div>
          </section>

          <section v-if="eventWatchtowerTab === 'speeches'" class="event-watch-grid">
            <article class="event-panel-card event-llm-table-card">
              <header>
                <h3>LLM Analysis Table</h3>
                <span class="pill quality">{{ eventWindowLlmAnalyses.length }} analyses</span>
              </header>
              <div class="event-llm-table">
                <button
                  v-for="item in eventWindowLlmAnalyses"
                  :key="text(item.analysis_id)"
                  class="event-llm-row"
                  :class="{ active: text(selectedEventLlmAnalysis.analysis_id) === text(item.analysis_id) }"
                  @click="selectedEventLlmAnalysisId = text(item.analysis_id)"
                >
                  <span>
                    <small>analysis_id</small>
                    <strong>{{ text(item.analysis_id).slice(0, 28) }}</strong>
                  </span>
                  <span>
                    <small>provider</small>
                    <strong>{{ text(item.provider, 'deepseek') }}</strong>
                  </span>
                  <span>
                    <small>status</small>
                    <strong>{{ text(item.status, 'success') }}</strong>
                  </span>
                  <span>
                    <small>tone</small>
                    <strong :class="eventLlmToneClass(item.tone)">{{ text(item.tone, 'pending') }}</strong>
                  </span>
                  <span>
                    <small>confidence</small>
                    <strong>{{ eventLlmConfidence(item) }}</strong>
                  </span>
                  <span>
                    <small>relevance</small>
                    <strong>{{ text(item.policy_relevance, 'unknown') }}</strong>
                  </span>
                  <span>
                    <small>boundary</small>
                    <strong>{{ eventLlmBoundaryPass(item) }}</strong>
                  </span>
                  <p>{{ eventLlmSummary(item) }}</p>
                </button>
                <div v-if="!eventWindowLlmAnalyses.length" class="event-empty-state">No LLM analyses in current Event Window snapshot.</div>
              </div>
            </article>

            <article class="event-panel-card event-llm-detail-card">
              <header>
                <h3>LLM 中文解释</h3>
                <span class="pill" :class="eventLlmToneClass(selectedEventLlmAnalysis.tone)">
                  {{ text(selectedEventLlmAnalysis.provider, 'deepseek') }} · {{ text(selectedEventLlmAnalysis.status, 'success') }}
                </span>
              </header>
              <div class="event-llm-detail-head">
                <span><small>tone</small><strong>{{ text(selectedEventLlmAnalysis.tone, 'pending') }}</strong></span>
                <span><small>confidence</small><strong>{{ eventLlmConfidence(selectedEventLlmAnalysis) }}</strong></span>
                <span><small>relevance</small><strong>{{ text(selectedEventLlmAnalysis.policy_relevance, 'unknown') }}</strong></span>
                <span :class="eventLlmBoundaryPass(selectedEventLlmAnalysis) ? 'bull' : 'bear'">
                  <small>boundary pass</small><strong>{{ eventLlmBoundaryPass(selectedEventLlmAnalysis) }}</strong>
                </span>
              </div>
              <p class="event-large-copy">{{ eventLlmSummary(selectedEventLlmAnalysis) }}</p>
              <div class="event-chip-row">
                <span class="event-chip">text {{ text(selectedEventLlmAnalysis.text_id, '-') }}</span>
                <span class="event-chip">analysis {{ text(selectedEventLlmAnalysis.analysis_id, '-').slice(0, 32) }}</span>
                <span class="event-chip mixed">direct_score_impact {{ eventWindowDirectScoreImpact }}</span>
              </div>
              <small class="event-source-note">
                Boundary: LLM 只做 Fed/官方文本语义、相关性和置信度解释；不能覆盖 actual、consensus、emergency overlay，也不能直接输出 BTC 多空。
              </small>
            </article>
          </section>

          <section v-if="eventWatchtowerTab === 'shock'" class="event-watch-grid">
            <div class="event-watch-card">
              <h3>Shock Fast Lane</h3>
              <strong>{{ text(eventWindowShockLane.shock_detected, 'false') }} · {{ text(eventWindowShockLane.shock_type, 'none') }}</strong>
              <p>
                confirmation {{ text(eventWindowShockLane.confirmation_level, 'none') }}
                · sources {{ text(eventWindowShockLane.source_count, '0') }}
              </p>
              <small>
                market {{ text(eventWindowShockLane.market_dislocation, 'false') }}
                · micro {{ text(eventWindowShockLane.btc_microstructure_confirmation, 'false') }}
                · rumor {{ text(eventWindowShockLane.rumor_risk, 'false') }}
              </small>
            </div>
            <div class="event-watch-card">
              <h3>Shock Boundary</h3>
              <strong>direct score impact {{ eventWindowDirectScoreImpact }}</strong>
              <p>Unscheduled shocks can raise emergency overlay and cap ordinary radar trust.</p>
              <small>They do not directly make BTC bullish or bearish.</small>
            </div>
          </section>

          <section v-if="eventWatchtowerTab === 'calendar'" class="alert-section">
            <div class="section-title-row">
              <h3>Upcoming Official Calendar</h3>
              <span class="pill">{{ eventWindowCalendar.length }} items</span>
            </div>
            <div class="event-grid page-grid">
              <div v-for="event in eventWindowCalendar" :key="text(event.event_id)" class="event-card">
                <span>{{ text(event.event_type) }} · {{ text(event.importance) }}</span>
                <strong>{{ text(event.title) }}</strong>
                <small>{{ text(event.release_time ?? event.release_time_utc) }}</small>
                <i>{{ text(event.source_tier, 'official') }} · {{ text(event.source_url, '-') }}</i>
              </div>
            </div>
          </section>

          <section v-if="eventWatchtowerTab === 'timeline'" class="alert-section">
            <div class="section-title-row">
              <h3>Timeline</h3>
              <span class="pill">{{ eventWindowTimeline.length }} rows</span>
            </div>
            <div class="watch-list">
              <div v-for="item in eventWindowTimeline.slice(0, 24)" :key="`${text(item.type)}-${text(item.ts)}-${text(item.title)}`" class="watch-row">
                <strong>{{ text(item.type) }} · {{ text(item.title) }}</strong>
                <small>{{ text(item.level) }} · {{ text(item.ts) }}</small>
                <span>{{ text((item.payload as Row | undefined)?.summary ?? (item.payload as Row | undefined)?.reason_code, '-') }}</span>
              </div>
            </div>
          </section>
        </article>

        <article v-else-if="activePage === 'alerts'" class="panel alerts-page">
          <div class="panel-head">
            <div>
              <h2>Alerts Workbench</h2>
              <p>P3 alerts + event windows · P4.5 invalidation / confirmation context</p>
            </div>
            <span class="pill mixed">{{ text(state.alerts?.schema_version, 'p3.alerts.v1') }}</span>
          </div>

          <section class="alert-hero">
            <div class="alert-hero-main">
              <span class="pill" :class="alertTone(topAlert?.level)">{{ text(topAlert?.level, 'watch') }}</span>
              <h3>{{ text(topAlert?.title, 'No high-priority alert in this run') }}</h3>
              <p>{{ alertSummaryText }}</p>
              <small>{{ cooldownText(topAlert?.cooldown_until) }} · {{ alertUpdatedText(topAlert?.updated_at) }}</small>
            </div>
            <div class="alert-stat-grid">
              <span><small>alerts</small><strong>{{ alertStats.total }}</strong></span>
              <span><small>critical</small><strong>{{ alertStats.critical }}</strong></span>
              <span><small>warning</small><strong>{{ alertStats.warning }}</strong></span>
              <span><small>cooling</small><strong>{{ alertStats.cooling }}</strong></span>
              <span><small>evidence</small><strong>{{ alertStats.evidence }}</strong></span>
              <span><small>final view</small><strong>{{ finalViewText }}</strong></span>
            </div>
          </section>

          <section class="lineage-grid compact">
            <span><small>collect</small><code>{{ text(alertRunLineage.collect_run_id) }}</code></span>
            <span><small>p2 radar</small><code>{{ text(alertRunLineage.p2_radar_run_id) }}</code></span>
            <span><small>p3</small><code>{{ text(alertRunLineage.p3_run_id) }}</code></span>
            <span><small>final</small><code>{{ text(alertRunLineage.final_run_id) }}</code></span>
          </section>

          <section class="alert-section">
            <div class="section-title-row">
              <h3>活跃预警</h3>
              <span class="pill">{{ alerts.length }} active / history rows</span>
            </div>
            <p v-if="!alerts.length" class="empty-note">本轮没有高优先级预警，继续观察反证和确认条件。</p>
            <div class="alert-list-grid">
            <button
              v-for="alert in alerts"
              :key="text(alert.alert_id)"
              class="alert-card"
              :class="alertTone(alert.level)"
              @click="openAlertEvidence(alert)"
            >
              <span>{{ text(alert.level) }} · {{ text(alert.state) }}</span>
              <strong>{{ text(alert.title) }}</strong>
              <small>{{ text(alert.summary) }}</small>
              <em>{{ cooldownText(alert.cooldown_until) }} · evidence {{ text(alert.evidence_count, '0') }} · {{ alertUpdatedText(alert.updated_at) }}</em>
              <i>{{ text(alert.alert_id) }} · {{ text(alert.run_id) }}</i>
              <b class="alert-actions">
                <span @click.stop="openAlertEvidence(alert)">Evidence</span>
                <span @click.stop="activePage = 'invalidation'">Invalidation</span>
                <span @click.stop="openAlertRunLogs(alert)">Run Logs</span>
              </b>
            </button>
            </div>
          </section>
          <section class="alert-section">
            <div class="section-title-row">
              <h3>反证 / 确认条件</h3>
              <span class="pill">{{ invalidationRules.length }} / {{ confirmationRules.length }}</span>
            </div>
            <div class="watch-list">
              <button v-for="rule in invalidationRules" :key="text(rule.rule_id)" class="watch-row" @click="activePage = 'invalidation'">
                <strong>反证 · {{ text(rule.title ?? rule.rule_id) }}</strong>
                <small>{{ text(rule.horizon) }} · {{ ruleAction(rule) }}</small>
                <span>{{ text(rule.reason) }}</span>
                <code>{{ ruleConditions(rule) }}</code>
              </button>
              <button v-for="rule in confirmationRules" :key="text(rule.rule_id)" class="watch-row" @click="activePage = 'invalidation'">
                <strong>确认 · {{ text(rule.title ?? rule.rule_id) }}</strong>
                <small>{{ text(rule.horizon) }} · {{ ruleAction(rule) }}</small>
                <span>{{ text(rule.reason) }}</span>
                <code>{{ ruleConditions(rule) }}</code>
              </button>
            </div>
          </section>
          <section class="alert-section">
            <div class="section-title-row">
              <h3>事件窗口</h3>
              <span class="pill">{{ eventWindowRows.length }} watched events</span>
            </div>
            <div class="event-grid page-grid">
              <button
                v-for="event in eventWindowRows"
                :key="text(event.row.feature_id ?? event.payload.event_type)"
                class="event-card"
                :class="directionClass(eventWindow(event.row))"
              >
                <span>{{ eventType(event.row) }} · {{ daysText(event.daysUntil) }}</span>
                <strong>{{ eventName(event.row) }}</strong>
                <small>{{ text(event.payload.event_datetime) }}</small>
                <small>{{ eventWindow(event.row) }} · {{ eventAction(event.row) }} · {{ text(event.payload.event_phase) }}</small>
                <em>{{ eventDailyWatch(event.row) }}</em>
                <i>{{ eventSourceStatus(event.row) }}</i>
              </button>
            </div>
          </section>
          <section class="alert-section">
            <div class="section-title-row">
              <h3>操作入口</h3>
              <span class="pill">same run context</span>
            </div>
            <div class="alert-action-grid">
              <button @click="navigateTo('evidence')">
                <strong>Evidence</strong>
                <small>查看触发预警的指标证据、评分和 freshness。</small>
              </button>
              <button @click="activePage = 'invalidation'">
                <strong>Invalidation / Confirmation</strong>
                <small>查看上修、降级和偏空确认条件。</small>
              </button>
              <button @click="activePage = 'logs'">
                <strong>Run Logs</strong>
                <small>追溯 P1/P2/P3/P4.5 本轮产物和审计 HTML。</small>
              </button>
              <div class="halving-strip wide">
                <span>halving estimated days</span>
                <strong>{{ daysText(halvingStats.days) }}</strong>
                <small>block height {{ compactNumber(halvingStats.height) }} · remaining blocks {{ compactNumber(halvingStats.blocks) }}</small>
              </div>
            </div>
          </section>
        </article>

        <article v-else-if="activePage === 'invalidation'" class="panel">
          <div class="panel-head">
            <div>
              <h2>Invalidation / Confirmation Workbench</h2>
              <p>BTC thesis validation · response gates · evidence matrix</p>
            </div>
            <span class="pill">{{ text(state.invalidation?.schema_version, 'p45.invalidation.v1') }}</span>
          </div>

          <section class="invalidation-hero">
            <div class="alert-hero-main">
              <span class="pill" :class="statusClass(invalidationWorkbench.validation_state)">{{ text(invalidationWorkbench.validation_state, 'watching') }}</span>
              <h3 v-if="hasInvalidationWorkbench">{{ text(invalidationWorkbench.validation_reason, '等待 BTC response / residual 裁决') }}</h3>
              <h3 v-else>{{ text(decision.conclusion_sentence, '等待 P4.5 final decision') }}</h3>
              <p v-if="hasInvalidationWorkbench">
                thesis {{ text(workbenchCurrentThesis.headline_state, 'neutral') }} · direction {{ text(workbenchCurrentThesis.btc_direction, 'neutral') }} · confidence {{ text(workbenchCurrentThesis.confidence_score, '0') }}
              </p>
              <p v-else>{{ text(decision.trade_permission, 'watch_only') }} · confidence {{ text(decision.confidence ?? aggregation.confidence) }} · {{ text(decision.risk_mode, 'risk mode pending') }}</p>
              <small>Workbench v2 只在 BTC response 与 residual gate 通过后触发确认或反证。</small>
            </div>
            <div class="alert-stat-grid">
              <span><small>confirmation</small><strong>{{ text(workbenchScores.confirmation_score, String(invalidationStats.confirmation)) }}</strong></span>
              <span><small>invalidation</small><strong>{{ text(workbenchScores.invalidation_score, String(invalidationStats.invalidation)) }}</strong></span>
              <span><small>conflict</small><strong>{{ text(workbenchScores.conflict_score, '0') }}</strong></span>
              <span><small>acceptance</small><strong>{{ text(workbenchScores.trend_acceptance_score, '0') }}</strong></span>
              <span><small>response</small><strong>{{ text(workbenchScores.btc_response_score, '0') }}</strong></span>
              <span><small>permission</small><strong>{{ text(workbenchCurrentThesis.trade_permission, tradePermissionText) }}</strong></span>
            </div>
          </section>

          <section class="lineage-grid compact">
            <span><small>collect</small><code>{{ text(invalidationRunLineage.collect_run_id) }}</code></span>
            <span><small>p2 radar</small><code>{{ text(invalidationRunLineage.p2_radar_run_id) }}</code></span>
            <span><small>p3</small><code>{{ text(invalidationRunLineage.p3_run_id) }}</code></span>
            <span><small>final</small><code>{{ text(invalidationRunLineage.final_run_id) }}</code></span>
          </section>

          <template v-if="hasInvalidationWorkbench">
            <section class="workbench-grid">
              <article class="workbench-card">
                <div class="section-title-row">
                  <h3>Current Thesis</h3>
                  <span class="pill" :class="directionClass(workbenchCurrentThesis.btc_direction)">{{ text(workbenchCurrentThesis.headline_state, 'neutral') }}</span>
                </div>
                <div class="detail-kv-grid">
                  <span><small>direction</small><strong>{{ text(workbenchCurrentThesis.btc_direction, 'neutral') }}</strong></span>
                  <span><small>quality</small><strong>{{ text(workbenchCurrentThesis.trend_quality, 'mixed') }}</strong></span>
                  <span><small>permission</small><strong>{{ text(workbenchCurrentThesis.trade_permission, 'watch_only') }}</strong></span>
                  <span><small>confidence</small><strong>{{ text(workbenchCurrentThesis.confidence_score, '0') }}</strong></span>
                </div>
              </article>

              <article class="workbench-card">
                <div class="section-title-row">
                  <h3>BTC Response Gate</h3>
                  <span class="pill" :class="directionClass(workbenchPriceAcceptance.direction)">{{ text(workbenchPriceAcceptance.direction, 'neutral') }}</span>
                </div>
                <div class="detail-kv-grid">
                  <span><small>price score</small><strong>{{ text(workbenchPriceAcceptance.score, 'missing') }}</strong></span>
                  <span><small>residual</small><strong>{{ text(workbenchResidual.direction, 'flat') }}</strong></span>
                  <span><small>residual z</small><strong>{{ text(workbenchResidual.zscore, 'missing') }}</strong></span>
                  <span><small>micro</small><strong>{{ text(workbenchMicroResponse.liquidity_survival, 'unknown') }}</strong></span>
                </div>
                <p>没有 BTC response / residual 时，规则只能 armed 或 blocked，不能 triggered。</p>
              </article>

              <article class="workbench-card">
                <div class="section-title-row">
                  <h3>Triggered / Armed</h3>
                  <span class="pill">{{ workbenchTriggeredRules.length }} / {{ workbenchArmedRules.length }}</span>
                </div>
                <div class="detail-kv-grid">
                  <span><small>triggered</small><strong>{{ workbenchTriggeredRules.length }}</strong></span>
                  <span><small>armed</small><strong>{{ workbenchArmedRules.length }}</strong></span>
                  <span><small>blocked</small><strong>{{ workbenchBlockedRules.length }}</strong></span>
                  <span><small>matrix</small><strong>{{ workbenchEvidenceMatrix.length }}</strong></span>
                </div>
              </article>
            </section>

            <section class="invalidation-grid">
              <div class="rule-column">
                <div class="section-title-row">
                  <h3>Confirmation Lane</h3>
                  <span class="pill bull">{{ workbenchConfirmationLane.length }} rules</span>
                </div>
                <article v-for="rule in workbenchConfirmationLane" :key="text(rule.rule_id)" class="rule-card confirm" :class="statusClass(rule.status)">
                  <div class="rule-card-head">
                    <span class="pill" :class="statusClass(rule.status)">{{ text(rule.status, 'arming') }}</span>
                    <strong>{{ text(rule.rule_id, 'confirmation_rule') }}</strong>
                    <small>{{ text(rule.progress, '0') }}% · {{ text(rule.target_view, 'watch') }}</small>
                  </div>
                  <p>{{ text(rule.reason, '等待确认解释') }}</p>
                  <code>{{ asList(rule.current_observations).map((item) => text(item)).join(' · ') || 'waiting observations' }}</code>
                  <div class="metric-chip-grid">
                    <span v-for="moduleId in asList(rule.observed_modules).slice(0, 8)" :key="text(moduleId)" class="metric-chip">
                      <strong>{{ text(moduleId) }}</strong>
                      <small>observed module</small>
                    </span>
                  </div>
                </article>
              </div>

              <div class="rule-column">
                <div class="section-title-row">
                  <h3>Invalidation Lane</h3>
                  <span class="pill bear">{{ workbenchInvalidationLane.length }} rules</span>
                </div>
                <article v-for="rule in workbenchInvalidationLane" :key="text(rule.rule_id)" class="rule-card" :class="statusClass(rule.status)">
                  <div class="rule-card-head">
                    <span class="pill" :class="statusClass(rule.status)">{{ text(rule.status, 'arming') }}</span>
                    <strong>{{ text(rule.rule_id, 'invalidation_rule') }}</strong>
                    <small>{{ text(rule.progress, '0') }}% · {{ text(rule.target_view, 'watch') }}</small>
                  </div>
                  <p>{{ text(rule.reason, '等待反证解释') }}</p>
                  <code>{{ asList(rule.missing_evidence).map((item) => text(item)).join(' · ') || 'gates available' }}</code>
                  <div class="metric-chip-grid">
                    <span v-for="moduleId in asList(rule.observed_modules).slice(0, 8)" :key="text(moduleId)" class="metric-chip">
                      <strong>{{ text(moduleId) }}</strong>
                      <small>observed module</small>
                    </span>
                  </div>
                </article>
              </div>
            </section>

            <section class="quality-grid">
              <article class="quality-card wide">
                <div class="section-title-row">
                  <h3>Evidence Matrix</h3>
                  <span class="pill">{{ workbenchEvidenceMatrix.length }} modules</span>
                </div>
                <div class="workbench-matrix">
                  <button
                    v-for="item in workbenchEvidenceMatrix"
                    :key="text(item.module_id)"
                    class="matrix-row"
                    :class="statusClass(item.evidence_state)"
                    @click="selectedModuleId = text(item.module_id)"
                  >
                    <strong>{{ text(item.module_id) }}</strong>
                    <span>{{ text(item.layer) }}</span>
                    <span>{{ text(item.evidence_state) }}</span>
                    <span>{{ text(item.evidence_weight_status, 'weight pending') }}</span>
                    <small>{{ text(item.btc_implication, 'no implication') }}</small>
                    <small>{{ item.trigger_eligible ? 'trigger eligible' : 'context / gated' }}</small>
                  </button>
                </div>
              </article>

              <article class="quality-card">
                <div class="section-title-row">
                  <h3>Trigger Timeline</h3>
                  <span class="pill">{{ workbenchTimeline.length }} events</span>
                </div>
                <button v-for="item in workbenchTimeline" :key="text(item.rule_id)" class="watch-row quality-row">
                  <strong>{{ text(item.rule_id) }}</strong>
                  <small>{{ text(item.status) }} · {{ text(item.rule_type) }} · {{ text(item.progress) }}%</small>
                </button>
              </article>
            </section>
          </template>

          <section v-else class="invalidation-grid">
            <div class="rule-column">
              <div class="section-title-row">
                <h3>反证规则</h3>
                <span class="pill">{{ invalidationRules.length }} rules</span>
              </div>
              <article v-for="rule in invalidationRules" :key="text(rule.rule_id)" class="rule-card">
                <div class="rule-card-head">
                  <span class="pill mixed">{{ text(rule.horizon, 'horizon') }}</span>
                  <strong>{{ text(rule.title ?? rule.rule_id) }}</strong>
                  <small>{{ ruleProgress(rule) }} · {{ ruleAction(rule) }}</small>
                </div>
                <p>{{ text(rule.reason, '等待反证解释') }}</p>
                <code>{{ ruleConditions(rule) }}</code>
                <div class="metric-chip-grid">
                  <button
                    v-for="metricId in ruleMetricIds(rule)"
                    :key="metricId"
                    class="metric-chip"
                    :class="directionClass(metricEvidence(metricId)?.direction)"
                    @click="openMetricEvidence(metricId)"
                  >
                    <strong>{{ metricId }}</strong>
                    <small v-if="metricEvidence(metricId)">
                      value {{ text(metricEvidence(metricId)?.value ?? metricEvidence(metricId)?.current_value) }} · score {{ text(metricEvidence(metricId)?.metric_score) }}
                    </small>
                    <small v-else>waiting evidence</small>
                  </button>
                </div>
              </article>
            </div>

            <div class="rule-column">
              <div class="section-title-row">
                <h3>确认规则</h3>
                <span class="pill">{{ confirmationRules.length }} rules</span>
              </div>
              <article v-for="rule in confirmationRules" :key="text(rule.rule_id)" class="rule-card confirm">
                <div class="rule-card-head">
                  <span class="pill bear">{{ text(rule.horizon, 'horizon') }}</span>
                  <strong>{{ text(rule.title ?? rule.rule_id) }}</strong>
                  <small>{{ ruleProgress(rule) }} · {{ ruleAction(rule) }}</small>
                </div>
                <p>{{ text(rule.reason, '等待确认解释') }}</p>
                <code>{{ ruleConditions(rule) }}</code>
                <div class="metric-chip-grid">
                  <button
                    v-for="metricId in ruleMetricIds(rule)"
                    :key="metricId"
                    class="metric-chip"
                    :class="directionClass(metricEvidence(metricId)?.direction)"
                    @click="openMetricEvidence(metricId)"
                  >
                    <strong>{{ metricId }}</strong>
                    <small v-if="metricEvidence(metricId)">
                      value {{ text(metricEvidence(metricId)?.value ?? metricEvidence(metricId)?.current_value) }} · score {{ text(metricEvidence(metricId)?.metric_score) }}
                    </small>
                    <small v-else>waiting evidence</small>
                  </button>
                </div>
              </article>
            </div>
          </section>

          <section class="alert-action-grid">
            <button @click="navigateTo('evidence')">
              <strong>Evidence</strong>
              <small>按规则 metric 查看当前值、分数、质量和数据源。</small>
            </button>
            <button @click="activePage = 'alerts'">
              <strong>Alerts</strong>
              <small>查看这些规则关联的预警和 cooldown 状态。</small>
            </button>
            <button @click="activePage = 'logs'">
              <strong>Run Logs</strong>
              <small>追溯本轮 P1/P2/P3/P4.5 审计产物。</small>
            </button>
            <button @click="activePage = 'overview'">
              <strong>Overview</strong>
              <small>回到 BTC 决策卡、周期视图和聚合审计。</small>
            </button>
          </section>
        </article>

        <article v-else-if="activePage === 'quality'" class="panel">
          <div class="panel-head">
            <div>
              <h2>Data Quality Console</h2>
              <p>P1/P2/P3/P4.5 quality boundary · freshness · source health</p>
            </div>
            <span class="pill quality">{{ text(state.dataQuality?.schema_version, 'p45.data_quality.v1') }}</span>
          </div>

          <section class="quality-hero">
            <div class="alert-hero-main">
              <span class="pill" :class="statusClass(qualityContract.status)">{{ text(qualityContract.status, 'unknown') }}</span>
              <h3>平均指标质量 {{ qualityScoreText }}</h3>
              <p>{{ qualityBoundaryText }}</p>
              <small>contract {{ text(qualityContract.status) }} · freshness {{ text(qualityFreshnessCheck.status, 'pending') }}</small>
            </div>
            <div class="alert-stat-grid">
              <span><small>metrics</small><strong>{{ text(qualityPayload.metric_count ?? dataQuality.metric_count) }}</strong></span>
              <span><small>modules</small><strong>{{ text(qualityPayload.module_count ?? dataQuality.module_count ?? state.dashboard?.radar_module_count) }}</strong></span>
              <span><small>P1 collected</small><strong>{{ text(metricCountAudit.collected_metric_count) }}</strong></span>
              <span><small>P4.5 evidence</small><strong>{{ text(metricCountAudit.scored_evidence_count) }}</strong></span>
              <span><small>unavailable</small><strong>{{ text(qualityPayload.unavailable_metric_count ?? evidenceStats.unavailable) }}</strong></span>
              <span><small>missing freshness</small><strong>{{ text(qualityPayload.missing_freshness_count) }}</strong></span>
              <span><small>fallback</small><strong>{{ evidenceStats.fallback }}</strong></span>
              <span><small>stale</small><strong>{{ evidenceStats.stale }}</strong></span>
            </div>
          </section>

          <section class="lineage-grid compact">
            <span><small>collect</small><code>{{ text((state.dataQuality?.run_lineage as Row | undefined)?.collect_run_id) }}</code></span>
            <span><small>p2 radar</small><code>{{ text((state.dataQuality?.run_lineage as Row | undefined)?.p2_radar_run_id) }}</code></span>
            <span><small>p3</small><code>{{ text((state.dataQuality?.run_lineage as Row | undefined)?.p3_run_id) }}</code></span>
            <span><small>final</small><code>{{ text((state.dataQuality?.run_lineage as Row | undefined)?.final_run_id) }}</code></span>
          </section>

          <section class="quality-grid">
            <article class="quality-card">
              <div class="section-title-row">
                <h3>Contract Validation</h3>
                <span class="pill" :class="statusClass(qualityContract.status)">{{ text(qualityContract.status) }}</span>
              </div>
              <p>{{ text((qualityContract.view_consistency_check as Row | undefined)?.status, 'view consistency pending') }} · duplicate groups {{ text(qualityChecks.duplicate_groups_checked) }}</p>
              <div class="quality-check-grid">
                <span v-for="row in qualityCheckRows()" :key="row.key" :class="statusClass(row.value)">
                  <small>{{ row.key }}</small>
                  <strong>{{ text(row.value) }}</strong>
                </span>
              </div>
            </article>

            <article class="quality-card">
              <div class="section-title-row">
                <h3>Freshness Boundary</h3>
                <span class="pill quality">{{ text(qualityFreshnessCheck.status, 'warning') }}</span>
              </div>
              <p>{{ qualityBoundaryText }}</p>
              <div class="detail-kv-grid">
                <span><small>available missing</small><strong>{{ text(qualityFreshnessCheck.available_metric_missing_freshness_count, '0') }}</strong></span>
                <span><small>unavailable missing</small><strong>{{ text(qualityFreshnessCheck.unavailable_metric_missing_freshness_count, '0') }}</strong></span>
                <span><small>required available</small><strong>{{ text(qualityFreshnessCheck.required_for_available_metrics) }}</strong></span>
                <span><small>required unavailable</small><strong>{{ text(qualityFreshnessCheck.required_for_unavailable_metrics) }}</strong></span>
              </div>
              <button v-for="warning in qualityWarnings" :key="text(warning.code)" class="watch-row quality-row">
                <strong>{{ warningSummary(warning) }}</strong>
                <small>warning · non blocking when unavailable-only</small>
              </button>
            </article>
          </section>

          <section class="quality-grid">
            <article class="quality-card">
              <div class="section-title-row">
                <h3>Evidence Quality</h3>
                <span class="pill">{{ evidenceStats.total }} items</span>
              </div>
              <p>{{ metricCountAuditText }}</p>
              <div class="detail-kv-grid">
                <span><small>collected metrics</small><strong>{{ text(metricCountAudit.collected_metric_count) }}</strong></span>
                <span><small>scored evidence</small><strong>{{ text(metricCountAudit.scored_evidence_count) }}</strong></span>
                <span><small>derived metrics</small><strong>{{ text(metricCountAudit.derived_metric_count) }}</strong></span>
                <span><small>unavailable</small><strong>{{ text(metricCountAudit.unavailable_metric_count) }}</strong></span>
              </div>
              <div class="quality-bars">
                <span><small>positive</small><i class="bar bull"><b :style="{ width: `${Math.min(100, evidenceStats.positive)}%` }"></b></i><strong>{{ evidenceStats.positive }}</strong></span>
                <span><small>negative</small><i class="bar bear"><b :style="{ width: `${Math.min(100, evidenceStats.negative)}%` }"></b></i><strong>{{ evidenceStats.negative }}</strong></span>
                <span><small>zero</small><i class="bar mixed"><b :style="{ width: `${Math.min(100, evidenceStats.zero)}%` }"></b></i><strong>{{ evidenceStats.zero }}</strong></span>
                <span><small>fallback</small><i class="bar quality"><b :style="{ width: `${Math.min(100, evidenceStats.fallback)}%` }"></b></i><strong>{{ evidenceStats.fallback }}</strong></span>
              </div>
            </article>

            <article class="quality-card">
              <div class="section-title-row">
                <h3>Multi-source Boundary</h3>
                <span class="pill" :class="conflictStats.high ? 'bear' : conflictStats.total ? 'mixed' : 'bull'">{{ conflictStats.total }} conflicts</span>
              </div>
              <p>多源冲突单独展示为 source arbitration，不和采集失败、stale 或 unavailable 混在一起。</p>
              <div class="detail-kv-grid">
                <span><small>definition conflict</small><strong>{{ conflictStats.definition }}</strong></span>
                <span><small>fallback resolution</small><strong>{{ conflictStats.fallback }}</strong></span>
                <span><small>high risk</small><strong>{{ conflictStats.high }}</strong></span>
                <span><small>duplicate groups</small><strong>{{ duplicateGroups.length }}</strong></span>
              </div>
              <button class="watch-row quality-row" @click="navigateTo('conflict')">
                <strong>Open conflict arbitration</strong>
                <small>查看 primary source、candidate/fallback source、source_resolution 和 downstream evidence。</small>
              </button>
            </article>

            <article class="quality-card">
              <div class="section-title-row">
                <h3>Source Health</h3>
                <span class="pill">{{ text(sourceHealth.source_count) }} sources</span>
              </div>
              <p>{{ sourceHealthScopeText }}</p>
              <div class="detail-kv-grid">
                <span><small>current failures</small><strong>{{ text(sourceHealth.current_run_failed_count, '0') }}</strong></span>
                <span><small>current warnings</small><strong>{{ text(sourceHealth.current_run_warning_count, '0') }}</strong></span>
                <span><small>history failures</small><strong>{{ text(sourceHealth.history_recent_failed_count, '0') }}</strong></span>
                <span><small>scope</small><strong>{{ text(sourceHealth.recent_failed_scope, 'split') }}</strong></span>
              </div>
              <div class="source-status-row">
                <span v-for="[status, count] in Object.entries(sourceStatusCounts)" :key="status" class="pill" :class="sourceStatusClass(status)">
                  {{ status }} {{ text(count) }}
                </span>
              </div>
              <div class="manual-source-list">
                <article v-for="row in semiAutoSources" :key="sourceId(row)" class="manual-source-card" :class="sourceStatusClass(sourceAuthState(row))">
                  <div>
                    <strong>{{ sourceId(row) }}</strong>
                    <small>automation {{ sourceAutomationMode(row) }} · reauth {{ sourceAuthState(row) }} · verified {{ timestampText(sourceLastVerified(row)) }}</small>
                    <em>{{ sourceManualSummary(row) }}</em>
                  </div>
                  <button @click="openSourceDetail(sourceId(row))">Open Source</button>
                </article>
              </div>
              <div class="source-run-list">
                <button v-for="row in currentRunWarningRows" :key="`warning-${text(row.source_id)}-${text(row.run_id)}`" class="source-run-row quality" @click="openSourceDetail(String(row.source_id))">
                  <strong>{{ text(row.source_id) }}</strong>
                  <small>current warning · {{ text(row.status) }} · {{ text(row.mode) }} · {{ text(row.run_id) }}</small>
                  <em>{{ text(row.error_message, 'warning without blocking failure') }}</em>
                </button>
                <button v-for="row in historyFailedRows" :key="`history-${text(row.source_id)}-${text(row.run_id)}`" class="source-run-row" :class="sourceStatusClass(row.status)" @click="openSourceDetail(String(row.source_id))">
                  <strong>{{ text(row.source_id) }}</strong>
                  <small>history failure · {{ text(row.status) }} · {{ text(row.mode) }} · {{ text(row.run_id) }}</small>
                  <em>{{ text(row.error_message, 'historical failed run') }}</em>
                </button>
              </div>
            </article>
          </section>

          <section class="alert-action-grid">
            <button @click="navigateTo('evidence')">
              <strong>Evidence</strong>
              <small>查看所有 scored evidence 的质量、freshness、fallback。</small>
            </button>
            <button @click="activePage = 'source'">
              <strong>Source Detail</strong>
              <small>按 source_id 追溯数据源状态和来源。</small>
            </button>
            <button @click="activePage = 'logs'">
              <strong>Run Logs</strong>
              <small>查看 P1/P2/P3/P4.5 阶段产物与审计报告。</small>
            </button>
            <button @click="activePage = 'overview'">
              <strong>Overview</strong>
              <small>回到最终决策卡和聚合审计。</small>
            </button>
          </section>
        </article>

        <article v-else-if="activePage === 'source'" class="panel source-detail-page">
          <div class="panel-head">
            <div>
              <h2>Source Detail</h2>
              <p>P1/P8 source profile · freshness · fallback · downstream impact</p>
            </div>
            <span class="pill" :class="sourceStatusClass(selectedSourceProfile.status)">{{ text(selectedSourceProfile.status, 'select source') }}</span>
          </div>

          <section class="source-picker-grid">
            <button v-for="sourceId in sourceSummary" :key="sourceId" class="source-picker" :class="{ active: sourceId === selectedSourceId }" @click="openSourceDetail(sourceId)">
              <strong>{{ sourceId }}</strong>
              <small>from P4.5 evidence source_id</small>
            </button>
          </section>

          <section v-if="state.selectedSourceDetail" class="source-hero">
            <div>
              <span class="pill" :class="sourceStatusClass(selectedSourceProfile.status)">{{ text(selectedSourceProfile.status, 'unknown') }}</span>
              <h3>{{ text(selectedSourceProfile.source_id ?? selectedSourceId) }}</h3>
              <p>{{ text(selectedSourceProfile.name, 'source profile pending') }}</p>
              <small>{{ sourceMeaning(latestSourceRun.error_message ?? selectedSourceProfile.status ?? selectedSourceProfile.source_id) }}</small>
            </div>
            <div class="alert-stat-grid">
              <span><small>method</small><strong>{{ text(selectedSourceProfile.method) }}</strong></span>
              <span><small>priority</small><strong>{{ text(selectedSourceProfile.priority) }}</strong></span>
              <span><small>group</small><strong>{{ text(selectedSourceProfile.group_name) }}</strong></span>
              <span><small>fallback</small><strong>{{ text(selectedSourceProfile.fallback_source_id, 'none') }}</strong></span>
              <span><small>runs</small><strong>{{ selectedSourceRuns.length }}</strong></span>
              <span><small>metrics</small><strong>{{ selectedSourceMetrics.length }}</strong></span>
            </div>
          </section>

          <section v-if="state.selectedSourceDetail" class="source-detail-grid">
            <article class="quality-card">
              <div class="section-title-row">
                <h3>Latest Source Run</h3>
                <span class="pill" :class="sourceStatusClass(latestSourceRun.status)">{{ text(latestSourceRun.status) }}</span>
              </div>
              <div class="detail-kv-grid">
                <span><small>run_id</small><strong>{{ text(latestSourceRun.run_id) }}</strong></span>
                <span><small>mode</small><strong>{{ text(latestSourceRun.mode) }}</strong></span>
                <span><small>started</small><strong>{{ timestampText(latestSourceRun.started_at) }}</strong></span>
                <span><small>completed</small><strong>{{ timestampText(latestSourceRun.completed_at) }}</strong></span>
                <span><small>latency</small><strong>{{ sourceRunDuration(latestSourceRun) }}</strong></span>
                <span><small>status meaning</small><strong>{{ sourceMeaning(latestSourceRun.error_message ?? latestSourceRun.status) }}</strong></span>
              </div>
              <p class="source-error-text">{{ text(latestSourceRun.error_message, 'no latest error message') }}</p>
            </article>

            <article class="quality-card">
              <div class="section-title-row">
                <h3>Freshness Policy</h3>
                <span class="pill quality">{{ text(selectedSourceMetadata.quality_score, 'q pending') }}</span>
              </div>
              <div class="detail-kv-grid">
                <span v-for="row in freshnessPolicyRows(selectedSourceFreshnessPolicy)" :key="row.key">
                  <small>{{ row.key.replace(/_/g, ' ') }}</small>
                  <strong>{{ text(row.value) }}</strong>
                </span>
              </div>
            </article>
          </section>

          <section v-if="state.selectedSourceDetail" class="source-detail-grid">
            <article class="quality-card">
              <div class="section-title-row">
                <h3>Raw Observation Preview</h3>
                <span class="pill">{{ selectedSourceRawObservations.length }} observations</span>
              </div>
              <button v-for="raw in selectedSourceRawObservations.slice(0, 6)" :key="`${text(raw.run_id)}-${text(raw.observed_at)}`" class="source-run-row" :class="sourceStatusClass(raw.status ?? raw.error_message)">
                <strong>{{ text(raw.run_id) }}</strong>
                <small>{{ timestampText(raw.observed_at) }} · {{ text(raw.mode) }}</small>
                <em>payload keys: {{ Array.isArray(raw.payload_keys) ? raw.payload_keys.join(', ') : text(raw.payload_keys, 'sanitized preview only') }}</em>
              </button>
            </article>

            <article class="quality-card">
              <div class="section-title-row">
                <h3>Normalized Metrics</h3>
                <span class="pill">{{ selectedSourceMetrics.length }} values</span>
              </div>
              <button v-for="metric in selectedSourceMetrics.slice(0, 10)" :key="`${text(metric.metric_id)}-${text(metric.run_id)}-${text(metric.ts)}`" class="source-run-row" :class="metric.is_fallback ? 'quality' : sourceStatusClass(metric.run_mode)">
                <strong>{{ metricValueText(metric) }}</strong>
                <small>{{ text(metric.run_mode) }} · {{ timestampText(metric.ts) }} · fallback {{ text(metric.is_fallback) }}</small>
                <em>{{ text(metric.run_id) }}</em>
              </button>
            </article>
          </section>

          <section v-if="state.selectedSourceDetail" class="source-detail-grid">
            <article class="quality-card">
              <div class="section-title-row">
                <h3>Downstream Impact</h3>
                <span class="pill">{{ selectedSourceEvidence.length }} evidence</span>
              </div>
              <div class="source-status-row">
                <span v-for="moduleId in selectedSourceModules" :key="moduleId" class="pill">{{ moduleId }}</span>
              </div>
              <button v-for="item in selectedSourceEvidence.slice(0, 8)" :key="text(item.evidence_id ?? item.metric_id)" class="source-run-row" @click="openSourceEvidenceItem(item)">
                <strong>{{ text(item.metric_id) }}</strong>
                <small>{{ text(item.radar_module) }} · {{ text(item.direction) }} · score {{ text(item.metric_effective_score ?? item.metric_score) }}</small>
                <em>{{ text(item.evidence_id) }}</em>
              </button>
            </article>

            <article class="quality-card">
              <div class="section-title-row">
                <h3>Manual Verification</h3>
                <span class="pill" :class="sourceStatusClass(sourceAuthState(selectedManualSource))">auth {{ sourceAuthState(selectedManualSource) }}</span>
              </div>
              <p>{{ sourceManualSummary(selectedManualSource) }}</p>
              <div class="detail-kv-grid manual-kv-grid">
                <span><small>automation</small><strong>{{ sourceAutomationMode(selectedManualSource) }}</strong></span>
                <span><small>profile dir</small><strong>{{ sourceProfileDir(selectedManualSource) }}</strong></span>
                <span><small>last verified</small><strong>{{ timestampText(sourceLastVerified(selectedManualSource)) }}</strong></span>
                <span><small>requires profile</small><strong>{{ text(selectedManualSource.requires_human_verified_profile ?? isSemiAutomatedSource(selectedManualSource)) }}</strong></span>
                <span><small>last error</small><strong>{{ text(selectedManualSource.last_error ?? latestSourceRun.error_message, 'none') }}</strong></span>
                <span><small>last capture</small><strong>{{ text(selectedSourceLastCapture.status ?? selectedSourceLastCapture.capture_path ?? selectedSourceLastCapture.updated_at, 'pending') }}</strong></span>
              </div>
              <div class="alert-action-grid source-actions">
                <button @click="openVerifyWindowForSource(text(selectedManualSource.source_id ?? selectedSourceId))"><strong>Open Verify Window</strong><small>打开可见浏览器完成验证</small></button>
                <button @click="retryCollectForSource(text(selectedManualSource.source_id ?? selectedSourceId))"><strong>Retry Collect</strong><small>验证后立即重试采集</small></button>
                <button @click="viewLastCaptureForSource(text(selectedManualSource.source_id ?? selectedSourceId))"><strong>View Last Capture</strong><small>读取最近一次 capture 状态</small></button>
                <button @click="activePage = 'logs'"><strong>Open Run Logs</strong><small>查看采集阶段和报告</small></button>
              </div>
              <p class="manual-action-result">{{ sourceActionStatus(selectedSourceActionResult) }}</p>
            </article>
          </section>
        </article>

        <article v-else-if="activePage === 'conflict'" class="panel conflict-page">
          <div class="panel-head">
            <div>
              <h2>多源冲突与仲裁解释</h2>
              <p>Source conflict is auditable data boundary, not collection failure.</p>
            </div>
            <span class="pill" :class="conflictStats.high ? 'bear' : conflictStats.total ? 'mixed' : 'bull'">{{ conflictStats.total }} conflicts</span>
          </div>

          <section class="quality-hero">
            <div class="alert-hero-main">
              <span class="pill quality">P1/P2 -> P4.5 evidence trace</span>
              <h3>本轮多源冲突 {{ conflictStats.total }} 项</h3>
              <p>页面按 selected source、candidate/fallback source、source_resolution、fallback、quality 和 downstream score 展示仲裁结果。</p>
              <small>definition_conflict 不渲染为采集失败；value_conflict 才提示高风险校准。</small>
            </div>
            <div class="alert-stat-grid">
              <span><small>high risk</small><strong>{{ conflictStats.high }}</strong></span>
              <span><small>fallback</small><strong>{{ conflictStats.fallback }}</strong></span>
              <span><small>definition</small><strong>{{ conflictStats.definition }}</strong></span>
              <span><small>duplicate groups</small><strong>{{ duplicateGroups.length }}</strong></span>
            </div>
          </section>

          <section v-if="multiSourceConflictRows.length" class="conflict-grid">
            <article
              v-for="row in multiSourceConflictRows"
              :key="`${conflictMetricId(row)}-${text(row.conflict_origin)}-${conflictSelectedSource(row)}`"
              class="conflict-card"
              :class="conflictSeverityClass(row)"
            >
              <div class="conflict-card-head">
                <div>
                  <strong>{{ metricLabel(conflictMetricId(row)) }}</strong>
                  <small>{{ text(row.radar_module ?? row.module_id, 'module pending') }}</small>
                </div>
                <span class="pill" :class="conflictSeverityClass(row)">{{ conflictTypeLabel(row) }}</span>
              </div>
              <div class="detail-kv-grid">
                <span><small>selected source</small><strong>{{ conflictSelectedSource(row) }}</strong></span>
                <span><small>candidates / fallback</small><strong>{{ text(conflictSourceList(row).join(', '), 'none') }}</strong></span>
                <span><small>source resolution</small><strong>{{ text(row.source_resolution ?? row.source_resolution_status ?? row.conflict_origin) }}</strong></span>
                <span><small>quality</small><strong>{{ text(row.quality_score) }}</strong></span>
                <span><small>metric score</small><strong>{{ text(row.metric_score) }}</strong></span>
                <span><small>effective score</small><strong>{{ text(row.metric_effective_score) }}</strong></span>
              </div>
              <p>{{ conflictReason(row) }}</p>
              <p>{{ conflictImpactText(row) }}</p>
              <div class="article-actions">
                <button class="small-link" :disabled="!conflictEvidenceId(row)" @click="openConflictEvidence(row)">Open Evidence</button>
                <button class="small-link" :disabled="!row.radar_module && !row.module_id" @click="openConflictRadar(row)">Open Radar</button>
                <button class="small-link" :disabled="!conflictSelectedSource(row)" @click="openSourceDetail(conflictSelectedSource(row))">Open Source</button>
              </div>
            </article>
          </section>

          <section v-else class="empty-note">
            本轮 API 未返回 source_conflicts，也没有检测到跨源 duplicate/fallback 冲突。若 P1/P2 HTML 显示冲突，需要回到 P9 聚合 API 补 `conflicting_evidence.source_conflicts`。
          </section>
        </article>

        <article v-else-if="activePage === 'logs'" class="panel runlogs-page">
          <div class="panel-head">
            <h2>Run Logs</h2>
            <button class="primary" @click="runAndOpenLogs" :disabled="state.running">
              {{ state.running ? 'Running' : 'Run Full Chain' }}
            </button>
          </div>
          <section class="run-pipeline-card" :class="[runHealthClass, { running: state.running }]">
            <div class="run-pipeline-head">
              <div>
                <span class="pipeline-eyebrow">current chain</span>
                <strong><span class="pipeline-live-dot"></span>{{ runningStageText }}</strong>
                <code>{{ text(store.finalRunId.value, '等待 final_run_id') }}</code>
              </div>
              <div class="run-status-actions">
                <span class="pipeline-status-pill" :class="runHealthClass"><i></i>{{ state.running ? 'Running' : text(latestRun.status, 'Ready') }}</span>
                <button @click="store.refreshLatest" :disabled="state.loading || state.running">Refresh</button>
                <button @click="openAuditReports">Audit Reports</button>
              </div>
            </div>
            <div class="run-pipeline" :style="pipelineProgressStyle">
              <div class="pipeline-track">
                <div class="pipeline-line"></div>
                <div class="pipeline-progress"></div>
                <div v-if="pipelineActive" class="pipeline-packet-rail">
                  <span class="pipeline-packet"></span>
                  <span class="pipeline-packet"></span>
                  <span class="pipeline-packet"></span>
                </div>
                <button
                  v-for="node in pipelineNodes"
                  :key="node.key"
                  class="pipeline-node"
                  :class="node.state"
                  @click="openPipelineStage(node)"
                >
                  <span class="pipeline-core">
                    <span v-if="node.state === 'active'" class="pipeline-scan-ring"></span>
                    <strong>{{ node.code }}</strong>
                    <em>{{ node.icon }}</em>
                  </span>
                  <span class="pipeline-label">
                    <strong>{{ node.label }}</strong>
                    <code>{{ shortRunId(node.runId) }}</code>
                    <small>{{ node.state }}</small>
                  </span>
                </button>
              </div>
            </div>
            <div class="pipeline-footer">
              <span>
                <small>run lineage</small>
                <strong>{{ runLlmEnabled ? 'P1 collect -> P2 radar -> P3 scoring -> P4.5 final -> LLM analyst' : 'P1 collect -> P2 radar -> P3 scoring -> P4.5 final' }}</strong>
              </span>
              <span>
                <small>execution profile</small>
                <strong>{{ runExecutionProfile }}</strong>
              </span>
              <span>
                <small>LLM status</small>
                <strong>{{ text(state.activeRunJob?.llm_status ?? latestRun.llm_status, runLlmEnabled ? pipelineHeartbeatText : 'skipped') }}</strong>
              </span>
            </div>
          </section>
          <section class="run-lineage-board">
            <div class="panel-head">
              <h3>Run Lineage</h3>
              <span class="pill mixed">frozen final lineage</span>
            </div>
            <div class="route-context-grid compact">
              <span><small>final_run_id</small><code>{{ text(frozenFinalLineage.final_run_id, 'pending') }}</code></span>
              <span><small>pack_id</small><code>{{ text(frozenFinalLineage.pack_id, 'pending') }}</code></span>
              <span><small>final created</small><code>{{ text(frozenFinalCreatedAt, 'pending') }}</code></span>
              <span><small>runtime mode</small><code>{{ text(frozenFinalLineage.runtime_mode ?? latestRun.runtime_mode, 'runtime pending') }}</code></span>
            </div>
            <div class="run-lineage-grid">
              <div v-for="entry in runLineageEntries" :key="entry.key" class="lineage-chip">
                <span>{{ entry.key.replace(/_/g, ' ') }}</span>
                <code>{{ text(entry.value) }}</code>
              </div>
            </div>
          </section>
          <section class="run-lineage-board">
            <div class="panel-head">
              <h3>Live Runtime Freshness</h3>
              <span class="pill bull">live radar heartbeat</span>
            </div>
            <div class="route-context-grid compact">
              <span><small>snapshot_id</small><code>{{ text(liveRuntimeFreshness.snapshot_id, 'pending') }}</code></span>
              <span><small>health</small><code>{{ text(liveRuntimeFreshness.health_state, 'unknown') }}</code></span>
              <span><small>runtime/source</small><code>{{ text(liveRuntimeFreshness.runtime_fresh, 'unknown') }} / {{ text(liveRuntimeFreshness.source_fresh, 'unknown') }}</code></span>
              <span><small>heartbeat age</small><code>{{ text(liveRuntimeFreshness.last_tick_age_sec, '-') }}s</code></span>
            </div>
          </section>
          <section v-if="runWarnings.length || runErrors.length" class="run-issue-grid">
            <article v-if="runWarnings.length" class="run-issue-card quality">
              <strong>Warnings / degraded but auditable</strong>
              <p v-for="(warning, index) in runWarnings" :key="`warning-${index}`">{{ issueText(warning) }}</p>
            </article>
            <article v-if="runErrors.length" class="run-issue-card bear">
              <strong>Errors / blocking failures</strong>
              <p v-for="(error, index) in runErrors" :key="`error-${index}`">{{ issueText(error) }}</p>
            </article>
          </section>
          <section class="stage-grid">
            <article
              v-for="stage in stages"
              :key="stageId(stage)"
              class="stage-card"
              :class="statusClass(stage.status)"
            >
              <div class="stage-head">
                <strong>{{ text(stage.label) }}</strong>
                <span>{{ text(stage.status) }}</span>
              </div>
              <code>{{ text(stage.run_id) }}</code>
              <div class="stage-meta-grid">
                <span>{{ stageId(stage) }}</span>
                <span>{{ stageUpdatedText(stage) }}</span>
                <span>{{ stageScope(stage) }}</span>
              </div>
              <p>{{ stageNote(stage) }}</p>
              <div v-if="stageNeedsManualAction(stage)" class="stage-action-row">
                <span class="pill mixed">manual reauth</span>
                <button @click="openVerifyWindowForSource(stageManualSourceId(stage))">Open Verify Window</button>
                <button @click="retryCollectForSource(stageManualSourceId(stage))">Retry Collect</button>
              </div>
              <button
                v-if="stageReport(stage).file_url"
                class="report-link"
                @click="openReport(stageReport(stage))"
              >
                {{ stageArtifactLabel(stage) }} · {{ reportSize(stageReport(stage).size_bytes) }}
              </button>
              <span v-else class="artifact-pending">{{ stageArtifactLabel(stage) }}</span>
            </article>
          </section>
          <section class="audit-report-grid">
            <div class="panel-head">
              <h3>Audit Reports</h3>
              <span class="pill">{{ auditReports.length }} reports</span>
            </div>
            <button
              v-for="report in auditReports"
              :key="text(report.relative_path ?? report.filename)"
              class="audit-report-card"
              @click="openReport(report)"
            >
              <strong>{{ reportTitle(report) }}</strong>
              <span>{{ text(report.phase) }} · {{ reportSize(report.size_bytes) }}</span>
              <span>{{ reportUpdatedText(report) }}</span>
              <small>{{ text(report.relative_path ?? report.filename) }}</small>
            </button>
          </section>
          <section v-if="state.runResult" class="run-result-box">
            <h3>Last Run Result</h3>
            <pre>{{ JSON.stringify(state.runResult, null, 2) }}</pre>
          </section>
        </article>

        <article v-else-if="activePage === 'history'" class="panel history-page">
          <div class="panel-head">
            <div>
              <h2>History Replay</h2>
              <p>Frozen final_run_id replay · read-only snapshot · no latest-run pollution</p>
            </div>
            <span class="pill" :class="state.routeContext.isHistorical ? 'quality' : 'mixed'">
              {{ state.routeContext.isHistorical ? 'historical mode' : 'latest mode' }}
            </span>
          </div>

          <section class="history-hero" :class="directionClass(historyFinal.final_view ?? historyDecision.direction)">
            <div>
              <span class="pill quality">read only replay</span>
              <h3>{{ text(historyFinal.final_view_cn ?? historyDecision.direction_cn ?? historyFinal.final_view, '选择一个历史 run') }}</h3>
              <p>{{ text(historyDecision.conclusion_sentence ?? historyResearch.executive_summary ?? historyPublish.body, '从下方快照选择 final_run_id，回放当时的 P4.5 final payload、文章、证据包和审计报告。') }}</p>
              <small>{{ historyValidityText() }}</small>
            </div>
            <div class="alert-stat-grid">
              <span><small>final run</small><strong>{{ text(historyLineage.final_run_id ?? state.routeContext.final_run_id, 'none') }}</strong></span>
              <span><small>runtime</small><strong>{{ text(historyFinal.runtime_mode ?? historyLineage.runtime_mode) }}</strong></span>
              <span><small>confidence</small><strong>{{ text(historyDecision.confidence ?? historyAggregation.confidence) }}</strong></span>
              <span><small>trade</small><strong>{{ text(historyDecision.trade_permission) }}</strong></span>
              <span><small>reports</small><strong>{{ historyReports.length }}</strong></span>
              <span><small>analysts</small><strong>{{ historyAnalysts.length }}</strong></span>
            </div>
          </section>

          <section class="history-action-row">
            <button :disabled="!store.finalRunId.value" @click="store.loadHistory(store.finalRunId.value)">
              <strong>Freeze Current Run</strong>
              <small>{{ text(store.finalRunId.value, 'no latest final_run_id') }}</small>
            </button>
            <button :disabled="!state.routeContext.isHistorical" @click="exitHistoryReplay">
              <strong>Exit Replay</strong>
              <small>return to latest live payloads</small>
            </button>
            <button @click="activePage = 'article'">
              <strong>Article</strong>
              <small>read frozen article context</small>
            </button>
            <button @click="activePage = 'logs'">
              <strong>Run Logs</strong>
              <small>compare with latest run chain</small>
            </button>
          </section>

          <section class="history-layout">
            <article class="history-card">
              <div class="section-title-row">
                <h3>History Snapshots</h3>
                <span class="pill">{{ articleHistoryRows.length }} runs</span>
              </div>
              <button v-for="row in articleHistoryRows" :key="text(row.final_run_id)" class="snapshot-row" :class="articleSnapshotClass(row)" @click="openHistorySnapshot(row)">
                <span>
                  <strong>{{ text(row.title, 'P4.5 Research Article') }}</strong>
                  <small>{{ articleSnapshotStatus(row) }}</small>
                </span>
                <code>{{ text(row.final_run_id) }}</code>
                <em>{{ timestampText(row.created_at) }}</em>
              </button>
            </article>

            <article class="history-card">
              <div class="section-title-row">
                <h3>Frozen Run Lineage</h3>
                <span class="pill">{{ text(historyPayload.schema_version, 'p45.history.v1') }}</span>
              </div>
              <div class="lineage-grid compact">
                <span v-for="entry in historyLineageEntries" :key="entry.key">
                  <small>{{ entry.key.replace(/_/g, ' ') }}</small>
                  <code>{{ text(entry.value) }}</code>
                </span>
              </div>
            </article>
          </section>

          <section v-if="state.routeContext.isHistorical" class="history-layout">
            <article class="history-card">
              <div class="section-title-row">
                <h3>Frozen Article</h3>
                <span class="pill">{{ text(historyPublish.publish_type ?? historyFinal.schema_version) }}</span>
              </div>
              <h4>{{ text(historyPublish.title ?? historyResearch.title, 'historical article') }}</h4>
              <p>{{ text(historyPublish.body ?? historyResearch.executive_summary ?? historyResearch.body, 'article body pending in snapshot') }}</p>
            </article>

            <article class="history-card">
              <div class="section-title-row">
                <h3>Replay Analysis</h3>
                <span class="pill quality">calibration</span>
              </div>
              <div class="detail-kv-grid">
                <span><small>signal validity</small><strong>pending feedback</strong></span>
                <span><small>alert validity</small><strong>pending feedback</strong></span>
                <span><small>confidence calibration</small><strong>{{ text(historyDecision.confidence_level, 'pending') }}</strong></span>
                <span><small>data quality</small><strong>{{ text(historyAggregation.data_quality_level, 'pending') }}</strong></span>
              </div>
              <p>{{ historyValidityText() }}</p>
            </article>
          </section>

          <section v-if="state.routeContext.isHistorical" class="audit-report-grid">
            <div class="panel-head">
              <h3>Historical Audit Reports</h3>
              <span class="pill">{{ historyReports.length }} reports</span>
            </div>
            <button v-for="report in historyReports" :key="text(report.relative_path ?? report.filename)" class="audit-report-card" @click="openReport(report)">
              <strong>{{ reportTitle(report) }}</strong>
              <span>{{ text(report.phase) }} · {{ reportSize(report.size_bytes) }}</span>
              <span>{{ reportUpdatedText(report) }}</span>
              <small>{{ text(report.relative_path ?? report.filename) }}</small>
            </button>
          </section>
        </article>

        <article v-else class="panel settings-page">
          <div class="panel-head">
            <div>
              <h2>Settings</h2>
              <p>Read-only configuration view · secrets masked · changes require backend settings API.</p>
            </div>
            <div class="history-actions">
              <button @click="goDashboard">Back Dashboard</button>
              <button @click="store.refreshLatest" :disabled="state.loading">Refresh Settings</button>
            </div>
          </div>

          <section class="settings-hero">
            <div>
              <span class="pill bull">{{ text(settingsPayload.status, 'ok') }}</span>
              <h3>{{ text(settingsApp.app_name, 'onlyBTC') }} · {{ text(settingsApp.environment, 'development') }}</h3>
              <p>Settings reflects current FastAPI `/api/settings` payload. API keys are represented only by configured flags and never rendered as plaintext.</p>
            </div>
            <div class="detail-kv-grid">
              <span><small>schema</small><strong>{{ text(settingsPayload.schema_version, 'p45.settings.v1') }}</strong></span>
              <span><small>api schema</small><strong>{{ text(settingsPayload.api_schema_version, 'onlybtc.api.v1') }}</strong></span>
              <span><small>api host</small><strong>{{ text(settingsApp.api_host) }}:{{ text(settingsApp.api_port) }}</strong></span>
              <span><small>refresh</small><strong>{{ text(settingsApp.default_refresh_seconds) }}s</strong></span>
            </div>
          </section>

          <section v-if="settingsWarnings.length || settingsErrors.length" class="run-issue-grid">
            <article v-if="settingsWarnings.length" class="run-issue-card quality">
              <strong>Settings Warnings</strong>
              <p v-for="(warning, index) in settingsWarnings" :key="`settings-warning-${index}`">{{ issueText(warning) }}</p>
            </article>
            <article v-if="settingsErrors.length" class="run-issue-card bear">
              <strong>Settings Errors</strong>
              <p v-for="(error, index) in settingsErrors" :key="`settings-error-${index}`">{{ issueText(error) }}</p>
            </article>
          </section>

          <section class="settings-layout">
            <nav class="settings-tabs" aria-label="Settings sections">
              <button
                v-for="tab in settingsTabs"
                :key="tab.id"
                :class="{ active: settingsTab === tab.id }"
                @click="settingsTab = tab.id"
              >
                {{ tab.label }}
              </button>
            </nav>

            <div class="settings-panel">
              <section v-if="settingsTab === 'llm'" class="settings-section">
                <div class="section-title">
                  <h3>LLM Providers</h3>
                  <span class="pill quality">P4.5 runtime governance</span>
                </div>
                <div class="settings-card-grid">
                  <span><small>research provider</small><strong>{{ text(settingsLlm.p45_research_provider, 'deepseek') }}</strong><em>{{ settingSourceLabel(settingsLlm.p45_research_provider) }}</em></span>
                  <span><small>deepseek model</small><strong>{{ text(settingsLlm.deepseek_model, 'deepseek-reasoner') }}</strong><em>{{ settingSourceLabel(settingsLlm.deepseek_model) }}</em></span>
                  <span><small>mock mode</small><strong>{{ settingsLlmRouting.mock_mode_enabled ? 'enabled' : 'disabled' }}</strong><em>P4 runtime</em></span>
                  <span><small>fallback policy</small><strong>{{ text(settingsLlmRouting.fallback_policy, 'fallback') }}</strong><em>P4 runtime</em></span>
                  <span><small>timeout</small><strong>{{ text(settingsLlmRuntimeDefaults.timeout_seconds, text(settingsLlm.p45_research_timeout_seconds, '180')) }}s</strong><em>.env / default</em></span>
                  <span><small>max tokens</small><strong>{{ text(settingsLlmRuntimeDefaults.max_tokens_per_call, '4096') }}</strong><em>per call</em></span>
                  <span><small>temperature</small><strong>{{ text(settingsLlmRuntimeDefaults.temperature, '0.2') }}</strong><em>chat completions</em></span>
                  <span><small>available</small><strong>{{ text(settingsLlmAvailableCount, '0') }}</strong><em>configured providers</em></span>
                </div>
                <div class="section-title compact-title">
                  <h3>Provider Readiness</h3>
                  <span class="pill quality">{{ text(settingsLlmProviders.length) }} providers</span>
                </div>
                <div class="settings-key-list">
                  <article v-for="row in settingsLlmProviders" :key="text(row.provider)" class="settings-key-row llm-route-row" :class="row.enabled ? 'bull' : 'neutral'">
                    <div>
                      <strong>{{ text(row.provider) }}</strong>
                      <small>{{ text(row.model, 'model missing') }} · {{ row.enabled ? 'enabled' : text(row.disabled_reason, 'disabled') }}</small>
                    </div>
                    <code>{{ text(row.base_url, 'base_url missing') }}</code>
                    <span class="pill">{{ row.api_key_configured ? 'key configured' : 'no key' }}</span>
                  </article>
                </div>
                <div class="section-title compact-title">
                  <h3>P4 Agent Routes</h3>
                  <span class="pill">{{ text(settingsLlmRoutes.length) }} routes</span>
                </div>
                <div class="settings-key-list">
                  <article v-for="row in settingsLlmRoutes" :key="text(row.agent_id)" class="settings-key-row llm-route-row" :class="row.enabled_for_llm ? 'bull' : 'mixed'">
                    <div>
                      <strong>{{ text(row.agent_label, text(row.agent_id)) }}</strong>
                      <small>{{ text(row.settings_field) }} · {{ row.mock_mode_bypasses_provider ? 'mock bypass' : 'real llm' }}</small>
                    </div>
                    <code>{{ text(row.provider) }} · {{ text(row.model, 'model missing') }}</code>
                    <span class="pill">{{ row.enabled_for_llm ? 'ready' : text(row.disabled_reason, 'disabled') }}</span>
                  </article>
                </div>
                <div class="settings-action-row">
                  <button disabled>Test Provider</button>
                  <button disabled>Save Changes</button>
                  <button disabled>Restore Default</button>
                </div>
              </section>

              <section v-else-if="settingsTab === 'keys'" class="settings-section">
                <div class="section-title">
                  <h3>API Keys</h3>
                  <span class="pill mixed">{{ text(settingsKeyRows.length) }} providers</span>
                </div>
                <div v-if="settingsKeyMessage || settingsKeyError" class="settings-save-status" :class="{ bear: settingsKeyError }">
                  {{ settingsKeyError || settingsKeyMessage }}
                </div>
                <div class="settings-key-list">
                  <article v-for="row in settingsKeyRows" :key="row.key" class="settings-key-row" :class="settingsKeyRowClass(row)">
                    <div>
                      <strong>{{ row.provider }}</strong>
                      <small>{{ row.key }} · {{ row.scope }} · {{ row.status }}</small>
                      <small class="settings-health-line">{{ providerHealthStatus(row) }} · {{ providerHealthMeta(row) }}</small>
                    </div>
                    <code>{{ text(row.masked, maskedSecret(row.enabled)) }}</code>
                    <input
                      v-model.trim="settingsKeyInputs[row.key]"
                      type="password"
                      autocomplete="off"
                      spellcheck="false"
                      :placeholder="row.enabled ? 'new key' : 'api key'"
                      @keyup.enter="saveSettingsKey(row)"
                    />
                    <div class="settings-key-actions">
                      <button
                        @click="saveSettingsKey(row)"
                        :disabled="settingsKeySaving === row.key || !hasSettingsKeyDraft(row.key)"
                      >
                        {{ settingsKeySaving === row.key ? 'Saving' : row.enabled ? 'Rotate' : 'Configure' }}
                      </button>
                      <button
                        @click="testSettingsProvider(row)"
                        :disabled="settingsProviderTesting === row.providerId || !row.supportsTest"
                      >
                        {{ settingsProviderTesting === row.providerId ? 'Testing' : 'Test' }}
                      </button>
                    </div>
                  </article>
                </div>
              </section>

              <section v-else-if="settingsTab === 'data'" class="settings-section">
                <div class="section-title">
                  <h3>Data Sources</h3>
                  <span class="pill">{{ text(sourceSummary.length) }} sampled sources</span>
                </div>
                <div class="settings-card-grid">
                  <span><small>source health</small><strong>{{ text(sourceHealth.status ?? sourceHealth.overall_status, 'latest') }}</strong><em>from Data Quality API</em></span>
                  <span><small>freshness policy</small><strong>{{ text(qualityContract.freshness_check ? 'enabled' : 'pending') }}</strong><em>P1/P8 contract</em></span>
                  <span><small>fallback governance</small><strong>{{ text(qualityChecks.duplicate_groups_checked ? 'checked' : 'pending') }}</strong><em>P2/P3 evidence</em></span>
                  <span><small>playwright sources</small><strong>{{ sourceSummary.filter((id) => id.includes('playwright')).length }}</strong><em>detected source ids</em></span>
                </div>
                <div class="section-title compact-title">
                  <h3>Semi-Automated Sources</h3>
                  <span class="pill mixed">{{ semiAutoSources.length }} configured</span>
                </div>
                <div class="settings-key-list">
                  <article v-for="row in semiAutoSources" :key="sourceId(row)" class="settings-key-row manual-settings-row" :class="sourceStatusClass(sourceAuthState(row))">
                    <div>
                      <strong>{{ sourceId(row) }}</strong>
                      <small>{{ sourceAutomationMode(row) }} · profile {{ sourceProfileDir(row) }}</small>
                    </div>
                    <code>{{ sourceAuthState(row) }} · {{ timestampText(sourceLastVerified(row)) }}</code>
                    <button @click="openSourceDetail(sourceId(row))">Open</button>
                  </article>
                </div>
              </section>

              <section v-else-if="settingsTab === 'radar'" class="settings-section">
                <div class="section-title">
                  <h3>Radar & Alerts</h3>
                  <span class="pill">{{ store.radarModules.value.length || 14 }} modules</span>
                </div>
                <div class="settings-card-grid">
                  <span><small>contract status</small><strong>{{ text(contract.status, 'unknown') }}</strong><em>P4.5 validation</em></span>
                  <span><small>alert level</small><strong>{{ text(topAlert?.level, 'watch') }}</strong><em>P3 alerts</em></span>
                  <span><small>invalidation rules</small><strong>{{ invalidationRules.length }}</strong><em>decision repair</em></span>
                  <span><small>confirmation rules</small><strong>{{ confirmationRules.length }}</strong><em>trend confirmation</em></span>
                </div>
              </section>

              <section v-else-if="settingsTab === 'run'" class="settings-section">
                <div class="section-title">
                  <h3>Run Once & Scheduler</h3>
                  <span class="pill" :class="runHealthClass">{{ runningStageText }}</span>
                </div>
                <div class="settings-card-grid">
                  <span><small>run mode</small><strong>{{ text(settingsRunDefaults.run_mode, 'live') }}</strong><em>default</em></span>
                  <span><small>runtime mode</small><strong>{{ text(settingsRunDefaults.runtime_mode, 'deterministic') }}</strong><em>default</em></span>
                  <span><small>llm runtime</small><strong>{{ text(settingsRunDefaults.llm_runtime_mode, 'llm') }}</strong><em>default</em></span>
                  <span><small>latest final</small><strong>{{ text(store.finalRunId.value, 'pending') }}</strong><em>current lineage</em></span>
                </div>
                <div class="settings-action-row">
                  <button class="primary" @click="runAndOpenLogs" :disabled="state.running">{{ state.running ? 'Running' : 'Run Full Chain' }}</button>
                  <button @click="navigateTo('logs')">Open Run Logs</button>
                </div>
              </section>

              <section v-else-if="settingsTab === 'publish'" class="settings-section">
                <div class="section-title">
                  <h3>Publish Policy</h3>
                  <span class="pill mixed">watch only by default</span>
                </div>
                <div class="settings-card-grid">
                  <span><small>trade permission</small><strong>{{ text(decision.trade_permission, 'watch_only') }}</strong><em>decision card</em></span>
                  <span><small>safe to publish</small><strong>{{ text(articlePublish.safe_to_publish, 'pending') }}</strong><em>publish article</em></span>
                  <span><small>article language</small><strong>中文</strong><em>P4.5 report</em></span>
                  <span><small>manual confirm</small><strong>required before external post</strong><em>UI policy</em></span>
                </div>
              </section>

              <section v-else-if="settingsTab === 'storage'" class="settings-section">
                <div class="section-title">
                  <h3>Storage & Paths</h3>
                  <span class="pill quality">read only</span>
                </div>
                <div class="settings-card-grid">
                  <span><small>audit reports</small><strong>{{ auditReports.length }} files</strong><em>reports/</em></span>
                  <span><small>history snapshots</small><strong>{{ articleHistoryRows.length }}</strong><em>P4.5 replay API</em></span>
                  <span><small>backup policy</small><strong>manual backups active</strong><em>workspace controlled</em></span>
                  <span><small>sqlite</small><strong>backend managed</strong><em>not mutated from UI</em></span>
                </div>
              </section>

              <section v-else class="settings-section">
                <div class="section-title">
                  <h3>System</h3>
                  <span class="pill bull">{{ text(settingsPayload.status, 'ok') }}</span>
                </div>
                <div class="settings-card-grid">
                  <span><small>frontend</small><strong>Vue3</strong><em>Vite dashboard</em></span>
                  <span><small>backend</small><strong>{{ text(settingsApp.api_host) }}:{{ text(settingsApp.api_port) }}</strong><em>FastAPI</em></span>
                  <span><small>endpoint errors</small><strong>{{ state.errors.length }}</strong><em>non-blocking cache</em></span>
                  <span><small>created at</small><strong>{{ timestampText(settingsPayload.created_at) }}</strong><em>settings payload</em></span>
                  <span><small>key audit events</small><strong>{{ text(settingsAudit.event_count, '0') }}</strong><em>{{ text(settingsAudit.schema_version, 'p10.c06.settings_key_audit.v1') }}</em></span>
                  <span><small>audit log</small><strong>{{ text(settingsAudit.log_path, 'logs/settings-key-audit.jsonl') }}</strong><em>redacted jsonl</em></span>
                </div>
                <div class="section-title compact-title">
                  <h3>Recent Key Audit</h3>
                  <span class="pill quality">{{ settingsAuditEvents.length }} events</span>
                </div>
                <div class="settings-key-list">
                  <article v-for="event in settingsAuditEvents" :key="text(event.event_id)" class="settings-key-row llm-route-row" :class="text(event.status) === 'failed' ? 'mixed' : 'bull'">
                    <div>
                      <strong>{{ text(event.action, 'audit') }} · {{ text(event.status, 'success') }}</strong>
                      <small>{{ timestampText(event.created_at) }} · {{ text(event.actor, 'local_api') }}</small>
                    </div>
                    <code>{{ compactList(event.env_keys, compactList(event.provider_ids, 'settings')) }}</code>
                    <span class="pill">{{ event.redacted ? 'redacted' : 'check' }}</span>
                  </article>
                </div>
              </section>
            </div>
          </section>
        </article>
      </section>

      <aside v-if="drawerOpen && !pageFullscreen" class="summary route-drawer">
        <article class="panel route-context-panel">
          <div class="panel-head">
            <div>
              <h2>{{ pageTitle }}</h2>
              <p>{{ routeModeLabel }}</p>
            </div>
            <button class="modal-close" aria-label="Close context drawer" @click="drawerOpen = false">Close</button>
          </div>
          <div class="route-context-grid">
            <span><small>final_run_id</small><code>{{ text(state.routeContext.final_run_id ?? store.runLineage.value.final_run_id) }}</code></span>
            <span><small>pack_id</small><code>{{ text(state.routeContext.pack_id ?? store.runLineage.value.pack_id) }}</code></span>
            <span><small>module_id</small><code>{{ text(state.routeContext.module_id, 'all') }}</code></span>
            <span><small>evidence_id</small><code>{{ text(state.routeContext.evidence_id, 'none') }}</code></span>
            <span><small>source_id</small><code>{{ text(state.routeContext.source_id, 'none') }}</code></span>
          </div>
          <div class="route-action-row">
            <button @click="goDashboard">Back Dashboard</button>
            <button :disabled="!fullscreenPages.has(activePage)" @click="togglePageFullscreen">Fullscreen</button>
          </div>
        </article>

        <article class="panel decision-panel">
          <div class="panel-head"><h2>Decision Card</h2><span class="pill">{{ text(state.dashboard?.final_view, 'final_view') }}</span></div>
          <div class="decision-list">
            <div v-for="(reason, index) in decisionReasons" :key="`${index}-${text(reason)}`" class="reason">
              <span class="num">{{ index + 1 }}</span>
              <span>{{ text(reason) }}</span>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-head"><h2>Run Lineage</h2><span class="pill mixed">frozen final lineage</span></div>
          <div class="runline">
            <div><span>collect</span><code>{{ text(frozenFinalLineage.collect_run_id) }}</code></div>
            <div><span>p2 radar</span><code>{{ text(frozenFinalLineage.p2_radar_run_id) }}</code></div>
            <div><span>p3</span><code>{{ text(frozenFinalLineage.p3_run_id) }}</code></div>
            <div><span>p45 final</span><code>{{ text(frozenFinalLineage.final_run_id) }}</code></div>
            <div><span>llm mode</span><code>{{ text(llm.provider, 'deepseek') }} · internal_reference</code></div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-head"><h2>Live Runtime</h2><span class="pill bull">radar freshness</span></div>
          <div class="runline">
            <div><span>snapshot</span><code>{{ text(liveRuntimeFreshness.snapshot_id) }}</code></div>
            <div><span>health</span><code>{{ text(liveRuntimeFreshness.health_state, 'unknown') }}</code></div>
            <div><span>runtime/source</span><code>{{ text(liveRuntimeFreshness.runtime_fresh, 'unknown') }} / {{ text(liveRuntimeFreshness.source_fresh, 'unknown') }}</code></div>
            <div><span>heartbeat</span><code>{{ text(liveRuntimeFreshness.last_tick_age_sec, '-') }}s</code></div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-head"><h2>LLM Appendix</h2><span class="pill quality">internal_reference</span></div>
          <div class="llm-grid">
            <div v-for="item in analystCards" :key="text(item.analyst_id)" class="llm-card">
              <strong>{{ text(item.analyst_id) }}</strong>
              <span>{{ text(item.status) }} · {{ text(item.provider ?? llm.provider, 'DeepSeek') }}</span>
              <small>{{ text(item.title, 'evidence cited') }}</small>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="quick-links">
            <button @click="navigateTo('overview')">Overview</button>
            <button @click="navigateTo('article')">Article</button>
            <button @click="navigateTo('radar')">Radar</button>
            <button @click="navigateTo('evidence')">Evidence</button>
            <button @click="navigateTo('alerts')">Alerts</button>
            <button @click="navigateTo('invalidation')">Invalidation</button>
            <button @click="navigateTo('quality')">Data Quality</button>
            <button @click="navigateTo('conflict')">Conflicts</button>
            <button @click="navigateTo('logs')">Run Logs</button>
            <button @click="navigateTo('history')">History</button>
            <button @click="navigateTo('settings')">Settings</button>
            <button @click="openAuditReports">Audit Reports</button>
          </div>
          <p>Click BTC, Radar, Alert, Evidence or Run Once to open detail views while preserving the same run context.</p>
        </article>
      </aside>
    </section>

    <div
      v-if="activePage === 'evidence' && state.selectedEvidenceDetail"
      class="modal-backdrop"
      role="presentation"
      @click.self="closeEvidenceDetail"
    >
      <aside class="evidence-modal" role="dialog" aria-modal="true" aria-label="Evidence detail">
        <div class="detail-title">
          <div>
            <small>selected evidence</small>
            <h3>{{ evidenceTitle(selectedEvidence) }}</h3>
          </div>
          <button class="modal-close" aria-label="Close evidence detail" @click="closeEvidenceDetail">Close</button>
        </div>
        <div class="modal-headline">
          <code class="evidence-id">{{ selectedEvidenceId }}</code>
          <span class="pill" :class="directionClass(evidenceDisplayDirection(selectedEvidence))">{{ evidenceDirectionLabel(selectedEvidence) }}</span>
        </div>
        <p class="detail-brief">{{ evidenceBrief(selectedEvidence) }}</p>
        <div class="detail-kv-grid">
          <span><small>value</small><strong>{{ text(selectedEvidence.value ?? selectedEvidence.current_value) }}</strong></span>
          <span><small>self direction</small><strong>{{ text(selectedEvidence.metric_self_direction ?? selectedEvidence.direction) }}</strong></span>
          <span><small>self score</small><strong>{{ text(selectedEvidence.metric_self_score ?? selectedEvidence.metric_score) }}</strong></span>
          <span><small>metric score</small><strong>{{ text(selectedEvidence.metric_score) }}</strong></span>
          <span><small>effective score</small><strong>{{ text(selectedEvidence.metric_effective_score) }}</strong></span>
          <span><small>quality</small><strong>{{ text(selectedEvidence.quality_score) }}</strong></span>
          <span><small>bucket</small><strong>{{ text(selectedEvidence.score_bucket) }}</strong></span>
          <span><small>available</small><strong>{{ text(selectedEvidence.available) }}</strong></span>
        </div>
        <section class="detail-section">
          <h4>Interpretation</h4>
          <p>{{ readableMetricText(selectedEvidence.score_reason ?? selectedEvidence.metric_explanation) }}</p>
          <p v-if="evidenceCompositeLine(selectedEvidence)">{{ evidenceCompositeLine(selectedEvidence) }}</p>
          <p>{{ evidenceWeightLine(selectedEvidence) }}</p>
        </section>
        <section class="detail-section">
          <h4>Source & Freshness</h4>
          <p>{{ evidenceSourceLine(selectedEvidence) }}</p>
          <p>{{ evidenceFreshnessLine(selectedEvidence) }}</p>
          <p>source_ts {{ text(selectedEvidence.source_ts) }} | collected_at {{ text(selectedEvidence.collected_at) }}</p>
          <button class="small-link" @click="openSourceDetail(String(selectedEvidence.source_id))">Open Source Detail</button>
        </section>
        <section class="detail-section">
          <h4>Horizon & Duplicate</h4>
          <p>{{ evidenceHorizonLine(selectedEvidence) }}</p>
          <p>semantic {{ text(selectedEvidence.semantic_rule_id) }} | role {{ text(selectedEvidence.role) }} | tier {{ text(selectedEvidence.evidence_tier) }}</p>
        </section>
        <section class="detail-section">
          <h4>History Context</h4>
          <p>previous {{ text(selectedEvidenceHistory.previous_value) }} | 24h {{ text(selectedEvidenceHistory.change_24h) }} | 7d {{ text(selectedEvidenceHistory.change_7d) }} | ma30 {{ text(selectedEvidenceHistory.ma_30d) }}</p>
        </section>
        <section v-if="selectedEvidence.fallback_used || selectedEvidence.fallback_reason || selectedEvidence.is_stale || selectedEvidence.legacy_future_source_ts" class="detail-section warning">
          <h4>Boundary Flags</h4>
          <p>fallback {{ text(selectedEvidence.fallback_used) }} | reason {{ text(selectedEvidence.fallback_reason) }} | stale {{ text(selectedEvidence.is_stale) }}</p>
          <p v-if="selectedEvidence.freshness_display_note">{{ text(selectedEvidence.freshness_display_note) }}</p>
        </section>
      </aside>
    </div>

    <p v-if="state.error" class="error">{{ state.error }}</p>
    <section v-if="store.hasEndpointErrors.value" class="endpoint-errors">
      <strong>API errors</strong>
      <span v-for="err in state.errors" :key="`${err.method}-${err.endpoint}-${err.status}`">
        {{ err.method }} {{ err.endpoint }} · {{ text(err.status) }}
      </span>
    </section>
  </main>
</template>

