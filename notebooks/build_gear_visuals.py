"""
TOKUBETSU Gear Visualization Builder

Creates dashboard-ready JSON from a Di2Stats aggregate gear-state export.

Important
---------
GitHub Pages is currently publishing the /docs folder. Therefore, dashboard-facing
JSON should be written to docs/data/ rather than repository-level processed/.

Example:
  python3 notebooks/build_gear_visuals.py \
    --ride-id R001_0513_GR \
    --di2 ~/Desktop/"Tokubetsu Local"/R001_0513_GR_di2.csv \
    --out docs/data/R001_0513_GR_gear_summary.json
"""

from __future__ import annotations

import argparse

def normalize_gear(g):
    s = str(g).strip()

    if "," in s:
        s = s.split(",")[0].strip()

    replacements = {
        "79x24": "1x24",
        "74x24": "1x24",
        "1x11": "1x10",
        "1x13": "1x12",
        "1x15": "1x14",
        "1x17": "1x16",
        "1x19": "1x18",
        "1x22": "1x21",
        "1x25": "1x24",
        "1x32": "1x33",
        "1x36": "1x39",
        "1x42": "1x45",
        "1x50": "1x51",
    }

    return replacements.get(s, s)


import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


def safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def safe_int(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(float(value))
    except Exception:
        return 0


def build_gear_summary(ride_id: str, di2_path: Path) -> Dict[str, Any]:
    df = pd.read_csv(di2_path)
    required = ["Gear", "Total Time", "Avg CAD", "Avg POW", "Avg Grade", "Avg KPH"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required Di2 aggregate columns: {missing}")

    total_time = safe_int(df["Total Time"].sum())
    total_count = safe_int(df["Count"].sum()) if "Count" in df.columns else 0
    rows: List[Dict[str, Any]] = []

    for _, row in df.sort_values("Total Time", ascending=False).iterrows():
        gear = str(row.get("Gear", ""))
        time_s = safe_int(row.get("Total Time", 0))
        rows.append({
            "gear": normalize_gear(gear),
            "time_s": time_s,
            "time_pct": round((time_s / total_time * 100), 2) if total_time else 0,
            "count": safe_int(row.get("Count", 0)),
            "avg_cadence": safe_float(row.get("Avg CAD", 0)),
            "max_cadence": safe_float(row.get("Max CAD", 0)),
            "avg_power": safe_float(row.get("Avg POW", 0)),
            "max_power": safe_float(row.get("Max POW", 0)),
            "avg_grade": round(safe_float(row.get("Avg Grade", 0)), 4),
            "avg_kph": safe_float(row.get("Avg KPH", 0)),
            "gear_inches": safe_float(row.get("GearInches", 0)),
        })

    cadence_values = [r["avg_cadence"] for r in rows if r["avg_cadence"] > 0]
    power_values = [r["avg_power"] for r in rows if r["avg_power"] > 0]

    return {
        "ride_id": ride_id,
        "source_type": "di2stats_aggregate_gear_state",
        "total_time_s": total_time,
        "total_count_proxy": total_count,
        "gear_states": len(rows),
        "dominant_gear": rows[0]["gear"] if rows else "",
        "mean_avg_cadence_by_gear": round(sum(cadence_values) / len(cadence_values), 2) if cadence_values else 0,
        "mean_avg_power_by_gear": round(sum(power_values) / len(power_values), 2) if power_values else 0,
        "gear_occupancy": rows,
        "note": "Di2Stats aggregate file: supports gear occupancy and cadence/power-by-gear, not exact shift timing."
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TOKUBETSU gear visualization JSON")
    parser.add_argument("--ride-id", required=True)
    parser.add_argument("--di2", required=True, type=Path)
    parser.add_argument("--out", default=None, type=Path)
    args = parser.parse_args()

    output_path = args.out or Path("docs/data") / f"{args.ride_id}_gear_summary.json"
    summary = build_gear_summary(args.ride_id, args.di2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote {output_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
