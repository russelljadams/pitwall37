# Mugello GP — Track Guide (Dallara F324 SFL)

> Sources: Track Titan F324 guide, PitWall37 telemetry analysis (8 sessions, 62 laps)
> Last updated: 2026-04-11

## Track Overview
- **Length:** 5.245 km
- **Corners:** 15 turns, mix of high-speed sweeps and technical chicanes
- **Character:** High-speed, flowing circuit. Aero platform stability is critical.
- **Key challenge:** Maintaining rear stability through high-speed direction changes (Casanova-Savelli, Arrabbiata)

## Russell's Data (PitWall37 Telemetry)
- **All-time PB:** 97.250s (2026-04-11, Lap 52)
- **Best avg session:** 97.633s (2026-04-10 11:31, StdDev 0.366s)
- **Most consistent session:** 0.292s StdDev (2026-04-10 13:35)
- **Top speed:** ~243 km/h
- **Sessions analyzed:** 8 with valid laps, 62 total valid laps

## Corner-by-Corner Reference (Track Titan + Telemetry)

### T1 — San Donato (Right)
- **Brake:** ~58m marker
- **Gear:** 3rd
- **Min speed:** ~124 km/h
- **Technique:** Trail brake into the turn, gradually pick up throttle after apex
- **Key:** Smooth steering inputs — the car is coming off a long straight with full aero load, sudden inputs will unsettle the platform

### T2-T3 — Luco / Poggio Secco (Left-Right)
- **Brake:** ~53m before apex
- **Gear:** 2nd
- **Min speed:** ~132 km/h
- **Technique:** Steady throttle through apex, let car stabilize before accelerating
- **Key:** Don't rush the exit — patience here sets up the run to Casanova

### T4-T5 — Casanova-Savelli (Right-Left)
- **Brake:** ~124m before apex
- **Gear:** 3rd
- **Min speed:** ~157 km/h
- **Technique:** Smooth, controlled braking with progressive throttle application
- **Key:** HIGH-SPEED direction change. Aero balance critical here — if the rear feels "floaty," this is where it shows first

### T6-T7 — Arrabbiata 1-2 (Right-Right)
- **Brake:** ~111m before apex
- **Gear:** 4th
- **Min speed:** ~191 km/h
- **Technique:** Trail brake slightly while turning, let car settle before full throttle
- **Key:** Very fast. Commitment corner — you need to trust the aero. Ride height at speed matters most here.

### T8 — Scarperia (Right)
- **Brake:** ~120m before apex
- **Gear:** 5th
- **Min speed:** ~207 km/h
- **Technique:** Smooth, efficient braking with steady throttle through middle section
- **Key:** Highest-speed corner on the track. Minimal braking — more of a lift-and-turn. Aero platform must be stable.

### T9-T10 — Palagio (Left-Right)
- **Brake:** ~154m before apex
- **Gear:** 3rd
- **Min speed:** ~130 km/h
- **Technique:** Find the right balance between braking, turning, and throttle control
- **Key:** Technical section. Trail braking skill matters here — this is where driver technique separates fast from slow.

### T11-T12 — Correntaio / Biondetti (Left-Right)
- Technical chicane section
- **Key:** Minimize time loss, don't overdrive. Clean exit matters for the run to the next section.

### T13-T14-T15 — Bucine (Right-Left-Right)
- Final complex before the main straight
- **Key:** Exit speed is EVERYTHING. This feeds the longest straight. Sacrifice entry to maximize exit. Every km/h lost here costs you all the way down the straight.

## Setup Trends from Data

### What worked (session progression):
| Change | Effect on Lap Time | Effect on Consistency |
|--------|-------------------|----------------------|
| Rear spring 149→166 N/mm | Faster (97.65→97.25) | Bottoming 7.4%→1.8% |
| Rear RH 36.6→41.8mm | Faster | More stable rear |
| Rear pushrod 3→37mm | Faster | Reduced rear float |

### Current fast setup (97.250s lap):
- Front flap: 16 deg
- Rear upper: 17 deg
- Beam wing: 4 deg (low drag)
- Front RH@speed: 14.0mm
- Rear RH@speed: 7.0mm (low but stable with 166 N/mm spring)
- Aero balance: 42.2%
- Heave spring: 140 N/mm
- Torsion bar: 13.87mm OD

### Known issues:
- Rear RH@speed at 7.0mm is still low — see ride_height_bottoming_engineering.md
- Aero balance at 42.2% may be too far forward for high-speed stability
- Driver reports rear feeling "unplanted" — data shows this correlates with higher bottoming %

## Driver Notes
- Corner min speeds improved +16.5 km/h over 8 sessions (137→154 km/h avg)
- Throttle modulation improved significantly (80% binary→70% modulated)
- Steering smoothness improved 22%
- These are primarily DRIVER improvements, not setup (see deep analysis 2026-04-11)
