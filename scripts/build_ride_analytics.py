from pathlib import Path
import json
import csv
import statistics as stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT_PROCESSED = ROOT / "processed"
OUT_PROCESSED.mkdir(exist_ok=True)

ride_index = json.loads((DATA / "ride_index.json").read_text())

def zone_for_gear(gear):
    try:
        cog = int(str(gear).split("x")[1])
    except Exception:
        return "unknown"
    if cog >= 39:
        return "climbing"
    if cog >= 24:
        return "midrange"
    return "high_speed"

def terrain_for_grade(g):
    if g > 0.03:
        return "climbing"
    if g < -0.03:
        return "descending"
    return "rolling"

master_rows = []
ride_summaries = []

for ride in ride_index:
    ride_id = ride["ride_id"]
    timeline_path = DATA / ride["timeline"].replace("data/", "")
    gear_path = DATA / ride["gear"].replace("data/", "")

    timeline = json.loads(timeline_path.read_text())
    gear_summary = json.loads(gear_path.read_text())

    points = timeline.get("points", [])
    if not points:
        continue

    max_distance_m = max(float(p.get("distance_m", 0) or 0) for p in points)
    distance_km = max_distance_m / 1000 if max_distance_m else 0
    shift_count = int(timeline.get("shift_event_count", 0))
    shift_frequency_per_km = shift_count / distance_km if distance_km else None

    for p in points:
        gear = str(p.get("gear", "unknown"))
        row = {
            "ride_id": ride_id,
            "time_s": p.get("time_s"),
            "gear": gear,
            "cassette_zone": zone_for_gear(gear),
            "terrain": terrain_for_grade(float(p.get("grade", 0) or 0)),
            "cadence": p.get("cadence"),
            "power": p.get("power"),
            "speed_kph": p.get("speed_kph"),
            "grade": p.get("grade"),
            "distance_m": p.get("distance_m"),
            "shift_event": p.get("shift_event"),
        }
        master_rows.append(row)

    ride_summaries.append({
        "ride_id": ride_id,
        "timeline_points": len(points),
        "shift_count": shift_count,
        "distance_km": round(distance_km, 3),
        "shift_frequency_per_km": round(shift_frequency_per_km, 3) if shift_frequency_per_km is not None else None,
        "dominant_gear": gear_summary.get("dominant_gear"),
        "total_time_s": gear_summary.get("total_time_s"),
    })

def grouped(rows, key):
    groups = {}
    for r in rows:
        groups.setdefault(r[key], []).append(r)
    return groups

cadence_by_gear = []
for gear, rows in grouped(master_rows, "gear").items():
    vals = [float(r["cadence"]) for r in rows if r["cadence"] not in (None, "")]
    cadence_by_gear.append({
        "gear": gear,
        "n": len(vals),
        "mean_cadence": round(stats.mean(vals), 2) if vals else None,
        "cadence_sd": round(stats.stdev(vals), 2) if len(vals) > 1 else 0,
    })

power_by_zone = []
for zone, rows in grouped(master_rows, "cassette_zone").items():
    vals = [float(r["power"]) for r in rows if r["power"] not in (None, "")]
    mean = stats.mean(vals) if vals else None
    sd = stats.stdev(vals) if len(vals) > 1 else 0
    power_by_zone.append({
        "cassette_zone": zone,
        "n": len(vals),
        "mean_power": round(mean, 2) if mean else None,
        "power_sd": round(sd, 2),
        "power_cv": round(sd / mean, 3) if mean else None,
    })

terrain_gear_occupancy = []
for terrain, rows in grouped(master_rows, "terrain").items():
    total = len(rows)
    for gear, gear_rows in grouped(rows, "gear").items():
        terrain_gear_occupancy.append({
            "terrain": terrain,
            "gear": gear,
            "count": len(gear_rows),
            "pct": round((len(gear_rows) / total) * 100, 2) if total else 0,
        })

analytics = {
    "rides": ride_summaries,
    "cadence_variance_by_gear": cadence_by_gear,
    "power_stability_by_cassette_zone": power_by_zone,
    "terrain_gear_occupancy": terrain_gear_occupancy,
}

(DATA / "comparative_analytics.json").write_text(json.dumps(analytics, indent=2), encoding="utf-8")

with open(OUT_PROCESSED / "master_telemetry.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=master_rows[0].keys())
    writer.writeheader()
    writer.writerows(master_rows)

print("Wrote docs/data/comparative_analytics.json")
print("Wrote processed/master_telemetry.csv")
print(f"Rows: {len(master_rows)}")
print(f"Rides: {len(ride_summaries)}")
