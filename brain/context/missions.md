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
- This is part of the private driver-improvement system, not audience packaging

## Mission 3: .sto Parser — BLOCKED (Encrypted)
- ~~Reverse-engineer the iRacing .sto binary format~~
- Findings: .sto setup data is ENCRYPTED by iRacing (confirmed 2026-04-11)
- Structure mapped: [magic:0x03][payload_size][sec1_size][sec2_size][ENCRYPTED params][UTF-16LE notes]
- Section 1: 2896 bytes (F324), ~5 bits/byte entropy, zero repeated blocks
- Nobody has publicly cracked this. setupdelta.com (only known parser) is dead.
- **PIVOTED to SDK bridge approach — read via pyirsdk, human applies changes in garage**

## Mission 4: Setup Editor — REDESIGNED
- ~~Export modified .sto files loadable by iRacing~~ — not possible (encryption)
- New approach: recommendation workflow that suggests changes with specific values
- Driver applies changes manually in iRacing garage
- Bridge detects the change via UpdateCount and validates it was applied correctly
- Still needs: lean recommendation logging, constraint validation display, experiment grading

## Mission 5: Garage61 Leaderboard Assault (ACTIVE)
- Track our times vs. top 10 on Garage61 hotlap boards
- Set specific targets per track
- Track delta to target over sessions
- Use this as the outward narrative for the content/brand journey

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

## Mission 8: PitWall Overlay / Audience Layer (ACTIVE)
- Keep `app/` lean and stream-readable
- Show live lap, telemetry highlights, setup status, and engineer radio snippets
- Make the overlay useful for audience context, not for the driver's primary workflow
- Use it to support streaming when the time is right, not as the main engineering surface

## Backlog
- Weekly content workflow: track writeups, telemetry-backed clips, improvement arcs
- Fuel strategy calculator
- Tire degradation modeling across stint lengths
- Race strategy tool (pit windows, undercut/overcut analysis)
- Public-facing website only after the content loop proves itself
- Racecraft coaching module (overtaking, defending, race starts)
- Auto-start bridge on Windows boot

## Not The Mission
- Turning the dashboard into a standalone product
- Building broad multi-car support right now
- Over-investing in UI at the expense of practice and review volume
