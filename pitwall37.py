"""PitWall37 v3 — Race Engineering API + Live Bridge + Session Agent
FastAPI server: data API, bridge WebSocket, engineer chat, live dashboard feed.
The session agent runs a persistent agentic loop for the duration of each session.
Frontend is served separately (see /app directory).
"""

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from engineering_data import (
    ensure_engineering_schema,
    get_driver_model,
    get_session_debrief,
    get_taxonomy_summary,
    grade_recommendation,
    list_experiments,
    list_recommendations,
    list_session_events,
    record_experiment,
    record_recommendation,
    record_session_event,
)
from session_agent import (
    AgentActions,
    get_active_agent,
    start_session_agent,
    stop_session_agent,
)

log = logging.getLogger("pitwall37")

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "pitwall37.db"
TELEM_DIR = DATA_DIR / "telemetry"
APP_DIR = Path(__file__).parent / "app" / "dist"

app = FastAPI(title="PitWall37", version="3.0")
ensure_engineering_schema(DB_PATH)

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


async def _stream_sdk_response(client, websocket: WebSocket):
    """Forward Claude SDK raw messages to a websocket.

    The SDK can emit control messages such as `rate_limit_event`. Treat them as
    non-fatal and continue the turn.
    """
    while True:
        raw = await client._query.receive_messages().__anext__()
        msg_type = raw.get("type")

        if msg_type == "assistant":
            for block in raw.get("message", {}).get("content", []):
                block_type = block.get("type")
                if block_type == "text" and block.get("text"):
                    await websocket.send_json({
                        "type": "chunk",
                        "content": block["text"],
                    })
                elif block_type == "tool_use":
                    await websocket.send_json({
                        "type": "tool_use",
                        "tool": block.get("name"),
                        "input": block.get("input"),
                    })
                elif block_type == "tool_result":
                    await websocket.send_json({
                        "type": "tool_result",
                        "tool_use_id": block.get("tool_use_id"),
                        "is_error": block.get("is_error") or False,
                    })

        elif msg_type == "result":
            await websocket.send_json({
                "type": "done",
                "cost_usd": raw.get("total_cost_usd"),
                "turns": raw.get("num_turns"),
                "session_id": raw.get("session_id"),
            })
            return

        elif msg_type in {"system", "stream_event", "rate_limit_event"}:
            continue

        else:
            log.warning("Ignoring unknown Claude SDK message type: %s", msg_type)


def get_db():
    ensure_engineering_schema(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


async def _ensure_session_agent() -> None:
    """Start the session agent if not already running."""
    agent = get_active_agent()
    if agent and agent.is_running:
        return
    actions = AgentActions(db_path=DB_PATH)
    await start_session_agent(actions=actions, db_path=DB_PATH)


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
        SELECT s.id, s.filename, s.car, s.track, s.track_config, s.track_length_km,
               s.session_date, s.driver_name, s.total_laps, s.timed_laps,
               s.best_lap_time, s.avg_lap_time, s.air_temp, s.track_temp
        FROM sessions s
        INNER JOIN laps l ON l.session_id = s.id
        GROUP BY s.id
        HAVING COUNT(l.lap_number) > 0
        ORDER BY s.session_date DESC
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


@app.get("/api/recommendations")
async def get_recommendations(
    limit: int = 50,
    track: str | None = None,
    session_id: str | None = None,
    status: str | None = None,
    grade: str | None = None,
):
    return list_recommendations(
        DB_PATH,
        limit=limit,
        track=track,
        session_id=session_id,
        status=status,
        grade=grade,
    )


@app.post("/api/recommendations")
async def create_recommendation(body: dict):
    try:
        return record_recommendation(body, DB_PATH)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/api/recommendations/{recommendation_id}/grade")
async def update_recommendation_grade(recommendation_id: int, body: dict):
    try:
        result = grade_recommendation(recommendation_id, body, DB_PATH)
        if not result:
            return JSONResponse({"error": "Recommendation not found"}, status_code=404)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/experiments")
async def get_experiments(
    limit: int = 50,
    track: str | None = None,
    session_id: str | None = None,
    result: str | None = None,
):
    return list_experiments(
        DB_PATH,
        limit=limit,
        track=track,
        session_id=session_id,
        result=result,
    )


@app.post("/api/experiments")
async def create_experiment(body: dict):
    try:
        return record_experiment(body, DB_PATH)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/insights/driver-model")
async def driver_model(track: str | None = None):
    return get_driver_model(DB_PATH, track=track)


@app.get("/api/insights/taxonomy")
async def taxonomy_summary(track: str | None = None):
    return get_taxonomy_summary(DB_PATH, track=track)


@app.get("/api/events")
async def get_events(
    limit: int = 50,
    track: str | None = None,
    session_id: str | None = None,
    event_type: str | None = None,
    severity: str | None = None,
):
    return list_session_events(
        DB_PATH,
        limit=limit,
        track=track,
        session_id=session_id,
        event_type=event_type,
        severity=severity,
    )


@app.get("/api/sessions/{session_id}/debrief")
async def session_debrief(session_id: str):
    try:
        return get_session_debrief(session_id, DB_PATH)
    except ValueError:
        return JSONResponse({"error": "Session not found"}, status_code=404)


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
    """WebSocket endpoint for the Windows bridge agent.

    All events are forwarded to the session agent's event queue.
    The agent decides what's interesting and how to respond.
    """
    await websocket.accept()
    bridge_state["connected"] = True
    bridge_state["ws"] = websocket
    log.info("Bridge connected from GPU box")

    # Start the session agent
    await _ensure_session_agent()
    agent = get_active_agent()

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type", "")
            data = raw.get("data", {})

            # --- Update bridge_state (fast, synchronous) ---

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

            elif msg_type in ("setup", "setup_change"):
                bridge_state["live_setup"] = data.get("setup", data)
                log.info(f"Setup update (UpdateCount: {data.get('setup', data).get('UpdateCount', '?')})")
                await broadcast_to_dashboards({"type": "setup_update", "data": data})

            elif msg_type == "telemetry":
                bridge_state["last_telemetry"] = data
                await broadcast_to_dashboards({"type": "telemetry", "data": data})

            elif msg_type == "lap_complete":
                bridge_state["last_lap"] = data
                lap_time = data.get("lap_time", 0)
                lap_num = data.get("lap_number", 0)
                log.info(f"Lap {lap_num}: {lap_time:.3f}s")
                await broadcast_to_dashboards({"type": "lap_complete", "data": data})

            elif msg_type == "state":
                event = data.get("event", "")
                log.info(f"State: {event}")
                await broadcast_to_dashboards({"type": "state", "data": data})

            elif msg_type == "bridge_connect":
                log.info(f"Bridge v{data.get('version')} from {data.get('hostname')}")

            # --- Forward ALL events to the session agent ---
            # The agent decides what's interesting. We don't filter here.
            if agent and agent.is_running:
                await agent.push_event({"type": msg_type, "data": data, "ts": raw.get("ts", time.time())})

    except WebSocketDisconnect:
        log.info("Bridge disconnected")
    except Exception as e:
        log.error(f"Bridge error: {e}")
    finally:
        bridge_state["connected"] = False
        bridge_state["iracing_connected"] = False
        bridge_state["ws"] = None

        # Stop the session agent and get final debrief
        debrief = await stop_session_agent()
        if debrief:
            log.info("Session agent final debrief generated (%d chars)", len(debrief))

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


# --- WebSocket for Engineer Chat (Claude Code SDK) ---

@app.websocket("/ws/engineer")
async def engineer_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        from claude_code_sdk import ClaudeSDKClient
        from race_agent import build_agent_options, set_bridge_state

        # Give race agent access to live bridge data
        set_bridge_state(bridge_state)
        options = build_agent_options()

        async with ClaudeSDKClient(options=options) as client:
            while True:
                data = await websocket.receive_json()
                msg = data.get("message", "")
                context = data.get("context", {})

                # Build context prefix from live data
                context_parts = []
                session = context.get("session") or bridge_state.get("session_info")
                if session:
                    context_parts.append(f"[Live: {session.get('car', '?')} @ {session.get('track', '?')}]")
                telem = context.get("telemetry") or bridge_state.get("last_telemetry")
                if telem:
                    speed = (telem.get("speed") or 0) * 3.6
                    context_parts.append(f"[Telemetry: {speed:.0f}km/h Lap:{telem.get('lap', 0)} Fuel:{telem.get('fuel_level', 0):.1f}L]")
                recent_laps = context.get("recent_laps")
                if recent_laps:
                    lap_strs = []
                    for l in recent_laps[:5]:
                        t = f"{l['time']:.3f}s" if l.get('time') and l['time'] > 0 else "?"
                        d = f" ({l['delta']:+.3f})" if l.get('delta') is not None else ""
                        lap_strs.append(f"L{l.get('lap', '?')}:{t}{d}")
                    context_parts.append(f"[Recent laps: {', '.join(lap_strs)}]")

                full_message = msg
                if context_parts:
                    full_message = "\n".join(context_parts) + "\n\n" + msg

                await client.query(full_message)
                await _stream_sdk_response(client, websocket)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error(f"Engineer error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass


# --- Session Agent API ---

@app.get("/api/session-agent/status")
async def session_agent_status():
    """Get the current session agent status."""
    agent = get_active_agent()
    if not agent or not agent.is_running:
        return {"active": False}
    state = agent.state
    return {
        "active": True,
        "car": state.car,
        "track": state.track,
        "total_laps": len(state.laps),
        "valid_laps": state.total_valid_laps,
        "session_best": state.session_best,
        "track_pb": state.track_pb,
        "pace_trend": state.pace_trend,
        "consistency": state.consistency,
        "total_agent_calls": state.total_agent_calls,
        "notes": [{"lap": n.lap, "note": n.note, "category": n.category} for n in state.notes[-10:]],
    }


# --- Static files (built frontend) ---

if APP_DIR.exists() and (APP_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=APP_DIR / "assets"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3737)
