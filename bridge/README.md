# PitWall37 Bridge — Windows GPU Box Agent

Real-time bridge between iRacing (Windows) and PitWall37 (Cloud).

## What It Does

- Streams live telemetry at 60Hz to PitWall37
- Monitors setup changes and records them automatically
- Automates pit stops (fuel, tire pressures)
- Triggers telemetry recording
- Reloads Trading Paints textures

## Requirements

- Python 3.10+ on Windows
- iRacing running
- `pip install pyirsdk websockets`
- Tailscale connected to the mesh

## Usage

```bash
python bridge.py
```

Connects to PitWall37 at ws://100.85.186.91:3737/ws/bridge
