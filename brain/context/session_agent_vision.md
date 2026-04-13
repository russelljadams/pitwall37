# PitWall37 — Session Agent & Live Production Vision

> Created: 2026-04-13
> Status: Active development
> Author: Russell Adams + Claude

## The Core Insight

The bridge should not be a dumb data pipe that logs events and fires one-shot Claude calls. The bridge IS the agent's sensory loop. A single persistent agent wakes up when a session starts and lives until it ends, accumulating context with every lap, every setup change, every telemetry tick. It decides what matters. It acts.

And that same data spine powers everything downstream — not just engineering, but a full live production system.

## What's Wrong Now

Current `_proactive_engineer()` in pitwall37.py:
- **Stateless** — every trigger spawns a fresh Claude SDK call with zero memory of prior laps
- **Hardcoded triggers** — Python if-statements decide when to fire (3 slower laps = degradation, PB = celebrate). The agent should decide, not the code.
- **Fire-and-forget** — no accumulated session model, no running narrative
- **Text-only output** — can only broadcast text to dashboard. Can't update overlays, push notifications, build reports, or take real actions.
- **N cold starts per session** — each proactive call is a separate Claude invocation. Expensive, slow, no continuity.

## The Session Agent (The Spine)

### Lifecycle

```
Bridge connects
  → Session detected (car + track)
    → spawn_session_agent()
      → Agent runs for entire session duration
        → Consumes events from an async queue
        → Maintains accumulated session state
        → Decides when to think, speak, or act
      → Session ends or bridge disconnects
    → Agent produces final session report
  → Agent dies
```

### Session State (accumulated, not reset per event)

```python
session_state = {
    # Identity
    "car": "Dallara F324",
    "track": "Interlagos",
    "track_config": "Grand Prix",
    "started_at": "2026-04-13T22:00:00Z",

    # Laps (every lap, growing list)
    "laps": [
        {"num": 1, "time": 84.932, "sectors": [28.1, 29.4, 27.4], "valid": True, "fuel_used": 1.82},
        {"num": 2, "time": 84.711, "sectors": [27.9, 29.3, 27.5], "valid": True, "fuel_used": 1.80},
        # ...
    ],

    # Running stats
    "best_lap": 84.590,
    "best_sectors": [27.6, 29.0, 27.2],
    "session_best": 84.711,
    "pace_trend": "improving",  # improving / stable / degrading
    "consistency": 0.34,  # std dev of last 5 valid laps

    # Setup
    "current_setup": { ... },
    "setup_changes": [
        {"lap": 15, "what_changed": "rear_wing +1 click", "before": {...}, "after": {...}},
    ],

    # Agent's running notes (its own internal narrative)
    "engineer_notes": [
        {"lap": 5, "note": "S2 is the limiter — losing 0.4s to track PB there"},
        {"lap": 12, "note": "Setup change to rear wing seems to have helped rotation in T6-T7"},
    ],

    # Reference data loaded at session start
    "track_pb": 84.590,
    "alien_reference": 83.7,  # Tamas Simon or whoever
    "driver_model": { ... },  # strengths/weaknesses from engineering_data
}
```

### Event Queue

The bridge handler in pitwall37.py stops calling `_proactive_engineer()` directly. Instead:

```python
# Bridge handler pushes events to the session agent's queue
await session_agent_queue.put({
    "type": "lap_complete",
    "data": { "lap_number": 5, "lap_time": 84.711, ... },
    "ts": time.time(),
})
```

The session agent consumes from this queue in its own loop:

```python
async def session_agent_loop(queue, session_state):
    while True:
        event = await queue.get()
        session_state = update_state(session_state, event)

        # Agent DECIDES whether this event warrants a response
        if should_think(session_state, event):
            response = await think(session_state, event)
            await dispatch_actions(response)
```

### Agent Decision Making

The agent doesn't respond to every event. It has judgment:

- **Lap complete, nothing interesting:** silence. Maybe update the overlay lap counter.
- **Lap complete, new PB:** "That's a 84.4! New PB. You found two tenths in S2 — the line change through Ferradura is working."
- **3 laps trending slower:** "Pace is dropping. Last three: 84.9, 85.1, 85.3. Tires going off or losing focus? Your S3 braking is getting later each lap."
- **Setup change detected:** Diffs against previous, checks constraints, gives opinion.
- **Fuel below threshold:** Calculates remaining laps at current consumption, advises.
- **Periodic (every 10 laps or so):** Mini-debrief. "You've done 15 laps. Best: 84.4. Consistency: 0.28s. Main limiter is still S2 entry. Recommend trying later braking into T4."

## The Production Layer (Consumers on the Spine)

The session agent is the brain. Multiple downstream consumers tap into it:

### 1. Engineer (Private Channel — Driver Only)

- Talks directly to the driver via earpiece / phone notification / private overlay panel
- Technical, concise, data-backed
- Setup recommendations, driving coaching, strategy calls
- Tone: professional F1 race engineer on the radio

Example: "Russell, you're losing two tenths in S2 on the last three laps. Rear is sliding on exit at T6. Consider one click more rear wing."

### 2. Commentator (Public Channel — Stream Audience)

- Talks to the stream audience via overlay text + TTS voice
- Explains what's happening in accessible terms
- Builds narrative and drama
- Tone: enthusiastic but knowledgeable motorsport commentator

Example: "And gh0st is starting to push now — that was a 1:24.4, his best of the session! He's been methodically working through that second sector and it's paying off. Still eight tenths off the alien pace but the trajectory is there."

### 3. Analyst (Post-Session / Desk Segments)

- Generates pre-session and post-session "desk" segments
- Summarizes the session narrative, key moments, progression
- Produces structured content for VODs, social media, clips

Pre-session example: "Welcome back to PitWall37 Live. Tonight Russell is heading to Interlagos for his fourth session this week. Coming in, his best is a 1:24.8 — still nearly a second off Tamas Simon's benchmark. Last session he made progress in sector 2 but was still losing time through the Senna S. Let's see if tonight he cracks the 1:24 barrier."

Post-session example: "That's a wrap on tonight's session. 47 laps at Interlagos. PB improved from 1:24.8 to 1:24.4. The breakthrough came on lap 23 after a rear wing adjustment — he carried 6km/h more through Ferradura and never looked back. Gap to the alien is now 0.7s. Tomorrow's target: find the remaining time in S1 braking zones."

### 4. Overlay Controller

- Updates stream overlay in real-time based on agent decisions
- Lap time ticker, sector comparisons, gap to alien, tire status
- Can trigger visual effects: PB celebration, "pace alert" warning
- Drives what the audience sees without manual OBS scene switching

### 5. Highlight Detector

- Flags moments worth clipping: PBs, dramatic recoveries, spins, close battles
- Marks timestamps for post-session clip generation
- Could auto-generate short-form content with commentary overlay

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    iRacing (GPU Box)                     │
│                                                         │
│  pyirsdk → bridge.py → WebSocket                       │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│                  pitwall37.py (Cloud)                     │
│                                                          │
│  /ws/bridge ──→ event_queue ──→ SESSION AGENT            │
│                                     │                    │
│                    ┌────────────────┼────────────────┐   │
│                    │                │                │   │
│              ┌─────▼─────┐  ┌──────▼──────┐  ┌─────▼─┐ │
│              │ ENGINEER  │  │COMMENTATOR  │  │OVERLAY│ │
│              │ (private) │  │ (stream)    │  │CONTROL│ │
│              └─────┬─────┘  └──────┬──────┘  └───┬───┘ │
│                    │               │             │     │
│              ┌─────▼─────┐  ┌──────▼──────┐     │     │
│              │phone push │  │  TTS voice  │     │     │
│              │private UI │  │stream overlay│     │     │
│              └───────────┘  └─────────────┘     │     │
│                                                  │     │
│  /ws/live ◄─────────────────────────────────────┘     │
│                                                        │
│  POST-SESSION:                                         │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ ANALYST  │  │  HIGHLIGHTS  │  │  SESSION REPORT  │  │
│  │desk segs │  │  clip marks  │  │  auto-generated  │  │
│  └──────────┘  └──────────────┘  └─────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Why This Works (Not Fantasy)

1. **The data pipeline already exists.** Bridge → WebSocket → parsed events → database. Months of work done.
2. **The overlay already exists.** React frontend on port 3737 with live WebSocket. Just needs new message types.
3. **120+ sessions of historical context.** The analyst and commentator aren't making stuff up — they query real data.
4. **The hardest part is the session agent.** Everything else is prompt engineering + plumbing. Different personas consuming the same accumulated context.
5. **Incremental delivery.** Each layer is independently useful. The engineer alone is a massive upgrade. The commentator adds stream value. The analyst adds content production.

## Build Order

### Phase 1: Session Agent (The Spine) ← START HERE
- `session_agent.py` — persistent agent loop with event queue and accumulated state
- Rewire `pitwall37.py` to feed events to the agent instead of `_proactive_engineer()`
- Agent decides when to speak, what to analyze, when to stay quiet
- Actions: broadcast to dashboard, log events, build running session report
- Load reference data at session start (track PB, alien times, driver model)

### Phase 2: Engineer Upgrade
- Engineer persona consumes session agent context
- Push notifications to phone (Pushover / ntfy.sh / similar)
- Private overlay panel for driver-only info
- Setup change analysis with session context (not stateless)

### Phase 3: Stream Commentator
- Second persona with audience-facing voice
- New overlay panel or mode for commentary text
- TTS integration (ElevenLabs / OpenAI TTS)
- Play-by-play + color commentary style

### Phase 4: Desk Segments & Analyst
- Pre-session briefing generated from historical data
- Post-session wrap-up from accumulated session state
- Content generation for social/VOD

### Phase 5: Highlight Detection & Clip Generation
- Timestamp marking during session
- Post-session clip extraction
- Auto-generated commentary overlays on clips

## Content Model: Weekly YouTube, Not Live Streaming

> Updated 2026-04-13: Russell doesn't stream live. The production model is weekly YouTube videos.

This actually makes things **better**, not worse. No live latency constraints. Full creative control. Post-production is where AI shines.

### How Weekly YouTube Changes the Architecture

**During the session (still real-time):**
- Session agent runs exactly as designed — accumulating context, making engineer calls
- Everything is logged to the database: laps, agent notes, setup changes, engineer commentary
- The session produces a complete **session narrative** as a byproduct

**After the session (post-production):**
- The Analyst persona reviews the session narrative and generates:
  - A scripted "show" — intro, key moments, analysis, conclusion
  - Commentator lines for key moments (keyed to lap numbers / timestamps)
  - Desk segment scripts (pre-race briefing, post-race analysis)
- AI-generated visuals for the "anchors" (options below)
- Voice: TTS generates the commentary audio
- Video: iRacing replay footage + overlay data + AI anchor segments
- Editing: Assembled into a cohesive YouTube episode

### AI Anchor / Commentator Visual Options

Russell isn't artsy and doesn't stream — so the "ESPN experience" needs AI-generated visuals:

1. **AI avatars / talking heads** — Tools like HeyGen, Synthesia, or D-ID can generate realistic talking head videos from a script + voice. You design the "anchor" character once, then generate new clips per episode.
2. **Animated overlays** — Skip the talking head entirely. Use motion graphics over replay footage: data visualizations, sector comparisons, telemetry traces. The "commentary" is a voiceover, not a face.
3. **Stylized characters** — Use AI image generation to create a consistent character design for the "PitWall37 broadcast team." Not photorealistic — more like illustrated/stylized sports graphics.
4. **Screen recording + data overlay** — Simplest: iRacing replay with PitWall37 overlay showing live data, agent commentary as text/voice, and post-session analysis segments.

The MVP is probably option 4 (replay + overlay + voiceover). The premium version adds AI anchors for the desk segments.

### Weekly Episode Structure (Example)

```
[COLD OPEN — 30s]
AI Commentator: "Last week, gh0st was 0.8 seconds off the alien pace at Interlagos.
Tonight, he's going to try to crack the 1:24 barrier with a new rear wing setup."

[SESSION FOOTAGE — 10-15 min]
iRacing replay footage with:
- PitWall37 overlay (lap times, sector splits, gap to alien)
- Engineer radio calls at key moments (voiced by TTS)
- Data visualizations at setup changes and PB moments

[ANALYSIS SEGMENT — 3-5 min]
AI Analyst: "Looking at the data, the breakthrough came on lap 23..."
Telemetry comparison graphics, sector breakdowns

[CLOSING — 1 min]
AI Commentator: "Gap to the alien is now 0.5 seconds. Next week: Mugello."
```

### What We Need to Build for This

1. **Session narrative export** — `pw.py export-narrative <session_id>` that produces a structured JSON/markdown of the session story: key moments, agent calls, lap progression, setup changes
2. **Script generator** — Takes the narrative and produces a show script with commentator/analyst lines, timestamps for replay footage, data visualization cues
3. **TTS pipeline** — Generate voice audio from scripts (OpenAI TTS, ElevenLabs)
4. **Replay + overlay capture** — Need to figure out how to record iRacing replays with the overlay (OBS probably)
5. **Video assembly** — Probably a Python script using moviepy or ffmpeg to stitch together replay footage, overlay, voiceover, and graphics

Steps 1-3 are all prompt engineering + plumbing. Steps 4-5 are video production tooling.

## Open Questions

- **Claude SDK session persistence:** Can we keep a single Claude conversation alive for an entire session (potentially hours), or do we need to manage context ourselves and make periodic calls with accumulated state?
- **Cost management:** Proactive calls every lap could get expensive. Need smart batching — agent decides when to think, not every event triggers a Claude call.
- **Phone push service:** ntfy.sh is simple and self-hostable. Pushover is polished. Which fits better?
- **AI avatar tooling:** HeyGen vs Synthesia vs D-ID for anchor segments — or skip faces entirely and go voiceover-only?
- **TTS voice selection:** Should the engineer, commentator, and analyst have distinct voices? (Yes.)
- **iRacing replay recording:** Can we automate OBS scene switching + replay capture? Or is manual recording fine for weekly cadence?
- **Multi-agent or multi-persona?** Is the commentator a separate Claude call with different system prompt, or the same agent wearing a different hat? Separate is cleaner but costs more.

## The Tagline

> "Greatest Race Car Driver Ever. He was built with Claude."

And now the audience gets to watch it happen, one episode at a time.
