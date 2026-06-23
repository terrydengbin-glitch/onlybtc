# P5-C73 Event Watchtower Three-column Layout Audit

## Status

DONE

## Scope

- Updated only the Event Watchtower Vue template and dedicated `event-*` styles.
- Added computed helpers for the Event Watchtower Calendar Mini month grid.
- No backend API/schema, BTC score, radar score, topbar, left rail, or other page behavior changed.

## Implementation

- `frontend/src/App.vue`
  - Added `eventCalendarMiniAnchor`, `eventCalendarMiniMonthLabel`, `eventCalendarMiniDays`, and weekday helpers.
  - Calendar Mini now groups real `eventWindowCalendar` rows by the active event month, using `release_time_utc`, `release_time`, `event_time`, or `date`.
  - Current Alert now exposes event title, `event_window_state`, reason codes, permission modifier, `valid_until`, and `direct_score_impact`.
  - Expectation Drift now shows nowcast gap, 1d/3d drift, rate odds drift, and prediction odds status.
  - Fed Speech / Policy Text now shows speaker, tone, policy relevance, confidence, and no-BTC-direction boundary.
  - Shock Fast Lane now shows none/shock badge, confirmation, source count, market, microstructure, and rumor fields.
  - Dashboard Summary Widget keeps the Open Watchtower action disabled on the current page.

- `frontend/src/styles.css`
  - Right rail width set to `320px-380px`, sticky on desktop, responsive down on narrow screens.
  - Calendar Mini changed to a 7-column month grid with weekday header, active event highlight, and importance-colored borders.
  - Existing card radius and restrained warning/critical coloring preserved.

## Verification

```text
cd frontend
npm run build
```

Result:

```text
vue-tsc -b && vite build
✓ built
```

## Notes

- Calendar Mini uses live store/API data only; empty fallback is `No events`.
- Importance coloring is derived from existing event row fields such as `importance`, `impact`, or `level`.
- The UI fallback strings are diagnostic only and do not inject mock event rows.
