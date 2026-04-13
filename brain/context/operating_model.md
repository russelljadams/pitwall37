# PitWall37 Operating Model

## Purpose

Make Russell Adams faster. That's it.

## Daily Loop

1. **Drive** — focused stint, one intent per run (braking, release, min speed, exits, or one setup variable)
2. **Sync** — `bash sync.sh`
3. **Parse** — `python3 ibt_parser.py`
4. **Debrief** — `python3 pw.py debrief <session_id>` — best lap, median, spread, gap to PB
5. **Diagnose** — identify the single biggest limiter. Is it driving or setup?
6. **Compare** — overlay against your PB or an alien reference lap. Find where the time lives.
7. **Plan one test** — one change only. Log it: observation, inference, action, validation plan.
8. **Drive again** — test the single variable
9. **Grade** — improved / no change / worse / mixed. Log the result.
10. **Capture** — save any real learning to track guide or driver model

## Tooling

- **Primary:** `pw.py` CLI + Claude chat for analysis
- **Secondary:** workstation UI for telemetry overlay and setup review
- **Data:** IBT files → parser → SQLite → analysis tools

## Scope Filter

Before building anything, ask: does this help me drive faster laps?

If not, it waits.
