# PitWall37 Capabilities

## Telemetry Analysis (Post-Session)
- Parse IBT binary files from iRacing (60Hz channel data)
- Extract: speed, throttle, brake, steering, gear, RPM, lap times, sectors
- Tire analysis: surface temps (L/M/R), hot pressures, wear patterns
- Ride height tracking: static, at-speed, min/max/avg per lap
- Fuel consumption tracking per lap
- Corner minimum speed detection
- Braking zone identification (track position, entry speed, speed shed)
- Trail braking percentage
- G-force envelope analysis

## Lap Comparison
- Channel-by-channel overlay of any two laps (same or different sessions)
- Speed delta by track position (10 sections)
- Braking point differences
- Corner speed differences with matching
- Time gained/lost estimation per section
- **NEEDED: alien reference lap ingestion for direct comparison to Tamas Simon**

## Setup Engineering
- Full Dallara F324 parameter knowledge (aero, suspension, diff, brakes)
- Observed safe ranges from 120+ real sessions
- Physics-based change prediction (what happens when you adjust X)
- AeroCalculator output prediction (ride height at speed, downforce/drag)
- Setup comparison (A/B diff with numeric deltas)
- Inspection rule validation (ride height, aero package compatibility)

## Engineering Scorecard (Anti-BS System)
- Structured recommendations: observation → inference → action → validation
- One-variable experiment tracking
- Grading: did the change actually work?
- Driver model: validated strengths and weaknesses from real test results
- Taxonomy: outcomes grouped by focus area across all sessions

## Coaching (Post-Session Only)
- Lap time progression analysis across sessions
- Sector split comparison
- Theoretical best lap calculation (best S1 + best S2 + best S3)
- Consistency analysis (lap time variance, top-5 spread)
- Session debrief generation

## Data Management
- IBT import pipeline: sync → parse → store → analyze
- SQLite database: sessions, laps, tire_snapshots, recommendations, experiments
- Per-lap telemetry JSON storage (60Hz for best lap, 10Hz for others)
- Reference setup library (Majors Garage baselines)

## What We Cannot Do
- Parse .sto binary files (encrypted by iRacing)
- Scrape Garage61 leaderboards automatically (manual for now)
- Model tire degradation over stint length
- Access alien driver telemetry unless we have their IBT files
