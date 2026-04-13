# PitWall37 Technical Stack

## Infrastructure
- **Dev Machine:** Vultr Cloud (137.220.32.162 / 100.85.186.91) — Kali Rolling, 4 vCPU, 8GB RAM
- **Racing Machine:** Windows GPU (100.73.76.109) — runs iRacing, 3080Ti
- **Sim Rig:** MOZA R3 wheelbase + Logitech load cell pedals
- **Connection:** Tailscale mesh, rsync for IBT file transfer
- **SSH:** `ssh -i ~/.ssh/id_ed25519 russell@100.73.76.109`

## Application
- **Workstation:** `workstation.py` + `workstation/` on port 3738
- **AI Engine:** Claude Code SDK via `race_agent.py` with MCP analysis tools
- **Database:** SQLite (pitwall37.db) — sessions, laps, tires, recommendations, experiments
- **Telemetry Parser:** Custom IBT binary parser (`ibt_parser.py`)
- **Setup Model:** Physics-based parameter validation (`setup_model.py`)
- **Engineering Log:** `engineering_data.py` — anti-BS scorecard
- **CLI:** `pw.py` — daily workflow commands

## Data
- **IBT Files:** 120+ in `data/ibt/`
- **Parsed Telemetry:** JSON files in `data/telemetry/` (per-lap, 60Hz/10Hz)
- **Sessions in DB:** 120+ with setup JSON
- **Reference Setups:** Majors Garage `.sto` files
- **Garage Constraints:** `knowledge/f324_garage_constraints.json`

## Key Files
| File | Purpose |
|------|---------|
| `workstation.py` | Workstation backend (port 3738) |
| `race_agent.py` | Claude agent with MCP analysis tools |
| `engineering_data.py` | Recommendations, experiments, driver model |
| `setup_model.py` | Setup validation, change prediction, comparison |
| `ibt_parser.py` | IBT binary → SQLite + JSON telemetry |
| `pw.py` | Daily CLI: stats, debrief, driver-model, taxonomy |
| `sync.sh` | Rsync IBTs from Windows GPU to cloud |

## Workflow
1. Drive on GPU box
2. `bash sync.sh` — pull IBT files
3. `python3 ibt_parser.py` — parse into DB
4. `python3 pw.py debrief <id>` or workstation UI — review
5. Claude chat for deep analysis and comparison
