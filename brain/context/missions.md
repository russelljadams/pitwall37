# Active Missions

## Mission 1: Brain Bootstrap — COMPLETE
- ~~Build the full race agent infrastructure~~
- ~~Memory, identity, shared state, project instructions~~
- ~~Make PitWall37 sessions persistent — no context lost between conversations~~
- Completed 2026-04-11

## Mission 2: Track Mastery — 26S2 Calendar (ACTIVE)
- Build track guides for every track on the current season calendar
- Each guide: corner-by-corner notes, setup tendencies, braking references, target times
- Populate from telemetry data + engineer analysis
- Tracks with data: Interlagos, Road Atlanta, Red Bull Ring, Mugello, Monza

## Mission 3: .sto Parser — BLOCKED (Encrypted)
- ~~Reverse-engineer the iRacing .sto binary format~~
- Findings: .sto setup data is ENCRYPTED by iRacing (confirmed 2026-04-11)
- Structure mapped: [magic:0x03][payload_size][sec1_size][sec2_size][ENCRYPTED params][UTF-16LE notes]
- Section 1: 2896 bytes (F324), ~5 bits/byte entropy, zero repeated blocks
- Nobody has publicly cracked this. setupdelta.com (only known parser) is dead.
- **PIVOTED to SDK bridge approach — read via pyirsdk, human applies changes in garage**

## Mission 4: Setup Editor — REDESIGNED
- ~~Export modified .sto files loadable by iRacing~~ — not possible (encryption)
- New approach: web UI that RECOMMENDS changes with specific values
- Driver applies changes manually in iRacing garage
- Bridge detects the change via UpdateCount and validates it was applied correctly
- Still needs: slider-based parameter editing UI, constraint validation display

## Mission 5: Garage61 Leaderboard Assault (QUEUED)
- Track our times vs. top 10 on Garage61 hotlap boards
- Set specific targets per track
- Track delta to target over sessions

## Mission 6: GPU Box Bridge — COMPLETE
- ~~Build bridge connecting iRacing to PitWall37 via WebSocket~~
- ~~Deploy to Windows GPU box~~
- ~~Test live connection~~
- Deployed to C:\pitwall37\bridge.py on GPU box (100.73.76.109)
- Successfully streaming: telemetry (10Hz), setup changes, lap completions, state events
- Pit commands (fuel, tire pressures) tested and working
- Completed 2026-04-11

## Mission 7: Hardware Awareness (ACTIVE)
- Sim rig: MOZA R3 wheelbase, Logitech load cell pedals (budget)
- MOZA Pit House for FFB tuning
- Still need: document FFB settings, pedal curves, create paired profiles

## Mission 8: Trading Paints / Livery Design (QUEUED)
- Interface with Trading Paints for custom livery management
- Bridge already supports texture reload via SDK broadcast
- Explore AI-generated paint scheme creation
- Team branding for gh0st / a1i3n37

## Backlog
- Fuel strategy calculator
- Tire degradation modeling across stint lengths
- Race strategy tool (pit windows, undercut/overcut analysis)
- Multi-car support (expand beyond F324)
- Public setup sharing site (separate project from setup editor)
- Racecraft coaching module (overtaking, defending, race starts)
- Series progression advisor (what to drive, when to move up)
- Zero-to-pro onboarding flow for new drivers
- Auto-start bridge on Windows boot
- Live telemetry → Claude engineer pipeline (real-time coaching while driving)
