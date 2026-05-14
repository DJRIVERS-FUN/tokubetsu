#!/usr/bin/env python3
"""
Build gear-state timeline JSON for the Tokubetsu hidden dashboard.

Input:
  data/raw/R001_0513_GR.fit

Output:
  docs/data/R001_0513_GR_timeline.json

Notes:
  - This script reads Garmin FIT record messages.
  - It looks for time, power, cadence, speed, grade and gear-related fields.
  - If gear fields are absent from the FIT file, the output will still contain
    telemetry points but gear values will be null. In that case, a true gear
    timeline requires a time-series Di2 export rather than the aggregate
    Di2Stats CSV currently stored in data/raw/R001_0513_GR_di2.csv.

Install dependency if needed:
  pip install fitparse

Run from repository root:
  python notebooks/build_timeline_json.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:
    from fitparse import FitFile
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: fitparse\n"
        "Install it with: pip install fitparse"
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
FIT_PATH = REPO_ROOT / "data" / "raw" / "R001_0513_GR.fit"
OUT_PATH = REPO_ROOT / "docs" / "data" / "R001_0513_GR_timeline.json"

GEAR_FIELD_CANDIDATES = (
    "gear",
    "front_gear",
    "rear_gear",
    "front_gear_num",
    "front_gear_teeth",
    "rear_gear_num",
    "rear_gear_teeth",
    "gear_change_data",
)


def field_dict(record: Any) -> Dict[str, Any]:
    """Convert a FIT record message into a simple field dictionary."""
    values: Dict[str, Any] = {}
    for field in record:
        try:
            values[field.name] = field.value
        except Exception:
            continue
    return values


def get_number(values: Dict[str, Any], *names: str) -> Optional[float]:
    for name in names:
        value = values.get(name)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def normalize_speed_kph(values: Dict[str, Any]) -> Optional[float]:
    # fitparse usually converts enhanced_speed/speed to m/s.
    speed = get_number(values, "enhanced_speed", "speed")
    if speed is None:
        return None
    return speed * 3.6


def normalize_grade(values: Dict[str, Any]) -> Optional[float]:
    grade = get_number(values, "grade")
    if grade is None:
        return None
    # Garmin grade may already be in percent. The dashboard expects decimal.
    # If magnitude is clearly percent-like, convert to decimal.
    if abs(grade) > 1:
        return grade / 100
    return grade


def infer_gear_label(values: Dict[str, Any]) -> Optional[str]:
    """Infer a display label such as 1x39 when FIT gear fields are present."""
    front_teeth = values.get("front_gear_teeth")
    rear_teeth = values.get("rear_gear_teeth")
    front_num = values.get("front_gear_num")
    rear_num = values.get("rear_gear_num")

    if isinstance(front_teeth, (int, float)) and isinstance(rear_teeth, (int, float)):
        return f"{int(front_teeth)}x{int(rear_teeth)}"

    # For 1x systems, rear gear teeth are sometimes present without front teeth.
    if isinstance(rear_teeth, (int, float)):
        return f"1x{int(rear_teeth)}"

    if isinstance(front_num, (int, float)) and isinstance(rear_num, (int, float)):
        return f"{int(front_num)}x{int(rear_num)}"

    raw = values.get("gear") or values.get("gear_change_data")
    if raw is not None:
        return str(raw)

    return None


def build_points() -> Dict[str, Any]:
    if not FIT_PATH.exists():
        raise SystemExit(f"FIT file not found: {FIT_PATH}")

    fit = FitFile(str(FIT_PATH))
    raw_points = []
    first_timestamp = None
    discovered_fields = set()
    discovered_gear_fields = set()

    for record in fit.get_messages("record"):
        values = field_dict(record)
        discovered_fields.update(values.keys())
        timestamp = values.get("timestamp")
        if timestamp is None:
            continue
        if first_timestamp is None:
            first_timestamp = timestamp
        try:
            time_s = int(round((timestamp - first_timestamp).total_seconds()))
        except Exception:
            continue

        for field_name in GEAR_FIELD_CANDIDATES:
            if field_name in values and values.get(field_name) is not None:
                discovered_gear_fields.add(field_name)

        point = {
            "time_s": time_s,
            "gear": infer_gear_label(values),
            "power": get_number(values, "power"),
            "cadence": get_number(values, "cadence"),
            "speed_kph": normalize_speed_kph(values),
            "grade": normalize_grade(values),
        }

        # Keep points with at least some useful telemetry.
        if any(point.get(k) is not None for k in ("gear", "power", "cadence", "speed_kph", "grade")):
            raw_points.append(point)

    # Downsample only if very dense, keeping approximately one point every 2 seconds.
    points = []
    last_time = -999
    for point in raw_points:
        if point["time_s"] - last_time >= 2:
            points.append(point)
            last_time = point["time_s"]

    return {
        "ride_id": "R001_0513_GR",
        "source_fit": str(FIT_PATH.relative_to(REPO_ROOT)),
        "point_count": len(points),
        "raw_point_count": len(raw_points),
        "gear_fields_found": sorted(discovered_gear_fields),
        "fit_fields_found": sorted(discovered_fields),
        "points": points,
    }


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = build_points()
    OUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"Timeline points: {data['point_count']}")
    print(f"Gear fields found: {data['gear_fields_found']}")
    if not data["gear_fields_found"]:
        print("WARNING: No gear fields found in FIT record messages.")
        print("A true gear-state timeline requires a time-series Di2 export.")


if __name__ == "__main__":
    main()
