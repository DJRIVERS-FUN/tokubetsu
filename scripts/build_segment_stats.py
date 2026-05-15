from pathlib import Path
import json
import csv
import statistics as stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT = ROOT / "processed"
OUT.mkdir(exist_ok=True)

rides = json.loads((DATA / "ride_index.json").read_text())
segments = json.loads((DATA / "segment_registry.json").read_text())

rows = []

for ride in rides:
    ride_id = ride["ride_id"]
    timeline_path = DATA / ride["timeline"].replace("data/", "")
    timeline = json.loads(timeline_path.read_text())
    points = timeline.get("points", [])

    for seg in segments:
        start_m = seg["start_m"]
        end_m = seg["end_m"]

        seg_points = [
            p for p in points
            if start_m <= float(p.get("distance_m", 0) or 0) <= end_m
        ]

        if not seg_points:
            continue

        powers = [float(p.get("power", 0) or 0) for p in seg_points]
        cadences = [float(p.get("cadence", 0) or 0) for p in seg_points]
        speeds = [float(p.get("speed_kph", 0) or 0) for p in seg_points]
        grades = [float(p.get("grade", 0) or 0) for p in seg_points]
        shifts = sum(1 for p in seg_points if p.get("shift_event"))

        gears = [p.get("gear") for p in seg_points if p.get("gear")]
        dominant_gear = max(set(gears), key=gears.count) if gears else ""

        elapsed_s = max(float(p.get("time_s", 0) or 0) for p in seg_points) - min(float(p.get("time_s", 0) or 0) for p in seg_points)
        distance_km = (end_m - start_m) / 1000

        rows.append({
            "ride_id": ride_id,
            "segment_id": seg["segment_id"],
            "segment_name": seg["name"],
            "start_m": start_m,
            "end_m": end_m,
            "distance_km": round(distance_km, 3),
            "elapsed_s": round(elapsed_s, 1),
            "avg_power": round(stats.mean(powers), 1),
            "avg_cadence": round(stats.mean(cadences), 1),
            "cadence_sd": round(stats.stdev(cadences), 1) if len(cadences) > 1 else 0,
            "avg_speed_kph": round(stats.mean(speeds), 1),
            "avg_grade": round(stats.mean(grades), 4),
            "shift_count": shifts,
            "shift_density_per_km": round(shifts / distance_km, 2) if distance_km else 0,
            "dominant_gear": dominant_gear
        })

with open(OUT / "segment_stats.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

(DATA / "segment_stats.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

print(f"Wrote {OUT / 'segment_stats.csv'}")
print(f"Wrote {DATA / 'segment_stats.json'}")
print(f"Rows: {len(rows)}")
