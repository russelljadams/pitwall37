"""PitWall37 Race Agent — Claude Code SDK integration with custom racing tools.

Custom racing tools are served via an in-process MCP server.
Built-in tools (WebSearch, Bash, Read, Write, Glob, Grep) come free from the SDK.
"""

import json
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

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

from setup_model import (
    compare_setups,
    predict_change_effects,
    validate_setup_change,
    get_setup_knowledge_for_prompt,
)

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "pitwall37.db"
BRAIN_DIR = Path(__file__).parent / "brain"
TELEM_DIR = DATA_DIR / "telemetry"
PROJECT_DIR = Path(__file__).parent
ensure_engineering_schema(DB_PATH)

# ---------------------------------------------------------------------------
# MCP Server — custom racing tools
# ---------------------------------------------------------------------------

mcp_server = FastMCP("pitwall37")

# Reference to bridge_state — set by pitwall37.py at startup
_bridge_state: dict = {}


def set_bridge_state(state: dict):
    """Set the bridge state reference so tools can access live data."""
    global _bridge_state
    _bridge_state = state


@mcp_server.tool(
    name="query_telemetry_db",
    description=(
        "Run a read-only SQL SELECT query against the PitWall37 SQLite database. "
        "Tables: sessions (id, filename, car, track, track_config, track_length_km, "
        "session_date, driver_name, total_laps, timed_laps, best_lap_time, avg_lap_time, "
        "air_temp, track_temp, setup_json), "
        "laps (session_id, lap_number, lap_time, sector_1, sector_2, sector_3, "
        "valid, avg_speed_ms, max_speed_ms, fuel_used, telemetry_file), "
        "tire_snapshots (session_id, lap_number, corner, temp_left, temp_mid, "
        "temp_right, wear_left, wear_mid, wear_right, cold_pressure, hot_pressure). "
        "120+ sessions of real F324 data across multiple tracks."
    ),
)
def query_telemetry_db(sql: str, purpose: str = "") -> str:
    """Query the PitWall37 SQLite database with a SELECT statement."""
    ensure_engineering_schema(DB_PATH)
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
        if len(results) > 50:
            truncated = json.dumps(results[:50], default=str)
            return truncated + f"\n... ({len(results)} total, showing first 50)"
        return json.dumps(results, default=str, indent=2)
    except Exception as e:
        return f"SQL Error: {e}"


@mcp_server.tool(
    name="analyze_lap",
    description=(
        "Load and analyze 60Hz telemetry for a specific lap. Computes: "
        "braking points (track position where brake > 0.05 after full throttle), "
        "corner minimum speeds at each apex, throttle application patterns "
        "(% full throttle, % coasting, % trail brake overlap), ride height analysis "
        "(min, bottoming events, danger zones), G-force envelope, fuel consumption rate. "
        "Requires session_id and lap_number."
    ),
)
def analyze_lap(session_id: str, lap_number: int) -> str:
    """Load and analyze 60Hz telemetry for a specific lap."""
    ensure_engineering_schema(DB_PATH)
    # Find the telemetry file
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    lap_row = conn.execute(
        "SELECT telemetry_file, lap_time FROM laps WHERE session_id = ? AND lap_number = ?",
        (session_id, lap_number),
    ).fetchone()
    session_row = conn.execute(
        "SELECT track, track_config, track_length_km FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    conn.close()

    if not lap_row or not lap_row["telemetry_file"]:
        return f"No telemetry found for session {session_id} lap {lap_number}."

    telem_path = DATA_DIR / lap_row["telemetry_file"]
    if not telem_path.exists():
        return f"Telemetry file missing: {lap_row['telemetry_file']}"

    with open(telem_path) as f:
        data = json.load(f)

    ch = data.get("channels", {})
    speeds = ch.get("speed", [])
    throttles = ch.get("throttle", [])
    brakes = ch.get("brake", [])
    dist_pcts = ch.get("dist_pct", [])
    gears = ch.get("gear", [])
    fuels = ch.get("fuel", [])
    lat_gs = ch.get("lat_g", [])
    long_gs = ch.get("long_g", [])
    steerings = ch.get("steering", [])

    n = len(speeds)
    if n == 0:
        return "Telemetry file has no speed data."

    sample_rate = data.get("sample_rate_hz", 10)
    track_info = ""
    if session_row:
        track_info = f"{session_row['track']} ({session_row['track_config'] or 'Grand Prix'})"

    result = {
        "session_id": session_id,
        "lap_number": lap_number,
        "lap_time": lap_row["lap_time"] or data.get("lap_time_s"),
        "track": track_info,
        "sample_rate_hz": sample_rate,
        "total_samples": n,
    }

    # Speed analysis
    speeds_kmh = [s * 3.6 for s in speeds]
    result["speed"] = {
        "max_kmh": round(max(speeds_kmh), 1),
        "min_kmh": round(min(speeds_kmh), 1),
        "avg_kmh": round(sum(speeds_kmh) / n, 1),
    }

    # Throttle analysis
    if throttles:
        full_throttle = sum(1 for t in throttles if t > 0.95)
        no_throttle = sum(1 for t in throttles if t < 0.05)
        partial = n - full_throttle - no_throttle
        result["throttle"] = {
            "full_pct": round(full_throttle / n * 100, 1),
            "partial_pct": round(partial / n * 100, 1),
            "off_pct": round(no_throttle / n * 100, 1),
        }

    # Trail braking (brake > 0.05 AND throttle > 0.05 simultaneously)
    if throttles and brakes:
        trail_brake = sum(1 for i in range(n) if brakes[i] > 0.05 and throttles[i] > 0.05)
        result["trail_braking_pct"] = round(trail_brake / n * 100, 1)

    # Braking zones — detect brake application points
    if brakes and dist_pcts and throttles:
        braking_zones = []
        in_brake = False
        brake_start_dist = 0
        pre_brake_speed = 0
        for i in range(1, n):
            if not in_brake and brakes[i] > 0.05 and brakes[i - 1] <= 0.05:
                in_brake = True
                brake_start_dist = dist_pcts[i] if i < len(dist_pcts) else 0
                pre_brake_speed = speeds_kmh[i]
            elif in_brake and brakes[i] <= 0.05:
                in_brake = False
                min_speed_zone = min(speeds_kmh[max(0, i - 30):i + 1])
                braking_zones.append({
                    "dist_pct": round(brake_start_dist, 4),
                    "entry_speed_kmh": round(pre_brake_speed, 1),
                    "min_speed_kmh": round(min_speed_zone, 1),
                    "speed_shed_kmh": round(pre_brake_speed - min_speed_zone, 1),
                })
        result["braking_zones"] = braking_zones[:15]  # Limit to 15

    # Corner minimum speeds (local minima in speed trace where speed < 80% of max)
    if speeds_kmh and dist_pcts:
        threshold = max(speeds_kmh) * 0.80
        corners = []
        in_corner = False
        corner_min = float("inf")
        corner_dist = 0
        for i in range(n):
            if speeds_kmh[i] < threshold:
                if not in_corner:
                    in_corner = True
                    corner_min = speeds_kmh[i]
                    corner_dist = dist_pcts[i] if i < len(dist_pcts) else 0
                elif speeds_kmh[i] < corner_min:
                    corner_min = speeds_kmh[i]
                    corner_dist = dist_pcts[i] if i < len(dist_pcts) else 0
            elif in_corner:
                in_corner = False
                corners.append({
                    "dist_pct": round(corner_dist, 4),
                    "min_speed_kmh": round(corner_min, 1),
                })
                corner_min = float("inf")
        result["corner_min_speeds"] = corners

    # G-force envelope
    if lat_gs and long_gs:
        result["g_forces"] = {
            "max_lateral_g": round(max(abs(g) for g in lat_gs), 2),
            "max_braking_g": round(max(abs(g) for g in long_gs if g < 0), 2) if any(g < 0 for g in long_gs) else 0,
            "max_accel_g": round(max(g for g in long_gs if g > 0), 2) if any(g > 0 for g in long_gs) else 0,
        }

    # Ride height analysis
    rh = data.get("ride_height", {})
    if rh:
        result["ride_height"] = rh

    # Fuel consumption
    if fuels and len(fuels) >= 2:
        fuel_start = fuels[0]
        fuel_end = fuels[-1]
        result["fuel"] = {
            "start_l": round(fuel_start, 2),
            "end_l": round(fuel_end, 2),
            "used_l": round(fuel_start - fuel_end, 3),
        }

    # Tire data (end-of-lap snapshot)
    tire_end = data.get("tire_end", {})
    if tire_end:
        result["tire_end"] = tire_end

    return json.dumps(result, indent=2)


@mcp_server.tool(
    name="compare_laps",
    description=(
        "Compare two laps channel-by-channel. Aligns by dist_pct and computes: "
        "speed delta by track position, where time is gained/lost by section, "
        "braking point differences, corner speed differences. "
        "Returns concrete analysis like 'You gained 0.15s in T3-T5 by carrying 4km/h more mid-corner'. "
        "Provide session_id and lap_number for each lap (can be from different sessions)."
    ),
)
def compare_laps(
    session_id_a: str, lap_number_a: int,
    session_id_b: str, lap_number_b: int,
) -> str:
    """Compare two laps channel-by-channel aligned by dist_pct."""
    ensure_engineering_schema(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    lap_a = conn.execute(
        "SELECT telemetry_file, lap_time FROM laps WHERE session_id = ? AND lap_number = ?",
        (session_id_a, lap_number_a),
    ).fetchone()
    lap_b = conn.execute(
        "SELECT telemetry_file, lap_time FROM laps WHERE session_id = ? AND lap_number = ?",
        (session_id_b, lap_number_b),
    ).fetchone()
    conn.close()

    if not lap_a or not lap_a["telemetry_file"]:
        return f"No telemetry for lap A (session {session_id_a}, lap {lap_number_a})."
    if not lap_b or not lap_b["telemetry_file"]:
        return f"No telemetry for lap B (session {session_id_b}, lap {lap_number_b})."

    path_a = DATA_DIR / lap_a["telemetry_file"]
    path_b = DATA_DIR / lap_b["telemetry_file"]
    if not path_a.exists() or not path_b.exists():
        return "One or both telemetry files are missing."

    with open(path_a) as f:
        data_a = json.load(f)
    with open(path_b) as f:
        data_b = json.load(f)

    ch_a = data_a.get("channels", {})
    ch_b = data_b.get("channels", {})

    dist_a = ch_a.get("dist_pct", [])
    dist_b = ch_b.get("dist_pct", [])
    speed_a = ch_a.get("speed", [])
    speed_b = ch_b.get("speed", [])

    if not dist_a or not dist_b or not speed_a or not speed_b:
        return "Insufficient telemetry data for comparison."

    time_a = lap_a["lap_time"] or data_a.get("lap_time_s", 0)
    time_b = lap_b["lap_time"] or data_b.get("lap_time_s", 0)

    result = {
        "lap_a": {"session": session_id_a, "lap": lap_number_a, "time": time_a},
        "lap_b": {"session": session_id_b, "lap": lap_number_b, "time": time_b},
        "delta_s": round(time_b - time_a, 3) if time_a and time_b else None,
    }

    # Interpolate both laps to common dist_pct grid (every 1%)
    import bisect

    def interp_at(dist_arr, val_arr, target_dist):
        """Linear interpolation of val at target_dist."""
        idx = bisect.bisect_left(dist_arr, target_dist)
        if idx == 0:
            return val_arr[0]
        if idx >= len(dist_arr):
            return val_arr[-1]
        d0, d1 = dist_arr[idx - 1], dist_arr[idx]
        if d1 == d0:
            return val_arr[idx]
        frac = (target_dist - d0) / (d1 - d0)
        return val_arr[idx - 1] + frac * (val_arr[idx] - val_arr[idx - 1])

    # Speed delta by section (divide track into 10 sections)
    n_sections = 10
    section_deltas = []
    for sec in range(n_sections):
        sec_start = sec / n_sections
        sec_end = (sec + 1) / n_sections
        sec_mid = (sec_start + sec_end) / 2

        speed_a_at = interp_at(dist_a, speed_a, sec_mid) * 3.6
        speed_b_at = interp_at(dist_b, speed_b, sec_mid) * 3.6

        section_deltas.append({
            "section": sec + 1,
            "dist_pct_range": f"{sec_start:.0%}-{sec_end:.0%}",
            "speed_a_kmh": round(speed_a_at, 1),
            "speed_b_kmh": round(speed_b_at, 1),
            "speed_diff_kmh": round(speed_b_at - speed_a_at, 1),
        })

    result["section_comparison"] = section_deltas

    # Time gained/lost per section (estimated from speed differences)
    # Time in section ≈ section_length / avg_speed
    if time_a and time_b:
        for sec_data in section_deltas:
            # Rough estimate: time proportional to 1/speed
            speed_a_ms = sec_data["speed_a_kmh"] / 3.6
            speed_b_ms = sec_data["speed_b_kmh"] / 3.6
            if speed_a_ms > 5 and speed_b_ms > 5:
                # Relative time: if B is faster in this section, B gains time
                # Delta ≈ section_time_a - section_time_b = L/vA - L/vB
                # As fraction of lap: (1/n) * (1/vA - 1/vB) * total_avg_speed * lap_time
                time_est_delta = (time_a / n_sections) * (1 - speed_a_ms / speed_b_ms)
                sec_data["time_delta_est_s"] = round(time_est_delta, 3)

    # Braking point comparison (significant braking zones)
    throttle_a = ch_a.get("throttle", [])
    throttle_b = ch_b.get("throttle", [])
    brake_a = ch_a.get("brake", [])
    brake_b = ch_b.get("brake", [])

    def find_brake_points(dist, brake, throttle):
        points = []
        in_brake = False
        for i in range(1, len(brake)):
            if not in_brake and brake[i] > 0.1 and brake[i - 1] <= 0.1:
                in_brake = True
                if i < len(dist):
                    points.append(round(dist[i], 4))
            elif in_brake and brake[i] <= 0.1:
                in_brake = False
        return points

    if brake_a and brake_b:
        bp_a = find_brake_points(dist_a, brake_a, throttle_a)
        bp_b = find_brake_points(dist_b, brake_b, throttle_b)
        result["brake_points_a"] = bp_a[:15]
        result["brake_points_b"] = bp_b[:15]

    # Corner min speeds comparison
    def find_corner_mins(dist, speed):
        threshold = max(speed) * 0.80
        corners = []
        in_corner = False
        corner_min = float("inf")
        corner_dist = 0
        for i in range(len(speed)):
            spd = speed[i] * 3.6
            if spd < threshold * 3.6:
                if not in_corner:
                    in_corner = True
                    corner_min = spd
                    corner_dist = dist[i] if i < len(dist) else 0
                elif spd < corner_min:
                    corner_min = spd
                    corner_dist = dist[i] if i < len(dist) else 0
            elif in_corner:
                in_corner = False
                corners.append({"dist": round(corner_dist, 4), "min_kmh": round(corner_min, 1)})
                corner_min = float("inf")
        return corners

    corners_a = find_corner_mins(dist_a, speed_a)
    corners_b = find_corner_mins(dist_b, speed_b)
    if corners_a and corners_b:
        # Match corners by proximity in dist_pct
        matched = []
        for ca in corners_a:
            best_match = min(corners_b, key=lambda cb: abs(cb["dist"] - ca["dist"]))
            if abs(best_match["dist"] - ca["dist"]) < 0.05:
                matched.append({
                    "dist_pct": ca["dist"],
                    "min_speed_a_kmh": ca["min_kmh"],
                    "min_speed_b_kmh": best_match["min_kmh"],
                    "diff_kmh": round(best_match["min_kmh"] - ca["min_kmh"], 1),
                })
        result["corner_speed_comparison"] = matched

    return json.dumps(result, indent=2)


@mcp_server.tool(
    name="get_live_bridge_data",
    description=(
        "Get real-time data from the iRacing bridge. Returns current telemetry "
        "(speed, RPM, gear, throttle, brake, fuel, lap, position), live setup "
        "(all chassis/aero parameters), session info (car, track, driver), "
        "and last completed lap. Use this to see what's happening RIGHT NOW."
    ),
)
def get_live_bridge_data() -> str:
    """Get current live data from the iRacing bridge."""
    if not _bridge_state or not _bridge_state.get("connected"):
        return "Bridge is not connected. No live data available."

    parts = []
    parts.append(f"Bridge connected: {_bridge_state.get('connected', False)}")
    parts.append(f"iRacing connected: {_bridge_state.get('iracing_connected', False)}")

    si = _bridge_state.get("session_info")
    if si:
        parts.append(f"Car: {si.get('car')} @ {si.get('track')} ({si.get('track_config', '')})")
        parts.append(f"Driver: {si.get('driver')}")

    t = _bridge_state.get("last_telemetry")
    if t:
        speed = (t.get("speed") or 0) * 3.6
        parts.append(f"\nLive telemetry:")
        parts.append(f"  Speed: {speed:.0f} km/h | RPM: {t.get('rpm', 0):.0f} | Gear: {t.get('gear', 0)}")
        parts.append(f"  Throttle: {(t.get('throttle') or 0)*100:.0f}% | Brake: {(t.get('brake') or 0)*100:.0f}%")
        parts.append(f"  Fuel: {t.get('fuel_level', 0):.2f}L ({(t.get('fuel_pct') or 0)*100:.1f}%)")
        parts.append(f"  Lap: {t.get('lap', 0)} | On track: {t.get('on_track')} | In garage: {t.get('in_garage')}")
        parts.append(f"  Best lap: {t.get('best_lap_time', 0):.3f}s | Last lap: {t.get('last_lap_time', 0):.3f}s")

    setup = _bridge_state.get("live_setup")
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
        for sec in ["Front", "LeftFront", "RightFront", "Rear", "LeftRear", "RightRear",
                     "BrakesInCarMisc", "Differential"]:
            section = chassis.get(sec, {})
            if section:
                parts.append(f"  {sec}:")
                for k, v in section.items():
                    parts.append(f"    {k}: {v}")

    last_lap = _bridge_state.get("last_lap")
    if last_lap:
        parts.append(f"\nLast completed lap: #{last_lap.get('lap_number')} — {last_lap.get('lap_time', 0):.3f}s")

    return "\n".join(parts) if parts else "No live data available."


@mcp_server.tool(
    name="validate_setup_change",
    description=(
        "Validate a proposed setup change against observed safe ranges from 120+ sessions. "
        "Returns whether it's safe, any warnings, and predicted side effects. "
        "Parameters: front_flap_angle_deg, rear_upper_flap_deg, rear_beam_wing_deg, "
        "front_ride_height_mm, torsion_bar_od_mm, rear_spring_rate_nmm, brake_bias_pct, "
        "diff_preload_nm, front_camber_deg, rear_camber_deg, etc."
    ),
)
def validate_setup_change_tool(parameter: str, new_value: float) -> str:
    """Validate a proposed setup change against constraints."""
    result = validate_setup_change(parameter, new_value)
    return json.dumps(result, default=str, indent=2)


@mcp_server.tool(
    name="predict_setup_effects",
    description=(
        "Predict what happens when a setup parameter is increased or decreased. "
        "Returns physics-based cause-and-effect analysis for each affected output. "
        "Direction must be 'increase' or 'decrease'."
    ),
)
def predict_setup_effects(parameter: str, direction: str = "increase") -> str:
    """Predict effects of a setup parameter change."""
    effects = predict_change_effects(parameter, direction)
    if effects:
        return "\n".join(effects)
    return f"No known effects for parameter '{parameter}'."


@mcp_server.tool(
    name="compare_session_setups",
    description=(
        "Compare the car setups from two sessions. Returns a diff showing what "
        "parameters changed, numeric deltas, and the lap time difference."
    ),
)
def compare_session_setups(session_id_a: str, session_id_b: str) -> str:
    """Compare setups from two sessions."""
    try:
        ensure_engineering_schema(DB_PATH)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        s1 = conn.execute(
            "SELECT setup_json, track, best_lap_time, session_date FROM sessions WHERE id = ?",
            (session_id_a,),
        ).fetchone()
        s2 = conn.execute(
            "SELECT setup_json, track, best_lap_time, session_date FROM sessions WHERE id = ?",
            (session_id_b,),
        ).fetchone()
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


@mcp_server.tool(
    name="log_recommendation",
    description=(
        "Persist a material coaching or setup recommendation in the engineering "
        "scorecard. Use after forming a serious recommendation. Required fields: "
        "category, observation, inference, confidence, action, validation_plan. "
        "Optional fields: session_id, track, lap_number, recommendation_type, "
        "focus_area, support_json."
    ),
)
def log_recommendation(payload_json: str) -> str:
    """Store a structured recommendation in the scorecard."""
    try:
        payload = json.loads(payload_json)
        saved = record_recommendation(payload, DB_PATH)
        return json.dumps(saved, indent=2)
    except Exception as e:
        return f"Error logging recommendation: {e}"


@mcp_server.tool(
    name="log_experiment",
    description=(
        "Persist a driver or setup experiment. Use this to track one-variable "
        "tests with hypothesis, expected_metric, baseline_metric_json, "
        "actual_metric_json, and result."
    ),
)
def log_experiment(payload_json: str) -> str:
    """Store an experiment log entry."""
    try:
        payload = json.loads(payload_json)
        saved = record_experiment(payload, DB_PATH)
        return json.dumps(saved, indent=2)
    except Exception as e:
        return f"Error logging experiment: {e}"


@mcp_server.tool(
    name="grade_recommendation",
    description=(
        "Grade a previously logged recommendation after the test outcome is known. "
        "Payload should contain recommendation_id plus grade and optional notes "
        "or actual_metric_json."
    ),
)
def grade_recommendation_tool(payload_json: str) -> str:
    """Grade a recommendation as improved/no_change/worse/mixed."""
    try:
        payload = json.loads(payload_json)
        recommendation_id = int(payload["recommendation_id"])
        grade_payload = {
            "grade": payload.get("grade"),
            "grade_notes": payload.get("grade_notes"),
            "actual_metric_json": payload.get("actual_metric_json"),
            "experiment_id": payload.get("experiment_id"),
            "status": payload.get("status"),
        }
        saved = grade_recommendation(recommendation_id, grade_payload, DB_PATH)
        return json.dumps(saved, indent=2)
    except Exception as e:
        return f"Error grading recommendation: {e}"


@mcp_server.tool(
    name="get_driver_model",
    description=(
        "Return the current validated driver model derived from graded "
        "recommendations and completed experiments. Optional track_name for "
        "track-specific strengths and weaknesses."
    ),
)
def get_driver_model_tool(track_name: str = "") -> str:
    """Fetch the current driver model."""
    try:
        model = get_driver_model(DB_PATH, track=track_name or None)
        return json.dumps(model, indent=2)
    except Exception as e:
        return f"Error loading driver model: {e}"


@mcp_server.tool(
    name="get_taxonomy_summary",
    description=(
        "Summarize recommendation and experiment outcomes grouped by category and "
        "focus area. Optional track_name filters to one track."
    ),
)
def get_taxonomy_summary_tool(track_name: str = "") -> str:
    """Fetch aggregated taxonomy data."""
    try:
        summary = get_taxonomy_summary(DB_PATH, track=track_name or None)
        return json.dumps(summary, indent=2)
    except Exception as e:
        return f"Error loading taxonomy summary: {e}"


@mcp_server.tool(
    name="get_session_debrief",
    description=(
        "Build a concise session debrief: best lap, median valid lap, top-5 spread, "
        "gap to track best, and any recommendations/experiments already attached "
        "to that session."
    ),
)
def get_session_debrief_tool(session_id: str) -> str:
    """Fetch a debrief for one session."""
    try:
        debrief = get_session_debrief(session_id, DB_PATH)
        return json.dumps(debrief, indent=2)
    except Exception as e:
        return f"Error loading session debrief: {e}"


@mcp_server.tool(
    name="list_engineering_log",
    description=(
        "List recent recommendations and experiments from the anti-BS engineering "
        "log. Optional track_name or session_id filters can narrow the view."
    ),
)
def list_engineering_log(track_name: str = "", session_id: str = "", limit: int = 10) -> str:
    """List recent engineering recommendations and experiments."""
    try:
        recommendations = list_recommendations(
            DB_PATH,
            limit=limit,
            track=track_name or None,
            session_id=session_id or None,
        )
        experiments = list_experiments(
            DB_PATH,
            limit=limit,
            track=track_name or None,
            session_id=session_id or None,
        )
        events = list_session_events(
            DB_PATH,
            limit=limit,
            track=track_name or None,
            session_id=session_id or None,
        )
        return json.dumps(
            {
                "recommendations": recommendations,
                "experiments": experiments,
                "events": events,
            },
            indent=2,
        )
    except Exception as e:
        return f"Error loading engineering log: {e}"


@mcp_server.tool(
    name="list_session_events",
    description=(
        "List recent important live/session events captured by bridge hooks and "
        "proactive engineer triggers. Optional track_name, session_id, "
        "event_type, or severity filters can narrow the results."
    ),
)
def list_session_events_tool(
    track_name: str = "",
    session_id: str = "",
    event_type: str = "",
    severity: str = "",
    limit: int = 10,
) -> str:
    """List recent session events."""
    try:
        events = list_session_events(
            DB_PATH,
            limit=limit,
            track=track_name or None,
            session_id=session_id or None,
            event_type=event_type or None,
            severity=severity or None,
        )
        return json.dumps(events, indent=2)
    except Exception as e:
        return f"Error loading session events: {e}"


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def _load_brain_file(filename: str) -> str:
    """Load a file from the brain directory."""
    path = BRAIN_DIR / filename
    if path.exists():
        return path.read_text()
    return ""


def build_system_prompt() -> str:
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

YOUR TOOLS:
You have both custom racing tools AND built-in tools. USE THEM.

Custom racing tools (via mcp__pitwall37__*):
- query_telemetry_db — SQL queries against 120+ sessions of historical data
- analyze_lap — deep 60Hz telemetry analysis for any lap
- compare_laps — channel-by-channel comparison of two laps
- get_live_bridge_data — real-time iRacing data from the bridge
- validate_setup_change — check setup changes against observed safe ranges
- predict_setup_effects — physics-based cause/effect for setup changes
- compare_session_setups — diff two session setups
- log_recommendation — persist a structured recommendation in the scorecard
- log_experiment — persist a test or one-variable experiment
- grade_recommendation — record whether a recommendation actually worked
- get_driver_model — load validated strengths/weaknesses from prior tests
- get_taxonomy_summary — summarize outcomes by focus area
- get_session_debrief — summarize one session's pace and attached tests
- list_engineering_log — inspect recent recommendations and experiments
- list_session_events — inspect important live/session hook events

Built-in tools (use freely):
- WebSearch / WebFetch — search for setup guides, racing techniques, track knowledge
- Bash — SSH to GPU box (ssh -i ~/.ssh/id_ed25519 russell@100.73.76.109), run scripts
- Read / Write — access brain files, save knowledge to brain/domain/
- Glob / Grep — search the codebase and data files

WORKING DIRECTORY: {PROJECT_DIR}
DATABASE: {DB_PATH}
BRAIN: {BRAIN_DIR}
GPU BOX SSH: ssh -i ~/.ssh/id_ed25519 russell@100.73.76.109

Be direct. Be data-backed. Push the driver to be better.
Celebrate progress but never accept "good enough."
If you don't know something, say so — then use your tools to find out.

ANTI-BS OUTPUT CONTRACT:
- Every meaningful recommendation MUST use this exact structure:
  Observation:
  Inference:
  Confidence: high | medium | low
  Source Tags: DATA / MODEL / HYPOTHESIS / REFERENCE
  Action:
  Validation:
- "Observation" must cite exact evidence: lap times, sectors, telemetry deltas,
  setup values, historical comparisons, or live bridge readings.
- "Action" must be a single concrete change unless the user explicitly asks for
  a broader plan.
- "Validation" must say what metric should move next: lap time, sector, minimum
  speed, brake point, hot pressure, ride height at speed, consistency, etc.
- If you cannot provide both Observation and Validation, DO NOT give advice.
  Say the evidence is insufficient and ask for or gather more data instead.
- Never hide uncertainty. If the conclusion is plausible but unproven, say so.
- For any material recommendation, call log_recommendation with the same
  structured fields before you answer.
- When reviewing prior work or building a long-term picture, prefer
  get_driver_model, get_taxonomy_summary, get_session_debrief,
  list_engineering_log, and list_session_events over vague memory.

The mission: make this driver an alien. Top 10 Garage61 leaderboards. Beat Tamas Simon.
"Greatest Race Car Driver Ever. He was built with Claude."
"""


# ---------------------------------------------------------------------------
# Agent SDK options builder
# ---------------------------------------------------------------------------

def build_agent_options(system_prompt: str | None = None) -> "ClaudeCodeOptions":
    """Build ClaudeCodeOptions for the race agent."""
    from claude_code_sdk import ClaudeCodeOptions

    return ClaudeCodeOptions(
        model="claude-sonnet-4-20250514",
        permission_mode="bypassPermissions",
        system_prompt=system_prompt or build_system_prompt(),
        allowed_tools=[
            "WebSearch", "WebFetch",
            "Bash",
            "Read", "Write",
            "Glob", "Grep",
            "mcp__pitwall37__query_telemetry_db",
            "mcp__pitwall37__analyze_lap",
            "mcp__pitwall37__compare_laps",
            "mcp__pitwall37__get_live_bridge_data",
            "mcp__pitwall37__validate_setup_change",
            "mcp__pitwall37__predict_setup_effects",
            "mcp__pitwall37__compare_session_setups",
            "mcp__pitwall37__log_recommendation",
            "mcp__pitwall37__log_experiment",
            "mcp__pitwall37__grade_recommendation",
            "mcp__pitwall37__get_driver_model",
            "mcp__pitwall37__get_taxonomy_summary",
            "mcp__pitwall37__get_session_debrief",
            "mcp__pitwall37__list_engineering_log",
            "mcp__pitwall37__list_session_events",
        ],
        mcp_servers={
            "pitwall37": {
                "type": "sdk",
                "name": "pitwall37",
                "instance": mcp_server._mcp_server,
            },
        },
        cwd=str(PROJECT_DIR),
        max_turns=25,
    )
