"""PitWall37 terminal workflow.

Lean CLI for the highest-value daily review tasks.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from engineering_data import (
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

DB_PATH = Path(__file__).parent / "data" / "pitwall37.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _json_arg(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def cmd_stats(_: argparse.Namespace) -> int:
    conn = get_db()
    total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    total_valid_laps = conn.execute(
        "SELECT COUNT(*) FROM laps WHERE valid = 1"
    ).fetchone()[0]
    tracks = conn.execute(
        "SELECT COUNT(DISTINCT track) FROM sessions"
    ).fetchone()[0]
    bests = conn.execute(
        """
        SELECT s.track, MIN(l.lap_time) AS best_time, COUNT(*) AS lap_count
        FROM laps l
        JOIN sessions s ON s.id = l.session_id
        WHERE l.valid = 1 AND l.lap_time > 0
        GROUP BY s.track
        ORDER BY best_time ASC
        """
    ).fetchall()
    conn.close()

    print(f"sessions: {total_sessions}")
    print(f"valid_laps: {total_valid_laps}")
    print(f"tracks: {tracks}")
    print("")
    for row in bests:
        print(f"{row['track']}: {row['best_time']:.3f}s ({row['lap_count']} valid laps)")
    return 0


def cmd_recent(args: argparse.Namespace) -> int:
    conn = get_db()
    rows = conn.execute(
        """
        SELECT id, session_date, track, best_lap_time, timed_laps
        FROM sessions
        ORDER BY session_date DESC
        LIMIT ?
        """,
        (args.limit,),
    ).fetchall()
    conn.close()

    for row in rows:
        best = f"{row['best_lap_time']:.3f}s" if row["best_lap_time"] else "--"
        print(f"{row['id']}  {row['session_date']}  {row['track']}  best={best}  timed_laps={row['timed_laps']}")
    return 0


def cmd_debrief(args: argparse.Namespace) -> int:
    debrief = get_session_debrief(args.session_id)
    session = debrief["session"]
    lap_summary = debrief["lap_summary"]
    sectors = debrief["sector_bests"]

    print(f"session: {session['id']}")
    print(f"track: {session['track']}")
    print(f"date: {session['session_date']}")
    print("")
    print(f"best_lap: {lap_summary['best_lap']}")
    print(f"median_valid_lap: {lap_summary['median_valid_lap']}")
    print(f"top5_spread: {lap_summary['top5_spread']}")
    print(f"gap_to_track_best: {lap_summary['gap_to_track_best']}")
    print("")
    print(
        "sector_bests: "
        f"S1={sectors['sector_1']} "
        f"S2={sectors['sector_2']} "
        f"S3={sectors['sector_3']}"
    )
    print(
        f"attached_recommendations: {len(debrief['recommendations'])}  "
        f"attached_experiments: {len(debrief['experiments'])}  "
        f"events: {len(debrief['events'])}"
    )
    return 0


def _print_signal_group(title: str, items: list[dict]) -> None:
    print(title)
    if not items:
        print("  none")
        return
    for item in items:
        focus = item.get("focus_area") or item.get("category")
        print(f"  {focus} [{item['confidence']}] {item['evidence']}")


def cmd_driver_model(args: argparse.Namespace) -> int:
    model = get_driver_model(track=args.track)
    print("global")
    _print_signal_group("strengths", model["global"]["strengths"])
    _print_signal_group("weaknesses", model["global"]["weaknesses"])
    _print_signal_group("developing", model["global"]["developing"])
    if args.track:
        print("")
        print(f"track: {args.track}")
        _print_signal_group("strengths", model["track"]["strengths"])
        _print_signal_group("weaknesses", model["track"]["weaknesses"])
        _print_signal_group("developing", model["track"]["developing"])
    return 0


def cmd_taxonomy(args: argparse.Namespace) -> int:
    summary = get_taxonomy_summary(track=args.track)
    print(f"track: {summary['track'] or 'all'}")
    if not summary["items"]:
        print("no classified engineering outcomes yet")
        return 0
    for item in summary["items"][: args.limit]:
        focus = item["focus_area"] or item["category"]
        print(f"{focus} ({item['category']})")
        print(f"  recommendations: {json.dumps(item['recommendations'], sort_keys=True)}")
        print(f"  experiments: {json.dumps(item['experiments'], sort_keys=True)}")
    return 0


def cmd_log_recommendation(args: argparse.Namespace) -> int:
    payload = {
        "session_id": args.session_id,
        "track": args.track,
        "lap_number": args.lap_number,
        "source": args.source,
        "recommendation_type": args.recommendation_type,
        "category": args.category,
        "focus_area": args.focus_area,
        "observation": args.observation,
        "inference": args.inference,
        "confidence": args.confidence,
        "action": args.action,
        "validation_plan": args.validation,
        "support_json": _json_arg(args.support_json),
    }
    saved = record_recommendation(payload, DB_PATH)
    _print_json(saved)
    return 0


def cmd_grade_recommendation(args: argparse.Namespace) -> int:
    payload = {
        "grade": args.grade,
        "grade_notes": args.notes,
        "actual_metric_json": _json_arg(args.actual_json),
        "experiment_id": args.experiment_id,
    }
    saved = grade_recommendation(args.recommendation_id, payload, DB_PATH)
    if not saved:
        raise SystemExit(f"recommendation {args.recommendation_id} not found")
    _print_json(saved)
    return 0


def cmd_log_experiment(args: argparse.Namespace) -> int:
    payload = {
        "session_id": args.session_id,
        "track": args.track,
        "lap_range": args.lap_range,
        "category": args.category,
        "focus_area": args.focus_area,
        "change_type": args.change_type,
        "change_json": _json_arg(args.change_json),
        "hypothesis": args.hypothesis,
        "expected_metric": args.expected_metric,
        "baseline_metric_json": _json_arg(args.baseline_json),
        "actual_metric_json": _json_arg(args.actual_json),
        "result": args.result,
        "confidence_before": args.confidence_before,
        "confidence_after": args.confidence_after,
        "notes": args.notes,
        "recommendation_id": args.recommendation_id,
    }
    saved = record_experiment(payload, DB_PATH)
    _print_json(saved)
    return 0


def cmd_list_recommendations(args: argparse.Namespace) -> int:
    items = list_recommendations(
        DB_PATH,
        limit=args.limit,
        track=args.track,
        session_id=args.session_id,
        status=args.status,
        grade=args.grade,
    )
    _print_json(items)
    return 0


def cmd_list_experiments(args: argparse.Namespace) -> int:
    items = list_experiments(
        DB_PATH,
        limit=args.limit,
        track=args.track,
        session_id=args.session_id,
        result=args.result,
    )
    _print_json(items)
    return 0


def cmd_events(args: argparse.Namespace) -> int:
    items = list_session_events(
        DB_PATH,
        limit=args.limit,
        track=args.track,
        session_id=args.session_id,
        event_type=args.event_type,
        severity=args.severity,
    )
    _print_json(items)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PitWall37 lean workflow CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    stats = sub.add_parser("stats", help="Show overall session and track stats")
    stats.set_defaults(func=cmd_stats)

    recent = sub.add_parser("recent", help="Show recent sessions")
    recent.add_argument("--limit", type=int, default=10)
    recent.set_defaults(func=cmd_recent)

    debrief = sub.add_parser("debrief", help="Show a concise session debrief")
    debrief.add_argument("session_id")
    debrief.set_defaults(func=cmd_debrief)

    model = sub.add_parser("driver-model", help="Show the current validated driver model")
    model.add_argument("--track")
    model.set_defaults(func=cmd_driver_model)

    taxonomy = sub.add_parser("taxonomy", help="Show engineering outcomes grouped by focus area")
    taxonomy.add_argument("--track")
    taxonomy.add_argument("--limit", type=int, default=10)
    taxonomy.set_defaults(func=cmd_taxonomy)

    log_rec = sub.add_parser("log-recommendation", help="Create a structured recommendation")
    log_rec.add_argument("--session-id")
    log_rec.add_argument("--track")
    log_rec.add_argument("--lap-number", type=int)
    log_rec.add_argument("--source", default="manual")
    log_rec.add_argument("--recommendation-type", default="driver", choices=["driver", "setup"])
    log_rec.add_argument("--category", required=True)
    log_rec.add_argument("--focus-area")
    log_rec.add_argument("--observation", required=True)
    log_rec.add_argument("--inference", required=True)
    log_rec.add_argument("--confidence", default="medium", choices=["low", "medium", "high"])
    log_rec.add_argument("--action", required=True)
    log_rec.add_argument("--validation", required=True)
    log_rec.add_argument("--support-json")
    log_rec.set_defaults(func=cmd_log_recommendation)

    grade_rec = sub.add_parser("grade-recommendation", help="Grade a recommendation after a test")
    grade_rec.add_argument("recommendation_id", type=int)
    grade_rec.add_argument("--grade", required=True, choices=["untested", "improved", "no_change", "worse", "mixed"])
    grade_rec.add_argument("--notes")
    grade_rec.add_argument("--actual-json")
    grade_rec.add_argument("--experiment-id", type=int)
    grade_rec.set_defaults(func=cmd_grade_recommendation)

    log_exp = sub.add_parser("log-experiment", help="Create a one-variable experiment entry")
    log_exp.add_argument("--session-id")
    log_exp.add_argument("--track")
    log_exp.add_argument("--lap-range")
    log_exp.add_argument("--category", required=True)
    log_exp.add_argument("--focus-area")
    log_exp.add_argument("--change-type", default="driver", choices=["driver", "setup"])
    log_exp.add_argument("--change-json")
    log_exp.add_argument("--hypothesis", required=True)
    log_exp.add_argument("--expected-metric", required=True)
    log_exp.add_argument("--baseline-json")
    log_exp.add_argument("--actual-json")
    log_exp.add_argument("--result", default="planned", choices=["planned", "improved", "no_change", "worse", "mixed", "abandoned"])
    log_exp.add_argument("--confidence-before", default="medium", choices=["low", "medium", "high"])
    log_exp.add_argument("--confidence-after")
    log_exp.add_argument("--notes")
    log_exp.add_argument("--recommendation-id", type=int)
    log_exp.set_defaults(func=cmd_log_experiment)

    recs = sub.add_parser("recommendations", help="List recommendations")
    recs.add_argument("--track")
    recs.add_argument("--session-id")
    recs.add_argument("--status")
    recs.add_argument("--grade")
    recs.add_argument("--limit", type=int, default=20)
    recs.set_defaults(func=cmd_list_recommendations)

    exps = sub.add_parser("experiments", help="List experiments")
    exps.add_argument("--track")
    exps.add_argument("--session-id")
    exps.add_argument("--result")
    exps.add_argument("--limit", type=int, default=20)
    exps.set_defaults(func=cmd_list_experiments)

    events = sub.add_parser("events", help="List captured live/session events")
    events.add_argument("--track")
    events.add_argument("--session-id")
    events.add_argument("--event-type")
    events.add_argument("--severity")
    events.add_argument("--limit", type=int, default=20)
    events.set_defaults(func=cmd_events)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
