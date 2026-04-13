# PitWall37 — Shared State

> Last updated: 2026-04-13
> Updated by: Claude (stripped to alien factory)

## Right Now

- **Project stripped down** — removed bridge, session agent, stream overlay, live telemetry, all production/content pipeline
- **Focus is pure:** drive → parse → compare → find tenths → drive again
- 120+ sessions parsed from IBT files into pitwall37.db
- Anti-BS engineering layer: structured recommendations, experiments, driver model
- Workstation UI for post-session review on port 3738
- Lean CLI via `pw.py` for stats, debriefs, driver model, taxonomy

## What Exists

| Component | Status | Notes |
|-----------|--------|-------|
| IBT Parser | Working | Parses 60Hz telemetry, tire data, setup JSON, ride height |
| Setup Model | Working | 120-session validated ranges, change effects, inspection rules |
| Engineering Data | Working | Anti-BS scorecard, experiments, driver model signals |
| Workstation | Working | Post-session review, telemetry viewer, engineer chat |
| Lean CLI | Working | `pw.py` — stats, debrief, driver-model, taxonomy, logging |
| Race Agent | Working | Claude SDK agent with MCP analysis tools |
| Knowledge Base | Partial | Garage constraints, .sto files. Track guides started |
| Brain/Memory | Working | Identity, shared state, context files |

## What Was Removed

- Bridge (GPU box live connection) — not needed for post-session workflow
- Session agent — live agentic loop, unnecessary
- Stream overlay (app/) — no streaming
- pitwall37.py (live API server) — workstation.py covers everything
- All content/production pipeline docs

## Services

| Service | Port | Status |
|---------|------|--------|
| Workstation | 3738 | Running (systemd) |

## Data Pipeline

```
iRacing (Windows GPU) → IBT files
  → sync.sh (rsync over Tailscale)
  → ibt_parser.py (parse binary → SQLite + JSON)
  → pw.py / workstation (review + analysis)
```

## Current Car: Dallara F324 (Super Formula Lights)

- Season: 26S2
- Tracks with data: Interlagos, Road Atlanta, Red Bull Ring, Mugello, Monza
- Sessions in DB: 120+
- All-time PBs: Mugello 97.250s, Road Atlanta 72.799s, Interlagos 84.590s, Red Bull Ring 84.235s

## Key Metrics

- Best lap time per track vs. Garage61 top 10
- Lap time consistency (std dev of valid laps)
- Sector split progression
- Gap to Tamas Simon's times

## What's Next

1. **Alien reference lap ingestion** — get Tamas Simon's IBTs or ghost laps into the DB for direct comparison
2. **Corner-by-corner delta analysis** — where exactly are the tenths? Braking? Min speed? Exit?
3. **Track guides for active season** — built from telemetry data, not generic advice
4. **Drive more, build less** — the system works. Use it.
5. Keep the daily loop tight: drive → debrief → diagnose one limiter → test one variable → grade result
