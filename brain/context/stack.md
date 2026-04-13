# PitWall37 Technical Stack

## Infrastructure
- **Dev Machine:** Vultr Cloud (137.220.32.162 / 100.85.186.91) — Kali Rolling, 4 vCPU, 8GB RAM
- **Racing Machine:** Windows GPU (100.73.76.109) — DESKTOP-KQ4MQ10, runs iRacing, 3080Ti
- **Sim Rig:** MOZA R3 wheelbase + Logitech load cell pedals (budget)
- **Connection:** Tailscale mesh (100.x.x.x), rsync for batch file transfer, WebSocket for live data
- **SSH:** `ssh -i ~/.ssh/id_ed25519 russell@100.73.76.109` (must run bridge from desktop session, not SSH)

## Application — Cloud (Vultr)
- **Private Driver System:** `workstation.py` + `workstation/` on port 3738 — private review room
- **Public Overlay Layer:** `pitwall37.py` + `app/` on port 3737 — stream-facing overlay and live APIs
- **AI Engine:** Claude Code SDK via `race_agent.py` — chat-first engineer workflow
- **Database:** SQLite (pitwall37.db) — sessions, laps, tires, recommendations, experiments, signals
- **Telemetry Parser:** Custom IBT binary parser (`ibt_parser.py`)
- **Setup Model:** Physics-based parameter validation (`setup_model.py`)
- **Engineering Log:** `engineering_data.py` — recommendations, experiments, driver model

## Application — GPU Box (Windows)
- **Bridge:** Python 3.13 + pyirsdk + websockets (`bridge.py`) — deployed to `C:\pitwall37\`
- **iRacing SDK:** pyirsdk 1.3.5 reads shared memory (60Hz telemetry + session YAML)
- **Capabilities:** Live telemetry stream, setup monitoring, pit commands, texture reload, IBT recording
- **IMPORTANT:** Bridge must run from desktop session (not SSH) — shared memory is per-session

## Data
- **IBT Files:** 120+ files in `data/ibt/`
- **Parsed Telemetry:** JSON files in `data/telemetry/` (per-lap channel data at 60Hz)
- **Sessions in DB:** 130+ parsed sessions with setup JSON
- **Reference Setups:** 26 Majors Garage `.sto` files (`knowledge/majors_garage_sto/`)
- **Garage Constraints:** F324 parameter definitions (`knowledge/f324_garage_constraints.json`)
- **Scraped Setups:** Community setups (`knowledge/scraped_setups.json`)
- **Engineering Memory:** recommendations, experiments, and derived driver-model signals

## Key Files
| File | Location | Purpose |
|------|----------|---------|
| `pitwall37.py` | Cloud | Public-facing overlay/live API backend |
| `workstation.py` | Cloud | Private workstation backend |
| `race_agent.py` | Cloud | Claude race engineer — tool wiring, output contract, streaming |
| `engineering_data.py` | Cloud | Recommendation scorecard, experiment log, driver model |
| `setup_model.py` | Cloud | Setup validation, change prediction, comparison |
| `ibt_parser.py` | Cloud | IBT binary → SQLite + JSON telemetry |
| `pw.py` | Cloud | Lean CLI for stats, debriefs, driver model, taxonomy |
| `sync.sh` | Cloud | Rsync IBT files from Windows GPU to cloud |
| `pitwall37.service` | Cloud | Systemd service definition |
| `bridge/bridge.py` | GPU Box | Live iRacing agent — telemetry, setup, pit commands via pyirsdk |

## API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Overlay/frontend entry |
| `/api/sessions` | GET | List all sessions |
| `/api/sessions/{id}` | GET | Session detail + laps + setup |
| `/api/sessions/{id}/debrief` | GET | Lean session debrief |
| `/api/laps/{id}/{lap}/telemetry` | GET | Per-lap 60Hz channel data |
| `/api/tires/{id}/{lap}` | GET | Tire snapshots |
| `/api/progress` | GET | Lap time progression by track |
| `/api/setup/{id}` | GET | Setup from historical session |
| `/api/stats` | GET | Overall driver stats |
| `/api/recommendations` | GET/POST | Recommendation scorecard |
| `/api/experiments` | GET/POST | One-variable experiment log |
| `/api/insights/driver-model` | GET | Validated strengths/weaknesses |
| `/api/insights/taxonomy` | GET | Outcomes grouped by focus area |
| `/api/import` | POST | Trigger IBT sync + parse |
| `/api/bridge/status` | GET | Live bridge connection status |
| `/api/bridge/setup` | GET | Current live setup from iRacing |
| `/api/bridge/telemetry` | GET | Latest live telemetry snapshot |
| `/api/bridge/pit` | POST | Send pit commands (fuel, tires) |
| `/api/bridge/command` | POST | Send bridge commands (reload textures, etc.) |
| `/ws/engineer` | WS | Streaming Claude race engineer chat |
| `/ws/bridge` | WS | Bridge connection from GPU box |
| `/ws/live` | WS | Live data feed for overlay clients |

## Workflow Preference
- **Primary:** Claude/Codex + `pw.py` + focused workstation views
- **Secondary:** richer dashboard interaction
- **Audience layer:** overlay only when it helps storytelling on stream
