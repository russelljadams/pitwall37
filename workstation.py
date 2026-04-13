"""PitWall37 Workstation — Post-session engineering station on port 3738.

Serves the workstation frontend, provides data APIs, and runs the agent chat.
The only server — drive, sync, parse, review here.
"""

import asyncio
import json
import logging
import sqlite3
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
)

log = logging.getLogger("workstation")

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "pitwall37.db"
TELEM_DIR = DATA_DIR / "telemetry"
DIST_DIR = Path(__file__).parent / "workstation" / "dist"

app = FastAPI(title="PitWall37 Workstation", version="1.0")
ensure_engineering_schema(DB_PATH)


async def _stream_sdk_response(client, websocket: WebSocket):
    """Forward Claude SDK raw messages to the workstation websocket.

    The SDK can emit control messages like `rate_limit_event` that older parser
    layers do not understand. Ignore those instead of failing the whole turn.
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


# --- Frontend ---

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = DIST_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text()
    return "<h1>PitWall37 Workstation — Frontend not built. Run: cd workstation && npm run build</h1>"


# --- Data APIs (same schema as pitwall37.py) ---

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

    tires = conn.execute("""
        SELECT * FROM tire_snapshots WHERE session_id = ?
        ORDER BY lap_number, corner
    """, (session_id,)).fetchall()

    setup = json.loads(session["setup_json"]) if session["setup_json"] else None
    conn.close()

    return {
        "session": dict(session),
        "laps": [dict(l) for l in laps],
        "tires": [dict(t) for t in tires],
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

    tracks = {}
    for r in rows:
        track = r["track"]
        if track not in tracks:
            tracks[track] = []
        tracks[track].append(dict(r))
    return tracks


@app.get("/api/setup/{session_id}")
async def get_setup(session_id: str):
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


@app.get("/api/stats")
async def get_stats():
    conn = get_db()
    total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    total_laps = conn.execute(
        "SELECT COUNT(*) FROM laps WHERE valid = 1"
    ).fetchone()[0]
    tracks = conn.execute(
        "SELECT DISTINCT track FROM sessions"
    ).fetchall()
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


# --- Engineer Chat WebSocket (Claude Code SDK) ---

@app.websocket("/ws/engineer")
async def engineer_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        from claude_code_sdk import ClaudeSDKClient
        from race_agent import build_agent_options

        options = build_agent_options()

        async with ClaudeSDKClient(options=options) as client:
            while True:
                data = await websocket.receive_json()
                msg = data.get("message", "")
                context = data.get("context", {})

                # Build context prefix from workstation selection state
                context_parts = []
                sel_session = context.get("session")
                if sel_session:
                    context_parts.append(
                        f"[Workstation: viewing {sel_session.get('track', '?')} "
                        f"session from {sel_session.get('date', '?')}, "
                        f"best: {sel_session.get('best_time', '?')}s]"
                    )
                sel_laps = context.get("selected_laps")
                if sel_laps:
                    context_parts.append(f"[Selected laps: {sel_laps}]")
                cmp = context.get("compare_session")
                if cmp:
                    context_parts.append(
                        f"[Comparing against: {cmp.get('track', '?')} "
                        f"{cmp.get('date', '?')}]"
                    )
                focused = context.get("focused_param")
                if focused:
                    context_parts.append(f"[Focused on setup param: {focused}]")

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


# --- Static files ---

if DIST_DIR.exists() and (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3738)
