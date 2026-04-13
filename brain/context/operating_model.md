# PitWall37 Operating Model

## Purpose

PitWall37 is not a product.

It exists to do two jobs:

1. Help Russell Adams get faster, every day.
2. Turn the improvement process into content, story, and eventually brand.

Everything in the repo must support one of those two jobs.

## Project Split

### 1. Driver System — Core

Internal tools used to improve pace:

- `data/` — evidence layer
- `ibt_parser.py` — ingest raw telemetry
- `pitwall37.db` — long-term memory of sessions and laps
- `engineering_data.py` — recommendations, experiments, driver model
- `setup_model.py` — deterministic setup guardrails
- `brain/` and `knowledge/` — track notes, engineering knowledge, research library
- `workstation/` — private review room for the driver
- Claude/Codex chat — primary interface for debriefs, planning, and analysis

This is the engine.

### 2. Audience Layer — Secondary

Public-facing pieces that help people follow the journey:

- `pitwall37.py` live APIs
- `app/` stream overlay
- any future clips, writeups, leaderboard updates, stream callouts, and web summaries

This is packaging, not the engine.

## Daily Driver Workflow

This is the default daily loop.

1. Drive
- Run a focused baseline stint.
- Use one intent per run: braking, release, minimum speed, exits, or one setup variable.

2. Debrief
- Pull the session summary immediately after the stint.
- Check best lap, median valid lap, top-5 spread, and gap to track best.

3. Diagnose
- Identify one biggest limiter only.
- Decide whether it is primarily:
  - driving
  - setup
  - uncertainty / not enough evidence

4. Plan One Test
- One change only.
- Log the recommendation with:
  - observation
  - inference
  - confidence
  - action
  - validation

5. Re-run
- Test the single variable over a short push set.
- Avoid changing more than one thing at a time unless the session is exploratory.

6. Grade
- Mark the recommendation:
  - improved
  - no change
  - worse
  - mixed
- Log the experiment outcome.

7. Capture
- Save any real learning to:
  - track guide
  - driver model
  - setup knowledge

## Weekly Content Workflow

The content is the real improvement process, not fake hype around it.

1. Pick the weekly narrative
- new official track
- revenge on a weakness track
- setup experiment week
- leaderboard assault week

2. Capture the arc
- where you started
- what the car / telemetry showed
- what one or two key fixes were
- whether they worked
- where you ended

3. Publish the proof
- clip
- stream segment
- thread/post
- weekly writeup

4. Archive the lesson
- update track notes
- update engineering log
- update brand story only from real data

## Scope Filter

Before building anything, ask:

Does this help me:
- practice better
- review faster
- remember real lessons
- turn improvement into content

If not, it waits.

## Now / Later / Not Now

### Now

- debriefs
- lap comparison
- recommendation logging
- experiment tracking
- driver model
- track notes
- simple overlay for stream readability

### Later

- richer overlay polish
- automated content summaries
- public website
- audience interaction features
- expanded hardware/racecraft modules

### Not Now

- trying to turn the dashboard into a standalone product
- building broad multi-car support
- over-designing UI
- speculative features with no direct training or content value

## Default Tooling Preference

Primary interface:

- Claude/Codex
- small CLI tools
- focused dashboard views when visually useful

Secondary:

- full workstation UI
- stream overlay polish

The fastest path is terminal/chat-first with the UI supporting, not dictating, the workflow.
