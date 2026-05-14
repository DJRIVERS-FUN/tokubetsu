"""
TOKUBETSU FIT + Di2 Synchronization Engine

Purpose
-------
This script provides the first operational ingestion layer for the TOKUBETSU
research workflow.

It is designed to:

1. parse Garmin FIT telemetry when a FIT parser is available;
2. ingest Di2Stats exports;
3. classify whether the Di2 file is an aggregate gear-state file or a
   timestamped shift-event file;
4. summarize gear-state behaviour;
5. load the monitored Strava segment registry;
6. generate ride-level JSON analytics for the public dashboard.

Current limitation
------------------
The first sample file, R001_0513_GR_di2.csv, is an aggregate Di2Stats export.
It contains gear-state summaries but not second-by-second shift events.
Therefore, exact shift timing cannot yet be reconstructed from that file alone.

For full synchronization, future Di2 exports should ideally include:

- timestamp
- gear before / after
- rear sprocket
- cadence
- power
- elapsed time

or the Garmin FIT file should contain developer fields for gear state / shifts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


AGGREGATE_DI2_COLUMNS = {
    "Gear",
    "Total Time",
    "Count",
    "Avg Grade",
    "Avg CAD",
    "Avg POW",
    "Avg KPH",
}

TIMESTAMP_CANDIDATES = ["timestamp", "time", "date_time", "datetime", "elapsed_time"]


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return pd.read_csv(path)


def classify_di2_export(df: pd.DataFrame) -> str:
    columns = set(df.columns)
    lower_columns = {c.lower() for c in df.columns}

    if AGGREGATE_DI2_COLUMNS.issubset(columns):
        return "aggregate_gear_state"

    if any(c in lower_columns for c in TIMESTAMP_CANDIDATES):
        return "timestamped_event_or_timeseries"

    return "unknown"


def summarize_aggregate_di2(df: pd.DataFrame) -> Dict[str, Any]:
    total_time = int(df["Total Time"].sum()) if "Total Time" in df.columns else 0
    total_count = int(df["Count"].sum()) if "Count" in df.columns else 0

    gear_rows: List[Dict[str, Any]] = []
    sort_col = "Total Time" if "Total Time" in df.columns else df.columns[0]

    for _, row in df.sort_values(sort_col, ascending=False).iterrows():
        total_time_s = int(row.get("Total Time", 0))
        gear_rows.append(
            {
                "gear": str(row.get("Gear", "")),
                "gear_inches": float(row.get("GearInches", 0)),
                "total_time_s": total_time_s,
                "time_share_pct": round((total_time_s / total_time * 100), 2) if total_time else 0,
                "shift_count_proxy": int(row.get("Count", 0)),
                "avg_grade": round(float(row.get("Avg Grade", 0)), 4),
                "avg_cadence": float(row.get("Avg CAD", 0)),
                "max_cadence": float(row.get("Max CAD", 0)),
                "avg_power": float(row.get("Avg POW", 0)),
                "max_power": float(row.get("Max POW", 0)),
                "avg_kph": float(row.get("Avg KPH", 0)),
                "max_kph": float(row.get("Max KPH", 0)),
            }
        )

    dominant_gear = gear_rows[0]["gear"] if gear_rows else None

    return {
        "di2_export_type": "aggregate_gear_state",
        "total_di2_time_s": total_time,
        "total_shift_count_proxy": total_count,
        "gear_states_observed": len(gear_rows),
        "dominant_gear": dominant_gear,
        "gear_occupancy": gear_rows,
        "interpretation_note": (
            "Aggregate Di2Stats export detected. Gear occupancy and cadence/power-by-gear "
            "summaries are available, but exact shift timing requires timestamped shift events."
        ),
    }


def summarize_timestamped_di2(df: pd.DataFrame) -> Dict[str, Any]:
    lower_map = {c.lower(): c for c in df.columns}
    time_col = next((lower_map[c] for c in TIMESTAMP_CANDIDATES if c in lower_map), None)

    return {
        "di2_export_type": "timestamped_event_or_timeseries",
        "rows": int(len(df)),
        "columns": list(df.columns),
        "timestamp_column": time_col,
        "interpretation_note": (
            "Timestamped Di2-style data detected. This can be aligned with FIT telemetry "
            "once FIT parsing is active and timestamps are normalized."
        ),
    }


def parse_fit_summary(fit_path: Path | None) -> Dict[str, Any]:
    """Parse basic FIT telemetry summary when fitparse is installed.

    The repository does not commit raw FIT files. Run this locally with the FIT
    file path if deeper telemetry parsing is needed.
    """

    if fit_path is None:
        return {"fit_status": "not_supplied"}

    if not fit_path.exists():
        return {"fit_status": "missing", "fit_path": str(fit_path)}

    try:
        from fitparse import FitFile  # type: ignore
    except Exception:
        return {
            "fit_status": "parser_not_installed",
            "fit_path": str(fit_path),
            "required_package": "fitparse",
            "install_hint": "pip install fitparse",
        }

    fitfile = FitFile(str(fit_path))
    records = []

    for record in fitfile.get_messages("record"):
        values = {field.name: field.value for field in record}
        records.append(values)

    if not records:
        return {"fit_status": "parsed_no_records", "fit_path": str(fit_path)}

    df = pd.DataFrame(records)

    summary = {
        "fit_status": "parsed",
        "fit_path": str(fit_path),
        "record_count": int(len(df)),
        "available_fields": list(df.columns),
    }

    for col in ["power", "cadence", "speed", "heart_rate", "altitude"]:
        if col in df.columns:
            numeric = pd.to_numeric(df[col], errors="coerce")
            summary[f"{col}_mean"] = round(float(numeric.mean()), 2) if numeric.notna().any() else None
            summary[f"{col}_max"] = round(float(numeric.max()), 2) if numeric.notna().any() else None

    return summary


def load_segment_registry(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"segment_registry_status": "missing", "registered_segments": 0, "segments": []}

    df = pd.read_csv(path)
    return {
        "segment_registry_status": "loaded",
        "registered_segments": int(len(df)),
        "segments": df.fillna("").to_dict(orient="records"),
        "segment_detection_note": (
            "Automatic detection requires segment geometry or Strava streams. Current registry "
            "provides IDs/URLs and classes for matching once segment geometry is available."
        ),
    }


def build_ride_analytics(
    ride_id: str,
    di2_path: Path,
    fit_path: Path | None,
    segment_registry_path: Path,
    output_path: Path,
) -> Dict[str, Any]:
    di2_df = load_csv(di2_path)
    di2_type = classify_di2_export(di2_df)

    if di2_type == "aggregate_gear_state":
        di2_summary = summarize_aggregate_di2(di2_df)
    elif di2_type == "timestamped_event_or_timeseries":
        di2_summary = summarize_timestamped_di2(di2_df)
    else:
        di2_summary = {
            "di2_export_type": "unknown",
            "rows": int(len(di2_df)),
            "columns": list(di2_df.columns),
        }

    analytics = {
        "ride_id": ride_id,
        "fit_summary": parse_fit_summary(fit_path),
        "di2_summary": di2_summary,
        "segment_registry": load_segment_registry(segment_registry_path),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2)

    return analytics


def main() -> None:
    parser = argparse.ArgumentParser(description="TOKUBETSU FIT + Di2 synchronization engine")
    parser.add_argument("--ride-id", required=True)
    parser.add_argument("--di2", required=True, type=Path)
    parser.add_argument("--fit", required=False, type=Path)
    parser.add_argument("--segments", default=Path("metadata/segment_registry.csv"), type=Path)
    parser.add_argument("--out", required=True, type=Path)

    args = parser.parse_args()

    analytics = build_ride_analytics(
        ride_id=args.ride_id,
        di2_path=args.di2,
        fit_path=args.fit,
        segment_registry_path=args.segments,
        output_path=args.out,
    )

    print(json.dumps(analytics, indent=2))


if __name__ == "__main__":
    main()
