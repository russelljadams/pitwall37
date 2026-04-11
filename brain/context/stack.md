# PitWall37 Technical Stack

## Infrastructure
- **Dev Machine:** Vultr Cloud (137.220.32.162 / 100.85.186.91) — Kali Rolling, 4 vCPU, 8GB RAM
- **Racing Machine:** Windows GPU (100.73.76.109) — DESKTOP-KQ4MQ10, runs iRacing, 3080Ti
- **Sim Rig:** MOZA R3 wheelbase + Logitech load cell pedals (budget)
- **Connection:** Tailscale mesh (100.x.x.x), rsync for batch file transfer, WebSocket for live data
- **SSH:** `ssh -i ~/.ssh/id_ed25519 russell@100.73.76.109` (must run bridge from desktop session, not SSH)

## Application — Cloud (Vultr)
- **Backend:** Python 3 + FastAPI (pitwall37.py) — port 3737, systemd managed
- **AI Engine:** Anthropic Claude API (engineer.py) — Sonnet 4 primary, Haiku 4.5 fallback
- **Database:** SQLite (pitwall37.db) — sessions, laps, tire_snapshots tables
- **Frontend:** Single-page HTML dashboard (dashboard.html)
- **Telemetry Parser:** Custom IBT binary parser (ibt_parser.py)
- **Setup Model:** Physics-based parameter validation (setup_model.py)

## Application — GPU Box (Windows)
- **Bridge:** Python 3.13 + pyirsdk + websockets (bridge.py) — deployed to C:\pitwall37\
- **iRacing SDK:** pyirsdk 1.3.5 reads shared memory (60Hz telemetry + session YAML)
- **Capabilities:** Live telemetry stream, setup monitoring, pit commands, texture reload, IBT recording
- **IMPORTANT:** Bridge must run from desktop session (not SSH) — shared memory is per-session

## Data
- **IBT Files:** ~120+ files in data/ibt/ (~5.7GB total)
- **Parsed Telemetry:** JSON files in data/telemetry/ (per-lap channel data at 60Hz)
- **Sessions in DB:** 120+ parsed sessions with setup JSON
- **Reference Setups:** 26 Majors Garage .sto files (knowledge/majors_garage_sto/)
- **Garage Constraints:** F324 parameter definitions (knowledge/f324_garage_constraints.json)
- **Scraped Setups:** Community setups (knowledge/scraped_setups.json)

## Key Files
| File | Location | Purpose |
|------|----------|---------|
| pitwall37.py | Cloud | FastAPI server — dashboard + API + bridge WebSocket endpoints |
| engineer.py | Cloud | Claude race engineer — system prompt, context builder, streaming |
| setup_model.py | Cloud | Setup validation, change prediction, comparison (118-session model) |
| ibt_parser.py | Cloud | IBT binary → SQLite + JSON telemetry |
| dashboard.html | Cloud | Single-page race engineering dashboard |
| sync.sh | Cloud | Rsync IBT files from Windows GPU to cloud |
| pitwall37.service | Cloud | Systemd service definition |
| bridge.py | GPU Box | Live iRacing agent — telemetry, setup, pit commands via pyirsdk |

## API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| / | GET | Dashboard HTML |
| /api/sessions | GET | List all sessions |
| /api/sessions/{id} | GET | Session detail + laps + setup |
| /api/laps/{id}/{lap}/telemetry | GET | Per-lap 60Hz channel data |
| /api/tires/{id}/{lap} | GET | Tire snapshots |
| /api/progress | GET | Lap time progression by track |
| /api/setup/{id} | GET | Setup from historical session |
| /api/stats | GET | Overall driver stats |
| /api/import | POST | Trigger IBT sync + parse |
| /api/bridge/status | GET | Live bridge connection status |
| /api/bridge/setup | GET | Current live setup from iRacing |
| /api/bridge/telemetry | GET | Latest live telemetry snapshot |
| /api/bridge/pit | POST | Send pit commands (fuel, tires) |
| /api/bridge/command | POST | Send bridge commands (reload textures, etc.) |
| /ws/engineer | WS | Streaming Claude race engineer chat |
| /ws/bridge | WS | Bridge connection from GPU box |
| /ws/live | WS | Live data feed for dashboard clients |
