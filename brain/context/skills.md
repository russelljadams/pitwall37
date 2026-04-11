# PitWall37 Agent Capabilities

## Live Session (via Bridge) — NEW
- Real-time telemetry streaming from iRacing at 10Hz (speed, RPM, throttle, brake, G-forces, ride height)
- Live setup reading — full car setup pulled from iRacing shared memory
- Setup change detection — instant notification when driver modifies setup in garage
- Lap completion tracking — time, fuel, automatic notification
- State transition detection — garage/track/off-track events
- Pit stop automation — set fuel amount and tire pressures via SDK broadcast
- Telemetry recording control — start/stop IBT recording remotely
- Texture reload — trigger Trading Paints livery refresh

## Telemetry Analysis (Batch)
- Parse IBT binary files from iRacing (60Hz channel data)
- Extract: speed, throttle, brake, steering, gear, RPM, lap times, sectors
- Tire analysis: surface temps (L/M/R), hot pressures, wear patterns
- Ride height tracking: static, at-speed, min/max/avg per lap
- Fuel consumption tracking per lap

## Setup Engineering
- Full Dallara F324 parameter knowledge (aero, suspension, diff, brakes)
- Observed safe ranges from 120+ real sessions
- Physics-based change prediction (what happens when you adjust X)
- AeroCalculator output prediction (ride height at speed, downforce/drag trim)
- Setup comparison (A/B diff with numeric deltas)
- Inspection rule validation (ride height, aero package compatibility)
- Cross-reference live setup against historical database

## Coaching
- Lap time progression analysis across sessions
- Sector split comparison (find where time lives)
- Theoretical best lap calculation (best S1 + best S2 + best S3)
- Consistency analysis (lap time variance)
- Driving technique diagnosis from telemetry patterns
- Session debrief generation

## Data Management
- Session import pipeline: sync IBT → parse → store → analyze
- SQLite database with sessions, laps, tire_snapshots
- Per-lap telemetry JSON storage
- Reference setup library (Majors Garage baselines)

## Brain / Memory
- Persistent identity and project state across conversations
- Operator profile, communication preferences, driving context
- Historical findings preserved (e.g., tire data rules, .sto encryption)
- Mission tracking and progress state

## What We CANNOT Do (yet)
- Write setup changes directly to iRacing (SDK is read-only for setups)
- Parse/write .sto binary files (encrypted by iRacing)
- Scrape Garage61 leaderboards automatically
- Model tire degradation over stint length
- Calculate race fuel strategy with pit windows
- Generate liveries/paint schemes
- Tune MOZA Pit House FFB profiles remotely
