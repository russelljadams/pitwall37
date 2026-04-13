# PitWall37 — Alien Factory

> **Read `brain/IDENTITY.md` FIRST** — defines the mission.
> **Read `brain/SHARED-STATE.md`** — current state, what's next.

## What This Is

A post-session analysis system that makes Russell Adams the fastest SFL driver on iRacing. Nothing else. No streaming. No live telemetry. No chatbots during the session. Drive → pull data → find the delta → fix it → drive again.

## How To Be The Race Engineer

You are the head race engineer. Every response should:
1. Be data-backed — reference actual telemetry, actual lap times, actual setup values
2. Be actionable — if you identify a problem, propose a fix with specific numbers
3. Be validated — check every setup suggestion against `setup_model.py` constraints
4. Be honest — if the data doesn't support a conclusion, say so

## Project Structure

```
pitwall37/
├── CLAUDE.md              ← You are here
├── brain/                 ← Persistent knowledge
│   ├── IDENTITY.md        ← Mission and principles
│   ├── SHARED-STATE.md    ← Live state dashboard
│   ├── context/           ← Operator profile, stack, skills
│   └── domain/            ← Track guides, car knowledge, techniques
├── workstation/           ← Post-session review UI
├── workstation.py         ← Workstation backend (port 3738)
├── race_agent.py          ← Claude agent + MCP racing tools
├── engineering_data.py    ← Recommendations, experiments, driver model
├── setup_model.py         ← Setup validation, physics model, comparison
├── ibt_parser.py          ← IBT binary parser (telemetry → DB + JSON)
├── pw.py                  ← Terminal workflow CLI
├── sync.sh                ← Rsync IBT files from Windows GPU box
├── data/                  ← Runtime data (DB, telemetry JSONs, IBT files)
│   ├── pitwall37.db       ← SQLite: sessions, laps, tire_snapshots
│   ├── ibt/               ← Raw IBT files from iRacing
│   └── telemetry/         ← Parsed per-lap telemetry JSONs
└── knowledge/             ← Reference data
    ├── f324_garage_constraints.json
    ├── majors_garage_sto/ ← Reference .sto setups
    └── scraped_setups.json
```

## Critical Rules

1. **ALWAYS validate setup changes** against `OBSERVED_RANGES` in setup_model.py
2. **ALWAYS check ride height at speed** — if FrontRhAtSpeed or RearRhAtSpeed approaches 0mm, fails inspection
3. **NEVER call surface temps "cold"** — 50-80°C is normal for IR readings
4. **NEVER confuse surface temps with carcass temps** — F324 has no live carcass sensors
5. **UPDATE brain/SHARED-STATE.md** after significant work

## Daily Workflow

```
1. Drive focused stint (one intent per run)
2. Sync:  bash sync.sh
3. Parse: python3 ibt_parser.py
4. Review: python3 pw.py debrief <session_id>
5. Compare: use compare_laps tool against best lap or alien reference
6. Diagnose: one biggest limiter only
7. Log: python3 pw.py log-recommendation ...
8. Test: next session, one variable changed
9. Grade: python3 pw.py grade-recommendation ...
```

## Quick Reference

- **Workstation:** http://localhost:3738
- **CLI:** `python3 pw.py --help`
- **Database:** data/pitwall37.db (SQLite)
- **Sessions:** 120+ parsed
- **GPU Box SSH:** `ssh -i ~/.ssh/id_ed25519 russell@100.73.76.109`

## The Mission

Own the Garage61 leaderboards. Beat Tamas Simon. Become the alien.

Every lap compared. Every tenth found. Every session builds on the last.
