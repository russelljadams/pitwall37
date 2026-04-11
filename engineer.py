"""Race Engineer — Claude-powered telemetry analysis and coaching.
Provides contextual race engineering advice through the PitWall37 dashboard.
"""

import json
import os
import sqlite3
from pathlib import Path

import anthropic

from setup_model import get_setup_knowledge_for_prompt, compare_setups

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "pitwall37.db"

# Load setup constraints once at startup
_SETUP_CONSTRAINTS = get_setup_knowledge_for_prompt()

SYSTEM_PROMPT = """You are the head race engineer for a driver racing Super Formula Lights (Dallara F324) in iRacing. You have deep expertise in open-wheel car setup, telemetry analysis, and driver coaching.

Your role:
- Analyze telemetry data and provide actionable insights
- Recommend setup changes with clear explanations of the physics behind each change
- Coach driving technique based on data patterns
- Track progress over sessions and identify improvement trends
- Communicate clearly and concisely, like a professional race engineer on the pit wall

When analyzing data:
- Reference specific corners, sectors, and track positions
- Compare against the driver's own best laps, not arbitrary benchmarks
- Identify the biggest time-gain opportunities first
- Distinguish between car problems (setup) and driver technique issues
- Always explain WHY — the physics, the cause-and-effect

Setup knowledge for the Dallara F324:
- Turbocharged 1.6L 3-cylinder Toyota, ~275hp
- Front/rear wing angles control aero balance
- Torsion bar springs front, coil springs rear
- 2-way dampers (bump/rebound per corner)
- Front and rear anti-roll bars
- Limited-slip differential with preload
- Brake bias adjustable (typical 52-58% front)
- Cold tire pressures affect grip and temperature distribution
- Ride height affects aero performance (lower = more downforce, risk of bottoming)

TIRE TELEMETRY — READ THIS CAREFULLY:

The Dallara F324 does NOT have live onboard carcass temp sensors. This is by iRacing design — it simulates real-world data availability. In a real F324, a crew member measures carcass temps with a pyrometer at pit stops. So:

- Carcass temps (tempCL/CM/CR) ONLY update when the car pits. While on track, they stay at whatever value they had at pit exit (often ambient ~51°C if fresh tires).
- This is the same in EVERY session type — Test Drive, Practice, Hosted, Race. It's a car-level limitation, not a session-level one.
- Tire wear channels behave the same way — they don't update live on track for this car.

The driver uses Active Reset in test sessions ("suicide practices") — chasing a ghost lap for 60+ minutes, advancing the reset point forward with each completed lap. The tires are NOT resetting to fresh. Active Reset preserves tire state from the snapshot, and the snapshot moves forward. The carcass temp channels just don't report it.

What IS available and real:
- Surface temps (tempL/M/R): instantaneous IR sensor readings at 60Hz. These DO update live. They swing with corner loading (hot in turns, cool on straights). The telemetry averages these over the last quarter of the lap.
- Hot pressures: update live. Cold pressure → hot pressure delta shows real tire work. Typical buildup is 124 → 130-140 kPa over a lap.

When analyzing tire data:
- If you see temps in the 50-80°C range, these are surface temps. They are NORMAL and EXPECTED. Do NOT call them "cold" or suggest they indicate a problem.
- Use the temp spread across left/middle/right to diagnose camber and pressure — the relative differences still matter even with surface temps.
- Hot pressures are your most reliable tire data point for setup work.
- Never recommend tire pressure or camber changes based on absolute surface temp values. Only use relative differences between the three tread zones (inside/middle/outside).
- Do NOT say "tires are too cold" or "tires aren't at operating temperature." The data doesn't support that conclusion with surface temps.

SETUP CHANGE PROTOCOL:
When recommending ANY setup change, you MUST:
1. Check the change against the constraints below — never suggest values outside observed safe ranges
2. State the side effects — what OTHER parameters will be affected
3. If the change affects ride height, check the AeroCalculator values in the current setup context
4. If ride height at speed would approach 0mm, WARN the driver — the car will fail inspection
5. If you're unsure whether a value is legal, say so — don't guess

If the driver's current setup is provided in context, reference the actual AeroCalculator values (FrontRhAtSpeed, RearRhAtSpeed) when discussing ride height or aero changes.

""" + _SETUP_CONSTRAINTS + """

Keep responses focused and practical. No filler. Every sentence should either inform or recommend."""

CLIENT = anthropic.Anthropic()
MODEL = "claude-sonnet-4-20250514"
MODEL_FALLBACK = "claude-haiku-4-5-20251001"


class EngineerChat:
    def __init__(self):
        self.messages = []

    async def respond(self, user_message: str, context: dict = None):
        """Generate engineer response. Yields text chunks for streaming."""
        # Build context from current session/lap if provided
        context_text = ""
        if context:
            context_text = self._build_context(context)

        # Prepend context to user message if available
        full_message = user_message
        if context_text:
            full_message = f"[Current context]\n{context_text}\n\n[Driver message]\n{user_message}"

        self.messages.append({"role": "user", "content": full_message})

        # Stream response, fall back to Haiku if Sonnet is overloaded
        model = MODEL
        try:
            stream_ctx = CLIENT.messages.stream(
                model=model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=self.messages,
            )
            with stream_ctx as stream:
                full_response = ""
                for text in stream.text_stream:
                    full_response += text
                    yield text
        except anthropic.APIStatusError as e:
            if "overloaded" in str(e).lower() or e.status_code == 529:
                model = MODEL_FALLBACK
                with CLIENT.messages.stream(
                    model=model,
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    messages=self.messages,
                ) as stream:
                    full_response = ""
                    for text in stream.text_stream:
                        full_response += text
                        yield text
            else:
                raise

        self.messages.append({"role": "assistant", "content": full_response})

        # Keep conversation manageable — trim to last 20 exchanges
        if len(self.messages) > 40:
            self.messages = self.messages[-40:]

    def _build_context(self, context: dict) -> str:
        """Build context string from session/lap data.
        Supports comparing two sessions when compare_session_id is provided."""
        parts = []
        session_id = context.get("session_id")
        lap_number = context.get("lap_number")
        compare_id = context.get("compare_session_id")

        if not session_id:
            return ""

        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row

            # Build primary session context
            parts.append("═══ PRIMARY SESSION ═══")
            parts.extend(self._session_context(conn, session_id, lap_number))

            # Build comparison session if requested
            if compare_id:
                parts.append("")
                parts.append("═══ COMPARISON SESSION ═══")
                parts.extend(self._session_context(conn, compare_id, None))

                # Setup diff
                s1 = conn.execute(
                    "SELECT setup_json FROM sessions WHERE id = ?", (session_id,)
                ).fetchone()
                s2 = conn.execute(
                    "SELECT setup_json FROM sessions WHERE id = ?", (compare_id,)
                ).fetchone()
                if s1 and s2 and s1["setup_json"] and s2["setup_json"]:
                    setup_a = json.loads(s1["setup_json"])
                    setup_b = json.loads(s2["setup_json"])
                    diff = compare_setups(setup_a, setup_b)
                    parts.append("")
                    parts.append("═══ SETUP DIFF (primary → comparison) ═══")
                    parts.append(diff)

                    # Lap time comparison
                    best_a = conn.execute(
                        "SELECT MIN(lap_time) as t FROM laps WHERE session_id = ? AND valid = 1 AND lap_time > 0",
                        (session_id,)
                    ).fetchone()
                    best_b = conn.execute(
                        "SELECT MIN(lap_time) as t FROM laps WHERE session_id = ? AND valid = 1 AND lap_time > 0",
                        (compare_id,)
                    ).fetchone()
                    if best_a and best_b and best_a["t"] and best_b["t"]:
                        delta = best_b["t"] - best_a["t"]
                        parts.append(f"\nBest lap delta: {delta:+.3f}s (comparison vs primary)")

            conn.close()
        except Exception as e:
            parts.append(f"[Error loading context: {e}]")

        return "\n".join(parts)

    def _session_context(self, conn, session_id: str, lap_number: int = None) -> list[str]:
        """Build context lines for a single session."""
        parts = []

        session = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if session:
            parts.append(f"Track: {session['track']} ({session['track_config']})")
            parts.append(f"Date: {session['session_date']}")
            parts.append(f"Conditions: Air {session['air_temp']}°C, Track {session['track_temp']}°C")
            parts.append(f"Best lap: {session['best_lap_time']:.3f}s" if session['best_lap_time'] else "No timed laps")

        # All valid laps summary
        laps = conn.execute("""
            SELECT lap_number, lap_time, sector_1, sector_2, sector_3,
                   avg_speed_ms, max_speed_ms, fuel_used
            FROM laps WHERE session_id = ? AND valid = 1 AND lap_time > 0
            ORDER BY lap_time
        """, (session_id,)).fetchall()

        if laps:
            parts.append(f"\nValid laps ({len(laps)}):")
            for l in laps:
                parts.append(
                    f"  Lap {l['lap_number']}: {l['lap_time']:.3f}s "
                    f"(S1={l['sector_1']:.3f} S2={l['sector_2']:.3f} S3={l['sector_3']:.3f}) "
                    f"top {l['max_speed_ms']*3.6:.0f}km/h, fuel {l['fuel_used']:.3f}L"
                )

        # Specific lap telemetry summary
        if lap_number:
            lap = conn.execute(
                "SELECT * FROM laps WHERE session_id = ? AND lap_number = ?",
                (session_id, lap_number),
            ).fetchone()

            if lap and lap["telemetry_file"]:
                telem_path = DATA_DIR / lap["telemetry_file"]
                if telem_path.exists():
                    with open(telem_path) as f:
                        telem = json.load(f)

                    ch = telem.get("channels", {})
                    parts.append(f"\nDetailed telemetry for Lap {lap_number}:")

                    speeds = ch.get("speed", [])
                    if speeds:
                        speeds_kmh = [s * 3.6 for s in speeds]
                        parts.append(f"  Speed: min {min(speeds_kmh):.0f}, max {max(speeds_kmh):.0f}, avg {sum(speeds_kmh)/len(speeds_kmh):.0f} km/h")

                    brakes = ch.get("brake", [])
                    if brakes:
                        brake_pct = sum(1 for b in brakes if b > 0.05) / len(brakes) * 100
                        max_brake = max(brakes)
                        parts.append(f"  Braking: {brake_pct:.1f}% of lap, max pressure {max_brake:.2f}")

                    throttle = ch.get("throttle", [])
                    if throttle:
                        full_thr = sum(1 for t in throttle if t > 0.95) / len(throttle) * 100
                        parts.append(f"  Full throttle: {full_thr:.1f}% of lap")

                    tire_end = telem.get("tire_end", {})
                    if tire_end:
                        parts.append("  Tire temps (O/M/I):")
                        for corner, td in tire_end.items():
                            temps = td.get("temp", [0, 0, 0])
                            wear = td.get("wear", [0, 0, 0])
                            parts.append(
                                f"    {corner}: {temps[0]:.0f}/{temps[1]:.0f}/{temps[2]:.0f}°C "
                                f"wear {wear[0]:.1f}/{wear[1]:.1f}/{wear[2]:.1f}%"
                            )

                    parts.append(
                        f"  Fuel: {telem.get('fuel_start_l', 0):.2f} → "
                        f"{telem.get('fuel_end_l', 0):.2f}L "
                        f"(used {telem.get('fuel_start_l', 0) - telem.get('fuel_end_l', 0):.3f}L)"
                    )

                    # Ride height data (actual measured, not garage estimate)
                    rh = telem.get("ride_height", {})
                    if rh:
                        parts.append("  Ride height (measured from telemetry):")
                        f_rh = rh.get("front_mm", {})
                        r_rh = rh.get("rear_mm", {})
                        if f_rh.get("avg"):
                            parts.append(f"    Front: min={f_rh['min']}mm avg={f_rh['avg']}mm max={f_rh['max']}mm")
                        if r_rh.get("avg"):
                            parts.append(f"    Rear: min={r_rh['min']}mm avg={r_rh['avg']}mm max={r_rh['max']}mm")
                        as_f = rh.get("at_speed_front_mm", {})
                        as_r = rh.get("at_speed_rear_mm", {})
                        if as_f.get("avg"):
                            parts.append(f"    At speed (>108km/h): Front min={as_f['min']}mm avg={as_f['avg']}mm | Rear min={as_r.get('min')}mm avg={as_r.get('avg')}mm")

            # Tire snapshots
            tires = conn.execute("""
                SELECT * FROM tire_snapshots
                WHERE session_id = ? AND lap_number = ?
            """, (session_id, lap_number)).fetchall()

            if tires:
                parts.append(f"\nTire data for Lap {lap_number}:")
                for t in tires:
                    parts.append(
                        f"  {t['corner']}: temps {t['temp_left']:.0f}/{t['temp_mid']:.0f}/{t['temp_right']:.0f}°C "
                        f"wear {t['wear_left']:.1f}/{t['wear_mid']:.1f}/{t['wear_right']:.1f}% "
                        f"pressure {t['cold_pressure']:.0f}→{t['hot_pressure']:.0f} kPa"
                    )

        # Setup — send full setup
        if session and session["setup_json"]:
            setup = json.loads(session["setup_json"])
            parts.append(f"\nCar setup:")

            aero_calc = setup.get("TiresAero", {}).get("AeroCalculator", {})
            if aero_calc:
                parts.append("  AeroCalculator (computed):")
                for k, v in aero_calc.items():
                    parts.append(f"    {k}: {v}")

            aero = setup.get("TiresAero", {}).get("AeroSetup", {})
            if aero:
                parts.append("  AeroSetup:")
                for k, v in aero.items():
                    parts.append(f"    {k}: {v}")

            chassis = setup.get("Chassis", {})
            for section_name in ["Front", "LeftFront", "RightFront",
                                 "Rear", "LeftRear", "RightRear",
                                 "BrakesInCarMisc", "Differential"]:
                section = chassis.get(section_name, {})
                if section:
                    parts.append(f"  {section_name}:")
                    for k, v in section.items():
                        parts.append(f"    {k}: {v}")

        return parts


def analyze_session(session_id: str) -> str:
    """Generate a session debrief analysis."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    laps = conn.execute("""
        SELECT * FROM laps WHERE session_id = ? AND valid = 1 AND lap_time > 0
        ORDER BY lap_time
    """, (session_id,)).fetchall()

    if not session or not laps:
        return "No valid data for this session."

    context = {
        "track": session["track"],
        "date": session["session_date"],
        "air_temp": session["air_temp"],
        "track_temp": session["track_temp"],
        "laps": [dict(l) for l in laps],
    }

    response = CLIENT.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Debrief this session:\n{json.dumps(context, indent=2, default=str)}\n\nGive me a concise session debrief: pace analysis, consistency, where the time is, what to work on next."
        }],
    )

    conn.close()
    return response.content[0].text
