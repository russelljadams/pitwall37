"""Shared engineering data layer for PitWall37.

Stores anti-BS recommendations, experiments, and derived driver-model signals.
These records are designed to keep the LLM honest by forcing every meaningful
claim into an observation -> inference -> action -> validation loop.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "data" / "pitwall37.db"

VALID_CONFIDENCE = {"low", "medium", "high"}
VALID_RECOMMENDATION_TYPES = {"driver", "setup"}
VALID_RECOMMENDATION_GRADES = {"untested", "improved", "no_change", "worse", "mixed"}
VALID_EXPERIMENT_RESULTS = {"planned", "improved", "no_change", "worse", "mixed", "abandoned"}
VALID_EVENT_SEVERITIES = {"info", "notable", "warning", "critical"}

FOCUS_AREAS = [
    "high_speed_aero",
    "medium_speed_rotation",
    "slow_speed_traction",
    "chicane_direction_change",
    "brake_stability",
    "brake_release_rotation",
    "exit_commitment",
    "consistency",
    "setup_platform",
    "setup_aero_balance",
    "setup_diff",
    "setup_damping",
    "setup_tire_pressure",
    "setup_ride_height",
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _json_loads(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _normalize_confidence(value: str | None, default: str = "medium") -> str:
    value = (value or default).strip().lower()
    if value not in VALID_CONFIDENCE:
        return default
    return value


def _normalize_focus_area(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _normalize_track(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"Missing required field: {key}")
    return value


def ensure_engineering_schema(db_path: Path | str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'engineer',
            session_id TEXT,
            lap_number INTEGER,
            track TEXT,
            recommendation_type TEXT NOT NULL DEFAULT 'driver',
            category TEXT NOT NULL,
            focus_area TEXT,
            observation TEXT NOT NULL,
            inference TEXT NOT NULL,
            confidence TEXT NOT NULL,
            action TEXT NOT NULL,
            validation_plan TEXT NOT NULL,
            support_json TEXT,
            status TEXT NOT NULL DEFAULT 'proposed',
            grade TEXT NOT NULL DEFAULT 'untested',
            grade_notes TEXT,
            actual_metric_json TEXT,
            experiment_id INTEGER,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        );

        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            session_id TEXT,
            track TEXT,
            lap_range TEXT,
            category TEXT NOT NULL,
            focus_area TEXT,
            change_type TEXT NOT NULL,
            change_json TEXT,
            hypothesis TEXT NOT NULL,
            expected_metric TEXT NOT NULL,
            baseline_metric_json TEXT,
            actual_metric_json TEXT,
            result TEXT NOT NULL DEFAULT 'planned',
            confidence_before TEXT NOT NULL DEFAULT 'medium',
            confidence_after TEXT,
            notes TEXT,
            recommendation_id INTEGER,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (recommendation_id) REFERENCES recommendations(id)
        );

        CREATE TABLE IF NOT EXISTS driver_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            track TEXT,
            signal_type TEXT NOT NULL,
            category TEXT NOT NULL,
            focus_area TEXT,
            evidence TEXT NOT NULL,
            confidence TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'derived',
            strength REAL NOT NULL DEFAULT 0,
            metadata_json TEXT
        );

        CREATE TABLE IF NOT EXISTS session_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            session_id TEXT,
            track TEXT,
            lap_number INTEGER,
            source TEXT NOT NULL DEFAULT 'bridge',
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            title TEXT NOT NULL,
            summary TEXT,
            metadata_json TEXT,
            recommendation_id INTEGER,
            experiment_id INTEGER,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (recommendation_id) REFERENCES recommendations(id),
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        );

        CREATE INDEX IF NOT EXISTS idx_recommendations_track_created
            ON recommendations(track, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_recommendations_session_created
            ON recommendations(session_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_experiments_track_created
            ON experiments(track, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_experiments_session_created
            ON experiments(session_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_driver_signals_track_strength
            ON driver_signals(track, strength DESC, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_session_events_track_created
            ON session_events(track, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_session_events_session_created
            ON session_events(session_id, created_at DESC);
        """
    )
    conn.commit()
    conn.close()


def _get_db(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    ensure_engineering_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _session_track(conn: sqlite3.Connection, session_id: str | None) -> str | None:
    if not session_id:
        return None
    row = conn.execute(
        "SELECT track FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    return row["track"] if row else None


def _deserialize_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for key in ("support_json", "actual_metric_json", "change_json", "baseline_metric_json", "metadata_json"):
        if key in data:
            data[key] = _json_loads(data[key])
    return data


def record_session_event(
    payload: dict[str, Any],
    db_path: Path | str = DB_PATH,
) -> dict[str, Any]:
    conn = _get_db(db_path)
    session_id = payload.get("session_id")
    track = _normalize_track(payload.get("track")) or _session_track(conn, session_id)
    severity = (payload.get("severity") or "info").strip().lower()
    if severity not in VALID_EVENT_SEVERITIES:
        severity = "info"
    event_type = _require_text(payload, "event_type")
    title = _require_text(payload, "title")
    now = payload.get("created_at") or _utcnow()
    cur = conn.execute(
        """
        INSERT INTO session_events (
            created_at, session_id, track, lap_number, source, event_type,
            severity, title, summary, metadata_json, recommendation_id, experiment_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            session_id,
            track,
            payload.get("lap_number"),
            (payload.get("source") or "bridge").strip(),
            event_type,
            severity,
            title,
            (payload.get("summary") or "").strip() or None,
            _json_dumps(payload.get("metadata_json")),
            payload.get("recommendation_id"),
            payload.get("experiment_id"),
        ),
    )
    event_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM session_events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    return _deserialize_row(row) or {}


def list_session_events(
    db_path: Path | str = DB_PATH,
    *,
    limit: int = 50,
    track: str | None = None,
    session_id: str | None = None,
    event_type: str | None = None,
    severity: str | None = None,
) -> list[dict[str, Any]]:
    conn = _get_db(db_path)
    clauses = []
    params: list[Any] = []
    if track:
        clauses.append("track = ?")
        params.append(track)
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if severity:
        clauses.append("severity = ?")
        params.append(severity)
    sql = "SELECT * FROM session_events"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_deserialize_row(row) for row in rows if row]


def record_recommendation(
    payload: dict[str, Any],
    db_path: Path | str = DB_PATH,
) -> dict[str, Any]:
    conn = _get_db(db_path)
    session_id = payload.get("session_id")
    track = _normalize_track(payload.get("track")) or _session_track(conn, session_id)
    recommendation_type = (payload.get("recommendation_type") or "driver").strip().lower()
    if recommendation_type not in VALID_RECOMMENDATION_TYPES:
        recommendation_type = "driver"
    category = _require_text(payload, "category")
    observation = _require_text(payload, "observation")
    inference = _require_text(payload, "inference")
    action = _require_text(payload, "action")
    validation_plan = _require_text(payload, "validation_plan")

    now = _utcnow()
    cur = conn.execute(
        """
        INSERT INTO recommendations (
            created_at, updated_at, source, session_id, lap_number, track,
            recommendation_type, category, focus_area, observation, inference,
            confidence, action, validation_plan, support_json, status, grade,
            grade_notes, actual_metric_json, experiment_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            now,
            (payload.get("source") or "engineer").strip(),
            session_id,
            payload.get("lap_number"),
            track,
            recommendation_type,
            category,
            _normalize_focus_area(payload.get("focus_area")),
            observation,
            inference,
            _normalize_confidence(payload.get("confidence")),
            action,
            validation_plan,
            _json_dumps(payload.get("support_json")),
            (payload.get("status") or "proposed").strip(),
            (payload.get("grade") or "untested").strip(),
            (payload.get("grade_notes") or "").strip() or None,
            _json_dumps(payload.get("actual_metric_json")),
            payload.get("experiment_id"),
        ),
    )
    rec_id = cur.lastrowid
    conn.commit()
    refresh_driver_signals_conn(conn)
    row = conn.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,)).fetchone()
    conn.close()
    return _deserialize_row(row) or {}


def list_recommendations(
    db_path: Path | str = DB_PATH,
    *,
    limit: int = 50,
    track: str | None = None,
    session_id: str | None = None,
    status: str | None = None,
    grade: str | None = None,
) -> list[dict[str, Any]]:
    conn = _get_db(db_path)
    clauses = []
    params: list[Any] = []
    if track:
        clauses.append("track = ?")
        params.append(track)
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if grade:
        clauses.append("grade = ?")
        params.append(grade)

    sql = "SELECT * FROM recommendations"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_deserialize_row(row) for row in rows if row]


def grade_recommendation(
    recommendation_id: int,
    payload: dict[str, Any],
    db_path: Path | str = DB_PATH,
) -> dict[str, Any] | None:
    conn = _get_db(db_path)
    now = _utcnow()
    grade = (payload.get("grade") or "untested").strip()
    if grade not in VALID_RECOMMENDATION_GRADES:
        grade = "untested"
    status = "graded" if grade != "untested" else (payload.get("status") or "proposed")
    conn.execute(
        """
        UPDATE recommendations
        SET updated_at = ?, status = ?, grade = ?, grade_notes = ?,
            actual_metric_json = ?, experiment_id = COALESCE(?, experiment_id)
        WHERE id = ?
        """,
        (
            now,
            status,
            grade,
            (payload.get("grade_notes") or "").strip() or None,
            _json_dumps(payload.get("actual_metric_json")),
            payload.get("experiment_id"),
            recommendation_id,
        ),
    )
    conn.commit()
    refresh_driver_signals_conn(conn)
    row = conn.execute("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)).fetchone()
    conn.close()
    return _deserialize_row(row)


def record_experiment(
    payload: dict[str, Any],
    db_path: Path | str = DB_PATH,
) -> dict[str, Any]:
    conn = _get_db(db_path)
    session_id = payload.get("session_id")
    track = _normalize_track(payload.get("track")) or _session_track(conn, session_id)
    change_type = (payload.get("change_type") or "driver").strip().lower()
    if change_type not in VALID_RECOMMENDATION_TYPES:
        change_type = "driver"
    result = (payload.get("result") or "planned").strip()
    if result not in VALID_EXPERIMENT_RESULTS:
        result = "planned"
    category = _require_text(payload, "category")
    hypothesis = _require_text(payload, "hypothesis")
    expected_metric = _require_text(payload, "expected_metric")

    now = _utcnow()
    cur = conn.execute(
        """
        INSERT INTO experiments (
            created_at, updated_at, session_id, track, lap_range, category,
            focus_area, change_type, change_json, hypothesis, expected_metric,
            baseline_metric_json, actual_metric_json, result, confidence_before,
            confidence_after, notes, recommendation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            now,
            session_id,
            track,
            (payload.get("lap_range") or "").strip() or None,
            category,
            _normalize_focus_area(payload.get("focus_area")),
            change_type,
            _json_dumps(payload.get("change_json")),
            hypothesis,
            expected_metric,
            _json_dumps(payload.get("baseline_metric_json")),
            _json_dumps(payload.get("actual_metric_json")),
            result,
            _normalize_confidence(payload.get("confidence_before")),
            payload.get("confidence_after"),
            (payload.get("notes") or "").strip() or None,
            payload.get("recommendation_id"),
        ),
    )
    experiment_id = cur.lastrowid
    conn.commit()
    refresh_driver_signals_conn(conn)
    row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
    conn.close()
    return _deserialize_row(row) or {}


def list_experiments(
    db_path: Path | str = DB_PATH,
    *,
    limit: int = 50,
    track: str | None = None,
    session_id: str | None = None,
    result: str | None = None,
) -> list[dict[str, Any]]:
    conn = _get_db(db_path)
    clauses = []
    params: list[Any] = []
    if track:
        clauses.append("track = ?")
        params.append(track)
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if result:
        clauses.append("result = ?")
        params.append(result)

    sql = "SELECT * FROM experiments"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_deserialize_row(row) for row in rows if row]


def _collect_signal_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add_row(
        track: str | None,
        category: str,
        focus_area: str | None,
        outcome: str,
        source_table: str,
    ) -> None:
        rows.append(
            {
                "track": track,
                "category": category,
                "focus_area": focus_area,
                "outcome": outcome,
                "source_table": source_table,
            }
        )

    recs = conn.execute(
        """
        SELECT track, category, focus_area, grade
        FROM recommendations
        WHERE grade IN ('improved', 'no_change', 'worse', 'mixed')
        """
    ).fetchall()
    for row in recs:
        add_row(row["track"], row["category"], row["focus_area"], row["grade"], "recommendations")

    exps = conn.execute(
        """
        SELECT track, category, focus_area, result
        FROM experiments
        WHERE result IN ('improved', 'no_change', 'worse', 'mixed')
        """
    ).fetchall()
    for row in exps:
        add_row(row["track"], row["category"], row["focus_area"], row["result"], "experiments")

    return rows


def refresh_driver_signals_conn(conn: sqlite3.Connection) -> None:
    signal_rows = _collect_signal_rows(conn)
    now = _utcnow()
    conn.execute("DELETE FROM driver_signals WHERE source = 'derived'")

    groups: dict[tuple[str | None, str, str | None], list[dict[str, Any]]] = {}
    for row in signal_rows:
        keys = [
            (None, row["category"], row["focus_area"]),
            (row["track"], row["category"], row["focus_area"]),
        ]
        for key in keys:
            groups.setdefault(key, []).append(row)

    for (track, category, focus_area), entries in groups.items():
        attempts = len(entries)
        improved = sum(1 for item in entries if item["outcome"] == "improved")
        worse = sum(1 for item in entries if item["outcome"] == "worse")
        mixed = sum(1 for item in entries if item["outcome"] == "mixed")
        score = (improved - worse) / attempts if attempts else 0.0
        if score >= 0.35:
            signal_type = "strength"
        elif score <= -0.15:
            signal_type = "weakness"
        else:
            signal_type = "developing"

        confidence = "low"
        if attempts >= 5:
            confidence = "high"
        elif attempts >= 3:
            confidence = "medium"

        evidence = (
            f"{improved}/{attempts} validated results improved, "
            f"{worse} worse, {mixed} mixed."
        )
        metadata = {
            "attempts": attempts,
            "improved": improved,
            "worse": worse,
            "mixed": mixed,
            "score": round(score, 3),
            "focus_area": focus_area,
            "category": category,
        }
        conn.execute(
            """
            INSERT INTO driver_signals (
                created_at, updated_at, track, signal_type, category, focus_area,
                evidence, confidence, source, strength, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'derived', ?, ?)
            """,
            (
                now,
                now,
                track,
                signal_type,
                category,
                focus_area,
                evidence,
                confidence,
                round(score, 3),
                _json_dumps(metadata),
            ),
        )

    conn.commit()


def refresh_driver_signals(db_path: Path | str = DB_PATH) -> None:
    conn = _get_db(db_path)
    refresh_driver_signals_conn(conn)
    conn.close()


def get_driver_model(db_path: Path | str = DB_PATH, *, track: str | None = None) -> dict[str, Any]:
    conn = _get_db(db_path)
    refresh_driver_signals_conn(conn)
    global_rows = conn.execute(
        """
        SELECT * FROM driver_signals
        WHERE track IS NULL
        ORDER BY strength DESC, confidence DESC, updated_at DESC
        """
    ).fetchall()
    track_rows = []
    if track:
        track_rows = conn.execute(
            """
            SELECT * FROM driver_signals
            WHERE track = ?
            ORDER BY strength DESC, confidence DESC, updated_at DESC
            """,
            (track,),
        ).fetchall()
    conn.close()

    global_signals = [_deserialize_row(row) for row in global_rows if row]
    scoped_signals = [_deserialize_row(row) for row in track_rows if row]

    return {
        "focus_areas": FOCUS_AREAS,
        "global": {
            "strengths": [row for row in global_signals if row["signal_type"] == "strength"][:5],
            "weaknesses": [row for row in global_signals if row["signal_type"] == "weakness"][:5],
            "developing": [row for row in global_signals if row["signal_type"] == "developing"][:5],
        },
        "track": {
            "name": track,
            "strengths": [row for row in scoped_signals if row["signal_type"] == "strength"][:5],
            "weaknesses": [row for row in scoped_signals if row["signal_type"] == "weakness"][:5],
            "developing": [row for row in scoped_signals if row["signal_type"] == "developing"][:5],
        },
    }


def get_taxonomy_summary(db_path: Path | str = DB_PATH, *, track: str | None = None) -> dict[str, Any]:
    conn = _get_db(db_path)
    refresh_driver_signals_conn(conn)

    filters = []
    params: list[Any] = []
    if track:
        filters.append("track = ?")
        params.append(track)

    where_sql = ""
    if filters:
        where_sql = " WHERE " + " AND ".join(filters)

    rec_rows = conn.execute(
        f"""
        SELECT category, focus_area, grade, COUNT(*) AS count
        FROM recommendations
        {where_sql}
        GROUP BY category, focus_area, grade
        ORDER BY count DESC
        """,
        params,
    ).fetchall()

    exp_rows = conn.execute(
        f"""
        SELECT category, focus_area, result, COUNT(*) AS count
        FROM experiments
        {where_sql}
        GROUP BY category, focus_area, result
        ORDER BY count DESC
        """,
        params,
    ).fetchall()
    conn.close()

    buckets: dict[tuple[str, str | None], dict[str, Any]] = {}
    for row in rec_rows:
        key = (row["category"], row["focus_area"])
        buckets.setdefault(key, {
            "category": row["category"],
            "focus_area": row["focus_area"],
            "recommendations": {},
            "experiments": {},
        })
        buckets[key]["recommendations"][row["grade"]] = row["count"]

    for row in exp_rows:
        key = (row["category"], row["focus_area"])
        buckets.setdefault(key, {
            "category": row["category"],
            "focus_area": row["focus_area"],
            "recommendations": {},
            "experiments": {},
        })
        buckets[key]["experiments"][row["result"]] = row["count"]

    items = list(buckets.values())
    items.sort(
        key=lambda item: (
            item["recommendations"].get("improved", 0) + item["experiments"].get("improved", 0),
            -(item["recommendations"].get("worse", 0) + item["experiments"].get("worse", 0)),
        ),
        reverse=True,
    )
    return {"track": track, "items": items, "focus_areas": FOCUS_AREAS}


def get_session_debrief(session_id: str, db_path: Path | str = DB_PATH) -> dict[str, Any]:
    conn = _get_db(db_path)
    session = conn.execute(
        """
        SELECT id, track, session_date, best_lap_time, total_laps, timed_laps
        FROM sessions
        WHERE id = ?
        """,
        (session_id,),
    ).fetchone()
    if not session:
        conn.close()
        raise ValueError(f"Session {session_id} not found")

    laps = conn.execute(
        """
        SELECT lap_number, lap_time, sector_1, sector_2, sector_3, valid
        FROM laps
        WHERE session_id = ?
        ORDER BY lap_number
        """,
        (session_id,),
    ).fetchall()

    track_best = conn.execute(
        """
        SELECT MIN(l.lap_time) AS best_track_lap
        FROM laps l
        JOIN sessions s ON s.id = l.session_id
        WHERE s.track = ? AND l.valid = 1 AND l.lap_time > 0
        """,
        (session["track"],),
    ).fetchone()

    recs = conn.execute(
        """
        SELECT id, category, focus_area, grade
        FROM recommendations
        WHERE session_id = ?
        ORDER BY created_at DESC
        """,
        (session_id,),
    ).fetchall()
    exps = conn.execute(
        """
        SELECT id, category, focus_area, result
        FROM experiments
        WHERE session_id = ?
        ORDER BY created_at DESC
        """,
        (session_id,),
    ).fetchall()
    events = conn.execute(
        """
        SELECT id, event_type, severity, title, summary, lap_number, created_at
        FROM session_events
        WHERE session_id = ?
        ORDER BY created_at DESC
        LIMIT 25
        """,
        (session_id,),
    ).fetchall()
    conn.close()

    valid_laps = [row["lap_time"] for row in laps if row["valid"] and row["lap_time"] and row["lap_time"] > 0]
    sector_1 = [row["sector_1"] for row in laps if row["valid"] and row["sector_1"]]
    sector_2 = [row["sector_2"] for row in laps if row["valid"] and row["sector_2"]]
    sector_3 = [row["sector_3"] for row in laps if row["valid"] and row["sector_3"]]

    best_lap = min(valid_laps) if valid_laps else None
    median_lap = statistics.median(valid_laps) if valid_laps else None
    top5 = sorted(valid_laps)[:5]
    top5_spread = (max(top5) - min(top5)) if len(top5) >= 2 else 0.0
    track_best_lap = track_best["best_track_lap"] if track_best else None
    gap_to_track_best = (best_lap - track_best_lap) if best_lap and track_best_lap else None

    return {
        "session": dict(session),
        "lap_summary": {
            "valid_laps": len(valid_laps),
            "invalid_laps": len(laps) - len(valid_laps),
            "best_lap": round(best_lap, 3) if best_lap else None,
            "median_valid_lap": round(median_lap, 3) if median_lap else None,
            "top5_spread": round(top5_spread, 3),
            "gap_to_track_best": round(gap_to_track_best, 3) if gap_to_track_best is not None else None,
        },
        "sector_bests": {
            "sector_1": round(min(sector_1), 3) if sector_1 else None,
            "sector_2": round(min(sector_2), 3) if sector_2 else None,
            "sector_3": round(min(sector_3), 3) if sector_3 else None,
        },
        "recommendations": [dict(row) for row in recs],
        "experiments": [dict(row) for row in exps],
        "events": [dict(row) for row in events],
    }
