# PitWall37 — Shared State

> Last updated: 2026-04-13
> Updated by: Claude (session agent + production vision)

## Right Now

- **Session agent is LIVE** — persistent agentic loop replaces old stateless `_proactive_engineer()`
- Agent accumulates full session context: laps, setup changes, pace trends, fuel, consistency
- Agent DECIDES when to speak (PBs, degradation, stint debriefs, periodic check-ins) — no hardcoded triggers
- Generates session-end debrief when bridge disconnects
- New endpoint: `/api/session-agent/status` — check agent state in real-time
- Full vision doc at `brain/context/session_agent_vision.md` — covers agent spine + production layer
- Production model: **weekly YouTube episodes**, not live streaming
- Live bridge TESTED AND WORKING — streaming real-time telemetry from iRacing on GPU box
- 120 sessions parsed from IBT files into pitwall37.db
- Anti-BS engineering layer: structured recommendations, experiments, driver model, taxonomy summaries
- Lean CLI via `pw.py` for stats, debriefs, driver model, and taxonomy

## What Exists

| Component | Status | Notes |
|-----------|--------|-------|
| IBT Parser | Working | Parses 60Hz telemetry, tire data, setup JSON, ride height |
| Setup Model | Working | 118-session validated ranges, change effects, inspection rules |
| Race Engineer | **Rebuilt** | Claude Code SDK agent with MCP tools, WebSearch, Bash, Read/Write |
| Workstation | Working | Private session review, telemetry viewer, engineer chat, comparison mode |
| Stream Overlay | Working | Public-facing live overlay on port 3737 |
| Lean CLI | **NEW** | `pw.py` supports terminal-first stats/debrief/model workflow |
| PitWall37 API | Working | FastAPI on port 3737, sessions/laps/telemetry/setup endpoints |
| Knowledge Base | Partial | Garage constraints JSON, .sto files. No track guides yet |
| Brain/Memory | Working | IDENTITY, SHARED-STATE, context files, Claude memory system |
| **Bridge (GPU)** | **LIVE** | **Deployed to C:\pitwall37\bridge.py, tested, streaming from iRacing** |
| **Bridge Server** | **LIVE** | **/ws/bridge, /ws/live, /api/bridge/* endpoints on pitwall37.py** |
| .sto Parser | BLOCKED | **Binary is ENCRYPTED by iRacing — confirmed via reverse engineering** |
| Setup Editor | BLOCKED | .sto encryption is permanent — pivoting to SDK-based approach |

## Services

| Service | Port | Status | Auth |
|---------|------|--------|------|
| PitWall37 Stream Overlay | 3737 | Running (systemd) | None |
| PitWall37 Workstation | 3738 | Running (systemd) | None |
| Bridge (GPU) | N/A | Connects outbound to ws://100.85.186.91:3737/ws/bridge | None |

## Data Pipeline

**Batch (post-session):**
```
iRacing (Windows GPU) → IBT files → sync.sh (rsync over Tailscale) → ibt_parser.py → pitwall37.db → Dashboard
```

**Live (during session) — NEW:**
```
iRacing → pyirsdk shared memory → bridge.py → WebSocket → PitWall37 → /ws/live → Dashboard
                                                            ↓
                                              /api/bridge/pit → pit commands back to iRacing
```

## Current Car: Dallara F324 (Super Formula Lights)

- Season: 26S2 (Season 2, 2026)
- Primary tracks practiced: Interlagos, Road Atlanta, Red Bull Ring, Mugello
- Sessions in DB: 120+
- Reference setups: Majors Garage baseline + Luis Nunez baselines
- All-time PB: Mugello 97.303s, Road Atlanta 72.799s, Interlagos 84.590s, Red Bull Ring 84.235s

## Key Metrics to Track

- Best lap time per track (vs. Garage61 leaderboard)
- Lap time consistency (std dev of valid laps)
- Sector split progression over sessions
- Setup iteration count per track

## .sto Format — Research Findings (2026-04-11)

**The .sto setup parameter data is ENCRYPTED by iRacing.**
- Structure: `[magic:0x03][payload_size][sec1_size][sec2_size][ENCRYPTED params][UTF-16LE notes]`
- Section 1 (2896 bytes for F324) contains 724 x 4-byte encrypted values
- Zero repeated blocks, ~5 bits/byte entropy, no recognizable patterns
- Nobody has publicly cracked this — setupdelta.com (only known parser) is dead
- The iRacing SDK is READ-ONLY for setups — no broadcast messages exist for garage changes
- **Pivot:** Use live SDK bridge for reading + human-in-the-loop for writing

## What's Next

1. **Drive with the session agent live** — first real test of the persistent agentic loop
2. Build the **session narrative export** (`pw.py export-narrative <session_id>`) for YouTube episodes
3. Build the **script generator** persona — takes session narrative, produces show script
4. Set up **TTS pipeline** — distinct voices for engineer, commentator, analyst
5. **First YouTube episode** — iRacing replay + PitWall37 overlay + TTS voiceover
6. Keep daily workflow lean: drive → debrief → diagnose one limiter → test one variable → grade result
7. Track Garage61 target deltas per circuit
8. Build track guides for the active season
