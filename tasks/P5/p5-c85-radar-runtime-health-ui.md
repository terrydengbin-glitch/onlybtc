# P5-C85 Radar Runtime Health UI

Status: DONE

## Background

After the radar chain becomes cadence-based, users need to see module freshness, daemon health, and whether a module is allowed to participate in confirmed signals.

## Goal

Add Radar Runtime visibility inside the current UI framework without breaking dashboard, radar, topology, or event window pages.

## UI Scope

```text
Dashboard top status:
  radar runtime daemon health
  heartbeat age
  watchdog state

BTC center card:
  runtime freshness badge
  fresh / stale / blocked module counts

14 radar cards:
  last_success_at
  age_sec
  freshness_state
  participates_in_confirmed_signal

Settings / Run area:
  Radar Runtime run once
  pause / resume if supported
```

## Boundaries

1. UI reads FastAPI / SQLite summaries only.
2. UI does not consume audit HTML files as business data.
3. Radar Runtime run once is separate from P4.5 full-chain run once.
4. Event Window remains an independent overlay.

## DoD

1. UI shows daemon health: healthy, degraded, stale, failed, paused_by_user.
2. UI shows each module freshness_state, last_success_at, ttl_sec, and age_sec.
3. Stale modules have clear visual downgrade.
4. BTC center card shows fresh / stale / blocked module counts.
5. Radar Runtime run once button calls the independent API.
6. Event Window floating overlay and subpage are not broken.
7. npm run build passes.
