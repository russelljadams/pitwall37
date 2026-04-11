"""PitWall37 Race Agent — Agentic AI race engineer with tools, memory, and proactive monitoring.

This is not a chatbot. This is the head race engineer on the pit wall.
It has tools to query data, validate setups, search the web, and monitor live sessions.
It is proactive — it speaks when it has something worth saying.
It remembers everything across sessions.
"""

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from setup_model import (
    get_setup_knowledge_for_prompt,
    compare_setups,
    validate_setup_change,
    predict_change_effects,
    OBSERVED_RANGES,
)

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "pitwall37.db"
BRAIN_DIR = Path(__file__).parent / "brain"
CONVERSATION_FILE = DATA_DIR / "engineer_conversation.json"

CLIENT = anthropic.Anthropic()
MODEL = "claude-sonnet-4-20250514"
MODEL_FALLBACK = "claude-haiku-4-5-20251001"


def _load_brain_file(filename: str) -> str:
    """Load a file from the brain directory."""
    path = BRAIN_DIR / filename
    if path.exists():
        return path.read_text()
    return f"[File not found: {filename}]"


def _build_system_prompt() -> str:
    """Build the full system prompt from brain files + setup knowledge."""
    identity = _load_brain_file("IDENTITY.md")
    operator = _load_brain_file("context/operator.md")
    setup_knowledge = get_setup_knowledge_for_prompt()

    return f"""You are PitWall37 — the head race engineer for Russell Adams (gh0st / a1i3n37).
You are not an assistant. You are not a chatbot. You are the engineer on the pit wall.

{identity}

{operator}

SETUP CONSTRAINTS AND PHYSICS MODEL:
{setup_knowledge}

TIRE TELEMETRY RULES (CRITICAL):
- The F324 has NO live carcass temp sensors. Carcass temps only update at pit stops.
- Surface temps (tempL/M/R) ARE real — 60Hz IR readings. 50-80°C is NORMAL. Never call them "cold."
- Use temp spread (L/M/R differences) for camber/pressure diagnosis, not absolute values.
- Hot pressures are the most reliable tire data point for setup work.

YOU HAVE TOOLS. USE THEM.
When the driver asks about their history, lap times, setups — don't guess. Query the database.
When they ask about setup changes — validate against the model.
When they want to know about racing technique or track guides — search the web.
When you need context about the project or the car — read the brain files.

Be direct. Be data-backed. Push the driver to be better.
Celebrate progress but never accept "good enough."
If you don't know something, say so — then use your tools to find out.

The mission: make this driver an alien. Top 10 Garage61 leaderboards. Beat Tamas Simon.
"Greatest Race Car Driver Ever. He was built with Claude."
"""


# --- Tool Definitions ---

TOOLS = [
    {
        "name": "query_database",
        "description": "Run a read-only SQL query against the PitWall37 database. Tables: sessions (id, filename, car, track, track_config, track_length_km, session_date, driver_name, total_laps, timed_laps, best_lap_time, avg_lap_time, air_temp, track_temp, setup_json), laps (session_id, lap_number, lap_time, sector_1, sector_2, sector_3, valid, avg_speed_ms, max_speed_ms, fuel_used, telemetry_file), tire_snapshots (session_id, lap_number, corner, temp_left, temp_mid, temp_right, wear_left, wear_mid, wear_right, cold_pressure, hot_pressure).",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SELECT query to run. Must be read-only (SELECT only).",
                },
                "purpose": {
                    "type": "string",
                    "description": "Brief description of what you're looking for.",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "name": "get_live_data",
        "description": "Get the current live data from the bridge — telemetry, setup, session info, recent laps. Use this to see what's happening RIGHT NOW in iRacing.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "validate_setup_change",
        "description": "Validate a proposed setup change against observed safe ranges from 120+ sessions. Returns whether it's safe, any warnings, and predicted side effects.",
        "input_schema": {
            "type": "object",
            "properties": {
                "parameter": {
                    "type": "string",
                    "description": "Parameter name (e.g., 'front_flap_angle_deg', 'rear_spring_rate_nmm', 'brake_bias_pct'). Must match keys in OBSERVED_RANGES.",
                },
                "new_value": {
                    "type": "number",
                    "description": "Proposed new value.",
                },
            },
            "required": ["parameter", "new_value"],
        },
    },
    {
        "name": "predict_effects",
        "description": "Predict what happens when a setup parameter is increased or decreased. Returns physics-based cause-and-effect analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "parameter": {
                    "type": "string",
                    "description": "Parameter name from CHANGE_EFFECTS.",
                },
                "direction": {
                    "type": "string",
                    "enum": ["increase", "decrease"],
                },
            },
            "required": ["parameter", "direction"],
        },
    },
    {
        "name": "compare_session_setups",
        "description": "Compare the setups from two sessions. Returns a diff showing what changed and the lap time delta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id_a": {"type": "string", "description": "First session ID."},
                "session_id_b": {"type": "string", "description": "Second session ID."},
            },
            "required": ["session_id_a", "session_id_b"],
        },
    },
    {
        "name": "read_brain_file",
        "description": "Read a file from the PitWall37 brain directory. Available: IDENTITY.md, SHARED-STATE.md, context/operator.md, context/missions.md, context/stack.md, context/skills.md, domain/INDEX.md",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path within the brain/ directory.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_web",
        "description": "Search the web for racing knowledge, setup guides, track info, techniques, or anything else useful. Use this to find information you don't already know.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query. Be specific — include car name, track, iRacing, etc.",
                },
            },
            "required": ["query"],
        },
    },
]


# --- Tool Execution ---

def _execute_tool(tool_name: str, tool_input: dict, bridge_state: dict = None) -> str:
    """Execute a tool and return the result as a string."""

    if tool_name == "query_database":
        sql = tool_input.get("sql", "")
        if not sql.strip().upper().startswith("SELECT"):
            return "Error: Only SELECT queries are allowed."
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql).fetchall()
            conn.close()
            if not rows:
                return "No results."
            results = [dict(r) for r in rows]
            # Truncate if too many results
            if len(results) > 50:
                results = results[:50]
                return json.dumps(results, default=str) + f"\n... ({len(rows)} total, showing first 50)"
            return json.dumps(results, default=str, indent=2)
        except Exception as e:
            return f"SQL Error: {e}"

    elif tool_name == "get_live_data":
        if not bridge_state:
            return "Bridge is not connected. No live data available."
        parts = []
        parts.append(f"Bridge connected: {bridge_state.get('connected', False)}")
        parts.append(f"iRacing connected: {bridge_state.get('iracing_connected', False)}")
        si = bridge_state.get("session_info")
        if si:
            parts.append(f"Car: {si.get('car')} @ {si.get('track')} ({si.get('track_config', '')})")
            parts.append(f"Driver: {si.get('driver')}")
        t = bridge_state.get("last_telemetry")
        if t:
            speed = (t.get("speed") or 0) * 3.6
            parts.append(f"\nLive telemetry:")
            parts.append(f"  Speed: {speed:.0f} km/h | RPM: {t.get('rpm', 0):.0f} | Gear: {t.get('gear', 0)}")
            parts.append(f"  Throttle: {(t.get('throttle') or 0)*100:.0f}% | Brake: {(t.get('brake') or 0)*100:.0f}%")
            parts.append(f"  Fuel: {t.get('fuel_level', 0):.2f}L ({(t.get('fuel_pct') or 0)*100:.1f}%)")
            parts.append(f"  Lap: {t.get('lap', 0)} | On track: {t.get('on_track')} | In garage: {t.get('in_garage')}")
            parts.append(f"  Best lap: {t.get('best_lap_time', 0):.3f}s | Last lap: {t.get('last_lap_time', 0):.3f}s")
        setup = bridge_state.get("live_setup")
        if setup:
            parts.append(f"\nLive setup (UpdateCount: {setup.get('UpdateCount', '?')}):")
            ac = setup.get("TiresAero", {}).get("AeroCalculator", {})
            if ac:
                for k, v in ac.items():
                    parts.append(f"  {k}: {v}")
            aero = setup.get("TiresAero", {}).get("AeroSetup", {})
            if aero:
                for k, v in aero.items():
                    parts.append(f"  {k}: {v}")
            chassis = setup.get("Chassis", {})
            for sec in ["Front", "LeftFront", "RightFront", "Rear", "LeftRear", "RightRear", "BrakesInCarMisc", "Differential"]:
                section = chassis.get(sec, {})
                if section:
                    parts.append(f"  {sec}:")
                    for k, v in section.items():
                        parts.append(f"    {k}: {v}")
        last_lap = bridge_state.get("last_lap")
        if last_lap:
            parts.append(f"\nLast completed lap: #{last_lap.get('lap_number')} — {last_lap.get('lap_time', 0):.3f}s")
        return "\n".join(parts) if parts else "No live data available."

    elif tool_name == "validate_setup_change":
        result = validate_setup_change(
            tool_input["parameter"],
            tool_input["new_value"],
        )
        return json.dumps(result, default=str, indent=2)

    elif tool_name == "predict_effects":
        effects = predict_change_effects(
            tool_input["parameter"],
            tool_input.get("direction", "increase"),
        )
        return "\n".join(effects) if effects else "No known effects for this parameter."

    elif tool_name == "compare_session_setups":
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            s1 = conn.execute("SELECT setup_json, track, best_lap_time, session_date FROM sessions WHERE id = ?",
                              (tool_input["session_id_a"],)).fetchone()
            s2 = conn.execute("SELECT setup_json, track, best_lap_time, session_date FROM sessions WHERE id = ?",
                              (tool_input["session_id_b"],)).fetchone()
            conn.close()
            if not s1 or not s2:
                return "One or both sessions not found."
            if not s1["setup_json"] or not s2["setup_json"]:
                return "One or both sessions have no setup data."
            setup_a = json.loads(s1["setup_json"])
            setup_b = json.loads(s2["setup_json"])
            diff = compare_setups(setup_a, setup_b)
            header = (
                f"Session A: {s1['track']} {s1['session_date']} (best: {s1['best_lap_time']:.3f}s)\n"
                f"Session B: {s2['track']} {s2['session_date']} (best: {s2['best_lap_time']:.3f}s)\n"
            )
            if s1["best_lap_time"] and s2["best_lap_time"]:
                delta = s2["best_lap_time"] - s1["best_lap_time"]
                header += f"Delta: {delta:+.3f}s (B vs A)\n"
            return header + "\n" + diff
        except Exception as e:
            return f"Error comparing: {e}"

    elif tool_name == "read_brain_file":
        return _load_brain_file(tool_input["path"])

    elif tool_name == "search_web":
        # Return a marker — the server will intercept this and do the actual search
        return json.dumps({"_search_request": tool_input["query"]})

    return f"Unknown tool: {tool_name}"


# --- Conversation Persistence ---

def _load_conversation() -> list:
    """Load saved conversation from disk."""
    if CONVERSATION_FILE.exists():
        try:
            data = json.loads(CONVERSATION_FILE.read_text())
            # Keep last 60 messages max
            return data[-60:]
        except Exception:
            return []
    return []


def _save_conversation(messages: list):
    """Save conversation to disk."""
    try:
        CONVERSATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Keep last 60 messages
        CONVERSATION_FILE.write_text(json.dumps(messages[-60:], default=str, indent=2))
    except Exception:
        pass


# --- The Agent ---

class RaceAgent:
    """The PitWall37 race engineer agent. Has tools, memory, and opinions."""

    def __init__(self, bridge_state_ref: dict = None):
        self.bridge_state = bridge_state_ref or {}
        self.messages = _load_conversation()
        self.system_prompt = _build_system_prompt()

    async def respond(self, user_message: str, context: dict = None):
        """Generate an agentic response. Yields text chunks for streaming.
        The agent may call tools multiple times before responding."""

        # Build context prefix from live data if available
        context_parts = []
        if context:
            session = context.get("session")
            if session:
                context_parts.append(f"[Live: {session.get('car', '?')} @ {session.get('track', '?')}]")
            telemetry = context.get("telemetry")
            if telemetry:
                speed = (telemetry.get("speed") or 0) * 3.6
                context_parts.append(f"[Telemetry: {speed:.0f}km/h Lap:{telemetry.get('lap', 0)} Fuel:{telemetry.get('fuel_level', 0):.1f}L]")
            recent_laps = context.get("recent_laps")
            if recent_laps:
                lap_strs = []
                for l in recent_laps[:5]:
                    t = f"{l['time']:.3f}s" if l.get('time') and l['time'] > 0 else "?"
                    d = f" ({l['delta']:+.3f})" if l.get('delta') is not None else ""
                    lap_strs.append(f"L{l.get('lap', '?')}:{t}{d}")
                context_parts.append(f"[Recent laps: {', '.join(lap_strs)}]")

        # Prepend context to message
        full_message = user_message
        if context_parts:
            full_message = "\n".join(context_parts) + "\n\n" + user_message

        self.messages.append({"role": "user", "content": full_message})

        # Agentic loop — keep going until we get a final text response
        model = MODEL
        while True:
            try:
                response = CLIENT.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=self.system_prompt,
                    tools=TOOLS,
                    messages=self.messages,
                )
            except anthropic.APIStatusError as e:
                if "overloaded" in str(e).lower() or e.status_code == 529:
                    model = MODEL_FALLBACK
                    response = CLIENT.messages.create(
                        model=model,
                        max_tokens=4096,
                        system=self.system_prompt,
                        tools=TOOLS,
                        messages=self.messages,
                    )
                else:
                    raise

            # Process response blocks
            assistant_content = response.content
            self.messages.append({"role": "assistant", "content": assistant_content})

            # Check if there are tool calls
            tool_uses = [b for b in assistant_content if b.type == "tool_use"]

            if not tool_uses:
                # No tool calls — extract text and yield it
                text_blocks = [b.text for b in assistant_content if b.type == "text"]
                full_text = "\n".join(text_blocks)
                # Yield in chunks for streaming effect
                chunk_size = 12
                for i in range(0, len(full_text), chunk_size):
                    yield full_text[i:i + chunk_size]
                break

            # Execute tools and continue the loop
            tool_results = []
            for tool_use in tool_uses:
                # Yield a status message so the user knows what's happening
                yield f"\n[Using tool: {tool_use.name}...]\n"

                if tool_use.name == "search_web":
                    # Web search — yield marker, actual search done by caller
                    result = _execute_tool(tool_use.name, tool_use.input, self.bridge_state)
                    parsed = json.loads(result)
                    if "_search_request" in parsed:
                        # We can't do web search from here — tell the agent
                        result = "Web search is not available in this context. Use your existing knowledge or suggest the driver search for specific information."
                else:
                    result = _execute_tool(tool_use.name, tool_use.input, self.bridge_state)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                })

            self.messages.append({"role": "user", "content": tool_results})

            # Check stop reason — if end_turn, we might have text + tool use
            if response.stop_reason == "end_turn":
                text_blocks = [b.text for b in assistant_content if b.type == "text"]
                if text_blocks:
                    full_text = "\n".join(text_blocks)
                    chunk_size = 12
                    for i in range(0, len(full_text), chunk_size):
                        yield full_text[i:i + chunk_size]
                    break

        # Save conversation after response
        _save_conversation(self._serialize_messages())

        # Trim if getting long
        if len(self.messages) > 60:
            self.messages = self.messages[-60:]

    async def proactive_analysis(self, event_type: str, event_data: dict):
        """Generate proactive analysis for events like lap completion or setup changes.
        Returns the full text response (not streamed)."""

        if event_type == "lap_complete":
            lap_num = event_data.get("lap_number", 0)
            lap_time = event_data.get("lap_time", 0)
            if lap_time <= 0:
                return None

            prompt = (
                f"[PROACTIVE — Lap {lap_num} just completed: {lap_time:.3f}s]\n"
                f"Give a brief 1-2 sentence radio call about this lap. "
                f"If it's notably fast or slow compared to recent laps, say why. "
                f"If there's nothing interesting, just confirm the time. Be a real engineer — brief and useful."
            )

        elif event_type == "setup_change":
            prompt = (
                f"[PROACTIVE — Setup change detected (UpdateCount: {event_data.get('update_count', '?')})]\n"
                f"The driver just changed the setup. Use get_live_data to see the new setup and give a brief opinion."
            )

        elif event_type == "fuel_warning":
            fuel = event_data.get("fuel_level", 0)
            prompt = f"[PROACTIVE — Fuel warning: {fuel:.1f}L remaining]\nBrief fuel status call."

        elif event_type == "pace_degradation":
            prompt = (
                f"[PROACTIVE — Pace degradation detected: last 3 laps trending slower]\n"
                f"Brief radio call — are tires going off, or is the driver losing focus?"
            )

        elif event_type == "personal_best":
            lap_time = event_data.get("lap_time", 0)
            prompt = (
                f"[PROACTIVE — NEW PERSONAL BEST: {lap_time:.3f}s! Lap {event_data.get('lap_number', '?')}]\n"
                f"Celebrate this! Brief, excited engineer radio call."
            )

        else:
            return None

        self.messages.append({"role": "user", "content": prompt})

        try:
            response = CLIENT.messages.create(
                model=MODEL,
                max_tokens=512,
                system=self.system_prompt,
                tools=TOOLS,
                messages=self.messages,
            )

            # Handle tool use in proactive mode (simple, one round)
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if tool_uses:
                self.messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for tu in tool_uses:
                    result = _execute_tool(tu.name, tu.input, self.bridge_state)
                    tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": result})
                self.messages.append({"role": "user", "content": tool_results})
                response = CLIENT.messages.create(
                    model=MODEL,
                    max_tokens=512,
                    system=self.system_prompt,
                    messages=self.messages,
                )

            text = "\n".join(b.text for b in response.content if b.type == "text")
            self.messages.append({"role": "assistant", "content": response.content})
            _save_conversation(self._serialize_messages())
            return text

        except Exception as e:
            return f"[Engineer error: {e}]"

    def _serialize_messages(self) -> list:
        """Serialize messages for JSON storage."""
        serialized = []
        for msg in self.messages:
            if isinstance(msg.get("content"), list):
                # Handle content blocks (tool use/result)
                blocks = []
                for block in msg["content"]:
                    if hasattr(block, "type"):
                        # Anthropic content block object
                        if block.type == "text":
                            blocks.append({"type": "text", "text": block.text})
                        elif block.type == "tool_use":
                            blocks.append({
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            })
                    elif isinstance(block, dict):
                        blocks.append(block)
                serialized.append({"role": msg["role"], "content": blocks})
            elif isinstance(msg.get("content"), str):
                serialized.append(msg)
            else:
                # Content block objects from API response
                content = msg.get("content", [])
                if hasattr(content, '__iter__') and not isinstance(content, str):
                    blocks = []
                    for block in content:
                        if hasattr(block, "type"):
                            if block.type == "text":
                                blocks.append({"type": "text", "text": block.text})
                            elif block.type == "tool_use":
                                blocks.append({
                                    "type": "tool_use",
                                    "id": block.id,
                                    "name": block.name,
                                    "input": block.input,
                                })
                        elif isinstance(block, dict):
                            blocks.append(block)
                    serialized.append({"role": msg["role"], "content": blocks})
                else:
                    serialized.append(msg)
        return serialized


# Keep backward compat alias
EngineerChat = RaceAgent
