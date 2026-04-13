# PitWall37

> **Read `brain/IDENTITY.md`** — what we are and how we operate.

## What This Is

Russell and AI learning how to go faster. Data aggregation, knowledge sourcing, and content creation. Not a race engineer. Not a coach.

## What's Here

```
pitwall37/
├── brain/IDENTITY.md      ← What we are
├── brain/SHARED-STATE.md   ← Current data state
├── brain/domain/           ← Track and car knowledge
├── ibt_parser.py           ← IBT binary → SQLite + JSON
├── setup_model.py          ← Setup parameter validation
├── engineering_data.py     ← Recommendations, experiments, driver model
├── race_agent.py           ← Claude agent + MCP tools
├── sync.sh                 ← Rsync IBTs from GPU box
├── knowledge/              ← Reference setups, garage constraints
└── data/                   ← DB, telemetry, Garage61 scrape, Tamas's files
```

## Rules

1. Don't guess. Present data with sources.
2. IBT data is truth. Garage61 is approximate. Flag which is which.
3. No unsolicited driving advice. Russell interprets the data.
4. Aggregate from everywhere — books, research, telemetry, forums, fast drivers.
5. Content should teach. No drama. No inflation.

## Data Pipeline

```
Drive → bash sync.sh → python3 ibt_parser.py → data is in the DB → talk to Claude
```

## Quick Reference

- **Database:** data/pitwall37.db
- **GPU Box:** `ssh -i ~/.ssh/id_ed25519 russell@100.73.76.109`
- **Garage61 cookies:** Firefox on GPU box, steal with sqlite3
