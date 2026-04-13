# PitWall37 — State

> Updated: 2026-04-13

## What Exists

- `ibt_parser.py` — IBT binary → SQLite + JSON telemetry
- `setup_model.py` — setup validation against 120+ sessions of observed ranges
- `engineering_data.py` — recommendations, experiments, driver model
- `race_agent.py` — Claude agent with MCP analysis tools
- `sync.sh` — rsync IBTs from GPU box

## Data

- 52 Russell sessions in DB (Interlagos, Road Atlanta, Red Bull Ring, Mugello)
- 8 Tamas Simon sessions in DB (same 4 tracks, real telemetry)
- 3,061 clean SFL laps scraped from Garage61 (16 tracks, full history)
- Garage61 full history JSON saved locally
- Tamas's setups (.sto) for all 4 current tracks

## Gaps to Tamas

| Track | Russell | Tamas | Gap |
|-------|---------|-------|-----|
| Interlagos | 86.752s | 84.590s | +2.162s |
| Road Atlanta | 72.799s | 71.360s | +1.439s |
| Red Bull Ring | 84.235s | 82.312s | +1.923s |
| Mugello | 97.000s | 95.170s | +1.830s |

## Workflow

```
1. Drive (active reset practice)
2. bash sync.sh && python3 ibt_parser.py
3. Talk to Claude — compare laps, find where the time is
```
