# PitWall37 — Shared State

> Last updated: 2026-04-11
> Updated by: Claude (brain bootstrap + bridge deployment session)

## Right Now

- Brain system fully operational (IDENTITY, SHARED-STATE, context, memory)
- Live bridge TESTED AND WORKING — streaming real-time telemetry from iRacing on GPU box
- Successfully read live setup + telemetry from Mugello session (SFL, 97.846s best this session)
- 120 sessions parsed from IBT files into pitwall37.db (was 118, grew during session)
- PitWall37 dashboard running as systemd service on port 3737
- .sto binary format reverse-engineered: ENCRYPTED by iRacing, pivot to SDK bridge complete

## What Exists

| Component | Status | Notes |
|-----------|--------|-------|
| IBT Parser | Working | Parses 60Hz telemetry, tire data, setup JSON, ride height |
| Setup Model | Working | 118-session validated ranges, change effects, inspection rules |
| Race Engineer | Working | Claude-powered, streams via WebSocket, full setup context |
| Dashboard | Working | Session list, telemetry viewer, engineer chat, comparison mode |
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
| PitWall37 | 3737 | Running (systemd) | None |
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

1. ~~Build brain system~~ DONE
2. ~~Set up Claude memory~~ DONE
3. ~~Build bridge~~ DONE
4. ~~Deploy bridge to GPU box~~ DONE — tested live with Mugello session
5. ~~Create GitHub repo~~ DONE
6. Track guides for current season tracks
7. Garage61 leaderboard tracking/targets
8. Live dashboard enhancements (real-time telemetry display from bridge)
9. Auto-start bridge on Windows boot (scheduled task or startup folder)
10. Bridge → engineer integration (live telemetry feeds directly into Claude analysis)
