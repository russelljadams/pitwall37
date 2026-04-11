"""Setup model for Dallara F324 — validates changes, predicts effects, compares setups.

Built from 118 sessions of real setup data + iRacing garage knowledge.
The engineer uses this to validate suggestions and predict consequences.
"""

import json
import re
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "pitwall37.db"
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def _parse_num(s):
    if not s:
        return None
    m = re.search(r'[-+]?[\d.]+', str(s))
    return float(m.group()) if m else None


# ── Observed ranges from 118 real sessions ──
OBSERVED_RANGES = {
    "front_flap_angle_deg": (9, 21),
    "rear_upper_flap_deg": (9, 25),
    "rear_beam_wing_deg": (4, 12),
    "front_ride_height_mm": (15.1, 21.0),
    "torsion_bar_od_mm": (12.15, 14.16),
    "torsion_bar_preload_turns": (-0.026, -0.020),
    "heave_spring_nmm": (0, 140),
    "heave_perch_offset_mm": (96.2, 98.0),
    "front_pushrod_offset_mm": (-30.0, -7.0),
    "rear_ride_height_mm": (32.6, 41.5),
    "rear_spring_rate_nmm": (122, 184),
    "rear_spring_perch_offset_mm": (102.0, 108.8),
    "rear_pushrod_offset_mm": (3.0, 40.0),
    "front_comp_clicks": (4, 11),
    "front_rbd_clicks": (0, 7),
    "rear_comp_clicks": (4, 9),
    "rear_rbd_clicks": (0, 9),
    "front_camber_deg": (-4.0, -3.7),
    "rear_camber_deg": (-3.0, -2.2),
    "front_toe_mm": (-2.0, -1.0),
    "rear_toe_mm": (0.0, 1.0),
    "brake_bias_pct": (53.5, 58.0),
    "diff_preload_nm": (20, 80),
    "diff_clutch_faces": (2, 8),
    "diff_coast_deg": (45, 80),
    "diff_drive_deg": (45, 80),
}

DISCRETE_OPTIONS = {
    "aero_package": ["Low DF", "Medium DF", "High DF"],
    "front_flap_config": ["Low DF", "High DF"],
    "front_flap_gurney": ["None", "5mm", "10mm"],
    "gear_stack": ["Extra Short", "Short", "Medium", "Long"],
    "front_arb_size": ["Soft", "Medium", "Stiff", "Disconnected"],
    "front_arb_blades": list(range(1, 6)),
    "rear_arb_size": ["Soft", "Medium", "Stiff", "Disconnected"],
    "rear_arb_arm": ["Position 1", "Position 2", "Position 3", "Position 4"],
}

# ── Directional change model ──
# How each input parameter affects computed outputs.
# Built from physics + confirmed by observing changes across 17 unique configs.
# Format: parameter → {output: (direction, magnitude_estimate, confidence)}
#   direction: +1 = increasing input increases output, -1 = decreasing
#   magnitude: qualitative ("small", "medium", "large")
#   confidence: how sure we are ("confirmed" = seen in data, "physics" = from theory)
CHANGE_EFFECTS = {
    "front_flap_angle_deg": {
        "front_rh_at_speed": ("-", "medium", "confirmed",
            "More front wing pushes front down at speed. ~1mm per 3-4° change."),
        "aero_balance": ("+", "medium", "confirmed",
            "Shifts balance forward. ~0.5% per degree."),
        "downforce_trim": ("+", "large", "confirmed",
            "Adds overall downforce. Major front DF contributor."),
        "drag_trim": ("+", "small", "confirmed",
            "Slight drag increase with angle."),
    },
    "rear_upper_flap_deg": {
        "rear_rh_at_speed": ("-", "large", "confirmed",
            "Main rear downforce element. Pushes rear down hard at speed."),
        "aero_balance": ("-", "large", "confirmed",
            "Shifts balance rearward. ~0.3% per degree. Biggest balance lever."),
        "downforce_trim": ("+", "large", "confirmed",
            "Primary overall downforce control."),
        "drag_trim": ("+", "large", "confirmed",
            "Biggest drag contributor. Each degree costs straight-line speed."),
    },
    "rear_beam_wing_deg": {
        "rear_rh_at_speed": ("-", "medium", "confirmed",
            "Secondary rear DF element. Less effect than upper flap."),
        "aero_balance": ("-", "small", "confirmed",
            "Slightly shifts balance rearward."),
        "downforce_trim": ("+", "medium", "confirmed",
            "Moderate downforce gain."),
        "drag_trim": ("+", "medium", "confirmed",
            "Moderate drag increase."),
    },
    "torsion_bar_od_mm": {
        "front_rh_at_speed": ("+", "medium", "confirmed",
            "Stiffer front spring resists aero compression. Keeps front higher at speed."),
        "front_ride_height_mm": ("~", "small", "physics",
            "May slightly affect static RH through spring deflection."),
    },
    "rear_spring_rate_nmm": {
        "rear_rh_at_speed": ("+", "medium", "confirmed",
            "Stiffer rear resists compression under aero load."),
        "rear_ride_height_mm": ("~", "small", "physics",
            "May slightly affect static RH through deflection."),
    },
    "heave_spring_nmm": {
        "front_rh_at_speed": ("+", "medium", "confirmed",
            "Third spring prevents front from dropping under aero. 0=disconnected."),
        "front_ride_height_mm": ("~", "small", "physics",
            "Active heave adds resistance to vertical movement."),
    },
    "front_pushrod_offset_mm": {
        "front_ride_height_mm": ("-", "large", "confirmed",
            "Direct front RH control. More negative = lower front. PRIMARY tool."),
        "front_rh_at_speed": ("-", "medium", "physics",
            "Lower static = lower at speed (all else equal)."),
    },
    "rear_pushrod_offset_mm": {
        "rear_ride_height_mm": ("+", "large", "confirmed",
            "Direct rear RH control. More positive = higher rear. PRIMARY tool."),
        "rear_rh_at_speed": ("+", "medium", "physics",
            "Higher static = higher at speed (all else equal)."),
    },
    "front_camber_deg": {
        "front_ride_height_mm": ("+", "small", "confirmed",
            "More negative camber slightly raises effective ride height. ~0.1-0.3mm per 0.1°."),
    },
    "rear_camber_deg": {
        "rear_ride_height_mm": ("+", "small", "confirmed",
            "Same as front — more negative slightly raises RH."),
    },
    "torsion_bar_preload_turns": {
        "front_ride_height_mm": ("-", "medium", "physics",
            "More negative preload = more weight on corner = higher RH."),
        "cross_weight_pct": ("varies", "medium", "physics",
            "Asymmetric changes shift diagonal weight."),
    },
    "rear_spring_perch_offset_mm": {
        "rear_ride_height_mm": ("-", "medium", "physics",
            "Lower offset = more preload = higher RH."),
        "cross_weight_pct": ("varies", "medium", "physics",
            "Asymmetric changes shift diagonal weight."),
    },
}

# ── Inspection rules ──
INSPECTION_RULES = [
    "Ride height at speed must remain positive (>0mm). This is the #1 cause of inspection failures.",
    "Aero package/flap config must match: High DF pkg needs High DF flap, Low DF pkg needs Low DF flap, Medium allows either.",
    "Rear spring rates must be symmetrical (L/R same) — homologation rule.",
    "Observed safe static minimums: front 15.1mm, rear 32.6mm.",
]

# ── Known-good configurations (lookup table) ──
# Every unique input→output combo from 118 sessions that passed inspection.
def _load_known_configs():
    """Load all unique configs from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            'SELECT setup_json FROM sessions WHERE setup_json IS NOT NULL'
        ).fetchall()
        conn.close()
    except Exception:
        return []

    configs = {}
    for r in rows:
        s = json.loads(r[0])
        ac = s.get('TiresAero', {}).get('AeroCalculator', {})
        aero = s.get('TiresAero', {}).get('AeroSetup', {})
        ch = s.get('Chassis', {})
        lf = ch.get('LeftFront', {})
        rear = ch.get('Rear', {})
        lr = ch.get('LeftRear', {})
        front = ch.get('Front', {})

        key = (
            _parse_num(aero.get('FrontFlapAngle')),
            _parse_num(aero.get('RearUpperFlap')),
            _parse_num(aero.get('RearBeamWing')),
            _parse_num(lf.get('TorsionBarOD')),
            _parse_num(lr.get('SpringRate')),
            _parse_num(front.get('HeaveSpring')),
            _parse_num(lf.get('RideHeight')),
            _parse_num(rear.get('RideHeight')),
            _parse_num(front.get('PRodLengthOffset')),
            _parse_num(rear.get('PRodLengthOffset')),
        )
        configs[key] = {
            'inputs': {
                'front_flap': key[0], 'rear_upper': key[1], 'beam_wing': key[2],
                'torsion_od': key[3], 'rear_spring': key[4], 'heave_spring': key[5],
                'front_rh_static': key[6], 'rear_rh_static': key[7],
                'front_prod': key[8], 'rear_prod': key[9],
            },
            'outputs': {
                'front_rh_at_speed': _parse_num(ac.get('FrontRhAtSpeed')),
                'rear_rh_at_speed': _parse_num(ac.get('RearRhAtSpeed')),
                'downforce_trim': _parse_num(ac.get('DownforceTrim')),
                'drag_trim': _parse_num(ac.get('DragTrim')),
                'aero_balance': _parse_num(ac.get('AeroBalance')),
                'balance_trim': _parse_num(ac.get('BalanceTrim')),
                'df_to_drag': _parse_num(ac.get('DownforceToDrag')),
            },
        }
    return list(configs.values())


def find_nearest_config(setup_params: dict) -> dict | None:
    """Find the known config most similar to the given parameters.
    Returns the closest match with its computed outputs."""
    configs = _load_known_configs()
    if not configs:
        return None

    best = None
    best_dist = float('inf')
    for cfg in configs:
        dist = 0
        for k, v in setup_params.items():
            if k in cfg['inputs'] and v is not None and cfg['inputs'][k] is not None:
                # Normalize by observed range
                range_key = {
                    'front_flap': 'front_flap_angle_deg',
                    'rear_upper': 'rear_upper_flap_deg',
                    'beam_wing': 'rear_beam_wing_deg',
                    'torsion_od': 'torsion_bar_od_mm',
                    'rear_spring': 'rear_spring_rate_nmm',
                    'heave_spring': 'heave_spring_nmm',
                    'front_rh_static': 'front_ride_height_mm',
                    'rear_rh_static': 'rear_ride_height_mm',
                }.get(k)
                if range_key and range_key in OBSERVED_RANGES:
                    lo, hi = OBSERVED_RANGES[range_key]
                    span = hi - lo if hi > lo else 1
                    dist += ((v - cfg['inputs'][k]) / span) ** 2
                else:
                    dist += (v - cfg['inputs'][k]) ** 2
        if dist < best_dist:
            best_dist = dist
            best = cfg
    return best


def predict_change_effects(param: str, direction: str = "increase") -> list[str]:
    """Describe what happens when a parameter is increased/decreased."""
    effects = CHANGE_EFFECTS.get(param, {})
    if not effects:
        return [f"No known effects data for {param}."]

    results = []
    for output, (dir_sign, magnitude, confidence, explanation) in effects.items():
        if dir_sign == "~":
            results.append(f"  {output}: minor/indirect effect — {explanation}")
        elif dir_sign == "varies":
            results.append(f"  {output}: depends on context — {explanation}")
        else:
            actual_dir = dir_sign if direction == "increase" else ("+" if dir_sign == "-" else "-")
            results.append(
                f"  {output}: {actual_dir} ({magnitude}) — {explanation} [{confidence}]"
            )
    return results


def compare_setups(setup_a: dict, setup_b: dict) -> str:
    """Generate a human-readable diff between two setup JSONs."""
    lines = []

    def _flatten(obj, prefix=""):
        flat = {}
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                flat.update(_flatten(v, key))
            else:
                flat[key] = v
        return flat

    flat_a = _flatten(setup_a)
    flat_b = _flatten(setup_b)
    all_keys = sorted(set(flat_a.keys()) | set(flat_b.keys()))

    # Skip noisy keys
    skip = {'UpdateCount'}
    diffs = []
    for key in all_keys:
        short_key = key.split('.')[-1]
        if short_key in skip:
            continue
        va = flat_a.get(key, "—")
        vb = flat_b.get(key, "—")
        if str(va) != str(vb):
            # Try to compute numeric delta
            na, nb = _parse_num(va), _parse_num(vb)
            delta = ""
            if na is not None and nb is not None:
                d = nb - na
                delta = f" (Δ {d:+.2f})"
            diffs.append(f"  {key}: {va} → {vb}{delta}")

    if not diffs:
        return "Setups are identical."

    lines.append(f"Setup differences ({len(diffs)} parameters changed):")
    lines.extend(diffs)
    return "\n".join(lines)


def validate_setup_change(param: str, new_value, current_setup: dict = None) -> dict:
    """Validate a proposed change against constraints and predict effects."""
    result = {"valid": True, "warnings": [], "side_effects": [], "predictions": []}

    # Check observed ranges
    if param in OBSERVED_RANGES:
        lo, hi = OBSERVED_RANGES[param]
        result["observed_range"] = (lo, hi)
        try:
            val = float(new_value)
            if val < lo or val > hi:
                result["warnings"].append(
                    f"{param}={new_value} is OUTSIDE observed range [{lo}, {hi}]. "
                    f"Never seen in 118 sessions — may fail inspection."
                )
                result["valid"] = False
        except (ValueError, TypeError):
            pass

    # Check discrete options
    if param in DISCRETE_OPTIONS:
        if new_value not in DISCRETE_OPTIONS[param]:
            result["warnings"].append(
                f"{param}={new_value} is not valid. Options: {DISCRETE_OPTIONS[param]}"
            )
            result["valid"] = False

    # Predict effects
    effects = predict_change_effects(param, "increase")
    if effects:
        result["predictions"] = effects

    return result


def get_setup_knowledge_for_prompt() -> str:
    """Generate the setup constraints text for the engineer's system prompt."""
    lines = []
    lines.append("SETUP CONSTRAINTS — Dallara F324 in iRacing SFL")
    lines.append("=" * 50)
    lines.append("")
    lines.append("CRITICAL: Validate EVERY setup suggestion against these constraints.")
    lines.append("These ranges come from 118 real sessions that passed tech inspection.")
    lines.append("")

    lines.append("── OBSERVED SAFE RANGES ──")
    for param, (lo, hi) in sorted(OBSERVED_RANGES.items()):
        lines.append(f"  {param}: {lo} to {hi}")

    lines.append("")
    lines.append("── DISCRETE OPTIONS ──")
    for param, opts in sorted(DISCRETE_OPTIONS.items()):
        lines.append(f"  {param}: {opts}")

    lines.append("")
    lines.append("── CHANGE EFFECTS (what happens when you adjust each parameter) ──")
    for param, effects in sorted(CHANGE_EFFECTS.items()):
        lines.append(f"  {param}:")
        for output, (direction, magnitude, confidence, explanation) in effects.items():
            lines.append(f"    → {output}: {direction} ({magnitude}) — {explanation}")

    lines.append("")
    lines.append("── INSPECTION RULES ──")
    for rule in INSPECTION_RULES:
        lines.append(f"  - {rule}")

    lines.append("")
    lines.append("── RIDE HEIGHT AT SPEED ──")
    lines.append("The AeroCalculator section shows computed values. These determine inspection pass/fail.")
    lines.append("ALWAYS check FrontRhAtSpeed and RearRhAtSpeed before suggesting aero or spring changes.")
    lines.append("If either approaches 0mm, the car WILL fail inspection or bottom out.")
    lines.append("")
    lines.append("── SETUP COMPARISON ──")
    lines.append("When comparing two sessions, focus on:")
    lines.append("  1. What setup parameters changed between sessions")
    lines.append("  2. How those changes affected the AeroCalculator outputs")
    lines.append("  3. How lap times and tire behavior changed as a result")
    lines.append("  4. Whether the changes moved in the right direction")

    return "\n".join(lines)


if __name__ == "__main__":
    print(get_setup_knowledge_for_prompt())
    print()
    print("Known configs:", len(_load_known_configs()))
    print()
    print("Effects of increasing rear_upper_flap_deg:")
    for line in predict_change_effects("rear_upper_flap_deg", "increase"):
        print(line)
