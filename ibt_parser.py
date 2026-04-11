"""IBT telemetry parser for PitWall37 v2.
Parses iRacing IBT files via pyirsdk, extracts laps, telemetry, tire data.
Stores structured data in SQLite + per-lap JSON files.
"""

import hashlib
import json
import os
import sqlite3
import struct
import time
from datetime import datetime
from pathlib import Path

import yaml

try:
    import irsdk
except ImportError:
    print("pyirsdk not installed: pip install pyirsdk")
    raise

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "pitwall37.db"
IBT_DIR = DATA_DIR / "ibt"
TELEM_DIR = DATA_DIR / "telemetry"

# Telemetry channels to extract per tick
CHANNELS = [
    "Speed", "Throttle", "Brake", "SteeringWheelAngle",
    "Gear", "RPM", "FuelLevel", "LapDistPct",
    "Lap", "SessionTime", "LapCurrentLapTime",
    "LapLastLapTime", "LapBestLapTime",
    "LatAccel", "LongAccel", "YawRate",
    "LFtempCL", "LFtempCM", "LFtempCR",
    "RFtempCL", "RFtempCM", "RFtempCR",
    "LRtempCL", "LRtempCM", "LRtempCR",
    "RRtempCL", "RRtempCM", "RRtempCR",
    "LFwearL", "LFwearM", "LFwearR",
    "RFwearL", "RFwearM", "RFwearR",
    "LRwearL", "LRwearM", "LRwearR",
    "RRwearL", "RRwearM", "RRwearR",
    "LFcoldPressure", "RFcoldPressure", "LRcoldPressure", "RRcoldPressure",
    "LFpressure", "RFpressure", "LRpressure", "RRpressure",
    "OnPitRoad", "TrackSurface",
    # Ride height channels (meters) — actual dynamic RH per corner
    "LFrideHeight", "RFrideHeight", "LRrideHeight", "RRrideHeight",
    # Pitch for rake calculation (radians)
    "Pitch",
]

# Short keys for JSON storage (save space in per-lap files)
CHANNEL_KEYS = {
    "Speed": "speed",
    "Throttle": "throttle",
    "Brake": "brake",
    "SteeringWheelAngle": "steering",
    "Gear": "gear",
    "RPM": "rpm",
    "FuelLevel": "fuel",
    "LapDistPct": "dist_pct",
    "LatAccel": "lat_g",
    "LongAccel": "long_g",
    "YawRate": "yaw_rate",
    "LFrideHeight": "lf_rh",
    "RFrideHeight": "rf_rh",
    "LRrideHeight": "lr_rh",
    "RRrideHeight": "rr_rh",
    "Pitch": "pitch",
}


def init_db():
    """Create SQLite tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            car TEXT,
            track TEXT,
            track_config TEXT,
            track_id INTEGER,
            track_length_km REAL,
            session_date TEXT,
            session_type TEXT,
            driver_name TEXT,
            irating INTEGER,
            license TEXT,
            total_laps INTEGER,
            timed_laps INTEGER,
            best_lap_time REAL,
            avg_lap_time REAL,
            air_temp REAL,
            track_temp REAL,
            setup_json TEXT,
            imported_at TEXT
        );

        CREATE TABLE IF NOT EXISTS laps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            lap_number INTEGER NOT NULL,
            lap_time REAL,
            sector_1 REAL,
            sector_2 REAL,
            sector_3 REAL,
            valid INTEGER DEFAULT 1,
            fuel_used REAL,
            fuel_remaining REAL,
            avg_speed_ms REAL,
            max_speed_ms REAL,
            telemetry_file TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            UNIQUE(session_id, lap_number)
        );

        CREATE TABLE IF NOT EXISTS tire_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            lap_number INTEGER NOT NULL,
            corner TEXT NOT NULL,
            temp_left REAL,
            temp_mid REAL,
            temp_right REAL,
            wear_left REAL,
            wear_mid REAL,
            wear_right REAL,
            cold_pressure REAL,
            hot_pressure REAL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS setups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            track TEXT,
            source TEXT,
            parameters TEXT,
            notes TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS coaching_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            lap_number INTEGER,
            corner TEXT,
            category TEXT,
            observation TEXT,
            recommendation TEXT,
            severity TEXT,
            created_at TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS driver_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track TEXT,
            metric TEXT,
            value REAL,
            recorded_at TEXT
        );
    """)
    conn.commit()
    return conn


def file_hash(filepath):
    """SHA256 of filename (not content — too slow for large files)."""
    return hashlib.sha256(Path(filepath).name.encode()).hexdigest()[:16]


def parse_session_info(filepath):
    """Read IBT header and extract session YAML."""
    with open(filepath, "rb") as f:
        header = struct.unpack("iiiiiiiiii", f.read(40))
        f.seek(header[5])
        raw = f.read(header[4]).decode("latin-1").rstrip("\x00")
    return yaml.safe_load(raw)


def extract_driver(session_info):
    """Find the player driver from session info."""
    drivers = session_info.get("DriverInfo", {}).get("Drivers", [])
    # CarIdx 0 is usually the player in test sessions
    for d in drivers:
        if d.get("CarIdx") == 0:
            return d
    return drivers[0] if drivers else {}


def extract_setup(session_info):
    """Extract car setup from session info."""
    return session_info.get("CarSetup", {})


def detect_laps(ibt_obj, tick_count):
    """Detect clean lap boundaries using S/F crossings and teleport detection.
    A clean lap has LapDistPct going 0->1 with no large jumps (teleports).
    Returns list of dicts with lap_number, start_tick, end_tick, lap_time, valid.
    """
    dist_data = ibt_obj.get_all("LapDistPct")
    lap_data = ibt_obj.get_all("Lap")
    laptime_data = ibt_obj.get_all("LapLastLapTime")
    on_pit = ibt_obj.get_all("OnPitRoad")

    # Find S/F crossings (dist wraps from >0.95 to <0.05)
    crossings = []
    for i in range(1, tick_count):
        if dist_data[i - 1] > 0.95 and dist_data[i] < 0.05:
            crossings.append(i)

    laps = []
    for idx in range(1, len(crossings)):
        start = crossings[idx - 1]
        end = crossings[idx]

        # Detect teleports: any dist_pct jump > 0.01 in a single tick
        has_teleport = False
        for j in range(start, end - 1):
            if dist_data[j + 1] - dist_data[j] > 0.01:
                has_teleport = True
                break

        # Lap number from the start of this lap segment
        lap_num = lap_data[start]

        # LapLastLapTime is reported at the NEXT crossing (end of this lap)
        # Check at the end crossing and a few ticks after
        lap_time = None
        check_end = min(end + 60, tick_count)  # Check up to 1 sec after crossing
        for j in range(end, check_end):
            if laptime_data[j] > 0:
                lap_time = laptime_data[j]
                break

        # Check pit road
        was_on_pit = any(on_pit[j] for j in range(start, min(end, tick_count)))

        # Valid = no teleport, not on pit, has timed lap > 10s
        valid = (not has_teleport and not was_on_pit
                 and lap_time is not None and lap_time > 10)

        laps.append({
            "lap_number": lap_num,
            "start_tick": start,
            "end_tick": end,
            "lap_time": lap_time,
            "on_pit": was_on_pit,
            "teleport": has_teleport,
            "valid": valid,
        })

    return laps


def extract_lap_telemetry(ibt_obj, start_tick, end_tick, downsample=6):
    """Extract telemetry channels for a lap, optionally downsampled.
    downsample=1 means keep all 60Hz, 6 means keep every 6th (10Hz).
    """
    channels = {}
    for ch_name, key in CHANNEL_KEYS.items():
        all_data = ibt_obj.get_all(ch_name)
        if all_data is None:
            continue
        samples = all_data[start_tick:end_tick:downsample]
        # Round floats to save space
        if key in ("gear",):
            channels[key] = [int(v) for v in samples]
        elif key in ("dist_pct",):
            channels[key] = [round(v, 5) for v in samples]
        else:
            channels[key] = [round(v, 3) for v in samples]
    return channels


def extract_tire_data(ibt_obj, start_tick, end_tick):
    """Extract tire temps, wear, and pressures.
    Uses carcass temps (pyrometer) averaged over the last quarter of the lap.
    Falls back to surface temps (IR sensor) if carcass temps are stuck at ambient.
    """
    quarter = start_tick + 3 * (end_tick - start_tick) // 4
    step = 30  # Sample every 0.5s

    corners = {}
    for corner in ("LF", "RF", "LR", "RR"):
        # Carcass temps (pyrometer — accumulated heat from work done)
        carcass_l = [ibt_obj.get(t, f"{corner}tempCL") or 0 for t in range(quarter, end_tick, step)]
        carcass_m = [ibt_obj.get(t, f"{corner}tempCM") or 0 for t in range(quarter, end_tick, step)]
        carcass_r = [ibt_obj.get(t, f"{corner}tempCR") or 0 for t in range(quarter, end_tick, step)]

        avg_c = [
            round(sum(carcass_l) / len(carcass_l), 1) if carcass_l else 0,
            round(sum(carcass_m) / len(carcass_m), 1) if carcass_m else 0,
            round(sum(carcass_r) / len(carcass_r), 1) if carcass_r else 0,
        ]

        # Surface temps (IR sensor — instantaneous contact patch)
        surface_l = [ibt_obj.get(t, f"{corner}tempL") or 0 for t in range(quarter, end_tick, step)]
        surface_m = [ibt_obj.get(t, f"{corner}tempM") or 0 for t in range(quarter, end_tick, step)]
        surface_r = [ibt_obj.get(t, f"{corner}tempR") or 0 for t in range(quarter, end_tick, step)]

        avg_s = [
            round(sum(surface_l) / len(surface_l), 1) if surface_l else 0,
            round(sum(surface_m) / len(surface_m), 1) if surface_m else 0,
            round(sum(surface_r) / len(surface_r), 1) if surface_r else 0,
        ]

        # Use carcass if they show real variation (not stuck at ambient)
        # If all 3 carcass temps are within 2C of each other AND below 60C, use surface
        carcass_spread = max(avg_c) - min(avg_c)
        use_surface = (carcass_spread < 2 and max(avg_c) < 60)

        corners[corner] = {
            "temp": avg_s if use_surface else avg_c,
            "temp_source": "surface" if use_surface else "carcass",
            "wear": [
                round((ibt_obj.get(end_tick - 1, f"{corner}wearL") or 0) * 100, 1),
                round((ibt_obj.get(end_tick - 1, f"{corner}wearM") or 0) * 100, 1),
                round((ibt_obj.get(end_tick - 1, f"{corner}wearR") or 0) * 100, 1),
            ],
            "cold_pressure_kpa": round(ibt_obj.get(end_tick - 1, f"{corner}coldPressure") or 0, 1),
            "hot_pressure_kpa": round(ibt_obj.get(end_tick - 1, f"{corner}pressure") or 0, 1),
        }
    return corners


def parse_ibt(filepath, conn=None):
    """Parse a single IBT file. Returns session dict.
    If conn provided, writes to database.
    """
    filepath = Path(filepath)
    sid = file_hash(filepath)

    # Check if already imported
    if conn:
        existing = conn.execute("SELECT id FROM sessions WHERE id = ?", (sid,)).fetchone()
        if existing:
            return None  # Already imported

    print(f"  Parsing: {filepath.name}")
    t0 = time.time()

    # Session info from YAML header
    session_info = parse_session_info(filepath)
    wi = session_info.get("WeekendInfo", {})
    driver = extract_driver(session_info)
    setup = extract_setup(session_info)

    # Parse track name (clean up encoding artifacts)
    track_name = wi.get("TrackDisplayName", "Unknown")
    track_config = wi.get("TrackConfigName", "")
    track_length = wi.get("TrackLength", "0 km")
    if isinstance(track_length, str):
        track_length = float(track_length.split()[0])

    # Parse date from filename: car_track YYYY-MM-DD HH-MM-SS.ibt
    date_str = None
    parts = filepath.stem.split(" ")
    for i, p in enumerate(parts):
        if len(p) == 10 and p[4] == "-" and p[7] == "-":
            date_str = p
            if i + 1 < len(parts):
                time_str = parts[i + 1].replace("-", ":")
                date_str += " " + time_str
            break

    # Open IBT for telemetry
    ibt = irsdk.IBT()
    ibt.open(str(filepath))

    # Get total tick count from first channel
    all_laps = ibt.get_all("Lap")
    tick_count = len(all_laps)

    # Detect laps
    laps = detect_laps(ibt, tick_count)

    # Find best valid lap for full-resolution storage
    valid_laps = [l for l in laps if l["valid"]]
    best_time = min(l["lap_time"] for l in valid_laps) if valid_laps else None

    # Process only valid laps (no teleports, no pits, has timed crossing)
    TELEM_DIR.mkdir(parents=True, exist_ok=True)
    session_telem_dir = TELEM_DIR / sid
    session_telem_dir.mkdir(exist_ok=True)

    lap_records = []
    tire_records = []

    for lap_info in laps:
        # Skip invalid laps (teleports, pit laps, untimed)
        if not lap_info["valid"]:
            continue

        ln = lap_info["lap_number"]
        lt = lap_info["lap_time"]
        start = lap_info["start_tick"]
        end = lap_info["end_tick"]

        valid = True

        # Downsample: 60Hz for best lap, 10Hz for others
        ds = 1 if (lt and lt == best_time) else 6

        # Extract telemetry
        channels = extract_lap_telemetry(ibt, start, end, downsample=ds)

        # Compute lap metrics from telemetry
        speeds = channels.get("speed", [])
        avg_speed = sum(speeds) / len(speeds) if speeds else 0
        max_speed = max(speeds) if speeds else 0

        # Fuel
        fuels = channels.get("fuel", [])
        fuel_start = fuels[0] if fuels else 0
        fuel_end = fuels[-1] if fuels else 0
        fuel_used = fuel_start - fuel_end

        # Sector times (default thirds — will be refined per track)
        sector_times = compute_sectors(ibt, start, end)

        # Tire data (averaged over last quarter of lap)
        tires = extract_tire_data(ibt, start, end)

        # Ride height summary (per-corner meters → averaged front/rear mm)
        ride_height = {}
        lf_rh = channels.get("lf_rh", [])
        rf_rh = channels.get("rf_rh", [])
        lr_rh = channels.get("lr_rh", [])
        rr_rh = channels.get("rr_rh", [])
        speed_samples = channels.get("speed", [])
        if lf_rh and rf_rh and lr_rh and rr_rh and speed_samples:
            n = min(len(lf_rh), len(rf_rh), len(lr_rh), len(rr_rh), len(speed_samples))
            # Average L/R per axle, convert to mm
            front_mm = [(lf_rh[i] + rf_rh[i]) / 2 * 1000 for i in range(n)]
            rear_mm = [(lr_rh[i] + rr_rh[i]) / 2 * 1000 for i in range(n)]
            # At speed: above 30 m/s (108 km/h)
            at_speed_f = [front_mm[i] for i in range(n) if speed_samples[i] > 30]
            at_speed_r = [rear_mm[i] for i in range(n) if speed_samples[i] > 30]
            # Bottoming events: any corner goes negative
            bottoming_count = sum(
                1 for i in range(n)
                if min(lf_rh[i], rf_rh[i], lr_rh[i], rr_rh[i]) < 0
            )
            ride_height = {
                "front_mm": {
                    "min": round(min(front_mm), 1),
                    "max": round(max(front_mm), 1),
                    "avg": round(sum(front_mm) / len(front_mm), 1),
                },
                "rear_mm": {
                    "min": round(min(rear_mm), 1),
                    "max": round(max(rear_mm), 1),
                    "avg": round(sum(rear_mm) / len(rear_mm), 1),
                },
                "at_speed_front_mm": {
                    "min": round(min(at_speed_f), 1) if at_speed_f else None,
                    "avg": round(sum(at_speed_f) / len(at_speed_f), 1) if at_speed_f else None,
                },
                "at_speed_rear_mm": {
                    "min": round(min(at_speed_r), 1) if at_speed_r else None,
                    "avg": round(sum(at_speed_r) / len(at_speed_r), 1) if at_speed_r else None,
                },
                "bottoming_events": bottoming_count,
                "bottoming_pct": round(bottoming_count / n * 100, 1),
            }

        # Save telemetry JSON
        telem_file = session_telem_dir / f"lap_{ln:03d}.json"
        telem_data = {
            "session_id": sid,
            "lap_number": ln,
            "lap_time_s": lt,
            "valid": valid,
            "sample_rate_hz": 60 // ds,
            "samples": len(speeds),
            "channels": channels,
            "tire_end": tires,
            "ride_height": ride_height,
            "fuel_start_l": round(fuel_start, 2),
            "fuel_end_l": round(fuel_end, 2),
        }
        with open(telem_file, "w") as f:
            json.dump(telem_data, f)

        lap_records.append({
            "session_id": sid,
            "lap_number": ln,
            "lap_time": lt,
            "sector_1": sector_times[0],
            "sector_2": sector_times[1],
            "sector_3": sector_times[2],
            "valid": 1 if valid else 0,
            "fuel_used": round(fuel_used, 3),
            "fuel_remaining": round(fuel_end, 2),
            "avg_speed_ms": round(avg_speed, 2),
            "max_speed_ms": round(max_speed, 2),
            "telemetry_file": str(telem_file.relative_to(DATA_DIR)),
        })

        # Tire records
        for corner, td in tires.items():
            tire_records.append({
                "session_id": sid,
                "lap_number": ln,
                "corner": corner,
                "temp_left": td["temp"][0],
                "temp_mid": td["temp"][1],
                "temp_right": td["temp"][2],
                "wear_left": td["wear"][0],
                "wear_mid": td["wear"][1],
                "wear_right": td["wear"][2],
                "cold_pressure": td["cold_pressure_kpa"],
                "hot_pressure": td["hot_pressure_kpa"],
            })

    ibt.close()

    # Parse air/track temp
    air_temp = wi.get("TrackAirTemp", "0")
    track_temp = wi.get("TrackSurfaceTemp", "0")
    if isinstance(air_temp, str):
        air_temp = float(air_temp.split()[0])
    if isinstance(track_temp, str):
        track_temp = float(track_temp.split()[0])

    timed_times = [r["lap_time"] for r in lap_records if r["lap_time"] and r["lap_time"] > 10]
    avg_time = sum(timed_times) / len(timed_times) if timed_times else None

    session = {
        "id": sid,
        "filename": filepath.name,
        "car": driver.get("CarScreenName", "Unknown"),
        "track": track_name,
        "track_config": track_config,
        "track_id": wi.get("TrackID"),
        "track_length_km": track_length,
        "session_date": date_str,
        "session_type": "practice",  # Will refine from SessionInfo
        "driver_name": driver.get("UserName", "Unknown"),
        "irating": driver.get("IRating", 0),
        "license": driver.get("LicString", ""),
        "total_laps": len(lap_records),
        "timed_laps": len(timed_times),
        "best_lap_time": best_time,
        "avg_lap_time": avg_time,
        "air_temp": air_temp,
        "track_temp": track_temp,
        "setup_json": json.dumps(setup),
        "imported_at": datetime.now().isoformat(),
    }

    # Write to database
    if conn:
        conn.execute("""
            INSERT OR REPLACE INTO sessions
            (id, filename, car, track, track_config, track_id, track_length_km,
             session_date, session_type, driver_name, irating, license,
             total_laps, timed_laps, best_lap_time, avg_lap_time,
             air_temp, track_temp, setup_json, imported_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["id"], session["filename"], session["car"],
            session["track"], session["track_config"], session["track_id"],
            session["track_length_km"], session["session_date"],
            session["session_type"], session["driver_name"],
            session["irating"], session["license"],
            session["total_laps"], session["timed_laps"],
            session["best_lap_time"], session["avg_lap_time"],
            session["air_temp"], session["track_temp"],
            session["setup_json"], session["imported_at"],
        ))

        for lr in lap_records:
            conn.execute("""
                INSERT OR REPLACE INTO laps
                (session_id, lap_number, lap_time, sector_1, sector_2, sector_3,
                 valid, fuel_used, fuel_remaining, avg_speed_ms, max_speed_ms,
                 telemetry_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lr["session_id"], lr["lap_number"], lr["lap_time"],
                lr["sector_1"], lr["sector_2"], lr["sector_3"],
                lr["valid"], lr["fuel_used"], lr["fuel_remaining"],
                lr["avg_speed_ms"], lr["max_speed_ms"], lr["telemetry_file"],
            ))

        for tr in tire_records:
            conn.execute("""
                INSERT INTO tire_snapshots
                (session_id, lap_number, corner, temp_left, temp_mid, temp_right,
                 wear_left, wear_mid, wear_right, cold_pressure, hot_pressure)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tr["session_id"], tr["lap_number"], tr["corner"],
                tr["temp_left"], tr["temp_mid"], tr["temp_right"],
                tr["wear_left"], tr["wear_mid"], tr["wear_right"],
                tr["cold_pressure"], tr["hot_pressure"],
            ))

        conn.commit()

    elapsed = time.time() - t0
    print(f"    -> {len(lap_records)} laps ({len(timed_times)} timed), "
          f"best: {best_time:.3f}s, parsed in {elapsed:.1f}s" if best_time else
          f"    -> {len(lap_records)} laps (no timed laps), parsed in {elapsed:.1f}s")

    return session


def compute_sectors(ibt_obj, start_tick, end_tick):
    """Compute sector times by dividing track into thirds by LapDistPct.
    Returns (s1_time, s2_time, s3_time) or (None, None, None).
    """
    dist = ibt_obj.get_all("LapDistPct")
    stime = ibt_obj.get_all("SessionTime")

    boundaries = [0.3333, 0.6667]
    times = [stime[start_tick]]

    for boundary in boundaries:
        for i in range(start_tick, end_tick - 1):
            if dist[i] < boundary <= dist[i + 1]:
                # Linear interpolation
                frac = (boundary - dist[i]) / (dist[i + 1] - dist[i]) if dist[i + 1] != dist[i] else 0
                t = stime[i] + frac * (stime[i + 1] - stime[i])
                times.append(t)
                break

    times.append(stime[end_tick - 1])

    if len(times) == 4:
        return (
            round(times[1] - times[0], 3),
            round(times[2] - times[1], 3),
            round(times[3] - times[2], 3),
        )
    return (None, None, None)


def import_all(ibt_dir=None):
    """Parse all IBT files in directory, skip already imported."""
    ibt_dir = Path(ibt_dir or IBT_DIR)
    conn = init_db()

    files = sorted(ibt_dir.glob("*.ibt"))
    print(f"Found {len(files)} IBT files")

    imported = 0
    skipped = 0
    errors = 0

    for f in files:
        try:
            result = parse_ibt(f, conn)
            if result is None:
                skipped += 1
            else:
                imported += 1
        except Exception as e:
            print(f"  ERROR parsing {f.name}: {e}")
            errors += 1

    conn.close()
    print(f"\nDone: {imported} imported, {skipped} skipped, {errors} errors")
    return imported, skipped, errors


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Parse specific file
        conn = init_db()
        parse_ibt(sys.argv[1], conn)
        conn.close()
    else:
        import_all()
