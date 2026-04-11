# PitWall37 Domain Knowledge Index

## Car
- Dallara F324 (Super Formula Lights) — only car currently supported
- Setup parameter database: `setup_model.py` (OBSERVED_RANGES, CHANGE_EFFECTS)
- Garage constraints: `knowledge/f324_garage_constraints.json`
- Reference setups: `knowledge/majors_garage_sto/` (26 Majors Garage baselines)
- Scraped community setups: `knowledge/scraped_setups.json`

## Tracks
Track-specific guides will live in `brain/domain/tracks/` as they're built.
Current season (26S2) tracks with data:
- Interlagos (multiple sessions, primary practice track)
- Road Atlanta
- Red Bull Ring
- Mugello

## Techniques
Racing technique guides will live in `brain/domain/techniques/`.
To be built from telemetry patterns and coaching sessions.

## Key Physics Concepts
- **Aero balance:** ratio of front-to-rear downforce. Controls understeer/oversteer at speed
- **Ride height at speed:** the real ride height under aero load. Must stay >0mm
- **Mechanical grip vs aero grip:** low-speed corners = mechanical, high-speed = aero
- **Trail braking:** carrying brake pressure past turn-in to rotate the car
- **Tire temp spread:** inside/mid/outside delta reveals camber and pressure issues
- **Hot pressure buildup:** cold→hot pressure delta shows tire work intensity
