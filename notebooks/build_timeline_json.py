#!/usr/bin/env python3
"""
Build timeline JSON for the Tokubetsu hidden dashboard.

Preferred input:
  data/raw/R001_0513_GR_di2_timeline.xlsx

Fallback input:
  data/raw/R001_0513_GR.fit

Output:
  docs/data/R001_0513_GR_timeline.json

The Di2Stats XLSX timeline is preferred because it contains a true sequential
Gear column. The first row contains timezone metadata and the real header begins
on row 2, so this script reads the file with header=1.

Install dependencies if needed:
  pip install pandas openpyxl fitparse

Run from repository root:
  python3 notebooks/build_timeline_json.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
DI2_XLSX_PATH = REPO_ROOT / "data" / "raw" / "R001_0513_GR_di2_timeline.xlsx"
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


def clean_number(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None
        number = float(value)
        if number != number:
            return None
        return number
    except Exception:
        return None


def normalize_di2_gear(value: Any) -> Optional[str]:
    """Normalize Di2Stats values like '1x15,1,10' to '1x15'."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text.split(",", 1)[0].strip()


def build_from_di2_xlsx() -> Dict[str, Any]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("Missing dependency: pandas. Install with: pip install pandas openpyxl") from exc

    if not DI2_XLSX_PATH.exists():
        raise FileNotFoundError(DI2_XLSX_PATH)

    df = pd.read_excel(DI2_XLSX_PATH, header=1)
    required = {"TS", "Gear"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"Di2 XLSX missing required columns: {missing}")

    df = df.dropna(subset=["TS", "Gear"]).copy()
    df["TS"] = df["TS"].apply(clean_number)
    df = df.dropna(subset=["TS"])
    df = df.sort_values("TS")

    if df.empty:
        raise SystemExit("Di2 XLSX contained no usable timestamped rows.")

    first_ts = float(df["TS"].iloc[0])
    points = []
    last_time = -999

    for _, row in df.iterrows():
        ts = clean_number(row.get("TS"))
        gear = normalize_di2_gear(row.get("Gear"))
        if ts is None or gear is None:
            continue

        time_s = int(round(ts - first_ts))

        # Di2Stats rows appear approximately every 8 seconds. Keep all rows.
        if time_s == last_time:
            continue
        last_time = time_s

        speed = clean_number(row.get("SPD"))
        grade = clean_number(row.get("GRADE"))
        cadence = clean_number(row.get("CAD"))
        power = clean_number(row.get("POW"))
        distance = clean_number(row.get("DIST"))
        elevation = clean_number(row.get("ELEV"))
        heart_rate = clean_number(row.get("HR"))

        # GRADE in this file is percent-like, so convert to decimal for consistency.
        grade_decimal = None if grade is None else grade / 100

        points.append({
            "time_s": time_s,
            "timestamp": int(ts),
            "gear": gear,
            "gear_raw": str(row.get("Gear")),
            "power": power,
            "cadence": cadence,
            "speed_kph": speed,
            "grade": grade_decimal,
            "distance_m": distance,
            "elevation_m": elevation,
            "heart_rate": heart_rate,
        })

    shifts = 0
    previous = None
    for point in points:
        current = point.get("gear")
        point["shift_event"] = previous is not None and current != previous
        if point["shift_event"]:
            shifts += 1
        previous = current

    gears = sorted({p["gear"] for p in points if p.get("gear")})

    return {
        "ride_id": "R001_0513_GR",
        "source_di2_timeline": str(DI2_XLSX_PATH.relative_to(REPO_ROOT)),
        "point_count": len(points),
        "raw_point_count": len(df),
        "has_real_gear_timeline": True,
        "fallback_lane": None,
        "gear_fields_found": ["TS", "Gear", "SPD", "GRADE", "CAD", "POW", "DIST"],
        "gear_states_found": gears,
        "shift_event_count": shifts,
        "points": points,
    }


def field_dict(record: Any) -> Dict[str, Any]:
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
    speed = get_number(values, "enhanced_speed", "speed")
    if speed is None:
        return None
    return speed * 3.6


def normalize_grade(values: Dict[str, Any]) -> Optional[float]:
    grade = get_number(values, "grade")
    if grade is None:
        return None
    if abs(grade) > 1:
        return grade / 100
    return grade


def infer_gear_label(values: Dict[str, Any]) -> Optional[str]:
    front_teeth = values.get("front_gear_teeth")
    rear_teeth = values.get("rear_gear_teeth")
    front_num = values.get("front_gear_num")
    rear_num = values.get("rear_gear_num")

    if isinstance(front_teeth, (int, float)) and isinstance(rear_teeth, (int, float)):
        return f"{int(front_teeth)}x{int(rear_teeth)}"
    if isinstance(rear_teeth, (int, float)):
        return f"1x{int(rear_teeth)}"
    if isinstance(front_num, (int, float)) and isinstance(rear_num, (int, float)):
        return f"{int(front_num)}x{int(rear_num)}"

    raw = values.get("gear") or values.get("gear_change_data")
    if raw is not None:
        return str(raw)
    return None


def build_from_fit() -> Dict[str, Any]:
    try:
        from fitparse import FitFile
    except ImportError as exc:
        raise SystemExit("Missing dependency: fitparse. Install with: pip install fitparse") from exc

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

        if any(point.get(k) is not None for k in ("gear", "power", "cadence", "speed_kph", "grade")):
            raw_points.append(point)

    has_real_gear = bool(discovered_gear_fields) and any(p.get("gear") for p in raw_points)
    if not has_real_gear:
        for point in raw_points:
            point["gear"] = "Telemetry"

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
        "has_real_gear_timeline": has_real_gear,
        "fallback_lane": None if has_real_gear else "Telemetry",
        "fit_fields_found": sorted(discovered_fields),
        "points": points,
    }


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if DI2_XLSX_PATH.exists():
        data = build_from_di2_xlsx()
        print(f"Using Di2Stats timeline XLSX: {DI2_XLSX_PATH}")
    else:
        data = build_from_fit()
        print(f"Using Garmin FIT fallback: {FIT_PATH}")

    OUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"Timeline points: {data['point_count']}")
    print(f"Real gear timeline: {data['has_real_gear_timeline']}")
    if data.get("shift_event_count") is not None:
        print(f"Shift events: {data['shift_event_count']}")


if __name__ == "__main__":
    main()
