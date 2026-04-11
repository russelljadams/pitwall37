"""PitWall37 v3 — Race Engineering API + Live Bridge
FastAPI server: data API, bridge WebSocket, engineer chat, live dashboard feed.
Frontend is served separately (see /app directory).
"""

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger("pitwall37")

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "pitwall37.db"
TELEM_DIR = DATA_DIR / "telemetry"
APP_DIR = Path(__file__).parent / "app" / "dist"

app = FastAPI(title="PitWall37", version="3.0")

# --- Bridge State (live connection to GPU box) ---

bridge_state = {
    "connected": False,
    "iracing_connected": False,
    "last_heartbeat": 0,
    "session_info": None,
    "live_setup": None,
    "last_telemetry": None,
    "last_lap": None,
    "ws": None,  # bridge WebSocket reference
}

# Dashboard clients that want live data
dashboard_clients: set[WebSocket] = set()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = APP_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text()
    return "<h1>PitWall37 v3 — Frontend not built yet. API is live at /docs</h1>"


@app.get("/api/sessions")
async def list_sessions():
    conn = get_db()
    rows = conn.execute("""
        SELECT id, filename, car, track, track_config, track_length_km,
               session_date, driver_name, total_laps, timed_laps,
               best_lap_time, avg_lap_time, air_temp, track_temp
        FROM sessions
        ORDER BY session_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    conn = get_db()
    session = conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    laps = conn.execute("""
        SELECT * FROM laps WHERE session_id = ?
        ORDER BY lap_number
    """, (session_id,)).fetchall()

    # Setup data
    setup = json.loads(session["setup_json"]) if session["setup_json"] else None

    conn.close()
    return {
        "session": dict(session),
        "laps": [dict(l) for l in laps],
        "setup": setup,
    }


@app.get("/api/laps/{session_id}/{lap_number}/telemetry")
async def get_lap_telemetry(session_id: str, lap_number: int):
    conn = get_db()
    lap = conn.execute(
        "SELECT telemetry_file FROM laps WHERE session_id = ? AND lap_number = ?",
        (session_id, lap_number),
    ).fetchone()
    conn.close()

    if not lap or not lap["telemetry_file"]:
        return JSONResponse({"error": "Telemetry not found"}, status_code=404)

    telem_path = DATA_DIR / lap["telemetry_file"]
    if not telem_path.exists():
        return JSONResponse({"error": "Telemetry file missing"}, status_code=404)

    with open(telem_path) as f:
        return json.load(f)


@app.get("/api/tires/{session_id}/{lap_number}")
async def get_tire_data(session_id: str, lap_number: int):
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM tire_snapshots
        WHERE session_id = ? AND lap_number = ?
    """, (session_id, lap_number)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/progress")
async def get_progress():
    """Lap time progression across all sessions."""
    conn = get_db()
    rows = conn.execute("""
        SELECT s.track, s.session_date, l.lap_number, l.lap_time,
               l.sector_1, l.sector_2, l.sector_3,
               l.avg_speed_ms, l.max_speed_ms, l.fuel_used
        FROM laps l
        JOIN sessions s ON l.session_id = s.id
        WHERE l.valid = 1 AND l.lap_time > 0
        ORDER BY s.session_date, l.lap_number
    """).fetchall()
    conn.close()

    # Group by track
    tracks = {}
    for r in rows:
        track = r["track"]
        if track not in tracks:
            tracks[track] = []
        tracks[track].append(dict(r))

    return tracks


@app.get("/api/setup/{session_id}")
async def get_setup(session_id: str):
    """Get car setup from a session."""
    conn = get_db()
    session = conn.execute(
        "SELECT setup_json, track, session_date FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    if not session or not session["setup_json"]:
        return JSONResponse({"error": "Setup not found"}, status_code=404)
    return {
        "track": session["track"],
        "date": session["session_date"],
        "setup": json.loads(session["setup_json"]),
    }


@app.post("/api/import")
async def trigger_import():
    """Sync IBT files from GPU and parse them."""
    sync_script = Path(__file__).parent / "sync.sh"
    parser_script = Path(__file__).parent / "ibt_parser.py"
    venv_python = Path(__file__).parent / "venv" / "bin" / "python3"

    results = {"sync": "", "parse": ""}

    # Run sync
    if sync_script.exists():
        try:
            r = subprocess.run(
                ["bash", str(sync_script)],
                capture_output=True, text=True, timeout=300,
            )
            results["sync"] = r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            results["sync"] = "Sync timed out after 5 minutes"

    # Run parser
    try:
        r = subprocess.run(
            [str(venv_python), str(parser_script)],
            capture_output=True, text=True, timeout=600,
        )
        results["parse"] = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        results["parse"] = "Parse timed out after 10 minutes"

    return results


@app.get("/api/stats")
async def get_stats():
    """Overall driver stats summary."""
    conn = get_db()

    total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    total_laps = conn.execute(
        "SELECT COUNT(*) FROM laps WHERE valid = 1"
    ).fetchone()[0]
    tracks = conn.execute(
        "SELECT DISTINCT track FROM sessions"
    ).fetchall()

    # Best lap per track
    bests = conn.execute("""
        SELECT s.track, MIN(l.lap_time) as best_time, COUNT(*) as lap_count
        FROM laps l JOIN sessions s ON l.session_id = s.id
        WHERE l.valid = 1 AND l.lap_time > 0
        GROUP BY s.track
    """).fetchall()

    conn.close()
    return {
        "total_sessions": total_sessions,
        "total_valid_laps": total_laps,
        "tracks_driven": len(tracks),
        "track_bests": [dict(b) for b in bests],
    }


# --- Bridge API (GPU box status + commands) ---

@app.get("/api/bridge/status")
async def bridge_status():
    """Get live bridge connection status."""
    return {
        "bridge_connected": bridge_state["connected"],
        "iracing_connected": bridge_state["iracing_connected"],
        "last_heartbeat": bridge_state["last_heartbeat"],
        "session_info": bridge_state["session_info"],
        "has_live_setup": bridge_state["live_setup"] is not None,
        "has_telemetry": bridge_state["last_telemetry"] is not None,
    }


@app.get("/api/bridge/setup")
async def bridge_live_setup():
    """Get the current live setup from iRacing (via bridge)."""
    if not bridge_state["live_setup"]:
        return JSONResponse({"error": "No live setup available"}, status_code=404)
    return bridge_state["live_setup"]


@app.get("/api/bridge/telemetry")
async def bridge_live_telemetry():
    """Get the latest telemetry snapshot from iRacing (via bridge)."""
    if not bridge_state["last_telemetry"]:
        return JSONResponse({"error": "No live telemetry"}, status_code=404)
    return bridge_state["last_telemetry"]


@app.post("/api/bridge/pit")
async def bridge_pit_command(body: dict):
    """Send pit commands to iRacing via bridge.
    Body: {"fuel": 50, "lf": 165, "rf": 165, "lr": 155, "rr": 155}
    """
    ws = bridge_state.get("ws")
    if not ws or not bridge_state["connected"]:
        return JSONResponse({"error": "Bridge not connected"}, status_code=503)
    try:
        await ws.send_json({"command": "pit", "params": body})
        return {"status": "sent", "params": body}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/bridge/command")
async def bridge_command(body: dict):
    """Send a command to the bridge.
    Body: {"command": "get_setup"} or {"command": "reload_textures"} etc.
    """
    ws = bridge_state.get("ws")
    if not ws or not bridge_state["connected"]:
        return JSONResponse({"error": "Bridge not connected"}, status_code=503)
    try:
        await ws.send_json(body)
        return {"status": "sent", "command": body.get("command")}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def broadcast_to_dashboards(msg: dict):
    """Send a message to all connected dashboard WebSocket clients."""
    dead = set()
    for client in dashboard_clients:
        try:
            await client.send_json(msg)
        except Exception:
            dead.add(client)
    dashboard_clients.difference_update(dead)


# --- WebSocket: Bridge connection (from GPU box) ---

@app.websocket("/ws/bridge")
async def bridge_ws(websocket: WebSocket):
    """WebSocket endpoint for the Windows bridge agent."""
    await websocket.accept()
    bridge_state["connected"] = True
    bridge_state["ws"] = websocket
    log.info("Bridge connected from GPU box")

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type", "")
            data = raw.get("data", {})

            if msg_type == "heartbeat":
                bridge_state["last_heartbeat"] = raw.get("ts", time.time())
                bridge_state["iracing_connected"] = data.get(
                    "iracing_connected",
                    raw.get("iracing_connected", False),
                )

            elif msg_type == "session_info":
                bridge_state["session_info"] = data
                log.info(f"Session: {data.get('car')} @ {data.get('track')}")
                await broadcast_to_dashboards({"type": "session_info", "data": data})

            elif msg_type == "setup" or msg_type == "setup_change":
                bridge_state["live_setup"] = data.get("setup", data)
                log.info(f"Setup update (UpdateCount: {data.get('setup', data).get('UpdateCount', '?')})")
                await broadcast_to_dashboards({"type": "setup_update", "data": data})

            elif msg_type == "telemetry":
                bridge_state["last_telemetry"] = data
                await broadcast_to_dashboards({"type": "telemetry", "data": data})

            elif msg_type == "lap_complete":
                bridge_state["last_lap"] = data
                log.info(f"Lap {data.get('lap_number')}: {data.get('lap_time', 0):.3f}s")
                await broadcast_to_dashboards({"type": "lap_complete", "data": data})

            elif msg_type == "state":
                event = data.get("event", "")
                log.info(f"State: {event}")
                await broadcast_to_dashboards({"type": "state", "data": data})

            elif msg_type == "bridge_connect":
                log.info(f"Bridge v{data.get('version')} from {data.get('hostname')}")

    except WebSocketDisconnect:
        log.info("Bridge disconnected")
    except Exception as e:
        log.error(f"Bridge error: {e}")
    finally:
        bridge_state["connected"] = False
        bridge_state["iracing_connected"] = False
        bridge_state["ws"] = None
        await broadcast_to_dashboards({"type": "bridge_disconnected"})


# --- WebSocket: Live dashboard (browser clients) ---

@app.websocket("/ws/live")
async def live_dashboard(websocket: WebSocket):
    """WebSocket for browser dashboards to receive live data."""
    await websocket.accept()
    dashboard_clients.add(websocket)

    # Send current state on connect
    try:
        await websocket.send_json({
            "type": "init",
            "data": {
                "bridge_connected": bridge_state["connected"],
                "iracing_connected": bridge_state["iracing_connected"],
                "session_info": bridge_state["session_info"],
                "has_live_setup": bridge_state["live_setup"] is not None,
            },
        })

        # Keep alive — client will receive broadcasts from bridge handler
        while True:
            # Wait for client messages (ping/pong or commands)
            data = await websocket.receive_json()
            cmd = data.get("command")
            if cmd == "get_setup" and bridge_state["live_setup"]:
                await websocket.send_json({
                    "type": "setup_update",
                    "data": {"setup": bridge_state["live_setup"]},
                })
            elif cmd == "get_telemetry" and bridge_state["last_telemetry"]:
                await websocket.send_json({
                    "type": "telemetry",
                    "data": bridge_state["last_telemetry"],
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        dashboard_clients.discard(websocket)


# --- WebSocket for Engineer Chat ---

@app.websocket("/ws/engineer")
async def engineer_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        # Lazy import to avoid loading anthropic at startup
        from engineer import EngineerChat
        chat = EngineerChat()

        while True:
            data = await websocket.receive_json()
            msg = data.get("message", "")
            context = data.get("context", {})

            # Inject server-side bridge state if frontend didn't provide it
            if not context.get("session") and bridge_state.get("session_info"):
                context["session"] = bridge_state["session_info"]
            if not context.get("setup") and bridge_state.get("live_setup"):
                context["setup"] = bridge_state["live_setup"]
            if not context.get("telemetry") and bridge_state.get("last_telemetry"):
                context["telemetry"] = bridge_state["last_telemetry"]

            # Stream response
            async for chunk in chat.respond(msg, context):
                await websocket.send_json({"type": "chunk", "content": chunk})
            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass


# --- Static files (built frontend) ---

if APP_DIR.exists() and (APP_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=APP_DIR / "assets"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3737)
