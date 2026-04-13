"""PitWall37 Session Agent — silent observer that builds the session narrative.

The session agent is the data spine of PitWall37. It:
- Spawns when a bridge connects and a session is detected
- Silently accumulates context across the entire session
- Calls Claude at key moments to ANALYZE and LOG insights (not to talk to the driver)
- Produces a complete session narrative when the session ends
- Everything goes to the database — the YouTube pipeline reads from there later

The driver is DRIVING. They're not reading a dashboard or listening to radio calls.
The agent's job is to watch, understand, and write it all down.
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engineering_data import (
    DB_PATH as DEFAULT_DB_PATH,
    ensure_engineering_schema,
    get_driver_model,
    list_session_events,
    record_session_event,
)

log = logging.getLogger("pitwall37.session_agent")

# ---------------------------------------------------------------------------
# Session State — accumulated across the entire session, never reset per event
# ---------------------------------------------------------------------------

@dataclass
class LapRecord:
    number: int
    time: float  # 0 if invalid/untimed
    sectors: list[float] = field(default_factory=list)  # [s1, s2, s3]
    valid: bool = True
    fuel_used: float = 0.0
    fuel_remaining: float = 0.0
    tire_data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class SetupChange:
    lap: int
    timestamp: str
    update_count: Any = None
    setup_snapshot: dict = field(default_factory=dict)
    summary: str = ""


@dataclass
class AgentNote:
    lap: int | None
    timestamp: str
    note: str
    category: str = "observation"  # observation, recommendation, alert, milestone


@dataclass
class SessionState:
    """All accumulated knowledge about the current session."""

    # Identity
    car: str = ""
    track: str = ""
    track_config: str = ""
    track_id: int = 0
    driver: str = ""
    started_at: str = ""
    session_id: str | None = None

    # Laps (growing list — every lap recorded)
    laps: list[LapRecord] = field(default_factory=list)

    # Running stats (derived from laps, updated on each lap)
    session_best: float = 0.0
    session_best_lap_num: int = 0
    best_sectors: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    pace_trend: str = "unknown"  # improving, stable, degrading, unknown
    consistency: float = 0.0  # std dev of last N valid laps
    total_valid_laps: int = 0

    # Setup
    current_setup: dict = field(default_factory=dict)
    setup_changes: list[SetupChange] = field(default_factory=list)

    # Agent's running notes (internal narrative)
    notes: list[AgentNote] = field(default_factory=list)

    # Reference data (loaded at session start)
    track_pb: float = 0.0  # all-time PB at this track
    alien_reference: float = 0.0  # target time (Tamas Simon etc.)
    driver_model: dict = field(default_factory=dict)

    # Driver state
    on_track: bool = False
    in_garage: bool = False
    last_fuel_level: float = 0.0
    fuel_per_lap: float = 0.0

    # Timing
    last_agent_call_time: float = 0.0
    last_agent_call_lap: int = 0
    total_agent_calls: int = 0

    def valid_laps(self) -> list[LapRecord]:
        return [l for l in self.laps if l.valid and l.time > 0]

    def recent_valid_laps(self, n: int = 5) -> list[LapRecord]:
        return self.valid_laps()[-n:]

    def lap_times(self) -> list[float]:
        return [l.time for l in self.valid_laps()]

    def to_context_summary(self) -> str:
        """Build a concise context string for Claude prompts."""
        parts = []
        parts.append(f"Session: {self.car} @ {self.track} ({self.track_config or 'GP'})")
        parts.append(f"Started: {self.started_at}")

        valid = self.valid_laps()
        parts.append(f"Laps: {len(self.laps)} total, {len(valid)} valid")

        if self.session_best > 0:
            parts.append(f"Session best: {self.session_best:.3f}s (lap {self.session_best_lap_num})")
        if self.track_pb > 0:
            parts.append(f"All-time track PB: {self.track_pb:.3f}s")
            if self.session_best > 0:
                gap = self.session_best - self.track_pb
                parts.append(f"Gap to PB: {gap:+.3f}s")
        if self.alien_reference > 0:
            parts.append(f"Alien target: {self.alien_reference:.3f}s")
            if self.session_best > 0:
                gap = self.session_best - self.alien_reference
                parts.append(f"Gap to alien: {gap:+.3f}s")

        if self.pace_trend != "unknown":
            parts.append(f"Pace trend: {self.pace_trend}")
        if self.consistency > 0:
            parts.append(f"Consistency (last 5): {self.consistency:.3f}s std dev")

        if self.fuel_per_lap > 0:
            parts.append(f"Fuel per lap: {self.fuel_per_lap:.2f}L")
            if self.last_fuel_level > 0:
                est_laps = self.last_fuel_level / self.fuel_per_lap
                parts.append(f"Fuel remaining: {self.last_fuel_level:.1f}L (~{est_laps:.0f} laps)")

        # Recent laps
        recent = self.recent_valid_laps(5)
        if recent:
            lap_strs = []
            for l in recent:
                delta = ""
                if self.session_best > 0 and l.time > 0:
                    d = l.time - self.session_best
                    delta = f" ({d:+.3f})" if d != 0 else " (PB)"
                lap_strs.append(f"L{l.number}: {l.time:.3f}s{delta}")
            parts.append(f"Recent laps: {', '.join(lap_strs)}")

        # Setup changes
        if self.setup_changes:
            parts.append(f"Setup changes this session: {len(self.setup_changes)}")
            last_change = self.setup_changes[-1]
            parts.append(f"Last setup change: lap {last_change.lap} — {last_change.summary or 'details in setup data'}")

        # Agent notes
        if self.notes:
            recent_notes = self.notes[-3:]
            parts.append("Agent notes:")
            for n in recent_notes:
                parts.append(f"  [{n.category}] L{n.lap}: {n.note}")

        return "\n".join(parts)


# ---------------------------------------------------------------------------
# State update logic — pure functions that update state from events
# ---------------------------------------------------------------------------

def _update_running_stats(state: SessionState) -> None:
    """Recompute derived stats from current lap list."""
    valid = state.valid_laps()
    state.total_valid_laps = len(valid)

    if not valid:
        return

    times = [l.time for l in valid]
    best_time = min(times)
    best_lap = next(l for l in valid if l.time == best_time)
    state.session_best = best_time
    state.session_best_lap_num = best_lap.number

    # Best sectors
    for i in range(3):
        sector_times = [l.sectors[i] for l in valid if len(l.sectors) > i and l.sectors[i] > 0]
        if sector_times:
            state.best_sectors[i] = min(sector_times)

    # Consistency (std dev of last 5 valid laps)
    recent = times[-5:]
    if len(recent) >= 2:
        state.consistency = statistics.stdev(recent)

    # Pace trend (compare last 3 laps to the 3 before them)
    if len(times) >= 6:
        older = statistics.mean(times[-6:-3])
        newer = statistics.mean(times[-3:])
        delta = newer - older
        if delta < -0.15:
            state.pace_trend = "improving"
        elif delta > 0.15:
            state.pace_trend = "degrading"
        else:
            state.pace_trend = "stable"
    elif len(times) >= 3:
        # Simpler: are last 3 going up or down?
        if times[-1] < times[-2] < times[-3]:
            state.pace_trend = "improving"
        elif times[-1] > times[-2] > times[-3]:
            state.pace_trend = "degrading"
        else:
            state.pace_trend = "stable"


def update_state(state: SessionState, event: dict) -> None:
    """Update session state from a bridge event. Mutates state in place."""
    event_type = event.get("type", "")
    data = event.get("data", {})

    if event_type == "session_info":
        state.car = data.get("car", state.car)
        state.track = data.get("track", state.track)
        state.track_config = data.get("track_config", state.track_config)
        state.track_id = data.get("track_id", state.track_id)
        state.driver = data.get("driver", state.driver)
        if not state.started_at:
            state.started_at = datetime.now(timezone.utc).isoformat()

    elif event_type == "lap_complete":
        lap_time = data.get("lap_time", 0)
        lap_num = data.get("lap_number", len(state.laps) + 1)
        fuel = data.get("fuel_level", 0)

        lap = LapRecord(
            number=lap_num,
            time=lap_time,
            valid=lap_time > 0,
            fuel_remaining=fuel,
            metadata=data,
        )

        # Compute fuel used from previous lap
        if state.laps and state.last_fuel_level > 0 and fuel > 0:
            lap.fuel_used = state.last_fuel_level - fuel
            if lap.fuel_used > 0:
                # Running average fuel per lap
                valid_fuel = [l.fuel_used for l in state.laps if l.fuel_used > 0]
                valid_fuel.append(lap.fuel_used)
                state.fuel_per_lap = statistics.mean(valid_fuel)

        state.last_fuel_level = fuel
        state.laps.append(lap)
        _update_running_stats(state)

    elif event_type == "telemetry":
        state.on_track = data.get("on_track", state.on_track)
        state.in_garage = data.get("in_garage", state.in_garage)
        fuel = data.get("fuel_level", 0)
        if fuel > 0:
            state.last_fuel_level = fuel

    elif event_type in ("setup", "setup_change"):
        setup_data = data.get("setup", data)
        state.current_setup = setup_data
        if event_type == "setup_change":
            state.setup_changes.append(SetupChange(
                lap=len(state.laps),
                timestamp=datetime.now(timezone.utc).isoformat(),
                update_count=setup_data.get("UpdateCount"),
                setup_snapshot=setup_data,
            ))

    elif event_type == "state":
        sub_event = data.get("event", "")
        if sub_event == "on_track":
            state.on_track = True
            state.in_garage = False
        elif sub_event == "off_track":
            state.on_track = False
        elif sub_event == "in_garage":
            state.in_garage = True
            state.on_track = False


# ---------------------------------------------------------------------------
# Agent judgment — decides what events warrant a Claude call
# ---------------------------------------------------------------------------

@dataclass
class AgentDecision:
    """What the agent decided to do (or not do) about an event."""
    should_think: bool = False
    reason: str = ""
    priority: str = "normal"  # low, normal, high, critical
    prompt: str = ""
    actions: list[str] = field(default_factory=list)  # what to do with the response


def decide(state: SessionState, event: dict) -> AgentDecision:
    """Decide whether this event warrants a Claude call and what to ask.

    This is where judgment lives. The agent is selective — it doesn't react
    to every event, and it batches its thinking when possible.
    """
    event_type = event.get("type", "")
    data = event.get("data", {})
    now = time.time()

    # Rate limiting: don't call Claude more than once per 15 seconds
    time_since_last = now - state.last_agent_call_time
    min_interval = 15.0

    # --- Events that NEVER trigger a call ---
    if event_type in ("heartbeat", "telemetry", "bridge_connect", "pong"):
        return AgentDecision(should_think=False, reason="routine event")

    # --- Session start: log that a session began ---
    if event_type == "session_info" and state.total_valid_laps == 0:
        return AgentDecision(
            should_think=False,
            reason="session start — logged, no analysis needed yet",
            actions=["log_event_simple"],
        )

    # --- Lap complete: the main decision point ---
    if event_type == "lap_complete":
        lap_time = data.get("lap_time", 0)
        if lap_time <= 0:
            return AgentDecision(should_think=False, reason="invalid/untimed lap")

        is_track_pb = state.track_pb > 0 and lap_time < state.track_pb
        is_pb = state.session_best > 0 and lap_time <= state.session_best

        # All-time track PB — analyze why, this is a milestone
        if is_track_pb:
            return AgentDecision(
                should_think=True,
                reason="new all-time track PB",
                priority="critical",
                prompt=_build_track_pb_prompt(state, data),
                actions=["log_event"],
            )

        # Session PB — note it, analyze if we have enough context
        if is_pb and state.total_valid_laps >= 3:
            return AgentDecision(
                should_think=True,
                reason="new session PB",
                priority="high",
                prompt=_build_session_pb_prompt(state, data),
                actions=["log_event"],
            )

        # Pace degradation: 3+ laps each slower than the last
        recent = state.recent_valid_laps(3)
        if (len(recent) >= 3 and
                recent[-1].time > recent[-2].time > recent[-3].time and
                time_since_last >= min_interval):
            return AgentDecision(
                should_think=True,
                reason="pace degradation — 3 consecutive slower laps",
                priority="normal",
                prompt=_build_pace_degradation_prompt(state),
                actions=["log_event"],
            )

        # Periodic analysis: every 10 valid laps
        if (state.total_valid_laps > 0 and
                state.total_valid_laps % 10 == 0 and
                time_since_last >= min_interval):
            return AgentDecision(
                should_think=True,
                reason=f"periodic analysis at lap {state.total_valid_laps}",
                priority="low",
                prompt=_build_periodic_analysis_prompt(state),
                actions=["log_event"],
            )

        return AgentDecision(should_think=False, reason="routine lap")

    # --- Setup change ---
    if event_type == "setup_change":
        if time_since_last >= min_interval:
            return AgentDecision(
                should_think=True,
                reason="setup change detected",
                priority="normal",
                prompt=_build_setup_change_prompt(state),
                actions=["log_event"],
            )

    # --- Stint boundary: driver enters garage after track time ---
    if event_type == "state":
        sub_event = data.get("event", "")
        if sub_event == "in_garage" and state.total_valid_laps >= 3:
            if time_since_last >= min_interval:
                return AgentDecision(
                    should_think=True,
                    reason="stint complete — driver entered garage",
                    priority="normal",
                    prompt=_build_stint_analysis_prompt(state),
                    actions=["log_event"],
                )

    return AgentDecision(should_think=False, reason="no action needed")


# ---------------------------------------------------------------------------
# Prompt builders — construct context-rich prompts for Claude
# ---------------------------------------------------------------------------

def _analysis_preamble() -> str:
    return (
        "You are the PitWall37 session observer. You are NOT talking to the driver. "
        "You are writing analytical notes that will be stored in the database and later "
        "used to generate YouTube episode scripts, post-session debriefs, and content. "
        "Write in third person about the driver. Be specific with data.\n\n"
        "CRITICAL BOUNDARIES:\n"
        "- ONLY reference data you can actually see in the session context below.\n"
        "- NEVER invent sector times, corner speeds, or telemetry you don't have.\n"
        "- If you don't know WHY pace changed, say 'cause unclear from available data' "
        "— don't guess.\n"
        "- Lap times, fuel, setup changes, and lap counts are REAL. Everything else is "
        "inference — label it as such.\n"
        "- These notes are the raw material for storytelling, but the story must be "
        "grounded in what actually happened. No fiction. No embellishment.\n"
    )


def _build_session_pb_prompt(state: SessionState, lap_data: dict) -> str:
    lap_time = lap_data.get("lap_time", 0)
    lap_num = lap_data.get("lap_number", 0)
    prev_best = 0
    for l in state.valid_laps()[:-1]:
        if prev_best == 0 or l.time < prev_best:
            prev_best = l.time
    improvement = prev_best - lap_time if prev_best > 0 else 0

    return (
        f"{_analysis_preamble()}\n\n"
        f"[SESSION PB] Lap {lap_num}: {lap_time:.3f}s — improved by {improvement:.3f}s\n\n"
        f"Session context:\n{state.to_context_summary()}\n\n"
        f"Analyze this PB. What likely caused the improvement? Did a setup change precede it? "
        f"Where in the session does this fall (early exploration vs late refinement)? "
        f"Note the gap to track PB and alien target. 3-4 sentences of analytical notes."
    )


def _build_track_pb_prompt(state: SessionState, lap_data: dict) -> str:
    lap_time = lap_data.get("lap_time", 0)
    lap_num = lap_data.get("lap_number", 0)
    old_pb = state.track_pb
    improvement = old_pb - lap_time if old_pb > 0 else 0

    return (
        f"{_analysis_preamble()}\n\n"
        f"[ALL-TIME TRACK PB] Lap {lap_num}: {lap_time:.3f}s — beat previous PB of {old_pb:.3f}s by {improvement:.3f}s\n\n"
        f"Session context:\n{state.to_context_summary()}\n\n"
        f"This is a major milestone — new all-time personal best at this track. "
        f"Analyze what led to this: setup changes during the session, lap count (was the "
        f"driver in the zone?), progression through the session. How much gap remains to "
        f"the alien target? What's the narrative arc here? 4-5 sentences."
    )


def _build_pace_degradation_prompt(state: SessionState) -> str:
    recent = state.recent_valid_laps(5)
    lap_strs = ", ".join(f"L{l.number}: {l.time:.3f}s" for l in recent)

    return (
        f"{_analysis_preamble()}\n\n"
        f"[PACE DEGRADATION] Last laps trending slower: {lap_strs}\n\n"
        f"Session context:\n{state.to_context_summary()}\n\n"
        f"Pace is dropping. Analyze possible causes: tire degradation (how many laps on "
        f"this stint?), concentration fade (session length?), or just inconsistency? "
        f"Note the magnitude of the drop and whether it's a story-worthy moment "
        f"(struggled and recovered later?) or just normal tire fall-off. 2-3 sentences."
    )


def _build_periodic_analysis_prompt(state: SessionState) -> str:
    return (
        f"{_analysis_preamble()}\n\n"
        f"[PERIODIC ANALYSIS] {state.total_valid_laps} valid laps completed.\n\n"
        f"Session context:\n{state.to_context_summary()}\n\n"
        f"Mid-session snapshot. Summarize: current pace relative to PB and alien, "
        f"consistency trend, any setup changes and their apparent effect, "
        f"overall session trajectory (improving? plateaued? struggling?). "
        f"This note helps build the session narrative arc. 3-4 sentences."
    )


def _build_setup_change_prompt(state: SessionState) -> str:
    last_change = state.setup_changes[-1] if state.setup_changes else None
    change_info = ""
    if last_change:
        change_info = f"UpdateCount: {last_change.update_count}"

    return (
        f"{_analysis_preamble()}\n\n"
        f"[SETUP CHANGE] {change_info}\n\n"
        f"Session context:\n{state.to_context_summary()}\n\n"
        f"Note the setup change for the narrative. Use get_live_bridge_data if needed "
        f"to see what changed. Record what was changed and what the pace was before the "
        f"change — we'll compare after a few more laps to see if it helped. 2-3 sentences."
    )


def _build_stint_analysis_prompt(state: SessionState) -> str:
    return (
        f"{_analysis_preamble()}\n\n"
        f"[STINT COMPLETE] Driver returned to garage after {state.total_valid_laps} valid laps.\n\n"
        f"Session context:\n{state.to_context_summary()}\n\n"
        f"Stint summary for the narrative: best lap, consistency, pace evolution during "
        f"the stint, effect of any setup changes. Was this a productive stint or a "
        f"frustrating one? What's the story? 3-5 sentences."
    )


def _build_session_end_prompt(state: SessionState) -> str:
    return (
        f"{_analysis_preamble()}\n\n"
        f"[SESSION COMPLETE] Full session is over.\n\n"
        f"Full session context:\n{state.to_context_summary()}\n\n"
        f"Write the complete session narrative. This is the primary source material for "
        f"a YouTube episode script. Cover:\n"
        f"- Total laps and session duration feel\n"
        f"- Best lap vs track PB vs alien target — did records fall?\n"
        f"- The arc: how did pace evolve from first lap to last?\n"
        f"- Key moments: PBs, setup changes and their effects, struggles, breakthroughs\n"
        f"- Consistency: was the driver dialed in or all over the place?\n"
        f"- What worked and what didn't\n"
        f"- Where the remaining time lives (sectors, corners, technique vs setup)\n"
        f"- One priority for the next session\n\n"
        f"Write this as a narrative, not a bullet list. 8-12 sentences. "
        f"This should read like something a commentator could turn into a show segment."
    )


# ---------------------------------------------------------------------------
# Action dispatch — log everything to the database
# ---------------------------------------------------------------------------

@dataclass
class AgentActions:
    """Configuration for the session agent."""
    db_path: Path = field(default_factory=lambda: DEFAULT_DB_PATH)


def log_agent_analysis(
    text: str,
    decision: AgentDecision,
    state: SessionState,
    db_path: Path,
) -> None:
    """Write the agent's analysis to the session_events table."""
    try:
        severity = {
            "critical": "critical",
            "high": "notable",
            "normal": "info",
            "low": "info",
        }.get(decision.priority, "info")

        # Clean up the event type for DB storage
        event_type = decision.reason.replace(" — ", "_").replace(" ", "_").lower()
        if len(event_type) > 50:
            event_type = event_type[:50]

        record_session_event(
            {
                "track": state.track or None,
                "source": "session_agent",
                "event_type": event_type,
                "severity": severity,
                "title": decision.reason,
                "summary": text[:500],
                "lap_number": len(state.laps) if state.laps else None,
                "metadata_json": {
                    "priority": decision.priority,
                    "lap_count": state.total_valid_laps,
                    "session_best": state.session_best,
                    "full_text": text,  # Store the complete analysis
                },
            },
            db_path,
        )
    except Exception:
        log.exception("Failed to log session agent analysis")


# ---------------------------------------------------------------------------
# Claude SDK integration — the actual thinking
# ---------------------------------------------------------------------------

async def think(state: SessionState, decision: AgentDecision) -> str:
    """Call Claude with the accumulated session context and get a response.

    Returns the text response from Claude.
    """
    try:
        from claude_code_sdk import ClaudeCodeOptions, query

        from race_agent import build_system_prompt, mcp_server, set_bridge_state

        options = ClaudeCodeOptions(
            model="claude-sonnet-4-20250514",
            permission_mode="bypassPermissions",
            system_prompt=build_system_prompt(),
            allowed_tools=[
                "mcp__pitwall37__query_telemetry_db",
                "mcp__pitwall37__analyze_lap",
                "mcp__pitwall37__compare_laps",
                "mcp__pitwall37__get_live_bridge_data",
                "mcp__pitwall37__validate_setup_change",
                "mcp__pitwall37__predict_setup_effects",
                "mcp__pitwall37__compare_session_setups",
                "mcp__pitwall37__log_recommendation",
                "mcp__pitwall37__get_driver_model",
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
            cwd=str(Path(__file__).parent),
            max_turns=5,  # Keep proactive responses quick
        )

        text_parts = []
        async for msg in query(prompt=decision.prompt, options=options):
            if hasattr(msg, "content"):
                # AssistantMessage
                for block in msg.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
            # ResultMessage has session_id, cost, etc. — we just want text

        return "".join(text_parts) or "(no response)"

    except Exception as e:
        log.error("Session agent think() failed: %s", e, exc_info=True)
        return f"(agent error: {e})"


# ---------------------------------------------------------------------------
# Reference data loader — sets up context at session start
# ---------------------------------------------------------------------------

def load_reference_data(state: SessionState, db_path: Path | str = DEFAULT_DB_PATH) -> None:
    """Load track PB, alien references, and driver model into session state."""
    import sqlite3

    ensure_engineering_schema(db_path)

    if not state.track:
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Track PB
        row = conn.execute(
            """
            SELECT MIN(l.lap_time) as best
            FROM laps l JOIN sessions s ON s.id = l.session_id
            WHERE s.track = ? AND l.valid = 1 AND l.lap_time > 0
            """,
            (state.track,),
        ).fetchone()
        if row and row["best"]:
            state.track_pb = row["best"]

        conn.close()
    except Exception:
        log.exception("Failed to load reference data")

    # Driver model
    try:
        state.driver_model = get_driver_model(db_path, track=state.track)
    except Exception:
        log.exception("Failed to load driver model")


# ---------------------------------------------------------------------------
# The main agent loop
# ---------------------------------------------------------------------------

class SessionAgent:
    """Persistent agent that lives for an entire session."""

    def __init__(
        self,
        actions: AgentActions,
        db_path: Path | str = DEFAULT_DB_PATH,
    ):
        self.state = SessionState()
        self.queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)
        self.actions = actions
        self.db_path = Path(db_path)
        self._task: asyncio.Task | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start the agent loop."""
        if self.is_running:
            log.warning("Session agent already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        log.info("Session agent started")

    async def stop(self) -> str | None:
        """Stop the agent loop and return a final session narrative."""
        self._running = False
        narrative_text = None

        # Generate session narrative if we had a real session
        if self.state.total_valid_laps >= 3:
            try:
                prompt = _build_session_end_prompt(self.state)
                decision = AgentDecision(
                    should_think=True,
                    reason="session_complete",
                    priority="high",
                    prompt=prompt,
                    actions=["log_event"],
                )
                narrative_text = await think(self.state, decision)
                log_agent_analysis(narrative_text, decision, self.state, self.db_path)
            except Exception:
                log.exception("Failed to generate session narrative")

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        log.info(
            "Session agent stopped. %d laps, best: %.3f",
            self.state.total_valid_laps,
            self.state.session_best,
        )
        return narrative_text

    async def push_event(self, event: dict) -> None:
        """Push an event to the agent's queue (called by bridge handler)."""
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest event on overflow — telemetry events are high volume
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self.queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def _run(self) -> None:
        """Main agent loop — consume events, update state, decide, act."""
        log.info("Session agent loop started")

        while self._running:
            try:
                # Wait for next event (with timeout so we can check _running flag)
                try:
                    event = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Update state
                update_state(self.state, event)

                # Load reference data on first session_info
                if event.get("type") == "session_info" and self.state.track_pb == 0:
                    load_reference_data(self.state, self.db_path)

                # Decide what to do
                decision = decide(self.state, event)

                # Log simple events without calling Claude
                if "log_event_simple" in decision.actions:
                    try:
                        record_session_event(
                            {
                                "track": self.state.track or None,
                                "source": "session_agent",
                                "event_type": event.get("type", "unknown"),
                                "severity": "info",
                                "title": decision.reason,
                                "summary": f"{self.state.car} @ {self.state.track}" if self.state.track else "",
                                "metadata_json": event.get("data", {}),
                            },
                            self.db_path,
                        )
                    except Exception:
                        log.exception("Failed to log simple event")

                if not decision.should_think:
                    continue

                # Think
                log.info(
                    "Agent thinking: %s (priority: %s)",
                    decision.reason,
                    decision.priority,
                )

                text = await think(self.state, decision)
                self.state.last_agent_call_time = time.time()
                self.state.last_agent_call_lap = len(self.state.laps)
                self.state.total_agent_calls += 1

                # Add to agent notes
                self.state.notes.append(AgentNote(
                    lap=len(self.state.laps),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    note=text[:200],
                    category=decision.reason.split(" — ")[0] if " — " in decision.reason else decision.reason,
                ))

                # Log analysis to the database
                log_agent_analysis(text, decision, self.state, self.db_path)

                log.info(
                    "Agent responded (%d chars, call #%d)",
                    len(text),
                    self.state.total_agent_calls,
                )

            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Error in session agent loop")
                await asyncio.sleep(1)  # Don't spin on repeated errors

        log.info("Session agent loop ended")


# ---------------------------------------------------------------------------
# Module-level agent instance (managed by pitwall37.py)
# ---------------------------------------------------------------------------

_active_agent: SessionAgent | None = None


def get_active_agent() -> SessionAgent | None:
    """Get the currently active session agent (if any)."""
    return _active_agent


async def start_session_agent(
    actions: AgentActions,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> SessionAgent:
    """Start a new session agent, stopping any existing one."""
    global _active_agent

    if _active_agent and _active_agent.is_running:
        log.info("Stopping previous session agent before starting new one")
        await _active_agent.stop()

    _active_agent = SessionAgent(actions=actions, db_path=db_path)
    await _active_agent.start()
    return _active_agent


async def stop_session_agent() -> str | None:
    """Stop the active session agent and return its debrief."""
    global _active_agent
    if _active_agent and _active_agent.is_running:
        debrief = await _active_agent.stop()
        _active_agent = None
        return debrief
    _active_agent = None
    return None
